// test_sound.c - host tests for components/mostctl: sound and dsp_img.
//
// Telegrams in, the head unit's settings out; settings in, J3's coefficient
// words out, judged on the rounded words: each shelf's response at a few
// frequencies, the gains, the clamps, stability. It also writes one
// coefficient set to image_example.txt, which check_image.py runs through
// the FPGA engine's bit-exact model (listener_gw/sim/dsp_asm.py).
#include <math.h>
#include <stdio.h>
#include <string.h>

#include "dsp_img.h"
#include "sound.h"

static int fails;
#define CHECK(cond, ...) do { if (!(cond)) { fails++; printf("    FAIL: "); \
    printf(__VA_ARGS__); printf("\n"); } } while (0)

static mm_tel_t tel(uint8_t fb, uint16_t fkt, uint8_t op, int len, const uint8_t *d)
{
    mm_tel_t t;
    memset(&t, 0, sizeof t);
    t.target = 0x0186; t.source = 0x0100;
    t.fblock = fb; t.inst = 0x01; t.fkt = fkt; t.op = op; t.len = (uint8_t)len;
    memcpy(t.data, d, (size_t)len);
    return t;
}

static int feed(snd_t *s, uint8_t fb, uint16_t fkt, uint8_t op, int len, const uint8_t *d)
{
    const mm_tel_t t = tel(fb, fkt, op, len, d);
    return snd_tel(s, &snd_cfg_default, &t);
}

static void test_decode(void)
{
    printf("sound:\n");
    snd_t s;
    snd_init(&s);
    CHECK(snd_volume_db(&s) <= SND_SILENT, "no volume heard: silent");
    const uint8_t v20[] = {20}, v0[] = {0};
    CHECK(feed(&s, 0x22, 0x400, MM_OP_STATUS, 1, v20) == 1, "Volume Status");
    CHECK(fabsf(snd_volume_db(&s) - (-12.041f)) < 0.01f, "20 of 40: %.3f dB (want -12.04)", snd_volume_db(&s));
    CHECK(feed(&s, 0x22, 0x400, MM_OP_SET, 1, v20) == 0, "the same again is no change");
    const uint8_t inc[] = {3};
    CHECK(feed(&s, 0x22, 0x400, MM_OP_INC, 1, inc) == 0, "Increment carries steps, not a value: ignored");
    CHECK(feed(&s, 0x22, 0x400, MM_OP_SETGET, 1, v0) == 1 && snd_volume_db(&s) <= SND_SILENT, "0 = silent");

    const uint8_t bal[] = {0xFD}, bass[] = {5}, treb[] = {0xFE}, loud0[] = {0};
    feed(&s, 0x22, 0x200, MM_OP_SET, 1, bal);
    feed(&s, 0x22, 0x202, MM_OP_STATUS, 1, bass);
    feed(&s, 0x22, 0x203, MM_OP_STATUS, 1, treb);
    feed(&s, 0x22, 0x201, MM_OP_STATUS, 1, loud0);
    CHECK(s.balance == -3 && s.bass == 5 && s.treble == -2 && !s.loudness &&
          s.have == (SND_H_BAL | SND_H_BASS | SND_H_TREBLE | SND_H_LOUD), "tone: %d %d %d %d", s.balance,
          s.bass, s.treble, s.loudness);

    // sources: the first in the list that has been heard wins
    const uint8_t f0[] = {0x00, 0x00, 20, 0, 0, 0, 0, 0, 0, 0, 0, 0};
    feed(&s, 0xF0, 0x409, MM_OP_STATUS, 12, f0);
    CHECK(fabsf(snd_volume_db(&s) - (-9.722f)) < 0.01f, "Jaguar XF 0xF0.0x409 byte 2, 20 of 35, over the "
          "catalogue's: %.3f", snd_volume_db(&s));
    const uint8_t bmw[] = {63};
    feed(&s, 0x20, 0x200, MM_OP_STATUS, 1, bmw);
    CHECK(fabsf(snd_volume_db(&s)) < 0.01f, "BMW 63 of 63 = 0 dB, over 0xF0");
    const uint8_t spk_nav[] = {0x00, 0x02, 0xE2, 0xE2, 0xE2, 0xE2, 0xE2, 0xE2, 0xE2};
    CHECK(feed(&s, 0x22, 0x46D, MM_OP_SET, 9, spk_nav) == 1 && fabsf(snd_volume_db(&s)) < 0.01f &&
          s.spk_have == 0x02 && fabsf(snd_sink_db(&s, &snd_cfg_default, 2) + 30.0f) < 0.01f,
          "SpeakerLevel to sink 2: that sink's level, not the volume");
    const uint8_t spk[] = {0x00, 0x01, 0xE2, 0xE1, 0xE2, 0xE4, 0xE2, 0xE2, 0xE2};   // -30 -31 -30 -28 ...
    feed(&s, 0x22, 0x46D, MM_OP_SET, 9, spk);
    CHECK(fabsf(snd_volume_db(&s) - (-28.0f)) < 0.01f, "SpeakerLevel dB on the wire, the loudest: %.1f",
          snd_volume_db(&s));
    const uint8_t bbal[] = {4};
    feed(&s, 0x20, 0x220, MM_OP_STATUS, 1, bbal);
    CHECK(s.balance == 4, "BMW balance");
    CHECK(snd_curve_db(80, 40) == 0.0f && snd_curve_db(10, 40) < -24.0f, "the curve clamps at 0 dB");
    printf("  volume sources heard 0x%X, volume %.1f dB\n", s.vol_have, snd_volume_db(&s));
}

