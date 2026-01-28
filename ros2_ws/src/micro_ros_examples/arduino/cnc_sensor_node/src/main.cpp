/**
 * CNC Sensor Node - micro-ROS on ESP32-S3
 * =======================================
 * Multi-transport support: Serial, WiFi/UDP, WiFi/TCP
 *
 * Enhanced with Edge Robustness Features:
 * - WiFi reconnect with exponential backoff
 * - Agent heartbeat monitoring
 * - Hardware watchdog support
 * - Payload throttling option
 * - Status LED patterns
 *
 * Hardware:
 * - ESP32-S3 DevKitC
 * - MPU6050 IMU (optional - can simulate data)
 *
 * Topics Published:
 * - /sensors/imu (sensor_msgs/Imu)
 * - /sensors/temperature (std_msgs/Float32)
 *
 * Build with PlatformIO:
 *   pio run -e esp32s3_serial     # USB Serial transport
 *   pio run -e esp32s3_wifi_udp   # WiFi UDP transport
 *   pio run -e esp32s3_wifi_tcp   # WiFi TCP transport
 */

#include <Arduino.h>
#include <micro_ros_arduino.h>
#include "config.h"

#include <stdio.h>
#include <rcl/rcl.h>
#include <rcl/error_handling.h>
#include <rclc/rclc.h>
#include <rclc/executor.h>

#include <sensor_msgs/msg/imu.h>
#include <std_msgs/msg/float32.h>

#if defined(TRANSPORT_WIFI_UDP) || defined(TRANSPORT_WIFI_TCP)
#include <WiFi.h>
#endif

#if ENABLE_WATCHDOG
#include <esp_task_wdt.h>
#endif

// ============================================================================
// Global variables
// ============================================================================

rcl_publisher_t imu_publisher;
rcl_publisher_t temp_publisher;
sensor_msgs__msg__Imu imu_msg;
std_msgs__msg__Float32 temp_msg;

rclc_executor_t executor;
rclc_support_t support;
rcl_allocator_t allocator;
rcl_node_t node;
rcl_timer_t timer;

// Connection state
enum AgentState {
    WIFI_CONNECTING,
    WAITING_AGENT,
    AGENT_AVAILABLE,
    AGENT_CONNECTED,
    AGENT_DISCONNECTED,
    WIFI_DISCONNECTED
};
AgentState agent_state = WAITING_AGENT;
const char* agent_state_names[] = {
    "WIFI_CONNECTING", "WAITING_AGENT", "AGENT_AVAILABLE",
    "AGENT_CONNECTED", "AGENT_DISCONNECTED", "WIFI_DISCONNECTED"
};

// Timing
unsigned long last_heartbeat = 0;
unsigned long last_state_change = 0;
unsigned long wifi_retry_delay = WIFI_RECONNECT_INITIAL_MS;

// Throttling
uint32_t publish_counter = 0;

// Simulated sensor state
float sim_angle = 0.0;
float sim_vibration = 0.0;

// Statistics
uint32_t messages_published = 0;
uint32_t reconnect_count = 0;
uint32_t wifi_reconnect_count = 0;

// ============================================================================
// Error handling
// ============================================================================

#define RCCHECK(fn) { rcl_ret_t temp_rc = fn; if((temp_rc != RCL_RET_OK)){error_loop();}}
#define RCSOFTCHECK(fn) { rcl_ret_t temp_rc = fn; if((temp_rc != RCL_RET_OK)){}}

void error_loop() {
    Serial.println("ERROR: Entering error loop!");
    while(1) {
        digitalWrite(LED_PIN, !digitalRead(LED_PIN));
        delay(LED_ERROR);
#if ENABLE_WATCHDOG
        esp_task_wdt_reset();  // Keep feeding watchdog to allow recovery
#endif
    }
}

// ============================================================================
// LED Status Indicator
// ============================================================================

