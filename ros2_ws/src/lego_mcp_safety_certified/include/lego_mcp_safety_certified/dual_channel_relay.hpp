/**
 * @file dual_channel_relay.hpp
 * @brief Dual-Channel Redundant E-Stop Relay Controller
 *
 * IEC 61508 SIL 2+ Hardware Fault Tolerance (HFT=1)
 *
 * Implements dual-channel architecture with:
 * - Independent relay control paths
 * - Cross-channel monitoring
 * - Disagreement detection and safe state enforcement
 * - Diagnostic coverage > 99%
 *
 * HARDWARE REQUIREMENTS:
 * - Two independent relay circuits
 * - Normally-closed (NC) contacts for fail-safe
 * - Readback capability on each channel
 * - Independent power supplies recommended
 *
 * SAFETY PROPERTIES (formally verified via TLA+):
 * - P1: Estop active => both relays open
 * - P2: Channel disagreement => trigger estop within 10ms
 * - P3: Single channel failure => system remains safe
 */

#ifndef LEGO_MCP_SAFETY_CERTIFIED__DUAL_CHANNEL_RELAY_HPP_
#define LEGO_MCP_SAFETY_CERTIFIED__DUAL_CHANNEL_RELAY_HPP_

#include <atomic>
#include <chrono>
#include <cstdint>
#include <functional>
#include <optional>

namespace lego_mcp
{

/**
 * @brief Relay state enumeration
 */
enum class RelayState : std::uint8_t
{
    CLOSED = 0U,  ///< Relay closed (power flowing)
    OPEN = 1U,    ///< Relay open (power cut - safe state)
    UNKNOWN = 2U, ///< State unknown (readback failure)
    FAULT = 3U    ///< Fault detected
};

/**
 * @brief Channel fault type
 */
enum class ChannelFault : std::uint8_t
{
    NONE = 0U,
    STUCK_CLOSED = 1U,    ///< Relay won't open (dangerous)
    STUCK_OPEN = 2U,      ///< Relay won't close (safe failure)
    READBACK_MISMATCH = 3U, ///< Command vs readback disagree
    COMMUNICATION_LOSS = 4U, ///< GPIO communication failure
    CROSS_CHANNEL_DISAGREE = 5U ///< Channels in different states
};

/**
 * @brief Single relay channel status
 */
struct ChannelStatus
{
    RelayState commanded_state{RelayState::OPEN};
    RelayState actual_state{RelayState::UNKNOWN};
    ChannelFault fault{ChannelFault::NONE};
    std::uint64_t activation_count{0U};
    std::chrono::steady_clock::time_point last_transition;
    std::chrono::microseconds response_time{0};
};

/**
 * @brief Dual-channel relay controller configuration
 */
struct DualChannelConfig
{
    // GPIO pins
    std::uint8_t primary_output_pin{17U};
    std::uint8_t primary_readback_pin{24U};
    std::uint8_t secondary_output_pin{27U};
    std::uint8_t secondary_readback_pin{25U};

    // Polarity
    bool output_active_low{true};
    bool readback_active_low{true};

    // Timing
    std::chrono::microseconds debounce_time{50000};
    std::chrono::microseconds max_response_time{5000};  // 5ms max relay response
    std::chrono::microseconds cross_check_interval{10000}; // 10ms cross-check

    // Diagnostics
    bool enable_readback{true};
    bool enable_cross_monitoring{true};
};

/**
 * @brief Dual-Channel Redundant Relay Controller
 *
 * Provides fault-tolerant e-stop relay control with:
 * - Independent control of two relay channels
 * - Continuous cross-channel monitoring
 * - Automatic safe state on disagreement
 * - Diagnostic coverage reporting
 *
 * INVARIANTS (enforced by design):
 * - Both channels commanded to same state
 * - Disagreement triggers immediate safe state
 * - Open (safe) state is fail-safe default
 *
 * @note This class is NOT thread-safe. External synchronization required.
 */
class DualChannelRelay
{
public:
    /// Callback type for fault notification
    using FaultCallback = std::function<void(ChannelFault, const char*)>;

    /**
     * @brief Construct with configuration
     *
     * @param config Dual-channel configuration
     * @param fault_callback Optional callback for fault notification
     */
    explicit DualChannelRelay(
        const DualChannelConfig& config,
        FaultCallback fault_callback = nullptr);

