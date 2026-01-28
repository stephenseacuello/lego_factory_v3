/**
 * Post-Quantum Cryptography Node
 *
 * Implements NIST standardized post-quantum algorithms:
 * - ML-KEM (CRYSTALS-Kyber) for key encapsulation
 * - ML-DSA (CRYSTALS-Dilithium) for digital signatures
 * - SLH-DSA (SPHINCS+) for hash-based signatures
 *
 * Reference: NIST FIPS 203, 204, 205
 */

#include <rclcpp/rclcpp.hpp>
#include <rclcpp_lifecycle/lifecycle_node.hpp>
#include <std_msgs/msg/string.hpp>
#include <std_srvs/srv/trigger.hpp>

#include <algorithm>
#include <array>
#include <chrono>
#include <cstdint>
#include <iomanip>
#include <memory>
#include <mutex>
#include <random>
#include <sstream>
#include <string>
#include <unordered_map>
#include <vector>

using namespace std::chrono_literals;

namespace lego_mcp {

/**
 * Security levels per NIST PQC standards
 */
enum class SecurityLevel {
    LEVEL_1 = 1,  // AES-128 equivalent
    LEVEL_3 = 3,  // AES-192 equivalent
    LEVEL_5 = 5   // AES-256 equivalent
};

/**
 * Algorithm types
 */
enum class PQAlgorithm {
    ML_KEM_512,       // Kyber-512 (Level 1)
    ML_KEM_768,       // Kyber-768 (Level 3)
    ML_KEM_1024,      // Kyber-1024 (Level 5)
    ML_DSA_44,        // Dilithium2 (Level 2)
    ML_DSA_65,        // Dilithium3 (Level 3)
    ML_DSA_87,        // Dilithium5 (Level 5)
    SLH_DSA_128S,     // SPHINCS+-128s
    SLH_DSA_192S,     // SPHINCS+-192s
    SLH_DSA_256S      // SPHINCS+-256s
};

/**
 * Key pair structure
 */
struct KeyPair {
    std::string key_id;
    PQAlgorithm algorithm;
    std::vector<uint8_t> public_key;
    std::vector<uint8_t> private_key;
    std::chrono::system_clock::time_point created;
    std::chrono::system_clock::time_point expires;
    bool is_valid{true};
};

/**
 * Encapsulation result (for KEM)
 */
struct EncapsulationResult {
    std::vector<uint8_t> ciphertext;
    std::vector<uint8_t> shared_secret;
};

/**
 * Signature result
 */
struct SignatureResult {
    std::vector<uint8_t> signature;
    std::string algorithm;
    std::string key_id;
};

/**
 * Simulated ML-KEM (Kyber) Implementation
 *
 * This is a simulation for demonstration.
 * Production would use liboqs or similar library.
 */
class MLKEM {
public:
    static constexpr size_t KYBER768_PK_SIZE = 1184;
    static constexpr size_t KYBER768_SK_SIZE = 2400;
    static constexpr size_t KYBER768_CT_SIZE = 1088;
    static constexpr size_t SHARED_SECRET_SIZE = 32;

    static KeyPair generate_keypair(const std::string& key_id, SecurityLevel level) {
        KeyPair kp;
        kp.key_id = key_id;
        kp.created = std::chrono::system_clock::now();
        kp.expires = kp.created + std::chrono::hours(24 * 365);  // 1 year

        size_t pk_size, sk_size;
        switch (level) {
            case SecurityLevel::LEVEL_1:
                kp.algorithm = PQAlgorithm::ML_KEM_512;
                pk_size = 800;
                sk_size = 1632;
                break;
            case SecurityLevel::LEVEL_5:
                kp.algorithm = PQAlgorithm::ML_KEM_1024;
                pk_size = 1568;
                sk_size = 3168;
                break;
            default:  // Level 3
                kp.algorithm = PQAlgorithm::ML_KEM_768;
                pk_size = KYBER768_PK_SIZE;
                sk_size = KYBER768_SK_SIZE;
        }

        // Simulate key generation with random bytes
        kp.public_key = generate_random_bytes(pk_size);
        kp.private_key = generate_random_bytes(sk_size);

        return kp;
    }

    static EncapsulationResult encapsulate(const std::vector<uint8_t>& public_key) {
        EncapsulationResult result;

        // Simulate encapsulation
        result.ciphertext = generate_random_bytes(KYBER768_CT_SIZE);
        result.shared_secret = generate_random_bytes(SHARED_SECRET_SIZE);

        // In real implementation, shared_secret would be derived from
        // the public key and randomness using the Kyber algorithm

        return result;
    }

