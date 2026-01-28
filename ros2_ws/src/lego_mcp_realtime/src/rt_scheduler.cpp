/**
 * @file rt_scheduler.cpp
 * @brief Real-Time Scheduler Implementation
 */

#include "lego_mcp_realtime/rt_scheduler.hpp"

#include <algorithm>
#include <mutex>
#include <thread>
#include <vector>
#include <stdexcept>

#ifdef __linux__
#include <pthread.h>
#include <sched.h>
#include <sys/mman.h>
#include <sys/resource.h>
#include <unistd.h>
#endif

namespace lego_mcp::realtime {

// RTTask Implementation
class RTTask::Impl {
public:
    Impl(const TaskConfig& config, TaskFunction func)
        : config_(config), func_(std::move(func)), stats_{config.name} {}

    ~Impl() {
        stop();
    }

    bool start() {
        if (running_.exchange(true)) {
            return false;
        }

        thread_ = std::thread(&Impl::run, this);
        return true;
    }

    void stop() noexcept {
        running_ = false;
        if (thread_.joinable()) {
            thread_.join();
        }
    }

    bool is_running() const noexcept {
        return running_;
    }

    TaskStats stats() const noexcept {
        std::lock_guard<std::mutex> lock(stats_mutex_);
        return stats_;
    }

    const std::string& name() const noexcept {
        return config_.name;
    }

private:
    void run() {
        // Set thread name
#ifdef __linux__
        pthread_setname_np(pthread_self(), config_.name.substr(0, 15).c_str());
#endif

        // Apply RT priority
        apply_rt_config();

        // Periodic task loop
        if (config_.period.count() > 0) {
            run_periodic();
        } else {
            // Aperiodic - just run once
            run_once();
        }
    }

    void apply_rt_config() {
#ifdef __linux__
        // Set scheduling policy and priority
        struct sched_param param;
        param.sched_priority = static_cast<int>(config_.priority);

        int policy = SCHED_OTHER;
        switch (config_.policy) {
            case RTPolicy::FIFO:
                policy = SCHED_FIFO;
                break;
            case RTPolicy::RR:
                policy = SCHED_RR;
                break;
            default:
                policy = SCHED_OTHER;
                param.sched_priority = 0;
        }

        if (pthread_setschedparam(pthread_self(), policy, &param) != 0) {
            // Failed to set RT priority - may need root
        }

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

    void run_periodic() {
        auto next_wake = std::chrono::steady_clock::now();

        while (running_) {
            next_wake += config_.period;

            auto start = std::chrono::steady_clock::now();

            // Execute task
            try {
                func_();
            } catch (...) {
                // Log error
            }

            auto end = std::chrono::steady_clock::now();
            auto execution_time = std::chrono::duration_cast<std::chrono::nanoseconds>(end - start);

            // Update stats
            update_stats(execution_time);

            // Sleep until next period
            std::this_thread::sleep_until(next_wake);
        }
    }

    void run_once() {
        auto start = std::chrono::steady_clock::now();

        try {
            func_();
        } catch (...) {
            // Log error
        }

        auto end = std::chrono::steady_clock::now();
        auto execution_time = std::chrono::duration_cast<std::chrono::nanoseconds>(end - start);

        update_stats(execution_time);
    }

    void update_stats(std::chrono::nanoseconds execution_time) {
        std::lock_guard<std::mutex> lock(stats_mutex_);

        stats_.execution_count++;
        stats_.total_execution_time += execution_time;
        stats_.min_execution_time = std::min(stats_.min_execution_time, execution_time);
        stats_.max_execution_time = std::max(stats_.max_execution_time, execution_time);
        stats_.avg_execution_time = stats_.total_execution_time / stats_.execution_count;

        // Check deadline
        if (config_.deadline.count() > 0 && execution_time > config_.deadline) {
            stats_.deadline_misses++;
        }

        // Calculate utilization
        if (config_.period.count() > 0) {
            stats_.cpu_utilization = static_cast<double>(stats_.avg_execution_time.count()) /
                                     static_cast<double>(config_.period.count());
        }
    }

    TaskConfig config_;
    TaskFunction func_;
    std::atomic<bool> running_{false};
    std::thread thread_;

    mutable std::mutex stats_mutex_;
    TaskStats stats_;
};

RTTask::RTTask(const TaskConfig& config, TaskFunction func)
    : impl_(std::make_unique<Impl>(config, std::move(func))) {
}

RTTask::~RTTask() = default;

bool RTTask::start() {
    return impl_->start();
}

void RTTask::stop() noexcept {
    impl_->stop();
}

bool RTTask::is_running() const noexcept {
    return impl_->is_running();
}

TaskStats RTTask::stats() const noexcept {
    return impl_->stats();
}

const std::string& RTTask::name() const noexcept {
    return impl_->name();
}

// RTScheduler Implementation
class RTScheduler::Impl {
public:
    Impl() = default;

    bool configure_system() {
#ifdef __linux__
        // Lock current and future memory
        if (mlockall(MCL_CURRENT | MCL_FUTURE) != 0) {
            return false;
        }

        // Set resource limits for RT priority
        struct rlimit rl;
        rl.rlim_cur = 99;
        rl.rlim_max = 99;
        setrlimit(RLIMIT_RTPRIO, &rl);

        return true;
#else
        return true;  // Non-Linux systems
#endif
    }

