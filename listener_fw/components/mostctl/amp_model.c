// amp_model.c - see amp_model.h.
#include "amp_model.h"

#include <string.h>

enum {
    F_SOURCEINFO = 0x100, F_ALLOCATE = 0x101, F_DEALLOCATE = 0x102,
    F_SINKINFO = 0x110, F_CONNECT = 0x111, F_DISCONNECT = 0x112, F_MUTE = 0x113,
};

void am_init(am_t *a)
{
    memset(a, 0, sizeof *a);
}

static int is_ack(uint8_t op)
{
    return op == MM_OP_STARTRESULTACK || op == MM_OP_ABORTACK || op == MM_OP_STARTACK ||
           op == MM_OP_ERRORACK || op == MM_OP_PROCESSINGACK || op == MM_OP_RESULTACK;
}

// A channel list from p[0..n): ascending, each 0..59. All 0xFF is "none"
// (n = 0); anything else odd is refused (-1).
static int parse_list(const uint8_t *p, int n, am_list_t *out)
{
    out->n = 0;
    if (n <= 0)
        return 0;
    int ff = 0;
    for (int i = 0; i < n; i++)
        ff += p[i] == 0xFF;
    if (ff == n)
        return 0;
    if (ff || n > AM_MAX_CH)
        return -1;
    for (int i = 0; i < n; i++)
        if (p[i] > 59 || (i && p[i] <= p[i - 1]))
            return -1;
    out->n = (uint8_t)n;
    memcpy(out->ch, p, (size_t)n);
    return 0;
}

static int same(const am_list_t *x, const am_list_t *y)
{
    return x->n == y->n && memcmp(x->ch, y->ch, x->n) == 0;
}

static int set_list(am_list_t *dst, const am_list_t *src)
{
    if (same(dst, src))
        return 0;
    *dst = *src;
    return 1;
}

// A request goes to the device (its target); every other OPType comes from it.
static int is_req(uint8_t op)
{
    return op <= MM_OP_STARTACK;
}

static int wild(uint8_t inst)
{
    return inst == 0x00 || inst == 0xFF;
}

static int find_dev(const am_t *a, uint16_t dev, uint8_t fb)
{
    for (int i = 0; i < AM_DEVS; i++)
        if (a->where[i].used && a->where[i].dev == dev && a->where[i].fb == fb)
            return i;
    return -1;
}

static int find_sink(const am_t *a, uint16_t dev, uint8_t inst, uint8_t nr)
{
    for (int i = 0; i < AM_SINKS; i++)
        if (a->sink[i].used && a->sink[i].dev == dev && a->sink[i].inst == inst && a->sink[i].nr == nr)
            return i;
    return -1;
}

static int find_src(const am_t *a, uint16_t dev, uint8_t inst, uint8_t nr)
{
    for (int i = 0; i < AM_SOURCES; i++)
        if (a->src[i].used && a->src[i].dev == dev && a->src[i].inst == inst && a->src[i].nr == nr)
            return i;
    return -1;
}

static int find_mute0(const am_t *a, uint16_t dev, uint8_t inst)
{
    for (int i = 0; i < AM_SINKS; i++)
        if (a->mute0[i].used && a->mute0[i].dev == dev && a->mute0[i].inst == inst)
            return i;
    return -1;
}

static int src_slot(am_t *a, uint16_t dev, uint8_t inst, uint8_t nr)
{
    const int s = find_src(a, dev, inst, nr);
    if (s >= 0)
        return s;
    for (int i = 0; i < AM_SOURCES; i++)
        if (!a->src[i].used) {
            memset(&a->src[i], 0, sizeof a->src[i]);
            a->src[i].used = 1;
            a->src[i].dev = dev;
            a->src[i].inst = inst;
            a->src[i].nr = nr;
            return i;
        }
    return -1;
}

static int sink_slot(am_t *a, uint16_t dev, uint8_t inst, uint8_t nr)
{
    const int s = find_sink(a, dev, inst, nr);
    if (s >= 0)
        return s;
    for (int i = 0; i < AM_SINKS; i++)
        if (!a->sink[i].used) {
            memset(&a->sink[i], 0, sizeof a->sink[i]);
            a->sink[i].used = 1;
            a->sink[i].dev = dev;
            a->sink[i].inst = inst;
            a->sink[i].nr = nr;
            const int m = find_mute0(a, dev, inst);      // a Mute to all sinks covers this one too
            a->sink[i].muted = m >= 0 ? a->mute0[m].muted : 0;
            return i;
        }
    return -1;
}

