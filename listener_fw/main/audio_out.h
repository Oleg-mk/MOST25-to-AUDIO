// audio_out.h - the phone's audio out on the listener's I2S DIN.
//
// The ESP32's I2S port is a slave on the listener's BCLK and LRCK (64 Fs,
// locked to the MOST ring), so every sample it sends lands in a ring frame.
// The ring's rate (44.1 or 48 kHz) is read off the pace of the DMA; the
// phone's audio is brought onto it by components/ratematch.
#pragma once

#include <stdint.h>

// I2S slave channel and its task (core 1). The output is silent until the
// ring's clocks run and the phone streams.
void audio_out_start(void);

// The ring's frame rate, 44100 or 48000; 0 until the ring's clocks have run.
uint32_t audio_out_ring_rate(void);

// From the A2DP codec configuration (Bluetooth task): the stream's rate and
// whether it is mono.
void audio_out_set_source(uint32_t fs_in, int mono);

// Decoded 16-bit PCM from the A2DP sink (Bluetooth task).
void audio_out_push(const uint8_t *pcm, uint32_t len);
