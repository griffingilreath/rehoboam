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
      lastHeartbeatMs_{0},
      notificationActive_{false},
      notificationEndMs_{0} {}

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

void StateMachine::triggerNotification(const NotificationPayload &payload) {
    notificationQueue_.push(payload);
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

void StateMachine::updateLedState(uint8_t index, uint8_t health, float activity, uint8_t type) {
    if (index < LED_COUNT) {
        ledData_[index].health = health;
        ledData_[index].activityLevel = static_cast<uint8_t>(activity * 255.0f);
        ledData_[index].activityType = type;
        lastHeartbeatMs_ = millis();
    }
}

CRGB *StateMachine::ledBuffer() {
    return leds_.data();
}

bool StateMachine::isFrameReady() const {
    return frameReady_;
}

CRGB StateMachine::getHealthColor(uint8_t healthCode) {
    switch (healthCode) {
        case 0: return COLOR_OFF;
        case 1: return COLOR_OK;
        case 2: return COLOR_WARN;
        case 3: return COLOR_ERR;
        case 4: return COLOR_UNK;
        default: return CRGB::Blue;
    }
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
        // Error flash: red
        if ((now / 500) % 2 == 0) {
            std::fill(leds_.begin(), leds_.end(), CRGB::Red);
        } else {
            std::fill(leds_.begin(), leds_.end(), CRGB::Black);
        }
        frameReady_ = true;
        return;
    }

    // Process Notifications
    if (notificationActive_) {
        if (now >= notificationEndMs_) {
            notificationActive_ = false;
        }
    }
    if (!notificationActive_ && !notificationQueue_.empty()) {
        const auto &payload = notificationQueue_.front();
        notificationEndMs_ = now + payload.ttlMs;
        notificationActive_ = true;
        notificationQueue_.pop();
    }

    if (notificationActive_) {
        // Notification animation: Pulse Blue/Cyan
        // Using built-in FastLED beatsin8 for smooth pulsing
        uint8_t brightness = beatsin8(60, 100, 255); 
        CRGB color = CRGB::Blue;
        if ((now / 200) % 2 == 0) color = CRGB::Cyan;
        
        std::fill(leds_.begin(), leds_.end(), color);
        for(auto &led : leds_) {
            led.nscale8(brightness);
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
    if (errorActive_ || alarmActive_ || currentState_ == BaseState::Startup) {
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
        CRGB baseColor = getHealthColor(data.health);

        // Apply activity modulation
        // Higher activity = faster pulse or brighter flash
        if (data.activityLevel > 0) {
             // Simple modulation: breathe brightness based on activity
             // Activity 0-255. 
             // We want a pulse that speeds up with activity.
             // Speed factor: 1.0 + (activity / 32.0) -> 1.0 to 9.0x speed
             float speed = 1.0f + (data.activityLevel / 32.0f);
             uint8_t brightness = beatsin8(10 * speed, 50, 255); // min 50, max 255
             
             leds_[i] = baseColor;
             leds_[i].nscale8(brightness);
             
             // If very high activity, flash white occasionally
             if (data.activityLevel > 200 && (now % 200 < 50)) {
                 leds_[i] = CRGB::White;
             }
        } else {
             // Solid color if no activity, slightly dimmed
             leds_[i] = baseColor;
             leds_[i].nscale8(200);
        }
    }
}

} // namespace controllers
} // namespace ledpanel