void update_led_status() {
    unsigned long now = millis();
    int blink_period;

    switch(agent_state) {
        case WIFI_CONNECTING:
        case WIFI_DISCONNECTED:
            blink_period = LED_WIFI_CONNECTING;
            break;
        case WAITING_AGENT:
        case AGENT_AVAILABLE:
            blink_period = LED_AGENT_WAITING;
            break;
        case AGENT_CONNECTED:
            blink_period = LED_CONNECTED;
            break;
        case AGENT_DISCONNECTED:
            blink_period = LED_AGENT_WAITING;
            break;
        default:
            blink_period = LED_ERROR;
    }

    digitalWrite(LED_PIN, (now / blink_period) % 2);
}

// ============================================================================
// WiFi Management (for WiFi transports)
// ============================================================================

#if defined(TRANSPORT_WIFI_UDP) || defined(TRANSPORT_WIFI_TCP)

bool connect_wifi() {
    if (WiFi.status() == WL_CONNECTED) {
        return true;
    }

    Serial.printf("[WiFi] Connecting to %s...\n", WIFI_SSID);
    agent_state = WIFI_CONNECTING;

    WiFi.disconnect(true);
    delay(100);
    WiFi.mode(WIFI_STA);
    WiFi.begin(WIFI_SSID, WIFI_PASSWORD);

    unsigned long start = millis();
    while (WiFi.status() != WL_CONNECTED) {
        if (millis() - start > WIFI_CONNECT_TIMEOUT_MS) {
            Serial.printf("[WiFi] Connection timeout after %dms\n", WIFI_CONNECT_TIMEOUT_MS);
            return false;
        }
        update_led_status();
        delay(100);
#if ENABLE_WATCHDOG
        esp_task_wdt_reset();
#endif
    }

    Serial.printf("[WiFi] Connected! IP: %s\n", WiFi.localIP().toString().c_str());
    Serial.printf("[WiFi] RSSI: %d dBm\n", WiFi.RSSI());
    wifi_retry_delay = WIFI_RECONNECT_INITIAL_MS;  // Reset backoff on success
    return true;
}

bool check_wifi_connection() {
    if (WiFi.status() == WL_CONNECTED) {
        return true;
    }

    Serial.printf("[WiFi] Connection lost! Reconnecting (attempt delay: %lums)...\n", wifi_retry_delay);
    wifi_reconnect_count++;

    // Apply exponential backoff
    delay(wifi_retry_delay);
    wifi_retry_delay = min(wifi_retry_delay * WIFI_RECONNECT_MULTIPLIER,
                          (unsigned long)WIFI_RECONNECT_MAX_MS);

    if (connect_wifi()) {
        Serial.println("[WiFi] Reconnected successfully!");
        return true;
    }

    return false;
}

#endif

// ============================================================================
// Transport setup (compile-time selection)
// ============================================================================

bool setup_transport() {
#if defined(TRANSPORT_SERIAL)
    // Serial transport - ESP32-S3 native USB
    Serial.begin(115200);
    set_microros_serial_transports(Serial);
    Serial.println("[Transport] Serial (USB)");
    return true;

#elif defined(TRANSPORT_WIFI_UDP)
    // WiFi UDP transport
    Serial.begin(115200);
    Serial.println("[Transport] WiFi UDP");

    if (!connect_wifi()) {
        return false;
    }

    set_microros_wifi_transports(
        (char*)WIFI_SSID,
        (char*)WIFI_PASSWORD,
        (char*)AGENT_IP,
        AGENT_PORT_UDP
    );
    Serial.printf("[Transport] Agent: %s:%d (UDP)\n", AGENT_IP, AGENT_PORT_UDP);
    return true;

#elif defined(TRANSPORT_WIFI_TCP)
    // WiFi TCP transport
    Serial.begin(115200);
    Serial.println("[Transport] WiFi TCP");

    if (!connect_wifi()) {
        return false;
    }

    set_microros_wifi_transports(
        (char*)WIFI_SSID,
        (char*)WIFI_PASSWORD,
        (char*)AGENT_IP,
        AGENT_PORT_TCP
    );
    Serial.printf("[Transport] Agent: %s:%d (TCP)\n", AGENT_IP, AGENT_PORT_TCP);
    return true;

#else
    // Default: Serial transport
    Serial.begin(115200);
    set_microros_serial_transports(Serial);
    Serial.println("[Transport] Serial (default)");
    return true;
#endif
}

