# Gowin EDA batch build: gw_sh build.tcl  (from listener_gw/board)
set_device GW2AR-LV18QN88C8/I7 -device_version C
add_file ../rtl/rx_runlen.v
add_file ../rtl/rx_classify.v
add_file ../rtl/rx_framer.v
add_file ../rtl/fs_fine.v
add_file ../rtl/regen.v
add_file ../rtl/tdm_out.v
add_file ../rtl/ctrl_uart.v
add_file ../rtl/i2c_master.v
add_file ../rtl/si514_ctrl.v
add_file ../rtl/tx_pre.v
add_file ../rtl/dpll.v
add_file ../rtl/uart_rx.v
add_file ../rtl/host_cmd.v
add_file ../rtl/dsp_core.v
add_file ../rtl/amp_out.v
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
run all
