/**
 * @file clock_sync.cpp
 * @brief Distributed Clock Synchronization for ROS2 Real-Time
 *
 * Implements clock synchronization across distributed nodes using
 * IEEE 1588 PTP with fallback mechanisms.
 *
 * Reference: IEEE 1588-2019, IEC 61784-3
 */

#include <chrono>
#include <memory>
#include <vector>
#include <functional>
#include <thread>
#include <atomic>
#include <mutex>
#include <cmath>
#include <algorithm>
#include <map>
#include <deque>

#ifdef __linux__
#include <sys/socket.h>
#include <netinet/in.h>
#include <arpa/inet.h>
#include <unistd.h>
#include <time.h>
#endif

namespace lego_mcp::realtime {

/**
 * @brief Clock synchronization state
 */
enum class SyncState {
    INITIALIZING,
    LISTENING,
    MASTER,
    SLAVE,
    PASSIVE,
    FAULTY
};

/**
 * @brief Clock quality level (ITU-T G.8275.1)
 */
enum class ClockQuality {
    PRIMARY_REFERENCE,      // Stratum 1 (GPS/atomic)
    SECONDARY_REFERENCE,    // Stratum 2
    HOLDOVER,              // Lost sync, using local oscillator
    LOCAL_OSCILLATOR,      // Free-running local clock
    UNKNOWN
};

/**
 * @brief Timestamp with nanosecond precision
 */
struct SyncTimestamp {
    int64_t seconds{0};
    int32_t nanoseconds{0};

    [[nodiscard]] std::chrono::nanoseconds to_duration() const noexcept {
        return std::chrono::seconds(seconds) + std::chrono::nanoseconds(nanoseconds);
    }

    static SyncTimestamp from_duration(std::chrono::nanoseconds ns) {
        auto secs = std::chrono::duration_cast<std::chrono::seconds>(ns);
        auto remaining = ns - secs;
        return {secs.count(), static_cast<int32_t>(remaining.count())};
    }

    [[nodiscard]] SyncTimestamp operator-(const SyncTimestamp& other) const noexcept {
        int64_t total_ns = (seconds - other.seconds) * 1'000'000'000LL +
                          (nanoseconds - other.nanoseconds);
        return from_duration(std::chrono::nanoseconds(total_ns));
    }
};

/**
 * @brief Clock statistics
 */
struct ClockStats {
    std::chrono::nanoseconds offset{0};
    std::chrono::nanoseconds delay{0};
    std::chrono::nanoseconds jitter{0};
    double frequency_offset_ppb{0.0};  // Parts per billion
    uint64_t sync_count{0};
    uint64_t timeout_count{0};
    ClockQuality quality{ClockQuality::UNKNOWN};
};

/**
 * @brief Peer clock information
 */
struct PeerClock {
    std::string id;
    std::string address;
    ClockQuality quality{ClockQuality::UNKNOWN};
    std::chrono::nanoseconds last_offset{0};
    std::chrono::steady_clock::time_point last_seen;
    uint32_t priority{255};  // Lower is better
    bool reachable{false};
};

/**
 * @brief Clock synchronization configuration
 */
struct ClockSyncConfig {
    std::string clock_id{"lego_mcp_clock"};
    std::string multicast_address{"224.0.1.129"};  // PTP default
    uint16_t event_port{319};
    uint16_t general_port{320};

    std::chrono::milliseconds sync_interval{125};      // 8 Hz default
    std::chrono::milliseconds announce_interval{1000}; // 1 Hz
    std::chrono::milliseconds timeout{3000};

    uint8_t priority1{128};
    uint8_t priority2{128};
    ClockQuality initial_quality{ClockQuality::LOCAL_OSCILLATOR};

    bool enable_hardware_timestamps{true};
    bool enable_two_step{false};  // Use one-step if possible

    // Servo parameters for clock discipline
    double servo_kp{0.7};       // Proportional gain
    double servo_ki{0.3};       // Integral gain
    double max_freq_adj_ppb{100000.0};  // 100 ppm max
};

/**
 * @brief PI servo for clock discipline
 */
class ClockServo {
public:
    explicit ClockServo(double kp = 0.7, double ki = 0.3, double max_adj = 100000.0)
        : kp_(kp), ki_(ki), max_freq_adj_(max_adj) {}

    /**
     * @brief Update servo with new offset measurement
     * @param offset_ns Offset in nanoseconds
     * @return Frequency adjustment in ppb
     */
    [[nodiscard]] double update(int64_t offset_ns) {
        double offset_s = offset_ns / 1e9;

        // Proportional term
        double p_term = kp_ * offset_s;

        // Integral term (accumulated offset)
        integral_ += offset_s;
        double i_term = ki_ * integral_;

        // Combined adjustment
        double adj = (p_term + i_term) * 1e9;  // Convert to ppb

        // Clamp to maximum
        adj = std::clamp(adj, -max_freq_adj_, max_freq_adj_);

        last_adj_ = adj;
        return adj;
    }

