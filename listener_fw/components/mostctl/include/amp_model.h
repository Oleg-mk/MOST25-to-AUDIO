// amp_model.h - what the factory amplifier is told, and where the AUX source is.
//
// Built only from telegrams on the bus (docs/host_control_formats.md,
// sections 4 and 6; MOST25 GeneralFBlock 2.5.1):
//   AuxIn 0x24:           0x101 Allocate.Result [SourceNr, SrcDelay, ChannelList]
//                         0x100 SourceInfo.Status [SourceNr, DataType, (PCM:)
//                               Resolution, AudioChannels, SrcDelay, ChannelList]
//                         0x102 DeAllocate [SourceNr]
//   AudioAmplifier 0x22:  0x111 Connect.StartResult [SinkNr, SrcDelay, ChannelList],
//                               confirmed by Connect.Result [SinkNr]
//                         0x110 SinkInfo.Status [SinkNr, DataType, (PCM:)
//                               Resolution, AudioChannels, SinkDelay, ChannelList]
//                         0x112 DisConnect [SinkNr]
//                         0x113 Mute [SinkNr, Status]  (SinkNr 0 = all sinks)
// The *Ack forms carry a 2-byte SenderHandle first. A channel list is in
// ascending order, channel N is frame byte N+1, 0xFF means "not allocated";
// stereo is 4 channels (16 bit: L-Hi, L-Lo, R-Hi, R-Lo) or 6 (24 bit).
//
// Everything is idempotent: a NAKed telegram shows up to 6 times on the wire.
#pragma once

#include <stdint.h>

#include "most_msg.h"

#define AM_FB_AMP     0x22
#define AM_FB_AUXIN   0x24
#define AM_SOURCES    4
#define AM_SINKS      8
#define AM_MAX_CH     8

typedef struct {
    uint8_t n;                  // 0: none known
    uint8_t ch[AM_MAX_CH];
} am_list_t;

typedef struct {
    struct { uint8_t used, inst, nr; am_list_t ch; } src[AM_SOURCES];       // AuxIn
    struct { uint8_t used, inst, nr, connected, muted; am_list_t ch, pend; } sink[AM_SINKS];  // amp
} am_t;

// Where a stereo stream sits in the frame: frame byte indices, MSB first.
typedef struct {
    int bits;                   // 16 or 24; 0 = none
    uint8_t l[3], r[3];
} am_pos_t;

void am_init(am_t *a);

// Feed a telegram. Returns 1 if the model changed.
int am_tel(am_t *a, const mm_tel_t *t);

// The AUX source's frame bytes, if an amplifier sink is connected to them.
am_pos_t am_aux_playing(const am_t *a);

// What the amplifier's sink 1 plays (the main zone), for the stereo output.
am_pos_t am_main(const am_t *a);

// That sink is muted (Mute 0x113 to it, or to all sinks).
int am_main_muted(const am_t *a);
