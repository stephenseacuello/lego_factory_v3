cmake_minimum_required(VERSION 3.8)
project(lego_mcp_agv)

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
  lego_mcp_agv/alvik_driver_node.py
  lego_mcp_agv/fleet_manager_node.py
  lego_mcp_agv/task_allocator_node.py
  lego_mcp_agv/waypoint_manager_node.py
  lego_mcp_agv/agv_simulator_node.py
  DESTINATION lib/${PROJECT_NAME}
)

# Install config files
install(DIRECTORY config/
  DESTINATION share/${PROJECT_NAME}/config
)

# Install launch files
install(DIRECTORY launch/
  DESTINATION share/${PROJECT_NAME}/launch
)

# Install maps
install(DIRECTORY maps/
  DESTINATION share/${PROJECT_NAME}/maps
)

if(BUILD_TESTING)
  find_package(ament_lint_auto REQUIRED)
  find_package(launch_testing_ament_cmake REQUIRED)
  ament_lint_auto_find_test_dependencies()
endif()

ament_package()
