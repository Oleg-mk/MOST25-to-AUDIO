// tb_dsp.v - amp_out (and dsp_core in it) alone, against sim/run_dsp.py.
//
// clk_s 99 MHz, clk_r 1024 Fs. A frame counter stands in for tdm_out's
// phase_n; each frame's 64 bytes (frames.hex) are written in clk_s shortly
// before the counter wraps, as rx_framer and the TDM FIFO place them in the
// core. Host commands (cmds.hex: delay in clk_s, then C P0..P6) are applied
// as host_cmd's `ok` pulses, one after another.
// Logged for run_dsp.py:
//   F n  pos x18 wid x3 mon x3        frame n done, with the positions it was collected with
//   S n  lastframe in_w               the engine started, on this frame's samples
//   E n  out_w bank                   the program ended: outputs and the bank it used
//   W n  bank addr value commit inuse a coefficient word the design accepted (n = starts
//                                    so far; inuse = the ring side's bank at that moment)
//   BANKERR / OVERRUN                 the bank changed during a run / a run missed its frame
//   out_i2s.txt: LRCK SD at every rising BCLK
`timescale 1ns/1ps
module tb_dsp;
    parameter real FS = 48000.0;
    parameter NFRAMES = 400;
    parameter NCMD = 256;

    reg clk_s = 0, clk_r = 0, rst_s = 1, rst_r = 1;
    real ts = 0.0, tr = 0.0;
    always begin ts = ts + 500.0 / 99.0; #(ts - $realtime) clk_s = ~clk_s; end
    always begin tr = tr + 1.0e9 / (2.0 * 1024.0 * FS); #(tr - $realtime) clk_r = ~clk_r; end

    // ------------------------------------------------ frame counter (clk_r)
    reg [9:0] phn = 10'd0;
    reg       run = 1'b0;
    always @(posedge clk_r) if (!rst_r) begin phn <= phn + 10'd1; run <= 1'b1; end

    // ---------------------------------------------------------- the design
    reg        cmd_ok = 1'b0; reg [7:0] cmd = 8'd0; reg [55:0] cmd_p = 56'd0;
    reg        bwe = 1'b0, fdone = 1'b0; reg [5:0] ba = 6'd0; reg [7:0] bd = 8'd0;
    wire       bclk, lrck, sd, overrun;
    amp_out dut (.clk_s(clk_s), .rst_s(rst_s), .cmd_ok(cmd_ok), .cmd(cmd), .cmd_p(cmd_p),
                 .byte_we(bwe), .byte_addr(ba), .byte_data(bd), .frame_done(fdone),
                 .clk_r(clk_r), .rst_r(rst_r), .phase_n(phn), .run(run),
                 .bclk(bclk), .lrck(lrck), .sd(sd), .overrun(overrun));

    // ------------------------------------------------- frames in (clk_s)
    reg [7:0] fb [0:NFRAMES*64-1];
    reg       ptog = 1'b0;
    always @(posedge clk_r) if (phn == 10'd850) ptog <= ~ptog;
    reg [2:0] pt = 3'd0;
    integer nf = 0, j, flog, slog;
    always @(posedge clk_s) pt <= {pt[1:0], ptog};
    initial begin
        @(negedge rst_s);
        forever begin
            @(posedge clk_s);
            if (pt[2] ^ pt[1]) begin
                if (nf < NFRAMES) begin
                    for (j = 0; j < 64; j = j + 1) begin
                        bwe <= 1'b1; ba <= j[5:0]; bd <= fb[nf * 64 + j];
                        @(posedge clk_s);
                    end
                    bwe <= 1'b0;
                    fdone <= 1'b1;
                    $fwrite(flog, "F %0d", nf);
                    for (j = 0; j < 18; j = j + 1) $fwrite(flog, " %0d", dut.pos[j]);
                    for (j = 0; j < 3; j = j + 1) $fwrite(flog, " %0d", dut.wid[j]);
                    for (j = 0; j < 3; j = j + 1) $fwrite(flog, " %0d", dut.mon[j]);
                    $fwrite(flog, "\n");
                    @(posedge clk_s);
                    fdone <= 1'b0;
                    nf = nf + 1;
                end
            end
        end
    end

    // ------------------------------------------------- host commands (clk_s)
    reg [31:0] cd [0:NCMD*9-1];               // delay, C, P0..P6 per command
    integer nc, ci;
    initial begin
        for (ci = 0; ci < NCMD * 9; ci = ci + 1) cd[ci] = 32'hFFFFFFFF;
        $readmemh("cmds.hex", cd);
        @(negedge rst_s);
        for (nc = 0; nc < NCMD && cd[nc * 9] != 32'hFFFFFFFF; nc = nc + 1) begin
            repeat (cd[nc * 9]) @(posedge clk_s);
            cmd <= cd[nc * 9 + 1][7:0];
            cmd_p <= {cd[nc*9+2][7:0], cd[nc*9+3][7:0], cd[nc*9+4][7:0], cd[nc*9+5][7:0],
                      cd[nc*9+6][7:0], cd[nc*9+7][7:0], cd[nc*9+8][7:0]};
            cmd_ok <= 1'b1;
            @(posedge clk_s);
            cmd_ok <= 1'b0;
        end
    end

    // --------------------------------------------------------- engine log
    integer nstart = 0, nend = 0;
    reg run_d = 1'b0, bank_d = 1'b1;
    always @(posedge clk_s) begin
        if (dut.w_ok)
            $fwrite(slog, "W %0d %0d %0d %0d %0d %0d\n", nstart, dut.bank_w, cmd_p[53:48],
                    $signed(cmd_p[47:16]), cmd_p[8], dut.bank_r);
    end
    always @(posedge clk_r) begin
        if (dut.start) begin
            nstart = nstart + 1;
            $fwrite(slog, "S %0d %0d %036h\n", nstart, nf - 1, dut.in_w);
        end
        if (run_d && !dut.running) begin
            nend = nend + 1;
            $fwrite(slog, "E %0d %012h %0d\n", nend, dut.out_w, dut.bank_r);
        end
        if (dut.running && run_d && dut.bank_r !== bank_d) $fwrite(slog, "BANKERR %0d\n", nstart);
        run_d <= dut.running;
        bank_d <= dut.bank_r;
    end

    integer fi2s;
    always @(posedge bclk) $fwrite(fi2s, "%0d%0d\n", lrck, sd);

    initial begin
        $readmemh("frames.hex", fb);
        flog = $fopen("out_frames.txt", "w");
        slog = $fopen("out_engine.txt", "w");
        fi2s = $fopen("out_i2s.txt", "w");
        repeat (20) @(posedge clk_s);
        rst_s = 0;
        @(posedge clk_r); rst_r = 0;
        wait (nf == NFRAMES);
        repeat (3000) @(posedge clk_r);
        if (overrun) $fwrite(slog, "OVERRUN\n");
        $fclose(flog); $fclose(slog); $fclose(fi2s);
        $finish;
    end
endmodule
