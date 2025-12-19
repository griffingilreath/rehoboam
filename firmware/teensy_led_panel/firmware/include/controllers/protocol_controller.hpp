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
    StaticJsonDocument<1024> jsonDoc_;
};

} // namespace controllers
} // namespace ledpanel
