// dsp_img.h - the head unit's sound settings as coefficient words for J3.
//
// The FPGA's engine (listener_gw/rtl/dsp_core.v, map in dsp_map.h) runs
// stream 0 through 8 biquads per side and mixes three streams into L and R
// with gliding gains. This fills its coefficient set:
//   biquad 0   low shelf at cfg->bass_hz: bass steps x tone_db_step, plus
//              loudness (up to loud_db_max, reached at loud_db_at of volume)
//   biquad 1   high shelf at cfg->treble_hz: treble steps x tone_db_step
//   2..7       straight through
//   gains      stream 0, the amplifier's sink 1: its level (the volume and its
//              MixerLevel), the side balance turns away attenuated (silent
//              from bal_mute_steps on); streams 1, 2, two more of its sinks
//              (navigation, phone, chimes: amp_model's am_extras): each at
//              its own level and balance (snd_sink_db, snd_sink_balance),
//              silent while muted; no tone on them
//   glide      k = 1/256 per frame: a volume step settles in ~5 ms
// Coefficients are designed in double (RBJ cookbook shelves, S = 1) and
// rounded to Q4.28; each filter's stability is checked on the rounded words.
#pragma once

#include <stdint.h>

#include "dsp_map.h"
#include "sound.h"

// J3's streams 1 and 2: which of the amplifier's sinks, and whether it is muted
typedef struct {
    uint8_t sink;               // SinkNr; 0: the stream is off
    uint8_t muted;
} dsp_extra_t;

// Every word the host sends, in order; the last (1 - k) goes with the commit.
// fs: the ring's rate. muted: the amplifier's main sink is muted. ex: streams
// 1 and 2 (NULL: both off).
// Returns 0, or -1 if a shelf would not be stable once rounded (it is then
// left straight through; the gains are right either way).
int dsp_image(const snd_t *s, const snd_cfg_t *cfg, int muted, const dsp_extra_t ex[2], double fs,
              int32_t w[DSP_C_IMAGE]);

// The gain of stream 0 into L and R (linear, before rounding) and the two
// shelves' gains in dB, as dsp_image computes them - for the log and tests.
void dsp_levels(const snd_t *s, const snd_cfg_t *cfg, int muted, double *gl, double *gr,
                double *bass_db, double *treble_db);

// The same for stream 1 or 2 (no tone).
void dsp_extra_levels(const snd_t *s, const snd_cfg_t *cfg, const dsp_extra_t *ex, double *gl, double *gr);
