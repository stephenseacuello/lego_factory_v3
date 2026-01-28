/**
 * Runtime Verification Monitor Node
 *
 * Implements real-time monitoring of temporal properties
 * for safety-critical manufacturing systems.
 *
 * Reference: IEEE 1012-2016, DO-178C
 */

#include <rclcpp/rclcpp.hpp>
#include <rclcpp_lifecycle/lifecycle_node.hpp>
#include <std_msgs/msg/string.hpp>
#include <std_srvs/srv/trigger.hpp>

#include <chrono>
#include <deque>
#include <functional>
#include <memory>
#include <mutex>
#include <optional>
#include <unordered_map>
#include <variant>
#include <vector>

using namespace std::chrono_literals;

namespace lego_mcp {

/**
 * Temporal Logic Formula Types (LTL subset)
 */
enum class LTLOperator {
    ALWAYS,       // G (globally/always)
    EVENTUALLY,   // F (finally/eventually)
    NEXT,         // X (next)
    UNTIL,        // U (until)
    RELEASE,      // R (release)
    NOT,          // ! (negation)
    AND,          // && (conjunction)
    OR,           // || (disjunction)
    IMPLIES,      // -> (implication)
    ATOM          // Atomic proposition
};

/**
 * Represents an event in the trace
 */
struct TraceEvent {
    std::string event_id;
    std::string event_type;
    std::chrono::steady_clock::time_point timestamp;
    std::unordered_map<std::string, std::string> properties;
    bool is_valid{true};
};

/**
 * Represents a safety property to monitor
 */
struct SafetyProperty {
    std::string id;
    std::string name;
    std::string description;
    LTLOperator op;
    std::vector<std::string> atoms;
    std::optional<std::chrono::milliseconds> time_bound;
    bool is_safety{true};  // Safety vs liveness
    int priority{1};       // 1=low, 5=critical
};

/**
 * Verdict for a property
 */
enum class Verdict {
    TRUE,       // Property satisfied
    FALSE,      // Property violated
    UNKNOWN,    // Cannot determine yet
    PENDING     // Waiting for more events
};

/**
 * Monitor state for a property
 */
struct MonitorState {
    std::string property_id;
    Verdict current_verdict{Verdict::UNKNOWN};
    std::vector<TraceEvent> relevant_events;
    std::chrono::steady_clock::time_point last_check;
    int violation_count{0};
    std::string last_violation_reason;
};

/**
 * Three-valued LTL semantics for runtime monitoring
 */
class LTL3Monitor {
public:
    /**
     * Evaluate a safety property against a trace prefix
     * Using 3-valued LTL semantics (true, false, inconclusive)
     */
    static Verdict evaluate(
        const SafetyProperty& property,
        const std::deque<TraceEvent>& trace,
        size_t position = 0
    ) {
        if (trace.empty()) {
            return Verdict::UNKNOWN;
        }

        switch (property.op) {
            case LTLOperator::ALWAYS:
                return evaluate_always(property, trace, position);
            case LTLOperator::EVENTUALLY:
                return evaluate_eventually(property, trace, position);
            case LTLOperator::NEXT:
                return evaluate_next(property, trace, position);
            case LTLOperator::UNTIL:
                return evaluate_until(property, trace, position);
            case LTLOperator::ATOM:
                return evaluate_atom(property, trace, position);
            default:
                return Verdict::UNKNOWN;
        }
    }

private:
    static Verdict evaluate_always(
        const SafetyProperty& property,
        const std::deque<TraceEvent>& trace,
        size_t position
    ) {
        // G(p): p must hold at all positions
        // False if p is false at any position
        // Inconclusive otherwise (since trace is finite)

        for (size_t i = position; i < trace.size(); ++i) {
            if (!check_atom(property.atoms[0], trace[i])) {
                return Verdict::FALSE;  // Safety violation!
            }
        }
        return Verdict::PENDING;  // True so far, but trace continues
    }

    static Verdict evaluate_eventually(
        const SafetyProperty& property,
        const std::deque<TraceEvent>& trace,
        size_t position
    ) {
        // F(p): p must hold at some position
        // True if p is true at any position
        // Inconclusive otherwise

        for (size_t i = position; i < trace.size(); ++i) {
            if (check_atom(property.atoms[0], trace[i])) {
                return Verdict::TRUE;
            }
        }
        return Verdict::PENDING;
    }

