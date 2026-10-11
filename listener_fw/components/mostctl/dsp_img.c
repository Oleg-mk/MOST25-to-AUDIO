// dsp_img.c - see dsp_img.h.
#include "dsp_img.h"

#include <math.h>
#include <stddef.h>

#define K_GLIDE   (1.0 / 256.0)
#define ONE       ((double)(1L << DSP_FRAC))

static int32_t q28(double x)
{
    const double v = x * ONE;
    if (v >= 2147483647.0)
        return INT32_MAX;
    if (v <= -2147483648.0)
        return INT32_MIN;
    return (int32_t)lround(v);
}

static double clamp(double v, double lo, double hi)
{
    return v < lo ? lo : v > hi ? hi : v;
}

// a level into L and R: the side the balance turns away from is attenuated
static void side_gains(const snd_cfg_t *cfg, double v, int bal, double *gl, double *gr)
{
    const int n = bal < 0 ? -bal : bal;                         // positive: to the left
    const double away = n >= cfg->bal_mute_steps ? 0.0 : pow(10.0, -n * cfg->bal_db_step / 20.0);
    *gl = v * (bal < 0 ? away : 1.0);
    *gr = v * (bal > 0 ? away : 1.0);
}

void dsp_levels(const snd_t *s, const snd_cfg_t *cfg, int muted, double *gl, double *gr,
                double *bass_db, double *treble_db)
{
    const double vdb = snd_sink_db(s, cfg, 1);
    const double v = (muted || vdb <= SND_SILENT + 1.0) ? 0.0 : pow(10.0, vdb / 20.0);
    side_gains(cfg, v, (s->have & SND_H_BAL) ? s->balance : 0, gl, gr);
    const double tmax = cfg->tone_db_max;
    double loud = 0.0;
    if (s->loudness && v > 0.0 && cfg->loud_db_at < 0.0)
        loud = cfg->loud_db_max * clamp(vdb / cfg->loud_db_at, 0.0, 1.0);
    *bass_db = clamp(((s->have & SND_H_BASS) ? s->bass : 0) * cfg->tone_db_step, -tmax, tmax) + loud;
    *treble_db = clamp(((s->have & SND_H_TREBLE) ? s->treble : 0) * cfg->tone_db_step, -tmax, tmax);
}

// RBJ cookbook shelf, S = 1, a0 normalised: b0 b1 b2 a1 a2
static void shelf(int high, double fs, double f0, double gdb, double c[5])
{
    const double a = pow(10.0, gdb / 40.0);
    const double w = 2.0 * M_PI * f0 / fs;
    const double cw = cos(w), sw = sin(w);
    const double al = sw / 2.0 * sqrt(2.0);                     // S = 1
    const double s2 = 2.0 * sqrt(a) * al;
    const double sg = high ? -1.0 : 1.0;                        // the sign of the (a-1)cw terms
    const double a0 = (a + 1) + sg * (a - 1) * cw + s2;
    c[0] = a * ((a + 1) - sg * (a - 1) * cw + s2) / a0;
    c[1] = sg * 2 * a * ((a - 1) - sg * (a + 1) * cw) / a0;
    c[2] = a * ((a + 1) - sg * (a - 1) * cw - s2) / a0;
    c[3] = -sg * 2 * ((a - 1) + sg * (a + 1) * cw) / a0;
    c[4] = ((a + 1) + sg * (a - 1) * cw - s2) / a0;
}

static void straight(int32_t *w)
{
    w[0] = q28(1.0);
    w[1] = w[2] = w[3] = w[4] = 0;
}

// the words of one biquad: b0 b1 b2, then -a1 -a2 (the engine only adds)
static int biquad(int32_t *w, int high, double fs, double f0, double gdb)
{
    if (fabs(gdb) < 0.01) {
        straight(w);
        return 0;
    }
    double c[5];
    shelf(high, fs, f0, gdb, c);
    for (int i = 0; i < 3; i++)
        w[i] = q28(c[i]);
    w[3] = q28(-c[3]);
    w[4] = q28(-c[4]);
    const double a1 = -(double)w[3] / ONE, a2 = -(double)w[4] / ONE;
    if (!(fabs(a2) < 1.0 && fabs(a1) < 1.0 + a2)) {
        straight(w);
        return -1;
    }
    return 0;
}

void dsp_extra_levels(const snd_t *s, const snd_cfg_t *cfg, const dsp_extra_t *ex, double *gl, double *gr)
{
    *gl = *gr = 0.0;
    if (!ex || !ex->sink || ex->muted)
        return;
    const double db = snd_sink_db(s, cfg, ex->sink);
    if (db <= SND_SILENT + 1.0)
        return;
    side_gains(cfg, pow(10.0, db / 20.0), snd_sink_balance(s, ex->sink), gl, gr);
}

int dsp_image(const snd_t *s, const snd_cfg_t *cfg, int muted, const dsp_extra_t ex[DSP_N_EXTRAS], double fs,
              int32_t w[DSP_C_IMAGE])
{
    double gl, gr, bass, treble;
    dsp_levels(s, cfg, muted, &gl, &gr, &bass, &treble);
    int r = 0;
    r |= biquad(&w[DSP_C_BQ(0, 0)], 0, fs, cfg->bass_hz, bass);
    r |= biquad(&w[DSP_C_BQ(1, 0)], 1, fs, cfg->treble_hz, treble);
    for (int b = 2; b < DSP_N_BQ; b++)
        straight(&w[DSP_C_BQ(b, 0)]);
    w[DSP_C_KT(0, 0)] = q28(K_GLIDE * gl);
    w[DSP_C_KT(0, 1)] = q28(K_GLIDE * gr);
    for (int st = 1; st < DSP_N_STREAMS; st++) {
        dsp_extra_levels(s, cfg, ex ? &ex[st - 1] : NULL, &gl, &gr);
        w[DSP_C_KT(st, 0)] = q28(K_GLIDE * gl);
        w[DSP_C_KT(st, 1)] = q28(K_GLIDE * gr);
    }
    w[DSP_C_1MK] = q28(1.0 - K_GLIDE);
    return r;
}
