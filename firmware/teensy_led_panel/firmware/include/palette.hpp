#pragma once

#include <FastLED.h>

namespace ledpanel {
namespace palette {

// Colors from DESIGN_SYSTEM.md (Phosphor Palette)
constexpr uint32_t COLOR_OK = 0x00FF41;      // Emerald-500
constexpr uint32_t COLOR_WARNING = 0xFFB000; // Amber-500
constexpr uint32_t COLOR_ERROR = 0xFF0033;   // Ruby-500
constexpr uint32_t COLOR_OFFLINE = 0x333333; // Dim Gray
constexpr uint32_t COLOR_UNKNOWN = 0x666666; // Gray

constexpr uint32_t COLOR_CYAN = 0x00FFFF;
constexpr uint32_t COLOR_BG = 0x050505;

inline CRGB getHealthColor(uint8_t healthCode) {
    switch (healthCode) {
        case 0: return CRGB(COLOR_OK);
        case 1: return CRGB(COLOR_WARNING);
        case 2: return CRGB(COLOR_ERROR);
        case 3: return CRGB(COLOR_OFFLINE);
        default: return CRGB(COLOR_UNKNOWN);
    }
}

} // namespace palette
} // namespace ledpanel
