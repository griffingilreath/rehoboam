#pragma once

#include <Stream.h>
#include <ArduinoJson.h>

#include "controllers/state_machine.hpp"

namespace ledpanel {
namespace controllers {

class ProtocolController {
public:
    ProtocolController(Stream &serial, StateMachine &stateMachine);

    void poll(uint32_t now);

private:
    void handleLine(const String &line, uint32_t now);
    void handleBinaryFrame(uint32_t now);
    void sendAck(const char *command);
    void sendErr(const char *reason);

    Stream &serial_;
    StateMachine &stateMachine_;
    
    // Buffer for incoming serial data
    static const size_t BUFFER_SIZE = 4096;
    char inputBuffer_[BUFFER_SIZE];
    size_t bufferIndex_{0};

    // JsonDocument for parsing frames
    // Size calculated to hold ~16 LEDs worth of data + metadata
    JsonDocument jsonDoc_;
};

} // namespace controllers
} // namespace ledpanel