// ============================================================================
// Sensor reading (simulated or real)
// ============================================================================

void read_sensor_data(float* ax, float* ay, float* az,
                      float* gx, float* gy, float* gz,
                      float* temp) {
#if USE_SIMULATED_SENSOR
    // Simulate accelerometer data with vibration pattern
    sim_angle += 0.1;
    sim_vibration = sin(sim_angle * 10) * 0.5;

    // Accelerometer (m/s^2) - gravity + vibration
    *ax = sim_vibration * 0.2;
    *ay = sim_vibration * 0.15;
    *az = 9.81 + sim_vibration * 0.1;

    // Gyroscope (rad/s)
    *gx = sim_vibration * 0.01;
    *gy = sim_vibration * 0.01;
    *gz = sim_vibration * 0.005;

    // Temperature (Celsius)
    *temp = 25.0 + sin(sim_angle * 0.1) * 2.0;
#else
    // TODO: Read from real MPU6050
    *ax = 0; *ay = 0; *az = 9.81;
    *gx = 0; *gy = 0; *gz = 0;
    *temp = 25.0;
#endif
}

// ============================================================================
// Timer callback - publishes sensor data
// ============================================================================

void timer_callback(rcl_timer_t* timer, int64_t last_call_time) {
    RCLC_UNUSED(last_call_time);
    if (timer != NULL) {
        publish_counter++;

#if ENABLE_THROTTLING
        // Skip publishing if throttling is enabled
        if (publish_counter % THROTTLE_SKIP_COUNT != 0) {
            return;
        }
#endif

        float ax, ay, az, gx, gy, gz, temp;
        read_sensor_data(&ax, &ay, &az, &gx, &gy, &gz, &temp);

        // Fill IMU message
        imu_msg.header.stamp.sec = millis() / 1000;
        imu_msg.header.stamp.nanosec = (millis() % 1000) * 1000000;

        // Orientation (quaternion) - identity
        imu_msg.orientation.x = 0.0;
        imu_msg.orientation.y = 0.0;
        imu_msg.orientation.z = 0.0;
        imu_msg.orientation.w = 1.0;
        imu_msg.orientation_covariance[0] = -1;

        // Angular velocity (rad/s)
        imu_msg.angular_velocity.x = gx;
        imu_msg.angular_velocity.y = gy;
        imu_msg.angular_velocity.z = gz;

        // Linear acceleration (m/s^2)
        imu_msg.linear_acceleration.x = ax;
        imu_msg.linear_acceleration.y = ay;
        imu_msg.linear_acceleration.z = az;

        // Temperature
        temp_msg.data = temp;

        // Publish
        RCSOFTCHECK(rcl_publish(&imu_publisher, &imu_msg, NULL));
        RCSOFTCHECK(rcl_publish(&temp_publisher, &temp_msg, NULL));

        messages_published++;
    }
}

// ============================================================================
// micro-ROS entity management
// ============================================================================

