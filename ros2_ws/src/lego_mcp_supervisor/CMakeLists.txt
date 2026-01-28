cmake_minimum_required(VERSION 3.8)
project(lego_mcp_supervisor)

# Default to C++17
if(NOT CMAKE_CXX_STANDARD)
  set(CMAKE_CXX_STANDARD 17)
endif()

if(CMAKE_COMPILER_IS_GNUCXX OR CMAKE_CXX_COMPILER_ID MATCHES "Clang")
  add_compile_options(-Wall -Wextra -Wpedantic)
endif()

# Find dependencies
find_package(ament_cmake REQUIRED)
find_package(ament_cmake_python REQUIRED)
find_package(rclpy REQUIRED)
find_package(std_msgs REQUIRED)
find_package(std_srvs REQUIRED)
find_package(lifecycle_msgs REQUIRED)
find_package(diagnostic_msgs REQUIRED)

# Install Python modules
ament_python_install_package(${PROJECT_NAME})

# Install Python executables
install(PROGRAMS
  lego_mcp_supervisor/supervisor_node.py
  lego_mcp_supervisor/heartbeat.py
  lego_mcp_supervisor/heartbeat_monitor_node.py
  lego_mcp_supervisor/checkpoint_manager.py
  DESTINATION lib/${PROJECT_NAME}
)

# Create executable wrappers for ros2 run
install(CODE "
  file(WRITE \"\${CMAKE_INSTALL_PREFIX}/lib/${PROJECT_NAME}/supervisor_node\"
\"#!/usr/bin/env python3
import sys
from lego_mcp_supervisor.supervisor_node import main
sys.exit(main())
\")
  execute_process(COMMAND chmod +x \"\${CMAKE_INSTALL_PREFIX}/lib/${PROJECT_NAME}/supervisor_node\")
")

install(CODE "
  file(WRITE \"\${CMAKE_INSTALL_PREFIX}/lib/${PROJECT_NAME}/heartbeat_monitor\"
\"#!/usr/bin/env python3
import sys
from lego_mcp_supervisor.heartbeat_monitor_node import main
sys.exit(main())
\")
  execute_process(COMMAND chmod +x \"\${CMAKE_INSTALL_PREFIX}/lib/${PROJECT_NAME}/heartbeat_monitor\")
")

# Install config files
install(DIRECTORY config/
  DESTINATION share/${PROJECT_NAME}/config
)

# Install launch files
install(DIRECTORY launch/
  DESTINATION share/${PROJECT_NAME}/launch
)

# Install test files
install(DIRECTORY test/
  DESTINATION share/${PROJECT_NAME}/test
)

if(BUILD_TESTING)
  find_package(ament_lint_auto REQUIRED)
  find_package(ament_cmake_pytest REQUIRED)

  # Lint tests
  ament_lint_auto_find_test_dependencies()

  # Python tests
  # ament_add_pytest_test(test_supervisor test/test_supervisor.py)
  # ament_add_pytest_test(test_heartbeat test/test_heartbeat.py)
endif()

ament_package()
