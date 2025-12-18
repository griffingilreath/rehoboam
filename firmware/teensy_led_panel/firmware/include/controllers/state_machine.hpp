#pragma once

#include <array>
#include <cstdint>

#include <FastLED.h>

#include "config.hpp"
#include "controllers/state_types.hpp"

namespace ledpanel {
namespace controllers {

class StateMachine {
public:
    StateMachine();

    void init();
    void tick(uint32_t now);

    // State control
    void requestReady();
    void requestState(BaseState target);
    void triggerNotification(const NotificationPayload &payload);
    void triggerAlarm(const AlarmPayload &payload);
    void clearAlarm(const AlarmPayload &payload);
    void resetError();
    
    // Data input
    void updateLeds(const std::array<LedData, LED_COUNT> &data);

    // LED buffer access
    CRGB *ledBuffer();
    bool isFrameReady() const;

private:
    void resolveState(uint32_t now);
    void stepActiveState(uint32_t now);
    void renderLive(uint32_t now);

    BaseState currentState_;
    BaseState baseState_;
    bool startupReady_;
    bool alarmActive_;
    bool errorActive_;
    bool frameReady_;

    std::array<CRGB, LED_COUNT> leds_{};
    std::array<LedData, LED_COUNT> ledData_{};

    // Track timestamps
    uint32_t lastHeartbeatMs_;
};

} // namespace controllers
} // namespace ledpanel
