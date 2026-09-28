// top_tangnano20k.v - listener_core on a Sipeed Tang Nano 20K (GW2AR-LV18QN88C8/I7).
//
// Clocks
//   27 MHz crystal -> rPLL: CLKOUT = 27 x 44 / 3 = 396 MHz (VCO 792 MHz, ODIV 2;
//   DS226 Table 3-20: VCO 500..1250 MHz, PFD 9 MHz >= 3 MHz)
//   396 MHz -> IDES8 FCLK: DDR sampling = 792 Msps (DS226 Table 3-17: IDES8
//   up to 1200 Mbps)
//   396 MHz -> CLKDIV /4 -> 99 MHz: IDES8 PCLK and the whole clk_s domain
//   CLK_1024 from the Si514 on pin 77 (GCLKT_1): the ring domain clk_r, which
//   this FPGA itself steers over I2C (dpll.v)
// IDES8 output order: Q0 is the EARLIEST sample of a word - checked by running
// Gowin's own model (IDE/simlib/gw2a/prim_sim.v) with an asymmetric pattern.
// TX_FB, the regenerated line fed back from the retiming flip-flop, goes
// through a second IDES8 on the same 792 Msps grid: the clock loop compares
// its preambles with the ring's to 1.26 ns.
// Pin numbers: schematic listener_hw/most_listener.kicad_sch, block 5, checked
// against the Sipeed Tang Nano 20K Datasheet v1.3 (corrected pinout, p. 5).
module top_tangnano20k (
    input  wire clk27,           // pin 4
    // ring: pins shared only with the empty LCD connector (datasheet v1.3 p. 5)
    input  wire rx_in,           // pin 27 LCD_B7   from U3 (RX_BUF isolation buffer)
    output wire tx_pre,          // pin 28 LCD_B6   to U9.D: retimed there on the Si514 CLK-, then U2.I1
    output wire lock,            // pin 31 LCD_B3   to U11 CLR (U11 Q drives U2.S while TX toggles) and U15 XSMT
    input  wire clk_1024,        // pin 77 GCLKT_1  Si514 CLK+ (1024 Fs)
    input  wire tx_fb,           // pin 25 LCD_HS   our TX, fed back (IDES8; its pair's pin 26 unused)
    inout  wire si_scl,          // pin 29 LCD_B5   Si514 I2C, its own bus
    inout  wire si_sda,          // pin 30 LCD_B4
    output wire tdm_bclk,        // pin 41 LCD_R4
    output wire tdm_fs,          // pin 48 LCD_DE
    output wire tdm_sd0,         // pin 49 LCD_BL
    output wire spdif,           // pin 42 LCD_R3   J3's L R as S/PDIF: TOSLINK transmitter and coax
    // not ring-critical: the BL616 HSPI lines (used as GPIO by Sipeed's examples),
    // the onboard audio amplifier's inputs (kept shut down by pa_en) and the
    // HDMI DDC pair (EDID)
    output wire tdm_sd1,         // pin 55 I2S_LRCK   (onboard amplifier input)
    output wire uart_tx,         // pin 56 I2S_BCLK   (onboard amplifier input)
    output wire mclk,            // pin 54 I2S_DIN    (onboard amplifier input) MCLK = 512 Fs, to J2
    input  wire uart_rx,         // pin 76 HSPI_DAT   host commands (stereo byte positions)
    output wire i2s_bclk,        // pin 72 HSPI_DIN1  stereo I2S, BCLK = 64 Fs
    output wire i2s_lrck,        // pin 71 HSPI_DIN0
    output wire i2s_dout,        // pin 53 EDID_CLK
    output wire i2s_mclk,        // pin 52 EDID_DAT   MCLK again, for J3
    input  wire i2s_din,         // pin 86 HSPI_CSN   audio in from the host, injected into the ring
    input  wire i2s_din2,        // pin 75 HSPI_DIR   audio in from the S/PDIF receiver's ASRC (U13)
    output wire src_bclk,        // pin 73 HSPI_DIN2  BCLK again, for U13 (SRC4192)
    output wire src_lrck,        // pin 74 HSPI_DIN3  LRCK again, for U13
    output wire pa_en,           // pin 51 PA_EN      the onboard amplifier, held shut down
    output wire [5:0] led_n      // pins 15 16 17 18 19 20, onboard, active low
);
    // ------------------------------------------------------------- clocks
    wire fclk, pll_lock, clk_s;
    rPLL #(
        .FCLKIN("27"), .IDIV_SEL(2), .FBDIV_SEL(43), .ODIV_SEL(2),
        .DYN_IDIV_SEL("false"), .DYN_FBDIV_SEL("false"), .DYN_ODIV_SEL("false"),
        .DYN_SDIV_SEL(2), .CLKFB_SEL("internal"), .CLKOUT_BYPASS("false"),
        .CLKOUTP_BYPASS("false"), .CLKOUTD_BYPASS("false"), .PSDA_SEL("0000"),
        .DUTYDA_SEL("1000"), .DYN_DA_EN("false"), .CLKOUT_FT_DIR(1'b1),
        .CLKOUTP_FT_DIR(1'b1), .CLKOUT_DLY_STEP(0), .CLKOUTP_DLY_STEP(0),
        .CLKOUTD_SRC("CLKOUT"), .CLKOUTD3_SRC("CLKOUT"), .DEVICE("GW2AR-18C")
    ) u_pll (
        .CLKIN(clk27), .CLKFB(1'b0), .RESET(1'b0), .RESET_P(1'b0),
        .FBDSEL(6'd0), .IDSEL(6'd0), .ODSEL(6'd0), .PSDA(4'd0), .DUTYDA(4'd0),
        .FDLY(4'd0), .CLKOUT(fclk), .LOCK(pll_lock), .CLKOUTP(), .CLKOUTD(), .CLKOUTD3()
    );
    CLKDIV #(.DIV_MODE("4"), .GSREN("false")) u_div (
        .HCLKIN(fclk), .RESETN(pll_lock), .CALIB(1'b0), .CLKOUT(clk_s));

    // ------------------------------------------------------------- reset
    // held until the PLL locks, then 2^16 clk_s (0.66 ms) more
    reg [16:0] por = 17'd0;
    always @(posedge clk_s or negedge pll_lock)
        if (!pll_lock) por <= 17'd0;
        else if (!por[16]) por <= por + 17'd1;
    // registered, and copied by synthesis wherever it would drive more than 64
    // loads: straight from the counter, one net across the whole chip was the
    // slowest path of clk_s
    reg rst_s /* synthesis syn_maxfan = 64 */;
    initial rst_s = 1'b1;
    always @(posedge clk_s) rst_s <= ~por[16];

    // ---------------------------------------------------------- sampler
    wire [7:0] q;
    IDES8 #(.GSREN("false"), .LSREN("true")) u_ides (
        .D(rx_in), .FCLK(fclk), .PCLK(clk_s), .CALIB(1'b0), .RESET(~pll_lock),
        .Q0(q[0]), .Q1(q[1]), .Q2(q[2]), .Q3(q[3]),
        .Q4(q[4]), .Q5(q[5]), .Q6(q[6]), .Q7(q[7]));
    reg [7:0] samp;
    always @(posedge clk_s) samp <= q;               // bit 0 = earliest

    wire [7:0] qf;
    IDES8 #(.GSREN("false"), .LSREN("true")) u_ides_fb (
        .D(tx_fb), .FCLK(fclk), .PCLK(clk_s), .CALIB(1'b0), .RESET(~pll_lock),
        .Q0(qf[0]), .Q1(qf[1]), .Q2(qf[2]), .Q3(qf[3]),
        .Q4(qf[4]), .Q5(qf[5]), .Q6(qf[6]), .Q7(qf[7]));
    reg [7:0] fb_samp;
    always @(posedge clk_s) fb_samp <= qf;

    // -------------------------------------------------------------- core
    wire scl_o, sda_o;
    wire [7:0] status;
    listener_core u_core (
        .clk_s(clk_s), .rst_s(rst_s), .samp(samp), .fb_samp(fb_samp),
        .clk_r(clk_1024),
        .fs_word(), .fs_late(), .tx_regen(tx_pre), .lock(lock),
        .tdm_bclk(tdm_bclk), .tdm_fs(tdm_fs), .tdm_sd0(tdm_sd0), .tdm_sd1(tdm_sd1),
        .uart_tx(uart_tx), .mclk(mclk), .uart_rx(uart_rx),
        .i2s_bclk(i2s_bclk), .i2s_lrck(i2s_lrck), .i2s_dout(i2s_dout),
        .i2s_din(i2s_din), .i2s_din2(i2s_din2), .spdif(spdif), .inj_active(),
        .i2c_scl_o(scl_o), .i2c_sda_o(sda_o), .i2c_sda_i(si_sda),
        .status(status));

    // J3 gets its own MCLK pin: one driver per connector, no stub between them.
    // U13 gets its own BCLK and LRCK the same way: it sits north of the bus that
    // goes to J3, the DAC and the host, and a branch of that bus to it would
    // cross every line on the way (board v1.2).
    assign i2s_mclk = mclk;
    assign src_bclk = i2s_bclk;
    assign src_lrck = i2s_lrck;

    // the module's own audio amplifier shares pins 54..56 with J2: kept shut down
    assign pa_en = 1'b0;

    // open drain: R11/R12 (2k to 3V3_SW) pull high
    assign si_scl = scl_o ? 1'bz : 1'b0;
    assign si_sda = sda_o ? 1'bz : 1'b0;

    // LEDs: rx locked, block known, Si514 centred, clock loop locked,
    //       regenerator ok, LOCK (regenerated path on the ring)
    assign led_n = ~{lock, status[5], status[3], status[2], status[1], status[0]};
endmodule
