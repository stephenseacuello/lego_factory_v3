/**
 * @file bft_consensus_node.cpp
 * @brief Byzantine Fault Tolerant Consensus for Distributed Manufacturing
 * 
 * Implements Practical Byzantine Fault Tolerance (PBFT) for:
 * - Multi-robot coordination with f fault tolerance
 * - Distributed decision making
 * - Safety-critical voting
 * 
 * Reference: Castro & Liskov "Practical Byzantine Fault Tolerance"
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
#include <functional>
#include <atomic>
#include <optional>

namespace lego_mcp {
namespace consensus {

using namespace std::chrono_literals;

/**
 * @brief PBFT Message Types
 */
enum class MessageType {
    REQUEST,
    PRE_PREPARE,
    PREPARE,
    COMMIT,
    REPLY,
    VIEW_CHANGE,
    NEW_VIEW,
    CHECKPOINT
};

/**
 * @brief Consensus phase
 */
enum class ConsensusPhase {
    IDLE,
    PRE_PREPARE,
    PREPARE,
    COMMIT,
    EXECUTED
};

/**
 * @brief PBFT Message structure
 */
struct PBFTMessage {
    MessageType type;
    uint64_t view_number;
    uint64_t sequence_number;
    std::string digest;        // SHA-256 of request
    std::string node_id;
    std::string signature;     // ECDSA signature
    std::string payload;
    int64_t timestamp;
    
    std::string to_json() const {
        std::ostringstream oss;
        oss << "{\"type\":" << static_cast<int>(type)
            << ",\"view\":" << view_number
            << ",\"seq\":" << sequence_number
            << ",\"digest\":\"" << digest << "\""
            << ",\"node\":\"" << node_id << "\""
            << ",\"ts\":" << timestamp << "}";
        return oss.str();
    }
};

/**
 * @brief Pending request entry
 */
struct RequestEntry {
    PBFTMessage request;
    ConsensusPhase phase;
    std::unordered_map<std::string, PBFTMessage> prepares;
    std::unordered_map<std::string, PBFTMessage> commits;
    bool executed;
};

/**
 * @brief BFT Consensus Node
 * 
 * Implements PBFT protocol for Byzantine fault tolerance.
 * Tolerates f Byzantine faults with 3f+1 nodes.
 */
class BFTConsensusNode : public rclcpp_lifecycle::LifecycleNode {
public:
    explicit BFTConsensusNode(const rclcpp::NodeOptions& options = rclcpp::NodeOptions())
        : rclcpp_lifecycle::LifecycleNode("bft_consensus", options)
        , view_number_(0)
        , sequence_number_(0)
        , is_primary_(false)
    {
        // Parameters
        declare_parameter("node_id", "node_0");
        declare_parameter("cluster_size", 4);  // 3f+1 for f=1
        declare_parameter("fault_tolerance", 1);
        declare_parameter("checkpoint_interval", 100);
        declare_parameter("view_change_timeout_ms", 5000);
        
        RCLCPP_INFO(get_logger(), "BFTConsensusNode created");
    }

    CallbackReturn on_configure(const rclcpp_lifecycle::State&) override {
        RCLCPP_INFO(get_logger(), "Configuring BFT Consensus...");
        
        node_id_ = get_parameter("node_id").as_string();
        cluster_size_ = get_parameter("cluster_size").as_int();
        fault_tolerance_ = get_parameter("fault_tolerance").as_int();
        checkpoint_interval_ = get_parameter("checkpoint_interval").as_int();
        view_change_timeout_ = std::chrono::milliseconds(
            get_parameter("view_change_timeout_ms").as_int()
        );
        
        // Verify 3f+1 requirement
        if (cluster_size_ < 3 * fault_tolerance_ + 1) {
            RCLCPP_ERROR(get_logger(), 
                "Cluster size %d insufficient for f=%d (need 3f+1=%d)",
                cluster_size_, fault_tolerance_, 3 * fault_tolerance_ + 1);
            return CallbackReturn::FAILURE;
        }
        
        // Calculate quorum sizes
        quorum_size_ = 2 * fault_tolerance_ + 1;  // 2f+1
        
        // Create publishers
        consensus_pub_ = create_publisher<std_msgs::msg::String>(
            "bft/consensus", 100
        );
        decision_pub_ = create_publisher<std_msgs::msg::String>(
            "bft/decisions", 10
        );
        
        // Create subscription
        consensus_sub_ = create_subscription<std_msgs::msg::String>(
            "bft/consensus", 100,
            std::bind(&BFTConsensusNode::handle_message, this, std::placeholders::_1)
        );
        
        // Create services
        propose_srv_ = create_service<std_srvs::srv::Trigger>(
            "bft/propose",
            std::bind(&BFTConsensusNode::handle_propose, this,
                     std::placeholders::_1, std::placeholders::_2)
        );
        
        RCLCPP_INFO(get_logger(), 
            "BFT configured: node=%s, cluster=%d, f=%d, quorum=%d",
            node_id_.c_str(), cluster_size_, fault_tolerance_, quorum_size_);
        
        return CallbackReturn::SUCCESS;
    }

