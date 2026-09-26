// rx_classify.v - run length in samples -> 1, 2 or 3 UI.
//
// Two quantities are learned from the line itself, so neither the ring rate
// (44.1 or 48 kHz) nor the receiver's pulse-width distortion has to be known:
//
//   ui  - one UI in samples, Q8.8.  Starts at 17.0, between 16.1 (48 kHz) and
//         17.5 (44.1 kHz); both classify correctly from the first run.
//   b   - pulse-width bias, Q8.8 signed. MOST SP4 lets a HIGH pulse be up to
//         +0.40 / -0.257 UI off and a LOW pulse the mirror of that; a single
//         1.5 UI threshold then leaves no margin. HIGH runs are corrected by
//         -b, LOW runs by +b, which is how the spec's own model (a falling
//         edge that moves) behaves.
//
// After correction a run r is class 1 below 1.5 UI, 2 below 2.5, 3 below 3.5;
// anything else is class 0 (error). Only classes 1 and 2 train the loops:
// class 3 appears once or twice a frame and adds nothing.
//
// Pipeline (runs can arrive on consecutive clocks, so it takes one per clock):
//   1  r = run -/+ b                         thresholds registered from ui
//   2  class from r              -> sym out
//   3  error of r against its class, rounded and scaled
//   4  ui += , b +=/-=  (held to what a MOST25 line can be; see there)
// The loops see their own correction 3 runs late. With steps of 1/64 and
// 1/128 that changes nothing; the regression (sim/run_rx.py) is the proof.
//
// The loops train on every run, framed or not, so noise trains them too. A
// 5 us burst of 0.6 UI runs on a line at the SP4 pulse-width limit (-0.15 UI)
// once left ui at 0.72 UI, a point the real line then held for good: the
// receiver never locked again. Two guards: ui and b stay inside what a
// MOST25 line can be, and after RELEARN clocks without a locked frame both
// start again from 17.0 and 0, as at power-up.
module rx_classify #(
    parameter RELEARN = 495000,     // clocks without a locked frame (5 ms at 99 MHz)
    parameter CLAMP   = 1           // 0 only in sim/run_rx.py, to test RELEARN alone
) (
    input  wire       clk,
    input  wire       rst,
    input  wire       run_valid,
    input  wire [7:0] run_len,
    input  wire       run_level,
    input  wire [31:0] run_t,       // edge time, passed through with the symbol
    input  wire       locked,       // rx_framer: frames are locked
    output reg        sym_valid,
    output reg  [1:0] sym,          // 1, 2, 3; 0 = error
    output reg        sym_level,
    output reg [15:0] ui_q,         // current UI estimate, Q8.8 (for status)
    output reg [31:0] sym_t         // sample time of the edge that ended this run
);
    reg signed [15:0] b;            // pulse-width bias, Q8.8

    // thresholds, re-registered every clock from ui_q
    reg signed [16:0] t05, t15, t25, t35, u1, u2;
    always @(posedge clk) begin
        t05 <= {1'b0, ui_q} >> 1;
        t15 <= {1'b0, ui_q} + ({1'b0, ui_q} >> 1);
        t25 <= ({1'b0, ui_q} << 1) + ({1'b0, ui_q} >> 1);
        t35 <= ({1'b0, ui_q} << 1) + {1'b0, ui_q} + ({1'b0, ui_q} >> 1);
        u1  <= {1'b0, ui_q};
        u2  <= {1'b0, ui_q} << 1;
    end

    // ---- stage 1: bias-corrected run
    reg               v1, l1;
    reg signed [16:0] r1;
    reg        [31:0] t1;
    wire signed [16:0] raw = {1'b0, run_len, 8'd0};
    always @(posedge clk) begin
        v1 <= run_valid & ~rst;
        l1 <= run_level;
        t1 <= run_t;
        r1 <= run_level ? raw - b : raw + b;
    end

    // ---- stage 2: class
    reg [1:0] c;
    always @* begin
        if (r1 < t05)       c = 2'd0;
        else if (r1 < t15)  c = 2'd1;
        else if (r1 < t25)  c = 2'd2;
        else if (r1 < t35)  c = 2'd3;
        else                c = 2'd0;
    end
    reg               v2, l2;
    reg [1:0]         c2;
    reg signed [16:0] r2;
    always @(posedge clk) begin
        v2 <= v1 & ~rst; l2 <= l1; c2 <= c; r2 <= r1;
        sym_valid <= v1 & ~rst; sym <= c; sym_level <= l1; sym_t <= t1;
    end

    // ---- stage 3: rounded, scaled error. Shifts sit in their own signed
    // registers: inside an expression with the unsigned ui_q, >>> would
    // silently turn into a logical shift. Rounded, not floored: a floor
    // biases ui low by half an LSB per step.
    reg               v3, l3;
    reg [1:0]         c3;
    reg signed [16:0] e6, e7;
    wire signed [16:0] e = r2 - ((c2 == 2'd2) ? u2 : u1);
    always @(posedge clk) begin
        v3 <= v2 & ~rst; l3 <= l2; c3 <= c2;
        e6 <= (e + 17'sd32) >>> 6;
        e7 <= (e + 17'sd64) >>> 7;
    end

    // ---- stage 4: loop update, held to what a MOST25 line can be:
    // ui  44.1/48 kHz +-0.1 % is 16.10..17.56 samples; kept in 15.5..18.25
    // b   SP4 allows +0.40 / -0.257 UI of pulse-width distortion, under
    //     7 samples; kept within +-7.5
    localparam signed [17:0] UI_MIN = 18'sd3968, UI_MAX = 18'sd4672;   // Q8.8
    localparam signed [17:0] B_MAX = 18'sd1920;
    wire signed [17:0] de = (c3 == 2'd1) ? {e6[16], e6} : {e7[16], e7};  // e covers two UI in class 2
    wire signed [17:0] db = {e7[16], e7};
    wire signed [17:0] ui_n = $signed({2'b0, ui_q}) + de;
    wire signed [17:0] b_n = l3 ? $signed({{2{b[15]}}, b}) + db : $signed({{2{b[15]}}, b}) - db;

    reg  [19:0] unl;                // clocks without a locked frame
    wire        relearn = (unl == RELEARN - 1);
    always @(posedge clk) unl <= (rst || locked || relearn) ? 20'd0 : unl + 20'd1;

    always @(posedge clk) begin
        if (rst || relearn) begin
            ui_q <= 16'd17 << 8;
            b    <= 16'sd0;
        end else if (v3 && (c3 == 2'd1 || c3 == 2'd2)) begin
            if (CLAMP) begin
                ui_q <= (ui_n < UI_MIN) ? UI_MIN[15:0] : (ui_n > UI_MAX) ? UI_MAX[15:0] : ui_n[15:0];
                b    <= (b_n < -B_MAX) ? -B_MAX[15:0] : (b_n > B_MAX) ? B_MAX[15:0] : b_n[15:0];
            end else begin
                ui_q <= ui_n[15:0];
                b    <= b_n[15:0];
            end
        end
    end
endmodule