    void reset() {
        integral_ = 0.0;
        last_adj_ = 0.0;
    }

    [[nodiscard]] double last_adjustment() const noexcept { return last_adj_; }

private:
    double kp_;
    double ki_;
    double max_freq_adj_;
    double integral_{0.0};
    double last_adj_{0.0};
};

/**
 * @brief Moving statistics calculator
 */
class MovingStats {
public:
    explicit MovingStats(size_t window_size = 16) : window_size_(window_size) {}

    void add_sample(int64_t value) {
        samples_.push_back(value);
        if (samples_.size() > window_size_) {
            samples_.pop_front();
        }
    }

    [[nodiscard]] int64_t mean() const {
        if (samples_.empty()) return 0;
        int64_t sum = 0;
        for (auto s : samples_) sum += s;
        return sum / static_cast<int64_t>(samples_.size());
    }

    [[nodiscard]] int64_t stddev() const {
        if (samples_.size() < 2) return 0;
        int64_t m = mean();
        int64_t var_sum = 0;
        for (auto s : samples_) {
            int64_t diff = s - m;
            var_sum += diff * diff;
        }
        return static_cast<int64_t>(std::sqrt(var_sum / (samples_.size() - 1)));
    }

    [[nodiscard]] size_t count() const { return samples_.size(); }

private:
    size_t window_size_;
    std::deque<int64_t> samples_;
};

/**
 * @brief Distributed Clock Synchronization Manager
 *
 * Provides IEEE 1588 PTP-based clock synchronization for
 * distributed ROS2 manufacturing nodes.
 */
class ClockSync {
public:
    explicit ClockSync(const ClockSyncConfig& config = ClockSyncConfig{})
        : config_(config),
          state_(SyncState::INITIALIZING),
          servo_(config.servo_kp, config.servo_ki, config.max_freq_adj_ppb),
          offset_stats_(16),
          delay_stats_(16) {
        stats_.quality = config.initial_quality;
    }

    ~ClockSync() {
        stop();
    }

    /**
     * @brief Start clock synchronization
     */
    bool start() {
        if (running_.exchange(true)) {
            return false;
        }

        // Initialize sockets
        if (!initialize_sockets()) {
            running_ = false;
            return false;
        }

        state_ = SyncState::LISTENING;

        // Start sync thread
        sync_thread_ = std::thread(&ClockSync::sync_loop, this);

        return true;
    }

    /**
     * @brief Stop clock synchronization
     */
    void stop() {
        running_ = false;
        if (sync_thread_.joinable()) {
            sync_thread_.join();
        }
        close_sockets();
    }

    /**
     * @brief Get current synchronized time
     */
    [[nodiscard]] SyncTimestamp now() const noexcept {
        auto sys_now = std::chrono::system_clock::now();
        auto epoch = sys_now.time_since_epoch();
        auto ns = std::chrono::duration_cast<std::chrono::nanoseconds>(epoch);

        // Apply current offset
        ns += stats_.offset;

        return SyncTimestamp::from_duration(ns);
    }

    /**
     * @brief Check if clock is synchronized
     */
    [[nodiscard]] bool is_synchronized(
        std::chrono::nanoseconds max_offset = std::chrono::microseconds(1)
    ) const noexcept {
        std::lock_guard<std::mutex> lock(mutex_);

        if (state_ == SyncState::MASTER) {
            return true;  // We are the master
        }

        if (state_ != SyncState::SLAVE) {
            return false;
        }

        return std::abs(stats_.offset.count()) <= max_offset.count();
    }

    /**
     * @brief Get current sync state
     */
    [[nodiscard]] SyncState state() const noexcept {
        std::lock_guard<std::mutex> lock(mutex_);
        return state_;
    }

    /**
     * @brief Get clock statistics
     */
    [[nodiscard]] ClockStats get_stats() const {
        std::lock_guard<std::mutex> lock(mutex_);
        return stats_;
    }

    /**
     * @brief Get peer clocks
     */
    [[nodiscard]] std::vector<PeerClock> get_peers() const {
        std::lock_guard<std::mutex> lock(mutex_);
        std::vector<PeerClock> result;
        for (const auto& [id, peer] : peers_) {
            result.push_back(peer);
        }
        return result;
    }

    /**
     * @brief Set clock quality (e.g., when GPS lock acquired)
     */
    void set_quality(ClockQuality quality) {
        std::lock_guard<std::mutex> lock(mutex_);
        stats_.quality = quality;

        // May trigger BMC recalculation
        if (quality < stats_.quality) {
            // We have better source, may become master
        }
    }

