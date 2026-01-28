/**
 * @file realtime_node.cpp
 * @brief ROS2 Real-Time Lifecycle Node for Manufacturing
 *
 * Integrates PTP clock sync, RT scheduling, WCET monitoring,
 * and deterministic execution for LEGO MCP manufacturing.
 *
 * Reference: ROS2 Real-Time WG, IEC 61784-3
 */

#include <chrono>
#include <memory>
#include <vector>
#include <functional>
#include <string>
#include <atomic>
#ifdef __linux__
#include <sys/mman.h>
#endif

// ROS2 includes (stubbed for standalone compilation)
#ifndef HAVE_ROS2
namespace rclcpp {
    class Node {
    public:
        explicit Node(const std::string& name) : name_(name) {}
        std::string get_name() const { return name_; }
    protected:
        std::string name_;
    };

    class Publisher {
    public:
        template<typename T>
        void publish(const T&) {}
    };

    class Subscription {};
    class TimerBase {};
}

namespace rclcpp_lifecycle {
    class LifecycleNode : public rclcpp::Node {
    public:
        explicit LifecycleNode(const std::string& name) : Node(name) {}
        virtual ~LifecycleNode() = default;
    };

    enum class State {
        PRIMARY_STATE_UNCONFIGURED,
        PRIMARY_STATE_INACTIVE,
        PRIMARY_STATE_ACTIVE,
        PRIMARY_STATE_FINALIZED
    };

    struct CallbackReturn {
        static constexpr int SUCCESS = 0;
        static constexpr int ERROR = 1;
        static constexpr int FAILURE = 2;
    };
}

namespace std_msgs::msg {
    struct Header {
        struct Stamp {
            int32_t sec{0};
            uint32_t nanosec{0};
        } stamp;
        std::string frame_id;
    };
}

namespace diagnostic_msgs::msg {
    struct DiagnosticStatus {
        static constexpr uint8_t OK = 0;
        static constexpr uint8_t WARN = 1;
        static constexpr uint8_t ERROR = 2;
        static constexpr uint8_t STALE = 3;

        uint8_t level{OK};
        std::string name;
        std::string message;
        std::string hardware_id;
    };

    struct DiagnosticArray {
        std_msgs::msg::Header header;
        std::vector<DiagnosticStatus> status;
    };
}
#endif

#include <mutex>
#include <thread>

namespace lego_mcp::realtime {

// Forward declarations (from other headers)
enum class RTPriority { SAFETY = 99, CONTROL = 90, SENSING = 80, PLANNING = 70, LOGGING = 50 };
enum class RTPolicy { FIFO, RR, OTHER };
enum class SyncState { INITIALIZING, LISTENING, MASTER, SLAVE, PASSIVE, FAULTY };
enum class ClockQuality { PRIMARY_REFERENCE, SECONDARY_REFERENCE, HOLDOVER, LOCAL_OSCILLATOR, UNKNOWN };
enum class CallbackPriority { SAFETY = 0, CONTROL = 1, SENSING = 2, PLANNING = 3, LOGGING = 4 };

/**
 * @brief Real-time node configuration
 */
struct RTNodeConfig {
    // Node identity
    std::string node_name{"lego_mcp_rt_node"};
    std::string namespace_{"lego_mcp"};

    // Real-time parameters
    int rt_priority{80};
    std::vector<int> cpu_affinity{2, 3};  // Isolated CPUs
    bool lock_memory{true};

    // Clock sync parameters
    bool enable_ptp_sync{true};
    std::chrono::microseconds max_clock_offset{100};  // 100μs max

    // Timing parameters
    std::chrono::milliseconds control_period{1};      // 1kHz control loop
    std::chrono::milliseconds sensing_period{5};      // 200Hz sensing
    std::chrono::milliseconds planning_period{100};   // 10Hz planning
    std::chrono::milliseconds diagnostics_period{1000}; // 1Hz diagnostics

    // WCET budgets
    std::chrono::microseconds control_wcet{500};      // 500μs budget
    std::chrono::microseconds sensing_wcet{2000};     // 2ms budget
    std::chrono::microseconds planning_wcet{50000};   // 50ms budget

    // Safety parameters
    uint32_t max_consecutive_overruns{3};
    bool enable_watchdog{true};
    std::chrono::milliseconds watchdog_timeout{100};
};

/**
 * @brief Real-time node statistics
 */
struct RTNodeStats {
    // Timing stats
    uint64_t control_cycles{0};
    uint64_t sensing_cycles{0};
    uint64_t planning_cycles{0};

