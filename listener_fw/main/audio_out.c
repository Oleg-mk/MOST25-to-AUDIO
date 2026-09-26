// audio_out.c - see audio_out.h.
//
// Pins (listener board, block 8; M2 = ESP32-DevKitC):
//   IO34 <- I2S_BCLK_F  (pad 5)   input only, no pull: the listener drives it
//   IO35 <- I2S_LRCK_F  (pad 6)
//   IO27 -> R21 -> I2S_DIN_F (pad 11)
// Format as the listener's DIN takes it: I2S (Philips), 32-bit slots, the
// sample in the top 24 bits, BCLK = 64 Fs.
//
// The ring's rate: the DMA only takes data as BCLK clocks it out, so the
// time a run of blocks takes to go out is the ring's frame rate. Measured
// once the clocks run; 44.1 or 48 kHz, nothing else is accepted.
//
// Clocks gone (the Si514 is being centred, or the ring sleeps): the write
// times out. The block that did not go out is kept and retried, so no audio
// is lost on this side; ratematch sees a consumer that stopped, and when the
// clocks come back it drops what went stale.
#include "audio_out.h"

#include <math.h>
#include <string.h>

#include "driver/i2s_std.h"
#include "esp_heap_caps.h"
#include "esp_log.h"
#include "esp_timer.h"
#include "freertos/FreeRTOS.h"
#include "freertos/semphr.h"
#include "freertos/task.h"
#include "rate_match.h"

#define PIN_BCLK    34
#define PIN_LRCK    35
#define PIN_DIN     27
#define BLOCK       240                 // frames per write: 5 ms at 48 kHz
#define TARGET_MS   200.0               // what ratematch keeps buffered
#define CAP_PSRAM   16384               // frames in the ring buffer (PSRAM)
#define CAP_IRAM    8192                // without PSRAM (a board with no WROVER)

static const char *TAG = "audio_out";

static rm_t s_rm;                       // 33 KB of coefficients: internal RAM
static int16_t *s_buf;
static uint32_t s_cap;
static i2s_chan_handle_t s_tx;
static SemaphoreHandle_t s_lock;        // rm_push against rm_init
static volatile int s_ready;            // s_rm set up for the current rates
static volatile uint32_t s_fs_req = 44100;  // from the A2DP codec
static volatile int s_mono;
static uint32_t s_fs_in;
static volatile uint32_t s_fs_out;      // the ring's rate, 0 until measured

uint32_t audio_out_ring_rate(void)
{
    return s_fs_out;
}

void audio_out_set_source(uint32_t fs_in, int mono)
{
    s_mono = mono;
    s_fs_req = fs_in;                   // the output task re-initialises
}

void audio_out_push(const uint8_t *pcm, uint32_t len)
{
    if (!s_ready)
        return;
    xSemaphoreTake(s_lock, portMAX_DELAY);
    if (s_ready) {
        if (!s_mono) {
            rm_push(&s_rm, (const int16_t *)pcm, len / 4);
        } else {
            int16_t st[2 * 128];
            const int16_t *m = (const int16_t *)pcm;
            uint32_t n = len / 2;
            while (n) {
                const uint32_t k = n < 128 ? n : 128;
                for (uint32_t i = 0; i < k; i++)
                    st[2 * i] = st[2 * i + 1] = m[i];
                rm_push(&s_rm, st, k);
                m += k;
                n -= k;
            }
        }
    }
    xSemaphoreGive(s_lock);
}

// Write one block; keeps retrying while the clocks are gone.
static void write_block(const int32_t *lr)
{
    const uint8_t *p = (const uint8_t *)lr;
    size_t left = 2 * BLOCK * sizeof(int32_t);
    int waited = 0;
    while (left) {
        size_t done = 0;
        const esp_err_t e = i2s_channel_write(s_tx, p, left, &done, pdMS_TO_TICKS(100));
        p += done;
        left -= done;
        if (e == ESP_ERR_TIMEOUT && !waited) {
            ESP_LOGW(TAG, "no BCLK from the listener: waiting");
            waited = 1;
        }
    }
    if (waited)
        ESP_LOGI(TAG, "BCLK back");
}