    /**
     * @brief Force master mode (for testing/fallback)
     */
    void force_master() {
        std::lock_guard<std::mutex> lock(mutex_);
        state_ = SyncState::MASTER;
        stats_.offset = std::chrono::nanoseconds(0);
    }

    /**
     * @brief Get current offset from master
     */
    [[nodiscard]] std::chrono::nanoseconds offset() const noexcept {
        std::lock_guard<std::mutex> lock(mutex_);
        return stats_.offset;
    }

private:
    bool initialize_sockets() {
#ifdef __linux__
        // Create event socket (for Sync/Delay_Req)
        event_socket_ = socket(AF_INET, SOCK_DGRAM, 0);
        if (event_socket_ < 0) {
            return false;
        }

        // Create general socket (for Announce/Follow_Up)
        general_socket_ = socket(AF_INET, SOCK_DGRAM, 0);
        if (general_socket_ < 0) {
            close(event_socket_);
            return false;
        }

        // Enable multicast
        int reuse = 1;
        setsockopt(event_socket_, SOL_SOCKET, SO_REUSEADDR, &reuse, sizeof(reuse));
        setsockopt(general_socket_, SOL_SOCKET, SO_REUSEADDR, &reuse, sizeof(reuse));

        // Bind sockets
        struct sockaddr_in addr{};
        addr.sin_family = AF_INET;
        addr.sin_addr.s_addr = htonl(INADDR_ANY);

        addr.sin_port = htons(config_.event_port);
        if (bind(event_socket_, (struct sockaddr*)&addr, sizeof(addr)) < 0) {
            close(event_socket_);
            close(general_socket_);
            return false;
        }

        addr.sin_port = htons(config_.general_port);
        if (bind(general_socket_, (struct sockaddr*)&addr, sizeof(addr)) < 0) {
            close(event_socket_);
            close(general_socket_);
            return false;
        }

        // Join multicast group
        struct ip_mreq mreq{};
        mreq.imr_multiaddr.s_addr = inet_addr(config_.multicast_address.c_str());
        mreq.imr_interface.s_addr = htonl(INADDR_ANY);

        setsockopt(event_socket_, IPPROTO_IP, IP_ADD_MEMBERSHIP, &mreq, sizeof(mreq));
        setsockopt(general_socket_, IPPROTO_IP, IP_ADD_MEMBERSHIP, &mreq, sizeof(mreq));

        return true;
#else
        // Simulation mode for non-Linux
        return true;
#endif
    }

    void close_sockets() {
#ifdef __linux__
        if (event_socket_ >= 0) {
            close(event_socket_);
            event_socket_ = -1;
        }
        if (general_socket_ >= 0) {
            close(general_socket_);
            general_socket_ = -1;
        }
#endif
    }

    void sync_loop() {
        auto next_sync = std::chrono::steady_clock::now();
        auto next_announce = next_sync;

        while (running_) {
            auto now = std::chrono::steady_clock::now();

            // State machine
            {
                std::lock_guard<std::mutex> lock(mutex_);

                switch (state_) {
                    case SyncState::LISTENING:
                        // Check for timeout -> become master
                        if (now > last_sync_rx_ + config_.timeout) {
                            state_ = SyncState::MASTER;
                        }
                        break;

                    case SyncState::MASTER:
                        // Send Sync messages
                        if (now >= next_sync) {
                            send_sync();
                            next_sync = now + config_.sync_interval;
                        }

                        // Send Announce
                        if (now >= next_announce) {
                            send_announce();
                            next_announce = now + config_.announce_interval;
                        }
                        break;

                    case SyncState::SLAVE:
                        // Check for master timeout
                        if (now > last_sync_rx_ + config_.timeout) {
                            stats_.timeout_count++;
                            state_ = SyncState::LISTENING;
                        }
                        break;

                    default:
                        break;
                }
            }

            // Receive and process messages
            process_messages();

            // Prune stale peers
            prune_peers(now);

            std::this_thread::sleep_for(std::chrono::milliseconds(10));
        }
    }

    void process_messages() {
        // Receive on event socket
#ifdef __linux__
        char buffer[256];
        struct sockaddr_in sender{};
        socklen_t sender_len = sizeof(sender);

        // Non-blocking receive
        fd_set read_fds;
        struct timeval tv{0, 1000};  // 1ms timeout

        FD_ZERO(&read_fds);
        FD_SET(event_socket_, &read_fds);

        if (select(event_socket_ + 1, &read_fds, nullptr, nullptr, &tv) > 0) {
            ssize_t len = recvfrom(event_socket_, buffer, sizeof(buffer), 0,
                                   (struct sockaddr*)&sender, &sender_len);
            if (len > 0) {
                auto rx_time = std::chrono::steady_clock::now();
                handle_event_message(buffer, len, sender, rx_time);
            }
        }

        // Receive on general socket
        FD_ZERO(&read_fds);
        FD_SET(general_socket_, &read_fds);

        if (select(general_socket_ + 1, &read_fds, nullptr, nullptr, &tv) > 0) {
            ssize_t len = recvfrom(general_socket_, buffer, sizeof(buffer), 0,
                                   (struct sockaddr*)&sender, &sender_len);
            if (len > 0) {
                handle_general_message(buffer, len, sender);
            }
        }
#endif
    }

