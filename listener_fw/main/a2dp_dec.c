// a2dp_dec.c - see a2dp_dec.h.
//
// The stack's callback only queues the packet; a task on core 1 decodes it
// (AAC-LC costs a noticeable share of a core) and hands the PCM to audio_out.
// The decoder handle is guarded: the phone may change the codec while a
// packet is being decoded.
#include "a2dp_dec.h"

#include <stdlib.h>

#include "audio_out.h"
#include "esp_aac_dec.h"
#include "esp_audio_dec.h"
#include "esp_audio_dec_reg.h"
#include "esp_log.h"
#include "esp_sbc_dec.h"
#include "freertos/FreeRTOS.h"
#include "freertos/queue.h"
#include "freertos/semphr.h"
#include "freertos/task.h"

#define QUEUE_DEPTH  32                  // media packets; about half a second of AAC

static const char *TAG = "a2dp_dec";

static QueueHandle_t s_q;
static SemaphoreHandle_t s_lock;         // s_dec
static esp_audio_dec_handle_t s_dec;
static uint8_t *s_pcm;
static uint32_t s_pcm_len = 4096;

void a2dp_dec_register_seps(void)
{
    esp_a2d_mcc_t aac = {0};
    aac.type = ESP_A2D_MCT_M24;
    aac.cie.m24_info.drc = ESP_A2D_M24_CIE_DRC_NS;
    aac.cie.m24_info.obj_type = ESP_A2D_M24_CIE_OBJ_TYPE_2_AAC_LC | ESP_A2D_M24_CIE_OBJ_TYPE_4_AAC_LC;
    aac.cie.m24_info.samp_freq1 = ESP_A2D_M24_CIE_SF1_44K;
    aac.cie.m24_info.samp_freq2 = ESP_A2D_M24_CIE_SF2_48K;
    aac.cie.m24_info.ch = ESP_A2D_M24_CIE_CH_1 | ESP_A2D_M24_CIE_CH_2;
    aac.cie.m24_info.vbr = ESP_A2D_M24_CIE_VBR_SUPPORT;
    aac.cie.m24_info.br1 = ESP_A2D_M24_CIE_BR1_MSK;     // no bit rate limit
    aac.cie.m24_info.br2 = ESP_A2D_M24_CIE_BR2_MSK;
    aac.cie.m24_info.br3 = ESP_A2D_M24_CIE_BR3_MSK;
    esp_a2d_sink_register_stream_endpoint(0, &aac);

    esp_a2d_mcc_t sbc = {0};
    sbc.type = ESP_A2D_MCT_SBC;
    sbc.cie.sbc_info.samp_freq = ESP_A2D_SBC_CIE_SF_44K | ESP_A2D_SBC_CIE_SF_48K;
    sbc.cie.sbc_info.ch_mode = ESP_A2D_SBC_CIE_CH_MODE_MONO | ESP_A2D_SBC_CIE_CH_MODE_DUAL_CHANNEL |
                               ESP_A2D_SBC_CIE_CH_MODE_STEREO | ESP_A2D_SBC_CIE_CH_MODE_JOINT_STEREO;
    sbc.cie.sbc_info.block_len = ESP_A2D_SBC_CIE_BLOCK_LEN_4 | ESP_A2D_SBC_CIE_BLOCK_LEN_8 |
                                 ESP_A2D_SBC_CIE_BLOCK_LEN_12 | ESP_A2D_SBC_CIE_BLOCK_LEN_16;
    sbc.cie.sbc_info.num_subbands = ESP_A2D_SBC_CIE_NUM_SUBBANDS_4 | ESP_A2D_SBC_CIE_NUM_SUBBANDS_8;
    sbc.cie.sbc_info.alloc_mthd = ESP_A2D_SBC_CIE_ALLOC_MTHD_SNR | ESP_A2D_SBC_CIE_ALLOC_MTHD_LOUDNESS;
    sbc.cie.sbc_info.min_bitpool = 2;
    sbc.cie.sbc_info.max_bitpool = 250;
    esp_a2d_sink_register_stream_endpoint(1, &sbc);
}