// Requests to "any instance" that came before the device showed its own wait
// under instance 0. Now that it has shown inst, they are filed under it.
static void settle(am_t *a, uint16_t dev, uint8_t fb, uint8_t inst)
{
    if (fb == AM_FB_AMP) {
        for (int i = 0; i < AM_SINKS; i++) {
            if (!a->sink[i].used || a->sink[i].dev != dev || a->sink[i].inst != 0)
                continue;
            const int j = find_sink(a, dev, inst, a->sink[i].nr);
            if (j < 0) {
                a->sink[i].inst = inst;
                continue;
            }
            if (a->sink[i].pend_ok) {
                a->sink[j].pend = a->sink[i].pend;
                a->sink[j].pend_ok = 1;
            }
            a->sink[i].used = 0;
        }
        const int m = find_mute0(a, dev, 0);
        if (m >= 0) {
            if (find_mute0(a, dev, inst) >= 0)
                a->mute0[m].used = 0;
            else
                a->mute0[m].inst = inst;
        }
        return;
    }
    for (int i = 0; i < AM_SOURCES; i++) {
        if (!a->src[i].used || a->src[i].dev != dev || a->src[i].inst != 0)
            continue;
        const int j = find_src(a, dev, inst, a->src[i].nr);
        if (j < 0) {
            a->src[i].inst = inst;
            continue;
        }
        a->src[j].ch = a->src[i].ch;            // the request came later than what was known
        a->src[i].used = 0;
    }
}

// The instance a telegram is about. An answer names the real one, which is
// learnt for its device; a request to any instance means the one its device
// has shown (0 while it has shown none).
static uint8_t inst_of(am_t *a, const mm_tel_t *t)
{
    if (!is_req(t->op)) {
        if (!wild(t->inst)) {
            int w = find_dev(a, t->source, t->fblock);
            for (int i = 0; i < AM_DEVS && w < 0; i++)
                if (!a->where[i].used)
                    w = i;
            if (w >= 0) {
                a->where[w].used = 1;
                a->where[w].dev = t->source;
                a->where[w].fb = t->fblock;
                a->where[w].inst = t->inst;
            }
            settle(a, t->source, t->fblock, t->inst);
        }
        return t->inst;
    }
    if (!wild(t->inst))
        return t->inst;
    const int w = find_dev(a, t->target, t->fblock);
    return w >= 0 ? a->where[w].inst : 0;
}

// SourceInfo / SinkInfo: Nr, DataType, Resolution, AudioChannels, Delay,
// ChannelList. Only PCM at 2 or 3 bytes a sample and 1 or 2 channels, with a
// list exactly that long, is taken (all 0xFF: none, n = 0); -1 otherwise.
static int fmt_list(const uint8_t *p, int n, am_list_t *l)
{
    l->n = 0;
    if (n < 6 || p[1] != 0x00)
        return -1;
    const int res = p[2], chn = p[3];
    if ((res != 2 && res != 3) || (chn != 1 && chn != 2) || n - 5 != res * chn)
        return -1;
    return parse_list(&p[5], n - 5, l);
}

static int auxin(am_t *a, const mm_tel_t *t, uint16_t dev, uint8_t inst, const uint8_t *p, int n)
{
    am_list_t l;
    int s;
    switch (t->fkt) {
    case F_ALLOCATE:        // Result: SourceNr, SrcDelay, ChannelList
        if ((t->op != MM_OP_RESULT && t->op != MM_OP_RESULTACK) || n < 3 || parse_list(&p[2], n - 2, &l))
            return 0;
        s = src_slot(a, dev, inst, p[0]);
        return s >= 0 ? set_list(&a->src[s].ch, &l) : 0;
    case F_SOURCEINFO:      // Status: SourceNr, DataType, Resolution, AudioChannels, SrcDelay, ChannelList
        if (t->op != MM_OP_STATUS || n < 1)
            return 0;
        s = src_slot(a, dev, inst, p[0]);
        if (s < 0)
            return 0;
        if (fmt_list(p, n, &l))
            l.n = 0;                                    // not a format we take: nothing known any more
        return set_list(&a->src[s].ch, &l);
    case F_DEALLOCATE:      // as soon as it is asked for, the channels are not AUX's to use
        if (n < 1 || !(t->op == MM_OP_STARTRESULT || t->op == MM_OP_STARTRESULTACK ||
                       t->op == MM_OP_RESULT || t->op == MM_OP_RESULTACK))
            return 0;
        s = src_slot(a, dev, inst, p[0]);
        l.n = 0;
        return s >= 0 ? set_list(&a->src[s].ch, &l) : 0;
    default:
        return 0;
    }
}

