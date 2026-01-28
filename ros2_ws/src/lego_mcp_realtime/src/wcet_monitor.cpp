/**
 * @file wcet_monitor.cpp
 * @brief WCET Monitor Implementation
 */

#include "lego_mcp_realtime/wcet_monitor.hpp"

#include <algorithm>
#include <cmath>
#include <map>
#include <mutex>
#include <numeric>
#include <sstream>
#include <vector>

namespace lego_mcp::realtime {

// WCETScope Implementation
WCETScope::WCETScope(
    WCETMonitor& monitor,
    const std::string& task_name,
    std::chrono::nanoseconds deadline
)
    : monitor_(monitor)
    , task_name_(task_name)
    , deadline_(deadline)
    , start_(std::chrono::steady_clock::now())
{}

WCETScope::~WCETScope() {
    auto end = std::chrono::steady_clock::now();
    auto execution_time = std::chrono::duration_cast<std::chrono::nanoseconds>(end - start_);

    WCETMeasurement measurement;
    measurement.task_name = task_name_;
    measurement.execution_time = execution_time;
    measurement.deadline = deadline_;
    measurement.start_time = start_;
    measurement.end_time = end;
    measurement.deadline_met = (deadline_ == std::chrono::nanoseconds::max()) ||
                               (execution_time <= deadline_);
    measurement.slack_ns = deadline_.count() - execution_time.count();

    monitor_.record(measurement);
}

std::chrono::nanoseconds WCETScope::elapsed() const noexcept {
    return std::chrono::duration_cast<std::chrono::nanoseconds>(
        std::chrono::steady_clock::now() - start_
    );
}

bool WCETScope::will_miss_deadline() const noexcept {
    if (deadline_ == std::chrono::nanoseconds::max()) {
        return false;
    }
    return elapsed() > deadline_;
}

// WCETMonitor Implementation
struct TaskData {
    std::string name;
    std::chrono::nanoseconds specified_wcet{0};
    std::chrono::nanoseconds period{0};
    std::vector<std::chrono::nanoseconds> samples;
    WCETStats stats;
    std::vector<uint64_t> histogram;
    std::chrono::nanoseconds histogram_min{0};
    std::chrono::nanoseconds histogram_max{std::chrono::milliseconds(10)};
};

class WCETMonitor::Impl {
public:
    explicit Impl(const WCETConfig& config) : config_(config) {}

    void register_task(
        const std::string& name,
        std::chrono::nanoseconds specified_wcet,
        std::chrono::nanoseconds period
    ) {
        std::lock_guard<std::mutex> lock(mutex_);

        TaskData data;
        data.name = name;
        data.specified_wcet = specified_wcet;
        data.period = period;
        data.stats.task_name = name;
        data.stats.specified_wcet = specified_wcet;

        if (config_.enable_histogram) {
            data.histogram.resize(config_.histogram_bins, 0);
            data.histogram_max = specified_wcet * 2;  // 2x WCET as max
        }

        tasks_[name] = std::move(data);
    }

    void record(const WCETMeasurement& measurement) {
        std::lock_guard<std::mutex> lock(mutex_);

        auto it = tasks_.find(measurement.task_name);
        if (it == tasks_.end()) {
            return;
        }

        TaskData& data = it->second;
        auto& stats = data.stats;

        // Add sample
        data.samples.push_back(measurement.execution_time);
        if (data.samples.size() > config_.sample_window) {
            data.samples.erase(data.samples.begin());
        }

        // Update stats
        stats.sample_count++;
        stats.min_et = std::min(stats.min_et, measurement.execution_time);
        stats.max_et = std::max(stats.max_et, measurement.execution_time);
        stats.measured_wcet = stats.max_et;

        // Running average
        stats.avg_et = std::chrono::nanoseconds(
            (stats.avg_et.count() * (stats.sample_count - 1) + measurement.execution_time.count()) /
            stats.sample_count
        );

        // Deadline miss
        if (!measurement.deadline_met) {
            stats.deadline_misses++;
        }

        // WCET overrun
        if (measurement.execution_time > data.specified_wcet) {
            stats.wcet_overruns++;

            // Notify overrun callback
            if (overrun_callback_) {
                overrun_callback_(measurement);
            }
        }

        // Update histogram
        if (config_.enable_histogram && !data.histogram.empty()) {
            auto bin_width = (data.histogram_max - data.histogram_min).count() /
                            static_cast<int64_t>(data.histogram.size());
            if (bin_width > 0) {
                auto bin_idx = (measurement.execution_time - data.histogram_min).count() / bin_width;
                bin_idx = std::max(int64_t(0), std::min(bin_idx,
                    static_cast<int64_t>(data.histogram.size() - 1)));
                data.histogram[static_cast<size_t>(bin_idx)]++;
            }
        }

        // Calculate utilization
        if (data.period.count() > 0) {
            stats.utilization = static_cast<double>(stats.avg_et.count()) /
                               static_cast<double>(data.period.count());
        }

        // Calculate stddev and p99 periodically
        if (stats.sample_count % 100 == 0) {
            update_advanced_stats(data);
        }
    }

