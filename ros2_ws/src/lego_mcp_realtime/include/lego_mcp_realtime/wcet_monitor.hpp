/**
 * @file wcet_monitor.hpp
 * @brief Worst-Case Execution Time Monitor
 *
 * Monitors and analyzes execution times for real-time tasks:
 * - WCET measurement
 * - Deadline monitoring
 * - Overrun detection
 * - Statistical analysis
 *
 * Reference: IEC 61508 timing requirements
 *
 * @copyright Copyright (c) 2024 LEGO MCP Team
 * @license Apache-2.0
 */

#ifndef LEGO_MCP_REALTIME__WCET_MONITOR_HPP_
#define LEGO_MCP_REALTIME__WCET_MONITOR_HPP_

#include <atomic>
#include <chrono>
#include <cstdint>
#include <functional>
#include <memory>
#include <optional>
#include <string>
#include <vector>

namespace lego_mcp::realtime {

/**
 * @brief WCET measurement result
 */
struct WCETMeasurement {
    std::string task_name;
    std::chrono::nanoseconds execution_time{0};
    std::chrono::nanoseconds deadline{0};
    std::chrono::steady_clock::time_point start_time;
    std::chrono::steady_clock::time_point end_time;
    bool deadline_met{true};
    int64_t slack_ns{0};  ///< Remaining time to deadline
};

/**
 * @brief WCET analysis statistics
 */
struct WCETStats {
    std::string task_name;
    std::chrono::nanoseconds specified_wcet{0};
    std::chrono::nanoseconds measured_wcet{0};
    std::chrono::nanoseconds min_et{std::chrono::hours(1)};
    std::chrono::nanoseconds max_et{0};
    std::chrono::nanoseconds avg_et{0};
    std::chrono::nanoseconds stddev{0};
    std::chrono::nanoseconds p99_et{0};  ///< 99th percentile
    uint64_t sample_count{0};
    uint64_t deadline_misses{0};
    uint64_t wcet_overruns{0};
    double utilization{0.0};
};

/**
 * @brief WCET monitor configuration
 */
struct WCETConfig {
    size_t sample_window{1000};          ///< Samples to keep
    bool enable_histogram{true};         ///< Compute histogram
    size_t histogram_bins{100};          ///< Number of histogram bins
    std::chrono::nanoseconds wcet_margin{std::chrono::microseconds(100)};
    bool log_overruns{true};
};

/**
 * @brief WCET measurement scope guard
 *
 * Measures execution time from construction to destruction.
 *
 * Usage:
 * @code
 * {
 *     WCETScope scope(monitor, "my_task", deadline);
 *     // ... task code ...
 * }  // Measurement recorded here
 * @endcode
 */
class WCETScope {
public:
    /**
     * @brief Start WCET measurement
     * @param monitor WCET monitor
     * @param task_name Task name
     * @param deadline Task deadline
     */
    WCETScope(
        class WCETMonitor& monitor,
        const std::string& task_name,
        std::chrono::nanoseconds deadline = std::chrono::nanoseconds::max()
    );

    ~WCETScope();

    // Non-copyable
    WCETScope(const WCETScope&) = delete;
    WCETScope& operator=(const WCETScope&) = delete;

    /**
     * @brief Get elapsed time so far
     * @return Elapsed nanoseconds
     */
    [[nodiscard]] std::chrono::nanoseconds elapsed() const noexcept;

    /**
     * @brief Check if deadline will be missed
     * @return true if likely to miss deadline
     */
    [[nodiscard]] bool will_miss_deadline() const noexcept;

private:
    class WCETMonitor& monitor_;
    std::string task_name_;
    std::chrono::nanoseconds deadline_;
    std::chrono::steady_clock::time_point start_;
};

/**
 * @brief Worst-Case Execution Time Monitor
 *
 * Monitors execution times for real-time guarantees.
 *
 * Usage:
 * @code
 * WCETMonitor monitor(config);
 * monitor.register_task("safety_check", std::chrono::microseconds(500));
 *
 * // In task:
 * {
 *     WCETScope scope(monitor, "safety_check", deadline);
 *     // ... task code ...
 * }
 *
 * auto stats = monitor.get_stats("safety_check");
 * @endcode
 */
class WCETMonitor {
public:
    /// Overrun callback type
    using OverrunCallback = std::function<void(const WCETMeasurement&)>;

