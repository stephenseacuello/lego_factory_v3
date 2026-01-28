cmake_minimum_required(VERSION 3.8)
project(cnc_interfaces)

if(CMAKE_COMPILER_IS_GNUCXX OR CMAKE_CXX_COMPILER_ID MATCHES "Clang")
  add_compile_options(-Wall -Wextra -Wpedantic)
endif()

# Find dependencies
find_package(ament_cmake REQUIRED)
find_package(rosidl_default_generators REQUIRED)
find_package(std_msgs REQUIRED)
find_package(geometry_msgs REQUIRED)
find_package(builtin_interfaces REQUIRED)
find_package(action_msgs REQUIRED)

# Generate interfaces
rosidl_generate_interfaces(${PROJECT_NAME}
  # Core Messages
  "msg/MachineStatus.msg"
  "msg/MachinePosition.msg"
  "msg/GrblStatus.msg"
  "msg/SensorReading.msg"
  "msg/SpindleState.msg"
  "msg/Alarm.msg"
  "msg/OeeMetrics.msg"
  "msg/JobEvent.msg"
  "msg/FleetEvent.msg"

  # Traceability messages
  "msg/KeyValue.msg"
  "msg/Measurement.msg"
  "msg/Defect.msg"
  "msg/ProcessStep.msg"
  "msg/QualityRecord.msg"
  "msg/PartGenealogy.msg"

  # Predictive Maintenance messages
  "msg/PredictiveMaintenance.msg"
  "msg/ToolWear.msg"

  # Motion Planning messages
  "msg/CollisionWarning.msg"
  "msg/PathPlan.msg"

  # Digital Twin messages
  "msg/DigitalTwinState.msg"

  # ISO 23247 / Unity Digital Twin messages
  "msg/ISO23247State.msg"
  "msg/AxisState.msg"
  "msg/ToolStateMsg.msg"
  "msg/SpindleStateMsg.msg"
  "msg/SensorOverlayMsg.msg"
  "msg/UnityCommand.msg"

  # Voice Control messages
  "msg/VoiceCommand.msg"

  # Safety messages
  "msg/SafetyState.msg"

  # Scheduling messages
  "msg/ScheduleJob.msg"

  # Cloud/Multi-site messages
  "msg/CloudSync.msg"

  # Traceability Enhancement messages
  "msg/BarcodeReading.msg"

  # Analytics messages
  "msg/BagAnalytics.msg"

  # Vision/CV messages
  "msg/VisionDetection.msg"
  "msg/VisionDetectionArray.msg"
  "msg/VisionSafetyAlert.msg"
  "msg/VisionStatus.msg"

  # Core Services
  "srv/Home.srv"
  "srv/Jog.srv"
  "srv/SendGcode.srv"
  "srv/SetFeedOverride.srv"
  "srv/EmergencyStop.srv"
  "srv/DispatchJob.srv"
  "srv/GetFleetStatus.srv"
  "srv/AllocateMachine.srv"
  "srv/GetGenealogy.srv"

  # Motion Planning services
  "srv/PlanPath.srv"

  # Predictive Maintenance services
  "srv/GetPrediction.srv"

  # Voice services
  "srv/ProcessVoice.srv"

  # Scheduling services
  "srv/ScheduleJobs.srv"

  # Safety services
  "srv/SafetyReset.srv"

  # Traceability services
  "srv/ScanBarcode.srv"

  # Analytics services
  "srv/AnalyzeBag.srv"

  # Cloud services
  "srv/CloudBroadcast.srv"

  # Vision/CV services
  "srv/InspectPart.srv"
  "srv/CheckToolWear.srv"
  "srv/VerifyPartPosition.srv"
  "srv/CheckSafetyZone.srv"

  # Core Actions
  "action/ExecuteGcode.action"

  # ML Training actions
  "action/TrainModel.action"

  DEPENDENCIES std_msgs geometry_msgs builtin_interfaces action_msgs
)

ament_export_dependencies(rosidl_default_runtime)

# Testing
if(BUILD_TESTING)
  find_package(ament_cmake_pytest REQUIRED)
  ament_add_pytest_test(test_message_schemas test/test_message_schemas.py
    TIMEOUT 60
  )
endif()

ament_package()