    static Verdict evaluate_next(
        const SafetyProperty& property,
        const std::deque<TraceEvent>& trace,
        size_t position
    ) {
        // X(p): p must hold at next position
        if (position + 1 >= trace.size()) {
            return Verdict::PENDING;
        }

        if (check_atom(property.atoms[0], trace[position + 1])) {
            return Verdict::TRUE;
        }
        return Verdict::FALSE;
    }

    static Verdict evaluate_until(
        const SafetyProperty& property,
        const std::deque<TraceEvent>& trace,
        size_t position
    ) {
        // p U q: p holds until q holds (and q eventually holds)
        if (property.atoms.size() < 2) {
            return Verdict::UNKNOWN;
        }

        for (size_t i = position; i < trace.size(); ++i) {
            // Check if q holds
            if (check_atom(property.atoms[1], trace[i])) {
                return Verdict::TRUE;
            }
            // Check if p still holds
            if (!check_atom(property.atoms[0], trace[i])) {
                return Verdict::FALSE;  // p failed before q
            }
        }
        return Verdict::PENDING;
    }

    static Verdict evaluate_atom(
        const SafetyProperty& property,
        const std::deque<TraceEvent>& trace,
        size_t position
    ) {
        if (position >= trace.size()) {
            return Verdict::UNKNOWN;
        }

        if (check_atom(property.atoms[0], trace[position])) {
            return Verdict::TRUE;
        }
        return Verdict::FALSE;
    }

    static bool check_atom(const std::string& atom, const TraceEvent& event) {
        // Atomic proposition matching
        // Format: "property=value" or just "event_type"

        size_t eq_pos = atom.find('=');
        if (eq_pos != std::string::npos) {
            std::string key = atom.substr(0, eq_pos);
            std::string value = atom.substr(eq_pos + 1);

            auto it = event.properties.find(key);
            if (it != event.properties.end()) {
                return it->second == value;
            }
            return false;
        }

        // Match event type
        return event.event_type == atom;
    }
};

/**
 * Runtime Monitor Node
 *
 * Monitors temporal properties in real-time
 */
class RuntimeMonitorNode : public rclcpp_lifecycle::LifecycleNode {
public:
    explicit RuntimeMonitorNode(const rclcpp::NodeOptions& options = rclcpp::NodeOptions())
        : rclcpp_lifecycle::LifecycleNode("runtime_monitor", options)
    {
        RCLCPP_INFO(get_logger(), "Runtime Monitor Node created");
    }

    // Lifecycle callbacks
    rclcpp_lifecycle::node_interfaces::LifecycleNodeInterface::CallbackReturn
    on_configure(const rclcpp_lifecycle::State&) override {
        RCLCPP_INFO(get_logger(), "Configuring Runtime Monitor");

        // Initialize default safety properties
        init_default_properties();

        // Create publishers and subscribers
        event_sub_ = create_subscription<std_msgs::msg::String>(
            "system_events", 100,
            std::bind(&RuntimeMonitorNode::event_callback, this, std::placeholders::_1)
        );

        violation_pub_ = create_publisher<std_msgs::msg::String>("safety_violations", 10);
        verdict_pub_ = create_publisher<std_msgs::msg::String>("property_verdicts", 10);

        // Create services
        check_property_srv_ = create_service<std_srvs::srv::Trigger>(
            "check_all_properties",
            std::bind(&RuntimeMonitorNode::check_all_properties, this,
                      std::placeholders::_1, std::placeholders::_2)
        );

        return rclcpp_lifecycle::node_interfaces::LifecycleNodeInterface::CallbackReturn::SUCCESS;
    }

    rclcpp_lifecycle::node_interfaces::LifecycleNodeInterface::CallbackReturn
    on_activate(const rclcpp_lifecycle::State&) override {
        RCLCPP_INFO(get_logger(), "Activating Runtime Monitor");

        violation_pub_->on_activate();
        verdict_pub_->on_activate();

        // Start periodic checking
        check_timer_ = create_wall_timer(
            100ms, std::bind(&RuntimeMonitorNode::periodic_check, this)
        );

        return rclcpp_lifecycle::node_interfaces::LifecycleNodeInterface::CallbackReturn::SUCCESS;
    }

