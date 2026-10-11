// test_mostctl.c - host tests for components/mostctl: most_msg, amp_model,
// ain and wheel.
//
// Blocks are built to the layout in docs/host_control_formats.md:
// 0-3 arbitration, 4-5 target, 6-7 source, 8 message type, 9 FBlockID,
// 10 InstID, 11-12 FktID:OPType, 13 TelID:TelLen, 14-25 data, 26-27 CRC,
// 28-29 transmission status.
#include "ain.h"
#include "amp_model.h"
#include "most_msg.h"
#include "wheel.h"

#include <stdio.h>
#include <string.h>

static int fails;
#define CHECK(cond, ...) do { if (!(cond)) { fails++; printf("    FAIL: "); \
    printf(__VA_ARGS__); printf("\n"); } } while (0)

#define HU    0x0100            // head unit, logical address
#define AMP   0x0103
#define AUX   0x0105

static void block(uint8_t b[32], uint16_t tgt, uint16_t src, uint8_t fb, uint8_t inst, uint16_t fkt,
                  uint8_t op, uint8_t telid, const uint8_t *d, int len)
{
    memset(b, 0, 32);
    b[0] = 0x3C; b[1] = 0x81; b[2] = 0x5A; b[3] = 0x0F;          // arbitration: whatever
    b[4] = (uint8_t)(tgt >> 8); b[5] = (uint8_t)tgt;
    b[6] = (uint8_t)(src >> 8); b[7] = (uint8_t)src;
    b[8] = 0x00;
    b[9] = fb; b[10] = inst;
    b[11] = (uint8_t)(fkt >> 4); b[12] = (uint8_t)((fkt & 0xF) << 4 | op);
    b[13] = (uint8_t)(telid << 4 | len);
    memcpy(&b[14], d, (size_t)len);
    b[26] = 0xA7; b[27] = 0x31;                                  // CRC: unknown, not checked
    b[28] = 0x10; b[29] = 0x10;
}

static mm_tel_t got[16];
static int ngot;

static void on_tel(void *ctx, const mm_tel_t *t)
{
    (void)ctx;
    if (ngot < 16)
        got[ngot] = *t;
    ngot++;
}

