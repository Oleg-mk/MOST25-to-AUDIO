// Timing constraints for top_tangnano20k.v.
// clk27  : board crystal.
// clk_s  : 99 MHz from the PLL + CLKDIV; the tools derive fclk (396 MHz) and
//          clk_s from clk27 through the PLL and CLKDIV.
// clk_1024: Si514 CLK+, 1024 Fs; the fastest case is 48 kHz -> 49.152 MHz, steered
//          up to ~0.2 % above that (centre and loop), so 50 MHz is constrained.
// The two domains meet only through the gray-coded FIFO in regen.v, the toggle
// handshakes and the 2-flop synchronisers (below).
// PR1014 (generic routing for clk27_d): Gowin takes clk27 (pin 4, the module's
// crystal) to the PLL over general routing. The net feeds nothing but the PLL, whose
// loop filters what the route adds, and every clk_s path is timed from the PLL's output.
create_clock -name clk27 -period 37.037 [get_ports {clk27}]
create_clock -name clk_1024 -period 20.0 [get_ports {clk_1024}]
set_clock_groups -asynchronous -group [get_clocks {clk_1024}] -group [get_clocks {clk27}]
create_generated_clock -name fclk -source [get_ports {clk27}] -master_clock clk27 -multiply_by 44 -divide_by 3 [get_pins {u_pll/CLKOUT}]
create_generated_clock -name clk_s -source [get_pins {u_pll/CLKOUT}] -master_clock fclk -divide_by 4 [get_pins {u_div/CLKOUT}]
// clk_s and clk_1024 are not cut apart: every path between them must arrive within
// 10 ns, both ways, and is checked. The crossings are regen.v's gray-coded write
// pointer (wgray -> wg1, wg2), the toggle handshakes (tdm_out.v, inject.v, amp_out.v:
// data that holds still for microseconds behind a toggle) and the 2-flop
// synchronisers in listener_core.v. For the gray pointer the bound is what makes it
// work: gray code changes one bit a step only if the bits arrive within a step of each
// other, the pointer steps once a run and runs are at least 1 UI (20.3 ns at 48 kHz)
// apart, so with every bit in flight for at most 10 ns the bus's skew stays below half
// a step wherever placement puts it. (As one asynchronous clock group these paths were
// cut, and a max-delay on the pointer alone was never applied: Gowin reported no path
// under it.) Hold between the unrelated clocks means nothing and is not checked.
set_max_delay -from [get_clocks {clk_s}] -to [get_clocks {clk_1024}] 10.0
set_max_delay -from [get_clocks {clk_1024}] -to [get_clocks {clk_s}] 10.0
set_false_path -hold -from [get_clocks {clk_s}] -to [get_clocks {clk_1024}]
set_false_path -hold -from [get_clocks {clk_1024}] -to [get_clocks {clk_s}]
// The one output the ring depends on: TX_PRE goes to U9 (74LVC1G79), which
// retimes it on the same Si514 edge (CLK+ through R15) that this FPGA runs on
// (CLK+ through R10, pin 77). U9 captures on the NEXT edge, one clk_1024 period
// (20.3 ns at 48 kHz) after the edge that launched the data: the data must be
// there its setup time (2 ns for the LVC at 3.3 V) plus a nanosecond of board
// skew before it, and must not change until its hold time after the launching
// edge. Without this the path was never checked, and the README itself notes
// that placement moves every margin.
set_output_delay -clock clk_1024 -max 3.0 [get_ports {tx_pre}]
set_output_delay -clock clk_1024 -min -1.0 [get_ports {tx_pre}]
// I2S_DIN (audio in) and the TDM / I2S / MCLK outputs need no constraint: DIN
// is sampled 8 clk_1024 after the BCLK edge the host changes it on (inject.v),
// and the outputs change on BCLK's falling edge for a receiver that samples on
// the rising one, half a BCLK period (163 ns on J3, 41 ns on J2) later.
