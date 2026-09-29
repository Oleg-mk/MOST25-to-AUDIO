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

// ------------------------------------------------ capture packets among control ones
static void make_cap(uint8_t *p, uint16_t seq, uint8_t fill, uint32_t glitch)
{
    p[0] = 0xA5; p[1] = 0xC5;
    p[2] = (uint8_t)seq; p[3] = (uint8_t)(seq >> 8);
    for (int i = 0; i < 32; i++)
        p[4 + i] = (uint8_t)(fill + i);
    for (int i = 0; i < 4; i++)
        p[36 + i] = (uint8_t)(glitch >> (8 * i));
    uint8_t x = 0;
    for (int i = 0; i < 40; i++)
        x ^= p[i];
    p[40] = x;
}

typedef struct { int n; uint16_t seq[8]; uint8_t first[8]; uint32_t glitch[8]; uint32_t count[8]; } cap_t;

static void on_cap(void *ctx, uint16_t seq, const uint8_t lens[32], uint32_t glitch, uint32_t count)
{
    cap_t *g = ctx;
    if (g->n < 8) {
        g->seq[g->n] = seq; g->first[g->n] = lens[0]; g->glitch[g->n] = glitch; g->count[g->n] = count;
    }
    g->n++;
}

static void on_block_cap(void *ctx, const lsn_block_t *b)
{
    (void)b;
    ((cap_t *)ctx)->count[7]++;          // control packets, counted apart
}

static void test_cap(void)
{
    static uint8_t s[1024];
    size_t n = 0;
    uint8_t p[LSN_PKT_LEN];
    make(p, 2000, LSN_ST_LOCKED | LSN_ST_BLOCK, 0x10); memcpy(&s[n], p, 42); n += 42;
    make_cap(p, 5, 0x20, 0x80000001u); memcpy(&s[n], p, 41); n += 41;          // runs 32..63, glitch on runs 0 and 31
    make_cap(p, 6, 0x30, 0); p[20] ^= 0x10; memcpy(&s[n], p, 41); n += 41;   // corrupted: dropped
    make(p, 2016, LSN_ST_LOCKED | LSN_ST_BLOCK, 0x40); memcpy(&s[n], p, 42); n += 42;
    make_cap(p, 0xFFFF, 0, 0); p[4] = 0x00; p[5] = 0x00; p[6] = 0x01; p[7] = 0x00;   // trailer: 65536 runs
    { uint8_t x = 0; for (int i = 0; i < 40; i++) x ^= p[i]; p[40] = x; }
    memcpy(&s[n], p, 41); n += 41;
    make_cap(p, 7, 0x50, 0); memcpy(&s[n], p, 41); n += 41;                   // A5 C5 right after a trailer

    lsn_rx_t rx;
    cap_t g = {0};
    lsn_rx_init(&rx);
    rx.cap_cb = on_cap;
    for (size_t i = 0; i < n; i++)
        lsn_rx_feed(&rx, &s[i], 1, on_block_cap, &g);
    printf("cap: %d capture packets, %u control; good %u bad %u\n", g.n, (unsigned)g.count[7],
           (unsigned)rx.cap_good, (unsigned)rx.cap_bad);
    CHECK(g.n == 3 && rx.cap_good == 3 && rx.cap_bad == 1, "3 good capture packets and 1 bad, got %d / %u",
          g.n, (unsigned)rx.cap_bad);
    CHECK(g.count[7] == 2 && rx.good == 2 && rx.bad == 0, "both control packets, byte by byte");
    CHECK(g.seq[0] == 5 && g.first[0] == 0x20 && g.glitch[0] == 0x80000001u, "packet 5's fields");
    CHECK(g.seq[1] == 0xFFFF && g.count[1] == 65536u, "the trailer's count");
    CHECK(g.seq[2] == 7 && g.first[2] == 0x50, "the packet after the trailer");
    // the same in one call
    cap_t g2 = {0};
    lsn_rx_init(&rx);
    rx.cap_cb = on_cap;
    lsn_rx_feed(&rx, s, n, on_block_cap, &g2);
    CHECK(g2.n == 3 && g2.count[7] == 2, "one call: %d capture, %u control", g2.n, (unsigned)g2.count[7]);
    // without a callback capture packets are counted and dropped, control unaffected
    cap_t g3 = {0};
    lsn_rx_init(&rx);
    lsn_rx_feed(&rx, s, n, on_block_cap, &g3);
    CHECK(g3.n == 0 && g3.count[7] == 2 && rx.cap_good == 3, "no callback: counted, dropped");
}

static void test_cmd(void)
{
    uint8_t c[LSN_CMD_LEN];
    const uint8_t l[3] = {5, 6, 0}, r[3] = {7, 8, 0};
    lsn_cmd_inject(c, 16, 0, 0, l, r);
    const uint8_t want[LSN_CMD_LEN] = {0xA5, 0x5A, 0x02, 0x02, 5, 6, 0, 7, 8, 0,
                                       (uint8_t)(0xA5 ^ 0x5A ^ 0x02 ^ 0x02 ^ 5 ^ 6 ^ 7 ^ 8)};
    printf("cmd 02:");
    for (int i = 0; i < LSN_CMD_LEN; i++)
        printf(" %02X", c[i]);
    printf("\n");
    CHECK(memcmp(c, want, sizeof want) == 0, "inject command bytes");
    lsn_cmd_inject(c, 0, 1, 0, NULL, NULL);
    CHECK(c[2] == 0x02 && c[3] == 0x80 && c[4] == 0 && c[9] == 0, "inject off, keep parity");
    lsn_cmd_inject(c, 24, 0, 1, l, r);
    CHECK(c[2] == 0x02 && c[3] == 0x07 && c[4] == 5 && c[7] == 7, "inject 24 bit from the S/PDIF input");
    lsn_cmd_stereo(c, 24, l, r);
    CHECK(c[2] == 0x01 && c[3] == 0x03, "stereo 24 bit");
    lsn_cmd_source(c, 1, 16, 1, l, r);
    const uint8_t s1[LSN_CMD_LEN] = {0xA5, 0x5A, 0x01, 0x16, 5, 6, 0, 0, 0, 0,
                                     (uint8_t)(0xA5 ^ 0x5A ^ 0x01 ^ 0x16 ^ 5 ^ 6)};
    CHECK(memcmp(c, s1, sizeof s1) == 0, "stream 1, 16-bit mono: P = 16h, the right bytes zero");
    lsn_cmd_source(c, 2, 24, 0, l, r);
    CHECK(c[3] == 0x23 && c[7] == 7 && c[8] == 8, "stream 2, 24-bit stereo: P = 23h");
    lsn_cmd_source(c, 2, 0, 0, NULL, NULL);
    CHECK(c[3] == 0x20 && c[4] == 0, "stream 2 off: P = 20h");
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
    lsn_cmd_capture(c, LSN_CAP_ARM | LSN_CAP_AUTO);
    CHECK(c[2] == 0x04 && c[3] == 0x05 && c[4] == 0 && c[9] == 0 &&
          c[10] == (uint8_t)(0xA5 ^ 0x5A ^ 0x04 ^ 0x05), "capture command: arm and dump when full");
}

int main(void)
{
    test_rx();
    test_cap();
    test_cmd();
    printf(fails ? "\n%d FAILED\n" : "\nall passed\n", fails);
    return fails != 0;
}
