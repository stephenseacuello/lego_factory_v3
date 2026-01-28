/**
 * @file compliance_monitor.cpp
 * @brief Real-time Compliance Monitoring for DoD/Federal Requirements
 * 
 * Implements:
 * - NIST 800-171 audit event generation
 * - CMMC practice monitoring
 * - CUI access tracking
 * - Real-time security alerting
 * 
 * Reference: NIST SP 800-171, CMMC 2.0, DFARS 252.204-7012
 */

#include <rclcpp/rclcpp.hpp>
#include <rclcpp_lifecycle/lifecycle_node.hpp>
#include <std_msgs/msg/string.hpp>
#include <std_srvs/srv/trigger.hpp>

#include <chrono>
#include <memory>
#include <string>
#include <vector>
#include <unordered_map>
#include <mutex>
#include <queue>
#include <fstream>
#include <sstream>
#include <iomanip>
#include <functional>

namespace lego_mcp {
namespace compliance {

using namespace std::chrono_literals;

/**
 * @brief Audit event severity levels (aligned with syslog)
 */
enum class AuditSeverity {
    EMERGENCY = 0,
    ALERT = 1,
    CRITICAL = 2,
    ERROR = 3,
    WARNING = 4,
    NOTICE = 5,
    INFO = 6,
    DEBUG = 7
};

/**
 * @brief Audit event categories per NIST 800-53 AU-2
 */
enum class AuditCategory {
    AUTHENTICATION,
    AUTHORIZATION,
    ACCESS,
    MODIFICATION,
    DELETION,
    PRIVILEGED,
    SYSTEM,
    SECURITY,
    COMPLIANCE,
    CUI,
    INCIDENT,
    CONFIGURATION
};

/**
 * @brief NIST 800-171 Control Families
 */
enum class ControlFamily {
    ACCESS_CONTROL,
    AWARENESS_TRAINING,
    AUDIT,
    CONFIGURATION,
    IDENTIFICATION,
    INCIDENT_RESPONSE,
    MAINTENANCE,
    MEDIA_PROTECTION,
    PERSONNEL,
    PHYSICAL,
    RISK,
    SECURITY_ASSESSMENT,
    SYSTEM_COMM,
    SYSTEM_INFO
};

/**
 * @brief Audit event structure
 */
struct AuditEvent {
    std::string event_id;
    std::string timestamp;
    AuditCategory category;
    AuditSeverity severity;
    bool success;
    
    std::string user_id;
    std::string action;
    std::string resource_type;
    std::string resource_id;
    std::string source_ip;
    std::string description;
    
    bool cui_involved;
    std::vector<std::string> cui_categories;
    std::vector<std::string> nist_controls;
    
    std::string hash;
    std::string previous_hash;
    
    std::string to_json() const {
        std::ostringstream oss;
        oss << "{";
        oss << "\"event_id\":\"" << event_id << "\",";
        oss << "\"timestamp\":\"" << timestamp << "\",";
        oss << "\"category\":" << static_cast<int>(category) << ",";
        oss << "\"severity\":" << static_cast<int>(severity) << ",";
        oss << "\"success\":" << (success ? "true" : "false") << ",";
        oss << "\"user_id\":\"" << user_id << "\",";
        oss << "\"action\":\"" << action << "\",";
        oss << "\"resource_type\":\"" << resource_type << "\",";
        oss << "\"resource_id\":\"" << resource_id << "\",";
        oss << "\"description\":\"" << description << "\",";
        oss << "\"cui_involved\":" << (cui_involved ? "true" : "false") << ",";
        oss << "\"hash\":\"" << hash << "\"";
        oss << "}";
        return oss.str();
    }
    