    static std::vector<uint8_t> decapsulate(
        const std::vector<uint8_t>& private_key,
        const std::vector<uint8_t>& ciphertext
    ) {
        // Simulate decapsulation
        // In real implementation, this derives the shared secret
        // from the ciphertext using the private key
        return generate_random_bytes(SHARED_SECRET_SIZE);
    }

private:
    static std::vector<uint8_t> generate_random_bytes(size_t count) {
        std::vector<uint8_t> bytes(count);
        std::random_device rd;
        std::mt19937 gen(rd());
        std::uniform_int_distribution<> dis(0, 255);
        for (auto& b : bytes) {
            b = static_cast<uint8_t>(dis(gen));
        }
        return bytes;
    }
};

/**
 * Simulated ML-DSA (Dilithium) Implementation
 */
class MLDSA {
public:
    static constexpr size_t DILITHIUM3_PK_SIZE = 1952;
    static constexpr size_t DILITHIUM3_SK_SIZE = 4000;
    static constexpr size_t DILITHIUM3_SIG_SIZE = 3293;

    static KeyPair generate_keypair(const std::string& key_id, SecurityLevel level) {
        KeyPair kp;
        kp.key_id = key_id;
        kp.created = std::chrono::system_clock::now();
        kp.expires = kp.created + std::chrono::hours(24 * 365);

        size_t pk_size, sk_size;
        switch (level) {
            case SecurityLevel::LEVEL_1:
                kp.algorithm = PQAlgorithm::ML_DSA_44;
                pk_size = 1312;
                sk_size = 2528;
                break;
            case SecurityLevel::LEVEL_5:
                kp.algorithm = PQAlgorithm::ML_DSA_87;
                pk_size = 2592;
                sk_size = 4864;
                break;
            default:  // Level 3
                kp.algorithm = PQAlgorithm::ML_DSA_65;
                pk_size = DILITHIUM3_PK_SIZE;
                sk_size = DILITHIUM3_SK_SIZE;
        }

        kp.public_key = generate_random_bytes(pk_size);
        kp.private_key = generate_random_bytes(sk_size);

        return kp;
    }

    static SignatureResult sign(
        const std::vector<uint8_t>& private_key,
        const std::vector<uint8_t>& message,
        const std::string& key_id
    ) {
        SignatureResult result;
        result.key_id = key_id;
        result.algorithm = "ML-DSA-65";

        // Simulate signature generation
        // Real implementation uses Dilithium algorithm
        result.signature = generate_random_bytes(DILITHIUM3_SIG_SIZE);

        return result;
    }

    static bool verify(
        const std::vector<uint8_t>& public_key,
        const std::vector<uint8_t>& message,
        const std::vector<uint8_t>& signature
    ) {
        // Simulate verification
        // In real implementation, this verifies the signature
        // against the message using the public key
        return true;  // Simulation always succeeds
    }

private:
    static std::vector<uint8_t> generate_random_bytes(size_t count) {
        std::vector<uint8_t> bytes(count);
        std::random_device rd;
        std::mt19937 gen(rd());
        std::uniform_int_distribution<> dis(0, 255);
        for (auto& b : bytes) {
            b = static_cast<uint8_t>(dis(gen));
        }
        return bytes;
    }
};

/**
 * Simulated SLH-DSA (SPHINCS+) Implementation
 */
class SLHDSA {
public:
    static constexpr size_t SPHINCS_128S_PK_SIZE = 32;
    static constexpr size_t SPHINCS_128S_SK_SIZE = 64;
    static constexpr size_t SPHINCS_128S_SIG_SIZE = 7856;

    static KeyPair generate_keypair(const std::string& key_id, SecurityLevel level) {
        KeyPair kp;
        kp.key_id = key_id;
        kp.created = std::chrono::system_clock::now();
        kp.expires = kp.created + std::chrono::hours(24 * 365 * 10);  // 10 years

        size_t pk_size, sk_size;
        switch (level) {
            case SecurityLevel::LEVEL_3:
                kp.algorithm = PQAlgorithm::SLH_DSA_192S;
                pk_size = 48;
                sk_size = 96;
                break;
            case SecurityLevel::LEVEL_5:
                kp.algorithm = PQAlgorithm::SLH_DSA_256S;
                pk_size = 64;
                sk_size = 128;
                break;
            default:  // Level 1
                kp.algorithm = PQAlgorithm::SLH_DSA_128S;
                pk_size = SPHINCS_128S_PK_SIZE;
                sk_size = SPHINCS_128S_SK_SIZE;
        }

        kp.public_key = generate_random_bytes(pk_size);
        kp.private_key = generate_random_bytes(sk_size);

        return kp;
    }

