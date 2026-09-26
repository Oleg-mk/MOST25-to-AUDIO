// dpll.v - the ring clock: an FPGA phase-locked loop steering a Si514 over I2C.
//
// The regenerator replays the ring's runs on clk_r (the Si514 output, 1024 Fs)
// out of a FIFO. clk_r must follow the ring exactly, or the FIFO drains or
// fills. This loop measures how far behind the ring our own TX is - each
// preamble on the TX loopback minus the same preamble on the input, both
// stamped on the 792 Msps grid (1.26 ns) - and holds that delay constant by
// steering the Si514's M (0.026 ppb steps). Design and gains: sim/dpll_model.py.
//
// 1. Measure. Once the receiver is locked, 64 frame periods of the ring are
//    counted in samples (L64); this picks the rate (48 or 44.1 kHz) and the
//    ring's offset from nominal, as seen by the local 27 MHz crystal.
// 2. Centre. M_c = M_nom + (L_nom64 - L64) x K, a "large frequency change"
//    (output off, FCAL, 10 ms) - so the loop starts within the crystals'
//    error (~+/-100 ppm) of the ring even if the ring is 0.1 % off nominal.
//    No division: K = M_nom / L_nom64 is a constant per rate.
// 3. Track. Every UPD frames the delay errors of those frames are summed
//    (acc) and a PI step computes u, written as M = M_c + u ("small frequency
//    change", glitch-free within +/-1000 ppm). Two gears: acquisition
//    (fn 40 Hz, zeta 1) until |mean error| < 2 samples for 16 updates, then
//    tracking (fn 2 Hz, zeta 1), switched bumplessly. `locked` after 16 more
//    updates under 8 samples; an error over 64 samples drops it and re-acquires.
// Holdover: if the ring goes, M stays where it was and clk_r keeps running.
// When it comes back, the rate is measured again: same rate and within
// 500 ppm of the current M - carry on; otherwise centre again. If u ever
// needs more than 900 ppm, the loop re-centres on M_c + u.
// All arithmetic is pipelined, one adder or multiplier per clock: nothing
// here is urgent (an update every 0.5 ms), and clk_s is 99 MHz.
module dpll #(
    parameter        UPD      = 24,                 // frames per loop update
    parameter signed [39:0] KP_A = 40'sd245786,     // gains, Q8, per sum of UPD errors
    parameter signed [39:0] KI_A = 40'sd15443,
    parameter signed [39:0] KP_T = 40'sd12289,
    parameter signed [39:0] KI_T = 40'sd39,
    parameter        SHIFT_ACC = 48,                // |acc| below in acquisition: ready to shift (2 samples mean)
    parameter        LOCK_ACC = 192,                // |acc| below in tracking: a good update (8 samples mean)
    parameter        UNLOCK_ACC = 1536,             // |acc| above in tracking: lost (64 samples)
    parameter        LOCK_N   = 16,
    parameter        L_FRAMES = 64,                 // frames in the rate measurement
    parameter [37:0] M48  = 38'd36306575326,        // M x 2^29 for 49.152 MHz, HS_DIV 44
    parameter [37:0] M44  = 38'd36389090270,        // M x 2^29 for 45.1584 MHz, HS_DIV 48
    parameter [21:0] LN48 = 22'd1056000,            // 64 frames in samples at 48 kHz
    parameter [21:0] LN44 = 22'd1149388,            // ... at 44.1 kHz (1149387.76)
    parameter [19:0] K48  = 20'd34381,              // M48 / LN48, LSB of M per sample
    parameter [19:0] K44  = 20'd31660,
    parameter [21:0] LSPLIT = 22'd1102694,          // between the two rates
    parameter [21:0] LDEV = 22'd1400,               // |L_nom - L64| beyond: not a MOST ring
    parameter [37:0] RESUME = 38'd18153288,         // 500 ppm of M: resume without centring
    parameter signed [39:0] ULIM = 40'sd32675918,   // 900 ppm of M: re-centre beyond
    parameter [23:0] BACKOFF = 24'd9900000          // 100 ms before retrying after a NACK
) (
    input  wire        clk,
    input  wire        rst,
    input  wire        rx_lk,                       // receiver locked to frames
    input  wire        fe_valid,                    // ring frame edges (rx_framer)
    input  wire        fe_rise,
    input  wire [31:0] fe_t,
    input  wire        tx_ev,                       // our TX preambles (tx_pre)
    input  wire [31:0] tx_t,
    input  wire        regen_ok,                    // regenerator running (clk_s)
    input  wire        si_busy,
    input  wire        si_nack,
    output reg         do_centre,
    output reg         do_update,
    output reg  [37:0] mfix,
    output reg  [9:0]  hs,
    output reg         centred,                     // the Si514 has been set up
    output reg         locked,
    output reg         gear                         // 0 acquisition, 1 tracking
);
    // one-hot: each state is one flip-flop, so a state test is a wire, not a
    // decode. The enables of u and integ (80 flip-flops) hang off S_TRACK and
    // S_CEN; decoded from three bits they were the slowest path of clk_s
    localparam I_IDLE = 0, I_MEAS = 1, I_CALC = 2, I_CEN = 3, I_CENW = 4,
               I_TRACK = 5, I_BACK = 6, I_PIPE = 7;
    localparam [7:0] S_IDLE = 8'b0000_0001, S_MEAS = 8'b0000_0010, S_CALC = 8'b0000_0100,
                     S_CEN = 8'b0000_1000, S_CENW = 8'b0001_0000, S_TRACK = 8'b0010_0000,
                     S_BACK = 8'b0100_0000, S_PIPE = 8'b1000_0000;
    reg  [7:0]  st;
    reg  [6:0]  nf;                                  // frames measured
    reg  [31:0] t0, lmeas;
    reg         cls48, cur48;                        // measured / programmed rate
    reg  [37:0] mc;                                  // centre M
    reg signed [39:0] integ, u;                      // Q8, LSB of M
    reg  [23:0] bo;
    reg         seen_busy, cen_pend;
    reg  [2:0]  pw;

    // step 2 arithmetic, one register per step, and S_CEN's two tests on its
    // result, registered too (5 clocks in all). A centring is rare, so S_PIPE
    // simply waits 8 clocks for this chain to settle; its inputs (lmeas,
    // cls48, cur48, centred, mc, u) do not change meanwhile.
    reg signed [22:0] delta;
    reg        [22:0] adelta;
    reg signed [39:0] prod, mt, mnow, dm;
    reg        [39:0] adm;
    reg               bad_rate, can_resume;
    always @(posedge clk) begin
        delta  <= $signed({1'b0, cls48 ? LN48 : LN44}) - $signed({1'b0, lmeas[21:0]});
        adelta <= delta[22] ? -delta : delta;
        prod   <= delta * $signed({1'b0, cls48 ? K48 : K44});
        mt     <= $signed({2'b0, cls48 ? M48 : M44}) + prod;
        mnow   <= $signed({2'b0, mc}) + (u >>> 8);
        dm     <= mt - mnow;
        adm    <= dm[39] ? -dm : dm;
        bad_rate   <= adelta > {1'b0, LDEV};                              // not a MOST rate
        can_resume <= centred && cls48 == cur48 && adm < {2'b0, RESUME};  // M still fits
    end

    // delay measurement: 1) the delay of this TX preamble behind the last
    // ring preamble, 2) its error against the target, 3) the sum over UPD frames
    reg  [31:0] rx_last;
    reg         rx_have, tgt_have, ok_d;
    reg  [15:0] tgt;
    reg         ev1, ev2;
    reg  [31:0] dly1;
    reg signed [16:0] e2;
    reg signed [19:0] acc;                           // sum of UPD errors
    reg  [5:0]  cnt;
    reg  [4:0]  good;
    always @(posedge clk) begin
        ev1  <= tx_ev;
        dly1 <= tx_t - rx_last;
    end

    // step 3 arithmetic: p1 products and |a1|, p2 partial sums and the gear
    // tests, p3 new u and gears, p4 the M to write, p5 write or re-centre
    reg signed [19:0] a1;
    reg        [19:0] aa1;
    reg               p1, p2, p3, p4, p5, upd_pend;
    reg signed [39:0] pp, pi, ppt, s1, bump, mnx;
    reg               gnow, unl, orng;
    wire signed [23:0] kp = gear ? KP_T[23:0] : KP_A[23:0];     // gains fit 24 bits
    wire signed [23:0] ki = gear ? KI_T[23:0] : KI_A[23:0];
    // shifting early leaves a residual frequency error the 2 Hz tracking gear
    // takes hundreds of ms to remove (~9 ns of wander in the model); at 2
    // samples it is about halved and the lock comes ~10 ms later
    wire        shift = !gear && gnow && good == LOCK_N - 1;    // acquisition -> tracking
    wire signed [39:0] ul = u >>> 8;                            // u in LSB of M

    always @(posedge clk) begin
        do_centre <= 1'b0; do_update <= 1'b0;
        ok_d <= regen_ok;
        ev2 <= 1'b0;
        p1 <= 1'b0; p2 <= p1; p3 <= p2; p4 <= p3; p5 <= p4;
        if (rst) begin
            st <= S_IDLE; nf <= 7'd0; t0 <= 32'd0; lmeas <= 32'd0; cls48 <= 1'b1; cur48 <= 1'b1;
            mc <= 38'd0; integ <= 40'sd0; u <= 40'sd0; bo <= 24'd0; seen_busy <= 1'b0;
            cen_pend <= 1'b0; pw <= 3'd0;
            mfix <= 38'd0; hs <= 10'd44; centred <= 1'b0; locked <= 1'b0; gear <= 1'b0;
            rx_last <= 32'd0; rx_have <= 1'b0; tgt_have <= 1'b0; tgt <= 16'd0; e2 <= 17'sd0;
            acc <= 20'sd0; cnt <= 6'd0; good <= 5'd0; a1 <= 20'sd0; aa1 <= 20'd0;
            p1 <= 1'b0; p2 <= 1'b0; p3 <= 1'b0; p4 <= 1'b0; p5 <= 1'b0; upd_pend <= 1'b0;
            pp <= 40'sd0; pi <= 40'sd0; ppt <= 40'sd0; s1 <= 40'sd0; bump <= 40'sd0;
            mnx <= 40'sd0; gnow <= 1'b0; unl <= 1'b0; orng <= 1'b0;
        end else begin
            case (1'b1)                                      // one-hot
            // ---------------------------------------------------- 1. measure
            st[I_IDLE]: begin
                locked <= 1'b0; nf <= 7'd0; upd_pend <= 1'b0;
                if (rx_lk) st <= S_MEAS;
            end
            st[I_MEAS]: begin
                if (!rx_lk) st <= S_IDLE;
                else if (fe_valid && fe_rise) begin
                    if (nf == 7'd0) t0 <= fe_t;
                    if (nf == L_FRAMES) begin lmeas <= fe_t - t0; st <= S_CALC; end
                    nf <= nf + 7'd1;
                end
            end
            // ---------------------------------------------------- 2. centre
            st[I_CALC]: begin
                cls48 <= lmeas[21:0] < LSPLIT;
                pw <= 3'd0;
                st <= (lmeas[31:22] != 0) ? S_IDLE : S_PIPE;      // not even close: again
            end
            st[I_PIPE]: begin
                pw <= pw + 3'd1;
                if (pw == 3'd7) st <= S_CEN;
            end
            st[I_CEN]: begin
                if (bad_rate) st <= S_IDLE;                      // not a MOST rate: again
                else if (can_resume) begin
                    st <= S_TRACK; gear <= 1'b0; good <= 5'd0;      // resume where we were
                    tgt_have <= 1'b0; rx_have <= 1'b0; acc <= 20'sd0; cnt <= 6'd0;
                end else if (!si_busy) begin
                    mc <= mt[37:0]; mfix <= mt[37:0]; hs <= cls48 ? 10'd44 : 10'd48;
                    cur48 <= cls48; integ <= 40'sd0; u <= 40'sd0;
                    do_centre <= 1'b1; seen_busy <= 1'b0; cen_pend <= 1'b0; locked <= 1'b0;
                    st <= S_CENW;
                end
            end
            st[I_CENW]: begin                                 // wait for the Si514 to settle
                if (si_busy) seen_busy <= 1'b1;
                else if (seen_busy) begin
                    if (si_nack) begin st <= S_BACK; bo <= BACKOFF; end
                    else begin
                        centred <= 1'b1; st <= S_TRACK; gear <= 1'b0; good <= 5'd0;
                        tgt_have <= 1'b0; rx_have <= 1'b0; acc <= 20'sd0; cnt <= 6'd0;
                    end
                end
            end
            st[I_BACK]: if (bo != 0) bo <= bo - 24'd1; else st <= S_IDLE;
            // ---------------------------------------------------- 3. track
            st[I_TRACK]: begin
                if (!rx_lk) begin
                    st <= S_IDLE; locked <= 1'b0;                   // holdover: M stays
                end else begin
                    if (regen_ok && !ok_d) tgt_have <= 1'b0;       // regenerator (re)started
                    if (fe_valid && fe_rise) begin rx_last <= fe_t; rx_have <= 1'b1; end
                    // 2) this preamble's error; the first one after a start is the target
                    if (ev1 && rx_have && dly1[31:13] == 19'd0 && regen_ok) begin
                        if (!tgt_have) begin
                            tgt <= dly1[15:0]; tgt_have <= 1'b1;
                        end else begin
                            e2 <= $signed({1'b0, dly1[15:0]}) - $signed({1'b0, tgt});
                            ev2 <= 1'b1;
                        end
                    end
                    // 3) the sum over UPD frames
                    if (ev2) begin
                        if (cnt == UPD - 1) begin
                            a1 <= acc + e2; p1 <= 1'b1; acc <= 20'sd0; cnt <= 6'd0;
                        end else begin
                            acc <= acc + e2; cnt <= cnt + 6'd1;
                        end
                    end
                    if (p1) begin
                        pp <= kp * a1; pi <= ki * a1; ppt <= $signed(KP_T[23:0]) * a1;
                        aa1 <= a1[19] ? -a1 : a1;
                    end
                    if (p2) begin
                        s1   <= integ + pi;
                        bump <= pp - ppt;
                        gnow <= aa1 < (gear ? LOCK_ACC : SHIFT_ACC);
                        unl  <= aa1 > UNLOCK_ACC;
                    end
                    if (p3) begin                                   // new u, gears, lock
                        u     <= s1 + pp;
                        integ <= s1 + (shift ? bump : 40'sd0);      // bumpless
                        if (gnow) begin
                            if (good == LOCK_N - 1) begin
                                good <= 5'd0;
                                if (!gear) gear <= 1'b1; else locked <= 1'b1;
                            end else good <= good + 5'd1;
                        end else begin
                            good <= 5'd0;
                            if (gear && unl) begin gear <= 1'b0; locked <= 1'b0; end
                        end
                    end
                    if (p4) begin
                        mnx  <= $signed({2'b0, mc}) + ul;
                        orng <= ul > ULIM || ul < -ULIM;
                    end
                    if (p5) begin                                   // write, or re-centre
                        if (orng) begin
                            mc <= mnx[37:0]; mfix <= mnx[37:0]; integ <= 40'sd0; u <= 40'sd0;
                            locked <= 1'b0; upd_pend <= 1'b0; cen_pend <= 1'b1;
                        end else begin
                            mfix <= mnx[37:0]; upd_pend <= 1'b1;
                        end
                    end else if (cen_pend && !si_busy) begin
                        do_centre <= 1'b1; seen_busy <= 1'b0; cen_pend <= 1'b0; st <= S_CENW;
                    end else if (upd_pend && !si_busy) begin
                        do_update <= 1'b1; upd_pend <= 1'b0;
                    end
                end
            end
            default: st <= S_IDLE;
            endcase
        end
    end
endmodule
