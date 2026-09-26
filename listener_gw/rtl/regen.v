// regen.v - retransmit the received line, retimed on the ring-locked clock.
//
// The receiver's runs, in whole UI (rx_classify sym_len: 1, 2 or 3 for a
// legal run, the rounded length for an error run), go through an
// asynchronous FIFO from the sample domain (clk_s, 99 MHz) into the ring
// domain (clk_r = the Si514 output = 1024 Fs, one UI per clock). There each
// run becomes a level held for that many clk_r cycles, then an edge. The
// same bits and the same preamble violations go out, but every edge now sits
// on a clean clock, which is what an active MOST node does (Physical Layer
// 2.1.1: "Having passed an active MOST node all pulse-width-distortion will
// be removed").
//
// An error on the line goes out as it came in: a run of a wrong length is
// sent with its measured length (a 4-UI run stays a 4-UI run), so the nodes
// after us see the same fault the ring gave us and nothing more, and the
// frame keeps its 1024 UI. Only a run below half a UI - a glitch that split
// a run in two - is dropped: its neighbours merge back into one run. Errors
// are the framer's to judge (rx_framer rides through one), not this block's:
// nothing here stops on them, so the ring is never switched over for one.
//
// Besides the line itself it reports each run as it starts (st, st_len): the
// injector (inject.v) re-draws the line from that and can change data bits.
//
// clk_r is frequency-locked to the ring, so the FIFO level only wanders. It
// starts reading at half full. If it ever runs dry or overflows, `ok` drops,
// and the top level falls back to the bypass path.
module regen #(
    parameter AW = 6                        // FIFO depth 2^AW runs
) (
    input  wire       clk_s,
    input  wire       rst_s,
    input  wire       sym_valid,
    input  wire [3:0] len,                  // the run in whole UI (rx_classify sym_len)
    input  wire       enable,               // clk_s domain: receiver locked
    input  wire       clk_r,
    input  wire       rst_r,
    output reg        tx,                   // regenerated line, clk_r domain
    output reg        ok,                   // clk_r domain: tx is valid
    output reg        st,                   // a run starts in this clk_r (an edge on tx)
    output reg  [3:0] st_len                // ... and is this many UI long
);
    // ---------------------------------------------------------- write side
    reg  [3:0]  mem [0:(1<<AW)-1];
    reg  [AW:0] wbin, wgray;
    wire [AW:0] wbin_n = wbin + 1'b1;
    always @(posedge clk_s) begin
        if (rst_s || !enable) begin
            wbin <= 0; wgray <= 0;
        end else if (sym_valid && len != 4'd0) begin
            mem[wbin[AW-1:0]] <= len;
            wbin  <= wbin_n;
            wgray <= wbin_n ^ (wbin_n >> 1);
        end
    end

    // ----------------------------------------------------------- read side
    reg  [AW:0] wg1, wg2, rbin;
    reg         en1, en2;
    always @(posedge clk_r) begin
        wg1 <= wgray; wg2 <= wg1;
        en1 <= enable; en2 <= en1;
    end
    // gray -> binary of the synchronised write pointer
    reg [AW:0] wb;
    integer i;
    always @* begin
        wb[AW] = wg2[AW];
        for (i = AW - 1; i >= 0; i = i - 1) wb[i] = wb[i+1] ^ wg2[i];
    end
    wire [AW:0] level = wb - rbin;

    reg        run;                          // reading
    reg        algn;                         // read pointer aligned to the writer
    reg  [3:0] left;                         // clk_r cycles left in this run
    always @(posedge clk_r) begin
        st <= 1'b0;
        if (rst_r || !en2) begin
            rbin <= 0; run <= 1'b0; ok <= 1'b0; left <= 4'd0; tx <= 1'b0; st_len <= 4'd0;
            algn <= 1'b0;
        end else if (!algn) begin
            // The read side can be reset alone (clk_r stops while the Si514
            // is centred; the receiver, and so the writer, keep running), so
            // rbin = 0 means nothing. Count the FIFO as empty from the
            // writer's position; the synchroniser has run through the reset.
            rbin <= wb; algn <= 1'b1;
        end else if (!run) begin
            // wait for half full, then go
            if (level >= (1 << (AW - 1))) run <= 1'b1;
        end else if (left <= 4'd1) begin
            // current run ends this cycle: edge, next run
            if (level == 0 || level > (1 << AW)) begin
                ok <= 1'b0; run <= 1'b0; rbin <= wb;      // under/overflow: restart
            end else begin
                tx     <= ~tx;
                left   <= mem[rbin[AW-1:0]];
                st     <= 1'b1;
                st_len <= mem[rbin[AW-1:0]];
                rbin <= rbin + 1'b1;
                ok   <= 1'b1;
            end
        end else begin
            left <= left - 4'd1;
        end
    end
endmodule