static void test_decode(void)
{
    mm_t m;
    uint8_t b[32];
    printf("most_msg:\n");
    mm_init(&m);
    ngot = 0;
    const uint8_t conn[] = {1, 0, 8, 9, 10, 11};
    block(b, AMP, HU, 0x22, 0x01, 0x111, MM_OP_STARTRESULT, 0, conn, 6);
    mm_block(&m, b, 1000, on_tel, NULL);
    CHECK(ngot == 1 && got[0].target == AMP && got[0].source == HU && got[0].fblock == 0x22 &&
          got[0].inst == 1 && got[0].fkt == 0x111 && got[0].op == MM_OP_STARTRESULT && got[0].len == 6 &&
          memcmp(got[0].data, conn, 6) == 0, "single telegram fields");

    // refused: internal target, group source, TelLen 13, 12 bytes to a group
    // address, all-zero block; skipped: a system message, MOST High Protocol
    const int before = ngot;
    block(b, AMP, HU, 0x22, 1, 0x111, 0, 0, conn, 6); b[8] = 0x03; mm_block(&m, b, 1016, on_tel, NULL);
    block(b, 0x0005, HU, 0x22, 1, 0x111, 0, 0, conn, 6); mm_block(&m, b, 1032, on_tel, NULL);
    block(b, AMP, 0x0322, 0x22, 1, 0x111, 0, 0, conn, 6); mm_block(&m, b, 1048, on_tel, NULL);
    block(b, AMP, HU, 0x22, 1, 0x111, 0, 0, conn, 6); b[13] = 0x0D; mm_block(&m, b, 1064, on_tel, NULL);
    uint8_t twelve[12] = {1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12};
    block(b, 0x0322, HU, 0x22, 1, 0x400, 0, 0, twelve, 12); mm_block(&m, b, 1080, on_tel, NULL);
    memset(b, 0, 32); mm_block(&m, b, 1096, on_tel, NULL);
    const uint32_t rej = m.rejected;
    block(b, AMP, HU, 0x22, 1, 0x111, 0, 8, conn, 6); mm_block(&m, b, 1112, on_tel, NULL);
    // the system message is skipped, not refused: it is ordinary traffic
    CHECK(ngot == before && rej == 5 && m.rejected == 5, "refused %u (want 5), passed %d", (unsigned)rej, ngot - before);
    block(b, 0x0322, HU, 0x22, 1, 0x400, 0, 0, twelve, 11); mm_block(&m, b, 1128, on_tel, NULL);
    CHECK(ngot == before + 1 && got[ngot - 1].len == 11, "11 bytes to a group address pass");

    // segmented: 1 + 2 + 3, with the middle one sent twice (a retransmission)
    uint8_t s1[12] = {0x00}, s2[12] = {0x01}, s3[6] = {0x02};
    for (int i = 1; i < 12; i++) { s1[i] = (uint8_t)(0x10 + i); s2[i] = (uint8_t)(0x20 + i); }
    for (int i = 1; i < 6; i++) s3[i] = (uint8_t)(0x30 + i);
    ngot = 0;
    block(b, HU, AUX, 0x24, 1, 0x104, MM_OP_STATUS, 1, s1, 12); mm_block(&m, b, 2000, on_tel, NULL);
    block(b, HU, AUX, 0x24, 1, 0x104, MM_OP_STATUS, 2, s2, 12); mm_block(&m, b, 2016, on_tel, NULL);
    block(b, HU, AUX, 0x24, 1, 0x104, MM_OP_STATUS, 2, s2, 12); mm_block(&m, b, 2032, on_tel, NULL);
    block(b, HU, AUX, 0x24, 1, 0x104, MM_OP_STATUS, 3, s3, 6); mm_block(&m, b, 2048, on_tel, NULL);
    CHECK(ngot == 1 && got[0].segmented && got[0].len == 27 && got[0].data[0] == 0x11 &&
          got[0].data[11] == 0x21 && got[0].data[22] == 0x31 && got[0].data[26] == 0x35,
          "segmented, with a repeated segment: %d telegrams, len %d", ngot, ngot ? got[0].len : 0);

    // a lost middle segment: nothing comes out
    ngot = 0;
    const uint32_t dropped = m.seg_dropped;
    uint8_t s2b[12] = {0x02};
    block(b, HU, AUX, 0x24, 1, 0x104, MM_OP_STATUS, 1, s1, 12); mm_block(&m, b, 3000, on_tel, NULL);
    block(b, HU, AUX, 0x24, 1, 0x104, MM_OP_STATUS, 2, s2b, 12); mm_block(&m, b, 3016, on_tel, NULL);
    block(b, HU, AUX, 0x24, 1, 0x104, MM_OP_STATUS, 3, s3, 6); mm_block(&m, b, 3032, on_tel, NULL);
    CHECK(ngot == 0 && m.seg_dropped > dropped, "a gap in MsgCnt drops the transfer");

    // left open too long
    uint8_t s3b[6] = {0x01, 1, 2, 3, 4, 5};
    block(b, HU, AUX, 0x24, 1, 0x104, MM_OP_STATUS, 1, s1, 12); mm_block(&m, b, 4000, on_tel, NULL);
    block(b, HU, AMP, 0x22, 1, 0x113, MM_OP_STATUS, 0, conn, 2); mm_block(&m, b, 4000 + 300000, on_tel, NULL);
    ngot = 0;
    block(b, HU, AUX, 0x24, 1, 0x104, MM_OP_STATUS, 3, s3b, 6); mm_block(&m, b, 4000 + 300016, on_tel, NULL);
    CHECK(ngot == 0, "a transfer older than 5 s is dropped");

    // two senders interleaved
    ngot = 0;
    block(b, HU, AUX, 0x24, 1, 0x104, MM_OP_STATUS, 1, s1, 12); mm_block(&m, b, 5000, on_tel, NULL);
    block(b, HU, AMP, 0x22, 1, 0x114, MM_OP_STATUS, 1, s1, 12); mm_block(&m, b, 5016, on_tel, NULL);
    block(b, HU, AUX, 0x24, 1, 0x104, MM_OP_STATUS, 3, s3b, 6); mm_block(&m, b, 5032, on_tel, NULL);
    block(b, HU, AMP, 0x22, 1, 0x114, MM_OP_STATUS, 3, s3b, 6); mm_block(&m, b, 5048, on_tel, NULL);
    CHECK(ngot == 2 && got[0].fblock == 0x24 && got[1].fblock == 0x22 && got[0].len == 16 && got[1].len == 16,
          "interleaved transfers: %d", ngot);
    printf("  blocks %u, telegrams %u, refused %u, segments dropped %u\n", (unsigned)m.blocks,
           (unsigned)m.telegrams, (unsigned)m.rejected, (unsigned)m.seg_dropped);
}

// ------------------------------------------------------------ amp_model
static mm_tel_t tel(uint16_t src, uint16_t tgt, uint8_t fb, uint16_t fkt, uint8_t op, const uint8_t *d, int n)
{
    mm_tel_t t;
    memset(&t, 0, sizeof t);
    t.source = src; t.target = tgt; t.fblock = fb; t.inst = 1; t.fkt = fkt; t.op = op; t.len = (uint8_t)n;
    memcpy(t.data, d, (size_t)n);
    return t;
}

#define FEED(a, ...) do { mm_tel_t _t = tel(__VA_ARGS__); am_tel(a, &_t); } while (0)

static int pos_is(am_pos_t p, int bits, int l0, int l1, int r0, int r1)
{
    return p.bits == bits && p.l[0] == l0 && p.l[1] == l1 && p.r[0] == r0 && p.r[1] == r1;
}

