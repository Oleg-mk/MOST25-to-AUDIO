// host.c - see host.h.
//
// UART2 at 3 Mbaud 8N1, as the FPGA's ctrl_uart / uart_rx:
//   IO4  <- UART_TX_F  control blocks (M2 pad 32)
//   IO15 -> R20 -> UART_RX_F  commands (M2 pad 35); IO15 is a strapping pin
//        (MTDO), and the FPGA's pull-up on UART_RX holds it high through reset
//
// Every control block: most_msg decodes it, amp_model and sound follow it.
// Three decisions come from them:
//   02  our audio into the AUX source's frame bytes - while an amplifier sink
//       is connected to them AND one of our sources is live: the phone while
//       it streams, otherwise the board's TOSLINK input once its S/PDIF
//       receiver holds lock on PCM (IO13 <- DIR9001 ERROR, M2 pad 15; IO27 <-
//       DIR9001 AUDIO, M2 pad 11; ain.h). Otherwise the car's own AUX passes
//       untouched: we take nothing away from the car.
//   01  J3 plays what the amplifier's sink 1 (the main zone) plays, and on
//       streams 1 and 2 two more of its sinks - navigation, phone, chimes,
//       whatever it mixes in (am_extras: connected, SinkNr 2 and up, lowest
//       first)...
//   03  ...with the head unit's volume, mute, balance, bass, treble and
//       loudness, and each other sink at its own level and mute: dsp_img
//       turns them into the FPGA's coefficient set, written word by word and
//       committed with the last (at most every 20 ms while the knob turns;
//       at once when a sink comes or goes). The settings are kept in NVS, so
//       after a restart J3 starts where it was, as the factory amplifier
//       does; until a volume has been heard once, J3 is silent.
// And the steering wheel's track keys (wheel.h, Jaguar XF: 0xCA1) go to the
// phone over AVRCP (phone_ctl) while the phone is what the car plays - our
// audio in the AUX bytes, from the phone; otherwise they are the car's alone.
// A command goes out when its decision changes, at start-up (an ESP32 reset
// must not leave the FPGA injecting), and again every 2 s: after a core reset
// the FPGA's injection is off until told, and a repeated command changes
// nothing there (inject.v takes the same settings at the next frame; the
// same coefficient set committed again is the set in use).
//
// The FPGA sends a packet only for a locked, aligned block. None for 0.5 s:
// the ring is down or restarting, and on a restart the channels are handed
// out anew - if the model kept the old ones, our audio could land in another
// source's bytes before the new Allocate is seen. So the model starts over
// and both commands go to off; the cost is no AUX audio until the car
// allocates and connects again, which it does when the ring comes up.
//
// Telegrams are traced to the console by a low-priority task through a
// queue; when the console falls behind, lines are dropped and counted, never
// the UART - 126 kB/s would fill the 8 KB receive buffer in 65 ms.
//
// Capture (listener_gw/rtl/capture.v): the FPGA keeps the line's first 65536
// runs after power-up, and captures anew or dumps on command 04. Keys on the
// console: 'c' captures now and dumps when full, 'd' dumps what was captured.
// The dump's packets are collected here (in PSRAM), and once the trailer has
// come the low-priority task prints them as text for tools/capture_analyse.py:
//   CAP BEGIN runs=<n> packets=<p> missing=<m>
//   CAP <packet> <64 hex digits: 32 run lengths> <8 hex digits: glitch flags>
//   CAP <packet> -                                   (a packet that never came)
//   CAP END
#include "host.h"

#include <stdio.h>
#include <string.h>

#include "ain.h"
#include "amp_model.h"
#include "audio_out.h"
#include "driver/uart.h"
#include "dsp_img.h"
#include "esp_heap_caps.h"
#include "esp_log.h"
#include "esp_timer.h"
#include "freertos/FreeRTOS.h"
#include "freertos/queue.h"
#include "freertos/task.h"
#include "driver/gpio.h"
#include "lsn_link.h"
#include "most_msg.h"
#include "nvs.h"
#include "phone_ctl.h"
#include "sound.h"
#include "wheel.h"

