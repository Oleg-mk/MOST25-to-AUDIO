# Gowin EDA batch build: gw_sh build.tcl  (from listener_gw/board)
set_device GW2AR-LV18QN88C8/I7 -device_version C
add_file ../rtl/rx_runlen.v
add_file ../rtl/rx_classify.v
add_file ../rtl/rx_framer.v
add_file ../rtl/fs_fine.v
add_file ../rtl/regen.v
add_file ../rtl/tdm_out.v
add_file ../rtl/capture.v
add_file ../rtl/ctrl_uart.v
add_file ../rtl/i2c_master.v
add_file ../rtl/si514_ctrl.v
add_file ../rtl/tx_pre.v
add_file ../rtl/dpll.v
add_file ../rtl/uart_rx.v
add_file ../rtl/host_cmd.v
add_file ../rtl/dsp_core.v
add_file ../rtl/amp_out.v
add_file ../rtl/spdif_tx.v
add_file ../rtl/inject.v
add_file ../rtl/listener_core.v
add_file top_tangnano20k.v
add_file tangnano20k.cst
add_file tangnano20k.sdc
set_option -top_module top_tangnano20k
set_option -output_base_name listener
set_option -verilog_std v2001
set_option -use_mspi_as_gpio 1
set_option -use_sspi_as_gpio 1
set_option -timing_driven 1
# the bitstream is read from the module's flash at 25 MHz (250/10) instead of the default 2.5 MHz:
# one bit a clock, the 7.26 Mbit took 2.9 s to configure every time 5V_SW came up with the ring,
# long enough to miss the head unit's Connect; about 290 ms now (UG290 Table 3-3; the flash's limit
# is 66.6 MHz). The same setting as JLR-MOST-Reader's (its commit 171035c); -bit_compress leaves the
# bitstream uncompressed in this gw_sh, so it is not set.
set_option -loading_rate 250/10
run all
