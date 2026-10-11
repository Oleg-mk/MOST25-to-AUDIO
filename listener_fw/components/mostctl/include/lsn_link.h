// lsn_link.h - the UART link to the listener's FPGA, both ways.
//
// In (listener_gw/rtl/ctrl_uart.v): one 42-byte packet per control block,
// 3 Mbaud 8N1:
//   0  A5, 1  5A        sync
//   2..5                frame counter of the block's first frame, little endian
//   6                   status: b0 locked, b1 block known, b6..b2 frames of the
//                       block with parity 1, b7 a packet was dropped before this one
//   7..8                UI estimate, Q8.8 samples, little endian
//   9..40               the 32 control bytes (frame bytes 61, 62 of frames 0..15)
//   41                  XOR of bytes 0..40
//
// Out (listener_gw/rtl/host_cmd.v): 11-byte commands
//   A5 5A C P0..P6 X    X = XOR of the 10 bytes before it
//   C = 01  a source for J3:     P  L0 L1 L2  R0 R1 R2  (P[1:0]: 0 off, 2 16-bit,
//                                3 24-bit; P[2] mono; P[5:4] stream 0..3)
//   C = 02  audio into the ring: M  L0 L1 L2  R0 R1 R2  (M[1:0] as W; M[2] the source:
//                                0 = M2's I2S, 1 = the board's S/PDIF input; M[7] keep bit 511)
//   C = 03  a coefficient word:  A  V3 V2 V1 V0  F  T   (address 0..63, Q4.28 MSB
//                                first, F = 1: commit after this word, T the set's
//                                tag: the same in every word of a set, another for
//                                the next; amp_out.v switches only on a whole set)
//   Lx/Rx are frame byte indices, most significant byte first; the FPGA takes
//   0..63 for 01 and only 1..60 for 02.
//   C = 04  capture (listener_gw/rtl/capture.v): M  0 0 0 0 0 0
//           M bit 0 capture anew, bit 1 dump what was captured, bit 2 (with
//           bit 0) dump as soon as the buffer is full
//
// Capture packets, on the same line as the control blocks, 41 bytes:
//   0  A5, 1  C5        sync
//   2..3                packet number n, little endian: runs 32 n .. 32 n + 31
//   4..35               32 run lengths in samples of 1.26 ns (255 = 255 or more)
//   36..39              their glitch flags, bit i of byte 36 + i / 8 for run i
//   40                  XOR of bytes 0..39
//   n = FFFF is the trailer: bytes 4..7 = the number of runs captured (LE).
#pragma once

#include <stddef.h>
#include <stdint.h>

#define LSN_PKT_LEN   42
#define LSN_CAP_LEN   41
#define LSN_CMD_LEN   11

#define LSN_CAP_ARM   0x01     // command 04: capture anew
#define LSN_CAP_DUMP  0x02     // dump what was captured
#define LSN_CAP_AUTO  0x04     // with ARM: dump as soon as the buffer is full

#define LSN_ST_LOCKED   0x01
#define LSN_ST_BLOCK    0x02
#define LSN_ST_DROPPED  0x80

typedef struct {
    uint32_t frame;          // frame counter at the block's first frame
    uint8_t status;
    uint16_t ui_q88;
    uint8_t ctl[32];         // the control block, in frame order
} lsn_block_t;

typedef void (*lsn_block_cb)(void *ctx, const lsn_block_t *b);

// A capture packet: seq, the 32 run lengths, their glitch flags (bit i = run i);
// for the trailer (seq 0xFFFF) `count` is the number of runs captured.
typedef void (*lsn_cap_cb)(void *ctx, uint16_t seq, const uint8_t lens[32], uint32_t glitch,
                           uint32_t count);

typedef struct {
    uint8_t buf[LSN_PKT_LEN];
    int n;
    int kind;                // after the second byte: 1 control (42 bytes), 2 capture (41)
    uint32_t good, bad;      // control packets passed / failed the XOR
    uint32_t cap_good, cap_bad;
    lsn_cap_cb cap_cb;       // NULL: capture packets are counted and dropped
} lsn_rx_t;

void lsn_rx_init(lsn_rx_t *r);

// Bytes as they come from the UART; cb for each packet whose XOR is right.
// After a bad packet the search for A5 5A restarts inside it, so a lost byte
// costs one block, not a run of them.
void lsn_rx_feed(lsn_rx_t *r, const uint8_t *p, size_t n, lsn_block_cb cb, void *ctx);

// Commands. bits: 0 (off), 16 or 24. l, r: the sample's frame bytes, MSB first
// (the third one unused at 16 bits; r unused when mono). lsn_cmd_source picks
// J3's stream 0..3, mono feeding l to both sides; lsn_cmd_stereo is stream 0
// in stereo. spdif_in: the samples come from the board's S/PDIF input (its
// ASRC on the FPGA's DIN2) instead of M2's I2S.
void lsn_cmd_source(uint8_t out[LSN_CMD_LEN], int stream, int bits, int mono, const uint8_t l[3],
                    const uint8_t r[3]);
void lsn_cmd_stereo(uint8_t out[LSN_CMD_LEN], int bits, const uint8_t l[3], const uint8_t r[3]);
void lsn_cmd_inject(uint8_t out[LSN_CMD_LEN], int bits, int keep_parity, int spdif_in,
                    const uint8_t l[3], const uint8_t r[3]);
void lsn_cmd_word(uint8_t out[LSN_CMD_LEN], uint8_t addr, int32_t value, int commit, uint8_t tag);
void lsn_cmd_capture(uint8_t out[LSN_CMD_LEN], uint8_t mode);       // LSN_CAP_* bits
