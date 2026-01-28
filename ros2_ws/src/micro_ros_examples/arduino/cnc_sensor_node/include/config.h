/**
 * micro-ROS Configuration
 * =======================
 * Edit this file to configure your micro-ROS setup.
 *
 * IMPORTANT: This file contains sensitive credentials.
 * Add to .gitignore if pushing to public repository!
 */

#ifndef CONFIG_H
#define CONFIG_H

// ============================================================================
// WiFi Configuration
// ============================================================================
#define WIFI_SSID     "ISECapstone"
#define WIFI_PASSWORD "j0shf1sh"

// ============================================================================
// micro-ROS Agent Configuration
// ============================================================================
// For WiFi: Use your Mac's IP address on the same network
// Find it with: ifconfig | grep "inet " | grep -v 127.0.0.1
#define AGENT_IP      "192.168.1.100"  // UPDATE THIS to your Mac's IP!

// Transport ports (must match docker-compose)
#define AGENT_PORT_UDP  8888
#define AGENT_PORT_TCP  8889

// ============================================================================
// Node Configuration
// ============================================================================
#define NODE_NAME       "cnc_sensor_node"
#define SENSOR_ID       "esp32s3_imu_001"
#define PUBLISH_RATE_HZ 50

// ============================================================================
// Hardware Configuration (ESP32-S3)
// ============================================================================
#define LED_PIN         48    // ESP32-S3 DevKitC built-in LED (or 2 for other boards)
#define I2C_SDA         8     // ESP32-S3 default I2C SDA
#define I2C_SCL         9     // ESP32-S3 default I2C SCL

// ============================================================================
// Transport Selection (set via platformio.ini build_flags)
// ============================================================================
// These are set automatically by the build environment:
// - TRANSPORT_SERIAL   : USB Serial transport
// - TRANSPORT_WIFI_UDP : WiFi with UDP transport
// - TRANSPORT_WIFI_TCP : WiFi with TCP transport

// ============================================================================
// Sensor Configuration
// ============================================================================
// Set to false to use real MPU6050 sensor
#define USE_SIMULATED_SENSOR true

// MPU6050 I2C address (0x68 or 0x69 if AD0 is high)
#define MPU6050_ADDR 0x68

// ============================================================================
// Edge Robustness Configuration
// ============================================================================

// WiFi reconnect settings
#define WIFI_RECONNECT_INITIAL_MS   1000    // Initial retry delay
#define WIFI_RECONNECT_MAX_MS       60000   // Max retry delay (exponential backoff cap)
#define WIFI_RECONNECT_MULTIPLIER   2       // Backoff multiplier
#define WIFI_CONNECT_TIMEOUT_MS     10000   // Connection attempt timeout

// Agent heartbeat settings
#define AGENT_HEARTBEAT_INTERVAL_MS 5000    // How often to ping agent
#define AGENT_PING_TIMEOUT_MS       100     // Timeout for ping response
#define AGENT_PING_ATTEMPTS         1       // Number of ping attempts

// Watchdog settings
#define ENABLE_WATCHDOG             true    // Enable hardware watchdog
#define WATCHDOG_TIMEOUT_SEC        30      // Watchdog timeout

// Payload throttling (reduce bandwidth if needed)
#define ENABLE_THROTTLING           false   // Enable payload throttling
#define THROTTLE_SKIP_COUNT         2       // Publish every Nth reading when throttled

// Status LED patterns (ms)
#define LED_WIFI_CONNECTING         250     // Fast blink: connecting to WiFi
#define LED_AGENT_WAITING           500     // Medium blink: waiting for agent
#define LED_CONNECTED               1000    // Slow blink: connected and publishing
#define LED_ERROR                   100     // Very fast blink: error state

#endif // CONFIG_H
