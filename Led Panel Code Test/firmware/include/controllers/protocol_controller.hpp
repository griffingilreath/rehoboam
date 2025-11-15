#pragma once

#include <Stream.h>

#include "controllers/state_machine.hpp"

namespace ledpanel {
namespace controllers {

class ProtocolController {
public:
    ProtocolController(Stream &serial, StateMachine &stateMachine);

    void poll(uint32_t now);

private:
    void handleLine(const String &line, uint32_t now);
    void sendAck(const char *command);
    void sendErr(const char *reason);

    Stream &serial_;
    StateMachine &stateMachine_;
};

} // namespace controllers
} // namespace ledpanel
