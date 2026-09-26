// test_rate_match.c - host tests for components/ratematch.
//
// 1. The interpolator alone: a sine in the buffer, read at random fractional
//    positions, compared with the exact sine there. Passband SNR, and the
//    stopband of the 48 -> 44.1 kHz filter (a 23 kHz tone must not fold in).
// 2. The whole path in simulated ring time: a phone whose clock is off by
//    delta sends 1024-frame packets with random delays and periodic 70 ms
//    holds; the I2S side pulls 240-frame blocks. Checked: no underflow, no
//    jump, no drop; the loop settles at delta; the pitch stays still; over
//    the last 100 s the output tone is the phone's tone at the phone's speed
//    (nothing lost or repeated); no clicks.
// 3. Events: the phone pauses (fade out, silence, fade in), and the I2S
//    clocks stop while the phone keeps sending (drop, then one jump back).
#include "rate_match.h"

#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define CAP     16384
#define BLOCK   240
#define PKT     1024
#define TARGET  200.0            // ms, as in the firmware
#define TWO_PI  6.28318530717958647692

static int fails;
#define CHECK(cond, ...) do { if (!(cond)) { fails++; printf("    FAIL: "); \
    printf(__VA_ARGS__); printf("\n"); } } while (0)

static int16_t ring[2 * CAP];
static rm_t rm;

static uint64_t rng = 0x9E3779B97F4A7C15ull;
static double rnd(void)                     // uniform [0, 1)
{
    rng ^= rng << 13; rng ^= rng >> 7; rng ^= rng << 17;
    return (double)(rng >> 11) / 9007199254740992.0;
}

// ---------------------------------------------------------------- 1. filter
static double interp_snr(uint32_t fs_in, uint32_t fs_out, double f0)
{
    static int16_t tmp[2 * 8192];
    const double amp = 0.5 * 32767.0;
    rm_init(&rm, ring, CAP, fs_in, fs_out, TARGET);
    for (int n = 0; n < 8192; n++) {
        tmp[2 * n] = (int16_t)lrint(amp * sin(TWO_PI * f0 * n / fs_in));
        tmp[2 * n + 1] = (int16_t)lrint(amp * cos(TWO_PI * f0 * n / fs_in));
    }
    rm_push(&rm, tmp, 8192);
    double err = 0.0, sig = 0.0;
    for (int i = 0; i < 20000; i++) {
        const double p = 100.0 + (8192.0 - 200.0) * rnd();
        const uint64_t q = (uint64_t)(p * 4294967296.0);
        const double pe = (double)q / 4294967296.0;
        float l, r;
        rm_interp_at(&rm, q, &l, &r);
        const double il = amp / 32768.0 * sin(TWO_PI * f0 * pe / fs_in);
        const double ir = amp / 32768.0 * cos(TWO_PI * f0 * pe / fs_in);
        err += (l - il) * (l - il) + (r - ir) * (r - ir);
        sig += il * il + ir * ir;
    }
    return 10.0 * log10(sig / err);
}

// output level of a tone relative to its input level, dB
static double interp_gain_db(uint32_t fs_in, uint32_t fs_out, double f0)
{
    static int16_t tmp[2 * 8192];
    const double amp = 0.5 * 32767.0;
    rm_init(&rm, ring, CAP, fs_in, fs_out, TARGET);
    for (int n = 0; n < 8192; n++)
        tmp[2 * n] = tmp[2 * n + 1] = (int16_t)lrint(amp * sin(TWO_PI * f0 * n / fs_in));
    rm_push(&rm, tmp, 8192);
    double sum = 0.0;
    for (int i = 0; i < 20000; i++) {
        const double p = 100.0 + (8192.0 - 200.0) * rnd();
        float l, r;
        rm_interp_at(&rm, (uint64_t)(p * 4294967296.0), &l, &r);
        sum += (double)l * l;
    }
    const double rms = sqrt(sum / 20000.0), in = amp / 32768.0 / sqrt(2.0);
    return 20.0 * log10(rms / in + 1e-30);
}

static void test_filter(void)
{
    static const uint32_t rates[][2] = {{44100, 44100}, {48000, 48000}, {48000, 44100}, {44100, 48000}};
    printf("filter: SNR against the exact sine, amplitude -6 dBFS\n");
    for (int i = 0; i < 4; i++) {
        const double tones[] = {1000.0, 10000.0, 15000.0};
        printf("  %5u -> %5u:", rates[i][0], rates[i][1]);
        for (int t = 0; t < 3; t++) {
            const double snr = interp_snr(rates[i][0], rates[i][1], tones[t]);
            printf("  %5.0f Hz %5.1f dB", tones[t], snr);
            CHECK(snr >= (tones[t] < 12000.0 ? 85.0 : 75.0), "SNR %.1f dB at %.0f Hz", snr, tones[t]);
        }
        printf("\n");
    }
    const double stop = interp_gain_db(48000, 44100, 23000.0);
    printf("  48000 -> 44100: a 23 kHz tone comes out at %.1f dB (would fold to 21.1 kHz)\n", stop);
    CHECK(stop <= -80.0, "23 kHz leaks at %.1f dB", stop);
}

