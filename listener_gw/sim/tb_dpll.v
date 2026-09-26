// tb_dpll.v - the clock loop (dpll + si514_ctrl + i2c_master) against a Si514
// model and a frame-level ring, for long runs (hundreds of ms).
//
// Ring: frames every 1 / (FS (1 + DREL_PPM)) seconds of LOCAL time (DREL =
// ring offset relative to our own 27 MHz crystal), each preamble stamped on
// the 792 Msps grid with Gaussian jitter (JIT_NS rms) - fe events.
// TX: the regenerator plays frames at 1024 UI each on the Si514 frequency;
// after the Si514 output comes on it starts half full, D0_NS behind the ring;
// if the delay moves more than FIFO_LIM samples from there the FIFO slips:
// it restarts (regen_ok low for 10 us). Each TX preamble is stamped (tx_ev).
// Events: DROP_AT_MS > 0 takes the ring away for DROP_MS (holdover test).
// Log (out_dpll.txt): one line per loop update: time_ms, delay error in
// samples, u in ppm, gear, locked; plus a summary line at the end.
`timescale 1ns/1ps
module tb_dpll;
    parameter real FS         = 48000.0;
    parameter real DREL_PPM   = 0.0;
    parameter real DSI_PPM    = 0.0;
    parameter real JIT_NS     = 0.5;
    parameter real SIM_MS     = 300.0;
    parameter real D0_NS      = 1000.0;
    parameter integer FIFO_LIM = 600;
    parameter real DROP_AT_MS = 0.0;
    parameter real DROP_MS    = 5.0;
    parameter real FCAL_NS    = 10000000.0;
    parameter [6:0] SI_ADDR   = 7'h55;                  // the model's I2C address (found by probing)
    parameter real GLITCH_AT_MS = -1.0;                  // the Si514 ignores its address from here...
    parameter real GLITCH_MS  = 0.6;                     // ...for this long (longer than one update period)

    reg clk = 0, rst = 1;
    always #5.050505 clk = ~clk;                          // 99 MHz local clock

    // ------------------------------------------------ DUT: loop + Si514 control
    wire do_c, do_u, si_busy, si_off, si_nack, centred, locked, gear;
    wire [37:0] mfix; wire [9:0] hs;
    wire scl_o, sda_o, sda_low;
    wire scl = scl_o;
    wire sda = sda_o & ~sda_low;
    reg  fe_valid = 0, fe_rise = 0, tx_ev = 0, regen_ok = 0, rx_lk = 0;
    reg  [31:0] fe_t = 0, tx_t = 0;

    dpll u_pll (.clk(clk), .rst(rst), .rx_lk(rx_lk), .fe_valid(fe_valid), .fe_rise(fe_rise),
                .fe_t(fe_t), .tx_ev(tx_ev), .tx_t(tx_t), .regen_ok(regen_ok),
                .si_busy(si_busy), .si_nack(si_nack), .do_centre(do_c), .do_update(do_u),
                .mfix(mfix), .hs(hs), .centred(centred), .locked(locked), .gear(gear));
    si514_ctrl #(.FCAL_WAIT(24'd1188000)) u_si (.clk(clk), .rst(rst), .do_centre(do_c),
                .do_update(do_u), .mfix(mfix), .hs(hs), .busy(si_busy), .out_off(si_off),
                .nack_err(si_nack), .scl_o(scl_o), .sda_o(sda_o), .sda_i(sda));
    si514_model #(.ADDR(SI_ADDR), .DSI_PPM(DSI_PPM), .FCAL_NS(FCAL_NS),
                  .GLITCH_FROM_NS(GLITCH_AT_MS * 1e6), .GLITCH_TO_NS((GLITCH_AT_MS + GLITCH_MS) * 1e6))
        u_dev (.scl(scl), .sda(sda), .sda_low(sda_low));

    // ------------------------------------------------ ring and regenerator models
    real t_fr, t_next_rx, t_last_rx, ph, fr, t_tx_start, dly_err;
    real d0s;
    integer seed = 7, krx = 0, nslip = 0, maxdev = 0, e;
    reg  ring_on = 1, running = 0;
    real t_drop0, t_drop1;
    function [31:0] stamp;                                // floor(t x 0.792) with jitter
        input real t_ns;
        real j;
        begin
            j = $dist_normal(seed, 0, 1000) / 1000.0 * JIT_NS;
            stamp = $rtoi((t_ns + j) * 0.792);
        end
    endfunction

    integer flog;
    real ft;
    initial begin
        t_fr = 1.0e9 / (FS * (1.0 + DREL_PPM * 1e-6));
        t_next_rx = 5000.0; t_last_rx = 0.0; ph = 0.0; d0s = D0_NS * 0.792;
        t_drop0 = DROP_AT_MS * 1e6; t_drop1 = (DROP_AT_MS + DROP_MS) * 1e6;
        flog = $fopen("out_dpll.txt", "w");
        repeat (10) @(posedge clk);
        rst = 0;
    end

    // everything moves on the local clock; events are placed on the clock
    // tick that follows their true time (their stamps keep the true time)
    real now, prev_now, rx_stamp_t;
    initial prev_now = 0.0;
    reg  [31:0] rx_stamp;
    always @(posedge clk) begin
        prev_now = now;
        now = $realtime;
        fe_valid <= 1'b0; fe_rise <= 1'b0; tx_ev <= 1'b0;
        ring_on = !(DROP_AT_MS > 0.0 && now >= t_drop0 && now < t_drop1);
        // ring frames
        if (now >= t_next_rx) begin
            if (ring_on) begin
                fe_valid <= 1'b1; fe_rise <= 1'b1; fe_t <= stamp(t_next_rx);
                t_last_rx = t_next_rx; krx = krx + 1;
                rx_lk <= (krx > 4);
            end else rx_lk <= 1'b0;
            t_next_rx = t_next_rx + t_fr;
        end
        if (!ring_on) begin rx_lk <= 1'b0; krx = 0; end
        // regenerator: runs while the Si514 gives a clock and the ring is there
        fr = u_dev.freq;
        if (fr <= 0.0 || !ring_on) begin
            running = 0; regen_ok <= 1'b0;
        end else if (!running) begin
            // (re)start half full: the next TX preamble D0 after the next RX one
            running = 1; regen_ok <= 1'b1;
            t_tx_start = t_next_rx + D0_NS;
            ph = 1024.0 - (t_tx_start - now) * fr * 1e-9;
        end else begin
            ph = ph + (now - prev_now) * fr * 1e-9;    // the real tick (1 ps rounding)
            if (ph >= 1024.0) begin
                ph = ph - 1024.0;
                ft = now - ph / fr * 1e9;                  // when it crossed
                tx_ev <= 1'b1; tx_t <= stamp(ft) ;
                e = $rtoi((ft - t_last_rx) * 0.792 - d0s);
                // before the first centring the Si514 still runs at its
                // start-up frequency and slips are expected (LOCK is off);
                // from then on the loop owns the clock and is judged
                if (u_pll.centred) begin
                    if (e > maxdev) maxdev = e;
                    if (-e > maxdev) maxdev = -e;
                end
                if (e > FIFO_LIM || e < -FIFO_LIM) begin   // slip: FIFO over/underflow
                    if (u_pll.centred) nslip = nslip + 1;
                    running = 0; regen_ok <= 1'b0;
                end
            end
        end
    end

    // one log line per loop update (the write request): M in ppm from nominal
    real mreal;
    always @(posedge clk) if (do_u || do_c) begin
        mreal = $itor(mfix[37:29]) + $itor(mfix[28:0]) / 536870912.0;
        $fwrite(flog, "%0.3f %0d %0.3f %0d %0d %0d\n", $realtime / 1e6, e,
                (mreal / (hs == 10'd44 ? 67.6262664165 : 67.7799624765) - 1.0) * 1e6,
                gear, locked, do_c);
    end

    initial begin
        #(SIM_MS * 1e6);
        $fwrite(flog, "END slips=%0d maxdev=%0d locked=%0d centred=%0d fcal=%0d small=%0d bad_small=%0d bad_rmw=%0d nack=%0d freq=%0.3f addr=%0d found=%0d probes=%0d glitch=%0d nackerr=%0d\n",
                nslip, maxdev, locked, centred, u_dev.n_fcal, u_dev.n_small, u_dev.bad_small,
                u_dev.bad_rmw, u_dev.n_nack, u_dev.freq, SI_ADDR, u_si.addr, u_dev.n_probe,
                u_dev.n_glitch, si_nack);
        $fclose(flog);
        $display("END slips=%0d maxdev=%0d locked=%0d fcal=%0d small=%0d bad_small=%0d bad_rmw=%0d freq=%0.3f",
                 nslip, maxdev, locked, u_dev.n_fcal, u_dev.n_small, u_dev.bad_small, u_dev.bad_rmw, u_dev.freq);
        $finish;
    end
endmodule
