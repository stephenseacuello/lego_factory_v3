cmake_minimum_required(VERSION 3.8)
project(lego_mcp_bft_consensus)

if(NOT CMAKE_CXX_STANDARD)
  set(CMAKE_CXX_STANDARD 17)
endif()

if(CMAKE_COMPILER_IS_GNUCXX OR CMAKE_CXX_COMPILER_ID MATCHES "Clang")
  add_compile_options(-Wall -Wextra -Wpedantic)
endif()

find_package(ament_cmake REQUIRED)
find_package(rclcpp REQUIRED)
find_package(rclcpp_lifecycle REQUIRED)
find_package(std_msgs REQUIRED)
find_package(std_srvs REQUIRED)

add_executable(bft_consensus_node
  src/bft_consensus_node.cpp
)
ament_target_dependencies(bft_consensus_node
  rclcpp
  rclcpp_lifecycle
  std_msgs
  std_srvs
)

install(TARGETS bft_consensus_node
  DESTINATION lib/${PROJECT_NAME}
)

install(DIRECTORY config/
  DESTINATION share/${PROJECT_NAME}/config
)

ament_package()
