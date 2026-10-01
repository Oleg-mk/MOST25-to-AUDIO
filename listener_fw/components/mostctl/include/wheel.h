// wheel.h - the steering wheel's track keys, as the ring carries them.
//
// Jaguar XF X250: the gateway (0x161) sends the keys to the touchscreen
// (0x16E), which tells whatever source plays; with the factory screen in the
// car they are on the ring. FktID 0xCA1 - the one node known to act on them
// (SocketMost, branch usb, src/modules/JlrAudioControl.ts, standing in for
// the screen) checks nothing else, neither FBlock nor instance nor OPType:
//   next track      Data0 = 0x03 and Data1 = 0x01
//   previous track  Data0 = 0x04 and Data2 = 0x01
// Taken here exactly so; anything else with FktID 0xCA1 (a release, a
// layout another car uses) is no key.
//
// A NAKed telegram comes up to 6 times, and one press must not skip six
// tracks: the same 0xCA1 telegram again within 200 ms of the last one counts
// once. A different one in between (a release) ends that, so a new press
// counts at once.
#pragma once

#include <stdint.h>

#include "most_msg.h"

#define WHEEL_FKT          0xCA1
#define WHEEL_SAME_FRAMES  9600u        // 200 ms at 48 kHz (218 ms at 44.1 kHz)

enum { WHEEL_NONE = 0, WHEEL_NEXT = 1, WHEEL_PREV = 2 };

typedef struct {
    uint8_t have;
    uint32_t frame;                     // when the last 0xCA1 telegram came
    mm_tel_t last;                      // ...and what it was
} wheel_t;

void wheel_init(wheel_t *w);

// Feed a telegram. Returns WHEEL_NEXT or WHEEL_PREV for a key press, else WHEEL_NONE.
int wheel_tel(wheel_t *w, const mm_tel_t *t);