static void test_model(void)
{
    am_t a;
    printf("amp_model:\n");
    const uint8_t src1[] = {1}, alloc[] = {1, 0, 8, 9, 10, 11}, conn[] = {1, 0, 8, 9, 10, 11}, sink1[] = {1};
    // the head unit puts AUX on the amp: Allocate, its Result, Connect, its Result
    am_init(&a);
    FEED(&a, HU, AUX, 0x24, 0x101, MM_OP_STARTRESULT, src1, 1);
    FEED(&a, AUX, HU, 0x24, 0x101, MM_OP_RESULT, alloc, 6);
    CHECK(am_aux_playing(&a).bits == 0, "allocated but not connected yet: off");
    FEED(&a, HU, AMP, 0x22, 0x111, MM_OP_STARTRESULT, conn, 6);
    CHECK(am_aux_playing(&a).bits == 0, "Connect asked, not confirmed: off");
    FEED(&a, AMP, HU, 0x22, 0x111, MM_OP_RESULT, sink1, 1);
    am_pos_t p = am_aux_playing(&a);
    printf("  AUX on channels 8-11: 16 bit, L %d %d, R %d %d\n", p.l[0], p.l[1], p.r[0], p.r[1]);
    CHECK(pos_is(p, 16, 9, 10, 11, 12), "AUX playing at frame bytes 9..12");
    CHECK(pos_is(am_main(&a), 16, 9, 10, 11, 12), "main zone follows sink 1");
    // repeats change nothing
    mm_tel_t t = tel(AMP, HU, 0x22, 0x111, MM_OP_RESULT, sink1, 1);
    CHECK(am_tel(&a, &t) == 0 && am_tel(&a, &t) == 0, "a repeated Result is no change");
    // DisConnect: off at once
    FEED(&a, HU, AMP, 0x22, 0x112, MM_OP_STARTRESULT, sink1, 1);
    CHECK(am_aux_playing(&a).bits == 0 && am_main(&a).bits == 0, "DisConnect asked: off");
    // back, then DeAllocate: off at once
    FEED(&a, HU, AMP, 0x22, 0x111, MM_OP_STARTRESULT, conn, 6);
    FEED(&a, AMP, HU, 0x22, 0x111, MM_OP_RESULT, sink1, 1);
    CHECK(am_aux_playing(&a).bits == 16, "connected again");
    FEED(&a, HU, AUX, 0x24, 0x102, MM_OP_STARTRESULT, src1, 1);
    CHECK(am_aux_playing(&a).bits == 0 && am_main(&a).bits == 16, "DeAllocate asked: AUX off, amp still on its channels");

    // the amp moves to another source (a CD changer at 12..15) while AUX stays allocated
    am_init(&a);
    FEED(&a, AUX, HU, 0x24, 0x101, MM_OP_RESULT, alloc, 6);
    FEED(&a, HU, AMP, 0x22, 0x111, MM_OP_STARTRESULT, conn, 6);
    FEED(&a, AMP, HU, 0x22, 0x111, MM_OP_RESULT, sink1, 1);
    const uint8_t cd[] = {1, 0, 12, 13, 14, 15};
    FEED(&a, HU, AMP, 0x22, 0x111, MM_OP_STARTRESULT, cd, 6);
    CHECK(am_aux_playing(&a).bits == 0, "Connect to other channels: AUX off before the Result");
    FEED(&a, AMP, HU, 0x22, 0x111, MM_OP_RESULT, sink1, 1);
    CHECK(am_aux_playing(&a).bits == 0 && pos_is(am_main(&a), 16, 13, 14, 15, 16), "main zone on the CD");

    // Ack forms: SenderHandle first
    am_init(&a);
    const uint8_t alloc_ack[] = {0x12, 0x34, 1, 0, 30, 31, 32, 33}, conn_ack[] = {0x56, 0x78, 1, 0, 30, 31, 32, 33},
                  res_ack[] = {0x56, 0x78, 1};
    FEED(&a, AUX, HU, 0x24, 0x101, MM_OP_RESULTACK, alloc_ack, 8);
    FEED(&a, HU, AMP, 0x22, 0x111, MM_OP_STARTRESULTACK, conn_ack, 8);
    FEED(&a, AMP, HU, 0x22, 0x111, MM_OP_RESULTACK, res_ack, 3);
    CHECK(pos_is(am_aux_playing(&a), 16, 31, 32, 33, 34), "Ack forms");

    // after a reboot, from the Info properties alone
    am_init(&a);
    const uint8_t sinfo[] = {1, 0x00, 2, 2, 0, 8, 9, 10, 11}, kinfo[] = {1, 0x00, 2, 2, 0, 8, 9, 10, 11};
    FEED(&a, AUX, HU, 0x24, 0x100, MM_OP_STATUS, sinfo, 9);
    FEED(&a, AMP, HU, 0x22, 0x110, MM_OP_STATUS, kinfo, 9);
    CHECK(pos_is(am_aux_playing(&a), 16, 9, 10, 11, 12), "SourceInfo + SinkInfo");
    const uint8_t kinfo_off[] = {1, 0x00, 2, 2, 0, 0xFF, 0xFF, 0xFF, 0xFF};
    FEED(&a, AMP, HU, 0x22, 0x110, MM_OP_STATUS, kinfo_off, 9);
    CHECK(am_aux_playing(&a).bits == 0, "SinkInfo with 0xFF channels: not connected");

    // lists that make no sense are ignored
    am_init(&a);
    const uint8_t bad1[] = {1, 0, 9, 8, 10, 11}, bad2[] = {1, 0, 58, 59, 60, 61};
    FEED(&a, AUX, HU, 0x24, 0x101, MM_OP_RESULT, bad1, 6);
    FEED(&a, AUX, HU, 0x24, 0x101, MM_OP_RESULT, bad2, 6);
    CHECK(a.src[0].ch.n == 0, "unordered or out-of-range channel lists are refused");

    // 24 bit: 6 channels
    am_init(&a);
    const uint8_t a24[] = {1, 0, 20, 21, 22, 23, 24, 25}, c24[] = {1, 0, 20, 21, 22, 23, 24, 25};
    FEED(&a, AUX, HU, 0x24, 0x101, MM_OP_RESULT, a24, 8);
    FEED(&a, HU, AMP, 0x22, 0x111, MM_OP_STARTRESULT, c24, 8);
    FEED(&a, AMP, HU, 0x22, 0x111, MM_OP_RESULT, sink1, 1);
    p = am_aux_playing(&a);
    CHECK(p.bits == 24 && p.l[0] == 21 && p.l[2] == 23 && p.r[0] == 24 && p.r[2] == 26, "24 bit");

    // Mute: SinkNr 0 means all sinks
    const uint8_t mute_all[] = {0, 1}, unmute1[] = {1, 0};
    FEED(&a, AMP, HU, 0x22, 0x113, MM_OP_STATUS, mute_all, 2);
    CHECK(a.sink[0].muted == 1 && am_main_muted(&a), "Mute all: the main zone muted");
    FEED(&a, AMP, HU, 0x22, 0x113, MM_OP_STATUS, unmute1, 2);
    CHECK(a.sink[0].muted == 0 && !am_main_muted(&a), "unmute sink 1");
}