#define HOST_UART   UART_NUM_2
#define PIN_RX      4
#define PIN_TX      15
#define BAUD        3000000
#define RESEND_US   2000000
#define STALE_US    500000
#define STATUS_US   10000000
#define IMG_MIN_US  20000               // coefficient sets at most 50 a second
#define SAVE_US     10000000            // settings to flash 10 s after the last change
#define SND_MAGIC   0x534E4432u         // "SND2": the stored layout (per-sink levels)
#define CAP_RUNS    65536u              // the FPGA's capture buffer (CAP_AW 16)
#define PIN_OPT_ERR 13                  // DIR9001 ERROR (M2 pad 15): high = the S/PDIF input has no lock
#define PIN_OPT_NPCM 27                 // DIR9001 AUDIO (M2 pad 11, board v1.3): high = not PCM (AC-3, DTS)
#define CAP_PKTS    (CAP_RUNS / 32)

static const char *TAG = "host";

static lsn_rx_t s_rx;
static mm_t s_mm;
static am_t s_am;
static QueueHandle_t s_trace;
static uint32_t s_trace_lost;
static am_pos_t s_aux_sent, s_main_sent;
static am_sink_t s_ex_sent[2];                       // J3's streams 1, 2 as last sent
static dsp_extra_t s_dx[2];                          // ...and as the coefficient set has them
static int64_t s_last_locked;
static int s_stale = 1;
static volatile int s_streaming;
static ain_t s_ain;                                  // our source: the phone or the TOSLINK input
static int s_ain_sent = -1, s_src_seen = -1, s_opt_seen = -1;
static uint32_t s_fpga_dropped;
static snd_t s_snd;
static wheel_t s_wheel;
static int s_img_dirty = 1, s_muted_sent = -1;
static uint32_t s_fs_sent;
static int64_t s_img_sent, s_save_at;
static uint8_t *s_cap_len, *s_cap_gl, *s_cap_have;   // a dump: lengths, glitch flags, packet seen
static volatile uint32_t s_cap_count;                // the trailer's count: the dump is complete
static uint32_t s_cap_pkts, s_cap_dumps;

static int pos_eq(const am_pos_t *x, const am_pos_t *y)
{
    return x->bits == y->bits && !memcmp(x->l, y->l, 3) && !memcmp(x->r, y->r, 3);
}

static void log_pos(const char *what, const am_pos_t *p)
{
    if (p->bits)
        ESP_LOGI(TAG, "%s: %d bit, L bytes %d %d %d, R bytes %d %d %d", what, p->bits,
                 p->l[0], p->l[1], p->l[2], p->r[0], p->r[1], p->r[2]);
    else
        ESP_LOGI(TAG, "%s: off", what);
}

static int sink_eq(const am_sink_t *x, const am_sink_t *y)
{
    return pos_eq(&x->pos, &y->pos) && x->mono == y->mono && x->nr == y->nr;
}

static const char *src_name(int src)
{
    return src == AIN_PHONE ? "the phone" : src == AIN_TOSLINK ? "the TOSLINK input" : "none";
}

// the TOSLINK input's state: 0 no signal, 1 locked on PCM, 2 not PCM
static int opt_state(void)
{
    return s_ain.npcm ? 2 : s_ain.locked;
}

static const char *opt_name(int st)
{
    return st == 2 ? "not PCM (AC-3/DTS?): not used - set the source to PCM" : st ? "locked" : "no signal";
}

// ------------------------------------------------ the sound settings, kept
typedef struct {
    uint32_t magic;
    snd_t snd;
} snd_store_t;

static void snd_load(void)
{
    snd_init(&s_snd);
    nvs_handle_t h;
    if (nvs_open("sound", NVS_READONLY, &h) != ESP_OK)
        return;
    snd_store_t st;
    size_t n = sizeof st;
    if (nvs_get_blob(h, "state", &st, &n) == ESP_OK && n == sizeof st && st.magic == SND_MAGIC) {
        s_snd = st.snd;
        ESP_LOGI(TAG, "sound settings from flash: volume %.1f dB", snd_volume_db(&s_snd));
    }
    nvs_close(h);
}

static void snd_save(void)
{
    nvs_handle_t h;
    const snd_store_t st = {.magic = SND_MAGIC, .snd = s_snd};
    if (nvs_open("sound", NVS_READWRITE, &h) != ESP_OK)
        return;
    if (nvs_set_blob(h, "state", &st, sizeof st) != ESP_OK || nvs_commit(h) != ESP_OK)
        ESP_LOGW(TAG, "sound settings not saved");
    nvs_close(h);
}

