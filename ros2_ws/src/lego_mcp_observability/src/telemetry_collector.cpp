/**
 * Real-Time Telemetry Collector
 *
 * Collects and exports manufacturing telemetry with
 * minimal latency impact on control loops.
 *
 * Reference: OpenTelemetry C++ SDK, Prometheus C++ Client
 */

#include <rclcpp/rclcpp.hpp>
#include <rclcpp_lifecycle/lifecycle_node.hpp>

#include <atomic>
#include <chrono>
#include <cstdint>
#include <memory>
#include <mutex>
#include <queue>
#include <string>
#include <thread>
#include <unordered_map>
#include <vector>
#include <array>
#include <random>
#include <sstream>
#include <iomanip>
#include <fstream>

namespace lego_mcp {
namespace observability {

using namespace std::chrono_literals;

//==============================================================================
// Trace Context (W3C Compatible)
//==============================================================================

struct TraceId {
    std::array<uint8_t, 16> bytes{};

    static TraceId generate() {
        TraceId id;
        std::random_device rd;
        std::mt19937_64 gen(rd());
        std::uniform_int_distribution<uint64_t> dist;

        uint64_t high = dist(gen);
        uint64_t low = dist(gen);

        std::memcpy(id.bytes.data(), &high, 8);
        std::memcpy(id.bytes.data() + 8, &low, 8);
        return id;
    }

    std::string to_hex() const {
        std::stringstream ss;
        for (auto b : bytes) {
            ss << std::hex << std::setfill('0') << std::setw(2)
               << static_cast<int>(b);
        }
        return ss.str();
    }

    bool is_valid() const {
        for (auto b : bytes) {
            if (b != 0) return true;
        }
        return false;
    }
};

struct SpanId {
    std::array<uint8_t, 8> bytes{};

    static SpanId generate() {
        SpanId id;
        std::random_device rd;
        std::mt19937_64 gen(rd());
        std::uniform_int_distribution<uint64_t> dist;
        uint64_t val = dist(gen);
        std::memcpy(id.bytes.data(), &val, 8);
        return id;
    }

    std::string to_hex() const {
        std::stringstream ss;
        for (auto b : bytes) {
            ss << std::hex << std::setfill('0') << std::setw(2)
               << static_cast<int>(b);
        }
        return ss.str();
    }
};

struct SpanContext {
    TraceId trace_id;
    SpanId span_id;
    SpanId parent_span_id;
    uint8_t trace_flags{0x01};  // Sampled

    std::string to_traceparent() const {
        std::stringstream ss;
        ss << "00-" << trace_id.to_hex() << "-" << span_id.to_hex()
           << "-" << std::hex << std::setfill('0') << std::setw(2)
           << static_cast<int>(trace_flags);
        return ss.str();
    }
};

enum class SpanKind : uint8_t {
    INTERNAL = 0,
    SERVER = 1,
    CLIENT = 2,
    PRODUCER = 3,
    CONSUMER = 4
};

enum class SpanStatus : uint8_t {
    UNSET = 0,
    OK = 1,
    ERROR = 2
};

//==============================================================================
// Span (Lock-Free Recording)
//==============================================================================

struct SpanAttribute {
    std::string key;
    std::string value;  // Simplified: all values as strings
};

struct SpanEvent {
    std::string name;
    std::chrono::nanoseconds timestamp;
    std::vector<SpanAttribute> attributes;
};

class Span {
public:
    Span(const std::string& name, SpanContext context, SpanKind kind = SpanKind::INTERNAL)
        : name_(name)
        , context_(std::move(context))
        , kind_(kind)
        , start_time_(std::chrono::steady_clock::now())
        , status_(SpanStatus::UNSET)
        , ended_(false) {}

    void set_attribute(const std::string& key, const std::string& value) {
        std::lock_guard<std::mutex> lock(mutex_);
        attributes_.push_back({key, value});
    }

    template<typename T>
    void set_attribute(const std::string& key, T value) {
        set_attribute(key, std::to_string(value));
    }

