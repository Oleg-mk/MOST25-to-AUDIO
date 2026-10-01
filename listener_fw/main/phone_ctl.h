// phone_ctl.h - the phone's track keys over AVRCP: M2 is the remote control
// (AVRCP controller), the phone the target. The steering wheel's keys reach
// the phone this way (host.c).
#pragma once

#include <stdbool.h>

// After esp_bluedroid_enable(), before esp_a2d_sink_init(): AVRCP comes up
// with A2DP, and the phone connects it when it connects the stream.
void phone_ctl_init(void);

// Next or previous track: the key pressed and released. Nothing (and a
// warning) while the phone has no AVRCP link.
void phone_ctl_key(bool next);
