/**
 * LEGO MCP Alvik AGV Firmware
 *
 * Micro-ROS firmware for Arduino Alvik with ESP32-S3.
 * Publishes sensor data and subscribes to velocity commands.
 *
 * Topics Published:
 * - /alvik_XX/odom (nav_msgs/Odometry)
 * - /alvik_XX/imu (sensor_msgs/Imu)
 * - /alvik_XX/tof_front (sensor_msgs/Range)
 * - /alvik_XX/tof_left (sensor_msgs/Range)
 * - /alvik_XX/tof_right (sensor_msgs/Range)
 * - /alvik_XX/battery (sensor_msgs/BatteryState)
 *
 * Topics Subscribed:
 * - /alvik_XX/cmd_vel (geometry_msgs/Twist)
 * - /alvik_XX/led_cmd (std_msgs/ColorRGBA)
 *
 * LEGO MCP Manufacturing System v7.0
 */

#include <Arduino.h>
#include <WiFi.h>
#include <micro_ros_platformio.h>

#include <rcl/rcl.h>
#include <rclc/rclc.h>
#include <rclc/executor.h>

// Message types
#include <nav_msgs/msg/odometry.h>
#include <sensor_msgs/msg/imu.h>
#include <sensor_msgs/msg/range.h>
#include <sensor_msgs/msg/battery_state.h>
#include <geometry_msgs/msg/twist.h>
#include <std_msgs/msg/color_rgba.h>

// Alvik library (if using official Arduino Alvik)
// #include <Arduino_Alvik.h>

// Configuration
#define AGENT_ID "alvik_01"
#define WIFI_SSID "LEGO_MCP_Factory"
#define WIFI_PASSWORD "factory_password"
#define AGENT_IP "192.168.1.100"
#define AGENT_PORT 8888

// Hardware pins (adjust for your setup)
#define MOTOR_LEFT_PWM 5
#define MOTOR_LEFT_DIR 6
#define MOTOR_RIGHT_PWM 7
#define MOTOR_RIGHT_DIR 8
#define ENCODER_LEFT_A 9
#define ENCODER_LEFT_B 10
#define ENCODER_RIGHT_A 11
#define ENCODER_RIGHT_B 12
#define TOF_FRONT_PIN 13
#define TOF_LEFT_PIN 14
#define TOF_RIGHT_PIN 15
#define LED_R_PIN 16
#define LED_G_PIN 17
#define LED_B_PIN 18

// Robot parameters
#define WHEEL_RADIUS 0.017  // meters
#define WHEEL_BASE 0.098    // meters
#define ENCODER_CPR 1440    // counts per revolution
#define MAX_LINEAR_VEL 0.3  // m/s
#define MAX_ANGULAR_VEL 1.5 // rad/s

// micro-ROS entities
rcl_allocator_t allocator;
rclc_support_t support;
rcl_node_t node;
rclc_executor_t executor;

// Publishers
rcl_publisher_t odom_pub;
rcl_publisher_t imu_pub;
rcl_publisher_t tof_front_pub;
rcl_publisher_t tof_left_pub;
rcl_publisher_t tof_right_pub;
rcl_publisher_t battery_pub;

// Subscribers
rcl_subscription_t cmd_vel_sub;
rcl_subscription_t led_sub;

// Messages
nav_msgs__msg__Odometry odom_msg;
sensor_msgs__msg__Imu imu_msg;
sensor_msgs__msg__Range tof_front_msg;
sensor_msgs__msg__Range tof_left_msg;
sensor_msgs__msg__Range tof_right_msg;
sensor_msgs__msg__BatteryState battery_msg;
geometry_msgs__msg__Twist cmd_vel_msg;
std_msgs__msg__ColorRGBA led_msg;

// Timer
rcl_timer_t timer;

// State variables
volatile long encoder_left_count = 0;
volatile long encoder_right_count = 0;
float pose_x = 0.0;
float pose_y = 0.0;
float pose_theta = 0.0;
float target_linear_vel = 0.0;
float target_angular_vel = 0.0;

// Encoder ISRs
void IRAM_ATTR encoder_left_isr() {
    if (digitalRead(ENCODER_LEFT_B)) {
        encoder_left_count++;
    } else {
        encoder_left_count--;
    }
}