// the amplifier's other sinks: their levels
static void test_sinks(void)
{
    printf("sinks:\n");
    const snd_cfg_t *cfg = &snd_cfg_default;
    snd_t s;
    snd_init(&s);
    CHECK(snd_sink_db(&s, cfg, 1) <= SND_SILENT && snd_sink_db(&s, cfg, 2) <= SND_SILENT &&
          snd_sink_db(&s, cfg, 3) <= SND_SILENT, "no volume heard: sinks 1..3 silent");
    CHECK(fabsf(snd_sink_db(&s, cfg, 4) + 6.0f) < 0.01f, "...the chimes (sink 4) at their own -6 dB: %.2f",
          snd_sink_db(&s, cfg, 4));
    const uint8_t v20[] = {20};
    feed(&s, 0x22, 0x400, MM_OP_STATUS, 1, v20);                    // -12.04 dB
    CHECK(fabsf(snd_sink_db(&s, cfg, 3) + 12.041f) < 0.01f && fabsf(snd_sink_db(&s, cfg, 5) + 12.041f) < 0.01f,
          "nothing of its own: a sink at the volume");
    CHECK(fabsf(snd_sink_db(&s, cfg, 4) + 6.0f) < 0.01f, "...but not the chimes: %.2f", snd_sink_db(&s, cfg, 4));
    // MixerLevel is not taken: on the XF the gateway's shadow of the amplifier sends it, in no known layout
    const uint8_t mix[] = {0, 0, 0xFD, 0x80, 0x80, 0xF6, 0x80, 0x80, 0xEC, 0x05, 0x80};
    CHECK(feed(&s, 0x22, 0x467, MM_OP_STATUS, 11, mix) == 0 && fabsf(snd_sink_db(&s, cfg, 2) + 12.041f) < 0.01f,
          "MixerLevel: no change, sink 2 at the volume");
    CHECK(snd_balance(&s) == 0, "no balance heard: 0");
    s.have |= SND_H_BAL;
    s.balance = -3;
    CHECK(snd_balance(&s) == -3, "one balance for every sink");

    // Jaguar XF's 0xF0.0x409, the gateway's Status: byte 0 the record's kind (0, the whole record),
    // byte 2 the volume of 35; bytes 7, 9, 10, 11 phone, navigation, voice, parking sensors, each the
    // level + 5, the level of 25
    snd_init(&s);
    const uint8_t xf[] = {0x00, 0x00, 20, 0, 0, 0, 0, 25, 0, 15, 25, 8};
    CHECK(feed(&s, 0xF0, 0x409, MM_OP_STATUS, 12, xf) == 1 && s.annc_have && s.park_have, "0x409: bytes 2, 9, 11");
    CHECK(fabsf(snd_sink_db(&s, cfg, 1) + 9.722f) < 0.01f, "sink 1 at byte 2, 20 of 35: %.3f",
          snd_sink_db(&s, cfg, 1));
    CHECK(fabsf(snd_sink_db(&s, cfg, 2) + 15.918f) < 0.01f, "sink 2 at byte 9, 15 - 5 = 10 of 25: %.3f",
          snd_sink_db(&s, cfg, 2));
    CHECK(fabsf(snd_sink_db(&s, cfg, 3) + 36.833f) < 0.01f, "sink 3 at byte 11, 8 - 5 = 3 of 25: %.3f",
          snd_sink_db(&s, cfg, 3));
    CHECK(fabsf(snd_sink_db(&s, cfg, 4) + 6.0f) < 0.01f, "sink 4 at no byte and not the volume: %.3f",
          snd_sink_db(&s, cfg, 4));
    CHECK(fabsf(snd_sink_db(&s, cfg, 5) + 9.722f) < 0.01f, "sink 5 at the volume, not byte 9: %.3f",
          snd_sink_db(&s, cfg, 5));
    CHECK(feed(&s, 0xF0, 0x409, MM_OP_STATUS, 12, xf) == 0, "the same again is no change");
    // the screen's Set to one channel ([channel, 0, level + 5]) and a kind-1 record are not taken
    const uint8_t set_pdc[] = {0x09, 0x00, 30};
    CHECK(feed(&s, 0xF0, 0x409, MM_OP_SET, 3, set_pdc) == 0 && fabsf(snd_sink_db(&s, cfg, 1) + 9.722f) < 0.01f,
          "Set [09, 0, 30]: its byte 2 is that channel's level, not the volume");
    const uint8_t kind1[] = {0x01, 0x00, 30, 0, 0, 0, 0, 30, 0, 30, 30, 30};
    CHECK(feed(&s, 0xF0, 0x409, MM_OP_STATUS, 12, kind1) == 0, "a kind-1 record: not taken");
    const uint8_t set_all[] = {0x00, 0x00, 30, 0, 0, 0, 0, 30, 0, 30, 30, 30};
    CHECK(feed(&s, 0xF0, 0x409, MM_OP_SET, 12, set_all) == 0 && feed(&s, 0xF0, 0x409, MM_OP_SETGET, 12, set_all) == 0,
          "a whole record as Set or SetGet: not taken either, 0x409 from its Status alone");

    // a byte counts only where the length covers it
    snd_init(&s);
    const uint8_t xfl[] = {0x00, 0x00, 35, 0, 0, 0, 0, 25, 0, 15, 25, 8};
    CHECK(feed(&s, 0xF0, 0x409, MM_OP_STATUS, 9, xfl) == 1 && !s.annc_have && !s.park_have &&
          fabsf(snd_sink_db(&s, cfg, 2)) < 0.01f, "9 bytes: byte 2 alone, sink 2 at the volume (35 of 35)");
    CHECK(feed(&s, 0xF0, 0x409, MM_OP_STATUS, 10, xfl) == 1 && s.annc_have && !s.park_have &&
          fabsf(snd_sink_db(&s, cfg, 2) + 15.918f) < 0.01f && fabsf(snd_sink_db(&s, cfg, 3)) < 0.01f,
          "10 bytes: byte 9 too, sink 3 still at the volume");
    CHECK(feed(&s, 0xF0, 0x409, MM_OP_STATUS, 11, xfl) == 0 && !s.park_have, "11 bytes: still no byte 11");
    CHECK(feed(&s, 0xF0, 0x409, MM_OP_STATUS, 12, xfl) == 1 && fabsf(snd_sink_db(&s, cfg, 3) + 36.833f) < 0.01f,
          "12 bytes: sink 3 at byte 11: %.3f", snd_sink_db(&s, cfg, 3));
    // a level at the offset or below is silent, as a volume of 0 is
    const uint8_t low[] = {0x00, 0x00, 0, 0, 0, 0, 0, 0, 0, 5, 0, 3};
    feed(&s, 0xF0, 0x409, MM_OP_STATUS, 12, low);
    CHECK(snd_sink_db(&s, cfg, 1) <= SND_SILENT && snd_sink_db(&s, cfg, 2) <= SND_SILENT &&
          snd_sink_db(&s, cfg, 3) <= SND_SILENT && fabsf(snd_sink_db(&s, cfg, 4) + 6.0f) < 0.01f,
          "bytes 9 = 5 and 11 = 3: silent; the chimes play on");

    // SpeakerLevel to a sink beats its 0x409 level; to sink 1 it is the volume
    feed(&s, 0xF0, 0x409, MM_OP_STATUS, 12, xf);
    const uint8_t spk2[] = {0x00, 0x02, 0xEC, 0xEE, 0xEC};           // -20 -18 -20
    feed(&s, 0x22, 0x46D, MM_OP_SET, 5, spk2);
    CHECK(fabsf(snd_sink_db(&s, cfg, 2) + 18.0f) < 0.01f, "SpeakerLevel to sink 2 beats byte 9: %.2f",
          snd_sink_db(&s, cfg, 2));
    const uint8_t spk3[] = {0x00, 0x03, 0xF1};
    feed(&s, 0x22, 0x46D, MM_OP_STATUS, 3, spk3);
    CHECK(fabsf(snd_sink_db(&s, cfg, 3) + 15.0f) < 0.01f, "SpeakerLevel to sink 3 beats byte 11: %.3f",
          snd_sink_db(&s, cfg, 3));
    const uint8_t spk4[] = {0x00, 0x04, 0xF7, 0xF4};                 // -9 -12
    CHECK(feed(&s, 0x22, 0x46D, MM_OP_STATUS, 4, spk4) == 1 && fabsf(snd_sink_db(&s, cfg, 4) + 9.0f) < 0.01f,
          "SpeakerLevel to sink 4 beats the fixed level: %.3f", snd_sink_db(&s, cfg, 4));
    const uint8_t spk1[] = {0x00, 0x01, 0xEC};
    feed(&s, 0x22, 0x46D, MM_OP_STATUS, 3, spk1);
    CHECK(fabsf(snd_sink_db(&s, cfg, 1) + 20.0f) < 0.01f && fabsf(snd_sink_db(&s, cfg, 5) + 20.0f) < 0.01f,
          "SpeakerLevel to sink 1: the volume, over byte 2: %.3f", snd_sink_db(&s, cfg, 1));
    const uint8_t spk9[] = {0x00, 0x09, 0xEC};
    CHECK(feed(&s, 0x22, 0x46D, MM_OP_SET, 3, spk9) == 0 && snd_sink_db(&s, cfg, 9) <= SND_SILENT,
          "sink 9: beyond what is kept");

    // a car without 0x409: sinks 2 and 3 at the volume, the chimes at their fixed level
    snd_init(&s);
    feed(&s, 0x22, 0x400, MM_OP_STATUS, 1, v20);
    CHECK(fabsf(snd_sink_db(&s, cfg, 2) + 12.041f) < 0.01f && fabsf(snd_sink_db(&s, cfg, 3) + 12.041f) < 0.01f,
          "no 0x409: sinks 2, 3 at the volume");
    CHECK(fabsf(snd_sink_db(&s, cfg, 4) + 6.0f) < 0.01f, "no 0x409: sink 4 at -6 dB, not the volume: %.3f",
          snd_sink_db(&s, cfg, 4));
    const uint8_t v0[] = {0};
    feed(&s, 0x22, 0x400, MM_OP_STATUS, 1, v0);
    CHECK(snd_sink_db(&s, cfg, 3) <= SND_SILENT && fabsf(snd_sink_db(&s, cfg, 4) + 6.0f) < 0.01f,
          "volume 0: sink 3 silent, the chimes not");
}

