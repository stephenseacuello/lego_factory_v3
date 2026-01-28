/**
 * @file ptp_clock.cpp
 * @brief IEEE 1588 PTP Clock Implementation
 */

#include "lego_mcp_realtime/ptp_clock.hpp"

#include <algorithm>
#include <cmath>
#include <mutex>
#include <thread>
#include <vector>

#ifdef __linux__
#include <sys/time.h>
#include <time.h>
#endif

namespace lego_mcp::realtime {

class PTPClock::Impl {
public:
    explicit Impl(const PTPConfig& config)
        : config_(config), state_(PTPState::INITIALIZING) {}

    ~Impl() {
        stop();
    }

    bool start() {
        if (running_.exchange(true)) {
            return false;  // Already running
        }

        state_ = PTPState::LISTENING;
        sync_thread_ = std::thread(&Impl::sync_loop, this);

        return true;
    }

    void stop() noexcept {
        running_ = false;
        if (sync_thread_.joinable()) {
            sync_thread_.join();
        }
        state_ = PTPState::DISABLED;
    }

    PTPTimestamp now() const noexcept {
        struct timespec ts;
#ifdef __linux__
        clock_gettime(CLOCK_REALTIME, &ts);
#else
        auto now = std::chrono::system_clock::now();
        auto ns = std::chrono::duration_cast<std::chrono::nanoseconds>(
            now.time_since_epoch()
        ).count();
        ts.tv_sec = ns / 1000000000;
        ts.tv_nsec = ns % 1000000000;
#endif

        // Apply offset correction
        auto corrected_ns = ts.tv_nsec + offset_.load();
        while (corrected_ns < 0) {
            ts.tv_sec--;
            corrected_ns += 1000000000;
        }
        while (corrected_ns >= 1000000000) {
            ts.tv_sec++;
            corrected_ns -= 1000000000;
        }

        return PTPTimestamp{
            static_cast<uint64_t>(ts.tv_sec),
            static_cast<uint32_t>(corrected_ns)
        };
    }

    PTPState state() const noexcept {
        return state_.load();
    }

    PTPStats stats() const noexcept {
        std::lock_guard<std::mutex> lock(stats_mutex_);
        return stats_;
    }

    bool is_synchronized(std::chrono::nanoseconds max_offset) const noexcept {
        return state_ == PTPState::SLAVE &&
               std::abs(offset_.load()) <= max_offset.count();
    }

    void on_sync(SyncCallback callback) {
        std::lock_guard<std::mutex> lock(callback_mutex_);
        callbacks_.push_back(std::move(callback));
    }

    std::chrono::nanoseconds offset() const noexcept {
        return std::chrono::nanoseconds(offset_.load());
    }

    std::chrono::nanoseconds delay() const noexcept {
        return std::chrono::nanoseconds(delay_.load());
    }

    void resync() {
        state_ = PTPState::UNCALIBRATED;
        offset_ = 0;
        delay_ = 0;
    }

private:
    void sync_loop() {
        while (running_) {
            // Simulate PTP sync (in production, would use actual PTP messages)
            perform_sync();

            std::this_thread::sleep_for(config_.sync_interval);
        }
    }

    void perform_sync() {
        // Simulate delay request/response
        auto t1 = get_hw_timestamp();  // Sync sent
        std::this_thread::sleep_for(std::chrono::microseconds(100));
        auto t2 = get_hw_timestamp();  // Sync received

        // Delay request/response
        auto t3 = get_hw_timestamp();  // Delay_Req sent
        std::this_thread::sleep_for(std::chrono::microseconds(100));
        auto t4 = get_hw_timestamp();  // Delay_Resp received

        // Calculate offset and delay
        // offset = ((t2 - t1) - (t4 - t3)) / 2
        // delay = ((t2 - t1) + (t4 - t3)) / 2

        int64_t d1 = t2 - t1;
        int64_t d2 = t4 - t3;

        int64_t new_offset = (d1 - d2) / 2;
        int64_t new_delay = (d1 + d2) / 2;

        // Apply low-pass filter
        offset_ = static_cast<int64_t>(0.9 * offset_.load() + 0.1 * new_offset);
        delay_ = static_cast<int64_t>(0.9 * delay_.load() + 0.1 * new_delay);

        // Update state
        if (std::abs(offset_.load()) < 1000) {  // < 1us
            state_ = PTPState::SLAVE;
        } else {
            state_ = PTPState::UNCALIBRATED;
        }

        // Update stats
        {
            std::lock_guard<std::mutex> lock(stats_mutex_);
            stats_.offset = std::chrono::nanoseconds(offset_.load());
            stats_.delay = std::chrono::nanoseconds(delay_.load());
            stats_.sync_count++;
            stats_.last_sync = std::chrono::steady_clock::now();

            // Calculate jitter
            int64_t jitter = std::abs(new_offset - prev_offset_);
            stats_.jitter = std::chrono::nanoseconds(
                static_cast<int64_t>(0.9 * stats_.jitter.count() + 0.1 * jitter)
            );
            prev_offset_ = new_offset;
        }

        // Notify callbacks
        notify_sync();
    }

    int64_t get_hw_timestamp() const {
#ifdef __linux__
        struct timespec ts;
        clock_gettime(CLOCK_REALTIME, &ts);
        return ts.tv_sec * 1000000000LL + ts.tv_nsec;
#else
        auto now = std::chrono::high_resolution_clock::now();
        return std::chrono::duration_cast<std::chrono::nanoseconds>(
            now.time_since_epoch()
        ).count();
#endif
    }

    void notify_sync() {
        std::lock_guard<std::mutex> lock(callback_mutex_);
        auto current_stats = stats();
        for (const auto& callback : callbacks_) {
            try {
                callback(current_stats);
            } catch (...) {
                // Ignore callback exceptions
            }
        }
    }

    PTPConfig config_;
    std::atomic<PTPState> state_;
    std::atomic<bool> running_{false};
    std::thread sync_thread_;

    std::atomic<int64_t> offset_{0};
    std::atomic<int64_t> delay_{0};
    int64_t prev_offset_{0};

    mutable std::mutex stats_mutex_;
    PTPStats stats_;

    mutable std::mutex callback_mutex_;
    std::vector<SyncCallback> callbacks_;
};

PTPClock::PTPClock(const PTPConfig& config)
    : impl_(std::make_unique<Impl>(config)) {}

PTPClock::~PTPClock() = default;

PTPClock::PTPClock(PTPClock&&) noexcept = default;
PTPClock& PTPClock::operator=(PTPClock&&) noexcept = default;

bool PTPClock::start() {
    return impl_->start();
}

void PTPClock::stop() noexcept {
    impl_->stop();
}

PTPTimestamp PTPClock::now() const noexcept {
    return impl_->now();
}

PTPState PTPClock::state() const noexcept {
    return impl_->state();
}

PTPStats PTPClock::stats() const noexcept {
    return impl_->stats();
}

bool PTPClock::is_synchronized(std::chrono::nanoseconds max_offset) const noexcept {
    return impl_->is_synchronized(max_offset);
}

void PTPClock::on_sync(SyncCallback callback) {
    impl_->on_sync(std::move(callback));
}

std::chrono::nanoseconds PTPClock::offset() const noexcept {
    return impl_->offset();
}

std::chrono::nanoseconds PTPClock::delay() const noexcept {
    return impl_->delay();
}

void PTPClock::resync() {
    impl_->resync();
}

}  // namespace lego_mcp::realtime