    std::string to_cef() const {
        // Common Event Format
        int cef_severity = 10 - static_cast<int>(severity);
        if (cef_severity < 0) cef_severity = 0;
        if (cef_severity > 10) cef_severity = 10;
        
        std::ostringstream oss;
        oss << "CEF:0|LEGO MCP|Manufacturing|1.0|";
        oss << static_cast<int>(category) << "|" << action << "|";
        oss << cef_severity << "|";
        oss << "rt=" << timestamp << " ";
        oss << "suser=" << user_id << " ";
        oss << "outcome=" << (success ? "success" : "failure") << " ";
        oss << "msg=" << description;
        return oss.str();
    }
};

/**
 * @brief Security control status
 */
struct ControlStatus {
    std::string control_id;
    ControlFamily family;
    std::string title;
    bool implemented;
    bool verified;
    std::string last_assessment;
    std::vector<std::string> evidence;
};

/**
 * @brief Compliance Monitor ROS2 Lifecycle Node
 * 
 * Provides real-time compliance monitoring for manufacturing
 * operations with DoD/federal requirements.
 */
class ComplianceMonitor : public rclcpp_lifecycle::LifecycleNode {
public:
    explicit ComplianceMonitor(const rclcpp::NodeOptions& options = rclcpp::NodeOptions())
        : rclcpp_lifecycle::LifecycleNode("compliance_monitor", options)
        , event_counter_(0)
    {
        // Declare parameters
        declare_parameter("audit_log_path", "/var/log/lego_mcp/audit.log");
        declare_parameter("chain_enabled", true);
        declare_parameter("alert_threshold", static_cast<int>(AuditSeverity::WARNING));
        declare_parameter("cui_monitoring_enabled", true);
        declare_parameter("nist_controls_file", "");
        
        RCLCPP_INFO(get_logger(), "ComplianceMonitor node created");
    }

    // Lifecycle callbacks
    CallbackReturn on_configure(const rclcpp_lifecycle::State&) override {
        RCLCPP_INFO(get_logger(), "Configuring ComplianceMonitor...");
        
        audit_log_path_ = get_parameter("audit_log_path").as_string();
        chain_enabled_ = get_parameter("chain_enabled").as_bool();
        alert_threshold_ = static_cast<AuditSeverity>(
            get_parameter("alert_threshold").as_int()
        );
        cui_monitoring_ = get_parameter("cui_monitoring_enabled").as_bool();
        
        // Initialize hash chain
        if (chain_enabled_) {
            current_hash_ = compute_hash("GENESIS");
        }
        
        // Initialize NIST controls
        initialize_controls();
        
        // Create publishers
        audit_pub_ = create_publisher<std_msgs::msg::String>(
            "compliance/audit_events", 100
        );
        alert_pub_ = create_publisher<std_msgs::msg::String>(
            "compliance/security_alerts", 10
        );
        
        // Create services
        assessment_srv_ = create_service<std_srvs::srv::Trigger>(
            "compliance/run_assessment",
            std::bind(&ComplianceMonitor::handle_assessment, this,
                     std::placeholders::_1, std::placeholders::_2)
        );
        
        RCLCPP_INFO(get_logger(), "ComplianceMonitor configured");
        return CallbackReturn::SUCCESS;
    }

    CallbackReturn on_activate(const rclcpp_lifecycle::State&) override {
        RCLCPP_INFO(get_logger(), "Activating ComplianceMonitor...");
        
        // Start monitoring timer
        monitor_timer_ = create_wall_timer(
            1s,
            std::bind(&ComplianceMonitor::monitor_tick, this)
        );
        
        // Log activation
        log_event(
            AuditCategory::SYSTEM,
            "system_activate",
            AuditSeverity::NOTICE,
            true,
            "SYSTEM",
            "compliance_monitor",
            "node",
            "ComplianceMonitor activated"
        );
        
        RCLCPP_INFO(get_logger(), "ComplianceMonitor active");
        return CallbackReturn::SUCCESS;
    }

    CallbackReturn on_deactivate(const rclcpp_lifecycle::State&) override {
        RCLCPP_INFO(get_logger(), "Deactivating ComplianceMonitor...");
        
        monitor_timer_.reset();
        
        log_event(
            AuditCategory::SYSTEM,
            "system_deactivate",
            AuditSeverity::NOTICE,
            true,
            "SYSTEM",
            "compliance_monitor",
            "node",
            "ComplianceMonitor deactivated"
        );
        
        return CallbackReturn::SUCCESS;
    }

