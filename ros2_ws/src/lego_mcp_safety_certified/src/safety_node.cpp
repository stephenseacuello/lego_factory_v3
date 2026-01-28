/**
 * @file safety_node.cpp
 * @brief IEC 61508 Safety Node - Simplified Implementation
 *
 * ROS2 Lifecycle Node for safety-critical e-stop control
 */

#include <rclcpp/rclcpp.hpp>
#include <rclcpp_lifecycle/lifecycle_node.hpp>
#include <std_msgs/msg/bool.hpp>
#include <std_msgs/msg/string.hpp>
#include <std_srvs/srv/trigger.hpp>

#include <chrono>
#include <memory>
#include <mutex>
#include <atomic>

namespace lego_mcp
{

/**
 * @brief SafetyNode - Lifecycle node for safety functions
 */
class SafetyNode : public rclcpp_lifecycle::LifecycleNode
{
public:
    explicit SafetyNode(const rclcpp::NodeOptions& options = rclcpp::NodeOptions())
        : rclcpp_lifecycle::LifecycleNode("safety_node", options)
        , estop_active_(false)
    {
        // Declare parameters
        declare_parameter("heartbeat_timeout_ms", 1000);
        declare_parameter("watchdog_interval_ms", 100);
        declare_parameter("dual_channel_enabled", true);

        RCLCPP_INFO(get_logger(), "Safety Node constructed");
    }

    ~SafetyNode() override = default;

    // Lifecycle callbacks
    rclcpp_lifecycle::node_interfaces::LifecycleNodeInterface::CallbackReturn
    on_configure(const rclcpp_lifecycle::State&) override
    {
        RCLCPP_INFO(get_logger(), "Configuring Safety Node");

        // Create publishers
        state_pub_ = create_publisher<std_msgs::msg::String>(
            "~/safety_state", rclcpp::QoS(10));

        estop_pub_ = create_publisher<std_msgs::msg::Bool>(
            "~/estop_status", rclcpp::QoS(10).reliable());

        // Create subscriptions
        heartbeat_sub_ = create_subscription<std_msgs::msg::Bool>(
            "~/heartbeat",
            rclcpp::QoS(10),
            [this](std_msgs::msg::Bool::SharedPtr msg) {
                (void)msg;
                last_heartbeat_ = std::chrono::steady_clock::now();
            });

        estop_sub_ = create_subscription<std_msgs::msg::Bool>(
            "/estop",
            rclcpp::QoS(10).reliable(),
            [this](std_msgs::msg::Bool::SharedPtr msg) {
                if (msg->data) {
                    trigger_estop("External e-stop signal");
                }
            });

        // Create services
        estop_service_ = create_service<std_srvs::srv::Trigger>(
            "~/trigger_estop",
            [this](
                const std::shared_ptr<std_srvs::srv::Trigger::Request>,
                std::shared_ptr<std_srvs::srv::Trigger::Response> response) {
                trigger_estop("Service request");
                response->success = true;
                response->message = "E-stop triggered";
            });

        reset_service_ = create_service<std_srvs::srv::Trigger>(
            "~/reset_estop",
            [this](
                const std::shared_ptr<std_srvs::srv::Trigger::Request>,
                std::shared_ptr<std_srvs::srv::Trigger::Response> response) {
                reset_estop();
                response->success = true;
                response->message = "E-stop reset";
            });

        // Initialize heartbeat time
        last_heartbeat_ = std::chrono::steady_clock::now();

        RCLCPP_INFO(get_logger(), "Safety Node configured");
        return CallbackReturn::SUCCESS;
    }

    rclcpp_lifecycle::node_interfaces::LifecycleNodeInterface::CallbackReturn
    on_activate(const rclcpp_lifecycle::State&) override
    {
        RCLCPP_INFO(get_logger(), "Activating Safety Node");

        state_pub_->on_activate();
        estop_pub_->on_activate();

        // Create watchdog timer
        auto watchdog_interval = std::chrono::milliseconds(
            get_parameter("watchdog_interval_ms").as_int());

        watchdog_timer_ = create_wall_timer(
            watchdog_interval,
            [this]() { watchdog_callback(); });

        publish_state("ACTIVE");

        RCLCPP_INFO(get_logger(), "Safety Node activated");
        return CallbackReturn::SUCCESS;
    }

