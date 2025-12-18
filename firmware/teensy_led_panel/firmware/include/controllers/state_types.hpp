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

// Raw data for a single LED received from the host
struct LedData {
    uint8_t health;         // 0=OFF, 1=OK, 2=WARN, 3=ERR, 4=UNK
    uint8_t activityLevel;  // 0-255
    uint8_t activityType;   // 0=None, 1=Light, 2=Blind, 3=DNS, 4=Block, 5=Generic
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
