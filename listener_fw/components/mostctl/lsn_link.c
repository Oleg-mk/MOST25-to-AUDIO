// lsn_link.c - see lsn_link.h.
#include "lsn_link.h"

#include <string.h>

void lsn_rx_init(lsn_rx_t *r)
{
    memset(r, 0, sizeof *r);
}

static void take(lsn_rx_t *r, lsn_block_cb cb, void *ctx)
{
    uint8_t x = 0;
    for (int i = 0; i < LSN_PKT_LEN - 1; i++)
        x ^= r->buf[i];
    if (x == r->buf[LSN_PKT_LEN - 1]) {
        lsn_block_t b;
        const uint8_t *p = r->buf;
        b.frame = (uint32_t)p[2] | (uint32_t)p[3] << 8 | (uint32_t)p[4] << 16 | (uint32_t)p[5] << 24;
        b.status = p[6];
        b.ui_q88 = (uint16_t)(p[7] | p[8] << 8);
        memcpy(b.ctl, &p[9], 32);
        r->good++;
        r->n = 0;
        cb(ctx, &b);
        return;
    }
    r->bad++;
    // look for the next A5 5A inside the bad packet
    int k = 1;
    while (k < LSN_PKT_LEN && !(r->buf[k] == 0xA5 && (k + 1 == LSN_PKT_LEN || r->buf[k + 1] == 0x5A)))
        k++;
    r->n = LSN_PKT_LEN - k;
    memmove(r->buf, &r->buf[k], (size_t)r->n);
}

void lsn_rx_feed(lsn_rx_t *r, const uint8_t *p, size_t n, lsn_block_cb cb, void *ctx)
{
    // buf holds nothing, a lone A5, or a packet begun with A5 5A
    for (size_t i = 0; i < n; i++) {
        const uint8_t c = p[i];
        if (r->n == 0 && c != 0xA5)
            continue;
        if (r->n == 1 && c != 0x5A) {
            r->n = (c == 0xA5) ? 1 : 0;
            continue;
        }
        r->buf[r->n++] = c;
        if (r->n == LSN_PKT_LEN)
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

void lsn_cmd_stereo(uint8_t out[LSN_CMD_LEN], int bits, const uint8_t l[3], const uint8_t r[3])
{
    cmd(out, 0x01, width(bits), l, r);
}

void lsn_cmd_inject(uint8_t out[LSN_CMD_LEN], int bits, int keep_parity,
                    const uint8_t l[3], const uint8_t r[3])
{
    cmd(out, 0x02, (uint8_t)(width(bits) | (keep_parity ? 0x80 : 0)), l, r);
}

void lsn_cmd_word(uint8_t out[LSN_CMD_LEN], uint8_t addr, int32_t value, int commit)
{
    const uint32_t v = (uint32_t)value;
    const uint8_t l[3] = {(uint8_t)(v >> 24), (uint8_t)(v >> 16), (uint8_t)(v >> 8)};
    const uint8_t r[3] = {(uint8_t)v, (uint8_t)(commit ? 1 : 0), 0};
    cmd(out, 0x03, addr, l, r);
}