static int amp(am_t *a, const mm_tel_t *t, uint16_t dev, uint8_t inst, const uint8_t *p, int n)
{
    am_list_t l;
    int s, ch = 0;
    switch (t->fkt) {
    case F_CONNECT:
        if ((t->op == MM_OP_STARTRESULT || t->op == MM_OP_STARTRESULTACK) && n >= 3 &&
            !parse_list(&p[2], n - 2, &l)) {
            s = sink_slot(a, dev, inst, p[0]);
            if (s < 0)
                return 0;
            a->sink[s].pend = l;
            a->sink[s].pend_ok = 1;
            if (a->sink[s].connected && !same(&a->sink[s].ch, &l)) {
                a->sink[s].connected = 0;       // it drops the old channels first
                return 1;
            }
            return 0;
        }
        if ((t->op == MM_OP_RESULT || t->op == MM_OP_RESULTACK) && n >= 1) {
            s = sink_slot(a, dev, inst, p[0]);
            if (s < 0 || !a->sink[s].pend_ok)
                return 0;                       // no Connect open for this sink: a late or stray Result
            a->sink[s].pend_ok = 0;
            ch |= !a->sink[s].connected;
            a->sink[s].connected = 1;
            ch |= set_list(&a->sink[s].ch, &a->sink[s].pend);
            return ch;
        }
        if (t->op == MM_OP_ERROR || t->op == MM_OP_ERRORACK) {
            // the device turned a Connect down: none stays open on that instance
            for (int i = 0; i < AM_SINKS; i++)
                if (a->sink[i].used && a->sink[i].dev == dev && a->sink[i].inst == inst)
                    a->sink[i].pend_ok = 0;
        }
        return 0;
    case F_SINKINFO:        // Status: SinkNr, DataType, Resolution, AudioChannels, SinkDelay, ChannelList
        if (t->op != MM_OP_STATUS || n < 1)
            return 0;
        s = sink_slot(a, dev, inst, p[0]);
        if (s < 0)
            return 0;
        if (fmt_list(p, n, &l))
            l.n = 0;                            // not a format we take: nothing known any more
        ch |= (a->sink[s].connected != (l.n > 0));
        a->sink[s].connected = l.n > 0;
        ch |= set_list(&a->sink[s].ch, &l);
        return ch;
    case F_DISCONNECT:
        if (n < 1 || !(t->op == MM_OP_STARTRESULT || t->op == MM_OP_STARTRESULTACK ||
                       t->op == MM_OP_RESULT || t->op == MM_OP_RESULTACK))
            return 0;
        s = sink_slot(a, dev, inst, p[0]);
        if (s < 0)
            return 0;
        ch |= a->sink[s].connected;
        a->sink[s].connected = 0;
        a->sink[s].pend_ok = 0;                 // a Connect still open is void too
        l.n = 0;
        ch |= set_list(&a->sink[s].ch, &l);
        return ch;
    case F_MUTE:            // SetGet / Status: SinkNr, Status (bit 0 = muted)
        if (!(t->op == MM_OP_SETGET || t->op == MM_OP_STATUS || t->op == MM_OP_SET) || n < 2)
            return 0;
        if (p[0] == 0) {
            // all sinks of the instance, and every sink of it seen later
            int m = find_mute0(a, dev, inst);
            for (int i = 0; i < AM_SINKS && m < 0; i++)
                if (!a->mute0[i].used)
                    m = i;
            if (m >= 0) {
                ch |= !a->mute0[m].used || a->mute0[m].muted != (p[1] & 1);
                a->mute0[m].used = 1;
                a->mute0[m].dev = dev;
                a->mute0[m].inst = inst;
                a->mute0[m].muted = p[1] & 1;
            }
        } else if (sink_slot(a, dev, inst, p[0]) < 0) {
            return 0;
        }
        for (int i = 0; i < AM_SINKS; i++)
            if (a->sink[i].used && a->sink[i].dev == dev && a->sink[i].inst == inst &&
                (p[0] == 0 || a->sink[i].nr == p[0]) && a->sink[i].muted != (p[1] & 1)) {
                a->sink[i].muted = p[1] & 1;
                ch = 1;
            }
        return ch;
    default:
        return 0;
    }
}