    void add_event(const std::string& name) {
        std::lock_guard<std::mutex> lock(mutex_);
        events_.push_back({
            name,
            std::chrono::duration_cast<std::chrono::nanoseconds>(
                std::chrono::steady_clock::now().time_since_epoch()
            ),
            {}
        });
    }

    void set_status(SpanStatus status, const std::string& description = "") {
        status_ = status;
        status_description_ = description;
    }

    void end() {
        if (!ended_.exchange(true)) {
            end_time_ = std::chrono::steady_clock::now();
        }
    }

    [[nodiscard]] bool is_recording() const {
        return !ended_.load();
    }

    [[nodiscard]] std::chrono::nanoseconds duration() const {
        auto end = ended_.load() ? end_time_ : std::chrono::steady_clock::now();
        return std::chrono::duration_cast<std::chrono::nanoseconds>(end - start_time_);
    }

    [[nodiscard]] const std::string& name() const { return name_; }
    [[nodiscard]] const SpanContext& context() const { return context_; }
    [[nodiscard]] SpanKind kind() const { return kind_; }
    [[nodiscard]] SpanStatus status() const { return status_; }

    // Serialization for export
    std::string to_json() const {
        std::stringstream ss;
        ss << "{";
        ss << "\"name\":\"" << name_ << "\",";
        ss << "\"traceId\":\"" << context_.trace_id.to_hex() << "\",";
        ss << "\"spanId\":\"" << context_.span_id.to_hex() << "\",";
        ss << "\"parentSpanId\":\"" << context_.parent_span_id.to_hex() << "\",";
        ss << "\"kind\":" << static_cast<int>(kind_) << ",";
        ss << "\"status\":" << static_cast<int>(status_) << ",";
        ss << "\"durationNs\":" << duration().count();
        ss << "}";
        return ss.str();
    }

private:
    std::string name_;
    SpanContext context_;
    SpanKind kind_;
    std::chrono::steady_clock::time_point start_time_;
    std::chrono::steady_clock::time_point end_time_;
    SpanStatus status_;
    std::string status_description_;
    std::atomic<bool> ended_;

    mutable std::mutex mutex_;
    std::vector<SpanAttribute> attributes_;
    std::vector<SpanEvent> events_;
};

//==============================================================================
// Metric Types (Prometheus Compatible)
//==============================================================================

class Counter {
public:
    explicit Counter(const std::string& name, const std::string& help)
        : name_(name), help_(help), value_(0) {}

    void inc(double delta = 1.0) {
        if (delta < 0) return;  // Counters only go up
        value_.fetch_add(delta, std::memory_order_relaxed);
    }

    [[nodiscard]] double value() const {
        return value_.load(std::memory_order_relaxed);
    }

    [[nodiscard]] const std::string& name() const { return name_; }
    [[nodiscard]] const std::string& help() const { return help_; }

private:
    std::string name_;
    std::string help_;
    std::atomic<double> value_;
};

class Gauge {
public:
    explicit Gauge(const std::string& name, const std::string& help)
        : name_(name), help_(help), value_(0) {}

    void set(double value) {
        value_.store(value, std::memory_order_relaxed);
    }

    void inc(double delta = 1.0) {
        double old = value_.load(std::memory_order_relaxed);
        while (!value_.compare_exchange_weak(old, old + delta,
                                             std::memory_order_relaxed)) {}
    }

    void dec(double delta = 1.0) {
        inc(-delta);
    }

    [[nodiscard]] double value() const {
        return value_.load(std::memory_order_relaxed);
    }

    [[nodiscard]] const std::string& name() const { return name_; }
    [[nodiscard]] const std::string& help() const { return help_; }

private:
    std::string name_;
    std::string help_;
    std::atomic<double> value_;
};

class Histogram {
public:
    Histogram(const std::string& name, const std::string& help,
              std::vector<double> buckets = {0.001, 0.005, 0.01, 0.025, 0.05,
                                              0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0})
        : name_(name)
        , help_(help)
        , buckets_(std::move(buckets))
        , bucket_counts_(buckets_.size() + 1)
        , sum_(0)
        , count_(0) {
        for (auto& count : bucket_counts_) {
            count.store(0);
        }
    }

