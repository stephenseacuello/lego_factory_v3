cmake_minimum_required(VERSION 3.8)
project(lego_mcp_simulation)

if(CMAKE_COMPILER_IS_GNUCXX OR CMAKE_CXX_COMPILER_ID MATCHES "Clang")
  add_compile_options(-Wall -Wextra -Wpedantic)
endif()

find_package(ament_cmake REQUIRED)
find_package(ament_cmake_python REQUIRED)
find_package(rclpy REQUIRED)

# Install Python modules
ament_python_install_package(${PROJECT_NAME})

# Install Python executables
install(PROGRAMS
  lego_mcp_simulation/grbl_simulator.py
  lego_mcp_simulation/formlabs_simulator.py
  lego_mcp_simulation/bambu_simulator.py
  DESTINATION lib/${PROJECT_NAME}
)

# Create executable wrappers
install(CODE "
  file(WRITE \"\${CMAKE_INSTALL_PREFIX}/lib/${PROJECT_NAME}/grbl_simulator\"
\"#!/usr/bin/env python3
import sys
from lego_mcp_simulation.grbl_simulator import main
sys.exit(main())
\")
  execute_process(COMMAND chmod +x \"\${CMAKE_INSTALL_PREFIX}/lib/${PROJECT_NAME}/grbl_simulator\")
")

install(CODE "
  file(WRITE \"\${CMAKE_INSTALL_PREFIX}/lib/${PROJECT_NAME}/formlabs_simulator\"
\"#!/usr/bin/env python3
import sys
from lego_mcp_simulation.formlabs_simulator import main
sys.exit(main())
\")
  execute_process(COMMAND chmod +x \"\${CMAKE_INSTALL_PREFIX}/lib/${PROJECT_NAME}/formlabs_simulator\")
")

install(CODE "
  file(WRITE \"\${CMAKE_INSTALL_PREFIX}/lib/${PROJECT_NAME}/bambu_simulator\"
\"#!/usr/bin/env python3
import sys
from lego_mcp_simulation.bambu_simulator import main
sys.exit(main())
\")
  execute_process(COMMAND chmod +x \"\${CMAKE_INSTALL_PREFIX}/lib/${PROJECT_NAME}/bambu_simulator\")
")

# Install launch files
install(DIRECTORY launch/
  DESTINATION share/${PROJECT_NAME}/launch
)

# Install world files
install(DIRECTORY worlds/
  DESTINATION share/${PROJECT_NAME}/worlds
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
