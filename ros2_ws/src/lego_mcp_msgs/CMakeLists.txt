cmake_minimum_required(VERSION 3.8)
project(lego_mcp_msgs)

if(CMAKE_COMPILER_IS_GNUCXX OR CMAKE_CXX_COMPILER_ID MATCHES "Clang")
  add_compile_options(-Wall -Wextra -Wpedantic)
endif()

find_package(ament_cmake REQUIRED)
find_package(rosidl_default_generators REQUIRED)
find_package(std_msgs REQUIRED)
find_package(geometry_msgs REQUIRED)
find_package(sensor_msgs REQUIRED)
find_package(builtin_interfaces REQUIRED)

# Generate messages
rosidl_generate_interfaces(${PROJECT_NAME}
  # Messages - Core Manufacturing
  "msg/BrickSpec.msg"
  "msg/PrintJob.msg"
  "msg/AssemblyStep.msg"
  "msg/EquipmentStatus.msg"
  "msg/DefectDetection.msg"
  "msg/QualityEvent.msg"
  "msg/FailureEvent.msg"
  "msg/TwinState.msg"
  # Messages - OTP Supervision (v7.0)
  "msg/Heartbeat.msg"
  "msg/ChildStatus.msg"
  "msg/SupervisorStatus.msg"
  # Messages - AGV Fleet (v7.0)
  "msg/AGVStatus.msg"
  "msg/AGVMission.msg"
  # Messages - Quality Inspection (v7.0)
  "msg/Measurement.msg"
  "msg/InspectionResult.msg"
  # Messages - Equipment Discovery (v7.0)
  "msg/EquipmentDiscovery.msg"
  # Messages - Digital Twin Sync (v7.0)
  "msg/TwinSync.msg"
  # Services - Manufacturing
  "srv/ScheduleJob.srv"
  "srv/CreateWorkOrder.srv"
  "srv/RescheduleRemaining.srv"
  "srv/GetTwinState.srv"
  # Services - OTP Supervision (v7.0)
  "srv/RestartNode.srv"
  "srv/LifecycleTransition.srv"
  "srv/GetSupervisorStatus.srv"
  # Services - AGV Fleet (v7.0)
  "srv/DispatchAGV.srv"
  # Services - Equipment Discovery (v7.0)
  "srv/DiscoverEquipment.srv"
  # Services - Quality Inspection (v7.0)
  "srv/RequestInspection.srv"
  # Actions - Manufacturing
  "action/PrintBrick.action"
  "action/AssembleLego.action"
  "action/MachineOperation.action"
  "action/StopOperation.action"
  # Actions - OTP Supervision (v7.0)
  "action/SupervisorRecovery.action"
  # Actions - AGV Fleet (v7.0)
  "action/AGVNavigation.action"
  # Actions - Orchestration (v7.0)
  "action/ExecuteWorkOrder.action"
  # Actions - Quality Inspection (v7.0)
  "action/PerformInspection.action"
  DEPENDENCIES
    std_msgs
    geometry_msgs
    sensor_msgs
    builtin_interfaces
)

ament_package()
