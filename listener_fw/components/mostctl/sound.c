// sound.c - see sound.h.
#include "sound.h"

#include <math.h>
#include <string.h>

// Placeholders until a car is recorded: BMW's 0..63 is from its diagnostic
// data (docs/control_commands.md), Jaguar XF's 0..35 (the volume) and 0..25 (the
// 0x409 levels) are the scales JLR-HU's screen shows; the other maxima, the steps
// and the loudness curve are guesses of the usual kind (+-10 steps of tone, balance
// silent at the end).
const snd_cfg_t snd_cfg_default = {
    .vol_max = {[SND_VOL_46D] = 0, [SND_VOL_BMW] = 63, [SND_VOL_F0] = 35, [SND_VOL_STD] = 40},
    .lvl_max = 25,
    .tone_db_step = 1.0f,
    .tone_db_max = 12.0f,
    .bal_db_step = 2.0f,
    .bal_mute_steps = 10,
    .bass_hz = 100.0f,
    .treble_hz = 10000.0f,
    .loud_db_max = 8.0f,
    .loud_db_at = -40.0f,
    .chime_db = -6.0f,              // the chimes, as JLR-MOST-Reader plays them (DEFAULT_S3_DB)
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

static int set_spk(snd_t *s, int sink, float db)
{
    const uint8_t bit = (uint8_t)(1u << (sink - 1));
    if ((s->spk_have & bit) && s->spk_db[sink - 1] == db)
        return 0;
    s->spk_have |= bit;
    s->spk_db[sink - 1] = db;
    return 1;
}

static int set_annc(snd_t *s, float db)
{
    if (s->annc_have && s->annc_db == db)
        return 0;
    s->annc_have = 1;
    s->annc_db = db;
    return 1;
}

static int set_park(snd_t *s, float db)
{
    if (s->park_have && s->park_db == db)
        return 0;
    s->park_have = 1;
    s->park_db = db;
    return 1;
}

// a 0x409 level: sent as the level + 5, the level 0..25
static float f0_level_db(const snd_cfg_t *cfg, uint8_t raw)
{
    return snd_curve_db(raw > 5 ? raw - 5 : 0, cfg->lvl_max);
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
        case 0x46D: {                   // param, sink, then dB per speaker: the loudest counts
            if (t->len < 3 || d[1] < 1 || d[1] > SND_SINKS)
                return 0;
            int m = -128;
            for (int i = 2; i < t->len; i++)
                if ((int8_t)d[i] > m)
                    m = (int8_t)d[i];
            const float db = m <= -120 ? SND_SILENT : (float)m;
            return d[1] == 1 ? set_vol(s, SND_VOL_46D, db) : set_spk(s, d[1], db);
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
    // Jaguar XF: the gateway's Status, its whole record (byte 0 = 0) alone; a byte counts where
    // the length covers it
    if (t->fblock == 0xF0 && t->fkt == 0x409) {
        if (t->op != MM_OP_STATUS || d[0] != 0)
            return 0;
        int ch = 0;
        if (t->len > 2)                                             // byte 2 the volume
            ch |= set_vol(s, SND_VOL_F0, snd_curve_db(d[2], cfg->vol_max[SND_VOL_F0]));
        if (t->len > 9)                                             // byte 9 the navigation
            ch |= set_annc(s, f0_level_db(cfg, d[9]));
        if (t->len > 11)                                            // byte 11 the parking sensors
            ch |= set_park(s, f0_level_db(cfg, d[11]));
        return ch;
    }
    return 0;
}

float snd_volume_db(const snd_t *s)
{
    for (int i = 0; i < SND_VOL_N; i++)
        if (s->vol_have & (1u << i))
            return s->vol_db[i];
    return SND_SILENT;
}

float snd_sink_db(const snd_t *s, const snd_cfg_t *cfg, int sink)
{
    if (sink < 1 || sink > SND_SINKS)
        return SND_SILENT;
    const uint8_t bit = (uint8_t)(1u << (sink - 1));
    // the chimes keep their own level whatever the volume does, in every car
    const float db = sink >= 2 && (s->spk_have & bit)       ? s->spk_db[sink - 1]
                   : sink == SND_JLR_CHIMES                 ? cfg->chime_db
                   : sink == SND_JLR_PDC && s->park_have    ? s->park_db
                   : sink == SND_JLR_NAV && s->annc_have    ? s->annc_db
                                                            : snd_volume_db(s);
    return db <= SND_SILENT ? SND_SILENT : db;
}

int snd_balance(const snd_t *s)
{
    return (s->have & SND_H_BAL) ? s->balance : 0;
}