void IRAM_ATTR encoder_right_isr() {
    if (digitalRead(ENCODER_RIGHT_B)) {
        encoder_right_count++;
    } else {
        encoder_right_count--;
    }
}

// Callback for cmd_vel subscriber
void cmd_vel_callback(const void* msgin) {
    const geometry_msgs__msg__Twist* msg = (const geometry_msgs__msg__Twist*)msgin;
    target_linear_vel = constrain(msg->linear.x, -MAX_LINEAR_VEL, MAX_LINEAR_VEL);
    target_angular_vel = constrain(msg->angular.z, -MAX_ANGULAR_VEL, MAX_ANGULAR_VEL);
}

// Callback for LED subscriber
void led_callback(const void* msgin) {
    const std_msgs__msg__ColorRGBA* msg = (const std_msgs__msg__ColorRGBA*)msgin;
    analogWrite(LED_R_PIN, (int)(msg->r * 255));
    analogWrite(LED_G_PIN, (int)(msg->g * 255));
    analogWrite(LED_B_PIN, (int)(msg->b * 255));
}

// Timer callback - runs at 50Hz
void timer_callback(rcl_timer_t* timer, int64_t last_call_time) {
    RCLC_UNUSED(last_call_time);

    if (timer != NULL) {
        // Calculate dt
        static unsigned long last_time = 0;
        unsigned long current_time = millis();
        float dt = (current_time - last_time) / 1000.0;
        last_time = current_time;

        // Read encoder counts
        long left_count = encoder_left_count;
        long right_count = encoder_right_count;
        static long last_left_count = 0;
        static long last_right_count = 0;

        // Calculate wheel displacements
        float left_dist = (left_count - last_left_count) * (2 * M_PI * WHEEL_RADIUS / ENCODER_CPR);
        float right_dist = (right_count - last_right_count) * (2 * M_PI * WHEEL_RADIUS / ENCODER_CPR);
        last_left_count = left_count;
        last_right_count = right_count;

        // Differential drive odometry
        float d = (left_dist + right_dist) / 2.0;
        float dtheta = (right_dist - left_dist) / WHEEL_BASE;

        pose_x += d * cos(pose_theta + dtheta / 2.0);
        pose_y += d * sin(pose_theta + dtheta / 2.0);
        pose_theta += dtheta;

        // Normalize theta
        while (pose_theta > M_PI) pose_theta -= 2 * M_PI;
        while (pose_theta < -M_PI) pose_theta += 2 * M_PI;

        // Calculate velocities
        float linear_vel = d / dt;
        float angular_vel = dtheta / dt;

        // Publish odometry
        odom_msg.pose.pose.position.x = pose_x;
        odom_msg.pose.pose.position.y = pose_y;
        odom_msg.pose.pose.position.z = 0.0;

        // Quaternion from yaw
        odom_msg.pose.pose.orientation.w = cos(pose_theta / 2.0);
        odom_msg.pose.pose.orientation.x = 0.0;
        odom_msg.pose.pose.orientation.y = 0.0;
        odom_msg.pose.pose.orientation.z = sin(pose_theta / 2.0);

        odom_msg.twist.twist.linear.x = linear_vel;
        odom_msg.twist.twist.angular.z = angular_vel;

        rcl_publish(&odom_pub, &odom_msg, NULL);

        // Read and publish ToF sensors
        // (Using placeholder values - replace with actual sensor reads)
        tof_front_msg.range = 1.0;  // TODO: Read actual sensor
        tof_left_msg.range = 1.0;
        tof_right_msg.range = 1.0;

        rcl_publish(&tof_front_pub, &tof_front_msg, NULL);
        rcl_publish(&tof_left_pub, &tof_left_msg, NULL);
        rcl_publish(&tof_right_pub, &tof_right_msg, NULL);

        // Read and publish battery
        // (Using placeholder - replace with actual battery reading)
        battery_msg.voltage = 3.7;
        battery_msg.percentage = 0.85;

        rcl_publish(&battery_pub, &battery_msg, NULL);

        // Apply motor control
        apply_motor_control(target_linear_vel, target_angular_vel);
    }
}