    rclcpp_lifecycle::node_interfaces::LifecycleNodeInterface::CallbackReturn
    on_deactivate(const rclcpp_lifecycle::State&) override
    {
        RCLCPP_INFO(get_logger(), "Deactivating Safety Node");

        if (watchdog_timer_) {
            watchdog_timer_->cancel();
        }

        state_pub_->on_deactivate();
        estop_pub_->on_deactivate();

        RCLCPP_INFO(get_logger(), "Safety Node deactivated");
        return CallbackReturn::SUCCESS;
    }

    rclcpp_lifecycle::node_interfaces::LifecycleNodeInterface::CallbackReturn
    on_cleanup(const rclcpp_lifecycle::State&) override
    {
        RCLCPP_INFO(get_logger(), "Cleaning up Safety Node");

        watchdog_timer_.reset();
        state_pub_.reset();
        estop_pub_.reset();
        heartbeat_sub_.reset();
        estop_sub_.reset();
        estop_service_.reset();
        reset_service_.reset();

        return CallbackReturn::SUCCESS;
    }

    rclcpp_lifecycle::node_interfaces::LifecycleNodeInterface::CallbackReturn
    on_shutdown(const rclcpp_lifecycle::State&) override
    {
        RCLCPP_INFO(get_logger(), "Shutting down Safety Node");

        // Ensure safe state
        trigger_estop("Node shutdown");

        return CallbackReturn::SUCCESS;
    }

private:
    void watchdog_callback()
    {
        auto now = std::chrono::steady_clock::now();
        auto elapsed = std::chrono::duration_cast<std::chrono::milliseconds>(
            now - last_heartbeat_).count();

        auto timeout = get_parameter("heartbeat_timeout_ms").as_int();

        if (elapsed > timeout && !estop_active_) {
            RCLCPP_WARN(get_logger(), "Heartbeat timeout - triggering e-stop");
            trigger_estop("Heartbeat timeout");
        }

        // Publish e-stop status
        if (estop_pub_ && estop_pub_->is_activated()) {
            auto msg = std::make_unique<std_msgs::msg::Bool>();
            msg->data = estop_active_.load();
            estop_pub_->publish(std::move(msg));
        }
    }

    void trigger_estop(const std::string& reason)
    {
        estop_active_ = true;
        RCLCPP_ERROR(get_logger(), "E-STOP TRIGGERED: %s", reason.c_str());
        publish_state("ESTOP");
    }

    void reset_estop()
    {
        estop_active_ = false;
        RCLCPP_INFO(get_logger(), "E-stop reset");
        publish_state("ACTIVE");
    }

    void publish_state(const std::string& state)
    {
        if (state_pub_ && state_pub_->is_activated()) {
            auto msg = std::make_unique<std_msgs::msg::String>();
            msg->data = state;
            state_pub_->publish(std::move(msg));
        }
    }

    // State
    std::atomic<bool> estop_active_;
    std::chrono::steady_clock::time_point last_heartbeat_;

    // Publishers
    rclcpp_lifecycle::LifecyclePublisher<std_msgs::msg::String>::SharedPtr state_pub_;
    rclcpp_lifecycle::LifecyclePublisher<std_msgs::msg::Bool>::SharedPtr estop_pub_;

    // Subscriptions
    rclcpp::Subscription<std_msgs::msg::Bool>::SharedPtr heartbeat_sub_;
    rclcpp::Subscription<std_msgs::msg::Bool>::SharedPtr estop_sub_;

    // Services
    rclcpp::Service<std_srvs::srv::Trigger>::SharedPtr estop_service_;
    rclcpp::Service<std_srvs::srv::Trigger>::SharedPtr reset_service_;

    // Timers
    rclcpp::TimerBase::SharedPtr watchdog_timer_;
};

}  // namespace lego_mcp

// Register as ROS2 component
#include <rclcpp_components/register_node_macro.hpp>
RCLCPP_COMPONENTS_REGISTER_NODE(lego_mcp::SafetyNode)