// the amplifier's other sinks, as J3's streams 1..3 take them
static void connect(am_t *a, uint8_t inst, const uint8_t *d, int n)
{
    mm_tel_t t = tel(HU, AMP, 0x22, 0x111, MM_OP_STARTRESULT, d, n);
    t.inst = inst;
    am_tel(a, &t);
    t = tel(AMP, HU, 0x22, 0x111, MM_OP_RESULT, d, 1);
    t.inst = inst;
    am_tel(a, &t);
}

static void test_extras(void)
{
    am_t a;
    am_sink_t ex[2], ex3[3];
    printf("amp_model, other sinks:\n");
    am_init(&a);
    CHECK(am_extras(&a, ex, 2) == 0 && ex[0].pos.bits == 0 && ex[1].pos.bits == 0, "none connected");
    const uint8_t s1[] = {1, 0, 8, 9, 10, 11}, s3[] = {3, 0, 20, 21, 22, 23, 24, 25}, s2[] = {2, 0, 30, 31},
                  s4[] = {4, 0, 40, 41, 42, 43}, s5[] = {5, 0, 50, 51, 52, 53, 54};
    connect(&a, 1, s1, 6);
    connect(&a, 1, s3, 8);
    connect(&a, 1, s2, 4);
    CHECK(am_extras(&a, ex, 2) == 2, "two found");
    CHECK(ex[0].nr == 2 && ex[0].mono && ex[0].pos.bits == 16 && ex[0].pos.l[0] == 31 && ex[0].pos.l[1] == 32,
          "stream 1: sink 2, 16-bit mono at bytes 31, 32");
    CHECK(ex[1].nr == 3 && !ex[1].mono && ex[1].pos.bits == 24 && ex[1].pos.l[0] == 21 && ex[1].pos.r[2] == 26,
          "stream 2: sink 3, 24-bit stereo at 21..26");
    connect(&a, 1, s4, 6);
    CHECK(am_extras(&a, ex3, 3) == 3 && ex3[0].nr == 2 && ex3[1].nr == 3 && ex3[2].nr == 4 && !ex3[2].mono &&
          ex3[2].pos.bits == 16 && ex3[2].pos.l[0] == 41 && ex3[2].pos.l[1] == 42 && ex3[2].pos.r[0] == 43 &&
          ex3[2].pos.r[1] == 44, "three asked: sinks 2, 3, 4; stream 3 16-bit stereo at 41, 42 / 43, 44");
    const uint8_t s2b[] = {2, 0, 36, 37, 38};
    connect(&a, 2, s2b, 5);                          // another amplifier instance
    am_extras(&a, ex, 2);
    CHECK(ex[0].nr == 2 && ex[1].nr == 3 && ex[0].pos.l[0] == 31, "the lowest two SinkNr on sink 1's instance");
    CHECK(am_extras(&a, ex3, 3) == 3 && ex3[0].nr == 2 && ex3[0].pos.l[0] == 31 && ex3[1].nr == 3 &&
          ex3[2].nr == 4, "...and the lowest three");
    const uint8_t mute3[] = {3, 1};
    FEED(&a, HU, AMP, 0x22, 0x113, MM_OP_SETGET, mute3, 2);
    am_extras(&a, ex, 2);
    CHECK(!ex[0].muted && ex[1].muted, "sink 3 muted");
    const uint8_t dis2[] = {2};
    FEED(&a, HU, AMP, 0x22, 0x112, MM_OP_STARTRESULT, dis2, 1);
    am_extras(&a, ex, 2);
    CHECK(ex[0].nr == 3 && ex[1].nr == 4 && ex[1].pos.bits == 16 && !ex[1].mono, "sink 2 disconnected: 3 and 4");
    CHECK(am_extras(&a, ex3, 3) == 2 && ex3[0].nr == 3 && ex3[1].nr == 4 && ex3[2].pos.bits == 0 && !ex3[2].nr,
          "three asked, two left: the third cleared");
    const uint8_t s2x[] = {2, 0, 30, 31, 32, 33, 34};
    connect(&a, 1, s2x, 7);                          // sink 2 back with five channels
    CHECK(am_extras(&a, ex, 2) == 2 && ex[0].nr == 3 && ex[1].nr == 4, "a list J3 cannot take is passed over");
    connect(&a, 1, s5, 7);                           // five channels: no format J3 knows
    const uint8_t dis4[] = {4};
    FEED(&a, HU, AMP, 0x22, 0x112, MM_OP_STARTRESULT, dis4, 1);
    CHECK(am_extras(&a, ex, 2) == 1 && ex[0].nr == 3 && ex[1].pos.bits == 0, "sink 5's list skipped, the rest cleared");
    const uint8_t dis1[] = {1};
    FEED(&a, HU, AMP, 0x22, 0x112, MM_OP_STARTRESULT, dis1, 1);
    CHECK(am_extras(&a, ex, 2) == 1 && ex[0].nr == 3, "no main sink: the lowest instance that has one");
    FEED(&a, HU, AMP, 0x22, 0x112, MM_OP_STARTRESULT, (const uint8_t[]){3}, 1);
    CHECK(am_extras(&a, ex, 2) == 1 && ex[0].nr == 2 && ex[0].mono && ex[0].pos.bits == 24,
          "only the other instance's sink 2 left: 24-bit mono");

    // Jaguar Land Rover's layout: 1 main, 2 navigation and phone, 3 parking sensors, 4 chimes
    am_init(&a);
    const uint8_t j1[] = {1, 0, 8, 9, 10, 11}, j2[] = {2, 0, 20, 21}, j3[] = {3, 0, 24, 25}, j4[] = {4, 0, 26, 27};
    connect(&a, 1, j1, 6);
    connect(&a, 1, j2, 4);
    connect(&a, 1, j3, 4);
    connect(&a, 1, j4, 4);
    CHECK(am_extras(&a, ex3, 3) == 3 && ex3[0].nr == 2 && ex3[1].nr == 3 && ex3[2].nr == 4,
          "JLR: sinks 2, 3, 4 on streams 1, 2, 3");
    CHECK(ex3[0].mono && ex3[0].pos.bits == 16 && ex3[0].pos.l[0] == 21 && ex3[0].pos.l[1] == 22 &&
          ex3[1].mono && ex3[1].pos.bits == 16 && ex3[1].pos.l[0] == 25 && ex3[1].pos.l[1] == 26 &&
          ex3[2].mono && ex3[2].pos.bits == 16 && ex3[2].pos.l[0] == 27 && ex3[2].pos.l[1] == 28,
          "JLR: each 16-bit mono, at 21, 22 / 25, 26 / 27, 28");
    const uint8_t mute4[] = {4, 1}, unmute4[] = {4, 0};
    FEED(&a, HU, AMP, 0x22, 0x113, MM_OP_SETGET, mute4, 2);
    am_extras(&a, ex3, 3);
    CHECK(!ex3[0].muted && !ex3[1].muted && ex3[2].muted && !am_main_muted(&a), "Mute to sink 4: the chimes alone");
    FEED(&a, HU, AMP, 0x22, 0x113, MM_OP_SETGET, unmute4, 2);
    const uint8_t mute0[] = {0, 1}, unmute0[] = {0, 0};
    FEED(&a, HU, AMP, 0x22, 0x113, MM_OP_SETGET, mute0, 2);
    am_extras(&a, ex3, 3);
    CHECK(ex3[0].muted && ex3[1].muted && ex3[2].muted && am_main_muted(&a), "Mute to sink 0: all four");
    FEED(&a, HU, AMP, 0x22, 0x113, MM_OP_SETGET, unmute0, 2);
    am_extras(&a, ex3, 3);
    CHECK(!ex3[0].muted && !ex3[1].muted && !ex3[2].muted && !am_main_muted(&a), "...and unmuted");
    const uint8_t jdis2[] = {2};
    FEED(&a, HU, AMP, 0x22, 0x112, MM_OP_STARTRESULT, jdis2, 1);
    CHECK(am_extras(&a, ex3, 3) == 2 && ex3[0].nr == 3 && ex3[0].pos.l[0] == 25 && ex3[1].nr == 4 &&
          ex3[1].pos.l[0] == 27 && ex3[2].pos.bits == 0 && !ex3[2].nr,
          "JLR, sink 2 disconnected: 3 and 4 move up to streams 1, 2 (their levels go by SinkNr)");
}