    static SignatureResult sign(
        const std::vector<uint8_t>& private_key,
        const std::vector<uint8_t>& message,
        const std::string& key_id
    ) {
        SignatureResult result;
        result.key_id = key_id;
        result.algorithm = "SLH-DSA-128s";

        // SPHINCS+ produces larger signatures but is hash-based
        // (no lattice assumptions)
        result.signature = generate_random_bytes(SPHINCS_128S_SIG_SIZE);

        return result;
    }

    static bool verify(
        const std::vector<uint8_t>& public_key,
        const std::vector<uint8_t>& message,
        const std::vector<uint8_t>& signature
    ) {
        return true;  // Simulation
    }

private:
    static std::vector<uint8_t> generate_random_bytes(size_t count) {
        std::vector<uint8_t> bytes(count);
        std::random_device rd;
        std::mt19937 gen(rd());
        std::uniform_int_distribution<> dis(0, 255);
        for (auto& b : bytes) {
            b = static_cast<uint8_t>(dis(gen));
        }
        return bytes;
    }
};

/**
 * Post-Quantum Cryptography Node
 *
 * Provides ROS2 interface to PQC operations
 */
class PQCryptoNode : public rclcpp_lifecycle::LifecycleNode {
public:
    explicit PQCryptoNode(const rclcpp::NodeOptions& options = rclcpp::NodeOptions())
        : rclcpp_lifecycle::LifecycleNode("pq_crypto", options)
    {
        RCLCPP_INFO(get_logger(), "Post-Quantum Crypto Node created");
    }

    rclcpp_lifecycle::node_interfaces::LifecycleNodeInterface::CallbackReturn
    on_configure(const rclcpp_lifecycle::State&) override {
        RCLCPP_INFO(get_logger(), "Configuring PQ Crypto");

        // Declare parameters
        declare_parameter("default_security_level", 3);
        declare_parameter("key_rotation_hours", 24);

        security_level_ = static_cast<SecurityLevel>(
            get_parameter("default_security_level").as_int()
        );

        // Publishers
        key_event_pub_ = create_publisher<std_msgs::msg::String>("pq_key_events", 10);

        // Services
        gen_kem_key_srv_ = create_service<std_srvs::srv::Trigger>(
            "generate_kem_keypair",
            std::bind(&PQCryptoNode::handle_gen_kem_key, this,
                      std::placeholders::_1, std::placeholders::_2)
        );

        gen_sig_key_srv_ = create_service<std_srvs::srv::Trigger>(
            "generate_signature_keypair",
            std::bind(&PQCryptoNode::handle_gen_sig_key, this,
                      std::placeholders::_1, std::placeholders::_2)
        );

        encapsulate_srv_ = create_service<std_srvs::srv::Trigger>(
            "encapsulate",
            std::bind(&PQCryptoNode::handle_encapsulate, this,
                      std::placeholders::_1, std::placeholders::_2)
        );

        sign_srv_ = create_service<std_srvs::srv::Trigger>(
            "sign",
            std::bind(&PQCryptoNode::handle_sign, this,
                      std::placeholders::_1, std::placeholders::_2)
        );

        status_srv_ = create_service<std_srvs::srv::Trigger>(
            "crypto_status",
            std::bind(&PQCryptoNode::handle_status, this,
                      std::placeholders::_1, std::placeholders::_2)
        );

        return rclcpp_lifecycle::node_interfaces::LifecycleNodeInterface::CallbackReturn::SUCCESS;
    }

    rclcpp_lifecycle::node_interfaces::LifecycleNodeInterface::CallbackReturn
    on_activate(const rclcpp_lifecycle::State&) override {
        RCLCPP_INFO(get_logger(), "Activating PQ Crypto");

        key_event_pub_->on_activate();

        // Generate initial keys
        generate_default_keys();

        // Start key rotation timer
        rotation_timer_ = create_wall_timer(
            1h, std::bind(&PQCryptoNode::check_key_rotation, this)
        );

        return rclcpp_lifecycle::node_interfaces::LifecycleNodeInterface::CallbackReturn::SUCCESS;
    }