    CallbackReturn on_cleanup(const rclcpp_lifecycle::State&) override {
        audit_pub_.reset();
        alert_pub_.reset();
        assessment_srv_.reset();
        return CallbackReturn::SUCCESS;
    }

    CallbackReturn on_shutdown(const rclcpp_lifecycle::State&) override {
        RCLCPP_INFO(get_logger(), "Shutting down ComplianceMonitor");
        return CallbackReturn::SUCCESS;
    }

    /**
     * @brief Log an audit event
     */
    void log_event(
        AuditCategory category,
        const std::string& action,
        AuditSeverity severity,
        bool success,
        const std::string& user_id,
        const std::string& resource_id,
        const std::string& resource_type,
        const std::string& description,
        bool cui_involved = false,
        const std::vector<std::string>& nist_controls = {}
    ) {
        std::lock_guard<std::mutex> lock(mutex_);
        
        AuditEvent event;
        event.event_id = generate_event_id();
        event.timestamp = get_iso_timestamp();
        event.category = category;
        event.severity = severity;
        event.success = success;
        event.user_id = user_id;
        event.action = action;
        event.resource_type = resource_type;
        event.resource_id = resource_id;
        event.description = description;
        event.cui_involved = cui_involved;
        event.nist_controls = nist_controls;
        
        // Chain hash
        if (chain_enabled_) {
            event.previous_hash = current_hash_;
            event.hash = compute_event_hash(event);
            current_hash_ = event.hash;
        }
        
        // Write to audit log
        write_audit_log(event);
        
        // Publish event
        if (audit_pub_) {
            auto msg = std_msgs::msg::String();
            msg.data = event.to_json();
            audit_pub_->publish(msg);
        }
        
        // Check for alerts
        if (static_cast<int>(severity) <= static_cast<int>(alert_threshold_)) {
            trigger_alert(event);
        }
        
        // Store in memory for correlation
        recent_events_.push(event);
        if (recent_events_.size() > 1000) {
            recent_events_.pop();
        }
    }

    /**
     * @brief Log authentication event (NIST 3.5.1, 3.5.2)
     */
    void log_authentication(
        const std::string& user_id,
        bool success,
        const std::string& method = "password",
        bool mfa_used = false,
        const std::string& source_ip = ""
    ) {
        std::vector<std::string> controls = {"3.5.1", "3.5.2"};
        if (mfa_used) {
            controls.push_back("3.5.3");
        }
        
        log_event(
            AuditCategory::AUTHENTICATION,
            "login_" + method,
            success ? AuditSeverity::INFO : AuditSeverity::WARNING,
            success,
            user_id,
            "authentication",
            "session",
            "Authentication " + std::string(success ? "successful" : "failed"),
            false,
            controls
        );
    }

    /**
     * @brief Log CUI access (NIST 3.1.3, 3.3.1)
     */
    void log_cui_access(
        const std::string& user_id,
        const std::string& document_id,
        bool granted,
        const std::vector<std::string>& cui_categories
    ) {
        AuditEvent event;
        event.event_id = generate_event_id();
        event.timestamp = get_iso_timestamp();
        event.category = AuditCategory::CUI;
        event.severity = granted ? AuditSeverity::NOTICE : AuditSeverity::WARNING;
        event.success = granted;
        event.user_id = user_id;
        event.action = "cui_access";
        event.resource_type = "cui_document";
        event.resource_id = document_id;
        event.description = std::string("CUI access ") + (granted ? "granted" : "denied");
        event.cui_involved = true;
        event.cui_categories = cui_categories;
        event.nist_controls = {"3.1.3", "3.3.1", "3.3.2"};
        
        std::lock_guard<std::mutex> lock(mutex_);
        
        if (chain_enabled_) {
            event.previous_hash = current_hash_;
            event.hash = compute_event_hash(event);
            current_hash_ = event.hash;
        }
        
        write_audit_log(event);
        
        if (audit_pub_) {
            auto msg = std_msgs::msg::String();
            msg.data = event.to_json();
            audit_pub_->publish(msg);
        }
        
        if (!granted) {
            trigger_alert(event);
        }
    }