    /**
     * @brief Destructor - ensures safe state
     */
    ~DualChannelRelay();

    // Disable copy/move
    DualChannelRelay(const DualChannelRelay&) = delete;
    DualChannelRelay& operator=(const DualChannelRelay&) = delete;
    DualChannelRelay(DualChannelRelay&&) = delete;
    DualChannelRelay& operator=(DualChannelRelay&&) = delete;

    /**
     * @brief Initialize GPIO hardware
     *
     * @return true if both channels initialized successfully
     */
    [[nodiscard]] bool initialize();

    /**
     * @brief Shutdown GPIO hardware
     *
     * Sets both channels to safe (open) state before cleanup.
     */
    void shutdown() noexcept;

    /**
     * @brief Open both relay channels (SAFE STATE)
     *
     * This is the primary safety function.
     * WCET: < 500us
     *
     * @return true if both channels opened successfully
     */
    [[nodiscard]] bool open() noexcept;

    /**
     * @brief Close both relay channels (operational state)
     *
     * Only allowed when no faults are present.
     *
     * @return true if both channels closed successfully
     */
    [[nodiscard]] bool close() noexcept;

    /**
     * @brief Check if relays are in safe (open) state
     *
     * Verifies both channels via readback.
     */
    [[nodiscard]] bool is_open() const noexcept;

    /**
     * @brief Check if relays are closed (operational)
     *
     * Verifies both channels via readback.
     */
    [[nodiscard]] bool is_closed() const noexcept;

    /**
     * @brief Perform cross-channel consistency check
     *
     * Compares both channels for state agreement.
     * Triggers fault callback on disagreement.
     *
     * WCET: < 100us
     *
     * @return true if channels agree
     */
    [[nodiscard]] bool cross_check() noexcept;

    /**
     * @brief Get primary channel status
     */
    [[nodiscard]] const ChannelStatus& primary_status() const noexcept
    {
        return primary_status_;
    }

    /**
     * @brief Get secondary channel status
     */
    [[nodiscard]] const ChannelStatus& secondary_status() const noexcept
    {
        return secondary_status_;
    }

    /**
     * @brief Check if any fault is active
     */
    [[nodiscard]] bool has_fault() const noexcept
    {
        return primary_status_.fault != ChannelFault::NONE ||
               secondary_status_.fault != ChannelFault::NONE;
    }

    /**
     * @brief Get current fault (if any)
     */
    [[nodiscard]] std::optional<ChannelFault> get_fault() const noexcept;

    /**
     * @brief Clear fault (if safe to do so)
     *
     * Only clears safe faults (stuck open).
     * Dangerous faults require hardware reset.
     *
     * @return true if fault was cleared
     */
    [[nodiscard]] bool clear_fault() noexcept;

    /**
     * @brief Calculate diagnostic coverage
     *
     * Returns percentage of faults detectable by self-test.
     * Target: > 99% for SIL 2
     */
    [[nodiscard]] float diagnostic_coverage() const noexcept;

    /**
     * @brief Perform self-test
     *
     * Exercises both channels and verifies response.
     * Should only be called during safe conditions.
     *
     * @return true if self-test passed
     */
    [[nodiscard]] bool self_test();

private:
    /**
     * @brief Set GPIO output
     */
    void set_gpio(std::uint8_t pin, bool state) noexcept;

    /**
     * @brief Read GPIO input
     */
    [[nodiscard]] bool read_gpio(std::uint8_t pin) const noexcept;

    /**
     * @brief Update channel status from readback
     */
    void update_channel_status(ChannelStatus& status,
                                std::uint8_t readback_pin) noexcept;

    /**
     * @brief Report fault via callback
     */
    void report_fault(ChannelFault fault, const char* message) noexcept;

    /// Configuration
    DualChannelConfig config_;

    /// Fault notification callback
    FaultCallback fault_callback_;

    /// Channel status
    ChannelStatus primary_status_;
    ChannelStatus secondary_status_;

    /// Hardware initialized flag
    bool initialized_{false};

    /// Simulation mode (no actual GPIO)
    bool simulation_mode_{false};
};

}  // namespace lego_mcp

#endif  // LEGO_MCP_SAFETY_CERTIFIED__DUAL_CHANNEL_RELAY_HPP_