// The ring's frame rate from the pace of the DMA: 44100, 48000, or 0.
static uint32_t measure_fs(void)
{
    static int32_t zero[2 * BLOCK];
    for (int i = 0; i < 16; i++)                   // fill the DMA first
        write_block(zero);
    const int n = 200;                             // about 1 s
    const int64_t t0 = esp_timer_get_time();
    for (int i = 0; i < n; i++)
        write_block(zero);
    const double fs = (double)n * BLOCK * 1e6 / (double)(esp_timer_get_time() - t0);
    ESP_LOGI(TAG, "ring frame rate %.0f Hz", fs);
    if (fabs(fs / 44100.0 - 1.0) < 0.01)
        return 44100;
    if (fabs(fs / 48000.0 - 1.0) < 0.01)
        return 48000;
    return 0;
}

static void setup(uint32_t fs_in)
{
    xSemaphoreTake(s_lock, portMAX_DELAY);
    s_ready = 0;
    if (rm_init(&s_rm, s_buf, s_cap, fs_in, s_fs_out, TARGET_MS) == 0) {
        s_fs_in = fs_in;
        s_ready = 1;
        ESP_LOGI(TAG, "phone %lu Hz -> ring %lu Hz", (unsigned long)fs_in, (unsigned long)s_fs_out);
    } else {
        ESP_LOGE(TAG, "cannot convert %lu Hz to %lu Hz", (unsigned long)fs_in, (unsigned long)s_fs_out);
    }
    xSemaphoreGive(s_lock);
}

static void out_task(void *arg)
{
    static int32_t lr[2 * BLOCK];
    (void)arg;
    while ((s_fs_out = measure_fs()) == 0)
        ;
    setup(s_fs_req);
    int64_t next_log = esp_timer_get_time() + 5000000;
    for (;;) {
        if (s_fs_req != s_fs_in)
            setup(s_fs_req);
        if (s_ready)
            rm_pull(&s_rm, lr, BLOCK);
        else
            memset(lr, 0, sizeof lr);
        write_block(lr);
        if (esp_timer_get_time() > next_log) {
            rm_status_t st;
            rm_status(&s_rm, &st);
            ESP_LOGI(TAG, "state %d, fill %.0f ms, %+.1f ppm, underflows %lu, jumps %lu, dropped %lu",
                     st.state, st.fill_ms, st.ppm, (unsigned long)st.underflows,
                     (unsigned long)st.jumps, (unsigned long)st.dropped);
            next_log += 5000000;
        }
    }
}

void audio_out_start(void)
{
    s_lock = xSemaphoreCreateMutex();
    s_cap = CAP_PSRAM;
    s_buf = heap_caps_malloc(2 * s_cap * sizeof(int16_t), MALLOC_CAP_SPIRAM);
    if (!s_buf) {
        s_cap = CAP_IRAM;
        s_buf = heap_caps_malloc(2 * s_cap * sizeof(int16_t), MALLOC_CAP_INTERNAL);
    }
    ESP_ERROR_CHECK(s_buf ? ESP_OK : ESP_ERR_NO_MEM);

    i2s_chan_config_t cc = I2S_CHANNEL_DEFAULT_CONFIG(I2S_NUM_0, I2S_ROLE_SLAVE);
    cc.dma_desc_num = 4;
    cc.dma_frame_num = BLOCK;
    cc.auto_clear_after_cb = true;      // nothing new to send: zeros, not old audio
    ESP_ERROR_CHECK(i2s_new_channel(&cc, &s_tx, NULL));
    i2s_std_config_t sc = {
        // slave: the rate only sizes the internal clock, which must run at
        // least 8x BCLK; 48 kHz covers both ring rates
        .clk_cfg = I2S_STD_CLK_DEFAULT_CONFIG(48000),
        .slot_cfg = I2S_STD_PHILIPS_SLOT_DEFAULT_CONFIG(I2S_DATA_BIT_WIDTH_32BIT, I2S_SLOT_MODE_STEREO),
        .gpio_cfg = {
            .mclk = I2S_GPIO_UNUSED,
            .bclk = PIN_BCLK,
            .ws = PIN_LRCK,
            .dout = PIN_DIN,
            .din = I2S_GPIO_UNUSED,
        },
    };
    ESP_ERROR_CHECK(i2s_channel_init_std_mode(s_tx, &sc));
    ESP_ERROR_CHECK(i2s_channel_enable(s_tx));
    xTaskCreatePinnedToCore(out_task, "audio_out", 4096, NULL, configMAX_PRIORITIES - 2, NULL, 1);
}