// ------------------------------------------------------------ 2, 3. the path
typedef struct {
    const char *name;
    uint32_t fs_in, fs_out;
    double delta;                    // phone clock vs ring clock
    double seconds;
    double pause_at, pause_len;      // phone sends nothing
    double stall_at, stall_len;      // I2S does not pull
} scen_t;

typedef struct {
    rm_status_t st;
    double fill_min, fill_max;       // ms, while running, outside events
    double ppm_mean, ppm_std;        // over the last 200 s
    double max_step;                 // largest sample-to-sample change, L
    double freq;                     // L tone over the last 100 s, Hz
} res_t;

static void run(const scen_t *s, res_t *o)
{
    static int16_t pkt[2 * PKT];
    static int32_t out[2 * BLOCK];
    const double f_l = 1000.0, f_r = 1500.0, amp = 0.5 * 32767.0;
    const double t_pkt = PKT / (s->fs_in * (1.0 + s->delta));   // phone packet period, ring seconds
    const double t_blk = (double)BLOCK / s->fs_out;
    const double hold = 0.070, hold_every = 10.0, jitter = 0.040;
    rm_init(&rm, ring, CAP, s->fs_in, s->fs_out, TARGET);
    memset(o, 0, sizeof *o);
    o->fill_min = 1e9;
    uint64_t n_ph = 0;               // phone sample index
    long k = 0;                      // next packet
    double next_arrival = 0.0, prev_arrival = 0.0;
    int have = 0;
    double ppm_sum = 0.0, ppm_sq = 0.0; long ppm_n = 0;
    double prev_y = 0.0, last_y = 0.0, t_last_cross = -1.0, t_first_cross = -1.0; long crossings = 0;
    const long blocks = (long)(s->seconds / t_blk);
    for (long j = 0; j < blocks; j++) {
        const double t = j * t_blk;
        // phone side: every packet that has arrived by now
        for (;;) {
            if (!have) {
                const double due = (k + 1) * t_pkt;
                double a = due + jitter * rnd();
                const double in_cycle = fmod(due, hold_every);
                if (in_cycle > 5.0 && in_cycle < 5.0 + hold)       // a 70 ms hold, every 10 s
                    a = due - in_cycle + 5.0 + hold + jitter * rnd();
                if (a < prev_arrival)
                    a = prev_arrival;
                next_arrival = a;
                have = 1;
            }
            if (next_arrival > t)
                break;
            const int paused = s->pause_len > 0 && next_arrival >= s->pause_at &&
                               next_arrival < s->pause_at + s->pause_len;
            if (!paused) {
                for (int i = 0; i < PKT; i++, n_ph++) {
                    pkt[2 * i] = (int16_t)lrint(amp * sin(TWO_PI * f_l * (double)n_ph / s->fs_in));
                    pkt[2 * i + 1] = (int16_t)lrint(amp * sin(TWO_PI * f_r * (double)n_ph / s->fs_in));
                }
                rm_push(&rm, pkt, PKT);
            }
            prev_arrival = next_arrival;
            have = 0;
            k++;
        }
        // ring side
        const int stalled = s->stall_len > 0 && t >= s->stall_at && t < s->stall_at + s->stall_len;
        if (stalled)
            continue;
        rm_pull(&rm, out, BLOCK);
        rm_status(&rm, &o->st);
        const int quiet = (s->pause_len > 0 && t > s->pause_at - 1.0 && t < s->pause_at + s->pause_len + 3.0) ||
                          (s->stall_len > 0 && t > s->stall_at - 1.0 && t < s->stall_at + s->stall_len + 3.0);
        if (o->st.state == RM_RUN && t > 2.0 && !quiet) {
            if (o->st.fill_ms < o->fill_min) o->fill_min = o->st.fill_ms;
            if (o->st.fill_ms > o->fill_max) o->fill_max = o->st.fill_ms;
        }
        if (t > s->seconds - 200.0) {
            ppm_sum += o->st.ppm; ppm_sq += o->st.ppm * o->st.ppm; ppm_n++;
        }
        for (int i = 0; i < BLOCK; i++) {
            const double y = out[2 * i] / 2147483648.0;
            if (j > 0 || i > 0) {
                const double d = fabs(y - prev_y);
                if (d > o->max_step) o->max_step = d;
            }
            const double ti = t + (double)i / s->fs_out;
            if (ti > s->seconds - 100.0 && prev_y < 0.0 && y >= 0.0) {
                const double tc = ti - (y / (y - prev_y)) / s->fs_out;
                if (t_first_cross < 0.0) t_first_cross = tc;
                t_last_cross = tc;
                crossings++;
            }
            prev_y = y;
        }
        last_y = prev_y;
    }
    (void)last_y;
    o->ppm_mean = ppm_n ? ppm_sum / ppm_n : 0.0;
    o->ppm_std = ppm_n ? sqrt(fmax(0.0, ppm_sq / ppm_n - o->ppm_mean * o->ppm_mean)) : 0.0;
    o->freq = crossings > 1 ? (crossings - 1) / (t_last_cross - t_first_cross) : 0.0;
}

