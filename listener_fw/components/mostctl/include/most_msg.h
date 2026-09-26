// most_msg.h - MOST25 control blocks -> application telegrams.
//
// Formats: docs/host_control_formats.md (MOST Spec 2.5 core, MOST
// Book 2, OS8104 data sheet; page references there).
//
// Block, 32 bytes: 0-3 arbitration, 4-5 target, 6-7 source (high byte first),
// 8 message type (0x00 normal), 9-25 data area, 26-27 CRC, 28-29 transmission
// status, 30-31 reserved. Data area: FBlockID, InstID, FktID[11:4],
// FktID[3:0]:OPType, TelID:TelLen, Data0..Data11.
//
// What cannot be checked: the CRC (its polynomial is in no document on
// disk), the wire form of the transmission status, what an idle block and
// the 2 administrative blocks in every 64 look like. So a block is taken as a
// telegram only if everything that can be checked holds (see most_msg.c),
// and whoever acts on a telegram also checks that its parameters make sense.
//
// Segmented messages: TelID 1 (MsgCnt 0), 2 (MsgCnt 1, 2, ... wrapping), 3;
// Data0 is the MsgCnt and TelLen counts it. A NAKed telegram is sent again
// (up to 6 times), so a repeated segment is skipped, not taken for a lost
// one. A transfer left open for 5 s is dropped (MOST Spec 2.5, T3-19).
#pragma once

#include <stdint.h>

#define MM_MAX_PAYLOAD  64      // plenty for everything the host acts on
#define MM_SLOTS        4       // segmented transfers in flight, keyed by source/target

typedef struct {
    uint32_t frame;             // frame counter of the block that completed it
    uint16_t target, source;
    uint8_t fblock, inst;
    uint16_t fkt;
    uint8_t op;
    uint8_t len;                // payload bytes (MsgCnt bytes not included)
    uint8_t segmented, truncated;
    uint8_t data[MM_MAX_PAYLOAD];
} mm_tel_t;

typedef void (*mm_tel_cb)(void *ctx, const mm_tel_t *t);

typedef struct {
    struct {
        uint8_t active;
        uint16_t source, target;
        uint8_t fblock, inst, op;
        uint16_t fkt;
        uint8_t next_cnt, last_cnt;
        uint32_t last_frame;
        uint8_t len, truncated;
        uint8_t data[MM_MAX_PAYLOAD];
    } slot[MM_SLOTS];
    uint32_t blocks, telegrams, rejected, seg_dropped;
} mm_t;

void mm_init(mm_t *m);

// One aligned control block; cb for each complete telegram.
void mm_block(mm_t *m, const uint8_t blk[32], uint32_t frame, mm_tel_cb cb, void *ctx);

// OPType codes (MOST Spec 2.5, Table 2-4); methods share the codes.
enum {
    MM_OP_SET = 0x0, MM_OP_GET = 0x1, MM_OP_SETGET = 0x2, MM_OP_INC = 0x3, MM_OP_DEC = 0x4,
    MM_OP_GETIF = 0x5, MM_OP_STARTRESULTACK = 0x6, MM_OP_ABORTACK = 0x7, MM_OP_STARTACK = 0x8,
    MM_OP_ERRORACK = 0x9, MM_OP_PROCESSINGACK = 0xA, MM_OP_PROCESSING = 0xB, MM_OP_STATUS = 0xC,
    MM_OP_RESULTACK = 0xD, MM_OP_INTERFACE = 0xE, MM_OP_ERROR = 0xF,
};
#define MM_OP_START        MM_OP_SET
#define MM_OP_STARTRESULT  MM_OP_SETGET
#define MM_OP_RESULT       MM_OP_STATUS