    rclcpp_lifecycle::node_interfaces::LifecycleNodeInterface::CallbackReturn
    on_deactivate(const rclcpp_lifecycle::State&) override {
        RCLCPP_INFO(get_logger(), "Deactivating PQ Crypto");

        rotation_timer_.reset();
        key_event_pub_->on_deactivate();

        return rclcpp_lifecycle::node_interfaces::LifecycleNodeInterface::CallbackReturn::SUCCESS;
    }

    rclcpp_lifecycle::node_interfaces::LifecycleNodeInterface::CallbackReturn
    on_cleanup(const rclcpp_lifecycle::State&) override {
        RCLCPP_INFO(get_logger(), "Cleaning up PQ Crypto");

        std::lock_guard<std::mutex> lock(keys_mutex_);
        kem_keys_.clear();
        sig_keys_.clear();

        return rclcpp_lifecycle::node_interfaces::LifecycleNodeInterface::CallbackReturn::SUCCESS;
    }

    rclcpp_lifecycle::node_interfaces::LifecycleNodeInterface::CallbackReturn
    on_shutdown(const rclcpp_lifecycle::State&) override {
        RCLCPP_INFO(get_logger(), "Shutting down PQ Crypto");
        return rclcpp_lifecycle::node_interfaces::LifecycleNodeInterface::CallbackReturn::SUCCESS;
    }

private:
    void generate_default_keys() {
        std::lock_guard<std::mutex> lock(keys_mutex_);

        // Generate KEM key for secure key exchange
        auto kem_key = MLKEM::generate_keypair("kem-default", security_level_);
        kem_keys_[kem_key.key_id] = kem_key;
        current_kem_key_id_ = kem_key.key_id;

        // Generate Dilithium key for fast signatures
        auto dsa_key = MLDSA::generate_keypair("dsa-default", security_level_);
        sig_keys_[dsa_key.key_id] = dsa_key;
        current_sig_key_id_ = dsa_key.key_id;

        // Generate SPHINCS+ key for long-term signatures
        auto sphincs_key = SLHDSA::generate_keypair("sphincs-default", SecurityLevel::LEVEL_1);
        sig_keys_[sphincs_key.key_id] = sphincs_key;

        RCLCPP_INFO(get_logger(),
            "Generated default PQ keys: KEM=%s, DSA=%s, SPHINCS=%s",
            kem_key.key_id.c_str(), dsa_key.key_id.c_str(), sphincs_key.key_id.c_str());

        publish_key_event("KEY_GENERATED", "Default PQ keys generated");
    }

    void check_key_rotation() {
        std::lock_guard<std::mutex> lock(keys_mutex_);
        auto now = std::chrono::system_clock::now();

        for (auto& [id, key] : kem_keys_) {
            if (key.expires <= now) {
                RCLCPP_WARN(get_logger(), "KEM key %s expired, rotating", id.c_str());
                key.is_valid = false;
            }
        }

        for (auto& [id, key] : sig_keys_) {
            if (key.expires <= now) {
                RCLCPP_WARN(get_logger(), "Signature key %s expired, rotating", id.c_str());
                key.is_valid = false;
            }
        }
    }

    void handle_gen_kem_key(
        const std_srvs::srv::Trigger::Request::SharedPtr,
        std_srvs::srv::Trigger::Response::SharedPtr response
    ) {
        std::lock_guard<std::mutex> lock(keys_mutex_);

        std::string key_id = "kem-" + generate_uuid();
        auto key = MLKEM::generate_keypair(key_id, security_level_);
        kem_keys_[key_id] = key;
        current_kem_key_id_ = key_id;

        response->success = true;
        response->message = "Generated ML-KEM key: " + key_id +
                           " (pk_size=" + std::to_string(key.public_key.size()) + ")";

        publish_key_event("KEM_KEY_GENERATED", key_id);
    }

    void handle_gen_sig_key(
        const std_srvs::srv::Trigger::Request::SharedPtr,
        std_srvs::srv::Trigger::Response::SharedPtr response
    ) {
        std::lock_guard<std::mutex> lock(keys_mutex_);

        std::string key_id = "dsa-" + generate_uuid();
        auto key = MLDSA::generate_keypair(key_id, security_level_);
        sig_keys_[key_id] = key;
        current_sig_key_id_ = key_id;

        response->success = true;
        response->message = "Generated ML-DSA key: " + key_id +
                           " (pk_size=" + std::to_string(key.public_key.size()) + ")";

        publish_key_event("SIG_KEY_GENERATED", key_id);
    }