    CallbackReturn on_activate(const rclcpp_lifecycle::State&) override {
        RCLCPP_INFO(get_logger(), "Activating BFT Consensus...");
        
        // Determine if we're the primary
        is_primary_ = (compute_primary_index() == node_index());
        
        // Start consensus timer
        consensus_timer_ = create_wall_timer(
            100ms,
            std::bind(&BFTConsensusNode::process_consensus, this)
        );
        
        // Start view change timer
        view_change_timer_ = create_wall_timer(
            view_change_timeout_,
            std::bind(&BFTConsensusNode::check_view_change, this)
        );
        
        RCLCPP_INFO(get_logger(), "BFT active (primary=%s)", 
            is_primary_ ? "true" : "false");
        
        return CallbackReturn::SUCCESS;
    }

    CallbackReturn on_deactivate(const rclcpp_lifecycle::State&) override {
        consensus_timer_.reset();
        view_change_timer_.reset();
        return CallbackReturn::SUCCESS;
    }

    CallbackReturn on_cleanup(const rclcpp_lifecycle::State&) override {
        consensus_pub_.reset();
        decision_pub_.reset();
        consensus_sub_.reset();
        return CallbackReturn::SUCCESS;
    }

    CallbackReturn on_shutdown(const rclcpp_lifecycle::State&) override {
        RCLCPP_INFO(get_logger(), "Shutting down BFT Consensus");
        return CallbackReturn::SUCCESS;
    }

    /**
     * @brief Submit a request for consensus
     */
    bool submit_request(const std::string& operation) {
        if (!is_primary_) {
            RCLCPP_WARN(get_logger(), "Not primary - forwarding request");
            // In real implementation, forward to primary
            return false;
        }
        
        std::lock_guard<std::mutex> lock(mutex_);
        
        sequence_number_++;
        
        PBFTMessage request;
        request.type = MessageType::REQUEST;
        request.view_number = view_number_;
        request.sequence_number = sequence_number_;
        request.digest = compute_digest(operation);
        request.node_id = node_id_;
        request.payload = operation;
        request.timestamp = now_ms();
        request.signature = sign_message(request);
        
        // Create pending entry
        RequestEntry entry;
        entry.request = request;
        entry.phase = ConsensusPhase::PRE_PREPARE;
        entry.executed = false;
        pending_[sequence_number_] = entry;
        
        // Send PRE-PREPARE
        PBFTMessage pre_prepare = request;
        pre_prepare.type = MessageType::PRE_PREPARE;
        broadcast(pre_prepare);
        
        RCLCPP_INFO(get_logger(),
            "Request submitted: seq=%lu, digest=%s",
            sequence_number_.load(), request.digest.substr(0, 8).c_str());
        
        return true;
    }

private:
    void handle_message(const std_msgs::msg::String::SharedPtr msg) {
        // Parse message
        auto pbft_msg = parse_message(msg->data);
        if (!pbft_msg) {
            return;
        }
        
        // Verify signature
        if (!verify_signature(*pbft_msg)) {
            RCLCPP_WARN(get_logger(), "Invalid signature from %s", 
                pbft_msg->node_id.c_str());
            return;
        }
        
        // Ignore our own messages
        if (pbft_msg->node_id == node_id_) {
            return;
        }
        
        std::lock_guard<std::mutex> lock(mutex_);
        
        switch (pbft_msg->type) {
            case MessageType::PRE_PREPARE:
                handle_pre_prepare(*pbft_msg);
                break;
            case MessageType::PREPARE:
                handle_prepare(*pbft_msg);
                break;
            case MessageType::COMMIT:
                handle_commit(*pbft_msg);
                break;
            case MessageType::VIEW_CHANGE:
                handle_view_change(*pbft_msg);
                break;
            default:
                break;
        }
    }

