// sound.c - see sound.h.
#include "sound.h"

#include <math.h>
#include <string.h>

// Placeholders until a car is recorded: BMW's 0..63 is from its diagnostic
// data (docs/control_commands.md); the other maxima, the steps and the loudness curve are
// guesses of the usual kind (+-10 steps of tone, balance silent at the end).
const snd_cfg_t snd_cfg_default = {
    .vol_max = {[SND_VOL_46D] = 0, [SND_VOL_BMW] = 63, [SND_VOL_F0] = 40, [SND_VOL_STD] = 40},
    .tone_db_step = 1.0f,
    .tone_db_max = 12.0f,
    .bal_db_step = 2.0f,
    .bal_mute_steps = 10,
    .bass_hz = 100.0f,
    .treble_hz = 10000.0f,
    .loud_db_max = 8.0f,
    .loud_db_at = -40.0f,
};

void snd_init(snd_t *s)
{
    memset(s, 0, sizeof *s);
    for (int i = 0; i < SND_VOL_N; i++)
        s->vol_db[i] = SND_SILENT;
    s->loudness = 1;                // a factory amplifier runs with it on
}

float snd_curve_db(int raw, int max)
{
    if (raw <= 0 || max <= 0)
        return SND_SILENT;
    if (raw >= max)
        return 0.0f;
    return 40.0f * log10f((float)raw / (float)max);
}

static int set_vol(snd_t *s, int src, float db)
{
    const uint8_t bit = (uint8_t)(1u << src);
    if ((s->vol_have & bit) && s->vol_db[src] == db)
        return 0;
    s->vol_have |= bit;
    s->vol_db[src] = db;
    return 1;
}

static int set_s8(snd_t *s, uint8_t have, int8_t *dst, uint8_t v)
{
    if ((s->have & have) && *dst == (int8_t)v)
        return 0;
    s->have |= have;
    *dst = (int8_t)v;
    return 1;
}

int snd_tel(snd_t *s, const snd_cfg_t *cfg, const mm_tel_t *t)
{
    if (!(t->op == MM_OP_SET || t->op == MM_OP_SETGET || t->op == MM_OP_STATUS) || t->len < 1)
        return 0;
    const uint8_t *d = t->data;
    if (t->fblock == 0x22) {
        switch (t->fkt) {
        case 0x400:
            return set_vol(s, SND_VOL_STD, snd_curve_db(d[0], cfg->vol_max[SND_VOL_STD]));
        case 0x46D: {                   // param, sink, then dB per speaker; the main zone only
            if (t->len < 3 || d[1] != 1)
                return 0;
            int m = -128;
            for (int i = 2; i < t->len; i++)
                if ((int8_t)d[i] > m)
                    m = (int8_t)d[i];
            return set_vol(s, SND_VOL_46D, m <= -120 ? SND_SILENT : (float)m);
        }
        case 0x200:
            return set_s8(s, SND_H_BAL, &s->balance, d[0]);
        case 0x202:
            return set_s8(s, SND_H_BASS, &s->bass, d[0]);
        case 0x203:
            return set_s8(s, SND_H_TREBLE, &s->treble, d[0]);
        case 0x201: {
            const uint8_t on = d[0] != 0;
            if ((s->have & SND_H_LOUD) && s->loudness == on)
                return 0;
            s->have |= SND_H_LOUD;
            s->loudness = on;
            return 1;
        }
        default:
            return 0;
        }
    }
    if (t->fblock == 0x20) {            // BMW AudioMaster
        switch (t->fkt) {
        case 0x200:
            return set_vol(s, SND_VOL_BMW, snd_curve_db(d[0], cfg->vol_max[SND_VOL_BMW]));
        case 0x220:
            return set_s8(s, SND_H_BAL, &s->balance, d[0]);
        case 0x222:
            return set_s8(s, SND_H_BASS, &s->bass, d[0]);
        case 0x223:
            return set_s8(s, SND_H_TREBLE, &s->treble, d[0]);
        default:
            return 0;
        }
    }
    if (t->fblock == 0xF0 && t->fkt == 0x409 && t->len >= 3)       // Jaguar XF: byte 2 = entertainment
        return set_vol(s, SND_VOL_F0, snd_curve_db(d[2], cfg->vol_max[SND_VOL_F0]));
    return 0;
}

float snd_volume_db(const snd_t *s)
{
    for (int i = 0; i < SND_VOL_N; i++)
        if (s->vol_have & (1u << i))
            return s->vol_db[i];
    return SND_SILENT;
}