int am_tel(am_t *a, const mm_tel_t *t)
{
    const int skip = is_ack(t->op) ? 2 : 0;     // SenderHandle
    if (t->len < skip || (t->fblock != AM_FB_AUXIN && t->fblock != AM_FB_AMP))
        return 0;
    const uint8_t *p = &t->data[skip];
    const int n = t->len - skip;
    const uint16_t dev = is_req(t->op) ? t->target : t->source;
    const uint8_t inst = inst_of(a, t);
    if (t->fblock == AM_FB_AUXIN)
        return auxin(a, t, dev, inst, p, n);
    return amp(a, t, dev, inst, p, n);
}

static am_pos_t pos_of(const am_list_t *l)
{
    am_pos_t p = {0};
    if (l->n == 4) {
        p.bits = 16;
        p.l[0] = l->ch[0] + 1; p.l[1] = l->ch[1] + 1;
        p.r[0] = l->ch[2] + 1; p.r[1] = l->ch[3] + 1;
    } else if (l->n == 6) {
        p.bits = 24;
        for (int i = 0; i < 3; i++) {
            p.l[i] = l->ch[i] + 1;
            p.r[i] = l->ch[3 + i] + 1;
        }
    }
    return p;
}

am_pos_t am_aux_playing(const am_t *a)
{
    for (int i = 0; i < AM_SOURCES; i++) {
        if (!a->src[i].used || (a->src[i].ch.n != 4 && a->src[i].ch.n != 6))
            continue;
        for (int k = 0; k < AM_SINKS; k++)
            if (a->sink[k].used && a->sink[k].connected && same(&a->sink[k].ch, &a->src[i].ch))
                return pos_of(&a->src[i].ch);
    }
    am_pos_t none = {0};
    return none;
}

static int main_sink(const am_t *a)
{
    int best = -1;
    for (int k = 0; k < AM_SINKS; k++)
        if (a->sink[k].used && a->sink[k].nr == 1 && a->sink[k].connected &&
            (best < 0 || a->sink[k].inst < a->sink[best].inst))
            best = k;
    return best;
}

am_pos_t am_main(const am_t *a)
{
    const int best = main_sink(a);
    if (best >= 0)
        return pos_of(&a->sink[best].ch);
    am_pos_t none = {0};
    return none;
}

int am_main_muted(const am_t *a)
{
    const int best = main_sink(a);
    return best >= 0 && a->sink[best].muted;
}

// a channel list as J3 takes it: 2 / 3 channels mono, 4 / 6 stereo, 16 / 24 bit
static int sink_pos(const am_list_t *l, am_sink_t *s)
{
    if (l->n == 4 || l->n == 6) {
        s->pos = pos_of(l);
        s->mono = 0;
        return 1;
    }
    if (l->n == 2 || l->n == 3) {
        memset(&s->pos, 0, sizeof s->pos);
        s->pos.bits = l->n == 2 ? 16 : 24;
        for (int i = 0; i < l->n; i++)
            s->pos.l[i] = l->ch[i] + 1;
        s->mono = 1;
        return 1;
    }
    return 0;
}

int am_extras(const am_t *a, am_sink_t *out, int n)
{
    memset(out, 0, sizeof *out * (size_t)(n > 0 ? n : 0));
    const int m = main_sink(a);
    int inst = m >= 0 ? a->sink[m].inst : -1;
    uint16_t dev = m >= 0 ? a->sink[m].dev : 0;
    am_sink_t probe;
    if (inst < 0)
        for (int k = 0; k < AM_SINKS; k++)
            if (a->sink[k].used && a->sink[k].connected && a->sink[k].nr >= 2 &&
                sink_pos(&a->sink[k].ch, &probe) && (inst < 0 || a->sink[k].inst < inst)) {
                inst = a->sink[k].inst;
                dev = a->sink[k].dev;
            }
    int got = 0, last = 1;                      // SinkNr taken so far, ascending
    while (got < n) {
        int best = -1;
        for (int k = 0; k < AM_SINKS; k++)
            if (a->sink[k].used && a->sink[k].connected && a->sink[k].dev == dev && a->sink[k].inst == inst &&
                a->sink[k].nr > last && (best < 0 || a->sink[k].nr < a->sink[best].nr))
                best = k;
        if (best < 0)
            break;
        last = a->sink[best].nr;
        am_sink_t s = {0};
        if (!sink_pos(&a->sink[best].ch, &s))
            continue;                           // a list J3 cannot take: skipped, the next one tried
        s.nr = a->sink[best].nr;
        s.muted = a->sink[best].muted;
        out[got++] = s;
    }
    return got;
}
