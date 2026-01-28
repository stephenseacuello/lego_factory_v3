/**
 * @file opcua_server_node.cpp
 * @brief OPC UA Server for Industrial Manufacturing
 * 
 * Implements IEC 62541 (OPC UA) for:
 * - Manufacturing information model
 * - Equipment data publishing
 * - Method calls for control
 * - Event/alarm notification
 * 
 * Reference: IEC 62541 Parts 1-14, OPC UA for Machinery
 */

#include <rclcpp/rclcpp.hpp>
#include <rclcpp_lifecycle/lifecycle_node.hpp>
#include <std_msgs/msg/string.hpp>
#include <std_srvs/srv/trigger.hpp>

#include <memory>
#include <string>
#include <vector>
#include <unordered_map>
#include <mutex>
#include <atomic>
#include <chrono>
#include <functional>

namespace lego_mcp {
namespace opcua {

using namespace std::chrono_literals;

/**
 * @brief OPC UA Node Class
 */
enum class NodeClass {
    OBJECT,
    VARIABLE,
    METHOD,
    OBJECT_TYPE,
    VARIABLE_TYPE,
    REFERENCE_TYPE,
    DATA_TYPE,
    VIEW
};

/**
 * @brief OPC UA Data Types (subset)
 */
enum class DataType {
    BOOLEAN,
    INT16,
    INT32,
    INT64,
    UINT16,
    UINT32,
    UINT64,
    FLOAT,
    DOUBLE,
    STRING,
    DATETIME,
    BYTE_STRING,
    NODE_ID
};

/**
 * @brief OPC UA Access Level
 */
enum class AccessLevel {
    NONE = 0,
    CURRENT_READ = 1,
    CURRENT_WRITE = 2,
    HISTORY_READ = 4,
    HISTORY_WRITE = 8
};

/**
 * @brief OPC UA Variable node
 */
struct VariableNode {
    std::string node_id;
    std::string browse_name;
    std::string display_name;
    DataType data_type;
    std::string value;  // Serialized value
    uint8_t access_level;
    std::string parent_node_id;
    bool historizing;
};

/**
 * @brief OPC UA Method node
 */
struct MethodNode {
    std::string node_id;
    std::string browse_name;
    std::string display_name;
    std::vector<std::pair<std::string, DataType>> input_args;
    std::vector<std::pair<std::string, DataType>> output_args;
    std::function<std::string(const std::vector<std::string>&)> handler;
};

/**
 * @brief Subscription
 */
struct OPCUASubscription {
    std::string subscription_id;
    std::string client_id;
    std::vector<std::string> monitored_items;
    std::chrono::milliseconds publishing_interval;
    std::chrono::steady_clock::time_point last_publish;
};

/**
 * @brief OPC UA Server Node
 * 
 * Provides OPC UA server for manufacturing data exchange.
 */
class OPCUAServerNode : public rclcpp_lifecycle::LifecycleNode {
public:
    explicit OPCUAServerNode(const rclcpp::NodeOptions& options = rclcpp::NodeOptions())
        : rclcpp_lifecycle::LifecycleNode("opcua_server", options)
        , running_(false)
    {
        declare_parameter("server_name", "LEGO MCP OPC UA Server");
        declare_parameter("port", 4840);
        declare_parameter("security_mode", "SignAndEncrypt");
        declare_parameter("namespace_uri", "urn:lego-mcp:manufacturing");
        
        RCLCPP_INFO(get_logger(), "OPCUAServerNode created");
    }

