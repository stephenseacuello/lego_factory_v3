/**
 * @file rt_scheduler.hpp
 * @brief Real-Time Scheduler for Deterministic Execution
 *
 * Provides POSIX real-time scheduling with:
 * - SCHED_FIFO and SCHED_RR support
 * - CPU affinity control
 * - Memory locking
 * - Priority management
 *
 * Reference: POSIX 1003.1b Real-Time Extensions
 *
 * @copyright Copyright (c) 2024 LEGO MCP Team
 * @license Apache-2.0
 */

#ifndef LEGO_MCP_REALTIME__RT_SCHEDULER_HPP_
#define LEGO_MCP_REALTIME__RT_SCHEDULER_HPP_

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
 * @brief Real-time scheduling policy
 */
enum class RTPolicy {
    FIFO,       ///< First-in-first-out (SCHED_FIFO)
    RR,         ///< Round-robin (SCHED_RR)
    DEADLINE,   ///< Deadline scheduling (SCHED_DEADLINE)
    OTHER       ///< Normal scheduling (SCHED_OTHER)
};

/**
 * @brief Real-time priority levels
 *
 * Higher values = higher priority.
 * Safety-critical tasks should use SAFETY or CRITICAL.
 */
enum class RTPriority : int {
    IDLE = 0,
    LOW = 20,
    NORMAL = 40,
    HIGH = 60,
    REALTIME = 80,
    SAFETY = 90,
    CRITICAL = 99
};

/**
 * @brief Task configuration
 */
struct TaskConfig {
    std::string name;                        ///< Task name
    RTPolicy policy{RTPolicy::FIFO};         ///< Scheduling policy
    RTPriority priority{RTPriority::NORMAL}; ///< Task priority
    std::vector<int> cpu_affinity;           ///< CPU cores to bind to
    bool lock_memory{true};                  ///< Lock pages in memory
    std::chrono::nanoseconds period{0};      ///< Task period (0 = aperiodic)
    std::chrono::nanoseconds deadline{0};    ///< Relative deadline
    std::chrono::nanoseconds wcet{0};        ///< Worst-case execution time
};

/**
 * @brief Task execution statistics
 */
struct TaskStats {
    std::string name;
    uint64_t execution_count{0};
    std::chrono::nanoseconds total_execution_time{0};
    std::chrono::nanoseconds min_execution_time{std::chrono::hours(1)};
    std::chrono::nanoseconds max_execution_time{0};
    std::chrono::nanoseconds avg_execution_time{0};
    uint64_t deadline_misses{0};
    uint64_t preemption_count{0};
    double cpu_utilization{0.0};
};

/**
 * @brief Real-time task handle
 */
class RTTask {
public:
    using TaskFunction = std::function<void()>;

    /**
     * @brief Construct real-time task
     * @param config Task configuration
     * @param func Task function
     */
    RTTask(const TaskConfig& config, TaskFunction func);
    ~RTTask();

    // Non-copyable
    RTTask(const RTTask&) = delete;
    RTTask& operator=(const RTTask&) = delete;

    /**
     * @brief Start task execution
     * @return true if started
     */
    [[nodiscard]] bool start();

    /**
     * @brief Stop task execution
     */
    void stop() noexcept;

    /**
     * @brief Check if task is running
     * @return true if running
     */
    [[nodiscard]] bool is_running() const noexcept;

    /**
     * @brief Get task statistics
     * @return Task stats
     */
    [[nodiscard]] TaskStats stats() const noexcept;

    /**
     * @brief Get task name
     * @return Task name
     */
    [[nodiscard]] const std::string& name() const noexcept;

private:
    class Impl;
    std::unique_ptr<Impl> impl_;
};

/**
 * @brief Real-Time Scheduler
 *
 * Manages real-time task scheduling with deterministic guarantees.
 *
 * Usage:
 * @code
 * RTScheduler scheduler;
 * scheduler.configure_system();
 *
 * TaskConfig config;
 * config.name = "safety_monitor";
 * config.priority = RTPriority::SAFETY;
 * config.period = std::chrono::milliseconds(10);
 *
 * auto task = scheduler.create_task(config, []() {
 *     // Safety monitoring code
 * });
 * task->start();
 * @endcode
 */
class RTScheduler {
public:
    /**
     * @brief Construct RT scheduler
     */
    RTScheduler();
    ~RTScheduler();

    /**
     * @brief Configure system for real-time
     *
     * Sets up:
     * - Memory locking
     * - CPU isolation
     * - RT scheduling parameters
     *
     * @return true if configured successfully
     */
    [[nodiscard]] bool configure_system();

    /**
     * @brief Set current thread to real-time priority
     * @param priority Priority level
     * @param policy Scheduling policy
     * @return true if successful
     */
    [[nodiscard]] bool set_realtime_priority(
        RTPriority priority,
        RTPolicy policy = RTPolicy::FIFO
    );

    /**
     * @brief Set CPU affinity for current thread
     * @param cpus CPU cores to bind to
     * @return true if successful
     */
    [[nodiscard]] bool set_cpu_affinity(const std::vector<int>& cpus);

    /**
     * @brief Lock memory pages
     * @return true if successful
     */
    [[nodiscard]] bool lock_memory();

    /**
     * @brief Create real-time task
     * @param config Task configuration
     * @param func Task function
     * @return Task handle
     */
    [[nodiscard]] std::shared_ptr<RTTask> create_task(
        const TaskConfig& config,
        RTTask::TaskFunction func
    );

    /**
     * @brief Get maximum RT priority
     * @param policy Scheduling policy
     * @return Maximum priority value
     */
    [[nodiscard]] static int max_priority(RTPolicy policy) noexcept;

    /**
     * @brief Get minimum RT priority
     * @param policy Scheduling policy
     * @return Minimum priority value
     */
    [[nodiscard]] static int min_priority(RTPolicy policy) noexcept;

    /**
     * @brief Check if real-time scheduling is available
     * @return true if RT scheduling available
     */
    [[nodiscard]] static bool is_rt_available() noexcept;

    /**
     * @brief Get scheduler statistics
     * @return Vector of task stats
     */
    [[nodiscard]] std::vector<TaskStats> stats() const;

    /**
     * @brief Yield current thread
     */
    static void yield() noexcept;

    /**
     * @brief Sleep with nanosecond precision
     * @param duration Sleep duration
     */
    static void sleep_until(std::chrono::steady_clock::time_point until);

private:
    class Impl;
    std::unique_ptr<Impl> impl_;
};

/**
 * @brief RAII guard for real-time priority
 *
 * Sets RT priority on construction, restores on destruction.
 */
class RTPriorityGuard {
public:
    /**
     * @brief Construct and set RT priority
     * @param priority Priority level
     * @param policy Scheduling policy
     */
    explicit RTPriorityGuard(
        RTPriority priority,
        RTPolicy policy = RTPolicy::FIFO
    );

    ~RTPriorityGuard();

    // Non-copyable
    RTPriorityGuard(const RTPriorityGuard&) = delete;
    RTPriorityGuard& operator=(const RTPriorityGuard&) = delete;

    /**
     * @brief Check if RT priority was set successfully
     * @return true if successful
     */
    [[nodiscard]] bool is_active() const noexcept { return active_; }

private:
    bool active_{false};
    int original_policy_{0};
    int original_priority_{0};
};

}  // namespace lego_mcp::realtime

#endif  // LEGO_MCP_REALTIME__RT_SCHEDULER_HPP_
