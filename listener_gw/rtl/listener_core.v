// listener_core.v - the whole passive MOST25 listener, platform independent.
//
//   samp (8 per clk_s) -> rx_runlen -> rx_classify -> rx_framer
//        rx_classify -> regen (clk_r) -> inject -> tx_regen   ring, regenerated
//                                         (inject: our audio into chosen bytes)
//        rx_framer   -> tdm_out (clk_r) -> BCLK FS SD0 SD1  every frame byte, as it left us
//        rx_framer   -> ctrl_uart       -> uart_tx          raw control blocks
//        rx_framer   -> amp_out (clk_r) -> I2S, S/PDIF      up to 3 sources, tone, volume,
//                                                          balance: L R, as they left us
//        uart_rx -> host_cmd -> amp_out, inject, capture    host picks bytes, sets coefficients,
//                                                          asks for a capture or a dump
//        rx_runlen   -> capture -> ctrl_uart                the line's run lengths, on request
//        I2S_DIN / I2S_DIN2 -> inject                      audio in (the host M2 / the S/PDIF
//                                                          receiver's ASRC), on our own BCLK/LRCK
//        clk_r = 1024 Fs comes from a Si514 (I2C programmable XO) that this
//        FPGA steers itself (dpll.v): the regenerated TX is fed back (fb_samp),
//        its preambles are stamped like the ring's (tx_pre.v), and the delay
//        between the two, to 1.26 ns, is held constant by adjusting the Si514's
//        M over I2C (si514_ctrl.v). fs_fine keeps a 1.26 ns frame-rate square
//        wave (fs_word) for boards with an external clock multiplier instead.
//
// LOCK (regenerated or bypass, through the board watchdog U11) is decided in clk_s. clk_r
// does NOT always run: the Si514 output is off while it is centred (a large
// frequency change, up to 10 ms). Anything built in clk_r would freeze there
// - LOCK included, and a LOCK frozen high over a frozen TX is a broken ring.
// So clk_s watches clk_r directly and LOCK needs:
//   the receiver locked, the Si514 centred without an I2C error and its
//   output on, the loop locked, clk_r toggling, the regenerator running
//   without under/overflow, and our own TX coming back through U9 (TX_FB)
//   with a preamble at least every 4 ring frames -
// all of it continuously for HOLD frames before switching over, and any one
// of them lost drops it at once. What this cannot see is clk_s itself
// stopping: LOCK is a clk_s register. The board has the watchdog for that
// (listener_hw, block 2, U11): U2's select is LOCK only while TX_REGEN keeps
// toggling, and TX stops ~1 us after either clock does.
//
// One error on the line is not a reason to switch: the framer keeps its lock
// through one bad frame (rx_framer.v), the regenerator sends every run on with
// its measured length (regen.v), so `good` holds and LOCK with it. Before, a
// single bad bit unlocked the receiver, emptied the regenerator's FIFO and
// dropped LOCK for HOLD_RE - two phase steps for the nodes after us and a
// brief mute of the amplifier, from one bit.
//
// Switching either way is a phase step on the ring, and the MOST spec treats
// it as a normal event: "a node opens or closes its bypass" is a listed cause
// of unlock, and only unlocks adding up to more than tUnlock (60 ms min)
// without tLock (75..115 ms) of stable lock in between cause an Error
// Shutdown (MOST Specification 2V5, 3.2.5.2 and 3.8). A node relocks within a
// few frames (lock after 3 valid preambles, Oasis patent EP 1333580 B1), so
// one switch costs microseconds. What must never happen is flapping: after
// LOCK has once been lost it takes HOLD_RE frames (> 200 ms, beyond the
// largest tLock) of good state to come back.
module listener_core #(
    parameter HOLD      = 64,               // frames of good state before the first LOCK
    parameter HOLD_RE   = 10000,            // ... and before any later one (> 200 ms)
    parameter CAP_AW    = 16,               // capture buffer, 2^CAP_AW runs (16 = 32 BSRAM blocks)
    parameter RELEARN   = 495000,           // clk_s without a locked frame before the receiver relearns
    parameter INJ_FADE_LOG2 = 8,            // injection fades take 2^INJ_FADE_LOG2 frames (inject.v)
    parameter INJ_LEASE     = 198_000_000,  // clk_s cycles an injection command lasts without a repeat (2 s)
    // Si514 and its loop; the defaults are the real ones (sim/dpll_model.py,
    // sim/run_dpll.py), simulation of the whole core shortens them. The
    // Si514's I2C address is not a parameter: si514_ctrl finds it.
    parameter        SI_QDIV   = 62,        // I2C 393 kHz
    parameter [23:0] SI_FCAL   = 24'd1188000, // 12 ms
    parameter [17:0] SI_LOST   = 18'd131072,  // clk_s of a dead clk_r, not ours, before the Si514
                                              // counts as lost (1.3 ms; 0 = never, for a mutation run)
    parameter        L_FRAMES  = 64,
    parameter [21:0] LN48 = 22'd1056000, LN44 = 22'd1149388, LSPLIT = 22'd1102694,
    parameter [21:0] LDEV = 22'd1400,
    parameter [19:0] K48  = 20'd34381, K44 = 20'd31660,
    parameter        UPD       = 24,
    parameter        LOCK_N    = 16,
    parameter        SHIFT_ACC = 48, LOCK_ACC = 192, UNLOCK_ACC = 1536,   // sums of UPD errors: 2, 8, 64 samples mean
    parameter signed [39:0] KP_A = 40'sd245786, KI_A = 40'sd15443,
    parameter signed [39:0] KP_T = 40'sd12289,  KI_T = 40'sd39
) (
    input  wire       clk_s,                // 99 MHz, IDES8 parallel clock
    input  wire       rst_s,
    input  wire [7:0] samp,                 // bit 0 = earliest sample
    input  wire [7:0] fb_samp,              // our own TX, fed back, sampled like samp
    input  wire       clk_r,                // Si514 output, 1024 Fs
    output wire [7:0] fs_word,              // frame rate at 1.26 ns, 8 samples per clk_s
                                            // (only for an external clock multiplier)
    output wire       fs_late,              // sticky: a frame edge missed its output slot
    output wire       tx_regen,
    output reg        lock,                 // 1 = regenerated (U11 -> U2 select on the board)
    output wire       tdm_bclk, tdm_fs, tdm_sd0, tdm_sd1,
    output wire       mclk,                 // 512 Fs = clk_r / 2, for the receiver's DSP/codec
    output wire       uart_tx,
    input  wire       uart_rx,              // host commands, same baud as uart_tx
    output wire       i2s_bclk, i2s_lrck, i2s_dout,
    input  wire       i2s_din,              // audio in, for injection (the host M2)
    input  wire       i2s_din2,             // audio in from the S/PDIF receiver's ASRC (command 02, M[2])
    output wire       spdif,                // J3's L R as S/PDIF: TOSLINK transmitter and coax
    output wire       inj_active,           // clk_r: our audio is on the ring this frame
    output wire       i2c_scl_o, i2c_sda_o,
    input  wire       i2c_sda_i,
    output wire [7:0] status                // for LEDs / debug
);
    // ------------------------------------------------------------ receiver
    // wc counts clk_s words: with the sample index inside a word it is the
    // time base (1.26 ns units) for edges in and frame edges out
    reg [28:0] wc;
    always @(posedge clk_s) wc <= rst_s ? 29'd0 : wc + 29'd1;

    wire rv, rl, gl; wire [7:0] rlen; wire [31:0] run_tm;
    wire sv, sl; wire [1:0] sym; wire [3:0] slen; wire [15:0] ui_q; wire [31:0] sym_tm;
    wire bwe, fd, fpar, bk, rx_lk, er; wire [5:0] ba; wire [7:0] bd; wire [3:0] bi;
    wire fev, fer; wire [31:0] fet;

    rx_runlen   u_rl (.clk(clk_s), .rst(rst_s), .samp(samp), .wc(wc), .run_valid(rv), .run_len(rlen),
                      .run_level(rl), .glitch(gl), .run_t(run_tm));
    rx_classify #(.RELEARN(RELEARN))
                u_cl (.clk(clk_s), .rst(rst_s), .run_valid(rv), .run_len(rlen), .run_level(rl),
                      .glitch(gl), .run_t(run_tm), .locked(rx_lk), .sym_valid(sv), .sym(sym),
                      .sym_len(slen), .sym_level(sl), .ui_q(ui_q), .sym_t(sym_tm));
    rx_framer   u_fr (.clk(clk_s), .rst(rst_s), .sym_valid_i(sv), .sym_i(sym), .sym_t_i(sym_tm), .ui_q(ui_q),
                      .byte_we(bwe), .byte_addr(ba), .byte_data(bd), .frame_done(fd),
                      .frame_par(fpar), .blk_idx(bi), .blk_known(bk), .locked(rx_lk),
                      .err(er), .fs_sq(), .fe_valid(fev), .fe_rise(fer), .fe_t(fet));
    fs_fine     u_fs (.clk(clk_s), .rst(rst_s), .wc(wc), .locked(rx_lk),
                      .fe_valid(fev), .fe_rise(fer), .fe_t(fet), .word(fs_word), .late(fs_late));

    // --------------------------------------------- ring clock: Si514 + loop
    wire tx_ev; wire [31:0] tx_t;
    tx_pre u_txp (.clk(clk_s), .rst(rst_s), .samp(fb_samp), .wc(wc), .ui_q(ui_q),
                  .ev(tx_ev), .ev_t(tx_t));
    wire do_c, do_u, si_busy, si_off, si_nack, si_centred, pll_lk, pll_gear;
    wire [37:0] mfix; wire [9:0] hs;
    reg  [1:0] ok2;
    reg  si_lost;                           // the Si514 lost: below, after r_alive
    reg  loop_rst /* synthesis syn_maxfan = 64 */;   // the loop and the I2C side: rst_s, or lost
    wire si_scl, si_sda;
    dpll #(.UPD(UPD), .LOCK_N(LOCK_N), .KP_A(KP_A), .KI_A(KI_A), .KP_T(KP_T), .KI_T(KI_T),
           .SHIFT_ACC(SHIFT_ACC), .LOCK_ACC(LOCK_ACC), .UNLOCK_ACC(UNLOCK_ACC),
           .L_FRAMES(L_FRAMES), .LN48(LN48), .LN44(LN44), .LSPLIT(LSPLIT), .LDEV(LDEV),
           .K48(K48), .K44(K44))
         u_pll (.clk(clk_s), .rst(loop_rst), .rx_lk(rx_lk), .fe_valid(fev), .fe_rise(fer), .fe_t(fet),
                .tx_ev(tx_ev), .tx_t(tx_t), .regen_ok(ok2[1]), .si_busy(si_busy), .si_nack(si_nack),
                .do_centre(do_c), .do_update(do_u), .mfix(mfix), .hs(hs),
                .centred(si_centred), .locked(pll_lk), .gear(pll_gear));
    si514_ctrl #(.QDIV(SI_QDIV), .FCAL_WAIT(SI_FCAL))
         u_si (.clk(clk_s), .rst(loop_rst), .do_centre(do_c), .do_update(do_u), .mfix(mfix), .hs(hs),
               .busy(si_busy), .out_off(si_off), .nack_err(si_nack),
               .scl_o(si_scl), .sda_o(si_sda), .sda_i(i2c_sda_i));

    // ------------------------------------------------ ring-clock domain reset
    // Held until the Si514 has been centred once and while its output is off
    // (centring: clk_r stops or is undefined for up to 10 ms); released 3 clk_r
    // after it runs again. Until the first centring a part off the shelf runs
    // at its factory start-up frequency, anything to 250 MHz, and this domain
    // is built for 50: nothing in it may run before the clock is ours.
    wire rr_hold = rst_s | si_off | ~si_centred;
    reg [2:0] rr = 3'b111;                  // in reset from power-up, before any clk_r edge
    always @(posedge clk_r or posedge rr_hold)
        if (rr_hold) rr <= 3'b111; else rr <= {rr[1:0], 1'b0};
    wire rst_r = rr[2];

    // ---------------------------------------------------------- regenerator
    wire regen_ok, rg_tx, rg_st; wire [3:0] rg_len;
    regen u_rg (.clk_s(clk_s), .rst_s(rst_s), .sym_valid(sv), .len(slen), .enable(rx_lk),
                .clk_r(clk_r), .rst_r(rst_r), .tx(rg_tx), .ok(regen_ok),
                .st(rg_st), .st_len(rg_len));

    // --------------------------------------------------------------- TDM out
    // (with the bytes our audio replaced on the ring: what left us, not what came)
    wire tdm_valid; wire [9:0] tdm_n;
    wire ij_on, ij_w3; wire [35:0] ij_pos; wire [47:0] ij_val;
    wire t_bclk, t_fs, t_sd0, t_sd1;        // the pins: gated below while clk_r is dead
    tdm_out u_tdm (.clk_s(clk_s), .rst_s(rst_s), .byte_we(bwe), .byte_addr(ba), .byte_data(bd),
                   .frame_done(fd), .enable(rx_lk), .clk_r(clk_r), .rst_r(rst_r),
                   .sub_on(ij_on), .sub_w3(ij_w3), .sub_pos(ij_pos), .sub_val(ij_val),
                   .bclk(t_bclk), .fs(t_fs), .sd0(t_sd0), .sd1(t_sd1), .valid(tdm_valid),
                   .phase_n(tdm_n));

    // ------------------------------------- J3: the amplifier's outputs on I2S
    wire cv, hok; wire [7:0] cdat, hcmd; wire [55:0] hp;
    uart_rx    u_urx (.clk(clk_s), .rst(rst_s), .rxd(uart_rx), .valid(cv), .data(cdat));
    host_cmd   u_hc  (.clk(clk_s), .rst(rst_s), .rx_valid(cv), .rx_data(cdat),
                      .ok(hok), .cmd(hcmd), .p(hp));
    // the ring's rate, for the S/PDIF channel status: a UI under 16.8 samples is
    // 48 kHz (16.11 there, 17.53 at 44.1); a level, two flip-flops into clk_r
    reg       r48_s;
    reg [1:0] r48;
    always @(posedge clk_s) r48_s <= ui_q < 16'h10CC;
    always @(posedge clk_r) r48 <= {r48[0], r48_s};
    wire a_bclk, a_lrck, a_sd, a_spdif;     // the pins: gated below while clk_r is dead
    amp_out    u_amp (.clk_s(clk_s), .rst_s(rst_s), .cmd_ok(hok), .cmd(hcmd), .cmd_p(hp),
                      .byte_we(bwe), .byte_addr(ba), .byte_data(bd), .frame_done(fd),
                      .clk_r(clk_r), .rst_r(rst_r), .phase_n(tdm_n), .run(tdm_valid),
                      .sub_on(ij_on), .sub_w3(ij_w3), .sub_pos(ij_pos), .sub_val(ij_val), .rate48(r48[1]),
                      .bclk(a_bclk), .lrck(a_lrck), .sd(a_sd), .spdif(a_spdif),
                      .overrun());

    // ------------------------------------------------- audio into the ring
    inject #(.FADE_LOG2(INJ_FADE_LOG2), .LEASE(INJ_LEASE))
               u_inj (.clk_s(clk_s), .rst_s(rst_s), .cmd_ok(hok), .cmd(hcmd), .cmd_p(hp),
                      .clk_r(clk_r), .rst_r(rst_r), .st(rg_st), .st_len(rg_len),
                      .phase_n(tdm_n), .i2s_run(tdm_valid), .din(i2s_din), .din2(i2s_din2),
                      .tx(tx_regen), .active(inj_active),
                      .prev_on(ij_on), .prev_w3(ij_w3), .prev_pos(ij_pos), .prev_val(ij_val));

    // ------------------------------------------------------------------ MCLK
    // 512 Fs from the ring-locked clock: the receiver's master clock, at
    // 512 Fs for a 44.1/48 kHz system or 256 Fs for one at 88.2/96 kHz. It
    // stops with clk_r, i.e. while the Si514 is being centred, and is held
    // low until the first centring (a shelf part's start-up frequency is not
    // a clock for anything on J2 or J3).
    reg m_clk = 1'b0;                       // the pin: gated below while clk_r is dead
    always @(posedge clk_r) m_clk <= rst_r ? 1'b0 : ~m_clk;

    // ------------------------------------------------ capture (command 04)
    // M = P0: bit 0 capture anew, bit 1 dump what was captured, bit 2 (with
    // bit 0) dump as soon as the buffer is full. Registered decode.
    reg        c04;
    reg  [7:0] c04m;
    always @(posedge clk_s) begin c04 <= hok && hcmd == 8'h04 && !rst_s; c04m <= hp[55:48]; end
    wire cap_req, cap_take, cap_done, cap_busy; wire [319:0] cap_pkt;
    capture #(.AW(CAP_AW)) u_cap (.clk(clk_s), .rst(rst_s), .run_valid(rv), .run_len(rlen), .glitch(gl),
                                  .arm(c04 && c04m[0]), .auto_dump(c04m[2]), .dump(c04 && c04m[1]),
                                  .req(cap_req), .take(cap_take), .done(cap_done), .pkt(cap_pkt),
                                  .busy(cap_busy));

    // ------------------------------------------------------------ UART out
    wire u_txd;                             // the pin: held low while the Si514 is lost
    ctrl_uart u_ua (.clk(clk_s), .rst(rst_s), .byte_we(bwe), .byte_addr(ba), .byte_data(bd),
                    .frame_done(fd), .frame_par(fpar), .blk_idx(bi), .blk_known(bk),
                    .locked(rx_lk), .ui_q(ui_q), .txd(u_txd),
                    .cap_req(cap_req), .cap_pkt(cap_pkt), .cap_take(cap_take), .cap_done(cap_done));

    // ------------------------------------------------ LOCK, decided in clk_s
    // clk_r alive: a clk_r toggle must change within 64 clk_s (0.65 us);
    // the slowest clk_r (45 MHz) toggles every 22 ns.
    reg rtog = 1'b0;                       // no reset: clk_r may not run during rst_s
    always @(posedge clk_r) rtog <= ~rtog;
    reg [2:0] rt;
    reg [5:0] quiet;
    always @(posedge clk_s) begin
        rt <= {rt[1:0], rtog};
        if (rst_s || rt[2] != rt[1]) quiet <= 6'd0;
        else if (quiet != 6'h3F) quiet <= quiet + 6'd1;
    end
    wire r_alive = (quiet != 6'h3F);

    // ------------------------------------------ the lines built in clk_r, while it is dead
    // They freeze when clk_r stops, each at whatever level it had. With this module
    // on its own USB and 5V_SW off (the ring asleep, a laptop on the module), half of
    // them would hold 3.3 V on chips without supply - U13, U15, the TOSLINK
    // transmitter J6, the host M2 - and feed those rails through their input diodes.
    // So they are low from 0.65 us after clk_r's last edge, through a register, so
    // that no glitch of the compare reaches a pin. While the Si514 is centred they
    // carry nothing anyway. On from power-up, as r_alive is under rst_s: the lines
    // are the ring domain's reset levels until clk_r runs.
    reg pads_on = 1'b1;
    always @(posedge clk_s) pads_on <= r_alive;
    assign tdm_bclk = t_bclk & pads_on;  assign tdm_fs   = t_fs & pads_on;
    assign tdm_sd0  = t_sd0 & pads_on;   assign tdm_sd1  = t_sd1 & pads_on;
    assign mclk     = m_clk & pads_on;
    assign i2s_bclk = a_bclk & pads_on;  assign i2s_lrck = a_lrck & pads_on;
    assign i2s_dout = a_sd & pads_on;    assign spdif    = a_spdif & pads_on;

    // ------------------------------------------------------------ the Si514 lost
    // Its clock dead for SI_LOST clk_s, not by our command (si_off), after it had
    // been centred: its supply went with 5V_SW while this module runs on its own
    // USB (or the part failed). It comes back, if at all, at its factory frequency
    // with none of our settings, so the loop and the I2C side are held in reset
    // and centre it anew: resuming on the old M (dpll.v) would track a clock that
    // is not ours and never lock again. Meanwhile nothing of ours feeds its pins or
    // the host's: the I2C lines are held low, as R11/R12 pull them up to the
    // module's 3.3 V, and so is the UART to M2. A Si514 never centred is not lost:
    // the UART stays up to debug a part that does not start.
    reg [17:0] dead_t;
    always @(posedge clk_s) begin
        if (rst_s || r_alive || si_off) dead_t <= 18'd0;
        else if (dead_t != SI_LOST) dead_t <= dead_t + 18'd1;
        if (rst_s || r_alive) si_lost <= 1'b0;
        else if (SI_LOST != 18'd0 && dead_t == SI_LOST && si_centred) si_lost <= 1'b1;
        loop_rst <= rst_s | si_lost;
    end
    initial begin si_lost = 1'b0; loop_rst = 1'b1; end
    assign i2c_scl_o = si_scl & ~si_lost;
    assign i2c_sda_o = si_sda & ~si_lost;
    assign uart_tx   = u_txd & ~si_lost;

    always @(posedge clk_s) ok2 <= {ok2[0], regen_ok};
    // TX_FB alive: our TX comes back through U9 with a preamble every frame.
    // Four ring frames without one (U9 stuck or unclocked, the feedback open)
    // and the ring may be hanging on a line nobody regenerates.
    reg [2:0] fb_miss;
    always @(posedge clk_s)
        if (rst_s || tx_ev) fb_miss <= 3'd0;
        else if (fd && fb_miss != 3'd7) fb_miss <= fb_miss + 3'd1;
    wire fb_fresh = fb_miss < 3'd4;

    wire good = rx_lk & si_centred & ~si_off & ~si_nack & pll_lk & r_alive & ok2[1] & fb_fresh;

    reg [13:0] hold;
    reg        was_locked;                   // LOCK has been lost at least once
    wire [13:0] need = was_locked ? HOLD_RE[13:0] : HOLD[13:0];
    always @(posedge clk_s) begin
        if (rst_s) begin
            hold <= 14'd0; lock <= 1'b0; was_locked <= 1'b0;
        end else if (!good) begin
            hold <= 14'd0; lock <= 1'b0;
            if (lock) was_locked <= 1'b1;
        end else if (fd) begin
            if (hold != need) hold <= hold + 14'd1;
            else lock <= 1'b1;
        end
    end

    reg [1:0] tv;
    always @(posedge clk_s) tv <= {tv[0], tdm_valid};
    assign status = {si_nack, tv[1], ok2[1], r_alive, pll_lk, si_centred, bk, rx_lk};
endmodule
