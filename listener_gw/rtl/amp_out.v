// amp_out.v - J3: what the factory amplifier would play, as stereo I2S.
//
// Three sources are picked out of the frame (stream 0 is the main one: what
// the amplifier's sink 1 plays; 1 and 2 are for navigation and phone), run
// through dsp_core (tone on stream 0, then a mix into L and R with the head
// unit's volume and balance as gains), and leave on J3 DOUT as standard I2S:
// 64 BCLK per frame (BCLK = 64 Fs = clk_r / 16), 32-bit slots, LRCK low =
// left, MSB one BCLK after the LRCK edge, 24 data bits left-justified,
// changing on the falling BCLK edge. The same BCLK/LRCK clock the host's
// audio input (inject.v). There is no front and rear here: the fader is left
// to whatever follows J3. A sample leaves one frame after the frame it came
// in; the whole delay from the ring is about two frames.
//
// Host commands (packet format in host_cmd.v):
//
//   A5 5A 01  P  L0 L1 L2  R0 R1 R2  X      where a stream is in the frame
//     P[1:0]  0 = off (zeros in), 2 = 16 bit, 3 = 24 bit
//     P[2]    mono: the left bytes only, fed to both sides
//     P[5:4]  stream 0..2
//     P[7:6], P[3] zero; anything else is refused whole
//     L0..R2  frame byte index 0..63 of each sample byte, MSB first (L2/R2
//             ignored at 16 bit, R0..R2 when mono)
//   A5 5A 03  A  V3 V2 V1 V0  F  0  X       one coefficient word
//     A       address 0..63 (the map: sim/dsp_asm.py)
//     V3..V0  the word, Q4.28, most significant byte first
//     F[0]    commit: after this word, the bank written becomes the one in use
//     F[7:1] and the last byte zero; anything else is refused whole
//
// Coefficients live in two banks. The host writes the one not in use, word
// by word, and commits with the last word; the engine switches banks only
// between two runs of its program, so no frame is ever computed from half an
// old and half a new set. The host writes the whole set every time (the bank
// it writes next holds the set before last). A command packet takes 37 us on
// the UART, the switch at most one program run (9 us) after the commit, so
// the next write never reaches the bank still in use.
//
// The sources are taken from the frame as it left the listener: where our
// own audio replaced bytes on the ring (inject.v), the same bytes stand in
// here (sub_*, the set of the frame just ended, live at phase_n 0), so what a
// DSP on J3 plays is what the factory amplifier after us plays.
//
// Neither the banks nor the engine's gains are cleared by a reset: after power
// up everything is zero, so the output is silent until the host has written
// a set; after that a reset of either clock domain changes nothing audible,
// and the host sends its set again anyway (every 2 s).
module amp_out (
    // host command (host_cmd) and frame bytes, clk_s
    input  wire        clk_s,
    input  wire        rst_s,
    input  wire        cmd_ok,
    input  wire [7:0]  cmd,
    input  wire [55:0] cmd_p,
    input  wire        byte_we,
    input  wire [5:0]  byte_addr,
    input  wire [7:0]  byte_data,
    input  wire        frame_done,
    // ring clock, and the TDM frame counter (value it takes next)
    input  wire        clk_r,
    input  wire        rst_r,
    input  wire [9:0]  phase_n,
    input  wire        run,                 // tdm_out is running (clk_r domain)
    input  wire        sub_on,              // inject.v prev_*: the frame just ended was injected...
    input  wire        sub_w3,              // ...24 bit
    input  wire [35:0] sub_pos,             // ...into these frame bytes
    input  wire [47:0] sub_val,             // ...with these
    output reg         bclk,
    output reg         lrck,
    output reg         sd,                  // L R
    output wire        overrun              // clk_r: the engine missed a frame (sticky)
);
    integer k, s;

    // ------------------------------------------------ command 01 (clk_s)
    // The packet is registered once more here: decoded straight from host_cmd's
    // registers, across the chip, the 01 and 03 writes were clk_s's slowest
    // path. A packet holds for 37 us, so a clock costs nothing.
    // (syn_preserve: amp_out and inject each keep their own copy - merged into
    // one, the copy sat in one of them and the other decoded across the chip)
    reg        ok_q  /* synthesis syn_preserve = 1 */;
    reg [7:0]  cmd_q /* synthesis syn_preserve = 1 */;
    reg [55:0] p_q   /* synthesis syn_preserve = 1 */;
    always @(posedge clk_s) begin ok_q <= cmd_ok & ~rst_s; cmd_q <= cmd; p_q <= cmd_p; end
    wire [7:0] p0 = p_q[55:48];
    wire       p0_ok = p0[7:6] == 2'd0 && !p0[3] && p0[5:4] != 2'd3 && p0[1:0] != 2'd1;
    // decoded once more: a strobe per stream and the fields, so the writes
    // below are plain enables (the 6s+k address arithmetic was a slow path)
    reg  [2:0]  w01;                        // write stream 0 / 1 / 2
    reg  [1:0]  w01_w;
    reg         w01_m;
    reg  [35:0] w01_p;
    always @(posedge clk_s) begin
        for (s = 0; s < 3; s = s + 1) w01[s] <= ok_q && cmd_q == 8'h01 && p0_ok && p0[5:4] == s[1:0] && !rst_s;
        w01_w <= p0[1:0]; w01_m <= p0[2];
        for (k = 0; k < 6; k = k + 1) w01_p[6 * k +: 6] <= p_q[45 - 8 * k -: 6];
    end
    reg  [5:0] pnew [0:17];                 // stream s: L0 L1 L2 R0 R1 R2 at 6s..6s+5
    reg  [1:0] wnew [0:2];
    reg        mnew [0:2];
    always @(posedge clk_s) begin
        if (rst_s) begin
            for (s = 0; s < 3; s = s + 1) begin wnew[s] <= 2'd0; mnew[s] <= 1'b0; end
            for (k = 0; k < 18; k = k + 1) pnew[k] <= 6'd0;
        end else begin
            for (s = 0; s < 3; s = s + 1)
                if (w01[s]) begin
                    wnew[s] <= w01_w;
                    mnew[s] <= w01_m;
                    for (k = 0; k < 6; k = k + 1) pnew[6 * s + k] <= w01_p[6 * k +: 6];
                end
        end
    end

    // --------------------------------------- pick the bytes of each frame
    // A command takes effect at the next frame boundary, so no frame is ever
    // put together from two different sets of positions.
    // The byte stream is registered once more here: 18 address compares fed
    // straight from rx_framer's registers, across the chip, were clk_s's
    // slowest path. frame_done is delayed with it, so byte 63 lands before
    // the copy into fin.
    reg       we_q, fd_q;
    reg [5:0] ba_q;
    reg [7:0] bd_q;
    always @(posedge clk_s) begin
        we_q <= byte_we & ~rst_s; fd_q <= frame_done & ~rst_s; ba_q <= byte_addr; bd_q <= byte_data;
    end
    reg [5:0] pos [0:17];                   // in effect for the frame being collected
    reg [5:0] pfin [0:17];                  // ...and the positions fin was collected with
    reg [7:0] cur [0:17];                   // being collected
    reg [7:0] fin [0:17];                   // last complete frame, stable ~1 frame
    reg [1:0] wid [0:2], wfin [0:2];        // width in effect / with fin
    reg       mon [0:2], mfin [0:2];
    always @(posedge clk_s) begin
        if (rst_s) begin
            for (s = 0; s < 3; s = s + 1) begin
                wid[s] <= 2'd0; wfin[s] <= 2'd0; mon[s] <= 1'b0; mfin[s] <= 1'b0;
            end
            for (k = 0; k < 18; k = k + 1) pos[k] <= 6'd0;
        end else begin
            if (we_q)
                for (k = 0; k < 18; k = k + 1)
                    if (ba_q == pos[k]) cur[k] <= bd_q;
            if (fd_q) begin
                for (k = 0; k < 18; k = k + 1) begin
                    fin[k] <= cur[k];
                    pfin[k] <= pos[k];
                    pos[k] <= pnew[k];
                end
                for (s = 0; s < 3; s = s + 1) begin
                    wfin[s] <= wid[s]; wid[s] <= wnew[s];
                    mfin[s] <= mon[s]; mon[s] <= mnew[s];
                end
            end
        end
    end

    // the samples, as the engine takes them: fin changes at a frame
    // completion, 128+ clk_r before phase_n reaches 0 and ~900 clk_r after it,
    // so it is quiet when the engine latches it at phase_n == 0
    // Registered in two clk_r stages (the substitution, then the assembly):
    // as one cone into the engine's input register they were clk_1024's slowest
    // path. fin, pfin and sub_* hold still for over 100 clk_r before phase_n 0.
    reg [143:0] in_w;
    reg [23:0]  l24, r24;
    reg [7:0]   fb [0:17];                  // fin, with the bytes we put on the ring in their place
    reg [7:0]   fb_c [0:17];
    integer     q, m;                       // their own: the clocked blocks' loops run on k, s
    always @* begin
        for (q = 0; q < 18; q = q + 1) begin
            fb_c[q] = fin[q];
            for (m = 0; m < 6; m = m + 1)
                if (sub_on && (sub_w3 || (m != 2 && m != 5)) && sub_pos[6 * m +: 6] == pfin[q])
                    fb_c[q] = sub_val[8 * m +: 8];
        end
    end
    always @(posedge clk_r) begin
        for (q = 0; q < 18; q = q + 1) fb[q] <= fb_c[q];
        for (q = 0; q < 3; q = q + 1) begin
            l24 = (wfin[q] == 2'd3) ? {fb[6 * q], fb[6 * q + 1], fb[6 * q + 2]} :
                  (wfin[q] == 2'd2) ? {fb[6 * q], fb[6 * q + 1], 8'd0} : 24'd0;
            r24 = (wfin[q] == 2'd3) ? {fb[6 * q + 3], fb[6 * q + 4], fb[6 * q + 5]} :
                  (wfin[q] == 2'd2) ? {fb[6 * q + 3], fb[6 * q + 4], 8'd0} : 24'd0;
            in_w[143 - 48 * q -: 24] <= l24;
            in_w[119 - 48 * q -: 24] <= mfin[q] ? l24 : r24;
        end
    end

    // ------------------------------------------- command 03, banks (clk_s)
    reg [31:0] cmem [0:127];                // {bank, address}
    integer i;
    initial for (i = 0; i < 128; i = i + 1) cmem[i] = 32'd0;
    // not reset: they must agree with the ring side, which keeps its bank
    reg bank_w = 1'b0, c_tgl = 1'b0, c_bank = 1'b0;
    wire w_ok = ok_q && cmd_q == 8'h03 && p_q[55:54] == 2'd0 &&
                p_q[15:9] == 7'd0 && p_q[7:0] == 8'd0;
    reg         w03;                        // decoded once more, as for command 01
    reg  [5:0]  w03_a;
    reg  [31:0] w03_v;
    reg         w03_c;
    always @(posedge clk_s) begin
        w03 <= w_ok; w03_a <= p_q[53:48]; w03_v <= p_q[47:16]; w03_c <= p_q[8];
    end
    always @(posedge clk_s) begin
        if (w03) begin
            cmem[{bank_w, w03_a}] <= w03_v;
            if (w03_c) begin
                c_bank <= bank_w; c_tgl <= ~c_tgl; bank_w <= ~bank_w;
            end
        end
    end

    // ------------------------------------------------ engine (clk_r)
    reg  [2:0] tg = 3'd0;
    reg        pend = 1'b0, bank_r = 1'b1;  // bank 1 (zeros) until the first commit
    wire       running;
    wire [5:0] c_addr;
    reg  [31:0] c_q;
    wire [47:0] out_w;
    wire       start = run && phase_n == 10'd0;
    always @(posedge clk_r) begin
        tg <= {tg[1:0], c_tgl};
        if (tg[2] ^ tg[1]) pend <= 1'b1;    // c_bank has held still for > 3 clk_r
        if (pend && !running && !(tg[2] ^ tg[1])) begin
            bank_r <= c_bank; pend <= 1'b0;
        end
        c_q <= cmem[{bank_r, c_addr}];
    end
    dsp_core u_dsp (.clk(clk_r), .rst(rst_r), .start(start), .in_w(in_w), .c_addr(c_addr),
                    .c_q(c_q), .out_w(out_w), .running(running), .overrun(overrun));

    // ------------------------------------------------- I2S out (clk_r)
    // out_w is written during the program run (~450 clk_r after phase_n 0)
    // and latched here at the next phase_n 0
    reg [63:0] w;
    wire [5:0] sl = phase_n[9:4];           // BCLK slot 0..63
    always @(posedge clk_r) begin
        if (!run) begin
            bclk <= 1'b0; lrck <= 1'b0; sd <= 1'b0; w <= 64'd0;
        end else begin
            if (phase_n == 10'd0)
                w <= {out_w[47:24], 8'd0, out_w[23:0], 8'd0};
            bclk <= phase_n[3];
            lrck <= sl[5];
            if (phase_n[3:0] == 4'd0)       // falling BCLK edge: next bit
                sd <= (sl == 6'd0) ? 1'b0 : w[6'd0 - sl];     // 64 - sl, mod 64
        end
    end
endmodule
