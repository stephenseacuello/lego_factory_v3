/**
 * @file main.cpp
 * @brief Main entry point for safety node
 */

#include <rclcpp/rclcpp.hpp>

int main(int argc, char* argv[]) {
    rclcpp::init(argc, argv);
    rclcpp::spin(std::make_shared<rclcpp::Node>("safety_node"));
    rclcpp::shutdown();
    return 0;
}
