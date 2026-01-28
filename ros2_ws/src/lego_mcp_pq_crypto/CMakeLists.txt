cmake_minimum_required(VERSION 3.8)
project(lego_mcp_pq_crypto)

if(NOT CMAKE_CXX_STANDARD)
  set(CMAKE_CXX_STANDARD 17)
endif()

find_package(ament_cmake REQUIRED)
find_package(ament_cmake_python REQUIRED)
find_package(rclcpp REQUIRED)
find_package(rclcpp_lifecycle REQUIRED)
find_package(std_msgs REQUIRED)
find_package(std_srvs REQUIRED)

# C++ PQ Crypto Node
add_executable(pq_crypto_node src/pq_crypto_node.cpp)
ament_target_dependencies(pq_crypto_node rclcpp rclcpp_lifecycle std_msgs std_srvs)

install(TARGETS
  pq_crypto_node
  DESTINATION lib/${PROJECT_NAME}
)

# Python modules
ament_python_install_package(${PROJECT_NAME})

install(DIRECTORY config/ DESTINATION share/${PROJECT_NAME}/config)

ament_package()