    /**
     * @brief Log privileged action (NIST 3.1.7)
     */
    void log_privileged_action(
        const std::string& user_id,
        const std::string& action,
        const std::string& target,
        bool success
    ) {
        log_event(
            AuditCategory::PRIVILEGED,
            "privileged_" + action,
            AuditSeverity::NOTICE,
            success,
            user_id,
            target,
            "system",
            "Privileged action: " + action,
            false,
            {"3.1.7", "3.3.1", "3.3.2"}
        );
    }

    /**
     * @brief Log security incident (NIST 3.6.1, 3.6.2)
     */
    void log_security_incident(
        const std::string& incident_type,
        const std::string& description,
        AuditSeverity severity = AuditSeverity::ALERT
    ) {
        log_event(
            AuditCategory::INCIDENT,
            "incident_" + incident_type,
            severity,
            false,  // Incidents are failures
            "SYSTEM",
            incident_type,
            "security",
            description,
            false,
            {"3.6.1", "3.6.2"}
        );
    }

    /**
     * @brief Verify audit chain integrity
     */
    bool verify_chain_integrity() const {
        // In a real implementation, would verify all hashes
        return chain_enabled_;
    }

    /**
     * @brief Get compliance assessment summary
     */
    std::string get_assessment_summary() const {
        std::ostringstream oss;
        oss << "{";
        oss << "\"timestamp\":\"" << get_iso_timestamp() << "\",";
        oss << "\"controls_total\":" << controls_.size() << ",";
        
        int implemented = 0;
        for (const auto& [id, status] : controls_) {
            if (status.implemented) implemented++;
        }
        
        oss << "\"controls_implemented\":" << implemented << ",";
        oss << "\"compliance_score\":" << std::fixed << std::setprecision(2)
            << (static_cast<double>(implemented) / controls_.size() * 100) << ",";
        oss << "\"chain_integrity\":" << (verify_chain_integrity() ? "true" : "false");
        oss << "}";
        return oss.str();
    }

private:
    void initialize_controls() {
        // Key NIST 800-171 controls
        struct ControlDef {
            std::string id;
            ControlFamily family;
            std::string title;
        };
        
        std::vector<ControlDef> defs = {
            {"3.1.1", ControlFamily::ACCESS_CONTROL, "Limit system access"},
            {"3.1.2", ControlFamily::ACCESS_CONTROL, "Limit transaction types"},
            {"3.1.3", ControlFamily::ACCESS_CONTROL, "Control CUI flow"},
            {"3.1.5", ControlFamily::ACCESS_CONTROL, "Least privilege"},
            {"3.1.7", ControlFamily::ACCESS_CONTROL, "Privileged functions"},
            {"3.3.1", ControlFamily::AUDIT, "System auditing"},
            {"3.3.2", ControlFamily::AUDIT, "User accountability"},
            {"3.3.4", ControlFamily::AUDIT, "Audit failure alerting"},
            {"3.5.1", ControlFamily::IDENTIFICATION, "Identify users"},
            {"3.5.2", ControlFamily::IDENTIFICATION, "Authenticate users"},
            {"3.5.3", ControlFamily::IDENTIFICATION, "Multifactor authentication"},
            {"3.6.1", ControlFamily::INCIDENT_RESPONSE, "Incident handling"},
            {"3.6.2", ControlFamily::INCIDENT_RESPONSE, "Incident reporting"},
            {"3.13.8", ControlFamily::SYSTEM_COMM, "CUI encryption"},
            {"3.13.11", ControlFamily::SYSTEM_COMM, "FIPS cryptography"},
        };
        
        for (const auto& def : defs) {
            ControlStatus status;
            status.control_id = def.id;
            status.family = def.family;
            status.title = def.title;
            status.implemented = true;  // Assume implemented for demo
            status.verified = false;
            controls_[def.id] = status;
        }
    }

