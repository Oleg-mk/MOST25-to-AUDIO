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
//
// Instances. A request may name InstID 0 or 0xFF (any instance: the device
// picks); its answer names the real one. So requests are filed under the
// device (the target) and the instance that device has shown in its own
// telegrams; one that comes before the device has shown any waits under
// instance 0 and moves to the real instance with the first answer.
// Connect. Its Result counts only as the answer to a Connect.StartResult still
// open for that sink: DisConnect, an Error and a reset close it, so a late
// Result never brings a cancelled connection back.
// Formats. SourceInfo and SinkInfo are taken only for PCM at 16 or 24 bit
// (Resolution 2 or 3 bytes), 1 or 2 channels, with a channel list exactly
// Resolution x AudioChannels long; anything else there voids what was known.
// Mute to SinkNr 0 is kept per instance and given to sinks seen later too.
#pragma once

#include <stdint.h>

#include "most_msg.h"

#define AM_FB_AMP     0x22
#define AM_FB_AUXIN   0x24
#define AM_SOURCES    4
#define AM_SINKS      8
#define AM_MAX_CH     8
#define AM_DEVS       8

typedef struct {
    uint8_t n;                  // 0: none known
    uint8_t ch[AM_MAX_CH];
} am_list_t;

typedef struct {
    struct { uint8_t used, inst, nr; uint16_t dev; am_list_t ch; } src[AM_SOURCES];         // AuxIn
    struct { uint8_t used, inst, nr, connected, muted, pend_ok; uint16_t dev; am_list_t ch, pend; }
        sink[AM_SINKS];                                                                    // amp
    struct { uint8_t used, fb, inst; uint16_t dev; } where[AM_DEVS];    // a device's instance of an FBlock
    struct { uint8_t used, inst, muted; uint16_t dev; } mute0[AM_SINKS];  // Mute to SinkNr 0, per instance
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

// One of the amplifier's other sinks as J3 mixes it in.
typedef struct {
    am_pos_t pos;               // bits 0: none
    uint8_t mono;               // one channel (pos.l), fed to both sides
    uint8_t nr;                 // its SinkNr
    uint8_t muted;
} am_sink_t;

// Everything the amplifier plays besides sink 1 - navigation, phone, chimes,
// whichever sink numbers a car gives them: up to n connected sinks with
// SinkNr >= 2 on the main sink's instance (without a main sink, on the lowest
// instance that has one J3 can take), lowest SinkNr first. A channel list 2,
// 3, 4 or 6 long is 16/24-bit mono or stereo; other lengths are left out.
// Returns how many were found; the rest of out[] is cleared.
int am_extras(const am_t *a, am_sink_t *out, int n);
