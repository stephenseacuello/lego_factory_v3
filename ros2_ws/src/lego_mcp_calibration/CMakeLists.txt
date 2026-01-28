cmake_minimum_required(VERSION 3.8)
project(lego_mcp_calibration)

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
  lego_mcp_calibration/robot_calibration.py
  lego_mcp_calibration/hand_eye_calibration.py
  lego_mcp_calibration/tcp_calibration.py
  DESTINATION lib/${PROJECT_NAME}
)

ament_package()
