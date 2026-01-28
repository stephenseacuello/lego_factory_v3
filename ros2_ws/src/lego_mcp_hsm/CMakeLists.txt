cmake_minimum_required(VERSION 3.8)
project(lego_mcp_hsm)

if(NOT CMAKE_CXX_STANDARD)
  set(CMAKE_CXX_STANDARD 17)
endif()

find_package(ament_cmake REQUIRED)
find_package(rclcpp REQUIRED)
find_package(rclcpp_lifecycle REQUIRED)
find_package(std_msgs REQUIRED)
find_package(std_srvs REQUIRED)

add_executable(hsm_node src/hsm_node.cpp)
ament_target_dependencies(hsm_node rclcpp rclcpp_lifecycle std_msgs std_srvs)

install(TARGETS hsm_node DESTINATION lib/${PROJECT_NAME})
install(DIRECTORY config/ DESTINATION share/${PROJECT_NAME}/config)

ament_package()
