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
//     L0..R2  frame byte index of each sample byte, MSB first. Only 1..60 are
//             accepted (the synchronous area): a command naming byte 0 or the
//             control/frame-control bytes 61..63 is refused as a whole.
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
// Safety. Injection runs only while: the command is on, this block has seen
// INJ_LOCK frames in a row exactly 1024 UI apart, this frame opened on time,
// and the I2S clocks run. Any of these lost stops it at once, mid-frame; a new
// frame starts it again. It never touches the preamble or bytes 0 and 61..63.
module inject #(
    parameter INJ_LOCK = 8                  // frames in a row before injecting
) (
    input  wire        clk_s,
    input  wire        rst_s,
    input  wire        cmd_ok,
    input  wire [7:0]  cmd,
    input  wire [55:0] cmd_p,
    input  wire        clk_r,
    input  wire        rst_r,
    input  wire        st,                  // from regen
    input  wire [1:0]  st_len,
    input  wire [9:0]  phase_n,             // I2S / TDM frame counter (value it takes next)
    input  wire        i2s_run,             // that counter runs
    input  wire        din,                 // I2S_DIN, audio in
    output reg         tx,                  // line to the ring
    output reg         active               // injecting in this frame (clk_r)
);
    // --------------------------------------------- command 02 (clk_s)
    reg [7:0] c_m = 8'd0;
    reg [5:0] c_pos [0:5];
    reg       c_tgl = 1'b0;
    integer k, ki;
    initial for (ki = 0; ki < 6; ki = ki + 1) c_pos[ki] = 6'd1;
    wire [7:0] m_in = cmd_p[55:48];
    reg        good_pos;
    always @* begin
        good_pos = 1'b1;
        for (k = 0; k < 6; k = k + 1)
            if ((m_in[1:0] == 2'd3 || (k != 2 && k != 5)) &&
                (cmd_p[47 - 8 * k -: 8] == 8'd0 || cmd_p[47 - 8 * k -: 8] > 8'd60))
                good_pos = 1'b0;
    end
    always @(posedge clk_s) begin
        if (rst_s) begin
            // the ring side keeps its copy through its own resets (below), so
            // a reset here reaches it as a command: one more toggle if it was on
            if (c_m != 8'd0) c_tgl <= ~c_tgl;
            c_m <= 8'd0;
            for (k = 0; k < 6; k = k + 1) c_pos[k] <= 6'd1;
        end else if (cmd_ok && cmd == 8'h02) begin
            if (m_in[1:0] == 2'd0) begin
                c_m <= 8'd0; c_tgl <= ~c_tgl;
            end else if ((m_in[1:0] == 2'd2 || m_in[1:0] == 2'd3) && m_in[6:2] == 5'd0 && good_pos) begin
                c_m <= m_in; c_tgl <= ~c_tgl;
                for (k = 0; k < 6; k = k + 1) c_pos[k] <= cmd_p[45 - 8 * k -: 6];
            end
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
    reg        din_q;
    reg [63:0] sr;                          // sr[63 - s] = slot s
    reg [23:0] in_l, in_r;                  // last complete pair
    always @(posedge clk_r) begin
        din_q <= din;
        if (phase_n[3:0] == 4'd8) sr <= {sr[62:0], din_q};
        if (phase_n == 10'd1017) begin      // slot 63 has just been taken
            in_l <= sr[62:39];              // slots 1..24
            in_r <= sr[30:7];               // slots 33..56
        end
    end
    // I2S alive: phase_n must keep moving; checked once per frame
    reg [1:0] irun;
    always @(posedge clk_r) irun <= {irun[0], i2s_run};

    // ------------------------------------------- frame position (clk_r)
    reg        inf;                         // in a frame
    reg [10:0] nxt;                         // UI index of the UI in this clock
    reg [3:0]  good;                        // frames in a row, 1024 UI apart
    wire       pre    = st && st_len == 2'd3;            // a 3-UI run opens here
    wire       inpre  = inf && nxt < 11'd8;              // ...inside the preamble: part of it
    wire       fstart = pre && !inpre;                   // ...anywhere else: a frame opens
    wire       intime = inf && nxt == 11'd1024;          // exactly one frame after the last
    wire [9:0] u      = fstart ? 10'd0 : nxt[9:0];       // this UI
    wire       lost   = inf && nxt > 11'd1024;           // no preamble where one was due

    // this frame's settings and samples, taken at its first UI
    reg        on;                          // injecting in this frame
    reg        fix;
    reg        w3;
    reg [5:0]  fpos [0:5];
    reg [7:0]  val  [0:5];
    reg        delta;                       // XOR of all changed bits so far

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
        if (rst_r) begin
            inf <= 1'b0; nxt <= 11'd0; good <= 4'd0; on <= 1'b0; active <= 1'b0;
            tx <= 1'b0; delta <= 1'b0; fix <= 1'b0; w3 <= 1'b0;
        end else begin
            tx <= tx ^ f_out;
            if (go && hit && u[0]) delta <= delta ^ nb ^ st;
            if (lost) begin
                inf <= 1'b0; good <= 4'd0; on <= 1'b0; active <= 1'b0;
            end else if (fstart) begin
                inf <= 1'b1; nxt <= 11'd1;
                if (!intime) good <= 4'd0;
                else if (good != 4'd15) good <= good + 4'd1;
                // take this frame's settings and the newest sample pair
                on     <= (r_m[1:0] != 2'd0) && intime && good >= INJ_LOCK && irun[1];
                active <= (r_m[1:0] != 2'd0) && intime && good >= INJ_LOCK && irun[1];
                fix    <= ~r_m[7];
                w3     <= (r_m[1:0] == 2'd3);
                delta  <= 1'b0;
                for (k = 0; k < 6; k = k + 1) fpos[k] <= r_pos[k];
                val[0] <= in_l[23:16]; val[1] <= in_l[15:8]; val[2] <= in_l[7:0];
                val[3] <= in_r[23:16]; val[4] <= in_r[15:8]; val[5] <= in_r[7:0];
            end else if (inf) begin
                nxt <= nxt + 11'd1;
                if (!irun[1]) begin on <= 1'b0; active <= 1'b0; end
            end
        end
    end
endmodule
