/**
 * @file safety_state_machine.cpp
 * @brief Deterministic Safety State Machine Implementation
 *
 * IEC 61508 SIL 2+ Compliant
 * Formally verified via TLA+ (see formal/safety_node.tla)
 */

#include "lego_mcp_safety_certified/safety_state_machine.hpp"

namespace lego_mcp
{

// Static member definition
constexpr std::array<std::array<SafetyStateMachine::TransitionEntry, 9>, 5>
    SafetyStateMachine::TRANSITION_TABLE;

SafetyStateMachine::SafetyStateMachine(
    const StateMachineConfig& config,
    StateChangeCallback callback)
    : config_(config)
    , callback_(std::move(callback))
    , current_state_(SafetyState::ESTOP_ACTIVE)  // Start in safe state
    , state_entry_time_(std::chrono::steady_clock::now())
{
    // Initialize history buffer
    history_.fill(StateTransition{});
}

bool SafetyStateMachine::process_event(SafetyEvent event) noexcept
{
    if (event == SafetyEvent::NONE) {
        return false;
    }

    const auto transition = get_transition(current_state_, event);

    if (!transition.valid) {
        return false;
    }

    const SafetyState old_state = current_state_;
    current_state_ = transition.next_state;
    state_entry_time_ = std::chrono::steady_clock::now();

    record_transition(old_state, current_state_, event);

    if (callback_) {
        callback_(old_state, current_state_, event);
    }

    return true;
}

bool SafetyStateMachine::trigger_estop() noexcept
{
    if (current_state_ == SafetyState::LOCKOUT) {
        return false;  // Cannot transition from LOCKOUT
    }

    if (current_state_ == SafetyState::ESTOP_ACTIVE) {
        return true;  // Already in e-stop
    }

    const SafetyState old_state = current_state_;
    current_state_ = SafetyState::ESTOP_ACTIVE;
    state_entry_time_ = std::chrono::steady_clock::now();

    record_transition(old_state, current_state_, SafetyEvent::SOFTWARE_ESTOP);

    if (callback_) {
        callback_(old_state, current_state_, SafetyEvent::SOFTWARE_ESTOP);
    }

    return true;
}

bool SafetyStateMachine::request_reset(bool preconditions_met) noexcept
{
    if (current_state_ != SafetyState::ESTOP_ACTIVE) {
        return false;  // Can only reset from ESTOP_ACTIVE
    }

    if (!preconditions_met) {
        return false;  // Preconditions not satisfied
    }

    const SafetyState old_state = current_state_;
    current_state_ = SafetyState::NORMAL;
    state_entry_time_ = std::chrono::steady_clock::now();

    record_transition(old_state, current_state_, SafetyEvent::RESET_REQUEST);

    if (callback_) {
        callback_(old_state, current_state_, SafetyEvent::RESET_REQUEST);
    }

    return true;
}

bool SafetyStateMachine::trigger_lockout() noexcept
{
    if (current_state_ == SafetyState::LOCKOUT) {
        return true;  // Already locked out
    }

    const SafetyState old_state = current_state_;
    current_state_ = SafetyState::LOCKOUT;
    state_entry_time_ = std::chrono::steady_clock::now();

    record_transition(old_state, current_state_, SafetyEvent::MULTIPLE_FAULT);

    if (callback_) {
        callback_(old_state, current_state_, SafetyEvent::MULTIPLE_FAULT);
    }

    return true;
}

std::string_view SafetyStateMachine::state_name(SafetyState state) noexcept
{
    switch (state) {
        case SafetyState::NORMAL:
            return "NORMAL";
        case SafetyState::WARNING:
            return "WARNING";
        case SafetyState::ESTOP_PENDING:
            return "ESTOP_PENDING";
        case SafetyState::ESTOP_ACTIVE:
            return "ESTOP_ACTIVE";
        case SafetyState::LOCKOUT:
            return "LOCKOUT";
        default:
            return "UNKNOWN";
    }
}

std::string_view SafetyStateMachine::event_name(SafetyEvent event) noexcept
{
    switch (event) {
        case SafetyEvent::NONE:
            return "NONE";
        case SafetyEvent::HEARTBEAT_TIMEOUT:
            return "HEARTBEAT_TIMEOUT";
        case SafetyEvent::SOFTWARE_ESTOP:
            return "SOFTWARE_ESTOP";
        case SafetyEvent::HARDWARE_ESTOP:
            return "HARDWARE_ESTOP";
        case SafetyEvent::CHANNEL_DISAGREE:
            return "CHANNEL_DISAGREE";
        case SafetyEvent::RESET_REQUEST:
            return "RESET_REQUEST";
        case SafetyEvent::FAULT_CLEARED:
            return "FAULT_CLEARED";
        case SafetyEvent::MULTIPLE_FAULT:
            return "MULTIPLE_FAULT";
        case SafetyEvent::WATCHDOG_TIMEOUT:
            return "WATCHDOG_TIMEOUT";
        default:
            return "UNKNOWN";
    }
}

std::optional<StateTransition> SafetyStateMachine::last_transition() const noexcept
{
    if (transition_count_ == 0U) {
        return std::nullopt;
    }

    const std::size_t idx = (history_index_ == 0U) ?
        (history_.size() - 1U) : (history_index_ - 1U);

    return history_[idx];
}

std::chrono::milliseconds SafetyStateMachine::time_in_state() const noexcept
{
    const auto now = std::chrono::steady_clock::now();
    return std::chrono::duration_cast<std::chrono::milliseconds>(
        now - state_entry_time_);
}

bool SafetyStateMachine::is_valid_transition(SafetyEvent event) const noexcept
{
    return get_transition(current_state_, event).valid;
}

SafetyStateMachine::TransitionEntry SafetyStateMachine::get_transition(
    SafetyState state, SafetyEvent event) const noexcept
{
    const auto state_idx = static_cast<std::size_t>(state);
    const auto event_idx = static_cast<std::size_t>(event);

    if (state_idx >= TRANSITION_TABLE.size() ||
        event_idx >= TRANSITION_TABLE[0].size()) {
        return {state, false};  // Invalid indices - no transition
    }

    return TRANSITION_TABLE[state_idx][event_idx];
}

void SafetyStateMachine::record_transition(
    SafetyState from, SafetyState to, SafetyEvent event) noexcept
{
    StateTransition record{};
    record.from_state = from;
    record.to_state = to;
    record.trigger_event = event;
    record.timestamp = std::chrono::steady_clock::now();
    record.sequence_number = transition_count_;

    history_[history_index_] = record;
    history_index_ = (history_index_ + 1U) % history_.size();
    ++transition_count_;
}

}  // namespace lego_mcp
