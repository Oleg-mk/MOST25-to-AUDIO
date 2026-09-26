// main.c - M2 on the listener board: music from a phone into the MOST ring.
//
// Bluetooth classic, A2DP sink: a phone pairs with "MOST BT audio" (no PIN
// with Secure Simple Pairing; 0000 for an old phone) and streams AAC or SBC.
// a2dp_dec decodes the media packets, audio_out plays the PCM on the
// listener's DIN at the ring's pace.
//
// host follows the control channel: it puts our audio into the AUX source's
// frame bytes while the amplifier plays them and the phone streams, and the
// amplifier's main zone out on J3.
#include <string.h>

#include "a2dp_dec.h"
#include "audio_out.h"
#include "host.h"
#include "esp_a2dp_api.h"
#include "esp_bt.h"
#include "esp_bt_main.h"
#include "esp_gap_bt_api.h"
#include "esp_log.h"
#include "nvs_flash.h"

#define DEVICE_NAME "MOST BT audio"

static const char *TAG = "main";

static void gap_cb(esp_bt_gap_cb_event_t ev, esp_bt_gap_cb_param_t *p)
{
    switch (ev) {
    case ESP_BT_GAP_AUTH_CMPL_EVT:
        if (p->auth_cmpl.stat == ESP_BT_STATUS_SUCCESS)
            ESP_LOGI(TAG, "paired with %s", p->auth_cmpl.device_name);
        else
            ESP_LOGW(TAG, "pairing failed, status %d", p->auth_cmpl.stat);
        break;
    case ESP_BT_GAP_CFM_REQ_EVT:         // numeric comparison: nothing to show it on
        esp_bt_gap_ssp_confirm_reply(p->cfm_req.bda, true);
        break;
    default:
        break;
    }
}

static void a2d_cb(esp_a2d_cb_event_t ev, esp_a2d_cb_param_t *p)
{
    switch (ev) {
    case ESP_A2D_CONNECTION_STATE_EVT:
        if (p->conn_stat.state == ESP_A2D_CONNECTION_STATE_CONNECTED) {
            ESP_LOGI(TAG, "phone connected");
            esp_bt_gap_set_scan_mode(ESP_BT_CONNECTABLE, ESP_BT_NON_DISCOVERABLE);
        } else if (p->conn_stat.state == ESP_A2D_CONNECTION_STATE_DISCONNECTED) {
            ESP_LOGI(TAG, "phone disconnected");
            host_streaming(0);
            a2dp_dec_flush();
            esp_bt_gap_set_scan_mode(ESP_BT_CONNECTABLE, ESP_BT_GENERAL_DISCOVERABLE);
        }
        break;
    case ESP_A2D_AUDIO_STATE_EVT:
        if (p->audio_stat.state == ESP_A2D_AUDIO_STATE_STARTED) {
            ESP_LOGI(TAG, "stream started");
            host_streaming(1);
        } else {
            ESP_LOGI(TAG, "stream suspended");
            host_streaming(0);
            a2dp_dec_flush();
        }
        break;
    case ESP_A2D_AUDIO_CFG_EVT:
        a2dp_dec_config(&p->audio_cfg.mcc);
        break;
    case ESP_A2D_SEP_REG_STATE_EVT:
        if (p->a2d_sep_reg_stat.reg_state != ESP_A2D_SEP_REG_SUCCESS)
            ESP_LOGE(TAG, "stream endpoint %d not registered: %d", p->a2d_sep_reg_stat.seid,
                     p->a2d_sep_reg_stat.reg_state);
        break;
    default:
        break;
    }
}

static void a2d_media_cb(esp_a2d_conn_hdl_t conn, esp_a2d_audio_buff_t *buf)
{
    (void)conn;
    if (!buf)
        return;
    if (!buf->data || !buf->data_len) {
        esp_a2d_audio_buff_free(buf);
        return;
    }
    a2dp_dec_feed(buf);
}

void app_main(void)
{
    esp_err_t err = nvs_flash_init();          // pairing keys live here
    if (err == ESP_ERR_NVS_NO_FREE_PAGES || err == ESP_ERR_NVS_NEW_VERSION_FOUND) {
        ESP_ERROR_CHECK(nvs_flash_erase());
        err = nvs_flash_init();
    }
    ESP_ERROR_CHECK(err);

    audio_out_start();
    a2dp_dec_start();
    host_start();

    ESP_ERROR_CHECK(esp_bt_controller_mem_release(ESP_BT_MODE_BLE));
    esp_bt_controller_config_t bt_cfg = BT_CONTROLLER_INIT_CONFIG_DEFAULT();
    ESP_ERROR_CHECK(esp_bt_controller_init(&bt_cfg));
    ESP_ERROR_CHECK(esp_bt_controller_enable(ESP_BT_MODE_CLASSIC_BT));
    esp_bluedroid_config_t bd_cfg = BT_BLUEDROID_INIT_CONFIG_DEFAULT();
    ESP_ERROR_CHECK(esp_bluedroid_init_with_cfg(&bd_cfg));
    ESP_ERROR_CHECK(esp_bluedroid_enable());

    esp_bt_io_cap_t iocap = ESP_BT_IO_CAP_NONE;  // no screen, no keys: "just works"
    esp_bt_gap_set_security_param(ESP_BT_SP_IOCAP_MODE, &iocap, sizeof(uint8_t));
    esp_bt_pin_code_t pin = {'0', '0', '0', '0'};
    esp_bt_gap_set_pin(ESP_BT_PIN_TYPE_FIXED, 4, pin);
    esp_bt_gap_register_callback(gap_cb);
    esp_bt_gap_set_device_name(DEVICE_NAME);

    esp_a2d_register_callback(a2d_cb);
    ESP_ERROR_CHECK(esp_a2d_sink_init());
    a2dp_dec_register_seps();
    ESP_ERROR_CHECK(esp_a2d_sink_register_audio_data_callback(a2d_media_cb));
    esp_bt_gap_set_scan_mode(ESP_BT_CONNECTABLE, ESP_BT_GENERAL_DISCOVERABLE);
    ESP_LOGI(TAG, "ready: \"%s\" is discoverable", DEVICE_NAME);
}
