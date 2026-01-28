cmake_minimum_required(VERSION 3.16)
project(lego_mcp_safety_certified)

# ==============================================================================
# IEC 61508 SIL 2+ Safety-Critical Build Configuration
# ==============================================================================

# Require C++20 for safety-critical features
set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

# Safety-Critical Build Flags (ROS2 Humble compatible)
# Note: -fno-rtti and -fno-exceptions removed for ROS2 tracetools compatibility
set(SAFETY_CRITICAL_FLAGS
    -Wall
    -Wextra
    -Wpedantic
    -Wformat=2
    -Wformat-security
    -fstack-protector-strong
)

# Debug vs Release configurations
if(CMAKE_BUILD_TYPE STREQUAL "Debug")
    list(APPEND SAFETY_CRITICAL_FLAGS -O0 -g3 -DDEBUG_BUILD)
else()
    # Release with debug info for WCET analysis
    list(APPEND SAFETY_CRITICAL_FLAGS -O2 -g -DNDEBUG -DRELEASE_BUILD)
endif()

# Find dependencies
find_package(ament_cmake REQUIRED)
find_package(rclcpp REQUIRED)
find_package(rclcpp_lifecycle REQUIRED)
find_package(rclcpp_components REQUIRED)
find_package(std_msgs REQUIRED)
find_package(std_srvs REQUIRED)

# ==============================================================================
# Safety-Critical Library (Simplified)
# ==============================================================================

add_library(safety_core SHARED
    src/safety_node.cpp
)

target_compile_options(safety_core PRIVATE ${SAFETY_CRITICAL_FLAGS})

ament_target_dependencies(safety_core
    rclcpp
    rclcpp_lifecycle
    rclcpp_components
    std_msgs
    std_srvs
)

# ==============================================================================
# Executable Nodes
# ==============================================================================

add_executable(safety_node src/main.cpp)
target_link_libraries(safety_node safety_core)
target_compile_options(safety_node PRIVATE ${SAFETY_CRITICAL_FLAGS})

add_executable(safety_lifecycle_node src/main_lifecycle.cpp)
target_link_libraries(safety_lifecycle_node safety_core)
target_compile_options(safety_lifecycle_node PRIVATE ${SAFETY_CRITICAL_FLAGS})

# ==============================================================================
# Component Registration
# ==============================================================================

rclcpp_components_register_node(safety_core
    PLUGIN "lego_mcp::SafetyNode"
    EXECUTABLE safety_node_component
)

# ==============================================================================
# Installation
# ==============================================================================

install(TARGETS
    safety_core
    safety_node
    safety_lifecycle_node
    ARCHIVE DESTINATION lib
    LIBRARY DESTINATION lib
    RUNTIME DESTINATION lib/${PROJECT_NAME}
)

# ==============================================================================
# Testing
# ==============================================================================

if(BUILD_TESTING)
    find_package(ament_lint_auto REQUIRED)
    ament_lint_auto_find_test_dependencies()
endif()

ament_package()
