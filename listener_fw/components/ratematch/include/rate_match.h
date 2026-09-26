// rate_match.h - the phone's audio onto the ring's clock.
//
// A Bluetooth sink gets its samples at the phone's pace (the phone's crystal),
// in packets that arrive tens of milliseconds apart and not evenly. The I2S
// port takes them at the ring's pace: it is a slave on the listener's BCLK and
// LRCK, which are locked to the MOST ring. The two paces differ by up to a few
// hundred ppm, and the nominal rates may differ too (a 44.1 kHz phone stream
// into a 48 kHz ring, or back).
//
// This module sits between the two. The Bluetooth side pushes 16-bit stereo
// frames into a ring buffer; the I2S side pulls frames out through a
// polyphase FIR resampler whose step is the nominal rate ratio corrected by a
// slow PI loop on the buffer's fill level. The loop only has to follow two
// crystals, so it is made very slow (about a minute), and it looks at the fill's
// upper envelope - right after the least late packet - so late packets do
// not reach the pitch.
//
// One producer and one consumer, each in its own task or core; no locks.
// Everything the consumer needs is on its side, the producer only moves the
// write counter. Portable C11: the same file builds for the ESP32 and for the
// host-side tests in ../../test.
#pragma once

#include <stdatomic.h>
#include <stdint.h>

#define RM_TAPS    64    // FIR taps per output sample
#define RM_PHASES  128   // phases in the coefficient table (linear in between)

typedef enum {
    RM_PRIME,            // waiting until the buffer holds the target; output 0
    RM_FADE_IN,          // gain 0 -> 1
    RM_RUN,
    RM_FADE_OUT,         // gain 1 -> 0, then RM_PRIME (ran dry, or a stale backlog
                         // dropped) or a skip ahead to the target (too full)
} rm_state_t;

typedef struct {
    rm_state_t state;
    double fill_ms;          // last measured fill, ms of input audio
    double ppm;              // loop correction of the step, ppm
    uint32_t underflows;     // times the buffer ran dry and the output faded out
    uint32_t jumps;          // times a backlog was skipped (too full) or dropped (stale)
    uint32_t dropped;        // input frames refused because the buffer was full
} rm_status_t;

typedef struct {
    // ---------------------------------------------------------------- shared
    int16_t *buf;                  // cap frames of interleaved L/R
    uint32_t cap;                  // power of two
    _Atomic uint32_t wr;           // frames written, ever (wraps)
    _Atomic uint32_t rd_floor;     // oldest frame the consumer may still read
    _Atomic uint32_t dropped;
    // -------------------------------------------------------- consumer only
    uint32_t fs_in, fs_out;
    float coef[RM_PHASES + 1][RM_TAPS];
    uint64_t pos;                  // read position, 32.32 fixed point, input frames
    double step_nom;               // fs_in / fs_out
    uint64_t step;                 // current step, 32.32
    rm_state_t state;
    float gain, dgain;             // output gain and its change per frame
    int fade_jump;                 // the fade out ends in a jump, not in RM_PRIME
    uint32_t fade_frames;
    uint32_t target;               // wanted fill, input frames
    uint32_t low, high;            // fade out below low; jump back to target above high
    uint32_t seen_dropped;         // producer drops already handled
    // loop (runs every upd_frames output frames)
    uint32_t upd_frames, upd_count;
    double fill_peak, fill_f, integ, u;
    int loop_primed;
    uint32_t underflows, jumps;
    double last_fill;
} rm_t;

// buf holds cap stereo frames (cap a power of two, at least 4096). The ring
// buffer lives wherever the caller puts it (PSRAM on the ESP32).
// target_ms: fill the loop holds; 120 ms covers A2DP packet jitter.
// Returns 0, or -1 for bad arguments.
int rm_init(rm_t *r, int16_t *buf, uint32_t cap, uint32_t fs_in, uint32_t fs_out,
            double target_ms);

// Producer (Bluetooth task). Returns the frames accepted; the rest are
// dropped (and counted) when the consumer has stopped pulling.
uint32_t rm_push(rm_t *r, const int16_t *lr, uint32_t frames);

// Consumer (I2S task): frames of interleaved L/R, 24-bit samples in the top
// of 32-bit words - I2S with 32-bit slots, as the listener's DIN expects.
void rm_pull(rm_t *r, int32_t *lr, uint32_t frames);

void rm_status(const rm_t *r, rm_status_t *s);

// Test access: one frame read at a 32.32 input position, floats in [-1, 1).
void rm_interp_at(const rm_t *r, uint64_t pos, float *l, float *rt);
