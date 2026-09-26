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
    const uint8_t f0[] = {0x01, 0x00, 20, 0, 0, 0, 0, 0, 5, 0, 3};
    feed(&s, 0xF0, 0x409, MM_OP_SET, 11, f0);
    CHECK(fabsf(snd_volume_db(&s) - (-12.041f)) < 0.01f, "Jaguar XF 0xF0.0x409 byte 2 over the catalogue's");
    const uint8_t bmw[] = {63};
    feed(&s, 0x20, 0x200, MM_OP_STATUS, 1, bmw);
    CHECK(fabsf(snd_volume_db(&s)) < 0.01f, "BMW 63 of 63 = 0 dB, over 0xF0");
    const uint8_t spk_nav[] = {0x00, 0x02, 0xE2, 0xE2, 0xE2, 0xE2, 0xE2, 0xE2, 0xE2};
    CHECK(feed(&s, 0x22, 0x46D, MM_OP_SET, 9, spk_nav) == 0, "SpeakerLevel to sink 2: not the main zone");
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
    CHECK(dsp_image(&s, &snd_cfg_default, 0, 48000, w) == 0, "flat set");
    int flat = 1;
    for (int b = 0; b < DSP_N_BQ; b++)
        flat &= w[DSP_C_BQ(b, 0)] == (1 << DSP_FRAC) && !w[DSP_C_BQ(b, 1)] && !w[DSP_C_BQ(b, 2)] &&
                !w[DSP_C_BQ(b, 3)] && !w[DSP_C_BQ(b, 4)];
    CHECK(flat, "flat tone: every biquad straight through");
    const double k = 1.0 / 256.0;
    CHECK(fabs(w[DSP_C_KT(0, 0)] / one / k - 0.1) < 1e-6 && w[DSP_C_KT(0, 1)] == w[DSP_C_KT(0, 0)],
          "-20 dB: L and R x 0.1 (%.7f)", w[DSP_C_KT(0, 0)] / one / k);
    CHECK(w[DSP_C_KT(1, 0)] == 0 && w[DSP_C_KT(2, 1)] == 0, "navigation and phone silent");
    CHECK(w[DSP_C_1MK] == (int32_t)lround(one * (1 - k)), "1 - k");

    s.have |= SND_H_BAL;
    s.balance = 4;                                  // to the left: R turned down 8 dB
    dsp_image(&s, &snd_cfg_default, 0, 48000, w);
    const double rl = 20 * log10((double)w[DSP_C_KT(0, 1)] / w[DSP_C_KT(0, 0)]);
    CHECK(fabs(rl + 8.0) < 0.001, "balance +4: R %.3f dB under L", rl);
    s.balance = -10;
    dsp_image(&s, &snd_cfg_default, 0, 48000, w);
    CHECK(w[DSP_C_KT(0, 0)] == 0 && w[DSP_C_KT(0, 1)] > 0, "balance -10: L silent");
    s.balance = 0;
    dsp_image(&s, &snd_cfg_default, 1, 48000, w);
    CHECK(w[DSP_C_KT(0, 0)] == 0 && w[DSP_C_KT(0, 1)] == 0, "muted: both silent");

    // shelves, judged on the rounded words: the full gain well inside the
    // shelf (15 Hz; 0.45 fs), nothing well outside it (3 kHz; 300 Hz)
    double e_lo = 0, e_hi = 0, e_flat = 0;
    const double rates[2] = {44100, 48000};
    for (int r = 0; r < 2; r++) {
        const double fs = rates[r];
        s.have |= SND_H_BASS | SND_H_TREBLE;
        for (int st = -12; st <= 12; st += 4) {
            s.bass = (int8_t)st; s.treble = (int8_t)-st;
            CHECK(dsp_image(&s, &snd_cfg_default, 0, fs, w) == 0, "stable at %d / %d, %.0f Hz", st, -st, fs);
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
    dsp_image(&s, &snd_cfg_default, 0, 48000, w);
    FILE *f = fopen("image_example.txt", "w");
    if (f) {
        fprintf(f, "# fs 48000, volume -20 dB, balance +4 (R -8 dB), bass +6 dB, treble -4 dB\n");
        for (int a = 0; a < DSP_C_IMAGE; a++)
            fprintf(f, "%d\n", (int)w[a]);
        fclose(f);
    }
}

int main(void)
{
    test_decode();
    test_image();
    printf(fails ? "\n%d FAILED\n" : "\nall passed\n", fails);
    return fails != 0;
}
