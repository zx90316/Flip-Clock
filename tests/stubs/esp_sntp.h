#pragma once
#include <sys/time.h>
inline void esp_sntp_stop() {}
inline void esp_sntp_set_time_sync_notification_cb(void(*)(struct timeval*)) {}
inline void esp_sntp_set_sync_interval(uint32_t) {}