// J3's coefficient set, word by word, committed with the last
static void send_image(void)
{
    int32_t w[DSP_C_IMAGE];
    const uint32_t fs = audio_out_ring_rate();
    const int muted = am_main_muted(&s_am);
    if (dsp_image(&s_snd, &snd_cfg_default, muted, s_dx, fs ? fs : 48000, w) != 0)
        ESP_LOGW(TAG, "a tone shelf would not be stable once rounded: left flat");
    uint8_t c[LSN_CMD_LEN];
    for (int a = 0; a < DSP_C_IMAGE; a++) {
        lsn_cmd_word(c, (uint8_t)a, w[a], a == DSP_C_IMAGE - 1);
        uart_write_bytes(HOST_UART, c, sizeof c);
    }
    if (s_img_dirty) {
        double gl, gr, bass, treble;
        dsp_levels(&s_snd, &snd_cfg_default, muted, &gl, &gr, &bass, &treble);
        ESP_LOGI(TAG, "J3: volume %.1f dB%s, L x %.4f, R x %.4f, bass %+.1f dB, treble %+.1f dB, %lu Hz",
                 snd_sink_db(&s_snd, &snd_cfg_default, 1), muted ? " (muted)" : "", gl, gr, bass, treble,
                 (unsigned long)fs);
        for (int k = 0; k < 2; k++)
            if (s_dx[k].sink) {
                dsp_extra_levels(&s_snd, &snd_cfg_default, &s_dx[k], &gl, &gr);
                ESP_LOGI(TAG, "J3 stream %d: sink %d at %.1f dB%s, L x %.4f, R x %.4f", k + 1, s_dx[k].sink,
                         snd_sink_db(&s_snd, &snd_cfg_default, s_dx[k].sink), s_dx[k].muted ? " (muted)" : "",
                         gl, gr);
            }
    }
    s_img_dirty = 0;
    s_muted_sent = muted;
    s_fs_sent = fs;
    s_img_sent = esp_timer_get_time();
}

// Commands for the current decisions: when they change, or all of them (force).
static void decide(int force)
{
    static const am_pos_t off = {0};
    // our source: the phone while it streams, otherwise the TOSLINK input once it holds lock on PCM
    const int src = ain_pick(&s_ain, s_streaming, gpio_get_level(PIN_OPT_ERR), gpio_get_level(PIN_OPT_NPCM),
                             esp_timer_get_time());
    if (opt_state() != s_opt_seen) {
        s_opt_seen = opt_state();
        ESP_LOGI(TAG, "TOSLINK in: %s", opt_name(s_opt_seen));
    }
    if (src != s_src_seen) {
        ESP_LOGI(TAG, "audio in: %s", src_name(src));
        s_src_seen = src;
    }
    const int spdif = src == AIN_TOSLINK;
    const am_pos_t aux = src != AIN_NONE ? am_aux_playing(&s_am) : off, main_zone = am_main(&s_am);
    // the amplifier's other sinks, J3's streams 1 and 2
    am_sink_t ex[2];
    am_extras(&s_am, ex, 2);
    dsp_extra_t dx[2];
    for (int k = 0; k < 2; k++) {
        dx[k].sink = ex[k].pos.bits ? ex[k].nr : 0;
        dx[k].muted = ex[k].muted;
    }
    const int ex_changed = memcmp(dx, s_dx, sizeof dx) != 0;
    if (ex_changed) {
        memcpy(s_dx, dx, sizeof dx);
        s_img_dirty = 1;
    }
    uint8_t c[LSN_CMD_LEN];
    if (am_main_muted(&s_am) != s_muted_sent || audio_out_ring_rate() != s_fs_sent)
        s_img_dirty = 1;
    // the set first: a source switched on is heard with its gains, never at full scale
    if (force || ex_changed || (s_img_dirty && esp_timer_get_time() - s_img_sent >= IMG_MIN_US))
        send_image();
    if (force || !pos_eq(&aux, &s_aux_sent) || spdif != s_ain_sent) {
        lsn_cmd_inject(c, aux.bits, 0, spdif, aux.l, aux.r);
        uart_write_bytes(HOST_UART, c, sizeof c);
        if (!pos_eq(&aux, &s_aux_sent))
            log_pos(!aux.bits ? "our audio into AUX" : spdif ? "the TOSLINK input into AUX"
                                                             : "the phone into AUX", &aux);
        s_aux_sent = aux;
        s_ain_sent = spdif;
    }
    if (force || !pos_eq(&main_zone, &s_main_sent)) {
        lsn_cmd_stereo(c, main_zone.bits, main_zone.l, main_zone.r);
        uart_write_bytes(HOST_UART, c, sizeof c);
        if (!pos_eq(&main_zone, &s_main_sent))
            log_pos("J3 stereo (amp sink 1)", &main_zone);
        s_main_sent = main_zone;
    }
    for (int k = 0; k < 2; k++)
        if (force || !sink_eq(&ex[k], &s_ex_sent[k])) {
            lsn_cmd_source(c, 1 + k, ex[k].pos.bits, ex[k].mono, ex[k].pos.l, ex[k].pos.r);
            uart_write_bytes(HOST_UART, c, sizeof c);
            if (!sink_eq(&ex[k], &s_ex_sent[k])) {
                char what[40];
                snprintf(what, sizeof what, "J3 stream %d (amp sink %d%s)", k + 1, ex[k].nr,
                         ex[k].mono ? ", mono" : "");
                log_pos(what, &ex[k].pos);
            }
            s_ex_sent[k] = ex[k];
        }
}

