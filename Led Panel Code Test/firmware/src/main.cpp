#include <Arduino.h>
#include <FastLED.h>

#include "config.hpp"
#include "controllers/state_machine.hpp"
#include "controllers/protocol_controller.hpp"

using namespace ledpanel;

static controllers::StateMachine stateMachine;
static controllers::ProtocolController protocolController{Serial, stateMachine};

void setup() {
    FastLED.addLeds<NEOPIXEL, LED_DATA_PIN>(stateMachine.ledBuffer(), LED_COUNT);
    FastLED.setBrightness(DEFAULT_BRIGHTNESS);

    Serial.begin(SERIAL_BAUD_RATE);
    while (!Serial && millis() < SERIAL_START_TIMEOUT_MS) {
        // Wait for host connection or timeout to allow autonomous start
    }

    stateMachine.init();
}

void loop() {
    const uint32_t now = millis();

    protocolController.poll(now);
    stateMachine.tick(now);

    if (stateMachine.isFrameReady()) {
        FastLED.show();
    }
}