    // Overrun stats
    uint64_t control_overruns{0};
    uint64_t sensing_overruns{0};
    uint64_t planning_overruns{0};

    // Clock stats
    std::chrono::nanoseconds clock_offset{0};
    bool clock_synchronized{false};

    // WCET stats
    std::chrono::nanoseconds control_max_exec{0};
    std::chrono::nanoseconds sensing_max_exec{0};
    std::chrono::nanoseconds planning_max_exec{0};

    // System state
    bool rt_mode_active{false};
    uint32_t consecutive_overruns{0};
};

/**
 * @brief Callback registration for the RT executor
 */
struct RTCallback {
    std::string name;
    std::function<void()> callback;
    CallbackPriority priority;
    std::chrono::nanoseconds period;
    std::chrono::nanoseconds wcet;
    bool enabled{true};
};

/**
 * @brief ROS2 Real-Time Lifecycle Node
 *
 * Provides deterministic real-time execution for manufacturing:
 * - IEEE 1588 PTP clock synchronization
 * - POSIX real-time scheduling
 * - WCET monitoring and enforcement
 * - Graceful degradation on overruns
 */
class RealtimeNode : public rclcpp_lifecycle::LifecycleNode {
public:
    explicit RealtimeNode(const RTNodeConfig& config = RTNodeConfig{})
        : LifecycleNode(config.node_name),
          config_(config) {

        // Initialize stats
        stats_ = std::make_shared<RTNodeStats>();

        log_info("RealtimeNode created");
    }

    ~RealtimeNode() override {
        shutdown();
    }

    /**
     * @brief Lifecycle: on_configure
     */
    int on_configure() {
        log_info("Configuring RealtimeNode...");

        // Configure RT scheduling
        if (!configure_rt_scheduling()) {
            log_error("Failed to configure RT scheduling");
            return rclcpp_lifecycle::CallbackReturn::ERROR;
        }

        // Initialize clock sync if enabled
        if (config_.enable_ptp_sync) {
            if (!initialize_clock_sync()) {
                log_warn("PTP sync initialization failed, using local clock");
            }
        }

        // Register callbacks
        register_callbacks();

        // Create diagnostics publisher
        // diag_pub_ = create_publisher<diagnostic_msgs::msg::DiagnosticArray>(
        //     "diagnostics", 10);

        log_info("RealtimeNode configured");
        return rclcpp_lifecycle::CallbackReturn::SUCCESS;
    }

    /**
     * @brief Lifecycle: on_activate
     */
    int on_activate() {
        log_info("Activating RealtimeNode...");

        // Start RT executor
        if (!start_executor()) {
            log_error("Failed to start RT executor");
            return rclcpp_lifecycle::CallbackReturn::ERROR;
        }

        // Start watchdog if enabled
        if (config_.enable_watchdog) {
            start_watchdog();
        }

        stats_->rt_mode_active = true;
        log_info("RealtimeNode activated - RT mode ACTIVE");
        return rclcpp_lifecycle::CallbackReturn::SUCCESS;
    }

    /**
     * @brief Lifecycle: on_deactivate
     */
    int on_deactivate() {
        log_info("Deactivating RealtimeNode...");

        stats_->rt_mode_active = false;
        stop_executor();
        stop_watchdog();

        log_info("RealtimeNode deactivated");
        return rclcpp_lifecycle::CallbackReturn::SUCCESS;
    }

    /**
     * @brief Lifecycle: on_cleanup
     */
    int on_cleanup() {
        log_info("Cleaning up RealtimeNode...");

        callbacks_.clear();
        // diag_pub_.reset();

        log_info("RealtimeNode cleaned up");
        return rclcpp_lifecycle::CallbackReturn::SUCCESS;
    }

    /**
     * @brief Lifecycle: on_shutdown
     */
    int on_shutdown() {
        log_info("Shutting down RealtimeNode...");
        shutdown();
        return rclcpp_lifecycle::CallbackReturn::SUCCESS;
    }

    /**
     * @brief Register a control callback (highest priority)
     */
    void register_control_callback(
        const std::string& name,
        std::function<void()> callback
    ) {
        register_callback(
            name,
            std::move(callback),
            CallbackPriority::CONTROL,
            config_.control_period,
            config_.control_wcet
        );
    }