// A steering-wheel key: the phone's while its audio is in the AUX bytes (as
// last sent to the FPGA), else the car's alone.
static void wheel_key(int key)
{
    const char *what = key == WHEEL_NEXT ? "next track" : "previous track";
    if (s_aux_sent.bits && !s_ain_sent) {
        ESP_LOGI(TAG, "wheel: %s -> the phone", what);
        phone_ctl_key(key == WHEEL_NEXT);
    } else {
        ESP_LOGI(TAG, "wheel: %s, not ours (the phone is not in AUX)", what);
    }
}

static void on_tel(void *ctx, const mm_tel_t *t)
{
    (void)ctx;
    if (xQueueSend(s_trace, t, 0) != pdTRUE)
        s_trace_lost++;
    am_tel(&s_am, t);
    if (snd_tel(&s_snd, &snd_cfg_default, t)) {
        s_img_dirty = 1;
        s_save_at = esp_timer_get_time() + SAVE_US;
    }
    const int key = wheel_tel(&s_wheel, t);
    if (key)
        wheel_key(key);
}

static void on_block(void *ctx, const lsn_block_t *b)
{
    (void)ctx;
    if ((b->status & (LSN_ST_LOCKED | LSN_ST_BLOCK)) != (LSN_ST_LOCKED | LSN_ST_BLOCK))
        return;
    s_last_locked = esp_timer_get_time();
    s_stale = 0;
    if (b->status & LSN_ST_DROPPED)
        s_fpga_dropped++;
    mm_block(&s_mm, b->ctl, b->frame, on_tel, NULL);
}

// ------------------------------------------------ capture dumps
static void on_cap(void *ctx, uint16_t seq, const uint8_t lens[32], uint32_t glitch, uint32_t count)
{
    (void)ctx;
    if (seq == 0xFFFF) {
        s_cap_count = count ? count : 1;             // 1: an empty dump still prints its header
        return;
    }
    if (seq >= CAP_PKTS || s_cap_count)              // beyond the buffer, or a dump still being printed
        return;
    memcpy(&s_cap_len[32u * seq], lens, 32);
    for (int i = 0; i < 4; i++)
        s_cap_gl[4u * seq + (unsigned)i] = (uint8_t)(glitch >> (8 * i));
    s_cap_have[seq] = 1;
    s_cap_pkts++;
}

static void cap_print(void)
{
    const uint32_t n = s_cap_count == 1 ? 0 : s_cap_count, np = (n + 31) / 32;
    uint32_t missing = 0;
    for (uint32_t p = 0; p < np; p++)
        missing += !s_cap_have[p];
    printf("CAP BEGIN runs=%lu packets=%lu missing=%lu\n", (unsigned long)n, (unsigned long)np,
           (unsigned long)missing);
    static const char hx[] = "0123456789abcdef";
    char line[64 + 1 + 8 + 1];
    for (uint32_t p = 0; p < np; p++) {
        if (!s_cap_have[p]) {
            printf("CAP %lu -\n", (unsigned long)p);
            continue;
        }
        int k = 0;
        for (int i = 0; i < 32; i++) {
            const uint8_t v = s_cap_len[32u * p + (unsigned)i];
            line[k++] = hx[v >> 4];
            line[k++] = hx[v & 15];
        }
        line[k++] = ' ';
        for (int i = 0; i < 4; i++) {
            const uint8_t v = s_cap_gl[4u * p + (unsigned)i];
            line[k++] = hx[v >> 4];
            line[k++] = hx[v & 15];
        }
        line[k] = 0;
        printf("CAP %lu %s\n", (unsigned long)p, line);
        if ((p & 15) == 15)
            vTaskDelay(1);                           // let the console drain
    }
    printf("CAP END\n");
    memset(s_cap_have, 0, CAP_PKTS);
    s_cap_dumps++;
    s_cap_count = 0;
}