bool create_entities() {
    allocator = rcl_get_default_allocator();

    // Create init_options
    RCCHECK(rclc_support_init(&support, 0, NULL, &allocator));

    // Create node
    RCCHECK(rclc_node_init_default(&node, NODE_NAME, "", &support));

    // Create IMU publisher
    RCCHECK(rclc_publisher_init_default(
        &imu_publisher,
        &node,
        ROSIDL_GET_MSG_TYPE_SUPPORT(sensor_msgs, msg, Imu),
        "/sensors/imu"
    ));

    // Create temperature publisher
    RCCHECK(rclc_publisher_init_default(
        &temp_publisher,
        &node,
        ROSIDL_GET_MSG_TYPE_SUPPORT(std_msgs, msg, Float32),
        "/sensors/temperature"
    ));

    // Create timer
    const unsigned int timer_period_ms = 1000 / PUBLISH_RATE_HZ;
    RCCHECK(rclc_timer_init_default(
        &timer,
        &support,
        RCL_MS_TO_NS(timer_period_ms),
        timer_callback
    ));

    // Create executor
    RCCHECK(rclc_executor_init(&executor, &support.context, 1, &allocator));
    RCCHECK(rclc_executor_add_timer(&executor, &timer));

    // Initialize message frame_id
    static char frame_id[] = SENSOR_ID;
    imu_msg.header.frame_id.data = frame_id;
    imu_msg.header.frame_id.size = strlen(frame_id);
    imu_msg.header.frame_id.capacity = strlen(frame_id) + 1;

    return true;
}

void destroy_entities() {
    rmw_context_t* rmw_context = rcl_context_get_rmw_context(&support.context);
    (void) rmw_uros_set_context_entity_destroy_session_timeout(rmw_context, 0);

    rcl_publisher_fini(&imu_publisher, &node);
    rcl_publisher_fini(&temp_publisher, &node);
    rcl_timer_fini(&timer);
    rclc_executor_fini(&executor);
    rcl_node_fini(&node);
    rclc_support_fini(&support);
}

// ============================================================================
// Agent heartbeat check
// ============================================================================

bool check_agent_heartbeat() {
    if (millis() - last_heartbeat < AGENT_HEARTBEAT_INTERVAL_MS) {
        return true;  // Not time to check yet
    }

    last_heartbeat = millis();

    if (RMW_RET_OK == rmw_uros_ping_agent(AGENT_PING_TIMEOUT_MS, AGENT_PING_ATTEMPTS)) {
        return true;
    }

    Serial.println("[Heartbeat] Agent not responding!");
    return false;
}

// ============================================================================
// Print statistics
// ============================================================================

void print_statistics() {
    static unsigned long last_stats = 0;
    if (millis() - last_stats > 30000) {  // Every 30 seconds
        last_stats = millis();
        Serial.println("\n===== Statistics =====");
        Serial.printf("Messages published: %lu\n", messages_published);
        Serial.printf("Agent reconnects: %lu\n", reconnect_count);
#if defined(TRANSPORT_WIFI_UDP) || defined(TRANSPORT_WIFI_TCP)
        Serial.printf("WiFi reconnects: %lu\n", wifi_reconnect_count);
        Serial.printf("WiFi RSSI: %d dBm\n", WiFi.RSSI());
#endif
        Serial.printf("Uptime: %lu seconds\n", millis() / 1000);
        Serial.printf("State: %s\n", agent_state_names[agent_state]);
        Serial.println("======================\n");
    }
}

// ============================================================================
// Setup
// ============================================================================

void setup() {
    // LED setup
    pinMode(LED_PIN, OUTPUT);
    digitalWrite(LED_PIN, HIGH);

    // Serial for debug output
    Serial.begin(115200);
    delay(1000);  // Wait for serial monitor

    Serial.println("\n===================================");
    Serial.println("CNC Sensor Node - micro-ROS");
    Serial.println("With Edge Robustness Features");
    Serial.println("===================================");
    Serial.printf("Node: %s\n", NODE_NAME);
    Serial.printf("Sensor ID: %s\n", SENSOR_ID);
    Serial.printf("Publish Rate: %d Hz\n", PUBLISH_RATE_HZ);
    Serial.printf("Heartbeat Interval: %d ms\n", AGENT_HEARTBEAT_INTERVAL_MS);
#if ENABLE_WATCHDOG
    Serial.printf("Watchdog: Enabled (%d sec)\n", WATCHDOG_TIMEOUT_SEC);
#else
    Serial.println("Watchdog: Disabled");
#endif
#if ENABLE_THROTTLING
    Serial.printf("Throttling: Enabled (1/%d)\n", THROTTLE_SKIP_COUNT);
#else
    Serial.println("Throttling: Disabled");
#endif
    Serial.println("===================================");

#if ENABLE_WATCHDOG
    // Initialize watchdog
    esp_task_wdt_init(WATCHDOG_TIMEOUT_SEC, true);
    esp_task_wdt_add(NULL);  // Add current task to watchdog
    Serial.println("[Watchdog] Initialized");
#endif

    // Initialize transport
    if (!setup_transport()) {
        Serial.println("[ERROR] Transport setup failed!");
        agent_state = WIFI_DISCONNECTED;
    } else {
        agent_state = WAITING_AGENT;
    }

    Serial.println("[Setup] Complete. Waiting for agent...");
    last_state_change = millis();
}

