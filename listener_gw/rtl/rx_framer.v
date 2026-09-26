// rx_framer.v - run classes (1/2/3 UI) -> MOST25 frames.
//
// Frame (MOST Book 2, Table 5.1): 512 bit = 1024 UI. Bits 0..3 are the
// preamble, a biphase-mark coding violation 8 UI long; bits 4..511 are
// biphase mark (a '0' is one 2-UI run, a '1' is two 1-UI runs).
//
// What is NOT known from any document on disk, and how this block copes:
//  * The full preamble run pattern. Used only: it is 8 UI long and STARTS
//    with a 3-UI run. Sources: Oasis SiliconSystems patents by D. Knapp, the
//    MOST25 designer - US 2005/0053179 A1 ("512 bits sent between coding
//    violations which represent the beginning of each preamble") and
//    US 2004/0057542 A1 (the violation is "three logic high voltage values
//    strung together"; Fig. 10 draws parity, then a 3-cell run, then a 1-cell
//    run, data again ~8 cells later). Patents give examples, not the spec, so
//    anything else still shows up as a framer error, never as silently wrong
//    bytes: the next preamble must land exactly 1024 UI later.
//  * Which preamble marks the start of a control block. The framer learns it:
//    the pattern seen on two frames running is the common one; a frame with
//    a different pattern starts a block. Its index 0..15 replaces the four
//    preamble bits in byte 0.
//  * Parity sense. The XOR of bits 4..511 is reported raw (frame_par), not
//    judged.
//
// One error is ridden through. A coding or framing error ends the frame (it
// is not emitted) but, once locked, does not end the lock: the next frame
// must then open with a 3-UI run where it is due - 1024 UI after this
// frame's UI 0 (2048 if the run that failed was already the next frame's
// first), within 4 UI - and a clean frame clears the strike. A second error
// before that, or no preamble on time, is what unlocks; that is the rule a
// MOST node follows too (lock after 3 valid preambles, unlock after 2 invalid
// ones: Oasis patent EP 1333580 B1). Without it one bad bit on the line took
// the regenerator, LOCK and the ring's bypass switch with it for HOLD_RE.
// The lost frame may have been a block start, so the block index is
// unknown until the next block start is seen (blk_known drops). Should no
// run at all arrive while the strike is open (a dead line), STRIKE_MAX clocks
// end it the same way as a late one.
//
// Frame edges with full timing resolution. fs_sq below changes on the clock
// that sees an edge, so it sits on a 10.1 ns grid, and the beat between that
// grid and the frame rate passes through any clock multiplier as up to ~10 ns
// of wander. So the two edges that define the frame rate are also reported
// with the time the sampler saw them (sym_t, 1.26 ns units): the edge that
// opens the preamble (UI 0, fe_rise = 1) and the bit-cell edge at UI 512
// (fe_rise = 0). fs_fine.v re-draws the frame-rate square wave from these.
module rx_framer #(
    parameter STRIKE_MAX = 8192       // clocks a strike may stay open (83 us: two frames and a margin)
) (
    input  wire       clk,
    input  wire       rst,
    input  wire       sym_valid_i,
    input  wire [1:0] sym_i,
    input  wire [31:0] sym_t_i,       // sample time of the edge that ended this run
    input  wire [15:0] ui_q,          // UI in samples, Q8.8 (rx_classify): where the next frame is due
    // frame bytes, written as they complete; byte 0 = {block index, BD}
    output reg        byte_we,
    output reg  [5:0] byte_addr,
    output reg  [7:0] byte_data,
    output reg        frame_done,     // pulse after byte 63 of a clean frame
    output reg        frame_par,      // XOR of bits 4..511
    output reg  [3:0] blk_idx,        // index of the finished frame in its block
    output reg        blk_known,
    output reg        locked,
    output reg        err,            // pulse: coding or framing error
    output wire       fs_sq,          // frame-rate square wave, 50 %, on the clk grid
    output reg        fe_valid,       // a frame edge: UI 0 (fe_rise) or UI 512
    output reg        fe_rise,
    output reg [31:0] fe_t            // its sample time
);
    reg        in_frame;
    reg [10:0] pos;                   // UI position inside the frame
    reg        half;                  // first half of a '1' seen
    reg [7:0]  sh;                    // bit shift register
    reg        par;
    reg [31:0] prev_t;                // end time of the previous run = start of this one
    reg [11:0] sig, last_sig, common_sig;
    reg        common_ok;
    reg [2:0]  good;
    reg        bad;                   // one strike used: the next frame must open on time
    reg [31:0] f0_t;                  // sample time of UI 0 of the frame in progress
    reg [31:0] exp_t;                 // where UI 0 of the next frame is due (while bad)
    reg [17:0] flen, win;             // 1024 UI and 4 UI in whole samples, from ui_q
    always @(posedge clk) begin
        flen <= {2'b0, ui_q} << 2;                  // ui_q x 1024 / 256
        win  <= {2'b0, ui_q} >> 6;                  // ui_q x 4 / 256
    end
    // this run's start (prev_t) against the due time, modulo 2^18 samples (16 frames)
    wire signed [17:0] d_exp = prev_t[17:0] - exp_t[17:0];
    wire signed [17:0] w_s   = win;
    wire ontime = d_exp >= -w_s && d_exp <= w_s;
    reg  [13:0] strike;               // clocks the strike has been open
    wire late   = d_exp > w_s || strike == STRIKE_MAX[13:0];
    always @(posedge clk) strike <= (rst || !bad || in_frame) ? 14'd0 : (strike == STRIKE_MAX[13:0]) ? strike : strike + 14'd1;

    // The inputs are registered once more here. The decode below reaches most
    // of this block's registers; started from rx_classify's output register
    // (which synthesis shares with that block's own pipeline) it had become
    // clk_s's slowest path. The clk_s of latency changes nothing downstream:
    // every edge carries its own sample time.
    reg        sym_valid;
    reg [1:0]  sym;
    reg [31:0] sym_t;
    always @(posedge clk) begin
        sym_valid <= sym_valid_i & ~rst; sym <= sym_i; sym_t <= sym_t_i;
    end

    wire [8:0] k = pos[9:1];          // bit index of a bit that starts at pos

    // High for UI 0..511 of every frame. Its edges are run edges, so it is
    // exactly the ring's frame rate, with the 10 ns jitter of this clock domain
    // (unused now: the loop takes fe_t at 1.26 ns, fs_fine draws the edges).
    assign fs_sq = locked & ~pos[9];

    task put_bit(input b);
        begin
            sh  <= {sh[6:0], b};
            par <= par ^ b;
            if (k[2:0] == 3'd7) begin
                byte_we   <= 1'b1;
                byte_addr <= k[8:3];
                byte_data <= (k[8:3] == 6'd0) ? {blk_idx, sh[2:0], b} : {sh[6:0], b};
            end
        end
    endtask

    task fail;
        begin
            err <= 1'b1; in_frame <= 1'b0; half <= 1'b0;
            if (locked && !bad) begin
                // one strike: this frame is lost, the lock is kept; the next frame
                // is due one frame after this one's UI 0 - two, if the run that
                // failed was already the next frame's first
                bad       <= 1'b1;
                exp_t     <= f0_t + ((pos == 11'd1024) ? {13'd0, flen, 1'b0} : {14'd0, flen});
                blk_known <= 1'b0;
            end else begin
                locked <= 1'b0; good <= 3'd0; bad <= 1'b0;
            end
        end
    endtask

    // start a frame on a 3-UI run; the frame began where that run began
    task start;
        begin
            in_frame <= 1'b1; pos <= 11'd3; half <= 1'b0; par <= 1'b0;
            sig <= {10'd0, 2'd3};
            f0_t <= prev_t;
            fe_valid <= 1'b1; fe_rise <= 1'b1; fe_t <= prev_t;
        end
    endtask

    // the run that ends here ends exactly at UI 512
    task mid;
        begin
            fe_valid <= 1'b1; fe_rise <= 1'b0; fe_t <= sym_t;
        end
    endtask

    always @(posedge clk) begin
        byte_we <= 1'b0; frame_done <= 1'b0; err <= 1'b0; fe_valid <= 1'b0;
        if (rst) begin
            in_frame <= 1'b0; pos <= 11'd0; half <= 1'b0; sh <= 8'd0; par <= 1'b0;
            sig <= 12'd0; last_sig <= 12'd0; common_sig <= 12'd0; common_ok <= 1'b0;
            blk_idx <= 4'd0; blk_known <= 1'b0; locked <= 1'b0; good <= 3'd0;
            frame_par <= 1'b0; byte_addr <= 6'd0; byte_data <= 8'd0;
            prev_t <= 32'd0; fe_rise <= 1'b0; fe_t <= 32'd0;
            bad <= 1'b0; f0_t <= 32'd0; exp_t <= 32'd0;
        end else if (sym_valid) begin
            prev_t <= sym_t;
            if (!in_frame) begin
                if (bad) begin
                    // after a strike: a 3-UI run where the next frame is due keeps
                    // the lock; nothing on time is the second invalid preamble
                    if (sym == 2'd3 && ontime && strike != STRIKE_MAX[13:0]) start;
                    else if (late) begin
                        locked <= 1'b0; good <= 3'd0; bad <= 1'b0;
                        if (sym == 2'd3) start;
                    end
                end else if (sym == 2'd3) start;
            end else if (pos == 11'd1024) begin
                // previous frame finished cleanly; the next run must open a preamble
                if (sym == 2'd3) begin
                    start;
                    bad <= 1'b0;
                    if (good != 3'd7) good <= good + 3'd1;
                    if (good >= 3'd3) locked <= 1'b1;
                end else fail;
            end else if (pos < 11'd8) begin
                // preamble: collect the run pattern, must end exactly at 8 UI
                if (sym == 2'd0) fail;
                else if (pos + {9'd0, sym} > 11'd8) fail;
                else begin
                    pos <= pos + {9'd0, sym};
                    sig <= {sig[9:0], sym};
                    if (pos + {9'd0, sym} == 11'd8) begin
                        // block bookkeeping, once per frame
                        last_sig <= {sig[9:0], sym};
                        if (last_sig == {sig[9:0], sym}) begin
                            common_sig <= {sig[9:0], sym};
                            common_ok  <= 1'b1;
                        end
                        if (common_ok && ({sig[9:0], sym} != common_sig)) begin
                            blk_idx <= 4'd0; blk_known <= 1'b1;
                        end else begin
                            blk_idx <= blk_idx + 4'd1;
                        end
                    end
                end
            end else begin
                // data bits
                case (sym)
                    2'd2: if (half) fail;
                          else begin
                              put_bit(1'b0); pos <= pos + 11'd2;
                              if (pos + 11'd2 == 11'd512) mid;
                          end
                    2'd1: if (!half) begin half <= 1'b1; pos <= pos + 11'd1; end
                          else begin
                              half <= 1'b0; put_bit(1'b1); pos <= pos + 11'd1;
                              if (pos + 11'd1 == 11'd512) mid;
                          end
                    default: fail;
                endcase
            end
        end
        // frame end: bit 511 has just been shifted in
        if (in_frame && pos == 11'd1024 && !frame_done && byte_we && byte_addr == 6'd63) begin
            frame_done <= 1'b1;
            frame_par  <= par;
        end
    end
endmodule
