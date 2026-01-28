cmake_minimum_required(VERSION 3.14)
project(lego_mcp_observability VERSION 2.0.0 LANGUAGES CXX)

# C++20 for modern features
set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

# Compiler flags for optimization and safety
if(CMAKE_CXX_COMPILER_ID MATCHES "GNU|Clang")
    add_compile_options(
        -Wall -Wextra -Wpedantic
        -O3
    )
endif()

# Find dependencies
find_package(ament_cmake REQUIRED)
find_package(rclcpp REQUIRED)
find_package(rclcpp_lifecycle REQUIRED)
find_package(rclcpp_components REQUIRED)
find_package(std_msgs REQUIRED)

# Telemetry Collector Library
add_library(telemetry_collector SHARED
    src/telemetry_collector.cpp
)

target_include_directories(telemetry_collector
    PUBLIC
        $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
        $<INSTALL_INTERFACE:include>
)

ament_target_dependencies(telemetry_collector
    rclcpp
    rclcpp_lifecycle
    rclcpp_components
    std_msgs
)

rclcpp_components_register_nodes(telemetry_collector
    "lego_mcp::observability::TelemetryCollector"
)

# Install targets
install(TARGETS
    telemetry_collector
    ARCHIVE DESTINATION lib
    LIBRARY DESTINATION lib
    RUNTIME DESTINATION lib/${PROJECT_NAME}
)

# Install include directory
install(DIRECTORY include/
    DESTINATION include
)

# Install config and launch files
install(DIRECTORY
    config
    launch
    DESTINATION share/${PROJECT_NAME}
)

# Testing
if(BUILD_TESTING)
    find_package(ament_lint_auto REQUIRED)
    ament_lint_auto_find_test_dependencies()

    find_package(ament_cmake_gtest REQUIRED)
    ament_add_gtest(test_metrics
        test/test_metrics.cpp
    )
    target_link_libraries(test_metrics
        telemetry_collector
    )
endif()

ament_package()