// ============================================================================
// Loop - Connection state machine with robustness
// ============================================================================

void loop() {
#if ENABLE_WATCHDOG
    esp_task_wdt_reset();  // Feed watchdog
#endif

    update_led_status();
    print_statistics();

    switch (agent_state) {
#if defined(TRANSPORT_WIFI_UDP) || defined(TRANSPORT_WIFI_TCP)
        case WIFI_CONNECTING:
        case WIFI_DISCONNECTED:
            if (check_wifi_connection()) {
                agent_state = WAITING_AGENT;
                last_state_change = millis();
            }
            break;
#endif

        case WAITING_AGENT:
            // Try to ping the agent
            if (RMW_RET_OK == rmw_uros_ping_agent(AGENT_PING_TIMEOUT_MS, AGENT_PING_ATTEMPTS)) {
                agent_state = AGENT_AVAILABLE;
                last_state_change = millis();
            }
#if defined(TRANSPORT_WIFI_UDP) || defined(TRANSPORT_WIFI_TCP)
            // Check WiFi is still connected
            else if (WiFi.status() != WL_CONNECTED) {
                agent_state = WIFI_DISCONNECTED;
                last_state_change = millis();
            }
#endif
            break;

        case AGENT_AVAILABLE:
            Serial.println("[Agent] Found! Creating entities...");
            if (create_entities()) {
                agent_state = AGENT_CONNECTED;
                last_state_change = millis();
                last_heartbeat = millis();
                Serial.println("[Agent] Connected to micro-ROS agent!");
                Serial.printf("[Agent] Publishing to /sensors/imu at %d Hz\n", PUBLISH_RATE_HZ);
            } else {
                Serial.println("[Agent] Failed to create entities");
                agent_state = WAITING_AGENT;
                last_state_change = millis();
            }
            break;

        case AGENT_CONNECTED:
#if defined(TRANSPORT_WIFI_UDP) || defined(TRANSPORT_WIFI_TCP)
            // Check WiFi first
            if (WiFi.status() != WL_CONNECTED) {
                Serial.println("[WiFi] Connection lost during operation!");
                agent_state = AGENT_DISCONNECTED;
                last_state_change = millis();
                break;
            }
#endif
            // Normal operation - spin executor
            RCSOFTCHECK(rclc_executor_spin_some(&executor, RCL_MS_TO_NS(10)));

            // Periodic heartbeat check
            if (!check_agent_heartbeat()) {
                Serial.println("[Agent] Lost connection!");
                agent_state = AGENT_DISCONNECTED;
                last_state_change = millis();
            }
            break;

        case AGENT_DISCONNECTED:
            // Clean up and wait for agent
            Serial.println("[Agent] Disconnected. Cleaning up...");
            destroy_entities();
            reconnect_count++;

#if defined(TRANSPORT_WIFI_UDP) || defined(TRANSPORT_WIFI_TCP)
            // Check WiFi before waiting for agent
            if (WiFi.status() != WL_CONNECTED) {
                agent_state = WIFI_DISCONNECTED;
            } else {
                agent_state = WAITING_AGENT;
            }
#else
            agent_state = WAITING_AGENT;
#endif
            last_state_change = millis();
            Serial.println("[Agent] Waiting for reconnection...");
            break;

        default:
            agent_state = WAITING_AGENT;
            break;
    }

    delay(10);
}