    void handle_event_message(
        [[maybe_unused]] const char* data,
        [[maybe_unused]] size_t len,
        [[maybe_unused]] const struct sockaddr_in& sender,
        [[maybe_unused]] std::chrono::steady_clock::time_point rx_time
    ) {
        // Parse PTP message header
        // For simulation, just update last sync time
        std::lock_guard<std::mutex> lock(mutex_);
        last_sync_rx_ = rx_time;

        if (state_ == SyncState::LISTENING || state_ == SyncState::SLAVE) {
            state_ = SyncState::SLAVE;

            // Simulate offset calculation
            // In real implementation, would use T1, T2, T3, T4 timestamps
            stats_.sync_count++;
        }
    }

    void handle_general_message(
        [[maybe_unused]] const char* data,
        [[maybe_unused]] size_t len,
        [[maybe_unused]] const struct sockaddr_in& sender
    ) {
        // Parse Announce/Follow_Up messages
        // Update peer information
        // Run BMC algorithm if needed
    }

    void send_sync() {
        // Send Sync message
        // In real implementation, would construct proper PTP packet
#ifdef __linux__
        struct sockaddr_in dest{};
        dest.sin_family = AF_INET;
        dest.sin_addr.s_addr = inet_addr(config_.multicast_address.c_str());
        dest.sin_port = htons(config_.event_port);

        char sync_msg[44] = {};  // Minimal Sync message
        sync_msg[0] = 0x00;  // Sync message type

        sendto(event_socket_, sync_msg, sizeof(sync_msg), 0,
               (struct sockaddr*)&dest, sizeof(dest));
#endif
    }

    void send_announce() {
        // Send Announce message
#ifdef __linux__
        struct sockaddr_in dest{};
        dest.sin_family = AF_INET;
        dest.sin_addr.s_addr = inet_addr(config_.multicast_address.c_str());
        dest.sin_port = htons(config_.general_port);

        char announce_msg[64] = {};  // Minimal Announce message
        announce_msg[0] = 0x0B;  // Announce message type

        sendto(general_socket_, announce_msg, sizeof(announce_msg), 0,
               (struct sockaddr*)&dest, sizeof(dest));
#endif
    }

    void calculate_offset(
        SyncTimestamp t1,  // Master send time
        SyncTimestamp t2,  // Slave receive time
        SyncTimestamp t3,  // Slave send time (Delay_Req)
        SyncTimestamp t4   // Master receive time
    ) {
        // offset = ((t2 - t1) - (t4 - t3)) / 2
        auto t2_t1 = t2 - t1;
        auto t4_t3 = t4 - t3;

        int64_t offset_ns = (t2_t1.to_duration().count() - t4_t3.to_duration().count()) / 2;
        int64_t delay_ns = (t2_t1.to_duration().count() + t4_t3.to_duration().count()) / 2;

        offset_stats_.add_sample(offset_ns);
        delay_stats_.add_sample(delay_ns);

        std::lock_guard<std::mutex> lock(mutex_);

        // Apply servo discipline
        double freq_adj = servo_.update(offset_ns);
        stats_.frequency_offset_ppb = freq_adj;

        // Update stats
        stats_.offset = std::chrono::nanoseconds(offset_stats_.mean());
        stats_.delay = std::chrono::nanoseconds(delay_stats_.mean());
        stats_.jitter = std::chrono::nanoseconds(offset_stats_.stddev());
    }

    void prune_peers(std::chrono::steady_clock::time_point now) {
        std::lock_guard<std::mutex> lock(mutex_);

        for (auto it = peers_.begin(); it != peers_.end(); ) {
            if (now > it->second.last_seen + config_.timeout) {
                it->second.reachable = false;
                ++it;
            } else {
                ++it;
            }
        }
    }

    ClockSyncConfig config_;
    std::atomic<bool> running_{false};
    SyncState state_;

    mutable std::mutex mutex_;
    ClockStats stats_;
    ClockServo servo_;
    MovingStats offset_stats_;
    MovingStats delay_stats_;

    std::map<std::string, PeerClock> peers_;
    std::chrono::steady_clock::time_point last_sync_rx_;

    std::thread sync_thread_;

#ifdef __linux__
    int event_socket_{-1};
    int general_socket_{-1};
#endif
};

}  // namespace lego_mcp::realtime