    /**
     * @brief Construct WCET monitor
     * @param config Configuration
     */
    explicit WCETMonitor(const WCETConfig& config = WCETConfig{});
    ~WCETMonitor();

    /**
     * @brief Register a task for monitoring
     * @param name Task name
     * @param specified_wcet Specified WCET
     * @param period Task period (optional)
     */
    void register_task(
        const std::string& name,
        std::chrono::nanoseconds specified_wcet,
        std::chrono::nanoseconds period = std::chrono::nanoseconds{0}
    );

    /**
     * @brief Record measurement
     * @param measurement Measurement data
     */
    void record(const WCETMeasurement& measurement);

    /**
     * @brief Get statistics for a task
     * @param name Task name
     * @return Statistics or nullopt if not found
     */
    [[nodiscard]] std::optional<WCETStats> get_stats(const std::string& name) const;

    /**
     * @brief Get all task statistics
     * @return Vector of all stats
     */
    [[nodiscard]] std::vector<WCETStats> get_all_stats() const;

    /**
     * @brief Get execution time histogram
     * @param name Task name
     * @return Histogram (bin -> count)
     */
    [[nodiscard]] std::vector<std::pair<std::chrono::nanoseconds, uint64_t>>
    get_histogram(const std::string& name) const;

    /**
     * @brief Set overrun callback
     * @param callback Function to call on overrun
     */
    void on_overrun(OverrunCallback callback);

    /**
     * @brief Check if all tasks meet WCET
     * @return true if all tasks within WCET
     */
    [[nodiscard]] bool all_tasks_safe() const;

    /**
     * @brief Get total CPU utilization
     * @return Utilization (0.0 - 1.0+)
     */
    [[nodiscard]] double total_utilization() const;

    /**
     * @brief Reset statistics
     * @param name Task name (empty = all tasks)
     */
    void reset(const std::string& name = "");

    /**
     * @brief Export statistics to JSON
     * @return JSON string
     */
    [[nodiscard]] std::string export_json() const;

private:
    friend class WCETScope;

    class Impl;
    std::unique_ptr<Impl> impl_;
};

/**
 * @brief Rate Monotonic Analysis
 *
 * Performs RMA schedulability analysis for real-time tasks.
 */
class RMAAnalyzer {
public:
    /**
     * @brief Task parameters for RMA
     */
    struct TaskParam {
        std::string name;
        std::chrono::nanoseconds period;
        std::chrono::nanoseconds wcet;
    };

    /**
     * @brief Add task for analysis
     * @param task Task parameters
     */
    void add_task(const TaskParam& task);

    /**
     * @brief Check if task set is schedulable
     * @return true if schedulable under RMA
     */
    [[nodiscard]] bool is_schedulable() const;

    /**
     * @brief Get utilization bound
     * @return Maximum utilization for schedulability
     */
    [[nodiscard]] double utilization_bound() const;

    /**
     * @brief Get total utilization
     * @return Sum of Ci/Ti for all tasks
     */
    [[nodiscard]] double total_utilization() const;

    /**
     * @brief Perform response time analysis
     * @param task_name Task name
     * @return Worst-case response time
     */
    [[nodiscard]] std::chrono::nanoseconds response_time(const std::string& task_name) const;

private:
    std::vector<TaskParam> tasks_;
};

}  // namespace lego_mcp::realtime

#endif  // LEGO_MCP_REALTIME__WCET_MONITOR_HPP_
