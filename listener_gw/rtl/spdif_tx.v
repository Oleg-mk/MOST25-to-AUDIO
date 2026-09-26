// spdif_tx.v - J3's stereo once more as S/PDIF (IEC 60958-3), for the TOSLINK
// transmitter and the coaxial output.
//
// One S/PDIF frame per ring frame: 2 subframes x 32 time slots, biphase mark
// at 128 Fs = clk_r / 8. The half-cell clock is the ring clock divided by 8,
// so the stream is synchronous to the ring and there is no rate conversion
// anywhere; the receiver's PLL locks to us as it would to any source, at
// 44.1 or 48 kHz as the ring runs.
//
// Subframe: slots 0..3 the preamble (8 half-cells, not biphase: X = 1110 0010
// before a left sample, Y = 1110 0100 before a right one, Z = 1110 1000 before
// the left sample that starts a 192-frame channel-status block, each inverted
// when the line was high before it), slots 4..27 the sample, 24 bit, LSB
// first, 28 validity (0 = valid), 29 user data (0), 30 channel status, 31
// parity: even over slots 4..31. Channel status, the same for both channels:
// consumer, PCM, no copyright asserted (byte 0 = 04), category general, the
// ring's rate (byte 3 = 00 for 44.1 kHz, 02 for 48), 24-bit words (byte 4 =
// 0B), the rest zero.
//
// Every biphase bit cell opens with a transition; a 1 has a second one in the
// middle. The sample pair is latched at phase_n 0, where amp_out latches the
// same pair for I2S, so both outputs carry the same frame at the same time.
// The line is held low while the TDM frame counter does not run (before the
// Si514 is centred, ring gone): the receiver unlocks, as it should.
module spdif_tx (
    input  wire        clk,                 // clk_r = 1024 Fs
    input  wire        run,                 // the TDM frame counter runs
    input  wire [9:0]  phase_n,             // TDM frame counter (value it takes next)
    input  wire [47:0] lr,                  // L R, 24 bit each, L on top (amp_out's out_w)
    input  wire        rate48,              // 1 = 48 kHz ring, 0 = 44.1 (channel status byte 3)
    output reg         out
);
    reg  [47:0] s;                          // the pair on the way out
    reg  [7:0]  fr;                         // frame 0..191 of the channel-status block
    reg         whole;                      // the frame in progress began at half-cell 0 (not the
                                            // partial one run may start in): only those count
    reg         inv;                        // the line before this subframe's preamble
    wire        tick = run && phase_n[2:0] == 3'd0;      // one half-cell
    wire [6:0]  h    = phase_n[9:3];                     // half-cell 0..127 of the frame
    wire        sub  = h[6];                             // 0 left, 1 right
    wire [4:0]  slot = h[5:1];                           // time slot 0..31
    wire        half = h[0];
    wire [23:0] smp  = sub ? s[23:0] : s[47:24];
    // channel status bit of this frame: bytes 0..4 = 04 00 00 (00|02) 0B, then zeros
    wire [39:0] cs   = {8'h0B, {6'd0, rate48, 1'b0}, 8'h00, 8'h00, 8'h04};   // byte 4 on top
    wire        c    = (fr < 8'd40) ? cs[fr[5:0]] : 1'b0;
    wire        par  = (^smp) ^ c;                       // V = U = 0
    wire        b    = (slot <= 5'd27) ? smp[slot - 5'd4] :
                       (slot == 5'd30) ? c :
                       (slot == 5'd31) ? par : 1'b0;     // 28 validity, 29 user data
    // preambles as the levels of half-cells 0..7 after a low line, bit i = half-cell i
    wire [7:0]  pz  = 8'b0001_0111;                      // Z: 1110 1000
    wire [7:0]  px  = 8'b0100_0111;                      // X: 1110 0010
    wire [7:0]  py  = 8'b0010_0111;                      // Y: 1110 0100
    wire [7:0]  pre = sub ? py : (fr == 8'd0) ? pz : px;

    initial begin out = 1'b0; s = 48'd0; fr = 8'd0; whole = 1'b0; inv = 1'b0; end
    always @(posedge clk) begin
        if (!run) begin
            out <= 1'b0; fr <= 8'd0; whole <= 1'b0; inv <= 1'b0;
        end else begin
            if (phase_n == 10'd0) s <= lr;
            if (tick) begin
                if (h[2:0] == 3'd0 && slot == 5'd0) begin
                    inv <= out;                          // the line before the preamble
                    out <= pre[0] ^ out;
                end else if (slot < 5'd4) begin
                    out <= pre[h[2:0]] ^ inv;
                end else if (!half) begin
                    out <= ~out;                         // every cell opens with an edge
                end else if (b) begin
                    out <= ~out;                         // a 1: one more in the middle
                end
                if (h == 7'd0) whole <= 1'b1;
                if (h == 7'd127 && whole) fr <= (fr == 8'd191) ? 8'd0 : fr + 8'd1;
            end
        end
    end
endmodule
