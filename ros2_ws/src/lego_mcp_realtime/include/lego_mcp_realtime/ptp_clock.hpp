/**
 * @file ptp_clock.hpp
 * @brief IEEE 1588 Precision Time Protocol Clock
 *
 * Provides sub-microsecond time synchronization across distributed
 * manufacturing nodes using PTP (IEEE 1588-2019).
 *
 * Features:
 * - Hardware timestamping support
 * - Best Master Clock Algorithm
 * - Boundary/Transparent clock modes
 * - Synchronization monitoring
 *
 * @copyright Copyright (c) 2024 LEGO MCP Team
 * @license Apache-2.0
 */

#ifndef LEGO_MCP_REALTIME__PTP_CLOCK_HPP_
#define LEGO_MCP_REALTIME__PTP_CLOCK_HPP_

#include <atomic>
#include <chrono>
#include <cstdint>
#include <functional>
#include <memory>
#include <string>
#include <optional>

namespace lego_mcp::realtime {

/**
 * @brief PTP clock state
 */
enum class PTPState {
    INITIALIZING,
    FAULTY,
    DISABLED,
    LISTENING,
    PRE_MASTER,
    MASTER,
    PASSIVE,
    UNCALIBRATED,
    SLAVE
};

/**
 * @brief PTP clock configuration
 */
struct PTPConfig {
    std::string interface{"eth0"};          ///< Network interface
    std::string domain{0};                   ///< PTP domain number
    bool hardware_timestamping{true};        ///< Use hardware timestamps
    bool boundary_clock{false};              ///< Act as boundary clock
    std::chrono::nanoseconds sync_interval{std::chrono::milliseconds(125)};
    std::chrono::nanoseconds announce_interval{std::chrono::seconds(1)};
    uint8_t priority1{128};                  ///< Priority 1 for BMC
    uint8_t priority2{128};                  ///< Priority 2 for BMC
};

/**
 * @brief PTP synchronization statistics
 */
struct PTPStats {
    std::chrono::nanoseconds offset{0};      ///< Clock offset from master
    std::chrono::nanoseconds delay{0};       ///< Path delay to master
    std::chrono::nanoseconds jitter{0};      ///< Offset jitter
    double drift_ppb{0.0};                   ///< Clock drift in ppb
    uint64_t sync_count{0};                  ///< Number of sync messages
    uint64_t error_count{0};                 ///< Error count
    std::chrono::steady_clock::time_point last_sync;
};

/**
 * @brief PTP timestamp with nanosecond precision
 */
struct PTPTimestamp {
    uint64_t seconds{0};
    uint32_t nanoseconds{0};

    [[nodiscard]] std::chrono::nanoseconds to_duration() const noexcept {
        return std::chrono::seconds(seconds) + std::chrono::nanoseconds(nanoseconds);
    }

    [[nodiscard]] static PTPTimestamp from_timespec(const struct timespec& ts) noexcept {
        return {static_cast<uint64_t>(ts.tv_sec), static_cast<uint32_t>(ts.tv_nsec)};
    }
};

/**
 * @brief IEEE 1588 PTP Clock implementation
 *
 * Provides precision time synchronization for distributed manufacturing.
 *
 * Usage:
 * @code
 * PTPConfig config;
 * config.interface = "eth0";
 * auto clock = std::make_unique<PTPClock>(config);
 * clock->start();
 *
 * // Get synchronized time
 * auto now = clock->now();
 * @endcode
 */
class PTPClock {
public:
    /// Sync callback type
    using SyncCallback = std::function<void(const PTPStats&)>;

    /**
     * @brief Construct PTP clock
     * @param config Configuration
     */
    explicit PTPClock(const PTPConfig& config = PTPConfig{});

    /// Destructor
    ~PTPClock();

    // Non-copyable, movable
    PTPClock(const PTPClock&) = delete;
    PTPClock& operator=(const PTPClock&) = delete;
    PTPClock(PTPClock&&) noexcept;
    PTPClock& operator=(PTPClock&&) noexcept;

    /**
     * @brief Start PTP clock synchronization
     * @return true if started successfully
     */
    [[nodiscard]] bool start();

    /**
     * @brief Stop PTP clock
     */
    void stop() noexcept;

    /**
     * @brief Get current synchronized time
     * @return PTP timestamp
     */
    [[nodiscard]] PTPTimestamp now() const noexcept;

    /**
     * @brief Get current clock state
     * @return PTP state
     */
    [[nodiscard]] PTPState state() const noexcept;

    /**
     * @brief Get synchronization statistics
     * @return PTP stats
     */
    [[nodiscard]] PTPStats stats() const noexcept;

    /**
     * @brief Check if clock is synchronized
     * @param max_offset Maximum acceptable offset
     * @return true if synchronized within tolerance
     */
    [[nodiscard]] bool is_synchronized(
        std::chrono::nanoseconds max_offset = std::chrono::microseconds(1)
    ) const noexcept;

    /**
     * @brief Register sync callback
     * @param callback Function to call on sync events
     */
    void on_sync(SyncCallback callback);

    /**
     * @brief Get clock offset from master
     * @return Offset in nanoseconds
     */
    [[nodiscard]] std::chrono::nanoseconds offset() const noexcept;

    /**
     * @brief Get path delay to master
     * @return Delay in nanoseconds
     */
    [[nodiscard]] std::chrono::nanoseconds delay() const noexcept;

    /**
     * @brief Force resynchronization
     */
    void resync();

private:
    class Impl;
    std::unique_ptr<Impl> impl_;
};

}  // namespace lego_mcp::realtime

#endif  // LEGO_MCP_REALTIME__PTP_CLOCK_HPP_
