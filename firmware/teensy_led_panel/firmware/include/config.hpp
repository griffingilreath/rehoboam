#pragma once

#include <cstdint>

namespace ledpanel {

constexpr uint8_t LED_COUNT = 16;
constexpr uint8_t LED_DATA_PIN = 6;
constexpr uint8_t DEFAULT_BRIGHTNESS = 128; // 0-255
constexpr uint32_t SERIAL_BAUD_RATE = 115200;
constexpr uint32_t SERIAL_START_TIMEOUT_MS = 3000;
constexpr uint32_t HOST_HEARTBEAT_TIMEOUT_MS = 120000; // 2 minutes

} // namespace ledpanel
