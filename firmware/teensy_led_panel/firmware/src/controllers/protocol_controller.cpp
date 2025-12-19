#include "controllers/protocol_controller.hpp"

#include "controllers/state_types.hpp"

namespace ledpanel {
namespace controllers {

ProtocolController::ProtocolController(Stream &serial, StateMachine &stateMachine)
    : serial_{serial}, stateMachine_{stateMachine} {}

void ProtocolController::poll(uint32_t now) {
    while (serial_.available() > 0) {
        char c = serial_.read();
        
        if (c == '\n') {
            inputBuffer_[bufferIndex_] = '\0'; // Null-terminate
            handleLine(inputBuffer_, now);
            bufferIndex_ = 0; // Reset buffer
        } else {
            if (bufferIndex_ < BUFFER_SIZE - 1) {
                inputBuffer_[bufferIndex_++] = c;
            } else {
                // Overflow - reset buffer and log error if possible
                bufferIndex_ = 0;
                sendErr("BUFFER_OVERFLOW");
            }
        }
    }
}

void ProtocolController::handleLine(const char* line, uint32_t now) {
    (void)now;

    // Check if it's a JSON frame (starts with '{')
    if (line[0] == '{') {
        DeserializationError error = deserializeJson(jsonDoc_, line);
        
        if (error) {
            sendErr("JSON_PARSE_ERROR");
            return;
        }

        JsonArray leds = jsonDoc_["leds"];
        if (leds.isNull()) {
            sendErr("INVALID_FRAME");
            return;
        }

        for (JsonVariant v : leds) {
            uint8_t i = v["i"];
            uint8_t h = v["h"];
            float a = v["a"];
            uint8_t t = v["t"];
            
            stateMachine_.updateLedState(i, h, a, t);
        }
        
        stateMachine_.resetError(); // Valid frame = heartbeat
        // Optional: send ACK for frame, or stay silent to reduce traffic
        // sendAck("FRAME"); 
        return;
    }

    // Legacy/Simple text commands
    String lineStr = String(line);
    lineStr.trim();
    
    if (lineStr.length() == 0) return;

    if (lineStr == "READY") {
        stateMachine_.requestReady();
        sendAck("READY");
        return;
    }

    if (lineStr.startsWith("STATE:")) {
        const String stateVal = lineStr.substring(6);
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

    if (lineStr.startsWith("ALARM:")) {
        const String remainder = lineStr.substring(6);
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

    if (lineStr == "PING") {
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
