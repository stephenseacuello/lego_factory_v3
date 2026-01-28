/**
 * @file safety_state_machine.hpp
 * @brief Deterministic Safety State Machine
 *
 * IEC 61508 SIL 2+ Compliant State Machine Implementation
 *
 * This state machine is formally verified using TLA+ (see formal/safety_node.tla)
 * to guarantee the following safety properties:
 *
 * INVARIANTS:
 * - I1: State transitions are deterministic
 * - I2: ESTOP_ACTIVE can only transition to LOCKOUT or NORMAL (via safe reset)
 * - I3: LOCKOUT is terminal (requires hardware intervention)
 *
 * SAFETY PROPERTIES:
 * - P1: E-stop request always succeeds within bounded time
 * - P2: No transition from ESTOP to NORMAL without explicit reset
 * - P3: Multiple simultaneous faults -> LOCKOUT
 *
 * TIMING:
 * - All transitions complete within 1ms (formally verified WCET)
 */

#ifndef LEGO_MCP_SAFETY_CERTIFIED__SAFETY_STATE_MACHINE_HPP_
#define LEGO_MCP_SAFETY_CERTIFIED__SAFETY_STATE_MACHINE_HPP_

#include <array>
#include <atomic>
#include <chrono>
#include <cstdint>
#include <functional>
#include <optional>
#include <string_view>

namespace lego_mcp
{

/**
 * @brief Safety states (matches TLA+ specification)
 */
enum class SafetyState : std::uint8_t
{
    NORMAL = 0U,          ///< Normal operation - all systems go
    WARNING = 1U,         ///< Warning condition - limited operation
    ESTOP_PENDING = 2U,   ///< E-stop requested, executing
    ESTOP_ACTIVE = 3U,    ///< E-stop active - all motion stopped
    LOCKOUT = 4U          ///< Lockout - requires hardware reset
};

/**
 * @brief Safety events that trigger transitions
 */
enum class SafetyEvent : std::uint8_t
{
    NONE = 0U,
    HEARTBEAT_TIMEOUT = 1U,
    SOFTWARE_ESTOP = 2U,
    HARDWARE_ESTOP = 3U,
    CHANNEL_DISAGREE = 4U,
    RESET_REQUEST = 5U,
    FAULT_CLEARED = 6U,
    MULTIPLE_FAULT = 7U,
    WATCHDOG_TIMEOUT = 8U
};

/**
 * @brief State transition record for audit trail
 */
struct StateTransition
{
    SafetyState from_state;
    SafetyState to_state;
    SafetyEvent trigger_event;
    std::chrono::steady_clock::time_point timestamp;
    std::uint32_t sequence_number;
};

/**
 * @brief State machine configuration
 */
struct StateMachineConfig
{
    /// Maximum transitions to record in history
    std::size_t history_size{100U};

    /// Enable strict mode (reject invalid transitions)
    bool strict_mode{true};

    /// Require two-key reset (extra safety)
    bool require_two_key_reset{false};

    /// Timeout for ESTOP_PENDING -> ESTOP_ACTIVE
    std::chrono::milliseconds pending_timeout{10};
};

/**
 * @brief Deterministic Safety State Machine
 *
 * Implements a formally verified state machine for safety-critical control.
 * All transitions are deterministic and complete within bounded time.
 *
 * STATE DIAGRAM:
 * ```
 *                    ┌──────────────────────────────────────────┐
 *                    │                                          │
 *     ┌──────┐   ┌───▼────┐   ┌──────────────┐   ┌────────────┐ │
 *     │NORMAL├──►│WARNING ├──►│ ESTOP_PENDING├──►│ESTOP_ACTIVE│─┘
 *     └──┬───┘   └────────┘   └──────────────┘   └─────┬──────┘
 *        │           │                │                 │
 *        │           │                │                 │
 *        │           └────────────────┼─────────────────┤
 *        │                            │                 │
 *        │           ┌────────────────┘                 │
 *        │           │                                  │
 *        │           ▼                                  ▼
 *        │      IMMEDIATE E-STOP                   ┌────────┐
 *        │      (bypass pending)                   │LOCKOUT │
 *        │                                         └────────┘
 *        │                                              ▲
 *        └──────────────────────────────────────────────┘
 *                    (multiple faults)
 * ```
 *
 * @note This class is NOT thread-safe. External synchronization required.
 */
class SafetyStateMachine
{
public:
    /// Callback type for state change notification
    using StateChangeCallback = std::function<void(SafetyState, SafetyState, SafetyEvent)>;

