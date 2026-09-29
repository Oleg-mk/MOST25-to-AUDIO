// inject.v - put our own audio into chosen frame bytes on the way out.
//
// The regenerator hands over every run as it starts (st, st_len, one clk_r =
// one UI). This block re-draws the line from that, one UI per clock, and
// normally just copies it: an edge wherever a run starts. So with injection
// off the ring sees exactly the regenerated line, one UI later.
//
// Biphase mark makes substitution local. A frame is 1024 UI; bit k (k >= 4)
// is UI 2k and 2k+1; every bit cell opens with an edge, and a '1' has a
// second edge in the middle. To send a different bit, only the middle edge
// changes: the cell keeps its length, the next cell still opens with an
// edge, and the level after it may flip - which biphase mark ignores. The
// preamble (UI 0..7, a coding violation) and every byte not chosen are
// copied edge for edge.
//
// Parity. Book 2 Table 5.1 puts a parity bit at frame bit 511 (UI 1023)
// without saying which bits it covers or its sense. Whatever the rule, if it
// is an XOR over a set that includes the changed bits, flipping bit 511 by the
// XOR of all changes (new ^ old) leaves the check exactly as it was. That is
// the default; the host can turn it off (M bit 7) if a car shows otherwise.
//
// Host command (packet format in host_cmd.v):
//   A5 5A 02  M  L0 L1 L2  R0 R1 R2  X
//     M[1:0]  0 = off, 2 = 16 bit, 3 = 24 bit;  M[7] = 1: leave bit 511 alone
//     M[2]    the source: 0 = DIN (the host M2), 1 = DIN2 (the S/PDIF receiver
//             through its ASRC, on the same BCLK/LRCK)
//     L0..R2  frame byte index of each sample byte, MSB first. Only 1..60 are
//             accepted (the synchronous area): a command naming byte 0 or the
//             control/frame-control bytes 61..63 is refused as a whole.
//
// What went out. At every frame start the set just used - on or off, the
// byte positions and the six sample bytes - is handed out (prev_*) for the
// outputs that show the frame as it left us: tdm_out and amp_out take it when
// their frame counter wraps, 128 UI after the receiver completed that frame,
// which is after this block has begun the next one (the regenerator's delay
// is 11..85 UI) and long before it begins the one after.
//
// Audio in. The samples arrive on I2S_DIN in the same format as the stereo
// output (I2S, 32-bit slots, 16/24 bit, MSB one BCLK after the LRCK edge),
// clocked by our own BCLK/LRCK - which run from the ring clock, so there is
// no rate conversion: one sample pair per MOST frame. The last complete pair
// is taken at the start of each outgoing frame; the latency is fixed.
//
// Frames. A frame opens with a 3-UI run; the preamble's pattern is not
// documented and may hold a second 3-UI run (S/PDIF-like ones do), so a 3-UI
// run inside the first 8 UI of a frame is part of the preamble and copied, not
// a new frame. A 3-UI run anywhere else opens a frame: on time (exactly 1024 UI
// after the last) it counts towards INJ_LOCK, early it starts the count again -
// the line changed under us, or the first frame was anchored on a preamble's
// second run, and this run is the right anchor.
//
// Fades. Every change the host asks for reaches the line through silence,
// so a switch between the phone and the TOSLINK input, a start or a stop is
// never a step in the amplifier. The samples go out times g/256, and g moves
// by 256 >> FADE_LOG2 once per frame: 2^FADE_LOG2 frames from 0 to 256 (the
// default 256 frames: 5.3 ms at 48 kHz, 5.8 ms at 44.1 kHz).
//   on:            HOLD frames of silence, then g rises from 0
//   off:           g falls to 0 on the bytes in use, then the line is the
//                  ring's again
//   other source:  g falls to 0, DIN switches, HOLD more frames at 0 while
//                  the new source's first pair comes through, then g rises
//   other bytes:   at once, silence and a rise as for "on" - the old bytes
//                  may already be another source's
// The gain in a frame is the one decided at the frame before (the product is
// registered). DIN switches only while nothing goes out or at g = 0, and the
// HOLD frames cover the pair a switch cuts, wherever the pair's last slot
// falls against the frame start.
//
// Safety. Injection runs only while: the command is on (or fading out after
// it), this block has seen INJ_LOCK frames in a row exactly 1024 UI apart,
// this frame opened on time, and the I2S clocks run. Any of these lost stops
// it at once, mid-frame, with no fade; a new frame starts it again, from
// silence. It never touches the preamble or bytes 0 and 61..63.
module inject #(
    parameter INJ_LOCK  = 8,                // frames in a row before injecting
    parameter FADE_LOG2 = 8,                // a fade takes 2^FADE_LOG2 frames (0..8)
    parameter HOLD      = 3                 // frames at 0 after DIN switches
) (
    input  wire        clk_s,
    input  wire        rst_s,
    input  wire        cmd_ok,
    input  wire [7:0]  cmd,
    input  wire [55:0] cmd_p,
    input  wire        clk_r,
    input  wire        rst_r,
    input  wire        st,                  // from regen
    input  wire [3:0]  st_len,              // the run's length in UI
    input  wire [9:0]  phase_n,             // I2S / TDM frame counter (value it takes next)
    input  wire        i2s_run,             // that counter runs
    input  wire        din,                 // I2S_DIN, audio in from the host
    input  wire        din2,                // I2S_DIN2, audio in from the S/PDIF receiver (M[2] = 1)
    output reg         tx,                  // line to the ring
    output reg         active,              // injecting in this frame (clk_r)
    output reg         prev_on,             // the frame just ended was injected...
    output reg         prev_w3,             // ...24 bit (else 16: bytes 2 and 5 unused)
    output reg  [35:0] prev_pos,            // ...into these frame bytes (6 x 6 bits, L0 L1 L2 R0 R1 R2)
    output reg  [47:0] prev_val             // ...with these bytes
);
    // --------------------------------------------- command 02 (clk_s)
    // The packet is registered once more here (see amp_out): a packet holds
    // for 37 us, and decoding it across the chip was a slow path.
    // (syn_preserve: amp_out and inject each keep their own copy - merged into
    // one, the copy sat in one of them and the other decoded across the chip)
    reg        ok_q  /* synthesis syn_preserve = 1 */;
    reg [7:0]  cmd_q /* synthesis syn_preserve = 1 */;
    reg [55:0] p_q   /* synthesis syn_preserve = 1 */;
    always @(posedge clk_s) begin ok_q <= cmd_ok & ~rst_s; cmd_q <= cmd; p_q <= cmd_p; end
    reg [7:0] c_m = 8'd0;
    reg [5:0] c_pos [0:5];
    reg       c_tgl = 1'b0;
    integer k, ki;
    initial for (ki = 0; ki < 6; ki = ki + 1) c_pos[ki] = 6'd1;
    wire [7:0] m_in = p_q[55:48];
    reg        good_pos;
    always @* begin
        good_pos = 1'b1;
        for (k = 0; k < 6; k = k + 1)
            if ((m_in[1:0] == 2'd3 || (k != 2 && k != 5)) &&
                (p_q[47 - 8 * k -: 8] == 8'd0 || p_q[47 - 8 * k -: 8] > 8'd60))
                good_pos = 1'b0;
    end
    // decoded once more: off, or on with good positions
    reg        w02_off, w02_on;
    reg [7:0]  w02_m;
    reg [35:0] w02_p;
    always @(posedge clk_s) begin
        w02_off <= ok_q && cmd_q == 8'h02 && m_in[1:0] == 2'd0;
        w02_on  <= ok_q && cmd_q == 8'h02 && (m_in[1:0] == 2'd2 || m_in[1:0] == 2'd3) && m_in[6:3] == 4'd0 && good_pos;
        w02_m   <= m_in;
        for (k = 0; k < 6; k = k + 1) w02_p[6 * k +: 6] <= p_q[45 - 8 * k -: 6];
    end
    always @(posedge clk_s) begin
        if (rst_s) begin
            // the ring side keeps its copy through its own resets (below), so
            // a reset here reaches it as a command: one more toggle if it was on
            if (c_m != 8'd0) c_tgl <= ~c_tgl;
            c_m <= 8'd0;
            for (k = 0; k < 6; k = k + 1) c_pos[k] <= 6'd1;
        end else if (w02_off) begin
            c_m <= 8'd0; c_tgl <= ~c_tgl;
        end else if (w02_on) begin
            c_m <= w02_m; c_tgl <= ~c_tgl;
            for (k = 0; k < 6; k = k + 1) c_pos[k] <= w02_p[6 * k +: 6];
        end
    end

    // c_* hold still for a whole packet (37 us) after c_tgl flips, so they are
    // copied once the flip has crossed into clk_r. The copy is NOT cleared by
    // rst_r: the ring domain is reset every time the Si514 is centred (at
    // start-up, and on a re-centring mid-drive), and a command the host has
    // already sent must survive that. It starts as "off" at power-up.
    reg [2:0] tg = 3'd0;
    reg [7:0] r_m = 8'd0;
    reg [5:0] r_pos [0:5];
    initial for (ki = 0; ki < 6; ki = ki + 1) r_pos[ki] = 6'd1;
    always @(posedge clk_r) begin
        tg <= {tg[1:0], c_tgl};
        if (tg[2] ^ tg[1]) begin
            r_m <= c_m;
            for (k = 0; k < 6; k = k + 1) r_pos[k] <= c_pos[k];
        end
    end

    // ------------------------------------------------- audio in (clk_r)
    // amp_out raises BCLK on the clock where phase_n[3:0] = 8; the sender
    // changes DIN after the falling edge, so DIN is taken there, mid-bit.
    // Which DIN is `cur`: the command's M[2] while nothing goes out, and
    // while injecting it changes only at g = 0 (the fade, below).
    reg        on;                          // injecting in this frame
    reg        cur = 1'b0;                  // the source in use: 0 DIN, 1 DIN2
    reg [8:0]  g = 9'd0;                    // the gain, 0..256 = 0..1
    reg        din_q;
    reg [63:0] sr;                          // sr[63 - s] = slot s
    reg [23:0] in_l, in_r;                  // last complete pair
    always @(posedge clk_r) begin
        din_q <= cur ? din2 : din;
        if (phase_n[3:0] == 4'd8) sr <= {sr[62:0], din_q};
        if (phase_n == 10'd1017) begin      // slot 63 has just been taken
            in_l <= sr[62:39];              // slots 1..24
            in_r <= sr[30:7];               // slots 33..56
        end
    end
    // the pair times g/256, registered: |x g / 256| <= |x|, so 24 bits hold it
    reg signed [33:0] pl, pr;
    always @(posedge clk_r) begin
        pl <= $signed(in_l) * $signed({1'b0, g});
        pr <= $signed(in_r) * $signed({1'b0, g});
    end
    wire [23:0] gl = pl[31:8], gr = pr[31:8];
    // I2S alive: phase_n must keep moving; checked once per frame
    reg [1:0] irun;
    always @(posedge clk_r) irun <= {irun[0], i2s_run};

    // ------------------------------------------- frame position (clk_r)
    reg        inf;                         // in a frame
    reg [10:0] nxt;                         // UI index of the UI in this clock
    reg [3:0]  good;                        // frames in a row, 1024 UI apart
    wire       pre    = st && st_len == 4'd3;            // a 3-UI run opens here
    wire       inpre  = inf && nxt < 11'd8;              // ...inside the preamble: part of it
    wire       fstart = pre && !inpre;                   // ...anywhere else: a frame opens
    wire       intime = inf && nxt == 11'd1024;          // exactly one frame after the last
    wire [9:0] u      = fstart ? 10'd0 : nxt[9:0];       // this UI
    wire       lost   = inf && nxt > 11'd1024;           // no preamble where one was due

    // this frame's settings and samples, taken at its first UI
    reg        fix;
    reg        w3;
    reg [5:0]  fpos [0:5];
    reg [7:0]  val  [0:5];
    reg        delta;                       // XOR of all changed bits so far
    reg [1:0]  hold;                        // frames left at g = 0 after DIN switched
    localparam [8:0] GSTEP = 9'd256 >> FADE_LOG2;
    localparam [1:0] HOLD2 = HOLD;

    // the command against what is in use
    wire       want = r_m[1:0] != 2'd0;
    reg        moved;                       // other bytes, or another width
    always @* begin
        moved = w3 != (r_m[1:0] == 2'd3);
        for (k = 0; k < 6; k = k + 1)
            if (fpos[k] != r_pos[k]) moved = 1'b1;
    end

    // is UI u inside a chosen byte, and which new bit goes there
    wire [5:0] byte_u = u[9:4];
    wire [2:0] bit_u  = u[3:1];
    reg        hit;
    reg        nb;
    always @* begin
        hit = 1'b0; nb = 1'b0;
        for (k = 5; k >= 0; k = k - 1)
            if ((w3 || (k != 2 && k != 5)) && byte_u == fpos[k]) begin
                hit = 1'b1; nb = val[k][3'd7 - bit_u];
            end
    end
    wire go  = on && !lost && inf && u >= 10'd8;
    // edge (run start) wanted in this UI
    wire f_out = !go                          ? st :
                 hit && !u[0]                 ? 1'b1 :          // cell start
                 hit &&  u[0]                 ? nb :            // middle: the new bit
                 (fix && u == 10'd1023)       ? st ^ delta :    // parity bit 511
                                                st;

    always @(posedge clk_r) begin
        if (!on) cur <= r_m[2];             // nothing goes out: DIN follows the command
        if (rst_r) begin
            inf <= 1'b0; nxt <= 11'd0; good <= 4'd0; on <= 1'b0; active <= 1'b0;
            tx <= 1'b0; delta <= 1'b0; fix <= 1'b0; w3 <= 1'b0; g <= 9'd0; hold <= 2'd0;
            prev_on <= 1'b0; prev_w3 <= 1'b0; prev_pos <= 36'd0; prev_val <= 48'd0;
        end else begin
            tx <= tx ^ f_out;
            if (go && hit && u[0]) delta <= delta ^ nb ^ st;
            if (lost) begin
                inf <= 1'b0; good <= 4'd0; on <= 1'b0; active <= 1'b0; g <= 9'd0; hold <= 2'd0;
            end else if (fstart) begin
                inf <= 1'b1; nxt <= 11'd1;
                if (!intime) good <= 4'd0;
                else if (good != 4'd15) good <= good + 4'd1;
                // the set the frame just ended went out with
                prev_on <= on; prev_w3 <= w3;
                for (k = 0; k < 6; k = k + 1) begin
                    prev_pos[6 * k +: 6] <= fpos[k];
                    prev_val[8 * k +: 8] <= val[k];
                end
                // the newest sample pair, at the gain decided a frame ago
                delta  <= 1'b0;
                val[0] <= gl[23:16]; val[1] <= gl[15:8]; val[2] <= gl[7:0];
                val[3] <= gr[23:16]; val[4] <= gr[15:8]; val[5] <= gr[7:0];
                if (!(intime && good >= INJ_LOCK && irun[1])) begin
                    // not safe to touch the line: stop at once, no fade
                    on <= 1'b0; active <= 1'b0; g <= 9'd0; hold <= 2'd0;
                end else if (on && (!want || r_m[2] != cur)) begin
                    // off, or another source: down on the bytes in use...
                    if (g != 9'd0) g <= g - GSTEP;
                    else if (!want) begin on <= 1'b0; active <= 1'b0; end   // ...then the ring's line
                    else begin                                              // ...then the new source
                        cur <= r_m[2]; hold <= HOLD2;
                        fix <= ~r_m[7]; w3 <= (r_m[1:0] == 2'd3);
                        for (k = 0; k < 6; k = k + 1) fpos[k] <= r_pos[k];
                    end
                end else if (want) begin
                    // a start, or other bytes: from silence, after HOLD frames (DIN may
                    // have followed a new M[2] a moment ago, cutting a pair)
                    if (!on || moved) begin g <= 9'd0; hold <= HOLD2; end
                    else if (hold != 2'd0) hold <= hold - 2'd1;
                    else if (g != 9'd256) g <= g + GSTEP;
                    on <= 1'b1; active <= 1'b1;
                    fix <= ~r_m[7]; w3 <= (r_m[1:0] == 2'd3);
                    for (k = 0; k < 6; k = k + 1) fpos[k] <= r_pos[k];
                end
            end else if (inf) begin
                nxt <= nxt + 11'd1;
                if (!irun[1]) begin on <= 1'b0; active <= 1'b0; g <= 9'd0; hold <= 2'd0; end
            end
        end
    end
endmodule
