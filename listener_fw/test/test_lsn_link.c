// test_lsn_link.c - host tests for components/mostctl/lsn_link.c.
//
// Packets as ctrl_uart.v sends them, in a stream with noise between them,
// a corrupted byte, a lost byte, and sync bytes inside the payload; the
// command packets byte for byte.
#include "lsn_link.h"

#include <stdio.h>
#include <string.h>

static int fails;
#define CHECK(cond, ...) do { if (!(cond)) { fails++; printf("    FAIL: "); \
    printf(__VA_ARGS__); printf("\n"); } } while (0)

static void make(uint8_t *p, uint32_t frame, uint8_t status, uint8_t fill)
{
    p[0] = 0xA5; p[1] = 0x5A;
    p[2] = (uint8_t)frame; p[3] = (uint8_t)(frame >> 8); p[4] = (uint8_t)(frame >> 16); p[5] = (uint8_t)(frame >> 24);
    p[6] = status;
    p[7] = 0x34; p[8] = 0x12;
    for (int i = 0; i < 32; i++)
        p[9 + i] = (uint8_t)(fill + i);
    // sync pattern inside the payload, to be sure it cannot start a packet
    p[20] = 0xA5; p[21] = 0x5A;
    uint8_t x = 0;
    for (int i = 0; i < 41; i++)
        x ^= p[i];
    p[41] = x;
}

typedef struct { int n; lsn_block_t last; uint32_t frames[64]; } got_t;

static void on_block(void *ctx, const lsn_block_t *b)
{
    got_t *g = ctx;
    if (g->n < 64)
        g->frames[g->n] = b->frame;
    g->n++;
    g->last = *b;
}

static void test_rx(void)
{
    static uint8_t s[4096];
    size_t n = 0;
    uint8_t p[LSN_PKT_LEN];
    // 1: clean packet after noise
    s[n++] = 0x00; s[n++] = 0xA5; s[n++] = 0x11;             // noise, a false start
    make(p, 1000, LSN_ST_LOCKED | LSN_ST_BLOCK, 0x40); memcpy(&s[n], p, 42); n += 42;
    // 2: a corrupted payload byte - must be dropped
    make(p, 1016, LSN_ST_LOCKED | LSN_ST_BLOCK, 0x50); p[30] ^= 0x01; memcpy(&s[n], p, 42); n += 42;
    // 3: good
    make(p, 1032, LSN_ST_LOCKED | LSN_ST_BLOCK, 0x60); memcpy(&s[n], p, 42); n += 42;
    // 4: one byte lost - dropped, and packet 5 right behind it must survive
    make(p, 1048, LSN_ST_LOCKED | LSN_ST_BLOCK, 0x70); memcpy(&s[n], p, 25); memcpy(&s[n + 25], &p[26], 16); n += 41;
    make(p, 1064, LSN_ST_LOCKED | LSN_ST_BLOCK | LSN_ST_DROPPED, 0x80); memcpy(&s[n], p, 42); n += 42;
    // 6: good, fed byte by byte below
    make(p, 1080, LSN_ST_LOCKED | LSN_ST_BLOCK, 0x90); memcpy(&s[n], p, 42); n += 42;

    lsn_rx_t rx;
    got_t g = {0};
    lsn_rx_init(&rx);
    for (size_t i = 0; i < n; i++)
        lsn_rx_feed(&rx, &s[i], 1, on_block, &g);
    printf("rx: %d packets, frames", g.n);
    for (int i = 0; i < g.n && i < 64; i++)
        printf(" %u", (unsigned)g.frames[i]);
    printf("; good %u bad %u\n", (unsigned)rx.good, (unsigned)rx.bad);
    CHECK(g.n == 4, "%d packets, want 4 (1000, 1032, 1064, 1080)", g.n);
    CHECK(g.n >= 4 && g.frames[0] == 1000 && g.frames[1] == 1032 && g.frames[2] == 1064 && g.frames[3] == 1080,
          "wrong packets");
    CHECK(g.last.status == (LSN_ST_LOCKED | LSN_ST_BLOCK) && g.last.ui_q88 == 0x1234 &&
          g.last.ctl[0] == 0x90 && g.last.ctl[31] == (uint8_t)(0x90 + 31), "fields of the last packet");

    // the same stream in one call
    got_t g2 = {0};
    lsn_rx_init(&rx);
    lsn_rx_feed(&rx, s, n, on_block, &g2);
    CHECK(g2.n == 4, "one call: %d packets", g2.n);
}

static void test_cmd(void)
{
    uint8_t c[LSN_CMD_LEN];
    const uint8_t l[3] = {5, 6, 0}, r[3] = {7, 8, 0};
    lsn_cmd_inject(c, 16, 0, l, r);
    const uint8_t want[LSN_CMD_LEN] = {0xA5, 0x5A, 0x02, 0x02, 5, 6, 0, 7, 8, 0,
                                       (uint8_t)(0xA5 ^ 0x5A ^ 0x02 ^ 0x02 ^ 5 ^ 6 ^ 7 ^ 8)};
    printf("cmd 02:");
    for (int i = 0; i < LSN_CMD_LEN; i++)
        printf(" %02X", c[i]);
    printf("\n");
    CHECK(memcmp(c, want, sizeof want) == 0, "inject command bytes");
    lsn_cmd_inject(c, 0, 1, NULL, NULL);
    CHECK(c[2] == 0x02 && c[3] == 0x80 && c[4] == 0 && c[9] == 0, "inject off, keep parity");
    lsn_cmd_stereo(c, 24, l, r);
    CHECK(c[2] == 0x01 && c[3] == 0x03, "stereo 24 bit");
    lsn_cmd_word(c, 46, (int32_t)0xFF012345, 1);
    const uint8_t w46[LSN_CMD_LEN] = {0xA5, 0x5A, 0x03, 46, 0xFF, 0x01, 0x23, 0x45, 0x01, 0x00,
                                      (uint8_t)(0xA5 ^ 0x5A ^ 0x03 ^ 46 ^ 0xFF ^ 0x01 ^ 0x23 ^ 0x45 ^ 0x01)};
    CHECK(memcmp(c, w46, sizeof w46) == 0, "coefficient word: address, value MSB first, commit");
    lsn_cmd_word(c, 5, 0x10000000, 0);
    CHECK(c[3] == 5 && c[4] == 0x10 && c[8] == 0x00 && c[9] == 0x00, "coefficient word without commit");
    uint8_t x = 0;
    for (int i = 0; i < LSN_CMD_LEN; i++)
        x ^= c[i];
    CHECK(x == 0, "XOR of the whole packet is 0");
}

int main(void)
{
    test_rx();
    test_cmd();
    printf(fails ? "\n%d FAILED\n" : "\nall passed\n", fails);
    return fails != 0;
}