static void test_steady(void)
{
    static const uint32_t rates[][2] = {{44100, 44100}, {48000, 44100}, {44100, 48000}};
    static const double deltas[] = {-200e-6, 0.0, 200e-6};
    printf("path: 1024-frame packets, 0..40 ms late, a 70 ms hold every 10 s; 600 s\n");
    for (int i = 0; i < 3; i++)
        for (int d = 0; d < 3; d++) {
            const scen_t s = {"steady", rates[i][0], rates[i][1], deltas[d], 600.0, 0, 0, 0, 0};
            res_t o;
            run(&s, &o);
            const double want = 1000.0 * (1.0 + deltas[d]);
            printf("  %5u -> %5u, phone %+4.0f ppm: loop %+7.2f ppm (sd %.2f), fill %5.1f..%5.1f ms,"
                   " tone %+5.1f ppm, max step %.4f, under %u jump %u drop %u\n",
                   s.fs_in, s.fs_out, deltas[d] * 1e6, o.ppm_mean, o.ppm_std, o.fill_min, o.fill_max,
                   (o.freq / want - 1.0) * 1e6, o.max_step, o.st.underflows, o.st.jumps, o.st.dropped);
            CHECK(o.st.underflows == 0 && o.st.jumps == 0 && o.st.dropped == 0, "under/jump/drop");
            // the ear notices about 0.1 % (1000 ppm) of wow at best; these bounds
            // are far inside that and are here to catch a loop that misbehaves
            CHECK(fabs(o.ppm_mean - deltas[d] * 1e6) < 10.0, "loop %.2f ppm, phone %.0f", o.ppm_mean, deltas[d] * 1e6);
            CHECK(o.ppm_std < 20.0, "pitch wobble %.2f ppm", o.ppm_std);
            // the fill wanders by a few ms, so over 100 s the tone may be a few
            // ppm off; a wrong step or a leaking buffer would be far more
            CHECK(fabs(o.freq / want - 1.0) < 20e-6, "tone off by %.1f ppm", (o.freq / want - 1.0) * 1e6);
            CHECK(o.fill_min > 30.0 && o.fill_max < 300.0, "fill %.1f..%.1f ms", o.fill_min, o.fill_max);
            CHECK(o.max_step < 0.08, "click: step %.4f", o.max_step);
        }
}

static void test_events(void)
{
    printf("events, 44100 -> 48000, phone +150 ppm:\n");
    {
        const scen_t s = {"pause", 44100, 48000, 150e-6, 160.0, 100.0, 1.0, 0, 0};
        res_t o;
        run(&s, &o);
        printf("  phone pauses 1 s:         under %u jump %u drop %u, state %d, max step %.4f\n",
               o.st.underflows, o.st.jumps, o.st.dropped, o.st.state, o.max_step);
        CHECK(o.st.underflows == 1 && o.st.jumps == 0 && o.st.dropped == 0, "pause: under %u jump %u",
              o.st.underflows, o.st.jumps);
        CHECK(o.st.state == RM_RUN, "pause: not running again");
        CHECK(o.max_step < 0.08, "pause: click %.4f", o.max_step);
    }
    {
        const scen_t s = {"stall", 44100, 48000, 150e-6, 160.0, 0, 0, 100.0, 3.0};
        res_t o;
        run(&s, &o);
        printf("  I2S clocks stop for 3 s:  under %u jump %u drop %u, state %d, fill %.1f ms at the end, max step %.4f\n",
               o.st.underflows, o.st.jumps, o.st.dropped, o.st.state, o.st.fill_ms, o.max_step);
        CHECK(o.st.jumps == 1 && o.st.underflows == 0 && o.st.dropped > 0, "stall: under %u jump %u drop %u",
              o.st.underflows, o.st.jumps, o.st.dropped);
        CHECK(o.st.state == RM_RUN && fabs(o.st.fill_ms - TARGET) < 60.0, "stall: fill %.1f", o.st.fill_ms);
        CHECK(o.max_step < 0.08, "stall: click %.4f", o.max_step);
    }
}

int main(void)
{
    test_filter();
    test_steady();
    test_events();
    printf(fails ? "\n%d FAILED\n" : "\nall passed\n", fails);
    return fails != 0;
}
