/**
 * @file watchdog_timer.cpp
 * @brief Hardware Watchdog Timer Implementation
 *
 * IEC 61508 SIL 2+ Compliant
 */

#include "lego_mcp_safety_certified/watchdog_timer.hpp"

#include <fcntl.h>
#include <unistd.h>

#ifdef __linux__
#include <linux/watchdog.h>
#include <sys/ioctl.h>
#endif

#include <thread>

namespace lego_mcp
{

WatchdogTimer::WatchdogTimer(
    const WatchdogConfig& config,
    TimeoutCallback timeout_callback,
    PreTimeoutCallback pre_timeout_callback)
    : config_(config)
    , timeout_callback_(std::move(timeout_callback))
    , pre_timeout_callback_(std::move(pre_timeout_callback))
    , last_feed_time_(std::chrono::steady_clock::now())
{
}

WatchdogTimer::~WatchdogTimer()
{
    static_cast<void>(stop());
}

bool WatchdogTimer::start()
{
    if (state_.load(std::memory_order_acquire) == WatchdogState::RUNNING) {
        return true;  // Already running
    }

    // Open hardware watchdog if enabled
    if (config_.use_hardware_watchdog) {
        if (!open_hardware_watchdog()) {
            // Hardware watchdog not available - continue with software only
            if (!config_.use_software_watchdog) {
                return false;  // No watchdog available
            }
        }
    }

    // Reset timing
    last_feed_time_.store(std::chrono::steady_clock::now(), std::memory_order_release);
    stats_.last_feed = std::chrono::steady_clock::now();
    stats_.feed_count = 0U;

    // Start software watchdog thread if enabled
    if (config_.use_software_watchdog) {
        sw_watchdog_running_.store(true, std::memory_order_release);

        std::thread([this]() {
            software_watchdog_thread();
        }).detach();
    }

    state_.store(WatchdogState::RUNNING, std::memory_order_release);
    return true;
}

bool WatchdogTimer::stop()
{
    const auto current_state = state_.load(std::memory_order_acquire);
    if (current_state == WatchdogState::STOPPED) {
        return true;
    }

    // Stop software watchdog
    sw_watchdog_running_.store(false, std::memory_order_release);

    // Close hardware watchdog with magic close
    close_hardware_watchdog();

    state_.store(WatchdogState::STOPPED, std::memory_order_release);
    return true;
}

bool WatchdogTimer::feed() noexcept
{
    const auto current_state = state_.load(std::memory_order_acquire);
    if (current_state != WatchdogState::RUNNING) {
        return false;
    }

    const auto now = std::chrono::steady_clock::now();
    const auto last = last_feed_time_.load(std::memory_order_acquire);
    const auto interval = std::chrono::duration_cast<std::chrono::microseconds>(now - last);

    // Update statistics
    stats_.feed_count++;
    if (interval > stats_.max_feed_interval) {
        stats_.max_feed_interval = interval;
    }
    // Simple moving average
    stats_.avg_feed_interval = std::chrono::microseconds(
        (stats_.avg_feed_interval.count() * (stats_.feed_count - 1) + interval.count()) /
        stats_.feed_count);
    stats_.last_feed = now;

    // Update last feed time
    last_feed_time_.store(now, std::memory_order_release);

    // Feed hardware watchdog
    if (hw_watchdog_fd_ >= 0) {
        if (!feed_hardware_watchdog()) {
            return false;
        }
    }

    return true;
}

std::chrono::milliseconds WatchdogTimer::time_remaining() const noexcept
{
    const auto current_state = state_.load(std::memory_order_acquire);
    if (current_state != WatchdogState::RUNNING) {
        return std::chrono::milliseconds(0);
    }

    const auto now = std::chrono::steady_clock::now();
    const auto last = last_feed_time_.load(std::memory_order_acquire);
    const auto elapsed = std::chrono::duration_cast<std::chrono::milliseconds>(now - last);

    if (elapsed >= config_.timeout) {
        return std::chrono::milliseconds(0);
    }

    return config_.timeout - elapsed;
}

bool WatchdogTimer::open_hardware_watchdog()
{
    #ifdef __linux__
    hw_watchdog_fd_ = ::open(config_.hw_watchdog_device.c_str(), O_RDWR);
    if (hw_watchdog_fd_ < 0) {
        return false;
    }

    // Set timeout
    int timeout_sec = static_cast<int>(config_.timeout.count() / 1000);
    if (timeout_sec < 1) {
        timeout_sec = 1;
    }

    if (::ioctl(hw_watchdog_fd_, WDIOC_SETTIMEOUT, &timeout_sec) < 0) {
        ::close(hw_watchdog_fd_);
        hw_watchdog_fd_ = -1;
        return false;
    }

    // Set pre-timeout if supported
    if (config_.pre_timeout.count() > 0) {
        int pretimeout_sec = static_cast<int>(config_.pre_timeout.count() / 1000);
        static_cast<void>(::ioctl(hw_watchdog_fd_, WDIOC_SETPRETIMEOUT, &pretimeout_sec));
    }

    return true;
    #else
    return false;
    #endif
}

void WatchdogTimer::close_hardware_watchdog() noexcept
{
    #ifdef __linux__
    if (hw_watchdog_fd_ >= 0) {
        // Magic close - write 'V' to disable watchdog
        const char magic = 'V';
        static_cast<void>(::write(hw_watchdog_fd_, &magic, 1));
        ::close(hw_watchdog_fd_);
        hw_watchdog_fd_ = -1;
    }
    #endif
}

bool WatchdogTimer::feed_hardware_watchdog() noexcept
{
    #ifdef __linux__
    if (hw_watchdog_fd_ >= 0) {
        // Standard keepalive ioctl
        int dummy = 0;
        if (::ioctl(hw_watchdog_fd_, WDIOC_KEEPALIVE, &dummy) < 0) {
            // Fallback to write
            const char feed = '\0';
            if (::write(hw_watchdog_fd_, &feed, 1) < 0) {
                return false;
            }
        }
        return true;
    }
    #endif
    return false;
}

void WatchdogTimer::software_watchdog_thread()
{
    // Check interval - check more frequently than timeout
    const auto check_interval = config_.timeout / 4;

    while (sw_watchdog_running_.load(std::memory_order_acquire)) {
        std::this_thread::sleep_for(check_interval);

        if (!sw_watchdog_running_.load(std::memory_order_acquire)) {
            break;
        }

        const auto now = std::chrono::steady_clock::now();
        const auto last = last_feed_time_.load(std::memory_order_acquire);
        const auto elapsed = std::chrono::duration_cast<std::chrono::milliseconds>(now - last);

        // Check for pre-timeout
        if (pre_timeout_callback_ && elapsed >= (config_.timeout - config_.pre_timeout)) {
            const auto remaining = config_.timeout - elapsed;
            stats_.pre_timeout_count++;
            pre_timeout_callback_(remaining);
        }

        // Check for timeout
        if (elapsed >= config_.timeout) {
            trigger_timeout();
            break;
        }
    }
}

void WatchdogTimer::trigger_timeout() noexcept
{
    // Only trigger once
    WatchdogState expected = WatchdogState::RUNNING;
    if (!state_.compare_exchange_strong(expected, WatchdogState::TRIGGERED,
                                         std::memory_order_acq_rel)) {
        return;  // Already triggered or stopped
    }

    stats_.timeout_count++;

    // Call timeout callback
    if (timeout_callback_) {
        timeout_callback_();
    }
}

}  // namespace lego_mcp
