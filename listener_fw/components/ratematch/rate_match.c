// rate_match.c - see rate_match.h.
//
// Resampler: output frame m is the input read at a fractional position p_m,
// p_{m+1} = p_m + step, through a Kaiser-windowed sinc of RM_TAPS taps. The
// sinc's cutoff is 0.43 of the lower of the two rates, so 48 -> 44.1 kHz does
// not alias. The coefficients are tabulated for RM_PHASES fractional offsets
// and interpolated linearly in between; every table row is scaled to a DC
// gain of exactly 1.
//
// Loop: every 2 s it takes the highest fill seen (frames ahead of the read
// position). Packets can only come late, never early, so the fill right after
// the least late packet is the true balance of what the phone sent against
// what the ring took; the mean would carry the packet jitter into the pitch.
// That peak is low-passed (10 s) and a PI controller sets the step to
// step_nom * (1 + u). In ring time the fill x (seconds of input) obeys
// dx/dt = delta - u, delta being how much faster the phone's clock runs than
// the ring's; so u settles at delta and the fill at the target. The peak
// still scatters by 1-2 ms (the least late of ~90 packets is a few ms late,
// plus the I2S block it lands in), so the loop is slow: wn = 2 pi * 2.5 mHz,
// zeta 0.9. A 200 ppm offset then moves the fill by about 5 ms, and the pitch
// wanders by some 10 ppm (0.001 %) - two crystals drifting with temperature
// are easily followed at that speed.
//
// Backlog: above `high` the read side fades out and moves on. If the
// producer has dropped frames meanwhile (the I2S clocks had stopped and the
// buffer filled up), what is buffered no longer joins what comes next, so it
// is all dropped and the output waits for a fresh target; otherwise the read
// side skips ahead to the target.
#include "rate_match.h"

#include <math.h>
#include <string.h>

#define RM_PHASE_BITS  7
_Static_assert((1 << RM_PHASE_BITS) == RM_PHASES, "RM_PHASES must be 2^RM_PHASE_BITS");
_Static_assert(RM_TAPS % 2 == 0, "RM_TAPS must be even");

#define RM_PI          3.14159265358979323846
#define RM_BETA        8.6      // Kaiser beta: about 86 dB stopband
#define RM_CUTOFF      0.43     // of the lower rate
#define RM_FADE_MS     5.0
#define RM_UPD_HZ      0.5      // loop updates per second
#define RM_LPF_S       10.0     // fill filter time constant
#define RM_WN          (2.0 * RM_PI * 0.0025)
#define RM_ZETA        0.9
#define RM_U_MAX       1000e-6  // the loop never corrects by more than this

static double bessel_i0(double x)
{
    double sum = 1.0, term = 1.0, q = x * x / 4.0;
    for (int k = 1; k < 64; k++) {
        term *= q / ((double)k * k);
        sum += term;
        if (term < sum * 1e-17)
            break;
    }
    return sum;
}

static void design(rm_t *r)
{
    const double fc = RM_CUTOFF * (r->fs_in < r->fs_out ? r->fs_in : r->fs_out) / r->fs_in;
    const double half = RM_TAPS / 2.0, i0b = bessel_i0(RM_BETA);
    for (int p = 0; p <= RM_PHASES; p++) {
        const double f = (double)p / RM_PHASES;
        double h[RM_TAPS], sum = 0.0;
        for (int k = 0; k < RM_TAPS; k++) {
            // distance, in input frames, from the output time to tap k's frame
            const double t = f + half - 1.0 - k;
            const double a = 2.0 * t / RM_TAPS;
            double w = 0.0;
            if (a > -1.0 && a < 1.0)
                w = bessel_i0(RM_BETA * sqrt(1.0 - a * a)) / i0b;
            else if (a == -1.0 || a == 1.0)
                w = 1.0 / i0b;
            const double x = 2.0 * fc * t;
            const double s = (x == 0.0) ? 1.0 : sin(RM_PI * x) / (RM_PI * x);
            h[k] = 2.0 * fc * s * w;
            sum += h[k];
        }
        for (int k = 0; k < RM_TAPS; k++)
            r->coef[p][k] = (float)(h[k] / sum);
    }
}

static uint64_t to_q32(double v)
{
    return (uint64_t)llround(v * 4294967296.0);
}

double rm_target_ms(uint32_t cap, uint32_t fs_in, double want_ms)
{
    // rm_init needs target + RM_TAPS below cap - RM_TAPS - 16; a quarter of cap stays above
    const uint32_t keep = 2 * RM_TAPS + 16 + cap / 4;
    const double ms = cap > keep && fs_in ? (double)(cap - keep) * 1000.0 / fs_in : 0.0;
    return ms < want_ms ? ms : want_ms;
}

