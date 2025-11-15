#include "controllers/protocol_controller.hpp"

#include "controllers/state_types.hpp"

namespace ledpanel {
namespace controllers {

ProtocolController::ProtocolController(Stream &serial, StateMachine &stateMachine)
    : serial_{serial}, stateMachine_{stateMachine} {}

void ProtocolController::poll(uint32_t now) {
    (void)now;

    if (!serial_.available()) {
        return;
    }

    String line = serial_.readStringUntil('\n');
    line.trim();

    if (line.length() == 0) {
        return;
    }

    handleLine(line, now);
}

void ProtocolController::handleLine(const String &line, uint32_t now) {
    (void)now;

    if (line == "READY") {
        stateMachine_.requestReady();
        sendAck("READY");
        return;
    }

    if (line.startsWith("STATE:")) {
        const String stateVal = line.substring(6);
        if (stateVal == "LIVE") {
            stateMachine_.requestState(BaseState::Live);
            sendAck("STATE");
            return;
        }
        if (stateVal == "STANDBY") {
            stateMachine_.requestState(BaseState::Standby);
            sendAck("STATE");
            return;
        }
    }

    if (line.startsWith("ALARM:")) {
        const String remainder = line.substring(6);
        if (remainder.endsWith(":ON")) {
            AlarmPayload payload{remainder.substring(0, remainder.length() - 3).c_str()};
            stateMachine_.triggerAlarm(payload);
            sendAck("ALARM");
            return;
        }
        if (remainder.endsWith(":OFF")) {
            AlarmPayload payload{remainder.substring(0, remainder.length() - 4).c_str()};
            stateMachine_.clearAlarm(payload);
            sendAck("ALARM");
            return;
        }
    }

    if (line == "PING") {
        stateMachine_.resetError();
        sendAck("PING");
        return;
    }

    sendErr("UNHANDLED");
}

void ProtocolController::sendAck(const char *command) {
    serial_.print(F("ACK:"));
    serial_.println(command);
}

void ProtocolController::sendErr(const char *reason) {
    serial_.print(F("ERR:"));
    serial_.println(reason);
}

} // namespace controllers
} // namespace ledpanel