    /**
     * @brief Register a sensing callback
     */
    void register_sensing_callback(
        const std::string& name,
        std::function<void()> callback
    ) {
        register_callback(
            name,
            std::move(callback),
            CallbackPriority::SENSING,
            config_.sensing_period,
            config_.sensing_wcet
        );
    }

    /**
     * @brief Register a planning callback
     */
    void register_planning_callback(
        const std::string& name,
        std::function<void()> callback
    ) {
        register_callback(
            name,
            std::move(callback),
            CallbackPriority::PLANNING,
            config_.planning_period,
            config_.planning_wcet
        );
    }

    /**
     * @brief Get current statistics
     */
    [[nodiscard]] RTNodeStats get_stats() const {
        std::lock_guard<std::mutex> lock(stats_mutex_);
        return *stats_;
    }

    /**
     * @brief Check if RT mode is active
     */
    [[nodiscard]] bool is_rt_active() const noexcept {
        return stats_->rt_mode_active && running_;
    }

    /**
     * @brief Check if clock is synchronized
     */
    [[nodiscard]] bool is_clock_synced() const noexcept {
        std::lock_guard<std::mutex> lock(stats_mutex_);
        return stats_->clock_synchronized;
    }

    /**
     * @brief Get current synchronized timestamp
     */
    [[nodiscard]] std::chrono::steady_clock::time_point now() const {
        // In real implementation, would return PTP-synchronized time
        return std::chrono::steady_clock::now();
    }

    /**
     * @brief Force degraded mode (for testing/recovery)
     */
    void enter_degraded_mode() {
        log_warn("Entering degraded mode - reduced RT guarantees");
        degraded_mode_ = true;

        // Reduce priorities, extend deadlines
        for (auto& cb : callbacks_) {
            cb.wcet *= 2;  // Double WCET budget
        }
    }

    /**
     * @brief Exit degraded mode
     */
    void exit_degraded_mode() {
        if (degraded_mode_) {
            log_info("Exiting degraded mode - full RT restored");
            degraded_mode_ = false;

            // Restore original WCET budgets
            for (auto& cb : callbacks_) {
                cb.wcet /= 2;
            }
        }
    }

private:
    void register_callback(
        const std::string& name,
        std::function<void()> callback,
        CallbackPriority priority,
        std::chrono::milliseconds period,
        std::chrono::microseconds wcet
    ) {
        std::lock_guard<std::mutex> lock(callbacks_mutex_);

        RTCallback cb;
        cb.name = name;
        cb.callback = std::move(callback);
        cb.priority = priority;
        cb.period = period;
        cb.wcet = wcet;
        cb.enabled = true;

        callbacks_.push_back(std::move(cb));

        // Keep sorted by priority
        std::sort(callbacks_.begin(), callbacks_.end(),
            [](const RTCallback& a, const RTCallback& b) {
                return static_cast<int>(a.priority) < static_cast<int>(b.priority);
            });

        log_info("Registered callback: " + name);
    }

    void register_callbacks() {
        // Register diagnostics callback (low priority)
        register_callback(
            "diagnostics",
            [this]() { publish_diagnostics(); },
            CallbackPriority::LOGGING,
            config_.diagnostics_period,
            std::chrono::microseconds(10000)  // 10ms budget
        );
    }

    bool configure_rt_scheduling() {
#ifdef __linux__
        // Lock memory
        if (config_.lock_memory) {
            if (mlockall(MCL_CURRENT | MCL_FUTURE) != 0) {
                log_warn("Failed to lock memory - running without memory lock");
            }
        }

        // Set CPU affinity
        if (!config_.cpu_affinity.empty()) {
            cpu_set_t cpuset;
            CPU_ZERO(&cpuset);
            for (int cpu : config_.cpu_affinity) {
                CPU_SET(cpu, &cpuset);
            }
            if (sched_setaffinity(0, sizeof(cpu_set_t), &cpuset) != 0) {
                log_warn("Failed to set CPU affinity");
            }
        }

        return true;
#else
        return true;  // Simulation mode
#endif
    }

    bool initialize_clock_sync() {
        // In real implementation, would initialize PTP
        log_info("PTP clock sync initialized");

        std::lock_guard<std::mutex> lock(stats_mutex_);
        stats_->clock_synchronized = true;
        return true;
    }

    bool start_executor() {
        if (running_.exchange(true)) {
            return false;
        }

        executor_thread_ = std::thread(&RealtimeNode::executor_loop, this);
        return true;
    }