    void handle_pre_prepare(const PBFTMessage& msg) {
        // Verify it's from the primary
        if (!is_from_primary(msg)) {
            RCLCPP_WARN(get_logger(), "PRE-PREPARE not from primary");
            return;
        }
        
        // Check view number
        if (msg.view_number != view_number_) {
            return;
        }
        
        // Check we haven't already accepted a PRE-PREPARE for this seq
        if (pending_.find(msg.sequence_number) != pending_.end()) {
            return;
        }
        
        // Accept and move to PREPARE phase
        RequestEntry entry;
        entry.request = msg;
        entry.phase = ConsensusPhase::PREPARE;
        entry.executed = false;
        pending_[msg.sequence_number] = entry;
        
        // Send PREPARE
        PBFTMessage prepare;
        prepare.type = MessageType::PREPARE;
        prepare.view_number = view_number_;
        prepare.sequence_number = msg.sequence_number;
        prepare.digest = msg.digest;
        prepare.node_id = node_id_;
        prepare.timestamp = now_ms();
        prepare.signature = sign_message(prepare);
        
        broadcast(prepare);
        
        RCLCPP_DEBUG(get_logger(), 
            "Sent PREPARE for seq=%lu", msg.sequence_number);
    }

    void handle_prepare(const PBFTMessage& msg) {
        auto it = pending_.find(msg.sequence_number);
        if (it == pending_.end()) {
            return;
        }
        
        RequestEntry& entry = it->second;
        
        // Verify digest matches
        if (msg.digest != entry.request.digest) {
            return;
        }
        
        // Record prepare
        entry.prepares[msg.node_id] = msg;
        
        // Check if we have 2f prepares (including ours)
        if (entry.phase == ConsensusPhase::PREPARE &&
            entry.prepares.size() >= static_cast<size_t>(quorum_size_ - 1)) {
            
            entry.phase = ConsensusPhase::COMMIT;
            
            // Send COMMIT
            PBFTMessage commit;
            commit.type = MessageType::COMMIT;
            commit.view_number = view_number_;
            commit.sequence_number = msg.sequence_number;
            commit.digest = msg.digest;
            commit.node_id = node_id_;
            commit.timestamp = now_ms();
            commit.signature = sign_message(commit);
            
            broadcast(commit);
            
            RCLCPP_DEBUG(get_logger(), 
                "Sent COMMIT for seq=%lu (prepares=%zu)",
                msg.sequence_number, entry.prepares.size());
        }
    }

    void handle_commit(const PBFTMessage& msg) {
        auto it = pending_.find(msg.sequence_number);
        if (it == pending_.end()) {
            return;
        }
        
        RequestEntry& entry = it->second;
        
        // Verify digest
        if (msg.digest != entry.request.digest) {
            return;
        }
        
        // Record commit
        entry.commits[msg.node_id] = msg;
        
        // Check if we have 2f+1 commits
        if (!entry.executed &&
            entry.commits.size() >= static_cast<size_t>(quorum_size_)) {
            
            entry.phase = ConsensusPhase::EXECUTED;
            entry.executed = true;
            
            // Execute the request
            execute_request(entry.request);
            
            RCLCPP_INFO(get_logger(), 
                "Consensus reached: seq=%lu, commits=%zu",
                msg.sequence_number, entry.commits.size());
        }
    }

    void handle_view_change(const PBFTMessage& msg) {
        // Simplified view change handling
        RCLCPP_WARN(get_logger(), 
            "View change requested by %s", msg.node_id.c_str());
        // Full implementation would collect 2f+1 VIEW-CHANGE messages
        // and elect new primary
    }