// the whole chain, blocks in, decisions out
static am_t chain_am;
static void chain_tel(void *ctx, const mm_tel_t *t)
{
    (void)ctx;
    am_tel(&chain_am, t);
}

static void test_chain(void)
{
    mm_t m;
    uint8_t b[32];
    const uint8_t alloc[] = {1, 0, 8, 9, 10, 11}, conn[] = {1, 0, 8, 9, 10, 11}, sink1[] = {1};
    printf("chain:\n");
    mm_init(&m);
    am_init(&chain_am);
    block(b, AUX, HU, 0x24, 1, 0x101, MM_OP_STARTRESULT, 0, sink1, 1); mm_block(&m, b, 100, chain_tel, NULL);
    block(b, HU, AUX, 0x24, 1, 0x101, MM_OP_RESULT, 0, alloc, 6);      mm_block(&m, b, 116, chain_tel, NULL);
    block(b, AMP, HU, 0x22, 1, 0x111, MM_OP_STARTRESULT, 0, conn, 6);  mm_block(&m, b, 132, chain_tel, NULL);
    block(b, AMP, HU, 0x22, 1, 0x111, MM_OP_STARTRESULT, 0, conn, 6);  mm_block(&m, b, 148, chain_tel, NULL);
    block(b, HU, AMP, 0x22, 1, 0x111, MM_OP_RESULT, 0, sink1, 1);      mm_block(&m, b, 164, chain_tel, NULL);
    CHECK(pos_is(am_aux_playing(&chain_am), 16, 9, 10, 11, 12), "blocks -> telegrams -> AUX at 9..12");
}

