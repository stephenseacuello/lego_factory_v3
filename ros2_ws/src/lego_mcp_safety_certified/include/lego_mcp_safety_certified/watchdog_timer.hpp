/**
 * @file watchdog_timer.hpp
 * @brief Hardware Watchdog Timer for Safety-Critical Systems
 *
 * IEC 61508 SIL 2+ Compliant Watchdog Implementation
 *
 * Features:
 * - Hardware watchdog integration (Linux /dev/watchdog)
 * - Software watchdog fallback
 * - Heartbeat monitoring with configurable timeout
 * - Automatic safe state trigger on timeout
 *
 * SAFETY PROPERTIES:
 * - Timeout triggers e-stop within bounded time (WCET < 1ms)
 * - No single point of failure (hardware + software redundancy)
 * - Fail-safe on watchdog daemon failure
 */

#ifndef LEGO_MCP_SAFETY_CERTIFIED__WATCHDOG_TIMER_HPP_
#define LEGO_MCP_SAFETY_CERTIFIED__WATCHDOG_TIMER_HPP_

#include <atomic>
#include <chrono>
#include <cstdint>
#include <functional>
#include <string>

namespace lego_mcp
{

/**
 * @brief Watchdog state enumeration
 */
enum class WatchdogState : std::uint8_t
{
    STOPPED = 0U,     ///< Watchdog not running
    RUNNING = 1U,     ///< Watchdog active and being fed
    TRIGGERED = 2U,   ///< Timeout occurred - safe state triggered
    FAULT = 3U        ///< Hardware watchdog fault
};

/**
 * @brief Watchdog configuration
 */
struct WatchdogConfig
{
    /// Timeout duration before triggering safe state
    std::chrono::milliseconds timeout{100};

    /// Pre-timeout warning duration
    std::chrono::milliseconds pre_timeout{50};

    /// Hardware watchdog device path (empty = software only)
    std::string hw_watchdog_device{"/dev/watchdog0"};

    /// Enable hardware watchdog
    bool use_hardware_watchdog{true};

    /// Enable software watchdog (always recommended as backup)
    bool use_software_watchdog{true};

    /// Magicsysrq trigger on timeout (for debugging)
    bool enable_sysrq_trigger{false};
};

/**
 * @brief Watchdog statistics
 */
struct WatchdogStats
{
    std::uint64_t feed_count{0U};
    std::uint64_t timeout_count{0U};
    std::uint64_t pre_timeout_count{0U};
    std::chrono::steady_clock::time_point last_feed;
    std::chrono::microseconds max_feed_interval{0};
    std::chrono::microseconds avg_feed_interval{0};
};

/**
 * @brief Hardware Watchdog Timer
 *
 * Provides dual-layer watchdog protection:
 * 1. Hardware watchdog via /dev/watchdog (kernel level)
 * 2. Software watchdog via timer thread (application level)
 *
 * Both layers must be fed regularly or safe state is triggered.
 *
 * TIMING GUARANTEES:
 * - Feed operation: < 100us WCET
 * - Timeout detection: < 1ms from timeout
 * - Safe state trigger: Immediate (callback inline)
 */
class WatchdogTimer
{
public:
    /// Callback type for timeout notification
    using TimeoutCallback = std::function<void()>;

    /// Callback type for pre-timeout warning
    using PreTimeoutCallback = std::function<void(std::chrono::milliseconds remaining)>;

    /**
     * @brief Construct with configuration
     *
     * @param config Watchdog configuration
     * @param timeout_callback Callback invoked on timeout
     * @param pre_timeout_callback Optional pre-timeout warning callback
     */
    explicit WatchdogTimer(
        const WatchdogConfig& config,
        TimeoutCallback timeout_callback,
        PreTimeoutCallback pre_timeout_callback = nullptr);

    /**
     * @brief Destructor - stops watchdog safely
     */
    ~WatchdogTimer();

    // Disable copy/move
    WatchdogTimer(const WatchdogTimer&) = delete;
    WatchdogTimer& operator=(const WatchdogTimer&) = delete;
    WatchdogTimer(WatchdogTimer&&) = delete;
    WatchdogTimer& operator=(WatchdogTimer&&) = delete;

    /**
     * @brief Start the watchdog timer
     *
     * Opens hardware watchdog (if enabled) and starts monitoring.
     *
     * @return true if started successfully
     */
    [[nodiscard]] bool start();

    /**
     * @brief Stop the watchdog timer
     *
     * Disables hardware watchdog (magic close) and stops monitoring.
     * Only succeeds if system is in safe state.
     *
     * @return true if stopped successfully
     */
    [[nodiscard]] bool stop();

    /**
     * @brief Feed the watchdog
     *
     * Must be called periodically to prevent timeout.
     * WCET: < 100us
     *
     * @return true if fed successfully
     */
    [[nodiscard]] bool feed() noexcept;

    /**
     * @brief Check if watchdog has timed out
     */
    [[nodiscard]] bool has_timed_out() const noexcept
    {
        return state_.load(std::memory_order_acquire) == WatchdogState::TRIGGERED;
    }

    /**
     * @brief Get current watchdog state
     */
    [[nodiscard]] WatchdogState state() const noexcept
    {
        return state_.load(std::memory_order_acquire);
    }

    /**
     * @brief Get time remaining before timeout
     */
    [[nodiscard]] std::chrono::milliseconds time_remaining() const noexcept;

    /**
     * @brief Get watchdog statistics
     */
    [[nodiscard]] const WatchdogStats& stats() const noexcept
    {
        return stats_;
    }

    /**
     * @brief Check hardware watchdog availability
     */
    [[nodiscard]] bool has_hardware_watchdog() const noexcept
    {
        return hw_watchdog_fd_ >= 0;
    }

private:
    /**
     * @brief Open hardware watchdog device
     */
    [[nodiscard]] bool open_hardware_watchdog();

    /**
     * @brief Close hardware watchdog device
     */
    void close_hardware_watchdog() noexcept;

    /**
     * @brief Feed hardware watchdog
     */
    [[nodiscard]] bool feed_hardware_watchdog() noexcept;

    /**
     * @brief Software watchdog check thread
     */
    void software_watchdog_thread();

    /**
     * @brief Trigger timeout callback
     */
    void trigger_timeout() noexcept;

    /// Configuration
    WatchdogConfig config_;

    /// Callbacks
    TimeoutCallback timeout_callback_;
    PreTimeoutCallback pre_timeout_callback_;

    /// State
    std::atomic<WatchdogState> state_{WatchdogState::STOPPED};

    /// Timing
    std::atomic<std::chrono::steady_clock::time_point> last_feed_time_;

    /// Hardware watchdog file descriptor
    int hw_watchdog_fd_{-1};

    /// Statistics
    WatchdogStats stats_;

    /// Software watchdog thread control
    std::atomic<bool> sw_watchdog_running_{false};
};

}  // namespace lego_mcp

#endif  // LEGO_MCP_SAFETY_CERTIFIED__WATCHDOG_TIMER_HPP_
