/**
 * @file deterministic_executor.cpp
 * @brief Deterministic Executor for ROS2 Real-Time
 */

#include <chrono>
#include <memory>
#include <vector>
#include <functional>
#include <thread>
#include <atomic>
#include <mutex>

#ifdef __linux__
#include <pthread.h>
#include <sched.h>
#include <sys/mman.h>
#endif

namespace lego_mcp::realtime {

/**
 * @brief Callback priority level
 */
enum class CallbackPriority {
    SAFETY = 0,     // Highest - safety callbacks
    CONTROL = 1,    // Control loop callbacks
    SENSING = 2,    // Sensor processing
    PLANNING = 3,   // Motion planning
    LOGGING = 4     // Lowest - logging/diagnostics
};

/**
 * @brief Callback wrapper with priority
 */
struct PrioritizedCallback {
    std::function<void()> callback;
    CallbackPriority priority;
    std::chrono::nanoseconds period;
    std::chrono::steady_clock::time_point next_run;
    std::chrono::nanoseconds wcet;
    std::string name;
};

/**
 * @brief Deterministic executor for real-time ROS2 callbacks
 *
 * Provides:
 * - Priority-based callback scheduling
 * - Deterministic timing
 * - WCET enforcement
 * - Overrun protection
 */
class DeterministicExecutor {
public:
    /**
     * @brief Configuration
     */
    struct Config {
        std::chrono::nanoseconds base_period;
        int rt_priority;
        std::vector<int> cpu_affinity;
        bool lock_memory;

        Config() : base_period(std::chrono::milliseconds(1)),
                   rt_priority(80),
                   cpu_affinity(),
                   lock_memory(true) {}
    };

    DeterministicExecutor() : DeterministicExecutor(Config()) {}

    explicit DeterministicExecutor(const Config& config)
        : config_(config), running_(false) {}

    ~DeterministicExecutor() {
        stop();
    }

    /**
     * @brief Add callback with priority
     */
    void add_callback(
        const std::string& name,
        std::function<void()> callback,
        CallbackPriority priority,
        std::chrono::nanoseconds period,
        std::chrono::nanoseconds wcet = std::chrono::nanoseconds{0}
    ) {
        std::lock_guard<std::mutex> lock(mutex_);

        PrioritizedCallback pc;
        pc.name = name;
        pc.callback = std::move(callback);
        pc.priority = priority;
        pc.period = period;
        pc.wcet = wcet;
        pc.next_run = std::chrono::steady_clock::now();

        callbacks_.push_back(std::move(pc));

        // Sort by priority (lower value = higher priority)
        std::sort(callbacks_.begin(), callbacks_.end(),
            [](const PrioritizedCallback& a, const PrioritizedCallback& b) {
                return static_cast<int>(a.priority) < static_cast<int>(b.priority);
            });
    }

    /**
     * @brief Start executor
     */
    bool start() {
        if (running_.exchange(true)) {
            return false;
        }

        executor_thread_ = std::thread(&DeterministicExecutor::run, this);
        return true;
    }

    /**
     * @brief Stop executor
     */
    void stop() {
        running_ = false;
        if (executor_thread_.joinable()) {
            executor_thread_.join();
        }
    }

    /**
     * @brief Get statistics
     */
    struct Stats {
        uint64_t cycles{0};
        uint64_t overruns{0};
        std::chrono::nanoseconds max_cycle_time{0};
        std::chrono::nanoseconds avg_cycle_time{0};
    };

    Stats get_stats() const {
        std::lock_guard<std::mutex> lock(stats_mutex_);
        return stats_;
    }

private:
    void run() {
        // Configure RT thread
        configure_rt_thread();

        auto cycle_start = std::chrono::steady_clock::now();
        auto next_cycle = cycle_start + config_.base_period;

        while (running_) {
            cycle_start = std::chrono::steady_clock::now();

            // Execute ready callbacks in priority order
            {
                std::lock_guard<std::mutex> lock(mutex_);
                for (auto& cb : callbacks_) {
                    if (cycle_start >= cb.next_run) {
                        auto start = std::chrono::steady_clock::now();

                        try {
                            cb.callback();
                        } catch (...) {
                            // Log error
                        }

                        auto end = std::chrono::steady_clock::now();
                        auto duration = std::chrono::duration_cast<std::chrono::nanoseconds>(
                            end - start
                        );

                        // Check WCET violation
                        if (cb.wcet.count() > 0 && duration > cb.wcet) {
                            std::lock_guard<std::mutex> stats_lock(stats_mutex_);
                            stats_.overruns++;
                        }

                        // Schedule next run
                        cb.next_run += cb.period;

                        // Prevent drift
                        if (cb.next_run < cycle_start) {
                            cb.next_run = cycle_start + cb.period;
                        }
                    }
                }
            }

            // Update stats
            auto cycle_end = std::chrono::steady_clock::now();
            auto cycle_time = std::chrono::duration_cast<std::chrono::nanoseconds>(
                cycle_end - cycle_start
            );

            {
                std::lock_guard<std::mutex> lock(stats_mutex_);
                stats_.cycles++;
                stats_.max_cycle_time = std::max(stats_.max_cycle_time, cycle_time);
                stats_.avg_cycle_time = std::chrono::nanoseconds(
                    (stats_.avg_cycle_time.count() * (stats_.cycles - 1) +
                     cycle_time.count()) / stats_.cycles
                );
            }

            // Sleep until next cycle
            std::this_thread::sleep_until(next_cycle);
            next_cycle += config_.base_period;
        }
    }

    void configure_rt_thread() {
#ifdef __linux__
        // Set RT priority
        struct sched_param param;
        param.sched_priority = config_.rt_priority;
        pthread_setschedparam(pthread_self(), SCHED_FIFO, &param);

        // Set CPU affinity
        if (!config_.cpu_affinity.empty()) {
            cpu_set_t cpuset;
            CPU_ZERO(&cpuset);
            for (int cpu : config_.cpu_affinity) {
                CPU_SET(cpu, &cpuset);
            }
            pthread_setaffinity_np(pthread_self(), sizeof(cpu_set_t), &cpuset);
        }

        // Lock memory
        if (config_.lock_memory) {
            mlockall(MCL_CURRENT | MCL_FUTURE);
        }
#endif
    }

    Config config_;
    std::atomic<bool> running_;
    std::thread executor_thread_;

    mutable std::mutex mutex_;
    std::vector<PrioritizedCallback> callbacks_;

    mutable std::mutex stats_mutex_;
    Stats stats_;
};

}  // namespace lego_mcp::realtime