    rclcpp_lifecycle::node_interfaces::LifecycleNodeInterface::CallbackReturn
    on_deactivate(const rclcpp_lifecycle::State&) override {
        RCLCPP_INFO(get_logger(), "Deactivating Runtime Monitor");

        check_timer_.reset();
        violation_pub_->on_deactivate();
        verdict_pub_->on_deactivate();

        return rclcpp_lifecycle::node_interfaces::LifecycleNodeInterface::CallbackReturn::SUCCESS;
    }

    rclcpp_lifecycle::node_interfaces::LifecycleNodeInterface::CallbackReturn
    on_cleanup(const rclcpp_lifecycle::State&) override {
        RCLCPP_INFO(get_logger(), "Cleaning up Runtime Monitor");

        trace_.clear();
        properties_.clear();
        monitor_states_.clear();

        return rclcpp_lifecycle::node_interfaces::LifecycleNodeInterface::CallbackReturn::SUCCESS;
    }

    rclcpp_lifecycle::node_interfaces::LifecycleNodeInterface::CallbackReturn
    on_shutdown(const rclcpp_lifecycle::State&) override {
        RCLCPP_INFO(get_logger(), "Shutting down Runtime Monitor");
        return rclcpp_lifecycle::node_interfaces::LifecycleNodeInterface::CallbackReturn::SUCCESS;
    }

private:
    void init_default_properties() {
        // Manufacturing safety properties

        // SP-1: Emergency stop must always be responsive
        properties_.push_back({
            "SP-001",
            "EmergencyStopResponsive",
            "Emergency stop command must be acknowledged within 100ms",
            LTLOperator::ALWAYS,
            {"emergency_stop_responsive=true"},
            100ms,
            true,  // Safety property
            5      // Critical priority
        });

        // SP-2: Robot collision avoidance
        properties_.push_back({
            "SP-002",
            "NoCollision",
            "Robots must never enter collision state",
            LTLOperator::ALWAYS,
            {"collision_detected=false"},
            std::nullopt,
            true,
            5
        });

        // SP-3: Temperature bounds
        properties_.push_back({
            "SP-003",
            "TemperatureInRange",
            "Temperature must always be within safe limits",
            LTLOperator::ALWAYS,
            {"temperature_safe=true"},
            std::nullopt,
            true,
            4
        });

        // SP-4: Material handling sequence
        properties_.push_back({
            "SP-004",
            "MaterialHandling",
            "Material must be inspected before processing",
            LTLOperator::ALWAYS,
            {"material_inspected=true"},
            std::nullopt,
            true,
            3
        });

        // SP-5: Liveness - Jobs eventually complete
        properties_.push_back({
            "SP-005",
            "JobCompletion",
            "Every started job must eventually complete or fail",
            LTLOperator::EVENTUALLY,
            {"job_terminal_state=true"},
            60000ms,  // 60 second bound
            false,    // Liveness property
            2
        });

        // Initialize monitor states
        for (const auto& prop : properties_) {
            MonitorState state;
            state.property_id = prop.id;
            state.last_check = std::chrono::steady_clock::now();
            monitor_states_[prop.id] = state;
        }
    }

    void event_callback(const std_msgs::msg::String::SharedPtr msg) {
        std::lock_guard<std::mutex> lock(trace_mutex_);

        // Parse event from JSON-like string
        TraceEvent event;
        event.event_id = generate_event_id();
        event.timestamp = std::chrono::steady_clock::now();
        parse_event(msg->data, event);

        // Add to trace (bounded buffer)
        trace_.push_back(event);
        if (trace_.size() > max_trace_length_) {
            trace_.pop_front();
        }

        // Immediate check for critical safety properties
        for (const auto& prop : properties_) {
            if (prop.priority >= 4) {  // Critical
                check_property(prop);
            }
        }
    }

    void periodic_check() {
        std::lock_guard<std::mutex> lock(trace_mutex_);

        for (const auto& prop : properties_) {
            check_property(prop);
        }
    }

    void check_property(const SafetyProperty& prop) {
        auto& state = monitor_states_[prop.id];

        Verdict verdict = LTL3Monitor::evaluate(prop, trace_);
        state.current_verdict = verdict;
        state.last_check = std::chrono::steady_clock::now();

        if (verdict == Verdict::FALSE) {
            state.violation_count++;
            handle_violation(prop, state);
        }

        // Publish verdict
        auto verdict_msg = std_msgs::msg::String();
        verdict_msg.data = format_verdict(prop, verdict);
        verdict_pub_->publish(verdict_msg);
    }

