cmake_minimum_required(VERSION 3.14)
project(lego_mcp_realtime VERSION 1.0.0 LANGUAGES CXX)

# Require C++17
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

# Enable warnings
add_compile_options(-Wall -Wextra -Wpedantic -Werror)

# Real-time specific flags
if(CMAKE_SYSTEM_NAME STREQUAL "Linux")
  add_compile_definitions(HAVE_POSIX_RT)
  set(RT_LIBS rt pthread)
endif()

# Find dependencies
find_package(ament_cmake REQUIRED)
find_package(rclcpp REQUIRED)
find_package(rclcpp_lifecycle REQUIRED)
find_package(std_msgs REQUIRED)
find_package(builtin_interfaces REQUIRED)
find_package(rcl_interfaces REQUIRED)

# Include directories
include_directories(include)

# Real-time library
add_library(lego_mcp_realtime SHARED
  src/ptp_clock.cpp
  src/rt_scheduler.cpp
  src/deterministic_executor.cpp
  src/wcet_monitor.cpp
  src/clock_sync.cpp
)

target_include_directories(lego_mcp_realtime PUBLIC
  $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
  $<INSTALL_INTERFACE:include>
)

ament_target_dependencies(lego_mcp_realtime
  rclcpp
  rclcpp_lifecycle
  std_msgs
  builtin_interfaces
)

if(RT_LIBS)
  target_link_libraries(lego_mcp_realtime ${RT_LIBS})
endif()

# Real-time node
add_executable(realtime_node src/realtime_node.cpp)
target_link_libraries(realtime_node lego_mcp_realtime)
ament_target_dependencies(realtime_node rclcpp rclcpp_lifecycle std_msgs)

# Install
install(TARGETS
  lego_mcp_realtime
  ARCHIVE DESTINATION lib
  LIBRARY DESTINATION lib
  RUNTIME DESTINATION bin
)

install(TARGETS
  realtime_node
  DESTINATION lib/${PROJECT_NAME}
)

install(DIRECTORY include/
  DESTINATION include
)

install(DIRECTORY launch config
  DESTINATION share/${PROJECT_NAME}
)

# Testing
if(BUILD_TESTING)
  find_package(ament_lint_auto REQUIRED)
  find_package(ament_cmake_gtest REQUIRED)
  ament_lint_auto_find_test_dependencies()

  ament_add_gtest(test_ptp_clock test/test_ptp_clock.cpp)
  target_link_libraries(test_ptp_clock lego_mcp_realtime)

  ament_add_gtest(test_rt_scheduler test/test_rt_scheduler.cpp)
  target_link_libraries(test_rt_scheduler lego_mcp_realtime)
endif()

ament_export_include_directories(include)
ament_export_libraries(lego_mcp_realtime)
ament_export_dependencies(rclcpp std_msgs builtin_interfaces)

ament_package()
