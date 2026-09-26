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
// TX runs are whole UIs on a clean clock, so a preamble opens with a run of
// 2.5..3.5 UI (UI from the receiver's estimate); it starts where the previous
// run ended. One event per frame: a preamble may hold a second 3-UI run (the
// pattern is not documented; S/PDIF-like ones do), so a 3-UI run counts only
// if it starts at least 1016 UI after the last accepted one. The first one
// seen is taken as it comes: if that was a preamble's second 3-UI run, the
// next frame's first one is 1019 UI or more later and is accepted, and from
// then on every event sits on the frame's first run, as rx_framer's does.
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

    // 2.5 and 3.5 UI in Q8.8, and 1016 UI in whole samples, re-registered every clock
    reg  [17:0] t25, t35, guard;
    always @(posedge clk) begin
        t25   <= {2'b0, ui_q} + {2'b0, ui_q} + ({2'b0, ui_q} >> 1);
        t35   <= {2'b0, ui_q} + {2'b0, ui_q} + {2'b0, ui_q} + ({2'b0, ui_q} >> 1);
        guard <= ({2'b0, ui_q} << 2) - ({2'b0, ui_q} >> 5);     // (1024 - 8) x ui_q / 256
    end
    wire [17:0] r = {2'b0, rlen, 8'd0};

    reg [31:0] prev_t;                      // end of the previous run = start of this one
    reg        have;                        // a preamble has been accepted since reset
    wire [31:0] since = prev_t - ev_t;      // this run's start after the last preamble's
    always @(posedge clk) begin
        ev <= 1'b0;
        if (rst) begin
            prev_t <= 32'd0; ev_t <= 32'd0; have <= 1'b0;
        end else if (rv) begin
            if (r > t25 && r < t35 && (!have || since >= {14'd0, guard})) begin
                ev <= 1'b1; ev_t <= prev_t; have <= 1'b1;
            end
            prev_t <= rt;
        end
    end
endmodule