void apply_motor_control(float linear, float angular) {
    // Convert to wheel velocities
    float left_vel = linear - (angular * WHEEL_BASE / 2.0);
    float right_vel = linear + (angular * WHEEL_BASE / 2.0);

    // Convert to PWM (0-255)
    int left_pwm = (int)(abs(left_vel) / MAX_LINEAR_VEL * 255);
    int right_pwm = (int)(abs(right_vel) / MAX_LINEAR_VEL * 255);

    left_pwm = constrain(left_pwm, 0, 255);
    right_pwm = constrain(right_pwm, 0, 255);

    // Set direction
    digitalWrite(MOTOR_LEFT_DIR, left_vel >= 0 ? HIGH : LOW);
    digitalWrite(MOTOR_RIGHT_DIR, right_vel >= 0 ? HIGH : LOW);

    // Set speed
    analogWrite(MOTOR_LEFT_PWM, left_pwm);
    analogWrite(MOTOR_RIGHT_PWM, right_pwm);
}

bool create_entities() {
    allocator = rcl_get_default_allocator();

    // Create init options
    rcl_init_options_t init_options = rcl_get_zero_initialized_init_options();
    rcl_init_options_init(&init_options, allocator);

    // Create support
    rclc_support_init_with_options(&support, 0, NULL, &init_options, &allocator);

    // Create node
    char node_name[32];
    snprintf(node_name, sizeof(node_name), "alvik_driver_%s", AGENT_ID);
    rclc_node_init_default(&node, node_name, "", &support);

    // Create publishers
    char topic_name[64];

    snprintf(topic_name, sizeof(topic_name), "/%s/odom", AGENT_ID);
    rclc_publisher_init_default(&odom_pub, &node,
        ROSIDL_GET_MSG_TYPE_SUPPORT(nav_msgs, msg, Odometry), topic_name);

    snprintf(topic_name, sizeof(topic_name), "/%s/imu", AGENT_ID);
    rclc_publisher_init_default(&imu_pub, &node,
        ROSIDL_GET_MSG_TYPE_SUPPORT(sensor_msgs, msg, Imu), topic_name);

    snprintf(topic_name, sizeof(topic_name), "/%s/tof_front", AGENT_ID);
    rclc_publisher_init_default(&tof_front_pub, &node,
        ROSIDL_GET_MSG_TYPE_SUPPORT(sensor_msgs, msg, Range), topic_name);

    snprintf(topic_name, sizeof(topic_name), "/%s/tof_left", AGENT_ID);
    rclc_publisher_init_default(&tof_left_pub, &node,
        ROSIDL_GET_MSG_TYPE_SUPPORT(sensor_msgs, msg, Range), topic_name);

    snprintf(topic_name, sizeof(topic_name), "/%s/tof_right", AGENT_ID);
    rclc_publisher_init_default(&tof_right_pub, &node,
        ROSIDL_GET_MSG_TYPE_SUPPORT(sensor_msgs, msg, Range), topic_name);

    snprintf(topic_name, sizeof(topic_name), "/%s/battery", AGENT_ID);
    rclc_publisher_init_default(&battery_pub, &node,
        ROSIDL_GET_MSG_TYPE_SUPPORT(sensor_msgs, msg, BatteryState), topic_name);

    // Create subscribers
    snprintf(topic_name, sizeof(topic_name), "/%s/cmd_vel", AGENT_ID);
    rclc_subscription_init_default(&cmd_vel_sub, &node,
        ROSIDL_GET_MSG_TYPE_SUPPORT(geometry_msgs, msg, Twist), topic_name);

    snprintf(topic_name, sizeof(topic_name), "/%s/led_cmd", AGENT_ID);
    rclc_subscription_init_default(&led_sub, &node,
        ROSIDL_GET_MSG_TYPE_SUPPORT(std_msgs, msg, ColorRGBA), topic_name);

    // Create timer (50Hz)
    rclc_timer_init_default(&timer, &support, RCL_MS_TO_NS(20), timer_callback);

    // Create executor
    rclc_executor_init(&executor, &support.context, 4, &allocator);
    rclc_executor_add_subscription(&executor, &cmd_vel_sub, &cmd_vel_msg,
        &cmd_vel_callback, ON_NEW_DATA);
    rclc_executor_add_subscription(&executor, &led_sub, &led_msg,
        &led_callback, ON_NEW_DATA);
    rclc_executor_add_timer(&executor, &timer);

    return true;
}