    /**
     * @brief Construct with configuration
     *
     * @param config State machine configuration
     * @param callback Optional callback for state changes
     */
    explicit SafetyStateMachine(
        const StateMachineConfig& config = StateMachineConfig{},
        StateChangeCallback callback = nullptr);

    /**
     * @brief Get current state
     */
    [[nodiscard]] SafetyState current_state() const noexcept
    {
        return current_state_;
    }

    /**
     * @brief Check if in safe state (e-stop active or lockout)
     */
    [[nodiscard]] bool is_safe() const noexcept
    {
        return current_state_ == SafetyState::ESTOP_ACTIVE ||
               current_state_ == SafetyState::LOCKOUT;
    }

    /**
     * @brief Check if operational (NORMAL or WARNING)
     */
    [[nodiscard]] bool is_operational() const noexcept
    {
        return current_state_ == SafetyState::NORMAL ||
               current_state_ == SafetyState::WARNING;
    }

    /**
     * @brief Check if locked out (requires hardware reset)
     */
    [[nodiscard]] bool is_locked_out() const noexcept
    {
        return current_state_ == SafetyState::LOCKOUT;
    }

    /**
     * @brief Process event and transition state
     *
     * WCET: < 100us
     *
     * @param event The event to process
     * @return true if transition occurred, false if rejected
     */
    [[nodiscard]] bool process_event(SafetyEvent event) noexcept;

    /**
     * @brief Trigger immediate e-stop
     *
     * Bypasses ESTOP_PENDING and goes directly to ESTOP_ACTIVE.
     * Always succeeds unless already in LOCKOUT.
     *
     * WCET: < 50us
     *
     * @return true if e-stop activated
     */
    [[nodiscard]] bool trigger_estop() noexcept;

    /**
     * @brief Request reset from e-stop state
     *
     * Only succeeds if:
     * - Currently in ESTOP_ACTIVE (not LOCKOUT)
     * - All preconditions met (no faults, button released, etc.)
     *
     * @param preconditions_met External verification of reset preconditions
     * @return true if reset succeeded
     */
    [[nodiscard]] bool request_reset(bool preconditions_met) noexcept;

    /**
     * @brief Trigger lockout (terminal state)
     *
     * Called on multiple simultaneous faults or unrecoverable error.
     * Requires hardware intervention to recover.
     *
     * @return true (always succeeds)
     */
    bool trigger_lockout() noexcept;

    /**
     * @brief Get state name as string
     */
    [[nodiscard]] static std::string_view state_name(SafetyState state) noexcept;

    /**
     * @brief Get event name as string
     */
    [[nodiscard]] static std::string_view event_name(SafetyEvent event) noexcept;

    /**
     * @brief Get last transition
     */
    [[nodiscard]] std::optional<StateTransition> last_transition() const noexcept;

    /**
     * @brief Get transition count
     */
    [[nodiscard]] std::uint32_t transition_count() const noexcept
    {
        return transition_count_;
    }

    /**
     * @brief Get time in current state
     */
    [[nodiscard]] std::chrono::milliseconds time_in_state() const noexcept;

    /**
     * @brief Check if transition is valid
     *
     * For debugging/verification - checks if event would cause valid transition.
     */
    [[nodiscard]] bool is_valid_transition(SafetyEvent event) const noexcept;

private:
    /**
     * @brief Transition table entry
     */
    struct TransitionEntry
    {
        SafetyState next_state;
        bool valid;
    };

    /**
     * @brief Get transition for current state and event
     */
    [[nodiscard]] TransitionEntry get_transition(
        SafetyState state, SafetyEvent event) const noexcept;

    /**
     * @brief Record transition to history
     */
    void record_transition(
        SafetyState from, SafetyState to, SafetyEvent event) noexcept;

    /// Configuration
    StateMachineConfig config_;

    /// State change callback
    StateChangeCallback callback_;

    /// Current state
    SafetyState current_state_{SafetyState::ESTOP_ACTIVE};  // Start in safe state

    /// Transition history (circular buffer)
    std::array<StateTransition, 100> history_;
    std::size_t history_index_{0U};

    /// Statistics
    std::uint32_t transition_count_{0U};
    std::chrono::steady_clock::time_point state_entry_time_;

