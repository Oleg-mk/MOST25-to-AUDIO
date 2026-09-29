// lsn_link.c - see lsn_link.h.
#include "lsn_link.h"

#include <string.h>

void lsn_rx_init(lsn_rx_t *r)
{
    memset(r, 0, sizeof *r);
}

static int is_sync2(uint8_t c)
{
    return c == 0x5A || c == 0xC5;
}

static void take(lsn_rx_t *r, lsn_block_cb cb, void *ctx)
{
    const int len = (r->kind == 2) ? LSN_CAP_LEN : LSN_PKT_LEN;
    const uint8_t *p = r->buf;
    uint8_t x = 0;
    for (int i = 0; i < len - 1; i++)
        x ^= p[i];
    if (x == p[len - 1]) {
        if (r->kind == 2) {
            r->cap_good++;
            r->n = 0;
            if (r->cap_cb) {
                const uint32_t g = (uint32_t)p[36] | (uint32_t)p[37] << 8 | (uint32_t)p[38] << 16 |
                                   (uint32_t)p[39] << 24;
                const uint32_t cnt = (uint32_t)p[4] | (uint32_t)p[5] << 8 | (uint32_t)p[6] << 16 |
                                     (uint32_t)p[7] << 24;
                r->cap_cb(ctx, (uint16_t)(p[2] | p[3] << 8), &p[4], g, cnt);
            }
            return;
        }
        lsn_block_t b;
        b.frame = (uint32_t)p[2] | (uint32_t)p[3] << 8 | (uint32_t)p[4] << 16 | (uint32_t)p[5] << 24;
        b.status = p[6];
        b.ui_q88 = (uint16_t)(p[7] | p[8] << 8);
        memcpy(b.ctl, &p[9], 32);
        r->good++;
        r->n = 0;
        cb(ctx, &b);
        return;
    }
    if (r->kind == 2)
        r->cap_bad++;
    else
        r->bad++;
    // look for the next A5 5A / A5 C5 inside the bad packet
    int k = 1;
    while (k < len && !(r->buf[k] == 0xA5 && (k + 1 == len || is_sync2(r->buf[k + 1]))))
        k++;
    r->n = len - k;
    memmove(r->buf, &r->buf[k], (size_t)r->n);
    r->kind = (r->n >= 2) ? (r->buf[1] == 0xC5 ? 2 : 1) : 0;
}

void lsn_rx_feed(lsn_rx_t *r, const uint8_t *p, size_t n, lsn_block_cb cb, void *ctx)
{
    // buf holds nothing, a lone A5, or a packet begun with A5 5A (control) or A5 C5 (capture)
    for (size_t i = 0; i < n; i++) {
        const uint8_t c = p[i];
        if (r->n == 0 && c != 0xA5)
            continue;
        if (r->n == 1) {
            if (!is_sync2(c)) {
                r->n = (c == 0xA5) ? 1 : 0;
                continue;
            }
            r->kind = (c == 0xC5) ? 2 : 1;
        }
        r->buf[r->n++] = c;
        if (r->n == ((r->kind == 2) ? LSN_CAP_LEN : LSN_PKT_LEN))
            take(r, cb, ctx);
    }
}

static void cmd(uint8_t out[LSN_CMD_LEN], uint8_t c, uint8_t first, const uint8_t l[3], const uint8_t r[3])
{
    out[0] = 0xA5;
    out[1] = 0x5A;
    out[2] = c;
    out[3] = first;
    for (int i = 0; i < 3; i++) {
        out[4 + i] = l ? l[i] : 0;
        out[7 + i] = r ? r[i] : 0;
    }
    uint8_t x = 0;
    for (int i = 0; i < LSN_CMD_LEN - 1; i++)
        x ^= out[i];
    out[LSN_CMD_LEN - 1] = x;
}

static uint8_t width(int bits)
{
    return bits == 24 ? 3 : bits == 16 ? 2 : 0;
}

void lsn_cmd_source(uint8_t out[LSN_CMD_LEN], int stream, int bits, int mono, const uint8_t l[3],
                    const uint8_t r[3])
{
    cmd(out, 0x01, (uint8_t)(width(bits) | (mono ? 0x04 : 0) | ((stream & 3) << 4)), l, mono ? NULL : r);
}

void lsn_cmd_stereo(uint8_t out[LSN_CMD_LEN], int bits, const uint8_t l[3], const uint8_t r[3])
{
    lsn_cmd_source(out, 0, bits, 0, l, r);
}

void lsn_cmd_inject(uint8_t out[LSN_CMD_LEN], int bits, int keep_parity, int spdif_in,
                    const uint8_t l[3], const uint8_t r[3])
{
    cmd(out, 0x02, (uint8_t)(width(bits) | (spdif_in ? 0x04 : 0) | (keep_parity ? 0x80 : 0)), l, r);
}

void lsn_cmd_capture(uint8_t out[LSN_CMD_LEN], uint8_t mode)
{
    cmd(out, 0x04, mode, NULL, NULL);
}

void lsn_cmd_word(uint8_t out[LSN_CMD_LEN], uint8_t addr, int32_t value, int commit)
{
    const uint32_t v = (uint32_t)value;
    const uint8_t l[3] = {(uint8_t)(v >> 24), (uint8_t)(v >> 16), (uint8_t)(v >> 8)};
    const uint8_t r[3] = {(uint8_t)v, (uint8_t)(commit ? 1 : 0), 0};
    cmd(out, 0x03, addr, l, r);
}
