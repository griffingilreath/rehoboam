#pragma once

#include <cstdint>
#include <optional>
#include <string>

namespace ledpanel {
namespace controllers {

enum class BaseState : uint8_t {
    Startup,
    Live,
    Standby,
};

enum class PriorityState : uint8_t {
    None,
    Notification,
    Alarm,
    Error
};

struct NotificationPayload {
    std::string type;
    uint32_t ttlMs{5000};
};

struct AlarmPayload {
    std::string id;
};

struct StateTransitionContext {
    BaseState baseState;
    PriorityState priorityState;
};

} // namespace controllers
} // namespace ledpanel