    void execute_request(const PBFTMessage& request) {
        // Publish decision
        auto msg = std_msgs::msg::String();
        msg.data = "{\"seq\":" + std::to_string(request.sequence_number) +
                   ",\"operation\":\"" + request.payload + 
                   "\",\"digest\":\"" + request.digest + "\"}";
        
        if (decision_pub_) {
            decision_pub_->publish(msg);
        }
        
        RCLCPP_INFO(get_logger(), 
            "Executed: seq=%lu, op=%s",
            request.sequence_number, request.payload.c_str());
    }

    void process_consensus() {
        // Periodic consensus processing
        // Check for timeouts, retransmissions, etc.
    }

    void check_view_change() {
        // Check if primary is responsive
        // Initiate view change if needed
    }

    void handle_propose(
        const std::shared_ptr<std_srvs::srv::Trigger::Request>,
        std::shared_ptr<std_srvs::srv::Trigger::Response> response
    ) {
        bool success = submit_request("test_operation");
        response->success = success;
        response->message = success ? "Request submitted" : "Failed to submit";
    }

    void broadcast(const PBFTMessage& msg) {
        auto ros_msg = std_msgs::msg::String();
        ros_msg.data = msg.to_json();
        
        if (consensus_pub_) {
            consensus_pub_->publish(ros_msg);
        }
    }

    std::optional<PBFTMessage> parse_message(const std::string& data) {
        // Simplified parsing
        PBFTMessage msg;
        // In real implementation, parse JSON
        msg.payload = data;
        return msg;
    }

    std::string compute_digest(const std::string& data) {
        // Simplified hash - real implementation uses SHA-256
        std::hash<std::string> hasher;
        std::ostringstream oss;
        oss << std::hex << hasher(data);
        return oss.str();
    }

    std::string sign_message(const PBFTMessage& msg) {
        // Simplified signature - real implementation uses ECDSA
        return compute_digest(msg.to_json() + node_id_);
    }

    bool verify_signature(const PBFTMessage& msg) {
        // Simplified verification
        return !msg.signature.empty();
    }

    bool is_from_primary(const PBFTMessage& msg) {
        int primary_idx = compute_primary_index();
        // Check if sender is the primary for this view
        return msg.node_id == "node_" + std::to_string(primary_idx);
    }

    int compute_primary_index() {
        return static_cast<int>(view_number_ % cluster_size_);
    }

    int node_index() {
        // Extract node index from node_id (e.g., "node_0" -> 0)
        if (node_id_.substr(0, 5) == "node_") {
            return std::stoi(node_id_.substr(5));
        }
        return 0;
    }

    int64_t now_ms() {
        return std::chrono::duration_cast<std::chrono::milliseconds>(
            std::chrono::system_clock::now().time_since_epoch()
        ).count();
    }

    // Configuration
    std::string node_id_;
    int cluster_size_;
    int fault_tolerance_;
    int quorum_size_;
    int checkpoint_interval_;
    std::chrono::milliseconds view_change_timeout_;
    
    // State
    std::atomic<uint64_t> view_number_;
    std::atomic<uint64_t> sequence_number_;
    std::atomic<bool> is_primary_;
    std::unordered_map<uint64_t, RequestEntry> pending_;
    std::mutex mutex_;
    
    // ROS2 interfaces
    rclcpp::Publisher<std_msgs::msg::String>::SharedPtr consensus_pub_;
    rclcpp::Publisher<std_msgs::msg::String>::SharedPtr decision_pub_;
    rclcpp::Subscription<std_msgs::msg::String>::SharedPtr consensus_sub_;
    rclcpp::Service<std_srvs::srv::Trigger>::SharedPtr propose_srv_;
    rclcpp::TimerBase::SharedPtr consensus_timer_;
    rclcpp::TimerBase::SharedPtr view_change_timer_;
};

}  // namespace consensus
}  // namespace lego_mcp

int main(int argc, char* argv[]) {
    rclcpp::init(argc, argv);
    auto node = std::make_shared<lego_mcp::consensus::BFTConsensusNode>();
    rclcpp::executors::SingleThreadedExecutor executor;
    executor.add_node(node->get_node_base_interface());
    executor.spin();
    rclcpp::shutdown();
    return 0;
}