    /// Static transition table (5 states x 9 events)
    static constexpr std::array<std::array<TransitionEntry, 9>, 5> TRANSITION_TABLE = {{
        // NORMAL state transitions
        {{
            {SafetyState::NORMAL, false},       // NONE
            {SafetyState::ESTOP_ACTIVE, true},  // HEARTBEAT_TIMEOUT
            {SafetyState::ESTOP_ACTIVE, true},  // SOFTWARE_ESTOP
            {SafetyState::ESTOP_ACTIVE, true},  // HARDWARE_ESTOP
            {SafetyState::ESTOP_ACTIVE, true},  // CHANNEL_DISAGREE
            {SafetyState::NORMAL, false},       // RESET_REQUEST (invalid)
            {SafetyState::NORMAL, false},       // FAULT_CLEARED (no-op)
            {SafetyState::LOCKOUT, true},       // MULTIPLE_FAULT
            {SafetyState::ESTOP_ACTIVE, true},  // WATCHDOG_TIMEOUT
        }},
        // WARNING state transitions
        {{
            {SafetyState::WARNING, false},      // NONE
            {SafetyState::ESTOP_ACTIVE, true},  // HEARTBEAT_TIMEOUT
            {SafetyState::ESTOP_ACTIVE, true},  // SOFTWARE_ESTOP
            {SafetyState::ESTOP_ACTIVE, true},  // HARDWARE_ESTOP
            {SafetyState::ESTOP_ACTIVE, true},  // CHANNEL_DISAGREE
            {SafetyState::WARNING, false},      // RESET_REQUEST (invalid)
            {SafetyState::NORMAL, true},        // FAULT_CLEARED
            {SafetyState::LOCKOUT, true},       // MULTIPLE_FAULT
            {SafetyState::ESTOP_ACTIVE, true},  // WATCHDOG_TIMEOUT
        }},
        // ESTOP_PENDING state transitions
        {{
            {SafetyState::ESTOP_PENDING, false}, // NONE
            {SafetyState::ESTOP_ACTIVE, true},   // HEARTBEAT_TIMEOUT -> immediate
            {SafetyState::ESTOP_ACTIVE, true},   // SOFTWARE_ESTOP -> immediate
            {SafetyState::ESTOP_ACTIVE, true},   // HARDWARE_ESTOP -> immediate
            {SafetyState::ESTOP_ACTIVE, true},   // CHANNEL_DISAGREE -> immediate
            {SafetyState::ESTOP_PENDING, false}, // RESET_REQUEST (invalid)
            {SafetyState::ESTOP_PENDING, false}, // FAULT_CLEARED (pending)
            {SafetyState::LOCKOUT, true},        // MULTIPLE_FAULT
            {SafetyState::ESTOP_ACTIVE, true},   // WATCHDOG_TIMEOUT -> immediate
        }},
        // ESTOP_ACTIVE state transitions
        {{
            {SafetyState::ESTOP_ACTIVE, false},  // NONE
            {SafetyState::ESTOP_ACTIVE, false},  // HEARTBEAT_TIMEOUT (already e-stop)
            {SafetyState::ESTOP_ACTIVE, false},  // SOFTWARE_ESTOP (already e-stop)
            {SafetyState::ESTOP_ACTIVE, false},  // HARDWARE_ESTOP (already e-stop)
            {SafetyState::ESTOP_ACTIVE, false},  // CHANNEL_DISAGREE (already e-stop)
            {SafetyState::NORMAL, true},         // RESET_REQUEST (if preconditions met)
            {SafetyState::ESTOP_ACTIVE, false},  // FAULT_CLEARED (need reset)
            {SafetyState::LOCKOUT, true},        // MULTIPLE_FAULT
            {SafetyState::ESTOP_ACTIVE, false},  // WATCHDOG_TIMEOUT (already e-stop)
        }},
        // LOCKOUT state transitions (terminal - no valid transitions)
        {{
            {SafetyState::LOCKOUT, false},  // NONE
            {SafetyState::LOCKOUT, false},  // HEARTBEAT_TIMEOUT
            {SafetyState::LOCKOUT, false},  // SOFTWARE_ESTOP
            {SafetyState::LOCKOUT, false},  // HARDWARE_ESTOP
            {SafetyState::LOCKOUT, false},  // CHANNEL_DISAGREE
            {SafetyState::LOCKOUT, false},  // RESET_REQUEST
            {SafetyState::LOCKOUT, false},  // FAULT_CLEARED
            {SafetyState::LOCKOUT, false},  // MULTIPLE_FAULT
            {SafetyState::LOCKOUT, false},  // WATCHDOG_TIMEOUT
        }},
    }};
};

}  // namespace lego_mcp

#endif  // LEGO_MCP_SAFETY_CERTIFIED__SAFETY_STATE_MACHINE_HPP_
