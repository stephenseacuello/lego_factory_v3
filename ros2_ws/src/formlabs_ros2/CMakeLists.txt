cmake_minimum_required(VERSION 3.8)
project(formlabs_ros2)

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
  formlabs_ros2/formlabs_node.py
  DESTINATION lib/${PROJECT_NAME}
)

# Install lifecycle executable wrapper
install(CODE "
  file(WRITE \"\${CMAKE_INSTALL_PREFIX}/lib/${PROJECT_NAME}/formlabs_node_lifecycle\"
\"#!/usr/bin/env python3
import sys
from formlabs_ros2.formlabs_node import main_lifecycle
sys.exit(main_lifecycle())
\")
  execute_process(COMMAND chmod +x \"\${CMAKE_INSTALL_PREFIX}/lib/${PROJECT_NAME}/formlabs_node_lifecycle\")
")

ament_package()