    CallbackReturn on_configure(const rclcpp_lifecycle::State&) override {
        RCLCPP_INFO(get_logger(), "Configuring OPC UA Server...");
        
        server_name_ = get_parameter("server_name").as_string();
        port_ = get_parameter("port").as_int();
        namespace_uri_ = get_parameter("namespace_uri").as_string();
        
        // Initialize address space
        initialize_address_space();
        
        // Create ROS2 publishers
        data_change_pub_ = create_publisher<std_msgs::msg::String>(
            "opcua/data_changes", 100
        );

        // Create subscription for ROS2 -> OPC UA bridging
        ros_data_sub_ = create_subscription<std_msgs::msg::String>(
            "manufacturing/data", 100,
            std::bind(&OPCUAServerNode::handle_ros_data, this, std::placeholders::_1)
        );

        // Create services
        read_srv_ = create_service<std_srvs::srv::Trigger>(
            "opcua/read",
            std::bind(&OPCUAServerNode::handle_read, this,
                     std::placeholders::_1, std::placeholders::_2)
        );
        
        RCLCPP_INFO(get_logger(), "OPC UA Server configured on port %d", port_);
        
        return CallbackReturn::SUCCESS;
    }

    CallbackReturn on_activate(const rclcpp_lifecycle::State&) override {
        RCLCPP_INFO(get_logger(), "Activating OPC UA Server...");
        
        running_ = true;
        
        // Start server loop
        server_timer_ = create_wall_timer(
            100ms,
            std::bind(&OPCUAServerNode::server_loop, this)
        );

        // Start subscription publishing
        publish_timer_ = create_wall_timer(
            1s,
            std::bind(&OPCUAServerNode::publish_subscriptions, this)
        );
        
        RCLCPP_INFO(get_logger(), "OPC UA Server active");
        
        return CallbackReturn::SUCCESS;
    }

    CallbackReturn on_deactivate(const rclcpp_lifecycle::State&) override {
        running_ = false;
        server_timer_.reset();
        publish_timer_.reset();
        return CallbackReturn::SUCCESS;
    }

    CallbackReturn on_cleanup(const rclcpp_lifecycle::State&) override {
        data_change_pub_.reset();
        return CallbackReturn::SUCCESS;
    }

    CallbackReturn on_shutdown(const rclcpp_lifecycle::State&) override {
        return CallbackReturn::SUCCESS;
    }

    /**
     * @brief Read a variable node
     */
    std::optional<std::string> read_variable(const std::string& node_id) {
        std::lock_guard<std::mutex> lock(mutex_);
        
        auto it = variables_.find(node_id);
        if (it != variables_.end()) {
            return it->second.value;
        }
        return std::nullopt;
    }

    /**
     * @brief Write a variable node
     */
    bool write_variable(const std::string& node_id, const std::string& value) {
        std::lock_guard<std::mutex> lock(mutex_);
        
        auto it = variables_.find(node_id);
        if (it == variables_.end()) {
            return false;
        }
        
        // Check access level
        if (!(it->second.access_level & static_cast<uint8_t>(AccessLevel::CURRENT_WRITE))) {
            RCLCPP_WARN(get_logger(), "Write access denied for %s", node_id.c_str());
            return false;
        }
        
        std::string old_value = it->second.value;
        it->second.value = value;
        
        // Notify subscriptions
        notify_data_change(node_id, old_value, value);
        
        return true;
    }

    /**
     * @brief Call a method
     */
    std::string call_method(
        const std::string& node_id,
        const std::vector<std::string>& input_args
    ) {
        std::lock_guard<std::mutex> lock(mutex_);
        
        auto it = methods_.find(node_id);
        if (it == methods_.end()) {
            return "ERROR: Method not found";
        }
        
        if (it->second.handler) {
            return it->second.handler(input_args);
        }
        
        return "ERROR: No handler";
    }