// our source, read every 10 ms as the host's loop does: us of readings, the last one's pick
static int ain_for(ain_t *a, int64_t *t, int64_t us, int streaming, int err, int npcm)
{
    int src = AIN_NONE;
    for (const int64_t end = *t + us; *t < end; *t += 10000)
        src = ain_pick(a, streaming, err, npcm, *t);
    return src;
}

static void test_ain(void)
{
    ain_t a;
    int64_t t = 0;
    printf("audio in:\n");
    ain_init(&a);
    CHECK(ain_for(&a, &t, 3000000, 0, 1, 1) == AIN_NONE, "no receiver (ERROR, AUDIO pulled up), the phone idle: none");
    CHECK(ain_for(&a, &t, 100000, 1, 1, 1) == AIN_PHONE, "the phone streams");
    // the TOSLINK input locks at 3.1 s, while the phone plays; its lock time runs meanwhile
    CHECK(ain_for(&a, &t, 900000, 1, 0, 0) == AIN_PHONE && !a.locked, "0.9 s of lock: not settled yet");
    CHECK(ain_for(&a, &t, 200000, 1, 0, 0) == AIN_PHONE && a.locked, "settled; the phone still wins");
    CHECK(ain_pick(&a, 0, 0, 0, t) == AIN_TOSLINK, "the phone stops: the TOSLINK input at once");
    t += 10000;
    CHECK(ain_for(&a, &t, 1000000, 0, 0, 0) == AIN_TOSLINK, "and it stays");
    // a parity error: ERROR high for a moment
    CHECK(ain_pick(&a, 0, 1, 0, t) == AIN_TOSLINK, "a parity error's blip: kept");
    t += 10000;
    CHECK(ain_for(&a, &t, 80000, 0, 1, 0) == AIN_TOSLINK, "90 ms of ERROR: kept (the receiver sends zeros)");
    CHECK(ain_for(&a, &t, 50000, 0, 0, 0) == AIN_TOSLINK, "lock back within 100 ms: no new settle time");
    // the source turns to AC-3: still locked, AUDIO high
    CHECK(ain_pick(&a, 0, 0, 1, t) == AIN_NONE && a.npcm, "not PCM: dropped at the first reading");
    t += 10000;
    CHECK(ain_for(&a, &t, 3000000, 0, 0, 1) == AIN_NONE, "and kept off while it lasts");
    CHECK(ain_for(&a, &t, 990000, 0, 0, 0) == AIN_NONE && !a.npcm, "PCM again: not before 1 s");
    CHECK(ain_for(&a, &t, 20000, 0, 0, 0) == AIN_TOSLINK, "then the TOSLINK input");
    CHECK(ain_for(&a, &t, 100000, 1, 0, 1) == AIN_PHONE, "not PCM does not touch the phone");
    CHECK(ain_for(&a, &t, 1500000, 1, 0, 0) == AIN_PHONE && a.locked, "PCM, settled under the phone");
    // unplugged
    CHECK(ain_for(&a, &t, 90000, 0, 1, 0) == AIN_TOSLINK, "ERROR for 90 ms: still kept");
    CHECK(ain_for(&a, &t, 20000, 0, 1, 0) == AIN_NONE && !a.locked, "ERROR for 100 ms: lost, the car's AUX passes");
    CHECK(ain_for(&a, &t, 990000, 0, 0, 0) == AIN_NONE, "plugged in again: not before 1 s of lock");
    CHECK(ain_for(&a, &t, 20000, 0, 0, 0) == AIN_TOSLINK, "then the TOSLINK input");
    CHECK(ain_for(&a, &t, 100000, 1, 0, 0) == AIN_PHONE, "the phone takes over again");
}

// ------------------------------------------------------------ wheel
#define GW    0x0161            // Jaguar XF: the gateway
#define SCRN  0x016E            // ...and the touchscreen it sends the keys to

static mm_tel_t key_tel(uint16_t fkt, const uint8_t *d, int n, uint32_t frame)
{
    mm_tel_t t = tel(GW, SCRN, 0x10, fkt, MM_OP_STATUS, d, n);
    t.frame = frame;
    return t;
}

