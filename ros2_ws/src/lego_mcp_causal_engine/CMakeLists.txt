cmake_minimum_required(VERSION 3.8)
project(lego_mcp_causal_engine)

if(NOT CMAKE_CXX_STANDARD)
  set(CMAKE_CXX_STANDARD 17)
endif()

find_package(ament_cmake REQUIRED)
find_package(rclcpp REQUIRED)
find_package(rclcpp_lifecycle REQUIRED)
find_package(std_msgs REQUIRED)
find_package(std_srvs REQUIRED)

add_executable(causal_engine_node src/causal_engine_node.cpp)
ament_target_dependencies(causal_engine_node rclcpp rclcpp_lifecycle std_msgs std_srvs)

install(TARGETS causal_engine_node DESTINATION lib/${PROJECT_NAME})
install(DIRECTORY config/ DESTINATION share/${PROJECT_NAME}/config)

ament_package()
