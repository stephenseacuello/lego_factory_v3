cmake_minimum_required(VERSION 3.8)
project(lego_mcp_orchestrator)

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
  lego_mcp_orchestrator/orchestrator_node.py
  lego_mcp_orchestrator/twin_sync_node.py
  lego_mcp_orchestrator/ar_publisher_node.py
  lego_mcp_orchestrator/failure_detector_node.py
  lego_mcp_orchestrator/recovery_engine_node.py
  lego_mcp_orchestrator/quality_feedback_node.py
  lego_mcp_orchestrator/reschedule_service_node.py
  lego_mcp_orchestrator/moveit_assembly_node.py
  lego_mcp_orchestrator/equipment_monitor_node.py
  # v7.0 Action Servers
  lego_mcp_orchestrator/work_order_executor.py
  lego_mcp_orchestrator/inspection_action_server.py
  lego_mcp_orchestrator/agv_dispatcher.py
  # v7.0 Core Services
  lego_mcp_orchestrator/digital_twin_node.py
  lego_mcp_orchestrator/production_scheduler_node.py
  lego_mcp_orchestrator/traceability_node.py
  # v7.0 Lifecycle Management
  lego_mcp_orchestrator/lifecycle_manager.py
  lego_mcp_orchestrator/lifecycle_monitor_node.py
  lego_mcp_orchestrator/lifecycle_service_bridge.py
  lego_mcp_orchestrator/orchestrator_lifecycle_node.py
  DESTINATION lib/${PROJECT_NAME}
)

ament_package()