int rm_init(rm_t *r, int16_t *buf, uint32_t cap, uint32_t fs_in, uint32_t fs_out,
            double target_ms)
{
    if (!r || !buf || cap < 4096 || (cap & (cap - 1)) || !fs_in || !fs_out ||
        fs_in > 2 * fs_out || fs_out > 2 * fs_in || target_ms <= 0.0)
        return -1;
    memset(r, 0, sizeof *r);
    r->buf = buf;
    r->cap = cap;
    r->fs_in = fs_in;
    r->fs_out = fs_out;
    design(r);
    r->step_nom = (double)fs_in / fs_out;
    r->step = to_q32(r->step_nom);
    // the first output is centred on frame RM_TAPS/2 - 1, so its oldest tap is frame 0
    r->pos = (uint64_t)(RM_TAPS / 2 - 1) << 32;
    atomic_store(&r->wr, 0);
    atomic_store(&r->rd_floor, 0);
    atomic_store(&r->dropped, 0);
    r->state = RM_PRIME;
    r->fade_frames = (uint32_t)(RM_FADE_MS * fs_out / 1000.0);
    r->target = (uint32_t)(target_ms * fs_in / 1000.0);
    // a fade out needs fade_frames * step input frames plus the taps ahead
    r->low = RM_TAPS / 2 + 2 + (uint32_t)(r->fade_frames * r->step_nom * 1.1) + 1;
    uint32_t high = 3 * r->target;
    if (high > cap - RM_TAPS - 16)
        high = cap - RM_TAPS - 16;
    r->high = high;
    if (r->target < r->low + RM_TAPS || r->target + RM_TAPS >= r->high)
        return -1;
    r->upd_frames = (uint32_t)(fs_out / RM_UPD_HZ);
    r->fill_peak = -1e9;
    return 0;
}

uint32_t rm_push(rm_t *r, const int16_t *lr, uint32_t frames)
{
    const uint32_t wr = atomic_load_explicit(&r->wr, memory_order_relaxed);
    const uint32_t floor = atomic_load_explicit(&r->rd_floor, memory_order_acquire);
    const uint32_t space = r->cap - (wr - floor);
    const uint32_t n = frames < space ? frames : space;
    const uint32_t at = wr & (r->cap - 1);
    const uint32_t first = (r->cap - at) < n ? (r->cap - at) : n;
    memcpy(&r->buf[2 * at], lr, (size_t)first * 2 * sizeof(int16_t));
    if (n > first)
        memcpy(&r->buf[0], &lr[2 * first], (size_t)(n - first) * 2 * sizeof(int16_t));
    atomic_store_explicit(&r->wr, wr + n, memory_order_release);
    if (n < frames)
        atomic_fetch_add_explicit(&r->dropped, frames - n, memory_order_relaxed);
    return n;
}

// one output frame at position pos, as floats in [-1, 1)
static inline void interp(const rm_t *r, uint64_t pos, float *l, float *rt)
{
    const uint32_t c = (uint32_t)(pos >> 32);
    const uint32_t fr = (uint32_t)pos;
    const uint32_t p = fr >> (32 - RM_PHASE_BITS);
    const float w = (float)((fr >> (16 - RM_PHASE_BITS)) & 0xFFFFu) * (1.0f / 65536.0f);
    const float *h0 = r->coef[p], *h1 = r->coef[p + 1];
    const uint32_t mask = r->cap - 1, base = c - (RM_TAPS / 2 - 1);
    float al = 0.0f, ar = 0.0f;
    for (int k = 0; k < RM_TAPS; k++) {
        const float h = h0[k] + w * (h1[k] - h0[k]);
        const int16_t *s = &r->buf[2 * ((base + (uint32_t)k) & mask)];
        al += h * s[0];
        ar += h * s[1];
    }
    *l = al * (1.0f / 32768.0f);
    *rt = ar * (1.0f / 32768.0f);
}

static inline int32_t to_i2s(float v)
{
    long x = lrintf(v * 8388607.0f);
    if (x > 8388607)
        x = 8388607;
    if (x < -8388608)
        x = -8388608;
    return (int32_t)x * 256;             // 24-bit sample in the top of the slot
}

static void loop_update(rm_t *r)
{
    const double peak_s = r->fill_peak / r->fs_in;
    const double T = 1.0 / RM_UPD_HZ;
    r->fill_peak = -1e9;
    r->upd_count = 0;
    if (!r->loop_primed) {
        r->fill_f = peak_s;
        r->loop_primed = 1;
    }
    r->fill_f += (peak_s - r->fill_f) * (T / RM_LPF_S);
    const double e = r->fill_f - (double)r->target / r->fs_in;
    const double kp = 2.0 * RM_ZETA * RM_WN, ki = RM_WN * RM_WN;
    double integ = r->integ + e * T;
    double u = kp * e + ki * integ;
    if (u > RM_U_MAX || u < -RM_U_MAX)
        u = u > 0 ? RM_U_MAX : -RM_U_MAX;           // and keep the old integral
    else
        r->integ = integ;
    r->u = u;
    r->step = to_q32(r->step_nom * (1.0 + u));
}

