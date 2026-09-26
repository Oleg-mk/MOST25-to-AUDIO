// listener_core.v - the whole passive MOST25 listener, platform independent.
//
//   samp (8 per clk_s) -> rx_runlen -> rx_classify -> rx_framer
//        rx_classify -> regen (clk_r) -> inject -> tx_regen   ring, regenerated
//                                         (inject: our audio into chosen bytes)
//        rx_framer   -> tdm_out (clk_r) -> BCLK FS SD0 SD1  every frame byte, as it left us
//        rx_framer   -> ctrl_uart       -> uart_tx          raw control blocks
//        rx_framer   -> amp_out (clk_r) -> I2S              up to 3 sources, tone, volume,
//                                                          balance: L R, as they left us
//        uart_rx -> host_cmd -> amp_out, inject             host picks bytes, sets coefficients
//        I2S_DIN -> inject                                 audio in, on our own BCLK/LRCK
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
    parameter RELEARN   = 495000,           // clk_s without a locked frame before the receiver relearns
    // Si514 and its loop; the defaults are the real ones (sim/dpll_model.py,
    // sim/run_dpll.py), simulation of the whole core shortens them. The
    // Si514's I2C address is not a parameter: si514_ctrl finds it.
    parameter        SI_QDIV   = 62,        // I2C 393 kHz
    parameter [23:0] SI_FCAL   = 24'd1188000, // 12 ms
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
    output reg        mclk,                 // 512 Fs = clk_r / 2, for the receiver's DSP/codec
    output wire       uart_tx,
    input  wire       uart_rx,              // host commands, same baud as uart_tx
    output wire       i2s_bclk, i2s_lrck, i2s_dout,
    input  wire       i2s_din,              // audio in, for injection
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
    dpll #(.UPD(UPD), .LOCK_N(LOCK_N), .KP_A(KP_A), .KI_A(KI_A), .KP_T(KP_T), .KI_T(KI_T),
           .SHIFT_ACC(SHIFT_ACC), .LOCK_ACC(LOCK_ACC), .UNLOCK_ACC(UNLOCK_ACC),
           .L_FRAMES(L_FRAMES), .LN48(LN48), .LN44(LN44), .LSPLIT(LSPLIT), .LDEV(LDEV),
           .K48(K48), .K44(K44))
         u_pll (.clk(clk_s), .rst(rst_s), .rx_lk(rx_lk), .fe_valid(fev), .fe_rise(fer), .fe_t(fet),
                .tx_ev(tx_ev), .tx_t(tx_t), .regen_ok(ok2[1]), .si_busy(si_busy), .si_nack(si_nack),
                .do_centre(do_c), .do_update(do_u), .mfix(mfix), .hs(hs),
                .centred(si_centred), .locked(pll_lk), .gear(pll_gear));
    si514_ctrl #(.QDIV(SI_QDIV), .FCAL_WAIT(SI_FCAL))
         u_si (.clk(clk_s), .rst(rst_s), .do_centre(do_c), .do_update(do_u), .mfix(mfix), .hs(hs),
               .busy(si_busy), .out_off(si_off), .nack_err(si_nack),
               .scl_o(i2c_scl_o), .sda_o(i2c_sda_o), .sda_i(i2c_sda_i));

    // ------------------------------------------------ ring-clock domain reset
    // Held while the Si514 output is off (centring: clk_r stops or is
    // undefined for up to 10 ms); released 3 clk_r after it runs again.
    wire rr_hold = rst_s | si_off;
    reg [2:0] rr;
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
    tdm_out u_tdm (.clk_s(clk_s), .rst_s(rst_s), .byte_we(bwe), .byte_addr(ba), .byte_data(bd),
                   .frame_done(fd), .enable(rx_lk), .clk_r(clk_r), .rst_r(rst_r),
                   .sub_on(ij_on), .sub_w3(ij_w3), .sub_pos(ij_pos), .sub_val(ij_val),
                   .bclk(tdm_bclk), .fs(tdm_fs), .sd0(tdm_sd0), .sd1(tdm_sd1), .valid(tdm_valid),
                   .phase_n(tdm_n));

    // ------------------------------------- J3: the amplifier's outputs on I2S
    wire cv, hok; wire [7:0] cdat, hcmd; wire [55:0] hp;
    uart_rx    u_urx (.clk(clk_s), .rst(rst_s), .rxd(uart_rx), .valid(cv), .data(cdat));
    host_cmd   u_hc  (.clk(clk_s), .rst(rst_s), .rx_valid(cv), .rx_data(cdat),
                      .ok(hok), .cmd(hcmd), .p(hp));
    amp_out    u_amp (.clk_s(clk_s), .rst_s(rst_s), .cmd_ok(hok), .cmd(hcmd), .cmd_p(hp),
                      .byte_we(bwe), .byte_addr(ba), .byte_data(bd), .frame_done(fd),
                      .clk_r(clk_r), .rst_r(rst_r), .phase_n(tdm_n), .run(tdm_valid),
                      .sub_on(ij_on), .sub_w3(ij_w3), .sub_pos(ij_pos), .sub_val(ij_val),
                      .bclk(i2s_bclk), .lrck(i2s_lrck), .sd(i2s_dout),
                      .overrun());

    // ------------------------------------------------- audio into the ring
    inject     u_inj (.clk_s(clk_s), .rst_s(rst_s), .cmd_ok(hok), .cmd(hcmd), .cmd_p(hp),
                      .clk_r(clk_r), .rst_r(rst_r), .st(rg_st), .st_len(rg_len),
                      .phase_n(tdm_n), .i2s_run(tdm_valid), .din(i2s_din),
                      .tx(tx_regen), .active(inj_active),
                      .prev_on(ij_on), .prev_w3(ij_w3), .prev_pos(ij_pos), .prev_val(ij_val));

    // ------------------------------------------------------------------ MCLK
    // 512 Fs from the ring-locked clock: the receiver's master clock, at
    // 512 Fs for a 44.1/48 kHz system or 256 Fs for one at 88.2/96 kHz. It
    // stops with clk_r, i.e. while the Si514 is being centred.
    initial mclk = 1'b0;
    always @(posedge clk_r) mclk <= ~mclk;

    // ------------------------------------------------------------ UART out
    ctrl_uart u_ua (.clk(clk_s), .rst(rst_s), .byte_we(bwe), .byte_addr(ba), .byte_data(bd),
                    .frame_done(fd), .frame_par(fpar), .blk_idx(bi), .blk_known(bk),
                    .locked(rx_lk), .ui_q(ui_q), .txd(uart_tx));

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