    void observe(double value) {
        std::lock_guard<std::mutex> lock(mutex_);
        sum_ += value;
        count_++;

        for (size_t i = 0; i < buckets_.size(); i++) {
            if (value <= buckets_[i]) {
                bucket_counts_[i]++;
            }
        }
        bucket_counts_.back()++;  // +Inf bucket
    }

    [[nodiscard]] double sum() const { return sum_; }
    [[nodiscard]] uint64_t count() const { return count_; }
    [[nodiscard]] const std::string& name() const { return name_; }
    [[nodiscard]] const std::string& help() const { return help_; }

private:
    std::string name_;
    std::string help_;
    std::vector<double> buckets_;
    std::vector<std::atomic<uint64_t>> bucket_counts_;
    double sum_;
    uint64_t count_;
    mutable std::mutex mutex_;
};

//==============================================================================
// Manufacturing Metrics Registry
//==============================================================================

class ManufacturingMetricsRegistry {
public:
    ManufacturingMetricsRegistry()
        // Production counters
        : parts_produced_total("lego_mcp_parts_produced_total",
                               "Total parts produced")
        , parts_rejected_total("lego_mcp_parts_rejected_total",
                               "Total parts rejected")
        , cycles_total("lego_mcp_equipment_cycles_total",
                       "Total equipment cycles")

        // Equipment gauges
        , equipment_state("lego_mcp_equipment_state",
                          "Equipment state (1=running, 0=stopped)")
        , temperature_celsius("lego_mcp_temperature_celsius",
                              "Temperature in Celsius")
        , vibration_mm_s("lego_mcp_vibration_mm_per_sec",
                         "Vibration velocity in mm/s")

        // OEE gauges
        , oee_availability("lego_mcp_oee_availability",
                           "OEE availability component")
        , oee_performance("lego_mcp_oee_performance",
                          "OEE performance component")
        , oee_quality("lego_mcp_oee_quality",
                      "OEE quality component")
        , oee_overall("lego_mcp_oee_overall",
                      "Overall Equipment Effectiveness")

        // Timing histograms
        , cycle_time_seconds("lego_mcp_cycle_time_seconds",
                             "Cycle time in seconds",
                             {0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0, 120.0})
        , control_loop_latency("lego_mcp_control_loop_latency_seconds",
                               "Control loop latency",
                               {0.0001, 0.0005, 0.001, 0.005, 0.01, 0.05, 0.1})
    {}

    // Production counters
    Counter parts_produced_total;
    Counter parts_rejected_total;
    Counter cycles_total;

    // Equipment gauges
    Gauge equipment_state;
    Gauge temperature_celsius;
    Gauge vibration_mm_s;

    // OEE gauges
    Gauge oee_availability;
    Gauge oee_performance;
    Gauge oee_quality;
    Gauge oee_overall;

    // Timing histograms
    Histogram cycle_time_seconds;
    Histogram control_loop_latency;

    // Generate Prometheus exposition format
    std::string exposition() const {
        std::stringstream ss;

        // Counters
        write_counter(ss, parts_produced_total);
        write_counter(ss, parts_rejected_total);
        write_counter(ss, cycles_total);

        // Gauges
        write_gauge(ss, equipment_state);
        write_gauge(ss, temperature_celsius);
        write_gauge(ss, vibration_mm_s);
        write_gauge(ss, oee_availability);
        write_gauge(ss, oee_performance);
        write_gauge(ss, oee_quality);
        write_gauge(ss, oee_overall);

        return ss.str();
    }

private:
    void write_counter(std::stringstream& ss, const Counter& c) const {
        ss << "# HELP " << c.name() << " " << c.help() << "\n";
        ss << "# TYPE " << c.name() << " counter\n";
        ss << c.name() << " " << c.value() << "\n\n";
    }