// Leave a backlog. Frames dropped by the producer since the last look mean
// the buffered audio does not run on into what arrives next: drop it all and
// wait for a fresh target (returns 1). Otherwise skip ahead to the target
// (returns 0).
static int backlog(rm_t *r, uint32_t wr)
{
    const uint32_t d = atomic_load_explicit(&r->dropped, memory_order_relaxed);
    r->jumps++;
    if (d != r->seen_dropped) {
        r->seen_dropped = d;
        r->pos = ((uint64_t)wr << 32) | (uint32_t)r->pos;
        return 1;
    }
    r->pos = ((uint64_t)(wr - r->target) << 32) | (uint32_t)r->pos;
    return 0;
}

static inline double fill_at(const rm_t *r, uint32_t wr)
{
    return (double)(int32_t)(wr - (uint32_t)(r->pos >> 32)) - (double)(uint32_t)r->pos / 4294967296.0;
}

void rm_pull(rm_t *r, int32_t *lr, uint32_t frames)
{
    const uint32_t wr = atomic_load_explicit(&r->wr, memory_order_acquire);
    for (uint32_t i = 0; i < frames; i++) {
        double fill = fill_at(r, wr);
        if (i == 0)
            r->last_fill = fill;
        if (r->state == RM_PRIME) {
            const int go = fill > r->high ? !backlog(r, wr) : fill >= r->target;
            if (!go) {
                lr[2 * i] = lr[2 * i + 1] = 0;
                continue;
            }
            // start exactly on the target, so the loop has nothing to undo
            if (fill_at(r, wr) > r->target)
                r->pos = ((uint64_t)(wr - r->target) << 32) | (uint32_t)r->pos;
            fill = fill_at(r, wr);
            r->state = RM_FADE_IN;
            r->gain = 0.0f;
            r->dgain = 1.0f / r->fade_frames;
        } else if (r->state == RM_RUN && (fill < r->low || fill > r->high)) {
            r->fade_jump = fill > r->high;
            r->state = RM_FADE_OUT;
            r->dgain = 1.0f / r->fade_frames;
        }
        if ((int32_t)(wr - (uint32_t)(r->pos >> 32)) < RM_TAPS / 2 + 1) {
            // out of data mid-fade: cannot happen while low is honoured
            r->state = RM_PRIME;
            r->underflows++;
            r->gain = 0.0f;
            lr[2 * i] = lr[2 * i + 1] = 0;
            continue;
        }
        // the loop follows the clocks only while audio flows normally
        if (r->state == RM_RUN || r->state == RM_FADE_IN) {
            if (fill > r->fill_peak)
                r->fill_peak = fill;
            if (++r->upd_count >= r->upd_frames)
                loop_update(r);
        }
        float l, rt;
        interp(r, r->pos, &l, &rt);
        lr[2 * i] = to_i2s(l * r->gain);
        lr[2 * i + 1] = to_i2s(rt * r->gain);
        r->pos += r->step;
        if (r->state == RM_FADE_IN) {
            r->gain += r->dgain;
            if (r->gain >= 1.0f) {
                r->gain = 1.0f;
                r->state = RM_RUN;
            }
        } else if (r->state == RM_FADE_OUT) {
            r->gain -= r->dgain;
            if (r->gain <= 0.0f) {
                r->gain = 0.0f;
                if (r->fade_jump) {
                    r->state = backlog(r, wr) ? RM_PRIME : RM_FADE_IN;
                } else {
                    r->underflows++;
                    r->state = RM_PRIME;
                }
                // the window in progress saw the old fill
                r->fill_peak = -1e9;
                r->upd_count = 0;
            }
        }
    }
    const uint32_t c = (uint32_t)(r->pos >> 32);
    atomic_store_explicit(&r->rd_floor, c - (RM_TAPS / 2 - 1), memory_order_release);
}

void rm_status(const rm_t *r, rm_status_t *s)
{
    s->state = r->state;
    s->fill_ms = r->last_fill * 1000.0 / r->fs_in;
    s->ppm = r->u * 1e6;
    s->underflows = r->underflows;
    s->jumps = r->jumps;
    s->dropped = atomic_load_explicit(&r->dropped, memory_order_relaxed);
}

// test access to the interpolator alone
void rm_interp_at(const rm_t *r, uint64_t pos, float *l, float *rt)
{
    interp(r, pos, l, rt);
}
