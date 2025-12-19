#include "controllers/state_machine.hpp"

#include <algorithm>

namespace ledpanel {
namespace controllers {

StateMachine::StateMachine()
    : currentState_{BaseState::Startup},
      baseState_{BaseState::Startup},
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

void StateMachine::updateLedState(uint8_t index, uint8_t health, float activity, uint8_t type) {
    if (index < LED_COUNT) {
        logicalLeds_[index] = {health, activity, type};
    }
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
        // TODO: switch to alarm handler
        return;
    }

    if (errorActive_) {
        // Simple error flash
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
        }
        return;
    }

    currentState_ = baseState_;
}

CRGB StateMachine::getHealthColor(uint8_t healthCode) {
    switch (healthCode) {
        case 0: return CRGB::Green;
        case 1: return CRGB::Orange;
        case 2: return CRGB::Red;
        case 3: return CRGB::Grey;
        case 4: return CRGB::Purple;
        default: return CRGB::Blue;
    }
}

void StateMachine::stepActiveState(uint32_t now) {
    (void)now;
    
    if (errorActive_ || alarmActive_) return;

    if (currentState_ == BaseState::Standby) {
        std::fill(leds_.begin(), leds_.end(), CRGB::Black);
        frameReady_ = true;
        return;
    }

    // BaseState::Live or Startup
    for (size_t i = 0; i < LED_COUNT; ++i) {
        const auto &logical = logicalLeds_[i];
        CRGB color = getHealthColor(logical.healthCode);
        
        // Apply activity pulse
        // Map activity 0.0-1.0 to a brightness or saturation effect
        // For simple visualization: high activity = brighter or pulsing
        if (logical.activityLevel > 0.01f) {
            uint8_t pulse = beatsin8(60 + (int)(logical.activityLevel * 60), 100, 255);
            color.nscale8(pulse);
            
            // If very high activity, flash white occasionally
            if (logical.activityLevel > 0.8f && (now % 200 < 50)) {
                 color = CRGB::White;
            }
        } else {
             // Static dim if no activity
             color.nscale8(50);
        }
        leds_[i] = color;
    }
    
    frameReady_ = true;
}

} // namespace controllers
} // namespace ledpanel