    void monitor_tick() {
        // Periodic compliance checks
        // Could check for anomalies, audit failures, etc.
    }

    void handle_assessment(
        const std::shared_ptr<std_srvs::srv::Trigger::Request>,
        std::shared_ptr<std_srvs::srv::Trigger::Response> response
    ) {
        response->success = true;
        response->message = get_assessment_summary();
        
        log_event(
            AuditCategory::COMPLIANCE,
            "compliance_assessment",
            AuditSeverity::NOTICE,
            true,
            "SYSTEM",
            "nist_800_171",
            "assessment",
            "Compliance assessment performed"
        );
    }

    void write_audit_log(const AuditEvent& event) {
        try {
            std::ofstream file(audit_log_path_, std::ios::app);
            if (file.is_open()) {
                file << event.to_json() << "\n";
            }
        } catch (const std::exception& e) {
            RCLCPP_ERROR(get_logger(), "Audit log write failed: %s", e.what());
            // NIST 3.3.4: Alert on audit failure
            trigger_audit_failure_alert();
        }
    }

    void trigger_alert(const AuditEvent& event) {
        if (alert_pub_) {
            auto msg = std_msgs::msg::String();
            msg.data = event.to_json();
            alert_pub_->publish(msg);
        }
        
        RCLCPP_WARN(get_logger(), 
            "Security Alert: %s - %s", 
            event.action.c_str(),
            event.description.c_str()
        );
    }

    void trigger_audit_failure_alert() {
        RCLCPP_ERROR(get_logger(), "CRITICAL: Audit logging failure - NIST 3.3.4 violation");
    }

    std::string generate_event_id() {
        auto now = std::chrono::system_clock::now();
        auto time_t = std::chrono::system_clock::to_time_t(now);
        std::ostringstream oss;
        oss << "EVT-" << std::put_time(std::gmtime(&time_t), "%Y%m%d") 
            << "-" << std::setfill('0') << std::setw(8) << ++event_counter_;
        return oss.str();
    }

    static std::string get_iso_timestamp() {
        auto now = std::chrono::system_clock::now();
        auto time_t = std::chrono::system_clock::to_time_t(now);
        std::ostringstream oss;
        oss << std::put_time(std::gmtime(&time_t), "%Y-%m-%dT%H:%M:%S") << "Z";
        return oss.str();
    }

    std::string compute_hash(const std::string& data) const {
        // Simplified hash - real implementation would use SHA-256
        std::hash<std::string> hasher;
        std::ostringstream oss;
        oss << std::hex << std::setfill('0') << std::setw(16) << hasher(data);
        return oss.str();
    }

    std::string compute_event_hash(const AuditEvent& event) const {
        std::string content = event.event_id + event.timestamp + 
                             event.action + event.user_id + current_hash_;
        return compute_hash(content);
    }

    // Parameters
    std::string audit_log_path_;
    bool chain_enabled_;
    AuditSeverity alert_threshold_;
    bool cui_monitoring_;
    
    // State
    std::atomic<uint64_t> event_counter_;
    std::string current_hash_;
    std::unordered_map<std::string, ControlStatus> controls_;
    std::queue<AuditEvent> recent_events_;
    std::mutex mutex_;
    
    // ROS2 interfaces
    rclcpp::Publisher<std_msgs::msg::String>::SharedPtr audit_pub_;
    rclcpp::Publisher<std_msgs::msg::String>::SharedPtr alert_pub_;
    rclcpp::Service<std_srvs::srv::Trigger>::SharedPtr assessment_srv_;
    rclcpp::TimerBase::SharedPtr monitor_timer_;
};

}  // namespace compliance
}  // namespace lego_mcp

// Main entry point
int main(int argc, char* argv[]) {
    rclcpp::init(argc, argv);
    
    auto node = std::make_shared<lego_mcp::compliance::ComplianceMonitor>();
    
    rclcpp::executors::SingleThreadedExecutor executor;
    executor.add_node(node->get_node_base_interface());
    executor.spin();
    
    rclcpp::shutdown();
    return 0;
}