    void write_gauge(std::stringstream& ss, const Gauge& g) const {
        ss << "# HELP " << g.name() << " " << g.help() << "\n";
        ss << "# TYPE " << g.name() << " gauge\n";
        ss << g.name() << " " << g.value() << "\n\n";
    }
};

//==============================================================================
// Telemetry Collector Node
//==============================================================================

class TelemetryCollector : public rclcpp_lifecycle::LifecycleNode {
public:
    explicit TelemetryCollector(const rclcpp::NodeOptions& options = rclcpp::NodeOptions())
        : LifecycleNode("telemetry_collector", options)
        , metrics_(std::make_shared<ManufacturingMetricsRegistry>())
        , export_running_(false)
    {
        // Declare parameters
        declare_parameter("export_interval_ms", 1000);
        declare_parameter("metrics_file", "/tmp/lego_mcp_metrics.prom");
        declare_parameter("traces_file", "/tmp/lego_mcp_traces.json");
        declare_parameter("max_queued_spans", 10000);
        declare_parameter("sample_rate", 1.0);

        RCLCPP_INFO(get_logger(), "TelemetryCollector created");
    }

    ~TelemetryCollector() override {
        export_running_ = false;
        if (export_thread_.joinable()) {
            export_thread_.join();
        }
    }

    // Lifecycle callbacks
    rclcpp_lifecycle::node_interfaces::LifecycleNodeInterface::CallbackReturn
    on_configure(const rclcpp_lifecycle::State&) override {
        RCLCPP_INFO(get_logger(), "Configuring TelemetryCollector...");

        export_interval_ = std::chrono::milliseconds(
            get_parameter("export_interval_ms").as_int()
        );
        metrics_file_ = get_parameter("metrics_file").as_string();
        traces_file_ = get_parameter("traces_file").as_string();
        max_queued_spans_ = static_cast<size_t>(
            get_parameter("max_queued_spans").as_int()
        );
        sample_rate_ = get_parameter("sample_rate").as_double();

        return rclcpp_lifecycle::node_interfaces::LifecycleNodeInterface::CallbackReturn::SUCCESS;
    }

    rclcpp_lifecycle::node_interfaces::LifecycleNodeInterface::CallbackReturn
    on_activate(const rclcpp_lifecycle::State&) override {
        RCLCPP_INFO(get_logger(), "Activating TelemetryCollector...");

        // Start export thread
        export_running_ = true;
        export_thread_ = std::thread(&TelemetryCollector::export_loop, this);

        return rclcpp_lifecycle::node_interfaces::LifecycleNodeInterface::CallbackReturn::SUCCESS;
    }

    rclcpp_lifecycle::node_interfaces::LifecycleNodeInterface::CallbackReturn
    on_deactivate(const rclcpp_lifecycle::State&) override {
        RCLCPP_INFO(get_logger(), "Deactivating TelemetryCollector...");

        export_running_ = false;
        if (export_thread_.joinable()) {
            export_thread_.join();
        }

        return rclcpp_lifecycle::node_interfaces::LifecycleNodeInterface::CallbackReturn::SUCCESS;
    }

    rclcpp_lifecycle::node_interfaces::LifecycleNodeInterface::CallbackReturn
    on_cleanup(const rclcpp_lifecycle::State&) override {
        RCLCPP_INFO(get_logger(), "Cleaning up TelemetryCollector...");
        return rclcpp_lifecycle::node_interfaces::LifecycleNodeInterface::CallbackReturn::SUCCESS;
    }

    rclcpp_lifecycle::node_interfaces::LifecycleNodeInterface::CallbackReturn
    on_shutdown(const rclcpp_lifecycle::State&) override {
        RCLCPP_INFO(get_logger(), "Shutting down TelemetryCollector...");
        export_running_ = false;
        return rclcpp_lifecycle::node_interfaces::LifecycleNodeInterface::CallbackReturn::SUCCESS;
    }

    // Public API
    [[nodiscard]] std::shared_ptr<ManufacturingMetricsRegistry> metrics() const {
        return metrics_;
    }

    std::shared_ptr<Span> start_span(
        const std::string& name,
        SpanKind kind = SpanKind::INTERNAL,
        const SpanContext* parent = nullptr
    ) {
        // Sampling
        if (!should_sample()) {
            return nullptr;
        }

        SpanContext ctx;
        if (parent && parent->trace_id.is_valid()) {
            ctx.trace_id = parent->trace_id;
            ctx.parent_span_id = parent->span_id;
        } else {
            ctx.trace_id = TraceId::generate();
        }
        ctx.span_id = SpanId::generate();

        auto span = std::make_shared<Span>(name, ctx, kind);

        std::lock_guard<std::mutex> lock(active_spans_mutex_);
        active_spans_[ctx.span_id.to_hex()] = span;

        return span;
    }