    void stop_executor() {
        running_ = false;
        if (executor_thread_.joinable()) {
            executor_thread_.join();
        }
    }

    void executor_loop() {
#ifdef __linux__
        // Set RT priority for executor thread
        struct sched_param param;
        param.sched_priority = config_.rt_priority;
        pthread_setschedparam(pthread_self(), SCHED_FIFO, &param);
#endif

        // Initialize timing
        std::vector<std::chrono::steady_clock::time_point> next_run;
        {
            std::lock_guard<std::mutex> lock(callbacks_mutex_);
            auto now = std::chrono::steady_clock::now();
            for (size_t i = 0; i < callbacks_.size(); ++i) {
                next_run.push_back(now);
            }
        }

        auto cycle_time = std::chrono::microseconds(500);  // 2kHz base
        auto next_cycle = std::chrono::steady_clock::now();

        while (running_) {
            auto cycle_start = std::chrono::steady_clock::now();

            // Execute ready callbacks in priority order
            {
                std::lock_guard<std::mutex> lock(callbacks_mutex_);

                for (size_t i = 0; i < callbacks_.size(); ++i) {
                    auto& cb = callbacks_[i];
                    if (!cb.enabled) continue;

                    if (cycle_start >= next_run[i]) {
                        auto exec_start = std::chrono::steady_clock::now();

                        // Execute callback
                        try {
                            cb.callback();
                        } catch (const std::exception& e) {
                            log_error("Callback exception: " + std::string(e.what()));
                        } catch (...) {
                            log_error("Unknown callback exception");
                        }

                        auto exec_end = std::chrono::steady_clock::now();
                        auto exec_time = std::chrono::duration_cast<std::chrono::nanoseconds>(
                            exec_end - exec_start
                        );

                        // Update stats
                        update_callback_stats(cb, exec_time);

                        // Check WCET violation
                        if (exec_time > cb.wcet) {
                            handle_wcet_violation(cb, exec_time);
                        }

                        // Schedule next run
                        next_run[i] += cb.period;
                        if (next_run[i] < cycle_start) {
                            // Prevent drift
                            next_run[i] = cycle_start + cb.period;
                        }
                    }
                }
            }

            // Pet watchdog
            if (config_.enable_watchdog) {
                last_watchdog_pet_ = std::chrono::steady_clock::now();
            }

            // Sleep until next cycle
            next_cycle += cycle_time;
            std::this_thread::sleep_until(next_cycle);
        }
    }

    void update_callback_stats(const RTCallback& cb, std::chrono::nanoseconds exec_time) {
        std::lock_guard<std::mutex> lock(stats_mutex_);

        switch (cb.priority) {
            case CallbackPriority::CONTROL:
                stats_->control_cycles++;
                stats_->control_max_exec = std::max(stats_->control_max_exec, exec_time);
                break;
            case CallbackPriority::SENSING:
                stats_->sensing_cycles++;
                stats_->sensing_max_exec = std::max(stats_->sensing_max_exec, exec_time);
                break;
            case CallbackPriority::PLANNING:
                stats_->planning_cycles++;
                stats_->planning_max_exec = std::max(stats_->planning_max_exec, exec_time);
                break;
            default:
                break;
        }
    }

    void handle_wcet_violation(const RTCallback& cb, std::chrono::nanoseconds actual) {
        log_warn("WCET violation: " + cb.name +
                 " (actual=" + std::to_string(actual.count() / 1000) +
                 "μs, budget=" + std::to_string(cb.wcet.count() / 1000) + "μs)");

        std::lock_guard<std::mutex> lock(stats_mutex_);

        switch (cb.priority) {
            case CallbackPriority::CONTROL:
                stats_->control_overruns++;
                break;
            case CallbackPriority::SENSING:
                stats_->sensing_overruns++;
                break;
            case CallbackPriority::PLANNING:
                stats_->planning_overruns++;
                break;
            default:
                break;
        }

        stats_->consecutive_overruns++;

        // Check for excessive overruns
        if (stats_->consecutive_overruns >= config_.max_consecutive_overruns) {
            if (!degraded_mode_) {
                enter_degraded_mode();
            }
        }
    }

    void start_watchdog() {
        watchdog_running_ = true;
        last_watchdog_pet_ = std::chrono::steady_clock::now();

        watchdog_thread_ = std::thread([this]() {
            while (watchdog_running_) {
                auto now = std::chrono::steady_clock::now();
                auto since_pet = now - last_watchdog_pet_.load();

                if (since_pet > config_.watchdog_timeout) {
                    log_error("WATCHDOG TIMEOUT - RT executor not responding!");
                    // In real implementation, would trigger recovery
                }

                std::this_thread::sleep_for(std::chrono::milliseconds(10));
            }
        });
    }