    std::optional<WCETStats> get_stats(const std::string& name) const {
        std::lock_guard<std::mutex> lock(mutex_);

        auto it = tasks_.find(name);
        if (it == tasks_.end()) {
            return std::nullopt;
        }
        return it->second.stats;
    }

    std::vector<WCETStats> get_all_stats() const {
        std::lock_guard<std::mutex> lock(mutex_);

        std::vector<WCETStats> result;
        result.reserve(tasks_.size());
        for (const auto& [name, data] : tasks_) {
            result.push_back(data.stats);
        }
        return result;
    }

    std::vector<std::pair<std::chrono::nanoseconds, uint64_t>>
    get_histogram(const std::string& name) const {
        std::lock_guard<std::mutex> lock(mutex_);

        auto it = tasks_.find(name);
        if (it == tasks_.end() || !config_.enable_histogram) {
            return {};
        }

        const auto& data = it->second;
        std::vector<std::pair<std::chrono::nanoseconds, uint64_t>> result;
        result.reserve(data.histogram.size());

        auto bin_width = (data.histogram_max - data.histogram_min).count() /
                        static_cast<int64_t>(data.histogram.size());

        for (size_t i = 0; i < data.histogram.size(); ++i) {
            auto bin_start = data.histogram_min +
                std::chrono::nanoseconds(static_cast<int64_t>(i) * bin_width);
            result.emplace_back(bin_start, data.histogram[i]);
        }

        return result;
    }

    void on_overrun(OverrunCallback callback) {
        std::lock_guard<std::mutex> lock(mutex_);
        overrun_callback_ = std::move(callback);
    }

    bool all_tasks_safe() const {
        std::lock_guard<std::mutex> lock(mutex_);

        for (const auto& [name, data] : tasks_) {
            if (data.stats.measured_wcet > data.specified_wcet + config_.wcet_margin) {
                return false;
            }
        }
        return true;
    }

    double total_utilization() const {
        std::lock_guard<std::mutex> lock(mutex_);

        double total = 0.0;
        for (const auto& [name, data] : tasks_) {
            total += data.stats.utilization;
        }
        return total;
    }

    void reset(const std::string& name) {
        std::lock_guard<std::mutex> lock(mutex_);

        if (name.empty()) {
            for (auto& [n, data] : tasks_) {
                reset_task_data(data);
            }
        } else {
            auto it = tasks_.find(name);
            if (it != tasks_.end()) {
                reset_task_data(it->second);
            }
        }
    }

    std::string export_json() const {
        std::lock_guard<std::mutex> lock(mutex_);

        std::ostringstream ss;
        ss << "{\n  \"tasks\": [\n";

        bool first = true;
        for (const auto& [name, data] : tasks_) {
            if (!first) ss << ",\n";
            first = false;

            ss << "    {\n"
               << "      \"name\": \"" << name << "\",\n"
               << "      \"specified_wcet_ns\": " << data.specified_wcet.count() << ",\n"
               << "      \"measured_wcet_ns\": " << data.stats.measured_wcet.count() << ",\n"
               << "      \"min_et_ns\": " << data.stats.min_et.count() << ",\n"
               << "      \"max_et_ns\": " << data.stats.max_et.count() << ",\n"
               << "      \"avg_et_ns\": " << data.stats.avg_et.count() << ",\n"
               << "      \"sample_count\": " << data.stats.sample_count << ",\n"
               << "      \"deadline_misses\": " << data.stats.deadline_misses << ",\n"
               << "      \"wcet_overruns\": " << data.stats.wcet_overruns << ",\n"
               << "      \"utilization\": " << data.stats.utilization << "\n"
               << "    }";
        }

        ss << "\n  ],\n"
           << "  \"total_utilization\": " << total_utilization() << ",\n"
           << "  \"all_safe\": " << (all_tasks_safe() ? "true" : "false") << "\n"
           << "}\n";

        return ss.str();
    }

private:
    void update_advanced_stats(TaskData& data) {
        if (data.samples.empty()) return;

        // Calculate stddev
        double mean = static_cast<double>(data.stats.avg_et.count());
        double sum_sq = 0.0;
        for (const auto& s : data.samples) {
            double diff = static_cast<double>(s.count()) - mean;
            sum_sq += diff * diff;
        }
        double variance = sum_sq / static_cast<double>(data.samples.size());
        data.stats.stddev = std::chrono::nanoseconds(
            static_cast<int64_t>(std::sqrt(variance))
        );

        // Calculate p99
        std::vector<std::chrono::nanoseconds> sorted = data.samples;
        std::sort(sorted.begin(), sorted.end());
        size_t p99_idx = static_cast<size_t>(0.99 * static_cast<double>(sorted.size()));
        data.stats.p99_et = sorted[std::min(p99_idx, sorted.size() - 1)];
    }