static void console_key(uint8_t ch)
{
    uint8_t c[LSN_CMD_LEN];
    if (ch == 'h' || ch == '?') {
        ESP_LOGI(TAG, "keys: c = capture %u runs now and dump when full, d = dump what was captured "
                 "(after power-up: the ring's start-up)", (unsigned)CAP_RUNS);
        return;
    }
    if (ch != 'c' && ch != 'd')
        return;
    if (!s_cap_len) {
        ESP_LOGW(TAG, "capture: no memory for a dump (PSRAM missing?)");
        return;
    }
    if (ch == 'c') {
        lsn_cmd_capture(c, LSN_CAP_ARM | LSN_CAP_AUTO);
        uart_write_bytes(HOST_UART, c, sizeof c);
        ESP_LOGI(TAG, "capture: %u runs from now, the dump follows when full", (unsigned)CAP_RUNS);
    } else {
        lsn_cmd_capture(c, LSN_CAP_DUMP);
        uart_write_bytes(HOST_UART, c, sizeof c);
        ESP_LOGI(TAG, "capture: dumping what was captured");
    }
}

static const char *op_name(uint8_t op)
{
    static const char *n[16] = {"Set/Start", "Get/Abort", "SetGet/StartResult", "Inc", "Dec", "GetInterface",
                                "StartResultAck", "AbortAck", "StartAck", "ErrorAck", "ProcessingAck",
                                "Processing", "Status/Result", "ResultAck", "Interface", "Error"};
    return n[op & 0xF];
}

static void trace_task(void *arg)
{
    (void)arg;
    mm_tel_t t;
    char hex[3 * MM_MAX_PAYLOAD + 1];
    for (;;) {
        if (s_cap_count)
            cap_print();
        if (xQueueReceive(s_trace, &t, pdMS_TO_TICKS(20)) != pdTRUE)
            continue;
        int k = 0;
        for (int i = 0; i < t.len; i++)
            k += snprintf(&hex[k], sizeof hex - (size_t)k, " %02X", t.data[i]);
        hex[k] = 0;
        ESP_LOGI("tel", "%08lX %04X>%04X %02X.%02X.%03X %s [%d]%s%s", (unsigned long)t.frame, t.source,
                 t.target, t.fblock, t.inst, t.fkt, op_name(t.op), t.len, hex, t.truncated ? " ..." : "");
    }
}

static void host_task(void *arg)
{
    (void)arg;
    static uint8_t buf[512];
    decide(1);                          // at once: an ESP32 reset must not leave the FPGA injecting
    int64_t next_resend = esp_timer_get_time() + RESEND_US, next_status = esp_timer_get_time() + STATUS_US;
    for (;;) {
        const int n = uart_read_bytes(HOST_UART, buf, sizeof buf, pdMS_TO_TICKS(20));
        if (n > 0)
            lsn_rx_feed(&s_rx, buf, (size_t)n, on_block, NULL);
        uint8_t key;
        if (uart_read_bytes(UART_NUM_0, &key, 1, 0) == 1)
            console_key(key);
        decide(0);
        const int64_t now = esp_timer_get_time();
        if (!s_stale && now - s_last_locked > STALE_US) {
            ESP_LOGW(TAG, "no locked ring for %d ms: every allocation is void, starting over", STALE_US / 1000);
            mm_init(&s_mm);
            am_init(&s_am);
            s_stale = 1;
            decide(1);
        }
        if (now > next_resend) {
            decide(1);
            next_resend += RESEND_US;
        }
        if (s_save_at && now > s_save_at) {
            s_save_at = 0;
            snd_save();
        }
        if (now > next_status) {
            ESP_LOGI(TAG, "packets %lu (bad %lu, lost in the FPGA %lu), telegrams %lu, refused %lu, "
                     "segments dropped %lu, trace lost %lu, capture packets %lu (bad %lu), dumps %lu, "
                     "audio in %s (phone %s, TOSLINK %s)",
                     (unsigned long)s_rx.good, (unsigned long)s_rx.bad,
                     (unsigned long)s_fpga_dropped, (unsigned long)s_mm.telegrams, (unsigned long)s_mm.rejected,
                     (unsigned long)s_mm.seg_dropped, (unsigned long)s_trace_lost, (unsigned long)s_rx.cap_good,
                     (unsigned long)s_rx.cap_bad, (unsigned long)s_cap_dumps, src_name(s_src_seen),
                     s_streaming ? "streaming" : "idle", s_opt_seen == 2 ? "not PCM" : opt_name(s_opt_seen));
            next_status += STATUS_US;
        }
    }
}

