// sound.h - what the head unit tells the amplifier about the sound.
//
// Built only from telegrams on the bus. The MOST catalogue fixes the types
// (FBlock AudioAmplifier 2V4-3): Volume 0x400 TUByte (0 = mute, higher =
// louder), Balance 0x200, Bass 0x202, Treble 0x203 TSByte (balance: positive
// = to the left), Loudness 0x201 a switch; it leaves every range and every
// dB value to the application. Cars differ in where the volume is sent at
// all (docs/vehicle_survey.md, docs/control_commands.md):
//
//   source          telegram                          value
//   SND_VOL_46D     0x22.0x46D SpeakerLevel Set       byte 0 param, byte 1 sink, then
//                                                     signed dB per speaker (JLR AUD3,
//                                                     Freelander 2): the loudest is the volume
//   SND_VOL_BMW     0x20.0x200 VolumeActual           0..63 (BMW AudioMaster)
//   SND_VOL_F0      0xF0.0x409 byte 2                 raw, entertainment (Jaguar XF X250)
//   SND_VOL_STD     0x22.0x400 Volume                 raw (the catalogue; Mercedes per the
//                                                     Dension firmware)
//
// If a car sends more than one, the first in this list wins. Tone: 0x22
// 0x200/0x202/0x203/0x201, or BMW's AudioMaster 0x20 0x220/0x222/0x223.
// Fader (0x204, 0x221) is not used: J3 is stereo, front and rear are for
// whatever follows it.
//
// The scales (raw volume -> dB, dB per tone and balance step) are not known
// for any car but JLR AUD3 (dB on the wire); snd_cfg_t holds them, and the
// defaults are placeholders until a car is recorded. Values are taken from
// Set, SetGet and Status alike (the amplifier answers a Set with Status);
// Increment / Decrement carry a step count, not a value, and are left to that
// Status.
#pragma once

#include <stdint.h>

#include "most_msg.h"

enum { SND_VOL_46D, SND_VOL_BMW, SND_VOL_F0, SND_VOL_STD, SND_VOL_N };

typedef struct {
    uint8_t vol_max[SND_VOL_N];     // raw value at 0 dB, per source (46D: unused)
    float   tone_db_step;           // bass and treble, dB per step
    float   tone_db_max;            // clamp, either way
    float   bal_db_step;            // the other side, dB per balance step
    int8_t  bal_mute_steps;         // from here on the other side is silent
    float   bass_hz, treble_hz;     // shelf corners
    float   loud_db_max;            // loudness: bass boost at the quietest
    float   loud_db_at;             // ...reached at this volume (dB), 0 at 0 dB
} snd_cfg_t;

extern const snd_cfg_t snd_cfg_default;

// What has been heard. `have` bits say what has been heard at all.
typedef struct {
    uint8_t have;                   // SND_H_* bits
    uint8_t vol_have;               // bit per source
    float   vol_db[SND_VOL_N];      // per source; -inf / below -120 = silent
    int8_t  balance, bass, treble;  // steps, as sent
    uint8_t loudness;
} snd_t;

#define SND_H_BAL    0x01
#define SND_H_BASS   0x02
#define SND_H_TREBLE 0x04
#define SND_H_LOUD   0x08

#define SND_SILENT   (-200.0f)

void snd_init(snd_t *s);

// Feed a telegram. Returns 1 if anything changed.
int snd_tel(snd_t *s, const snd_cfg_t *cfg, const mm_tel_t *t);

// The volume in dB from the best source heard; SND_SILENT if none, or if
// the best one says silence.
float snd_volume_db(const snd_t *s);

// raw -> dB on the default curve: 0 = silence, else 40 log10(raw / max),
// i.e. amplitude as the square of the knob (half way is -12 dB)
float snd_curve_db(int raw, int max);
