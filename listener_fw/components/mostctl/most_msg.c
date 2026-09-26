// most_msg.c - see most_msg.h.
//
// A block is taken as a telegram only when all of this holds:
//   message type 0x00 (the system messages 0x01-0x05 carry no telegram);
//   target not 0x0000-0x000F (internal, and the MOST 3.0 "free-up" 0x0000),
//   not reserved (0x1000-0xFFFF);
//   source a logical or static address (0x0010-0x02FF, 0x0500-0x0FFF): the
//   receiver sees the sender's logical address there;
//   TelID 0-3 (8/9, MOST High Protocol, are skipped quietly);
//   TelLen at most 12, or 11 to a group / broadcast address (0x0300-0x03FF),
//   where the NIC puts a checksum in the last data byte;
//   the data area is not all 0x00 / 0xFF.
// First and middle segments must be full (TelLen 12, or 11 to a group).
#include "most_msg.h"

#include <string.h>

// 5 s at 48 kHz, 5.4 s at 44.1 kHz; the spec's tWaitForNextSegment is 4975..10015 ms
#define SEG_TIMEOUT_FRAMES  240000u

static uint16_t rd16(const uint8_t *p)
{
    return (uint16_t)(p[0] << 8 | p[1]);
}

static int is_group(uint16_t a)
{
    return a >= 0x0300 && a <= 0x03FF;
}

static int target_ok(uint16_t a)
{
    return a >= 0x0010 && a <= 0x0FFF;
}

static int source_ok(uint16_t a)
{
    return (a >= 0x0010 && a <= 0x02FF) || (a >= 0x0500 && a <= 0x0FFF);
}

static int idle(const uint8_t *d)
{
    for (int i = 0; i < 17; i++)
        if (d[i] != 0x00 && d[i] != 0xFF)
            return 0;
    return 1;
}

void mm_init(mm_t *m)
{
    memset(m, 0, sizeof *m);
}

static void append(mm_t *m, int s, const uint8_t *p, int n)
{
    int room = MM_MAX_PAYLOAD - m->slot[s].len;
    if (n > room) {
        n = room;
        m->slot[s].truncated = 1;
    }
    memcpy(&m->slot[s].data[m->slot[s].len], p, (size_t)n);
    m->slot[s].len = (uint8_t)(m->slot[s].len + n);
}

static int find(const mm_t *m, uint16_t src, uint16_t tgt)
{
    for (int i = 0; i < MM_SLOTS; i++)
        if (m->slot[i].active && m->slot[i].source == src && m->slot[i].target == tgt)
            return i;
    return -1;
}

void mm_block(mm_t *m, const uint8_t b[32], uint32_t frame, mm_tel_cb cb, void *ctx)
{
    m->blocks++;
    for (int i = 0; i < MM_SLOTS; i++)
        if (m->slot[i].active && frame - m->slot[i].last_frame > SEG_TIMEOUT_FRAMES) {
            m->slot[i].active = 0;
            m->seg_dropped++;
        }
    if (b[8] != 0x00)
        return;
    const uint16_t tgt = rd16(&b[4]), src = rd16(&b[6]);
    const uint8_t *d = &b[9];
    const uint8_t telid = d[4] >> 4, tellen = d[4] & 0x0F;
    const uint8_t full = is_group(tgt) ? 11 : 12;
    if (telid == 8 || telid == 9)
        return;
    if (!target_ok(tgt) || !source_ok(src) || telid > 3 || tellen > full || idle(d)) {
        m->rejected++;
        return;
    }
    mm_tel_t t;
    t.frame = frame;
    t.target = tgt;
    t.source = src;
    t.fblock = d[0];
    t.inst = d[1];
    t.fkt = (uint16_t)(d[2] << 4 | d[3] >> 4);
    t.op = d[3] & 0x0F;
    t.segmented = 0;
    t.truncated = 0;

    if (telid == 0) {
        t.len = tellen;
        memcpy(t.data, &d[5], tellen);
        m->telegrams++;
        cb(ctx, &t);
        return;
    }
    const uint8_t cnt = d[5];
    int s = find(m, src, tgt);
    if (telid == 1) {
        if (tellen != full || cnt != 0x00) {
            m->rejected++;
            return;
        }
        if (s < 0) {
            for (int i = 0; i < MM_SLOTS && s < 0; i++)
                if (!m->slot[i].active)
                    s = i;
            if (s < 0) {                        // all busy: the stalest one goes
                s = 0;
                for (int i = 1; i < MM_SLOTS; i++)
                    if (frame - m->slot[i].last_frame > frame - m->slot[s].last_frame)
                        s = i;
                m->seg_dropped++;
            }
        }
        memset(&m->slot[s], 0, sizeof m->slot[s]);
        m->slot[s].active = 1;
        m->slot[s].source = src;
        m->slot[s].target = tgt;
        m->slot[s].fblock = t.fblock;
        m->slot[s].inst = t.inst;
        m->slot[s].fkt = t.fkt;
        m->slot[s].op = t.op;
        m->slot[s].last_cnt = 0x00;
        m->slot[s].next_cnt = 0x01;
        m->slot[s].last_frame = frame;
        append(m, s, &d[6], tellen - 1);
        return;
    }
    // middle or last segment
    if (s < 0) {
        m->seg_dropped++;
        return;
    }
    if (m->slot[s].fblock != t.fblock || m->slot[s].inst != t.inst || m->slot[s].fkt != t.fkt ||
        m->slot[s].op != t.op || tellen < 1 || (telid == 2 && tellen != full)) {
        m->slot[s].active = 0;
        m->seg_dropped++;
        return;
    }
    if (cnt == m->slot[s].last_cnt)
        return;                                 // the same segment sent again
    if (cnt != m->slot[s].next_cnt) {
        m->slot[s].active = 0;                  // one was lost
        m->seg_dropped++;
        return;
    }
    append(m, s, &d[6], tellen - 1);
    m->slot[s].last_cnt = cnt;
    m->slot[s].next_cnt = (uint8_t)(cnt + 1);
    m->slot[s].last_frame = frame;
    if (telid == 3) {
        t.fblock = m->slot[s].fblock;
        t.len = m->slot[s].len;
        t.segmented = 1;
        t.truncated = m->slot[s].truncated;
        memcpy(t.data, m->slot[s].data, t.len);
        m->slot[s].active = 0;
        m->telegrams++;
        cb(ctx, &t);
    }
}
