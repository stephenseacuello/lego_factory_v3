cmake_minimum_required(VERSION 3.8)
project(lego_mcp_discovery)

if(CMAKE_COMPILER_IS_GNUCXX OR CMAKE_CXX_COMPILER_ID MATCHES "Clang")
  add_compile_options(-Wall -Wextra -Wpedantic)
endif()

find_package(ament_cmake REQUIRED)
find_package(ament_cmake_python REQUIRED)
find_package(rclpy REQUIRED)

# Install Python modules
ament_python_install_package(${PROJECT_NAME})

# Install executables
install(PROGRAMS
  lego_mcp_discovery/discovery_server_node.py
  lego_mcp_discovery/equipment_registry_node.py
  lego_mcp_discovery/topology_manager_node.py
  lego_mcp_discovery/bandwidth_optimizer_node.py
  lego_mcp_discovery/health_monitor_node.py
  DESTINATION lib/${PROJECT_NAME}
)

# Install config files
install(DIRECTORY config/
  DESTINATION share/${PROJECT_NAME}/config
)

if(BUILD_TESTING)
  find_package(ament_lint_auto REQUIRED)
  ament_lint_auto_find_test_dependencies()
endif()

ament_package()