    void handle_violation(const SafetyProperty& prop, MonitorState& state) {
        RCLCPP_ERROR(get_logger(),
            "SAFETY VIOLATION [%s]: %s - Priority: %d",
            prop.id.c_str(), prop.description.c_str(), prop.priority);

        auto msg = std_msgs::msg::String();
        msg.data = format_violation(prop, state);
        violation_pub_->publish(msg);

        // Critical violations trigger immediate response
        if (prop.priority == 5) {
            RCLCPP_FATAL(get_logger(),
                "CRITICAL SAFETY VIOLATION - Immediate action required!");
            // In production: trigger emergency protocols
        }
    }

    void check_all_properties(
        const std_srvs::srv::Trigger::Request::SharedPtr,
        std_srvs::srv::Trigger::Response::SharedPtr response
    ) {
        std::lock_guard<std::mutex> lock(trace_mutex_);

        int violations = 0;
        std::string details;

        for (const auto& prop : properties_) {
            Verdict verdict = LTL3Monitor::evaluate(prop, trace_);
            if (verdict == Verdict::FALSE) {
                violations++;
                details += prop.id + ": VIOLATED\n";
            } else if (verdict == Verdict::TRUE) {
                details += prop.id + ": SATISFIED\n";
            } else {
                details += prop.id + ": PENDING\n";
            }
        }

        response->success = (violations == 0);
        response->message = "Checked " + std::to_string(properties_.size()) +
                           " properties, " + std::to_string(violations) + " violations\n" + details;
    }

    void parse_event(const std::string& data, TraceEvent& event) {
        // Simple key=value parsing
        size_t pos = 0;
        while (pos < data.length()) {
            size_t eq = data.find('=', pos);
            if (eq == std::string::npos) break;

            size_t end = data.find(';', eq);
            if (end == std::string::npos) end = data.length();

            std::string key = data.substr(pos, eq - pos);
            std::string value = data.substr(eq + 1, end - eq - 1);

            if (key == "type") {
                event.event_type = value;
            } else {
                event.properties[key] = value;
            }

            pos = end + 1;
        }
    }

    std::string generate_event_id() {
        static int counter = 0;
        return "EVT-" + std::to_string(++counter);
    }

    std::string format_verdict(const SafetyProperty& prop, Verdict verdict) {
        std::string v_str;
        switch (verdict) {
            case Verdict::TRUE: v_str = "TRUE"; break;
            case Verdict::FALSE: v_str = "FALSE"; break;
            case Verdict::PENDING: v_str = "PENDING"; break;
            default: v_str = "UNKNOWN";
        }
        return prop.id + ":" + v_str + ":" + prop.name;
    }

    std::string format_violation(const SafetyProperty& prop, const MonitorState& state) {
        return "VIOLATION|" + prop.id + "|" + prop.name + "|" +
               "count=" + std::to_string(state.violation_count) + "|" +
               "priority=" + std::to_string(prop.priority);
    }

    // Members
    std::deque<TraceEvent> trace_;
    std::mutex trace_mutex_;
    size_t max_trace_length_{10000};

    std::vector<SafetyProperty> properties_;
    std::unordered_map<std::string, MonitorState> monitor_states_;

    rclcpp::Subscription<std_msgs::msg::String>::SharedPtr event_sub_;
    rclcpp_lifecycle::LifecyclePublisher<std_msgs::msg::String>::SharedPtr violation_pub_;
    rclcpp_lifecycle::LifecyclePublisher<std_msgs::msg::String>::SharedPtr verdict_pub_;
    rclcpp::Service<std_srvs::srv::Trigger>::SharedPtr check_property_srv_;
    rclcpp::TimerBase::SharedPtr check_timer_;
};

}  // namespace lego_mcp

int main(int argc, char** argv) {
    rclcpp::init(argc, argv);

    auto node = std::make_shared<lego_mcp::RuntimeMonitorNode>();

    rclcpp::executors::SingleThreadedExecutor executor;
    executor.add_node(node->get_node_base_interface());
    executor.spin();

    rclcpp::shutdown();
    return 0;
}
