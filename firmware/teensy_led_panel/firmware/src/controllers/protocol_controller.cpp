#include "controllers/protocol_controller.hpp"

#include "controllers/state_types.hpp"
#include "config.hpp"

namespace ledpanel {
namespace controllers {

static constexpr uint8_t START_MARKER = 0xBE;
static constexpr uint8_t END_MARKER = 0xED;
static constexpr size_t LED_FRAME_SIZE = 1 + (LED_COUNT * 3) + 1; // Start + 16*3 + End = 50

ProtocolController::ProtocolController(Stream &serial, StateMachine &stateMachine)
    : serial_{serial}, stateMachine_{stateMachine} {}

void ProtocolController::poll(uint32_t now) {
    if (!serial_.available()) {
        return;
    }

    // Check for binary frame start
    if (serial_.peek() == START_MARKER) {
        if (serial_.available() >= static_cast<int>(LED_FRAME_SIZE)) {
            handleBinaryFrame(now);
        }
        return;
    }

    // Otherwise treat as text command
    String line = serial_.readStringUntil('\n');
    line.trim();

    if (line.length() == 0) {
        return;
    }

    handleLine(line, now);
}

void ProtocolController::handleBinaryFrame(uint32_t now) {
    (void)now;
    
    // Buffer to hold the frame
    uint8_t buffer[LED_FRAME_SIZE];
    
    // Read the full frame
    size_t read = serial_.readBytes(buffer, LED_FRAME_SIZE);
    
    if (read != LED_FRAME_SIZE) {
        // Should not happen if available() check passed, but safety first
        return;
    }

    // Verify footer
    if (buffer[LED_FRAME_SIZE - 1] != END_MARKER) {
        // Invalid frame, flush and ignore
        // We consumed the start marker and some bytes, effectively resyncing
        sendErr("BAD_FRAME");
        return;
    }

    std::array<LedData, LED_COUNT> data;
    size_t offset = 1; // Skip start marker
    
    for (size_t i = 0; i < LED_COUNT; i++) {
        data[i].health = buffer[offset++];
        data[i].activityLevel = buffer[offset++];
        data[i].activityType = buffer[offset++];
    }

    stateMachine_.updateLeds(data);
    // No ACK for binary frames to save bandwidth/latency
}

void ProtocolController::handleLine(const String &line, uint32_t now) {
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

    if (line.startsWith("NOTIFY:")) {
        String remainder = line.substring(7);
        int separatorIdx = remainder.indexOf(':');

        if (separatorIdx != -1) {
            String typeStr = remainder.substring(0, separatorIdx);
            String ttlStr = remainder.substring(separatorIdx + 1);

            NotificationPayload payload;
            payload.type = typeStr.c_str();
            payload.ttlMs = ttlStr.toInt();

            stateMachine_.triggerNotification(payload);
            sendAck("NOTIFY");
            return;
        }
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