    void handle_encapsulate(
        const std_srvs::srv::Trigger::Request::SharedPtr,
        std_srvs::srv::Trigger::Response::SharedPtr response
    ) {
        std::lock_guard<std::mutex> lock(keys_mutex_);

        if (kem_keys_.empty() || current_kem_key_id_.empty()) {
            response->success = false;
            response->message = "No KEM key available";
            return;
        }

        auto& key = kem_keys_[current_kem_key_id_];
        auto result = MLKEM::encapsulate(key.public_key);

        response->success = true;
        response->message = "Encapsulation successful: ct_size=" +
                           std::to_string(result.ciphertext.size()) +
                           " ss_size=" + std::to_string(result.shared_secret.size());
    }

    void handle_sign(
        const std_srvs::srv::Trigger::Request::SharedPtr,
        std_srvs::srv::Trigger::Response::SharedPtr response
    ) {
        std::lock_guard<std::mutex> lock(keys_mutex_);

        if (sig_keys_.empty() || current_sig_key_id_.empty()) {
            response->success = false;
            response->message = "No signature key available";
            return;
        }

        auto& key = sig_keys_[current_sig_key_id_];

        // Sign a test message
        std::vector<uint8_t> message = {'t', 'e', 's', 't'};
        auto result = MLDSA::sign(key.private_key, message, key.key_id);

        response->success = true;
        response->message = "Signature generated: alg=" + result.algorithm +
                           " sig_size=" + std::to_string(result.signature.size());
    }

    void handle_status(
        const std_srvs::srv::Trigger::Request::SharedPtr,
        std_srvs::srv::Trigger::Response::SharedPtr response
    ) {
        std::lock_guard<std::mutex> lock(keys_mutex_);

        std::stringstream ss;
        ss << "Post-Quantum Crypto Status:\n";
        ss << "Security Level: " << static_cast<int>(security_level_) << "\n";
        ss << "KEM Keys: " << kem_keys_.size() << "\n";
        ss << "Signature Keys: " << sig_keys_.size() << "\n";
        ss << "Current KEM Key: " << current_kem_key_id_ << "\n";
        ss << "Current Sig Key: " << current_sig_key_id_ << "\n";
        ss << "\nAlgorithms:\n";
        ss << "  - ML-KEM-768 (Kyber): Key encapsulation\n";
        ss << "  - ML-DSA-65 (Dilithium): Fast signatures\n";
        ss << "  - SLH-DSA-128s (SPHINCS+): Long-term signatures\n";

        response->success = true;
        response->message = ss.str();
    }

    void publish_key_event(const std::string& event_type, const std::string& details) {
        auto msg = std_msgs::msg::String();
        msg.data = event_type + "|" + details + "|" +
                  std::to_string(std::chrono::system_clock::now().time_since_epoch().count());
        key_event_pub_->publish(msg);
    }

    std::string generate_uuid() {
        std::random_device rd;
        std::mt19937 gen(rd());
        std::uniform_int_distribution<> dis(0, 15);

        std::stringstream ss;
        for (int i = 0; i < 8; i++) {
            ss << std::hex << dis(gen);
        }
        return ss.str();
    }

    // Members
    SecurityLevel security_level_{SecurityLevel::LEVEL_3};
    std::mutex keys_mutex_;
    std::unordered_map<std::string, KeyPair> kem_keys_;
    std::unordered_map<std::string, KeyPair> sig_keys_;
    std::string current_kem_key_id_;
    std::string current_sig_key_id_;

    rclcpp_lifecycle::LifecyclePublisher<std_msgs::msg::String>::SharedPtr key_event_pub_;
    rclcpp::Service<std_srvs::srv::Trigger>::SharedPtr gen_kem_key_srv_;
    rclcpp::Service<std_srvs::srv::Trigger>::SharedPtr gen_sig_key_srv_;
    rclcpp::Service<std_srvs::srv::Trigger>::SharedPtr encapsulate_srv_;
    rclcpp::Service<std_srvs::srv::Trigger>::SharedPtr sign_srv_;
    rclcpp::Service<std_srvs::srv::Trigger>::SharedPtr status_srv_;
    rclcpp::TimerBase::SharedPtr rotation_timer_;
};

}  // namespace lego_mcp

int main(int argc, char** argv) {
    rclcpp::init(argc, argv);

    auto node = std::make_shared<lego_mcp::PQCryptoNode>();

    rclcpp::executors::SingleThreadedExecutor executor;
    executor.add_node(node->get_node_base_interface());
    executor.spin();

    rclcpp::shutdown();
    return 0;
}