static void dec_task(void *arg)
{
    (void)arg;
    esp_a2d_audio_buff_t *b;
    int errors = 0;
    for (;;) {
        xQueueReceive(s_q, &b, portMAX_DELAY);
        xSemaphoreTake(s_lock, portMAX_DELAY);
        if (s_dec) {
            esp_audio_dec_in_raw_t in = {.buffer = b->data, .len = b->data_len};
            while (in.len > 0) {
                esp_audio_dec_out_frame_t out = {.buffer = s_pcm, .len = s_pcm_len};
                const esp_audio_err_t e = esp_audio_dec_process(s_dec, &in, &out);
                if (e == ESP_AUDIO_ERR_BUFF_NOT_ENOUGH) {
                    uint8_t *p = realloc(s_pcm, 2 * s_pcm_len);
                    if (!p)
                        break;
                    s_pcm = p;
                    s_pcm_len *= 2;
                    continue;
                }
                if (e != ESP_AUDIO_ERR_OK) {
                    if (errors++ < 5)
                        ESP_LOGW(TAG, "decode error %d", e);
                    break;
                }
                if (out.decoded_size)
                    audio_out_push(s_pcm, out.decoded_size);
                if (!in.consumed)
                    break;
                in.buffer += in.consumed;
                in.len -= in.consumed;
            }
        }
        xSemaphoreGive(s_lock);
        esp_a2d_audio_buff_free(b);
    }
}

void a2dp_dec_start(void)
{
    s_lock = xSemaphoreCreateMutex();
    s_q = xQueueCreate(QUEUE_DEPTH, sizeof(esp_a2d_audio_buff_t *));
    s_pcm = malloc(s_pcm_len);
    ESP_ERROR_CHECK(s_lock && s_q && s_pcm ? ESP_OK : ESP_ERR_NO_MEM);
    esp_sbc_dec_register();
    esp_aac_dec_register();
    // below audio_out, which mostly waits on the I2S DMA
    xTaskCreatePinnedToCore(dec_task, "a2dp_dec", 6144, NULL, configMAX_PRIORITIES - 4, NULL, 1);
}

void a2dp_dec_config(const esp_a2d_mcc_t *mcc)
{
    uint32_t fs = 44100;
    int mono = 0;
    esp_audio_dec_cfg_t cfg = {0};
    esp_sbc_dec_cfg_t sbc = ESP_SBC_DEC_CONFIG_DEFAULT();
    esp_aac_dec_cfg_t aac = ESP_AAC_DEC_CONFIG_DEFAULT();
    if (mcc->type == ESP_A2D_MCT_SBC) {
        fs = (mcc->cie.sbc_info.samp_freq & ESP_A2D_SBC_CIE_SF_48K) ? 48000 : 44100;
        mono = (mcc->cie.sbc_info.ch_mode & ESP_A2D_SBC_CIE_CH_MODE_MONO) != 0;
        sbc.sbc_mode = ESP_SBC_MODE_STD;
        sbc.ch_num = mono ? 1 : 2;
        sbc.enable_plc = true;               // conceal a lost packet rather than click
        cfg = (esp_audio_dec_cfg_t){.type = ESP_AUDIO_TYPE_SBC, .cfg = &sbc, .cfg_sz = sizeof sbc};
    } else if (mcc->type == ESP_A2D_MCT_M24) {
        fs = (mcc->cie.m24_info.samp_freq2 & ESP_A2D_M24_CIE_SF2_48K) ? 48000 : 44100;
        mono = (mcc->cie.m24_info.ch & ESP_A2D_M24_CIE_CH_1) != 0;
        aac.sample_rate = fs;
        aac.channel = mono ? 1 : 2;
        aac.bits_per_sample = ESP_AUDIO_BIT16;
        aac.no_adts_header = true;           // raw access units from the stack
        aac.aac_plus_enable = false;         // only AAC-LC is offered
        cfg = (esp_audio_dec_cfg_t){.type = ESP_AUDIO_TYPE_AAC, .cfg = &aac, .cfg_sz = sizeof aac};
    } else {
        ESP_LOGW(TAG, "codec %d not offered", mcc->type);
        return;
    }
    xSemaphoreTake(s_lock, portMAX_DELAY);
    if (s_dec) {
        esp_audio_dec_close(s_dec);
        s_dec = NULL;
    }
    const esp_audio_err_t e = esp_audio_dec_open(&cfg, &s_dec);
    if (e != ESP_AUDIO_ERR_OK) {
        s_dec = NULL;
        ESP_LOGE(TAG, "decoder open failed: %d", e);
    }
    xSemaphoreGive(s_lock);
    ESP_LOGI(TAG, "%s %lu Hz %s", mcc->type == ESP_A2D_MCT_SBC ? "SBC" : "AAC", (unsigned long)fs,
             mono ? "mono" : "stereo");
    audio_out_set_source(fs, mono);
}

void a2dp_dec_feed(esp_a2d_audio_buff_t *buf)
{
    if (!s_q || xQueueSend(s_q, &buf, 0) != pdTRUE)
        esp_a2d_audio_buff_free(buf);        // queue full: the decoder has fallen behind
}

void a2dp_dec_flush(void)
{
    esp_a2d_audio_buff_t *b;
    while (s_q && xQueueReceive(s_q, &b, 0) == pdTRUE)
        esp_a2d_audio_buff_free(b);
}
