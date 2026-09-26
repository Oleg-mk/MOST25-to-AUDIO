// tx_pre.v - time-stamp the preambles of our own transmitted line.
//
// The regenerated TX is fed back into the FPGA (TX_FB, an IDES8 input like
// RX_IN) and measured on the same 792 Msps time base (wc). The clock loop
// (dpll.v) compares each preamble here with the same preamble on the ring
// input: the difference is the regenerator's delay, which the loop holds
// constant. Both ends keep the 1.26 ns resolution - a coarser detector
// (whole clk_s ticks, or the FIFO level in runs) would let the beat of its
// grid with the frame rate through as ring wander.
//
// TX runs are whole UIs on a clean clock, so a preamble is simply a run of
// 2.5..3.5 UI (UI from the receiver's estimate); it starts where the previous
// run ended.
module tx_pre (
    input  wire        clk,
    input  wire        rst,
    input  wire [7:0]  samp,                // loopback samples, bit 0 = earliest
    input  wire [28:0] wc,
    input  wire [15:0] ui_q,                // UI in samples, Q8.8 (rx_classify)
    output reg         ev,                  // a preamble started at ev_t
    output reg  [31:0] ev_t
);
    wire       rv, rl, gl;
    wire [7:0] rlen;
    wire [31:0] rt;
    rx_runlen u_rl (.clk(clk), .rst(rst), .samp(samp), .wc(wc), .run_valid(rv), .run_len(rlen),
                    .run_level(rl), .glitch(gl), .run_t(rt));

    // 2.5 and 3.5 UI in Q8.8, re-registered every clock
    reg  [17:0] t25, t35;
    always @(posedge clk) begin
        t25 <= {2'b0, ui_q} + {2'b0, ui_q} + ({2'b0, ui_q} >> 1);
        t35 <= {2'b0, ui_q} + {2'b0, ui_q} + {2'b0, ui_q} + ({2'b0, ui_q} >> 1);
    end
    wire [17:0] r = {2'b0, rlen, 8'd0};

    reg [31:0] prev_t;
    always @(posedge clk) begin
        ev <= 1'b0;
        if (rst) begin
            prev_t <= 32'd0; ev_t <= 32'd0;
        end else if (rv) begin
            if (r > t25 && r < t35) begin
                ev <= 1'b1; ev_t <= prev_t;
            end
            prev_t <= rt;
        end
    end
endmodule