// |H| of one biquad as the engine holds it (b0 b1 b2 -a1 -a2, Q4.28), in dB
static double resp_db(const int32_t *w, double fs, double f)
{
    const double one = (double)(1L << DSP_FRAC);
    const double b0 = w[0] / one, b1 = w[1] / one, b2 = w[2] / one, a1 = -w[3] / one, a2 = -w[4] / one;
    const double th = 2 * M_PI * f / fs;
    const double zr1 = cos(th), zi1 = -sin(th), zr2 = cos(2 * th), zi2 = -sin(2 * th);
    const double nr = b0 + b1 * zr1 + b2 * zr2, ni = b1 * zi1 + b2 * zi2;
    const double dr = 1 + a1 * zr1 + a2 * zr2, di = a1 * zi1 + a2 * zi2;
    return 10 * log10((nr * nr + ni * ni) / (dr * dr + di * di));
}

static void test_image(void)
{
    printf("dsp_img:\n");
    const double one = (double)(1L << DSP_FRAC);
    snd_t s;
    int32_t w[DSP_C_IMAGE];
    snd_init(&s);
    s.loudness = 0;
    s.vol_have = 1u << SND_VOL_STD;
    s.vol_db[SND_VOL_STD] = -20.0f;
    CHECK(dsp_image(&s, &snd_cfg_default, 0, NULL, 48000, w) == 0, "flat set");
    int flat = 1;
    for (int b = 0; b < DSP_N_BQ; b++)
        flat &= w[DSP_C_BQ(b, 0)] == (1 << DSP_FRAC) && !w[DSP_C_BQ(b, 1)] && !w[DSP_C_BQ(b, 2)] &&
                !w[DSP_C_BQ(b, 3)] && !w[DSP_C_BQ(b, 4)];
    CHECK(flat, "flat tone: every biquad straight through");
    const double k = 1.0 / 256.0;
    CHECK(fabs(w[DSP_C_KT(0, 0)] / one / k - 0.1) < 1e-6 && w[DSP_C_KT(0, 1)] == w[DSP_C_KT(0, 0)],
          "-20 dB: L and R x 0.1 (%.7f)", w[DSP_C_KT(0, 0)] / one / k);
    CHECK(w[DSP_C_KT(1, 0)] == 0 && w[DSP_C_KT(1, 1)] == 0 && w[DSP_C_KT(2, 0)] == 0 && w[DSP_C_KT(2, 1)] == 0 &&
          w[DSP_C_KT(3, 0)] == 0 && w[DSP_C_KT(3, 1)] == 0, "no other sink: streams 1..3 silent");
    CHECK(w[DSP_C_1MK] == (int32_t)lround(one * (1 - k)), "1 - k");

    s.have |= SND_H_BAL;
    s.balance = 4;                                  // to the left: R turned down 8 dB
    dsp_image(&s, &snd_cfg_default, 0, NULL, 48000, w);
    const double rl = 20 * log10((double)w[DSP_C_KT(0, 1)] / w[DSP_C_KT(0, 0)]);
    CHECK(fabs(rl + 8.0) < 0.001, "balance +4: R %.3f dB under L", rl);
    s.balance = -10;
    dsp_image(&s, &snd_cfg_default, 0, NULL, 48000, w);
    CHECK(w[DSP_C_KT(0, 0)] == 0 && w[DSP_C_KT(0, 1)] > 0, "balance -10: L silent");
    s.balance = 0;
    dsp_image(&s, &snd_cfg_default, 1, NULL, 48000, w);
    CHECK(w[DSP_C_KT(0, 0)] == 0 && w[DSP_C_KT(0, 1)] == 0, "muted: both silent");

    // streams 1..3: sink 2 at its SpeakerLevel -30 dB, sink 3 muted, sink 4 (the chimes) at its fixed
    // -6 dB, not the volume's -20; the main mute is not theirs
    s.spk_have = 0x02;
    s.spk_db[1] = -30.0f;
    const dsp_extra_t ex[DSP_N_EXTRAS] = {{2, 0}, {3, 1}, {4, 0}};
    dsp_image(&s, &snd_cfg_default, 1, ex, 48000, w);
    CHECK(fabs(w[DSP_C_KT(1, 0)] / one / k - 0.031623) < 1e-5 && w[DSP_C_KT(1, 1)] == w[DSP_C_KT(1, 0)],
          "sink 2: -30 dB = x %.6f, the main sink muted", w[DSP_C_KT(1, 0)] / one / k);
    CHECK(w[DSP_C_KT(2, 0)] == 0 && w[DSP_C_KT(2, 1)] == 0 && w[DSP_C_KT(0, 0)] == 0, "sink 3 muted: silent");
    CHECK(fabs(w[DSP_C_KT(3, 0)] / one / k - 0.501187) < 1e-5 && w[DSP_C_KT(3, 1)] == w[DSP_C_KT(3, 0)],
          "sink 4 on stream 3: -6 dB = x %.6f, beside a muted sink 3", w[DSP_C_KT(3, 0)] / one / k);
    const dsp_extra_t mute4[DSP_N_EXTRAS] = {{2, 0}, {3, 0}, {4, 1}};
    dsp_image(&s, &snd_cfg_default, 0, mute4, 48000, w);
    CHECK(w[DSP_C_KT(3, 0)] == 0 && w[DSP_C_KT(3, 1)] == 0 && w[DSP_C_KT(1, 0)] > 0 && w[DSP_C_KT(2, 0)] > 0,
          "sink 4 muted: the chimes silent too, sinks 2 and 3 play on");
    s.balance = 4;
    dsp_image(&s, &snd_cfg_default, 0, ex, 48000, w);
    const double rl1 = 20 * log10((double)w[DSP_C_KT(1, 1)] / w[DSP_C_KT(1, 0)]);
    CHECK(fabs(rl1 + 8.0) < 0.001, "sink 2 follows the main balance: R %.3f dB under L", rl1);
    const dsp_extra_t off[DSP_N_EXTRAS] = {{0, 0}, {0, 0}, {0, 0}};
    dsp_image(&s, &snd_cfg_default, 0, off, 48000, w);
    CHECK(w[DSP_C_KT(1, 0)] == 0 && w[DSP_C_KT(2, 0)] == 0 && w[DSP_C_KT(3, 0)] == 0, "streams off: silent");
    s.spk_have = 0;
    s.balance = 0;

    // shelves, judged on the rounded words: the full gain well inside the
    // shelf (15 Hz; 0.45 fs), nothing well outside it (3 kHz; 300 Hz)
    double e_lo = 0, e_hi = 0, e_flat = 0;
    const double rates[2] = {44100, 48000};
    for (int r = 0; r < 2; r++) {
        const double fs = rates[r];
        s.have |= SND_H_BASS | SND_H_TREBLE;
        for (int st = -12; st <= 12; st += 4) {
            s.bass = (int8_t)st; s.treble = (int8_t)-st;
            CHECK(dsp_image(&s, &snd_cfg_default, 0, NULL, fs, w) == 0, "stable at %d / %d, %.0f Hz", st, -st, fs);
            e_lo = fmax(e_lo, fabs(resp_db(&w[DSP_C_BQ(0, 0)], fs, 15) - st));
            e_hi = fmax(e_hi, fabs(resp_db(&w[DSP_C_BQ(1, 0)], fs, 0.45 * fs) + st));
            e_flat = fmax(e_flat, fabs(resp_db(&w[DSP_C_BQ(0, 0)], fs, 3000)));
            e_flat = fmax(e_flat, fabs(resp_db(&w[DSP_C_BQ(1, 0)], fs, 300)));
        }
    }
    CHECK(e_lo < 0.25 && e_hi < 0.5 && e_flat < 0.1, "shelves: bass %.3f, treble %.3f, flat band %.3f dB off",
          e_lo, e_hi, e_flat);
    printf("  bass/treble -12..+12 dB at 44.1 and 48 kHz: full gain within %.3f dB (15 Hz) and %.3f dB "
           "(0.45 fs), the other band within %.3f dB\n", e_lo, e_hi, e_flat);
    s.bass = 40;
    double gl, gr, bdb, tdb;
    dsp_levels(&s, &snd_cfg_default, 0, &gl, &gr, &bdb, &tdb);
    CHECK(fabs(bdb - 12.0) < 1e-9, "bass clamped to 12 dB");

    // loudness: +8 dB of bass at -40 dB and below, none at 0 dB
    s.bass = 0; s.treble = 0; s.loudness = 1;
    s.vol_db[SND_VOL_STD] = -40.0f;
    dsp_levels(&s, &snd_cfg_default, 0, &gl, &gr, &bdb, &tdb);
    CHECK(fabs(bdb - 8.0) < 1e-6, "loudness at -40 dB: +%.2f dB", bdb);
    s.vol_db[SND_VOL_STD] = -10.0f;
    dsp_levels(&s, &snd_cfg_default, 0, &gl, &gr, &bdb, &tdb);
    CHECK(fabs(bdb - 2.0) < 1e-6, "loudness at -10 dB: +%.2f dB", bdb);
    s.vol_db[SND_VOL_STD] = 0.0f;
    dsp_levels(&s, &snd_cfg_default, 0, &gl, &gr, &bdb, &tdb);
    CHECK(fabs(bdb) < 1e-9 && fabs(gl - 1.0) < 1e-9, "full volume: no loudness, gain 1");

    // the set check_image.py runs through the engine model
    snd_init(&s);
    s.loudness = 0;
    s.vol_have = 1u << SND_VOL_STD;
    s.vol_db[SND_VOL_STD] = -20.0f;
    s.have = SND_H_BAL | SND_H_BASS | SND_H_TREBLE;
    s.balance = 4; s.bass = 6; s.treble = -4;
    dsp_image(&s, &snd_cfg_default, 0, NULL, 48000, w);
    FILE *f = fopen("image_example.txt", "w");
    if (f) {
        fprintf(f, "# fs 48000, volume -20 dB, balance +4 (R -8 dB), bass +6 dB, treble -4 dB\n");
        for (int a = 0; a < DSP_C_IMAGE; a++)
            fprintf(f, "%d\n", (int)w[a]);
        fclose(f);
    }

    // ...and the mix: sink 1 flat at -20 dB, sink 2 (stream 1, mono) at its own SpeakerLevel -10 dB,
    // sink 3 (stream 2) at its own -26 dB, sink 4 (stream 3, the chimes) at its own -14 dB
    snd_init(&s);
    s.loudness = 0;
    s.vol_have = 1u << SND_VOL_STD;
    s.vol_db[SND_VOL_STD] = -20.0f;
    s.spk_have = 0x0E;
    s.spk_db[1] = -10.0f;
    s.spk_db[2] = -26.0f;
    s.spk_db[3] = -14.0f;
    const dsp_extra_t mixex[DSP_N_EXTRAS] = {{2, 0}, {3, 0}, {4, 0}};
    dsp_image(&s, &snd_cfg_default, 0, mixex, 48000, w);
    f = fopen("image_mix.txt", "w");
    if (f) {
        fprintf(f, "# fs 48000, sink 1 -20 dB flat; sink 2 (stream 1) -10 dB; sink 3 (stream 2) -26 dB; "
                   "sink 4 (stream 3) -14 dB\n");
        for (int a = 0; a < DSP_C_IMAGE; a++)
            fprintf(f, "%d\n", (int)w[a]);
        fclose(f);
    }
}

int main(void)
{
    test_decode();
    test_sinks();
    test_image();
    printf(fails ? "\n%d FAILED\n" : "\nall passed\n", fails);
    return fails != 0;
}