void destroy_entities() {
    rcl_publisher_fini(&odom_pub, &node);
    rcl_publisher_fini(&imu_pub, &node);
    rcl_publisher_fini(&tof_front_pub, &node);
    rcl_publisher_fini(&tof_left_pub, &node);
    rcl_publisher_fini(&tof_right_pub, &node);
    rcl_publisher_fini(&battery_pub, &node);
    rcl_subscription_fini(&cmd_vel_sub, &node);
    rcl_subscription_fini(&led_sub, &node);
    rcl_timer_fini(&timer);
    rclc_executor_fini(&executor);
    rcl_node_fini(&node);
    rclc_support_fini(&support);
}

void setup() {
    Serial.begin(115200);
    delay(2000);

    Serial.println("LEGO MCP Alvik AGV Firmware");
    Serial.println("Connecting to WiFi...");

    // Initialize pins
    pinMode(MOTOR_LEFT_PWM, OUTPUT);
    pinMode(MOTOR_LEFT_DIR, OUTPUT);
    pinMode(MOTOR_RIGHT_PWM, OUTPUT);
    pinMode(MOTOR_RIGHT_DIR, OUTPUT);
    pinMode(ENCODER_LEFT_A, INPUT_PULLUP);
    pinMode(ENCODER_LEFT_B, INPUT_PULLUP);
    pinMode(ENCODER_RIGHT_A, INPUT_PULLUP);
    pinMode(ENCODER_RIGHT_B, INPUT_PULLUP);
    pinMode(LED_R_PIN, OUTPUT);
    pinMode(LED_G_PIN, OUTPUT);
    pinMode(LED_B_PIN, OUTPUT);

    // Setup encoder interrupts
    attachInterrupt(digitalPinToInterrupt(ENCODER_LEFT_A), encoder_left_isr, RISING);
    attachInterrupt(digitalPinToInterrupt(ENCODER_RIGHT_A), encoder_right_isr, RISING);

    // Initialize messages
    odom_msg.header.frame_id.data = (char*)AGENT_ID "/odom";
    odom_msg.child_frame_id.data = (char*)AGENT_ID "/base_link";

    tof_front_msg.radiation_type = sensor_msgs__msg__Range__INFRARED;
    tof_front_msg.field_of_view = 0.44;
    tof_front_msg.min_range = 0.02;
    tof_front_msg.max_range = 2.0;

    tof_left_msg.radiation_type = sensor_msgs__msg__Range__INFRARED;
    tof_left_msg.field_of_view = 0.44;
    tof_left_msg.min_range = 0.02;
    tof_left_msg.max_range = 2.0;

    tof_right_msg.radiation_type = sensor_msgs__msg__Range__INFRARED;
    tof_right_msg.field_of_view = 0.44;
    tof_right_msg.min_range = 0.02;
    tof_right_msg.max_range = 2.0;

    // Connect to WiFi
    WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
    while (WiFi.status() != WL_CONNECTED) {
        delay(500);
        Serial.print(".");
    }
    Serial.println("\nWiFi connected!");
    Serial.print("IP: ");
    Serial.println(WiFi.localIP());

    // Set micro-ROS transport
    IPAddress agent_ip;
    agent_ip.fromString(AGENT_IP);
    set_microros_wifi_transports(WIFI_SSID, WIFI_PASSWORD,
        agent_ip, AGENT_PORT);

    // Wait for agent
    Serial.println("Connecting to micro-ROS agent...");

    // Create micro-ROS entities
    if (create_entities()) {
        Serial.println("micro-ROS entities created!");
        // Green LED = connected
        analogWrite(LED_G_PIN, 255);
    } else {
        Serial.println("Failed to create entities!");
        // Red LED = error
        analogWrite(LED_R_PIN, 255);
    }
}

void loop() {
    // Spin executor
    rclc_executor_spin_some(&executor, RCL_MS_TO_NS(10));

    // Reconnect if needed
    if (WiFi.status() != WL_CONNECTED) {
        Serial.println("WiFi disconnected, reconnecting...");
        WiFi.reconnect();
        delay(1000);
    }
}