    void end_span(std::shared_ptr<Span> span) {
        if (!span) return;

        span->end();

        // Move to export queue
        {
            std::lock_guard<std::mutex> lock(export_queue_mutex_);
            if (export_queue_.size() < max_queued_spans_) {
                export_queue_.push(span);
            }
        }

        // Remove from active
        {
            std::lock_guard<std::mutex> lock(active_spans_mutex_);
            active_spans_.erase(span->context().span_id.to_hex());
        }
    }

    // Record production event
    void record_production(bool is_good) {
        if (is_good) {
            metrics_->parts_produced_total.inc();
        } else {
            metrics_->parts_rejected_total.inc();
        }
    }

    // Record cycle completion
    void record_cycle(double duration_seconds) {
        metrics_->cycles_total.inc();
        metrics_->cycle_time_seconds.observe(duration_seconds);
    }

    // Update OEE metrics
    void update_oee(double availability, double performance, double quality) {
        metrics_->oee_availability.set(availability);
        metrics_->oee_performance.set(performance);
        metrics_->oee_quality.set(quality);
        metrics_->oee_overall.set(availability * performance * quality);
    }

    // Record control loop timing
    void record_control_loop_latency(double latency_seconds) {
        metrics_->control_loop_latency.observe(latency_seconds);
    }

private:
    bool should_sample() const {
        if (sample_rate_ >= 1.0) return true;
        if (sample_rate_ <= 0.0) return false;

        static thread_local std::mt19937 gen(std::random_device{}());
        static thread_local std::uniform_real_distribution<> dist(0.0, 1.0);
        return dist(gen) < sample_rate_;
    }

    void export_loop() {
        while (export_running_) {
            std::this_thread::sleep_for(export_interval_);
            export_metrics();
            export_traces();
        }
    }

    void export_metrics() {
        try {
            std::ofstream file(metrics_file_, std::ios::trunc);
            if (file.is_open()) {
                file << metrics_->exposition();
                file.close();
            }
        } catch (const std::exception& e) {
            RCLCPP_WARN(get_logger(), "Failed to export metrics: %s", e.what());
        }
    }

    void export_traces() {
        std::vector<std::shared_ptr<Span>> spans_to_export;

        {
            std::lock_guard<std::mutex> lock(export_queue_mutex_);
            while (!export_queue_.empty()) {
                spans_to_export.push_back(export_queue_.front());
                export_queue_.pop();
            }
        }

        if (spans_to_export.empty()) return;

        try {
            std::ofstream file(traces_file_, std::ios::app);
            if (file.is_open()) {
                for (const auto& span : spans_to_export) {
                    file << span->to_json() << "\n";
                }
                file.close();
            }
        } catch (const std::exception& e) {
            RCLCPP_WARN(get_logger(), "Failed to export traces: %s", e.what());
        }
    }

    // Configuration
    std::chrono::milliseconds export_interval_{1000};
    std::string metrics_file_;
    std::string traces_file_;
    size_t max_queued_spans_{10000};
    double sample_rate_{1.0};

    // Metrics registry
    std::shared_ptr<ManufacturingMetricsRegistry> metrics_;

    // Active spans
    std::mutex active_spans_mutex_;
    std::unordered_map<std::string, std::shared_ptr<Span>> active_spans_;

    // Export queue
    std::mutex export_queue_mutex_;
    std::queue<std::shared_ptr<Span>> export_queue_;

    // Export thread
    std::atomic<bool> export_running_;
    std::thread export_thread_;
};

}  // namespace observability
}  // namespace lego_mcp

// Register as ROS2 component
#include <rclcpp_components/register_node_macro.hpp>
RCLCPP_COMPONENTS_REGISTER_NODE(lego_mcp::observability::TelemetryCollector)