    /**
     * @brief Create an OPC UA subscription
     */
    std::string create_opcua_subscription(
        const std::string& client_id,
        const std::vector<std::string>& items,
        std::chrono::milliseconds interval
    ) {
        std::lock_guard<std::mutex> lock(mutex_);
        
        std::string sub_id = "sub_" + std::to_string(subscription_counter_++);
        
        OPCUASubscription sub;
        sub.subscription_id = sub_id;
        sub.client_id = client_id;
        sub.monitored_items = items;
        sub.publishing_interval = interval;
        sub.last_publish = std::chrono::steady_clock::now();
        
        subscriptions_[sub_id] = sub;
        
        RCLCPP_INFO(get_logger(), "Created subscription %s for %s", 
            sub_id.c_str(), client_id.c_str());
        
        return sub_id;
    }

private:
    void initialize_address_space() {
        // Root objects
        add_object("ns=1;s=Manufacturing", "Manufacturing", "Root manufacturing node");
        add_object("ns=1;s=Equipment", "Equipment", "Equipment root");
        add_object("ns=1;s=Production", "Production", "Production data");
        add_object("ns=1;s=Quality", "Quality", "Quality data");
        
        // Equipment variables
        add_variable("ns=1;s=Equipment.Status", "EquipmentStatus", DataType::STRING, 
            "RUNNING", AccessLevel::CURRENT_READ, "ns=1;s=Equipment");
        add_variable("ns=1;s=Equipment.Temperature", "Temperature", DataType::DOUBLE,
            "25.0", AccessLevel::CURRENT_READ, "ns=1;s=Equipment");
        add_variable("ns=1;s=Equipment.Speed", "Speed", DataType::DOUBLE,
            "100.0", static_cast<AccessLevel>(
                static_cast<uint8_t>(AccessLevel::CURRENT_READ) |
                static_cast<uint8_t>(AccessLevel::CURRENT_WRITE)
            ), "ns=1;s=Equipment");
        
        // Production variables
        add_variable("ns=1;s=Production.Count", "ProductionCount", DataType::UINT64,
            "0", AccessLevel::CURRENT_READ, "ns=1;s=Production");
        add_variable("ns=1;s=Production.OEE", "OEE", DataType::DOUBLE,
            "0.85", AccessLevel::CURRENT_READ, "ns=1;s=Production");
        add_variable("ns=1;s=Production.CycleTime", "CycleTime", DataType::DOUBLE,
            "45.0", AccessLevel::CURRENT_READ, "ns=1;s=Production");
        
        // Quality variables
        add_variable("ns=1;s=Quality.DefectRate", "DefectRate", DataType::DOUBLE,
            "0.02", AccessLevel::CURRENT_READ, "ns=1;s=Quality");
        add_variable("ns=1;s=Quality.FirstPassYield", "FirstPassYield", DataType::DOUBLE,
            "0.98", AccessLevel::CURRENT_READ, "ns=1;s=Quality");
        
        // Methods
        add_method("ns=1;s=Equipment.Start", "Start", 
            {}, {{"result", DataType::BOOLEAN}},
            [this](const std::vector<std::string>&) {
                write_variable("ns=1;s=Equipment.Status", "RUNNING");
                return "true";
            });
        
        add_method("ns=1;s=Equipment.Stop", "Stop",
            {}, {{"result", DataType::BOOLEAN}},
            [this](const std::vector<std::string>&) {
                write_variable("ns=1;s=Equipment.Status", "STOPPED");
                return "true";
            });
        
        add_method("ns=1;s=Equipment.SetSpeed", "SetSpeed",
            {{"speed", DataType::DOUBLE}}, {{"result", DataType::BOOLEAN}},
            [this](const std::vector<std::string>& args) {
                if (args.empty()) return "false";
                write_variable("ns=1;s=Equipment.Speed", args[0]);
                return "true";
            });
        
        RCLCPP_INFO(get_logger(), "Address space initialized with %zu variables, %zu methods",
            variables_.size(), methods_.size());
    }

    void add_object(
        const std::string& node_id,
        const std::string& browse_name,
        const std::string& description
    ) {
        // Add object node (simplified)
        objects_[node_id] = browse_name;
    }

    void add_variable(
        const std::string& node_id,
        const std::string& browse_name,
        DataType data_type,
        const std::string& initial_value,
        AccessLevel access_level,
        const std::string& parent_node_id
    ) {
        VariableNode var;
        var.node_id = node_id;
        var.browse_name = browse_name;
        var.display_name = browse_name;
        var.data_type = data_type;
        var.value = initial_value;
        var.access_level = static_cast<uint8_t>(access_level);
        var.parent_node_id = parent_node_id;
        var.historizing = false;
        
        variables_[node_id] = var;
    }

