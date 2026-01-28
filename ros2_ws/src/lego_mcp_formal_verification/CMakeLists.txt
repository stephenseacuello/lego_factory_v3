cmake_minimum_required(VERSION 3.8)
project(lego_mcp_formal_verification)

if(NOT CMAKE_CXX_STANDARD)
  set(CMAKE_CXX_STANDARD 17)
endif()

find_package(ament_cmake REQUIRED)
find_package(ament_cmake_python REQUIRED)
find_package(rclcpp REQUIRED)
find_package(rclcpp_lifecycle REQUIRED)
find_package(std_msgs REQUIRED)
find_package(std_srvs REQUIRED)

# C++ Runtime Monitor Node
add_executable(runtime_monitor_node src/runtime_monitor_node.cpp)
ament_target_dependencies(runtime_monitor_node rclcpp rclcpp_lifecycle std_msgs std_srvs)

# C++ Model Checker Bridge
add_executable(model_checker_node src/model_checker_node.cpp)
ament_target_dependencies(model_checker_node rclcpp rclcpp_lifecycle std_msgs std_srvs)

install(TARGETS 
  runtime_monitor_node 
  model_checker_node 
  DESTINATION lib/${PROJECT_NAME}
)

# Python modules
ament_python_install_package(${PROJECT_NAME})

install(DIRECTORY monitors/ DESTINATION share/${PROJECT_NAME}/monitors)
install(DIRECTORY promela/ DESTINATION share/${PROJECT_NAME}/promela)
install(DIRECTORY tla/ DESTINATION share/${PROJECT_NAME}/tla)
install(DIRECTORY config/ DESTINATION share/${PROJECT_NAME}/config)

ament_package()
