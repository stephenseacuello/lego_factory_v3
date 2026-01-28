cmake_minimum_required(VERSION 3.8)
project(lego_mcp_tests)

if(CMAKE_COMPILER_IS_GNUCXX OR CMAKE_CXX_COMPILER_ID MATCHES "Clang")
  add_compile_options(-Wall -Wextra -Wpedantic)
endif()

find_package(ament_cmake REQUIRED)
find_package(ament_cmake_python REQUIRED)

# Install Python test modules
ament_python_install_package(${PROJECT_NAME})

# Install test launch files
install(DIRECTORY test/
  DESTINATION share/${PROJECT_NAME}/test
)

if(BUILD_TESTING)
  find_package(ament_lint_auto REQUIRED)
  find_package(launch_testing_ament_cmake REQUIRED)

  ament_lint_auto_find_test_dependencies()

  # Integration tests - Core
  add_launch_test(test/test_full_workflow.py)
  add_launch_test(test/test_safety.py)
  add_launch_test(test/test_recovery.py)
  add_launch_test(test/test_agv_fleet.py)
  add_launch_test(test/test_discovery.py)

  # Integration tests - v7.0 Action Servers
  add_launch_test(test/test_action_servers.py)
  add_launch_test(test/test_orchestration_scenarios.py)

  # Integration tests - Lifecycle
  add_launch_test(test/test_lifecycle_nodes.py)
  add_launch_test(test/test_lifecycle_transitions.py)
endif()

ament_package()