void host_start(void)
{
    lsn_rx_init(&s_rx);
    mm_init(&s_mm);
    am_init(&s_am);
    ain_init(&s_ain);
    wheel_init(&s_wheel);
    snd_load();
    s_trace = xQueueCreate(64, sizeof(mm_tel_t));
    ESP_ERROR_CHECK(s_trace ? ESP_OK : ESP_ERR_NO_MEM);
    const uart_config_t cfg = {
        .baud_rate = BAUD,
        .data_bits = UART_DATA_8_BITS,
        .parity = UART_PARITY_DISABLE,
        .stop_bits = UART_STOP_BITS_1,
        .flow_ctrl = UART_HW_FLOWCTRL_DISABLE,
        .source_clk = UART_SCLK_DEFAULT,
    };
    // a TX buffer: a coefficient set (517 bytes) goes out without holding up the reading
    ESP_ERROR_CHECK(uart_driver_install(HOST_UART, 8192, 1024, 0, NULL, 0));
    ESP_ERROR_CHECK(uart_param_config(HOST_UART, &cfg));
    ESP_ERROR_CHECK(uart_set_pin(HOST_UART, PIN_TX, PIN_RX, UART_PIN_NO_CHANGE, UART_PIN_NO_CHANGE));
    // the console's UART, receive side only: the keys (its output stays the log's)
    ESP_ERROR_CHECK(uart_driver_install(UART_NUM_0, 256, 0, 0, NULL, 0));
    // the S/PDIF receiver's ERROR (DIR9001 pin 27): high = no lock; its AUDIO (pin 1):
    // high = not PCM. Both pulled up, so a board without the receiver never injects
    // from the TOSLINK input.
    const gpio_config_t opt = {.pin_bit_mask = (1ULL << PIN_OPT_ERR) | (1ULL << PIN_OPT_NPCM),
                               .mode = GPIO_MODE_INPUT,
                               .pull_up_en = GPIO_PULLUP_ENABLE, .pull_down_en = GPIO_PULLDOWN_DISABLE,
                               .intr_type = GPIO_INTR_DISABLE};
    ESP_ERROR_CHECK(gpio_config(&opt));
    // a dump: 64 KB of lengths, 8 KB of glitch flags, the packets seen - in PSRAM if there is any
    s_cap_len = heap_caps_malloc(CAP_RUNS, MALLOC_CAP_SPIRAM | MALLOC_CAP_8BIT);
    if (!s_cap_len)
        s_cap_len = heap_caps_malloc(CAP_RUNS, MALLOC_CAP_8BIT);
    s_cap_gl = s_cap_len ? heap_caps_malloc(CAP_RUNS / 8, MALLOC_CAP_8BIT) : NULL;
    s_cap_have = s_cap_gl ? heap_caps_calloc(CAP_PKTS, 1, MALLOC_CAP_8BIT) : NULL;
    if (s_cap_have) {
        s_rx.cap_cb = on_cap;
        ESP_LOGI(TAG, "capture: the ring's first %u runs are kept in the FPGA; 'd' dumps them, "
                 "'c' captures now, 'h' help", (unsigned)CAP_RUNS);
    } else {
        s_cap_len = NULL;
        ESP_LOGW(TAG, "capture: no memory for a dump");
    }
    // below Bluedroid (19-20) on core 0: the 8 KB buffer covers 65 ms of stall;
    // 6 KB of stack for the coefficient design (double) and its log line
    xTaskCreatePinnedToCore(host_task, "host", 6144, NULL, 10, NULL, 0);
    xTaskCreatePinnedToCore(trace_task, "trace", 4096, NULL, 2, NULL, 0);
}

void host_streaming(int on)
{
    s_streaming = on;
}