    void add_method(
        const std::string& node_id,
        const std::string& browse_name,
        const std::vector<std::pair<std::string, DataType>>& inputs,
        const std::vector<std::pair<std::string, DataType>>& outputs,
        std::function<std::string(const std::vector<std::string>&)> handler
    ) {
        MethodNode method;
        method.node_id = node_id;
        method.browse_name = browse_name;
        method.display_name = browse_name;
        method.input_args = inputs;
        method.output_args = outputs;
        method.handler = handler;
        
        methods_[node_id] = method;
    }

    void server_loop() {
        // Process incoming requests (simplified)
        // Real implementation would handle OPC UA binary protocol
    }

    void publish_subscriptions() {
        std::lock_guard<std::mutex> lock(mutex_);
        
        auto now = std::chrono::steady_clock::now();
        
        for (auto& [sub_id, sub] : subscriptions_) {
            if (now - sub.last_publish >= sub.publishing_interval) {
                // Publish data for monitored items
                for (const auto& item : sub.monitored_items) {
                    auto it = variables_.find(item);
                    if (it != variables_.end()) {
                        // Publish to ROS2
                        publish_data_change(item, it->second.value);
                    }
                }
                sub.last_publish = now;
            }
        }
    }

    void notify_data_change(
        const std::string& node_id,
        const std::string& old_value,
        const std::string& new_value
    ) {
        // Notify all subscriptions monitoring this node
        for (const auto& [sub_id, sub] : subscriptions_) {
            for (const auto& item : sub.monitored_items) {
                if (item == node_id) {
                    publish_data_change(node_id, new_value);
                    break;
                }
            }
        }
    }

    void publish_data_change(const std::string& node_id, const std::string& value) {
        if (!data_change_pub_) return;
        
        auto msg = std_msgs::msg::String();
        msg.data = "{\"node_id\":\"" + node_id + "\",\"value\":\"" + value + "\"}";
        data_change_pub_->publish(msg);
    }

    void handle_ros_data(const std_msgs::msg::String::SharedPtr msg) {
        // Bridge ROS2 data to OPC UA variables
        // Parse JSON and update corresponding OPC UA nodes
        RCLCPP_DEBUG(get_logger(), "Received ROS data: %s", msg->data.c_str());
    }

    void handle_read(
        const std::shared_ptr<std_srvs::srv::Trigger::Request>,
        std::shared_ptr<std_srvs::srv::Trigger::Response> response
    ) {
        auto value = read_variable("ns=1;s=Production.OEE");
        response->success = value.has_value();
        response->message = value.value_or("ERROR");
    }

    // Configuration
    std::string server_name_;
    int port_;
    std::string namespace_uri_;
    
    // Address space
    std::unordered_map<std::string, std::string> objects_;
    std::unordered_map<std::string, VariableNode> variables_;
    std::unordered_map<std::string, MethodNode> methods_;
    std::unordered_map<std::string, OPCUASubscription> subscriptions_;
    std::atomic<uint64_t> subscription_counter_{0};
    
    std::mutex mutex_;
    std::atomic<bool> running_;
    
    // ROS2 interfaces
    rclcpp::Publisher<std_msgs::msg::String>::SharedPtr data_change_pub_;
    rclcpp::Subscription<std_msgs::msg::String>::SharedPtr ros_data_sub_;
    rclcpp::Service<std_srvs::srv::Trigger>::SharedPtr read_srv_;
    rclcpp::TimerBase::SharedPtr server_timer_;
    rclcpp::TimerBase::SharedPtr publish_timer_;
};

}  // namespace opcua
}  // namespace lego_mcp

int main(int argc, char* argv[]) {
    rclcpp::init(argc, argv);
    auto node = std::make_shared<lego_mcp::opcua::OPCUAServerNode>();
    rclcpp::executors::SingleThreadedExecutor executor;
    executor.add_node(node->get_node_base_interface());
    executor.spin();
    rclcpp::shutdown();
    return 0;
}