static void test_wheel(void)
{
    wheel_t w;
    printf("wheel:\n");
    wheel_init(&w);
    const uint8_t next[] = {0x03, 0x01, 0x00}, prev[] = {0x04, 0x00, 0x01}, rel[] = {0x03, 0x00, 0x00},
                  prev_b1[] = {0x04, 0x01, 0x00};
    mm_tel_t t = key_tel(0xCA1, next, 3, 1000);
    CHECK(wheel_tel(&w, &t) == WHEEL_NEXT, "03 01: next track");
    t.frame = 1100;
    CHECK(wheel_tel(&w, &t) == WHEEL_NONE, "the same telegram 2 ms later (a NAKed one sent again): once");
    t.frame = 1100 + WHEEL_SAME_FRAMES - 1;
    CHECK(wheel_tel(&w, &t) == WHEEL_NONE, "again within 200 ms of the last one: still once");
    t.frame += WHEEL_SAME_FRAMES;
    CHECK(wheel_tel(&w, &t) == WHEEL_NEXT, "200 ms of quiet, then the same: a new press");
    t = key_tel(0xCA1, rel, 3, t.frame + 500);
    CHECK(wheel_tel(&w, &t) == WHEEL_NONE, "03 00: no key");
    t = key_tel(0xCA1, next, 3, t.frame + 500);
    CHECK(wheel_tel(&w, &t) == WHEEL_NEXT, "after another 0xCA1 telegram a press counts at once");
    t = key_tel(0xCA1, prev, 3, t.frame + 500);
    CHECK(wheel_tel(&w, &t) == WHEEL_PREV, "04 .. 01: previous track");
    t = key_tel(0xCA1, prev_b1, 3, t.frame + 20000);
    CHECK(wheel_tel(&w, &t) == WHEEL_NONE, "04 01 00: not the layout seen on the car, no key");
    t = key_tel(0xCA0, next, 3, t.frame + 20000);
    CHECK(wheel_tel(&w, &t) == WHEEL_NONE, "another FktID: no key");
    t = key_tel(0xCA1, next, 3, t.frame + 20000);
    t.len = 1;                                      // 03, and 01 lying beyond the length
    CHECK(wheel_tel(&w, &t) == WHEEL_NONE, "one byte only: no key");
    t = key_tel(0xCA1, next, 3, 0xFFFFFF00u);
    CHECK(wheel_tel(&w, &t) == WHEEL_NEXT, "by the frame counter's wrap: a press");
    t.frame = 0x00000010u;
    CHECK(wheel_tel(&w, &t) == WHEEL_NONE, "the same across the wrap, 6 ms later: once");
    // from the wire: a block from the gateway to the screen
    mm_t m;
    uint8_t b[32];
    mm_init(&m);
    wheel_init(&w);
    ngot = 0;
    block(b, SCRN, GW, 0x10, 0x01, 0xCA1, MM_OP_STATUS, 0, next, 3);
    mm_block(&m, b, 5000, on_tel, NULL);
    CHECK(ngot == 1 && wheel_tel(&w, &got[0]) == WHEEL_NEXT, "a block 0161 > 016E 10.01.CA1 03 01 00: next track");
    mm_block(&m, b, 5020, on_tel, NULL);
    CHECK(ngot == 2 && wheel_tel(&w, &got[1]) == WHEEL_NONE, "the block sent again: no second key");
}

// The orders of telegrams a critical audit (2026-10-03, R04 R07 R08 R09) showed the
// model getting wrong: each must now come out as the amplifier itself sees it.
static mm_tel_t tel_i(uint16_t src, uint16_t tgt, uint8_t inst, uint16_t fkt, uint8_t op, const uint8_t *d, int n)
{
    mm_tel_t t = tel(src, tgt, 0x22, fkt, op, d, n);
    t.inst = inst;
    return t;
}

#define FEED_I(a, ...) do { mm_tel_t _t = tel_i(__VA_ARGS__); am_tel(a, &_t); } while (0)

