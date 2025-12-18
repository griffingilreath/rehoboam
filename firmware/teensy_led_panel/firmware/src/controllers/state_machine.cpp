#include "controllers/state_machine.hpp"

#include <algorithm>

namespace ledpanel {
namespace controllers {

// Color definitions (R, G, B)
const CRGB COLOR_OFF = CRGB::Black;
const CRGB COLOR_OK = CRGB::Green;
const CRGB COLOR_WARN = CRGB(255, 140, 0); // DarkOrange
const CRGB COLOR_ERR = CRGB::Red;
const CRGB COLOR_UNK = CRGB::Purple;

StateMachine::StateMachine()
    : currentState_{BaseState::Startup},
      baseState_{BaseState::Standby},
      startupReady_{false},
      alarmActive_{false},
      errorActive_{false},
      frameReady_{false},
      lastHeartbeatMs_{0} {}

void StateMachine::init() {
    std::fill(leds_.begin(), leds_.end(), CRGB::Black);
    frameReady_ = true;
}

void StateMachine::tick(uint32_t now) {
    if (!errorActive_ && (now - lastHeartbeatMs_) > HOST_HEARTBEAT_TIMEOUT_MS) {
        errorActive_ = true;
    }

    resolveState(now);
    stepActiveState(now);
}

void StateMachine::requestReady() {
    startupReady_ = true;
}

void StateMachine::requestState(BaseState target) {
    baseState_ = target;
}

void StateMachine::triggerNotification(const NotificationPayload &) {
    // TODO: enqueue notification
}

void StateMachine::triggerAlarm(const AlarmPayload &) {
    alarmActive_ = true;
}

void StateMachine::clearAlarm(const AlarmPayload &) {
    alarmActive_ = false;
}

void StateMachine::resetError() {
    errorActive_ = false;
    lastHeartbeatMs_ = millis();
}

void StateMachine::updateLeds(const std::array<LedData, LED_COUNT> &data) {
    ledData_ = data;
    lastHeartbeatMs_ = millis(); // Valid data implies heartbeat
}

CRGB *StateMachine::ledBuffer() {
    return leds_.data();
}

bool StateMachine::isFrameReady() const {
    return frameReady_;
}

void StateMachine::resolveState(uint32_t now) {
    (void)now;

    if (alarmActive_) {
        // Alarm behavior: Flash Orange
        if ((now / 250) % 2 == 0) {
            std::fill(leds_.begin(), leds_.end(), COLOR_WARN);
        } else {
            std::fill(leds_.begin(), leds_.end(), COLOR_OFF);
        }
        frameReady_ = true;
        return;
    }

    if (errorActive_) {
        // TODO: switch to error handler
        // For now, just flash red
        if ((now / 500) % 2 == 0) {
            std::fill(leds_.begin(), leds_.end(), CRGB::Red);
        } else {
            std::fill(leds_.begin(), leds_.end(), CRGB::Black);
        }
        frameReady_ = true;
        return;
    }

    if (currentState_ == BaseState::Startup) {
        if (startupReady_) {
            currentState_ = baseState_;
        } else {
             // Startup animation: Knight Rider scanner in Blue
             uint8_t pos = (now / 100) % LED_COUNT;
             std::fill(leds_.begin(), leds_.end(), CRGB::Black);
             leds_[pos] = CRGB::Blue;
             frameReady_ = true;
        }
        return;
    }

    currentState_ = baseState_;
}

void StateMachine::stepActiveState(uint32_t now) {
    if (errorActive_ || currentState_ == BaseState::Startup) {
        return; 
    }
    
    if (currentState_ == BaseState::Standby) {
        std::fill(leds_.begin(), leds_.end(), CRGB::Black);
        frameReady_ = true;
        return;
    }

    if (currentState_ == BaseState::Live) {
        renderLive(now);
        frameReady_ = true;
    }
}

void StateMachine::renderLive(uint32_t now) {
    for (size_t i = 0; i < LED_COUNT; i++) {
        const auto &data = ledData_[i];
        CRGB baseColor = COLOR_OFF;
        
        switch (data.health) {
            case 1: baseColor = COLOR_OK; break;
            case 2: baseColor = COLOR_WARN; break;
            case 3: baseColor = COLOR_ERR; break;
            case 4: baseColor = COLOR_UNK; break;
            default: baseColor = COLOR_OFF; break;
        }

        // Apply activity modulation
        // Higher activity = faster pulse or brighter flash
        if (data.activityLevel > 0) {
             // Simple modulation: breathe brightness based on activity
             // Activity 0-255. 
             // We want a pulse that speeds up with activity.
             // Speed factor: 1.0 + (activity / 32.0) -> 1.0 to 9.0x speed
             float speed = 1.0f + (data.activityLevel / 32.0f);
             uint8_t brightness = beatsin8(10 * speed, 50, 255); // min 50, max 255
             
             // If activity type indicates a "block" or "event", maybe tint?
             // For now, keep it simple: just modulate brightness
             
             leds_[i] = baseColor;
             leds_[i].nscale8(brightness);
        } else {
             // Solid color if no activity
             leds_[i] = baseColor;
             // Dim it slightly if just static to save power?
             // leds_[i].nscale8(200);
        }
    }
}

} // namespace controllers
} // namespace ledpanel
