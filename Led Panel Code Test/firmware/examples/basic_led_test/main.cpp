#include <Arduino.h>
#include <FastLED.h>

namespace {
constexpr uint8_t LED_PIN = 6;
constexpr uint8_t LED_COUNT = 16; // Works even if only 1 LED is connected
constexpr uint8_t BRIGHTNESS = 255;
constexpr uint16_t STEP_INTERVAL_MS = 1000;

CRGB leds[LED_COUNT];

uint32_t lastStep = 0;
uint8_t testPhase = 0;
uint8_t chaseIndex = 0;

void showSingleColor(const CRGB &color) {
    fill_solid(leds, LED_COUNT, CRGB::Black);
    leds[0] = color;
    FastLED.show();
}

void advanceChase() {
    fill_solid(leds, LED_COUNT, CRGB::Black);
    leds[chaseIndex % LED_COUNT] = CHSV(chaseIndex * 16, 255, 255);
    FastLED.show();
    chaseIndex = (chaseIndex + 1) % LED_COUNT;
}

void stepTestPattern() {
    switch (testPhase) {
    case 0:
        showSingleColor(CRGB::Red);
        break;
    case 1:
        showSingleColor(CRGB::Green);
        break;
    case 2:
        showSingleColor(CRGB::Blue);
        break;
    case 3:
        showSingleColor(CRGB::White);
        break;
    default:
        advanceChase();
        break;
    }

    testPhase++;
    if (testPhase > 8) {
        testPhase = 4; // stay in chase phase after primary colors
    }
}
} // namespace

void setup() {
    pinMode(LED_BUILTIN, OUTPUT);
    digitalWrite(LED_BUILTIN, HIGH); // Indicate sketch is running

    FastLED.addLeds<WS2812B, LED_PIN, GRB>(leds, LED_COUNT);
    FastLED.setBrightness(BRIGHTNESS);
    FastLED.clear(true);
}

void loop() {
    digitalWrite(LED_BUILTIN, millis() & 0x200 ? HIGH : LOW);

    const uint32_t now = millis();
    if (now - lastStep < STEP_INTERVAL_MS) {
        return;
    }
    lastStep = now;
    stepTestPattern();
}
