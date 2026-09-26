// tb_core.v - the whole listener_core against a behavioural Si514 (sim/
// si514_model.v) on its I2C bus. The Si514's frequency drives clk_r; our own
// TX is sampled back at 792 Msps into fb_samp, as the board's loopback does.
// The loop runs with short simulation parameters (8-frame rate measurement,
// an update every 4 frames, fn 150/30 Hz) so it locks within the stimulus; the
// real parameters are proven over hundreds of ms by tb_dpll.v / run_dpll.py.
// Everything observable is logged for check_core.py.
`timescale 1ns/1ps
module tb_core;
    parameter MAXCLK = 700000;
    parameter [6:0] SI_ADDR = 7'h6A;                 // the model's I2C address: not 0x55, the core must find it
    parameter real  SI_PPM  = 0.0;                   // the model's own crystal error
    parameter real  SI_START_HZ = 49.152e6;          // the model's factory start-up frequency
    parameter       INJ_EARLY = 0;                   // 1: "inject" sent before the Si514 is centred
    parameter       NO_INJECT = 0;                   // 1: never inject (the line must stay as it came)
    parameter real  GAP_AFTER_LOCK_US = -1.0;        // > 0: the line dies this long after LOCK...
    parameter real  GAP_US  = 20.0;                  // ...for this long (logged in out_gap.txt)
    parameter real  FB_DEAD_AFTER_LOCK_US = -1.0;    // > 0: TX_FB dies this long after LOCK, for good
                                                     // (U9 stuck; logged in out_fbdead.txt)
    parameter real  CLKS_STOP_AFTER_LOCK_US = -1.0;  // > 0: clk_s stops this long after LOCK and
                                                     // the run ends 200 us later (out_clkstop.txt)
    parameter real  WD_TW_NS = 10000.0;              // the board's bypass watchdog U11 (R23 x C25)
    // 99 MHz exactly: the stimulus is 8 samples per clock at 792 Msps, and the
    // Si514 model runs in real time, so a clock off by 100 ppm (#5.05) would
    // move the ring by 100 ppm against clk_r. Each edge is placed at its exact
    // time and rounded to 1 ps on its own, so the error never accumulates.
    reg clk_s = 0, rst = 1;
    reg clks_run = 1'b1;                             // 0: the PLL or its crystal has died
    real t_s = 0.0;
    always begin
        t_s = t_s + 500.0 / 99.0;
        #(t_s - $realtime) if (clks_run) clk_s = ~clk_s;
    end

    reg [7:0] mem [0:MAXCLK-1];
    integer nclk, i;
    reg [7:0] samp = 0;

    // ------------------------------------------------ frame-rate output (kept for boards
    // with an external clock multiplier): each clk_s word of fs_word covers the next
    // clk_s period, bit i at i x 1.26 ns; the edges are logged in sample units
    wire [7:0] fs_word; wire fs_late;
    integer ffs, fsn = 0;
    reg fs_last = 1'b0;
    always @(negedge clk_s) begin : fs_rebuild
        integer k;
        for (k = 0; k < 8; k = k + 1) begin
            if (fs_word[k] !== fs_last) begin
                $fwrite(ffs, "%0d %0d\n", fsn * 8 + k, fs_word[k]);
                fs_last = fs_word[k];
            end
        end
        fsn = fsn + 1;
    end

    // ------------------------------------------------ Si514 on the I2C bus
    wire scl_o, sda_o, sda_low;
    wire scl = scl_o;
    wire sda = sda_o & ~sda_low;
    si514_model #(.ADDR(SI_ADDR), .DSI_PPM(SI_PPM), .FCAL_NS(15000.0), .SETTLE_NS(2000.0),
                  .START_HZ(SI_START_HZ))
        u_dev (.scl(scl), .sda(sda), .sda_low(sda_low));
    // clk_r from the model's frequency. Each edge is scheduled at an exact
    // real time; only the individual delay is rounded to the 1 ps time step,
    // so the rounding never accumulates (a plain #(half period) would round
    // the period itself and allow the frequency only in ~100 ppm steps).
    reg clk_r = 0, r_run = 0;
    real t_edge = 0.0;
    always begin
        if (u_dev.freq > 0.0) begin
            if (!r_run) begin t_edge = $realtime; r_run = 1; end   // (re)start only
            t_edge = t_edge + 0.5e9 / u_dev.freq;
            #(t_edge - $realtime) clk_r = ~clk_r;
        end else begin
            r_run = 0; clk_r = 0; #10;
        end
    end

    // ------------------------------------------------ TX loopback, 8 samples per clk_s
    wire tx;
    reg [7:0] fb_samp = 0, fb_acc = 0;
    // eight samples 1.26 ns apart; no delay after the last, or the block
    // would outlast the clock period (1 ps rounding) and miss the next edge.
    // The word handed to the FPGA is the previous period's complete one.
    always @(posedge clk_s) begin : fb_sample
        integer k;
        fb_samp <= fb_acc;
        for (k = 0; k < 8; k = k + 1) begin
            if (k) #(1000.0 / 792.0);
            fb_acc[k] = (tx === 1'b1);
        end
    end

    // ---------------------------------------------------------------- DUT
    wire lock, bclk, fs, sd0, sd1, utx, mclk; wire [7:0] status;
    wire ibclk, ilrck, isd, injact;
    reg  urx = 1'b1;                                 // host command line, idle high
    reg  idin = 1'b0;                                // audio in, from the DSP model
    listener_core #(.HOLD(8), .HOLD_RE(24), .SI_QDIV(4), .SI_FCAL(24'd2000),
                    .L_FRAMES(8), .LN48(22'd132000), .LN44(22'd143673), .LSPLIT(22'd137836),
                    .LDEV(22'd175), .K48(20'd275050), .K44(20'd253277),
                    .UPD(4), .LOCK_N(4), .SHIFT_ACC(8), .LOCK_ACC(32), .UNLOCK_ACC(256),
                    .KP_A(40'sd5530205), .KI_A(40'sd217171),
                    .KP_T(40'sd1106041), .KI_T(40'sd8687)) dut (
        .clk_s(clk_s), .rst_s(rst), .samp(samp), .fb_samp(fb_samp), .clk_r(clk_r),
        .fs_word(fs_word), .fs_late(fs_late), .tx_regen(tx), .lock(lock),
        .tdm_bclk(bclk), .tdm_fs(fs), .tdm_sd0(sd0), .tdm_sd1(sd1), .uart_tx(utx), .mclk(mclk),
        .uart_rx(urx), .i2s_bclk(ibclk), .i2s_lrck(ilrck), .i2s_dout(isd),
        .i2s_din(idin), .inj_active(injact),
        .i2c_scl_o(scl_o), .i2c_sda_o(sda_o), .i2c_sda_i(sda), .status(status));

    // ------------------------------------------------------------ loggers
    integer ftx, ftdm, fua, flk, fsi;
    // the ring domain must not move before the Si514 is centred: first edges of
    // its outputs against the moment the loop reports the centring
    real t_cen = -1.0, t_mclk1 = -1.0, t_bclk1 = -1.0;
    always @(posedge dut.u_pll.centred) if (t_cen < 0.0) t_cen = $realtime;
    always @(posedge mclk) if (t_mclk1 < 0.0) t_mclk1 = $realtime;
    always @(posedge bclk) if (t_bclk1 < 0.0) t_bclk1 = $realtime;

    // The board's bypass watchdog U11 (74LVC1G123): retriggered by TX's rising
    // edges (TX_REGEN), cleared by LOCK; its Q, TX_SEL, is U2's select.
    // Modelled at 50 ns: TX_SEL = LOCK and a rising edge within WD_TW_NS.
    real t_rise = -1.0e12;
    reg  tx_sel = 1'b0;
    integer sel_drops = 0;                           // falls while LOCK stayed on and clk_s ran
    always @(posedge tx) t_rise = $realtime;
    always #50 begin
        if (tx_sel && lock && ($realtime - t_rise >= WD_TW_NS) && clks_run) sel_drops = sel_drops + 1;
        tx_sel = lock && ($realtime - t_rise < WD_TW_NS);
    end
    // clk_s stops for good after LOCK: LOCK, a clk_s register, stays where it
    // is - only the watchdog can take the ring back to bypass
    integer fcs, kw;
    real    t_stop;
    initial if (CLKS_STOP_AFTER_LOCK_US > 0.0) begin
        @(posedge lock);
        #(CLKS_STOP_AFTER_LOCK_US * 1000.0);
        clks_run = 1'b0; t_stop = $realtime;
        for (kw = 0; kw < 4000 && tx_sel; kw = kw + 1) #50;          // up to 200 us
        #1000;
        fcs = $fopen("out_clkstop.txt", "w");
        // stop, TX's last rising edge, TX_SEL's fall (ns); TX_SEL and LOCK now; false drops before
        $fwrite(fcs, "%0.3f %0.3f %0.3f %0d %0d %0d\n", t_stop, t_rise,
                t_stop + 50.0 * kw, tx_sel, lock, sel_drops);
        $fclose(fcs);
        $finish;
    end
    // TX feedback lost after LOCK: what the FPGA sees if U9's output sticks
    integer ffb;
    initial if (FB_DEAD_AFTER_LOCK_US > 0.0) begin
        @(posedge lock);
        #(FB_DEAD_AFTER_LOCK_US * 1000.0);
        @(negedge clk_s);
        force fb_samp = 8'h00;
        ffb = $fopen("out_fbdead.txt", "w");
        $fwrite(ffb, "%0.3f\n", $realtime);                  // ns
        $fclose(ffb);
    end
    // a dead line placed after LOCK, wherever LOCK happens to come
    integer fgap;
    real    tg0;
    initial if (GAP_AFTER_LOCK_US > 0.0) begin
        @(posedge lock);
        #(GAP_AFTER_LOCK_US * 1000.0);
        @(negedge clk_s);
        force samp = 8'h00; tg0 = $realtime;
        #(GAP_US * 1000.0);
        @(negedge clk_s);
        release samp;
        fgap = $fopen("out_gap.txt", "w");
        $fwrite(fgap, "%0.3f %0.3f\n", tg0, $realtime);      // ns
        $fclose(fgap);
    end
    reg tx_d = 0; integer run = 0;
    always @(posedge clk_r) begin                    // regenerated runs, in clk_r cycles
        run = run + 1;
        if (tx !== tx_d) begin
            if (lock) $fwrite(ftx, "%0d\n", run);
            run = 0; tx_d = tx;
        end
    end
    // TDM rows carry LOCK: before it the clock may still stop (Si514 centring)
    always @(posedge bclk) $fwrite(ftdm, "%0d%0d%0d%0d\n", fs, sd0, sd1, lock);
    // MCLK periods per TDM frame (FS rising edge to FS rising edge), and LOCK
    integer fmc, nmc = 0; reg fs_d = 0;
    always @(posedge mclk) nmc = nmc + 1;
    always @(posedge bclk) begin
        if (fs && !fs_d) begin $fwrite(fmc, "%0d %0d\n", nmc, lock); nmc = 0; end
        fs_d = fs;
    end
    // I2S: LRCK and data at every rising BCLK
    integer fi2s, fcfg;
    always @(posedge ibclk) $fwrite(fi2s, "%0d%0d\n", ilrck, isd);

    // host commands, 8N1 at 3 Mbaud = 33 clk_s per bit
    task send_byte(input [7:0] b);
        integer j;
        begin
            urx = 1'b0; repeat (33) @(posedge clk_s);
            for (j = 0; j < 8; j = j + 1) begin urx = b[j]; repeat (33) @(posedge clk_s); end
            urx = 1'b1; repeat (40) @(posedge clk_s);
        end
    endtask
    task send_cmd(input [7:0] c, w, l0, l1, l2, r0, r1, r2, input bad);
        reg [7:0] x;
        begin
            x = 8'hA5 ^ 8'h5A ^ c ^ w ^ l0 ^ l1 ^ l2 ^ r0 ^ r1 ^ r2;
            send_byte(8'hA5); send_byte(8'h5A); send_byte(c); send_byte(w);
            send_byte(l0); send_byte(l1); send_byte(l2);
            send_byte(r0); send_byte(r1); send_byte(r2);
            send_byte(bad ? ~x : x);
            $fwrite(fcfg, "%0d %0d %0d %0d %0d %0d %0d %0d %0d %0d\n", $time, c, bad, w, l0, l1, l2, r0, r1, r2);
        end
    endtask
    // one coefficient word for amp_out (command 03); commit with the last one
    integer wi;
    task send_word(input [7:0] a, input [31:0] v, input commit);
        send_cmd(8'h03, a, v[31:24], v[23:16], v[15:8], v[7:0], {7'd0, commit}, 8'd0, 1'b0);
    endtask

    // DSP model on the audio input: an I2S slave on our BCLK/LRCK, sending
    // L = 5A nnnn, R = C3 (nnnn + 1234) (24 bit), n + 1 every frame; the
    // changed bits' XOR then varies from frame to frame, so parity is exercised.
    // It goes into bytes 1..6, the bytes J3's two configurations pick from, so
    // that J3 and TDM are seen to carry the frame as it left us
    integer slot = 0; reg lr_d = 1'b0; reg [15:0] cnt = 16'd0;
    reg [23:0] dl = 24'd0, dr = 24'd0;
    always @(negedge ibclk) begin
        #1;
        if (!ilrck && lr_d) begin
            slot = 0; cnt = cnt + 16'd1;
            dl = {8'h5A, cnt}; dr = {8'hC3, cnt + 16'h1234};
        end else slot = slot + 1;
        lr_d = ilrck;
        if (slot >= 1 && slot <= 24)       idin = dl[24 - slot];
        else if (slot >= 33 && slot <= 56) idin = dr[56 - slot];
        else                               idin = 1'b0;
    end
    initial begin
        #1;
        @(negedge rst);
        if (INJ_EARLY) begin                                        // before the Si514 is centred:
            repeat (3000) @(posedge clk_s);                         // the ring domain is reset under it
            send_cmd(8'h02, 8'd3, 8'd1, 8'd2, 8'd3, 8'd4, 8'd5, 8'd6, 1'b0);
        end
        @(posedge lock);                                            // the loop has locked
        repeat (2000) @(posedge clk_s);
        // J3's coefficients (map: sim/dsp_asm.py): every biquad straight through
        // (b0 = 1.0 at 0, 5, .. 35), stream 0 to L x 1 and R x 0.5, gains at once
        // (1 - k = 0 at 46, with the commit)
        for (wi = 0; wi < 8; wi = wi + 1) send_word(5 * wi, 32'h1000_0000, 1'b0);   // not i: it feeds samp
        send_word(8'd40, 32'h1000_0000, 1'b0);
        send_word(8'd41, 32'h0800_0000, 1'b0);
        send_word(8'd46, 32'h0000_0000, 1'b1);
        send_cmd(8'h01, 8'd3, 8'd4, 8'd1, 8'd3, 8'd2, 8'd4, 8'd1, 1'b1);   // wrong XOR: must be ignored
        send_cmd(8'h01, 8'd3, 8'd3, 8'd4, 8'd1, 8'd2, 8'd1, 8'd4, 1'b0);   // A: 24 bit, scrambled
        repeat (50000) @(posedge clk_s);
        if (!INJ_EARLY && !NO_INJECT) begin
`ifdef NOFIX
            send_cmd(8'h02, 8'h83, 8'd1, 8'd2, 8'd3, 8'd4, 8'd5, 8'd6, 1'b0);   // (mutation: parity not fixed)
`else
            send_cmd(8'h02, 8'd3, 8'd1, 8'd2, 8'd3, 8'd4, 8'd5, 8'd6, 1'b0);    // inject 24 bit into 1..6
`endif
        end
        repeat (20000) @(posedge clk_s);
        send_cmd(8'h02, 8'd3, 8'd11, 8'd12, 8'd61, 8'd14, 8'd15, 8'd16, 1'b0); // names byte 61: refused
        repeat (20000) @(posedge clk_s);
        send_cmd(8'h01, 8'd2, 8'd1, 8'd2, 8'd0, 8'd3, 8'd4, 8'd0, 1'b0);   // B: 16 bit, bytes 1..4
        repeat (20000) @(posedge clk_s);
        send_cmd(8'h02, 8'd0, 8'd0, 8'd0, 8'd0, 8'd0, 8'd0, 8'd0, 1'b0);   // injection off
    end

    reg u_d = 1;
    always @(utx) begin $fwrite(fua, "%0t %0d\n", $time, utx); end
    reg lk_d = 0;
    always @(posedge clk_s) if (lock !== lk_d) begin $fwrite(flk, "%0t lock=%0d status=%b\n", $time, lock, status); lk_d = lock; end

    initial begin
        for (i = 0; i < MAXCLK; i = i + 1) mem[i] = 8'hxx;
        $readmemh("samples.hex", mem);
        nclk = 0;
        while (nclk < MAXCLK && mem[nclk] !== 8'hxx) nclk = nclk + 1;
        ftx = $fopen("out_tx.txt", "w"); ftdm = $fopen("out_tdm.txt", "w");
        fua = $fopen("out_uart.txt", "w");
        flk = $fopen("out_lock.txt", "w"); fmc = $fopen("out_mclk.txt", "w");
        fi2s = $fopen("out_i2s.txt", "w"); fcfg = $fopen("out_cfg.txt", "w");
        ffs = $fopen("out_fs.txt", "w");
        repeat (4) @(posedge clk_s);
        rst = 0;
        for (i = 0; i < nclk; i = i + 1) @(negedge clk_s) samp = mem[i];
        @(negedge clk_s) samp = {8{mem[nclk-1][7]}};
        repeat (200) @(posedge clk_s);
        $display("clocks=%0d status=%b lock=%0d fs_late=%0d", nclk, status, lock, fs_late);
        $fclose(ftx); $fclose(ftdm); $fclose(fua); $fclose(flk); $fclose(fmc); $fclose(fi2s); $fclose(fcfg);
        fsi = $fopen("out_si514.txt", "w");
        $fwrite(fsi, "addr %0h found %0h probes %0d fcal %0d small %0d bad_small %0d bad_rmw %0d nack %0d hs %0d freq %0.3f reg132 %0h centred %0.3f first_mclk %0.3f first_bclk %0.3f start_hz %0.1f\n",
                SI_ADDR, dut.u_si.addr, u_dev.n_probe,
                u_dev.n_fcal, u_dev.n_small, u_dev.bad_small, u_dev.bad_rmw, u_dev.n_nack,
                {u_dev.regs[11][1:0], u_dev.regs[10]}, u_dev.freq, u_dev.regs[132],
                t_cen, t_mclk1, t_bclk1, SI_START_HZ);
        $fclose(fsi);
        $fwrite(ffs, "late %0d\n", fs_late); $fclose(ffs);
        fcs = $fopen("out_wd.txt", "w");                  // the watchdog model over the whole run
        $fwrite(fcs, "%0d\n", sel_drops); $fclose(fcs);
        $finish;
    end
endmodule
