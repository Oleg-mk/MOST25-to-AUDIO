// phone_ctl.c - see phone_ctl.h.
#include "phone_ctl.h"

#include "esp_avrc_api.h"
#include "esp_log.h"

static const char *TAG = "phone";

static volatile bool s_connected;
static uint8_t s_tl;                    // transaction label, 0..15, one per command

static void ct_cb(esp_avrc_ct_cb_event_t ev, esp_avrc_ct_cb_param_t *p)
{
    switch (ev) {
    case ESP_AVRC_CT_CONNECTION_STATE_EVT:
        s_connected = p->conn_stat.connected;
        ESP_LOGI(TAG, "remote control %s", s_connected ? "connected" : "gone");
        break;
    case ESP_AVRC_CT_REMOTE_FEATURES_EVT:
        if (!(p->rmt_feats.feat_mask & ESP_AVRC_FEAT_RCTG))
            ESP_LOGW(TAG, "the phone takes no remote-control keys");
        break;
    case ESP_AVRC_CT_PASSTHROUGH_RSP_EVT:
        if (p->psth_rsp.key_state == ESP_AVRC_PT_CMD_STATE_PRESSED && p->psth_rsp.rsp_code != ESP_AVRC_RSP_ACCEPT)
            ESP_LOGW(TAG, "key 0x%02X not taken (response %d)", p->psth_rsp.key_code, p->psth_rsp.rsp_code);
        break;
    default:
        break;
    }
}

void phone_ctl_init(void)
{
    ESP_ERROR_CHECK(esp_avrc_ct_register_callback(ct_cb));
    ESP_ERROR_CHECK(esp_avrc_ct_init());
}

void phone_ctl_key(bool next)
{
    if (!s_connected) {
        ESP_LOGW(TAG, "no remote-control link to the phone: key dropped");
        return;
    }
    const uint8_t key = next ? ESP_AVRC_PT_CMD_FORWARD : ESP_AVRC_PT_CMD_BACKWARD;
    esp_avrc_ct_send_passthrough_cmd(s_tl, key, ESP_AVRC_PT_CMD_STATE_PRESSED);
    s_tl = (uint8_t)((s_tl + 1) & 15);
    esp_avrc_ct_send_passthrough_cmd(s_tl, key, ESP_AVRC_PT_CMD_STATE_RELEASED);
    s_tl = (uint8_t)((s_tl + 1) & 15);
}