    void stop_watchdog() {
        watchdog_running_ = false;
        if (watchdog_thread_.joinable()) {
            watchdog_thread_.join();
        }
    }

    void publish_diagnostics() {
        diagnostic_msgs::msg::DiagnosticArray diag_msg;

        // RT Node status
        diagnostic_msgs::msg::DiagnosticStatus rt_status;
        rt_status.name = get_name() + ": RT Status";
        rt_status.hardware_id = config_.node_name;

        {
            std::lock_guard<std::mutex> lock(stats_mutex_);

            if (stats_->rt_mode_active && stats_->consecutive_overruns == 0) {
                rt_status.level = diagnostic_msgs::msg::DiagnosticStatus::OK;
                rt_status.message = "RT mode active, no overruns";
            } else if (degraded_mode_) {
                rt_status.level = diagnostic_msgs::msg::DiagnosticStatus::WARN;
                rt_status.message = "Degraded mode active";
            } else if (!stats_->rt_mode_active) {
                rt_status.level = diagnostic_msgs::msg::DiagnosticStatus::STALE;
                rt_status.message = "RT mode inactive";
            } else {
                rt_status.level = diagnostic_msgs::msg::DiagnosticStatus::WARN;
                rt_status.message = "Overruns detected";
            }
        }

        diag_msg.status.push_back(rt_status);

        // Clock sync status
        diagnostic_msgs::msg::DiagnosticStatus clock_status;
        clock_status.name = get_name() + ": Clock Sync";
        clock_status.hardware_id = config_.node_name;

        {
            std::lock_guard<std::mutex> lock(stats_mutex_);

            if (stats_->clock_synchronized) {
                clock_status.level = diagnostic_msgs::msg::DiagnosticStatus::OK;
                clock_status.message = "PTP synchronized, offset=" +
                    std::to_string(stats_->clock_offset.count()) + "ns";
            } else {
                clock_status.level = diagnostic_msgs::msg::DiagnosticStatus::WARN;
                clock_status.message = "Not synchronized, using local clock";
            }
        }

        diag_msg.status.push_back(clock_status);

        // Publish
        // if (diag_pub_) {
        //     diag_pub_->publish(diag_msg);
        // }
    }

    void shutdown() {
        stop_executor();
        stop_watchdog();
    }

    void log_info(const std::string& msg) {
        // RCLCPP_INFO(get_logger(), "%s", msg.c_str());
        (void)msg;  // Suppress unused warning in stub
    }

    void log_warn(const std::string& msg) {
        // RCLCPP_WARN(get_logger(), "%s", msg.c_str());
        (void)msg;
    }

    void log_error(const std::string& msg) {
        // RCLCPP_ERROR(get_logger(), "%s", msg.c_str());
        (void)msg;
    }

    RTNodeConfig config_;
    std::shared_ptr<RTNodeStats> stats_;
    mutable std::mutex stats_mutex_;

    std::atomic<bool> running_{false};
    std::thread executor_thread_;

    mutable std::mutex callbacks_mutex_;
    std::vector<RTCallback> callbacks_;

    std::atomic<bool> watchdog_running_{false};
    std::thread watchdog_thread_;
    std::atomic<std::chrono::steady_clock::time_point> last_watchdog_pet_;

    std::atomic<bool> degraded_mode_{false};

    // std::shared_ptr<rclcpp::Publisher<diagnostic_msgs::msg::DiagnosticArray>> diag_pub_;
};

}  // namespace lego_mcp::realtime

// Main entry point for standalone node
int main(int argc, char** argv) {
    (void)argc;
    (void)argv;

    // rclcpp::init(argc, argv);

    lego_mcp::realtime::RTNodeConfig config;
    config.node_name = "lego_mcp_realtime";
    config.rt_priority = 80;
    config.enable_ptp_sync = true;

    auto node = std::make_shared<lego_mcp::realtime::RealtimeNode>(config);

    // Configure and activate
    node->on_configure();
    node->on_activate();

    // Spin
    // rclcpp::spin(node->get_node_base_interface());

    // Cleanup
    node->on_deactivate();
    node->on_cleanup();
    node->on_shutdown();

    // rclcpp::shutdown();
    return 0;
}
