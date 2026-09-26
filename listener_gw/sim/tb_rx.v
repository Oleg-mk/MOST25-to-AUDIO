// tb_rx.v - drives samples.hex through runlen -> classify -> framer and
// writes every locked frame and every run class to text files for compare.py.
`timescale 1ns/1ps
module tb_rx;
    parameter MAXCLK = 120000;
    parameter RELEARN = 495000;          // rx_classify: clocks unlocked before it relearns
    parameter CLAMP = 1;                 // rx_classify: 0 = no bounds on ui and b (run_rx.py only)
    reg clk = 0, rst = 1;
    always #5.05 clk = ~clk;             // 99 MHz

    reg [7:0] mem [0:MAXCLK-1];
    integer nclk, i, j, fo, fr;
    reg [7:0] samp;

    wire rv, rl, gl; wire [7:0] rlen; wire [31:0] rt, st;
    wire sv, sl; wire [1:0] sym; wire [15:0] ui_q;
    wire bwe, fd, fpar, bk, lk, er; wire [5:0] ba; wire [7:0] bd; wire [3:0] bi;
    reg [28:0] wc;                       // the sample time base, as in listener_core
    always @(posedge clk) wc <= rst ? 29'd0 : wc + 29'd1;

    rx_runlen   u_rl (.clk(clk), .rst(rst), .samp(samp), .wc(wc), .run_valid(rv), .run_len(rlen),
                      .run_level(rl), .glitch(gl), .run_t(rt));
    rx_classify #(.RELEARN(RELEARN), .CLAMP(CLAMP))
                u_cl (.clk(clk), .rst(rst), .run_valid(rv), .run_len(rlen), .run_level(rl),
                      .glitch(gl), .run_t(rt), .locked(lk), .sym_valid(sv), .sym(sym), .sym_len(),
                      .sym_level(sl), .ui_q(ui_q), .sym_t(st));
    rx_framer   u_fr (.clk(clk), .rst(rst), .sym_valid_i(sv), .sym_i(sym), .sym_t_i(st), .ui_q(ui_q),
                      .byte_we(bwe), .byte_addr(ba), .byte_data(bd), .frame_done(fd),
                      .frame_par(fpar), .blk_idx(bi), .blk_known(bk), .locked(lk), .err(er));

    reg [7:0] fbuf [0:63];
    integer nerr = 0, nglitch = 0, nframes = 0, nsym0 = 0;
    always @(posedge clk) begin
        if (bwe) fbuf[ba] <= bd;
        if (er) begin nerr = nerr + 1; $display("EVT err    t=%0t locked_frames_so_far=%0d", $time, nframes); end
        if (gl) begin nglitch = nglitch + 1; $display("EVT glitch t=%0t locked_frames_so_far=%0d samp=%b", $time, nframes, samp); end
        if (sv && sym == 0) nsym0 = nsym0 + 1;
        if (sv) $fwrite(fr, "%0d\n", sym);
        if (fd && lk) begin
            nframes = nframes + 1;
            $fwrite(fo, "%0d %0d %0d ", bk, bi, fpar);
            for (j = 0; j < 64; j = j + 1) $fwrite(fo, "%02x", fbuf[j]);
            $fwrite(fo, "\n");
        end
    end

    initial begin
        for (i = 0; i < MAXCLK; i = i + 1) mem[i] = 8'hxx;
        $readmemh("samples.hex", mem);
        nclk = 0;
        while (nclk < MAXCLK && mem[nclk] !== 8'hxx) nclk = nclk + 1;
        fo = $fopen("out_frames.txt", "w");
        fr = $fopen("out_syms.txt", "w");
        samp = 0;
        repeat (4) @(posedge clk);
        rst = 0;
        for (i = 0; i < nclk; i = i + 1) begin
            @(negedge clk) samp = mem[i];
        end
        @(negedge clk) samp = {8{mem[nclk-1][7]}};   // hold the last level: no fake edges
        repeat (8) @(posedge clk);
        $display("clocks=%0d frames_locked=%0d errors=%0d glitches=%0d class0=%0d ui_q=%0d.%03d",
                 nclk, nframes, nerr, nglitch, nsym0, ui_q >> 8, ((ui_q & 255) * 1000) >> 8);
        $fclose(fo); $fclose(fr);
        $finish;
    end
endmodule
