// host.h - M2 as the listener's host.
//
// Control blocks come in from the FPGA on UART (IO4, 3 Mbaud); the host
// decodes the MOST control telegrams, follows which synchronous channels the
// AUX source and the amplifier use, and tells the FPGA (IO15) where to put
// our audio (command 02) and which channels to put out on J3 (command 01).
// Never a word on the MOST control channel itself: the listener only listens.
#pragma once

void host_start(void);

// The phone is streaming (A2DP started) or not: while it is, the phone goes
// into the AUX channels; while it is not, the board's TOSLINK input does, if
// its receiver holds lock on PCM (ain.h).
void host_streaming(int on);
