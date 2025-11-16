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
        // TODO: switch to error handler
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

void StateMachine::stepActiveState(uint32_t now) {
    (void)now;
    frameReady_ = true;
    // TODO: invoke concrete animation handlers
}

} // namespace controllers
} // namespace ledpanel
