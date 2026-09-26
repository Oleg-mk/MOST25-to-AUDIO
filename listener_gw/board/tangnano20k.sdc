// Timing constraints for top_tangnano20k.v.
// clk27  : board crystal.
// clk_s  : 99 MHz from the PLL + CLKDIV; the tools derive fclk (396 MHz) and
//          clk_s from clk27 through the PLL and CLKDIV.
// clk_1024: Si514 CLK+, 1024 Fs; the fastest case is 48 kHz -> 49.152 MHz, steered
//          up to ~0.2 % above that (centre and loop), so 50 MHz is constrained.
// The two domains meet only through the gray-coded FIFO in regen.v, the toggle
// handshake in tdm_out.v and the 2-flop synchronisers in listener_core.v.
create_clock -name clk27 -period 37.037 [get_ports {clk27}]
create_clock -name clk_1024 -period 20.0 [get_ports {clk_1024}]
set_clock_groups -asynchronous -group [get_clocks {clk_1024}] -group [get_clocks {clk27}]
create_generated_clock -name fclk -source [get_ports {clk27}] -master_clock clk27 -multiply_by 44 -divide_by 3 [get_pins {u_pll/CLKOUT}]
create_generated_clock -name clk_s -source [get_pins {u_pll/CLKOUT}] -master_clock fclk -divide_by 4 [get_pins {u_div/CLKOUT}]
set_clock_groups -asynchronous -group [get_clocks {clk_1024}] -group [get_clocks {clk_s}]
