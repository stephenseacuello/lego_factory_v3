/**
 * @file main_lifecycle.cpp
 * @brief Main entry point for safety lifecycle node
 */

#include <rclcpp/rclcpp.hpp>

int main(int argc, char* argv[]) {
    rclcpp::init(argc, argv);
    // Safety lifecycle node to be implemented
    rclcpp::spin(std::make_shared<rclcpp::Node>("safety_lifecycle_node"));
    rclcpp::shutdown();
    return 0;
}
