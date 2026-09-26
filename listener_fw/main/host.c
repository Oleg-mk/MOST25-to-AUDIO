// host.c - see host.h.
//
// UART2 at 3 Mbaud 8N1, as the FPGA's ctrl_uart / uart_rx:
//   IO33 <- UART_TX_F  control blocks (M2 pad 8)
//   IO25 -> R20 -> UART_RX_F  commands (M2 pad 9)
//
// Every control block: most_msg decodes it, amp_model and sound follow it.
// Three decisions come from them:
//   02  our audio into the AUX source's frame bytes - while an amplifier sink
//       is connected to them AND the phone is streaming. Otherwise the car's
//       own AUX passes untouched: we take nothing away from the car.
//   01  J3 plays what the amplifier's sink 1 (the main zone) plays...
//   03  ...with the head unit's volume, mute, balance, bass, treble and
//       loudness: dsp_img turns them into the FPGA's coefficient set, written
//       word by word and committed with the last (at most every 20 ms while
//       the knob turns). The settings are kept in NVS, so after a restart J3
//       starts where it was, as the factory amplifier does; until a volume
//       has been heard once, J3 is silent.
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
#include "host.h"

#include <stdio.h>
#include <string.h>

#include "amp_model.h"
#include "audio_out.h"
#include "driver/uart.h"
#include "dsp_img.h"
#include "esp_log.h"
#include "esp_timer.h"
#include "freertos/FreeRTOS.h"
#include "freertos/queue.h"
#include "freertos/task.h"
#include "lsn_link.h"
#include "most_msg.h"
#include "nvs.h"
#include "sound.h"

#define HOST_UART   UART_NUM_2
#define PIN_RX      33
#define PIN_TX      25
#define BAUD        3000000
#define RESEND_US   2000000
#define STALE_US    500000
#define STATUS_US   10000000
#define IMG_MIN_US  20000               // coefficient sets at most 50 a second
#define SAVE_US     10000000            // settings to flash 10 s after the last change
#define SND_MAGIC   0x534E4431u         // "SND1": the stored layout

static const char *TAG = "host";

static lsn_rx_t s_rx;
static mm_t s_mm;
static am_t s_am;
static QueueHandle_t s_trace;
static uint32_t s_trace_lost;
static am_pos_t s_aux_sent, s_main_sent;
static int64_t s_last_locked;
static int s_stale = 1;
static volatile int s_streaming;
static uint32_t s_fpga_dropped;
static snd_t s_snd;
static int s_img_dirty = 1, s_muted_sent = -1;
static uint32_t s_fs_sent;
static int64_t s_img_sent, s_save_at;

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
    if (dsp_image(&s_snd, &snd_cfg_default, muted, fs ? fs : 48000, w) != 0)
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
                 snd_volume_db(&s_snd), muted ? " (muted)" : "", gl, gr, bass, treble, (unsigned long)fs);
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
    const am_pos_t aux = s_streaming ? am_aux_playing(&s_am) : off, main_zone = am_main(&s_am);
    uint8_t c[LSN_CMD_LEN];
    if (am_main_muted(&s_am) != s_muted_sent || audio_out_ring_rate() != s_fs_sent)
        s_img_dirty = 1;
    // the set first: a source switched on is heard with its gains, never at full scale
    if (force || (s_img_dirty && esp_timer_get_time() - s_img_sent >= IMG_MIN_US))
        send_image();
    if (force || !pos_eq(&aux, &s_aux_sent)) {
        lsn_cmd_inject(c, aux.bits, 0, aux.l, aux.r);
        uart_write_bytes(HOST_UART, c, sizeof c);
        if (!pos_eq(&aux, &s_aux_sent))
            log_pos("our audio into AUX", &aux);
        s_aux_sent = aux;
    }
    if (force || !pos_eq(&main_zone, &s_main_sent)) {
        lsn_cmd_stereo(c, main_zone.bits, main_zone.l, main_zone.r);
        uart_write_bytes(HOST_UART, c, sizeof c);
        if (!pos_eq(&main_zone, &s_main_sent))
            log_pos("J3 stereo (amp sink 1)", &main_zone);
        s_main_sent = main_zone;
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
        xQueueReceive(s_trace, &t, portMAX_DELAY);
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
                     "segments dropped %lu, trace lost %lu", (unsigned long)s_rx.good, (unsigned long)s_rx.bad,
                     (unsigned long)s_fpga_dropped, (unsigned long)s_mm.telegrams, (unsigned long)s_mm.rejected,
                     (unsigned long)s_mm.seg_dropped, (unsigned long)s_trace_lost);
            next_status += STATUS_US;
        }
    }
}

void host_start(void)
{
    lsn_rx_init(&s_rx);
    mm_init(&s_mm);
    am_init(&s_am);
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
    // below Bluedroid (19-20) on core 0: the 8 KB buffer covers 65 ms of stall;
    // 6 KB of stack for the coefficient design (double) and its log line
    xTaskCreatePinnedToCore(host_task, "host", 6144, NULL, 10, NULL, 0);
    xTaskCreatePinnedToCore(trace_task, "trace", 4096, NULL, 2, NULL, 0);
}

void host_streaming(int on)
{
    s_streaming = on;
}