static void test_audit(void)
{
    am_t a;
    printf("amp_model, the audit's orders:\n");
    const uint8_t conn[] = {1, 0, 8, 9, 10, 11}, sink1[] = {1}, mute_all[] = {0, 1}, mute1[] = {1, 1},
                  kinfo[] = {1, 0x00, 2, 2, 0, 8, 9, 10, 11};
    // R04: Mute to all sinks before any sink is known; the sink seen afterwards is muted
    am_init(&a);
    FEED_I(&a, AMP, HU, 1, 0x113, MM_OP_STATUS, mute_all, 2);
    FEED_I(&a, AMP, HU, 1, 0x110, MM_OP_STATUS, kinfo, 9);
    CHECK(pos_is(am_main(&a), 16, 9, 10, 11, 12) && am_main_muted(&a), "Mute(all) before SinkInfo: sink 1 muted");
    am_init(&a);
    FEED_I(&a, HU, AMP, 1, 0x113, MM_OP_SETGET, mute_all, 2);
    FEED_I(&a, HU, AMP, 1, 0x111, MM_OP_STARTRESULT, conn, 6);
    FEED_I(&a, AMP, HU, 1, 0x111, MM_OP_RESULT, sink1, 1);
    CHECK(am_main(&a).bits == 16 && am_main_muted(&a), "Mute(all) before Connect: sink 1 muted");
    const uint8_t unmute_all[] = {0, 0};
    FEED_I(&a, AMP, HU, 1, 0x113, MM_OP_STATUS, unmute_all, 2);
    CHECK(!am_main_muted(&a), "unmute all");

    // R07: a Connect to "any instance" (0), answered with the real one (1)
    am_init(&a);
    FEED_I(&a, HU, AMP, 0, 0x111, MM_OP_STARTRESULT, conn, 6);
    FEED_I(&a, AMP, HU, 1, 0x111, MM_OP_RESULT, sink1, 1);
    CHECK(pos_is(am_main(&a), 16, 9, 10, 11, 12), "Connect to InstID 0, Result from InstID 1: sink 1 at 9..12");
    // ...and once the amplifier has shown its instance, a wildcard request goes straight to it (0xFF as well)
    am_init(&a);
    const uint8_t kinfo2[] = {2, 0x00, 2, 1, 0, 20, 21};
    FEED_I(&a, AMP, HU, 1, 0x110, MM_OP_STATUS, kinfo2, 7);
    FEED_I(&a, HU, AMP, 0xFF, 0x111, MM_OP_STARTRESULT, conn, 6);
    FEED_I(&a, AMP, HU, 1, 0x111, MM_OP_RESULT, sink1, 1);
    CHECK(pos_is(am_main(&a), 16, 9, 10, 11, 12), "instance known, Connect to InstID 0xFF: sink 1 at 9..12");
    FEED_I(&a, HU, AMP, 0, 0x113, MM_OP_SETGET, mute1, 2);
    CHECK(am_main_muted(&a), "Mute to InstID 0 reaches the sink on instance 1");
    int n_inst1 = 0, n_inst0 = 0;
    for (int i = 0; i < AM_SINKS; i++) {
        n_inst1 += a.sink[i].used && a.sink[i].inst == 1;
        n_inst0 += a.sink[i].used && a.sink[i].inst == 0;
    }
    CHECK(n_inst0 == 0 && n_inst1 == 2, "no sink filed under instance 0 (%d), two under 1 (%d)", n_inst0, n_inst1);

    // R08: a Result that comes after the DisConnect brings nothing back
    am_init(&a);
    FEED_I(&a, HU, AMP, 1, 0x111, MM_OP_STARTRESULT, conn, 6);
    FEED_I(&a, AMP, HU, 1, 0x111, MM_OP_RESULT, sink1, 1);
    FEED_I(&a, HU, AMP, 1, 0x112, MM_OP_STARTRESULT, sink1, 1);
    FEED_I(&a, AMP, HU, 1, 0x111, MM_OP_RESULT, sink1, 1);
    CHECK(am_main(&a).bits == 0, "a late Connect.Result after DisConnect: still off");
    // the same with the DisConnect between StartResult and Result
    am_init(&a);
    FEED_I(&a, HU, AMP, 1, 0x111, MM_OP_STARTRESULT, conn, 6);
    FEED_I(&a, HU, AMP, 1, 0x112, MM_OP_STARTRESULT, sink1, 1);
    FEED_I(&a, AMP, HU, 1, 0x111, MM_OP_RESULT, sink1, 1);
    CHECK(am_main(&a).bits == 0, "DisConnect while the Connect was open: its Result changes nothing");
    // and an Error closes it too
    am_init(&a);
    const uint8_t err[] = {0x20, 1};
    FEED_I(&a, HU, AMP, 1, 0x111, MM_OP_STARTRESULT, conn, 6);
    FEED_I(&a, AMP, HU, 1, 0x111, MM_OP_ERROR, err, 2);
    FEED_I(&a, AMP, HU, 1, 0x111, MM_OP_RESULT, sink1, 1);
    CHECK(am_main(&a).bits == 0, "Connect turned down (Error): a Result after it changes nothing");

    // R09: formats J3 cannot take are refused, and void what was known
    am_init(&a);
    const uint8_t pcm8x4[] = {1, 0x00, 1, 4, 0, 8, 9, 10, 11}, mp2[] = {1, 0x21, 2, 2, 0, 8, 9, 10, 11},
                  short_l[] = {1, 0x00, 3, 2, 0, 8, 9, 10, 11};
    FEED_I(&a, AMP, HU, 1, 0x110, MM_OP_STATUS, pcm8x4, 9);
    CHECK(am_main(&a).bits == 0, "SinkInfo PCM 8 bit x 4 channels on 4 bytes: not taken for stereo 16");
    FEED_I(&a, AMP, HU, 1, 0x110, MM_OP_STATUS, kinfo, 9);
    CHECK(am_main(&a).bits == 16, "SinkInfo PCM 16 bit stereo: taken");
    FEED_I(&a, AMP, HU, 1, 0x110, MM_OP_STATUS, short_l, 9);
    CHECK(am_main(&a).bits == 0, "24 bit stereo on 4 bytes: refused, and the stereo known before is void");
    FEED_I(&a, AMP, HU, 1, 0x110, MM_OP_STATUS, kinfo, 9);
    FEED_I(&a, AMP, HU, 1, 0x110, MM_OP_STATUS, mp2, 9);
    CHECK(am_main(&a).bits == 0, "SinkInfo MPEG2: not PCM, the stereo known before is void");
    mm_tel_t t = tel(AUX, HU, 0x24, 0x100, MM_OP_STATUS, pcm8x4, 9);
    am_tel(&a, &t);
    CHECK(a.src[0].ch.n == 0, "SourceInfo PCM 8 bit x 4 channels: no channels taken for AUX");
}

int main(void)
{
    test_decode();
    test_model();
    test_audit();
    test_extras();
    test_chain();
    test_ain();
    test_wheel();
    printf(fails ? "\n%d FAILED\n" : "\nall passed\n", fails);
    return fails != 0;
}