    bool set_realtime_priority(RTPriority priority, RTPolicy policy) {
#ifdef __linux__
        struct sched_param param;
        param.sched_priority = static_cast<int>(priority);

        int pol = SCHED_OTHER;
        switch (policy) {
            case RTPolicy::FIFO:
                pol = SCHED_FIFO;
                break;
            case RTPolicy::RR:
                pol = SCHED_RR;
                break;
            default:
                pol = SCHED_OTHER;
                param.sched_priority = 0;
        }

        return pthread_setschedparam(pthread_self(), pol, &param) == 0;
#else
        (void)priority;
        (void)policy;
        return false;
#endif
    }

    bool set_cpu_affinity(const std::vector<int>& cpus) {
#ifdef __linux__
        if (cpus.empty()) {
            return false;
        }

        cpu_set_t cpuset;
        CPU_ZERO(&cpuset);
        for (int cpu : cpus) {
            CPU_SET(cpu, &cpuset);
        }
        return pthread_setaffinity_np(pthread_self(), sizeof(cpu_set_t), &cpuset) == 0;
#else
        (void)cpus;
        return false;
#endif
    }

    bool lock_memory() {
#ifdef __linux__
        return mlockall(MCL_CURRENT | MCL_FUTURE) == 0;
#else
        return false;
#endif
    }

    std::shared_ptr<RTTask> create_task(const TaskConfig& config, RTTask::TaskFunction func) {
        auto task = std::make_shared<RTTask>(config, std::move(func));
        std::lock_guard<std::mutex> lock(tasks_mutex_);
        tasks_.push_back(task);
        return task;
    }

    std::vector<TaskStats> stats() const {
        std::vector<TaskStats> result;
        std::lock_guard<std::mutex> lock(tasks_mutex_);
        for (const auto& task : tasks_) {
            result.push_back(task->stats());
        }
        return result;
    }

private:
    mutable std::mutex tasks_mutex_;
    std::vector<std::shared_ptr<RTTask>> tasks_;
};

RTScheduler::RTScheduler()
    : impl_(std::make_unique<Impl>()) {}

RTScheduler::~RTScheduler() = default;

bool RTScheduler::configure_system() {
    return impl_->configure_system();
}

bool RTScheduler::set_realtime_priority(RTPriority priority, RTPolicy policy) {
    return impl_->set_realtime_priority(priority, policy);
}

bool RTScheduler::set_cpu_affinity(const std::vector<int>& cpus) {
    return impl_->set_cpu_affinity(cpus);
}

bool RTScheduler::lock_memory() {
    return impl_->lock_memory();
}

std::shared_ptr<RTTask> RTScheduler::create_task(
    const TaskConfig& config,
    RTTask::TaskFunction func
) {
    return impl_->create_task(config, std::move(func));
}

int RTScheduler::max_priority(RTPolicy policy) noexcept {
#ifdef __linux__
    int pol = (policy == RTPolicy::FIFO) ? SCHED_FIFO :
              (policy == RTPolicy::RR) ? SCHED_RR : SCHED_OTHER;
    return sched_get_priority_max(pol);
#else
    (void)policy;
    return 99;
#endif
}

int RTScheduler::min_priority(RTPolicy policy) noexcept {
#ifdef __linux__
    int pol = (policy == RTPolicy::FIFO) ? SCHED_FIFO :
              (policy == RTPolicy::RR) ? SCHED_RR : SCHED_OTHER;
    return sched_get_priority_min(pol);
#else
    (void)policy;
    return 1;
#endif
}

bool RTScheduler::is_rt_available() noexcept {
#ifdef __linux__
    return true;
#else
    return false;
#endif
}

std::vector<TaskStats> RTScheduler::stats() const {
    return impl_->stats();
}

void RTScheduler::yield() noexcept {
#ifdef __linux__
    sched_yield();
#else
    std::this_thread::yield();
#endif
}

void RTScheduler::sleep_until(std::chrono::steady_clock::time_point until) {
    std::this_thread::sleep_until(until);
}

// RTPriorityGuard Implementation
RTPriorityGuard::RTPriorityGuard(RTPriority priority, RTPolicy policy) {
#ifdef __linux__
    // Save current settings
    struct sched_param param;
    if (pthread_getschedparam(pthread_self(), &original_policy_, &param) == 0) {
        original_priority_ = param.sched_priority;

        // Set new priority
        param.sched_priority = static_cast<int>(priority);
        int pol = (policy == RTPolicy::FIFO) ? SCHED_FIFO :
                  (policy == RTPolicy::RR) ? SCHED_RR : SCHED_OTHER;

        if (pthread_setschedparam(pthread_self(), pol, &param) == 0) {
            active_ = true;
        }
    }
#else
    (void)priority;
    (void)policy;
#endif
}

RTPriorityGuard::~RTPriorityGuard() {
#ifdef __linux__
    if (active_) {
        struct sched_param param;
        param.sched_priority = original_priority_;
        pthread_setschedparam(pthread_self(), original_policy_, &param);
    }
#endif
}

}  // namespace lego_mcp::realtime
