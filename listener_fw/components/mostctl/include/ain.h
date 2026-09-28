// ain.h - which of our sources goes into the AUX source's frame bytes.
//
// The phone while it streams (A2DP started); otherwise the board's TOSLINK
// input, once its S/PDIF receiver has held lock on PCM for AIN_SETTLE_US;
// otherwise none, and the car's own AUX passes.
//
// The lock is read off the DIR9001's ERROR pin (SLES198A 8.3.9, Table 10):
// high while its PLL is unlocked, and at a detected parity error - whose
// sample the receiver replaces by the one before, so a blip is no reason to
// let go. The input is lost only once ERROR has read high for AIN_LOST_US
// with no low reading between; the receiver's DOUT is muted while unlocked,
// so that tail plays silence. It counts again after AIN_SETTLE_US of lock:
// the DIR9001 locks within 100 ms (SLES198A 7.7), and the SRC4192 mutes
// itself until its rate estimator has settled (RDY -> MUTE, board v1.3).
//
// PCM is read off the DIR9001's AUDIO pin, channel-status bit 1 (Table 8):
// high = not linear PCM (AC-3, DTS: IEC 61937), which the receiver passes to
// DOUT untouched (8.3.9.2) and would be full-scale noise in the car. High
// drops the input at once, and PCM again waits AIN_SETTLE_US.
//
// The lock time runs while the phone plays, so when the phone stops the
// TOSLINK input takes over at once.
#pragma once

#include <stdint.h>

#define AIN_SETTLE_US 1000000
#define AIN_LOST_US   100000

enum { AIN_NONE, AIN_PHONE, AIN_TOSLINK };

typedef struct {
    int run;                    // locked on PCM since `since` (ERROR highs shorter than AIN_LOST_US included)
    int locked;                 // the last answer: the input holds lock on PCM and has settled
    int npcm;                   // the last reading of AUDIO: 1 = not PCM
    int64_t since, low_at;      // us
} ain_t;

void ain_init(ain_t *a);

// One reading: the phone streams or not, ERROR's and AUDIO's levels (1 =
// high), the time in us. Returns AIN_PHONE, AIN_TOSLINK or AIN_NONE.
int ain_pick(ain_t *a, int streaming, int err, int npcm, int64_t now);
