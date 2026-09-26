// a2dp_dec.h - AAC and SBC from the A2DP sink, decoded for audio_out.
//
// The stack runs with an external codec: it hands over the media packets as
// they came from the phone, and this module decodes them with Espressif's
// esp_audio_codec. The phone picks the codec from what we offer: AAC-LC
// (what an iPhone sends) and SBC (the mandatory one), both at 44.1 and
// 48 kHz only - the ring runs at one of those, and ratematch converts
// between them.
#pragma once

#include "esp_a2dp_api.h"

// Offer AAC-LC (endpoint 0) and SBC (endpoint 1); after esp_a2d_sink_init().
void a2dp_dec_register_seps(void);

// The decoder task.
void a2dp_dec_start(void);

// The codec the phone chose (ESP_A2D_AUDIO_CFG_EVT).
void a2dp_dec_config(const esp_a2d_mcc_t *mcc);

// A media packet from the stack; this module frees it.
void a2dp_dec_feed(esp_a2d_audio_buff_t *buf);

// Drop the packets still queued (stream suspended, phone gone).
void a2dp_dec_flush(void);