    void reset_task_data(TaskData& data) {
        data.samples.clear();
        data.stats.sample_count = 0;
        data.stats.min_et = std::chrono::hours(1);
        data.stats.max_et = std::chrono::nanoseconds(0);
        data.stats.avg_et = std::chrono::nanoseconds(0);
        data.stats.measured_wcet = std::chrono::nanoseconds(0);
        data.stats.deadline_misses = 0;
        data.stats.wcet_overruns = 0;

        if (config_.enable_histogram) {
            std::fill(data.histogram.begin(), data.histogram.end(), 0);
        }
    }

    WCETConfig config_;
    mutable std::mutex mutex_;
    std::map<std::string, TaskData> tasks_;
    OverrunCallback overrun_callback_;
};

WCETMonitor::WCETMonitor(const WCETConfig& config)
    : impl_(std::make_unique<Impl>(config)) {}

WCETMonitor::~WCETMonitor() = default;

void WCETMonitor::register_task(
    const std::string& name,
    std::chrono::nanoseconds specified_wcet,
    std::chrono::nanoseconds period
) {
    impl_->register_task(name, specified_wcet, period);
}

void WCETMonitor::record(const WCETMeasurement& measurement) {
    impl_->record(measurement);
}

std::optional<WCETStats> WCETMonitor::get_stats(const std::string& name) const {
    return impl_->get_stats(name);
}

std::vector<WCETStats> WCETMonitor::get_all_stats() const {
    return impl_->get_all_stats();
}

std::vector<std::pair<std::chrono::nanoseconds, uint64_t>>
WCETMonitor::get_histogram(const std::string& name) const {
    return impl_->get_histogram(name);
}

void WCETMonitor::on_overrun(OverrunCallback callback) {
    impl_->on_overrun(std::move(callback));
}

bool WCETMonitor::all_tasks_safe() const {
    return impl_->all_tasks_safe();
}

double WCETMonitor::total_utilization() const {
    return impl_->total_utilization();
}

void WCETMonitor::reset(const std::string& name) {
    impl_->reset(name);
}

std::string WCETMonitor::export_json() const {
    return impl_->export_json();
}

// RMAAnalyzer Implementation
void RMAAnalyzer::add_task(const TaskParam& task) {
    tasks_.push_back(task);
    // Sort by period (shorter period = higher priority)
    std::sort(tasks_.begin(), tasks_.end(),
        [](const TaskParam& a, const TaskParam& b) {
            return a.period < b.period;
        });
}

bool RMAAnalyzer::is_schedulable() const {
    return total_utilization() <= utilization_bound();
}

double RMAAnalyzer::utilization_bound() const {
    if (tasks_.empty()) return 1.0;
    size_t n = tasks_.size();
    // Liu & Layland bound: n * (2^(1/n) - 1)
    return static_cast<double>(n) * (std::pow(2.0, 1.0 / static_cast<double>(n)) - 1.0);
}

double RMAAnalyzer::total_utilization() const {
    double total = 0.0;
    for (const auto& task : tasks_) {
        if (task.period.count() > 0) {
            total += static_cast<double>(task.wcet.count()) /
                    static_cast<double>(task.period.count());
        }
    }
    return total;
}

std::chrono::nanoseconds RMAAnalyzer::response_time(const std::string& task_name) const {
    // Find task index
    size_t task_idx = 0;
    for (size_t i = 0; i < tasks_.size(); ++i) {
        if (tasks_[i].name == task_name) {
            task_idx = i;
            break;
        }
    }

    // Response time analysis (fixed-point iteration)
    auto R = tasks_[task_idx].wcet;

    for (int iter = 0; iter < 100; ++iter) {
        auto R_new = tasks_[task_idx].wcet;

        // Add interference from higher-priority tasks
        for (size_t j = 0; j < task_idx; ++j) {
            auto ceil_val = (R.count() + tasks_[j].period.count() - 1) / tasks_[j].period.count();
            R_new += std::chrono::nanoseconds(ceil_val * tasks_[j].wcet.count());
        }

        if (R_new == R) break;
        R = R_new;
    }

    return R;
}

}  // namespace lego_mcp::realtime
