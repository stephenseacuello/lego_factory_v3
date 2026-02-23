"""
Robotics and Autonomous Mobile Robot (AMR) Services.

Implements integration with autonomous mobile robots,
automated guided vehicles, and robotic arms for manufacturing.

Robotic Arm Support:
- Niryo Ned2 (6-DOF collaborative robot)
- UFactory xArm Lite 6 (6-DOF industrial robot)

Standards Compliance:
- ISO 10218 (Industrial Robot Safety)
- ISO/TS 15066 (Collaborative Robots)
"""

from .amr_integration import (
    AMRIntegrationService,
    create_amr_service
)

from .arm_controller import (
    ArmModel,
    ArmState,
    JointState,
    CartesianPose,
    DHParameter,
    ArmSpecification,
    KinematicsEngine,
    TrajectoryPlanner,
    TrajectoryPoint,
    BaseArmDriver,
    SimulatedArmDriver,
)

from .drivers import (
    NiryoNed2Driver,
    NIRYO_NED2_SPEC,
    XArmLite6Driver,
    XARM_LITE6_SPEC,
)

from .master_scheduler import (
    TaskType,
    TaskPriority,
    TaskStatus,
    AcknowledgmentType,
    RobotTask,
    TaskAcknowledgment,
    SynchronizedMotion,
    MasterScheduler,
    get_master_scheduler,
)

from .multi_robot_coordinator import (
    RobotType,
    RobotState,
    CoordinationMode,
    AllocationStrategy,
    CollisionAvoidanceMethod,
    Position3D,
    Velocity3D,
    RobotStatus,
    CoordinatedTask,
    Formation,
    CollisionRisk,
    MultiRobotCoordinator,
    get_multi_robot_coordinator,
)

from .agv_fleet_manager import (
    AGVState,
    TaskType as AGVTaskType,
    TaskPriority as AGVTaskPriority,
    TaskStatus as AGVTaskStatus,
    ZoneType,
    AllocationStrategy as AGVAllocationStrategy,
    PathAlgorithm,
    Position2D,
    Velocity2D,
    AGVSpecification,
    AGVStatus,
    Zone,
    ChargingStation,
    TransportTask,
    PathSegment,
    PlannedPath,
    TrafficConflict,
    PathPlanner,
    AGVFleetManager,
    get_agv_fleet_manager,
)

__all__ = [
    # AMR
    "AMRIntegrationService",
    "create_amr_service",
    # Arm Controller
    "ArmModel",
    "ArmState",
    "JointState",
    "CartesianPose",
    "DHParameter",
    "ArmSpecification",
    "KinematicsEngine",
    "TrajectoryPlanner",
    "TrajectoryPoint",
    "BaseArmDriver",
    "SimulatedArmDriver",
    # Arm Drivers
    "NiryoNed2Driver",
    "NIRYO_NED2_SPEC",
    "XArmLite6Driver",
    "XARM_LITE6_SPEC",
    # Master Scheduler
    "TaskType",
    "TaskPriority",
    "TaskStatus",
    "AcknowledgmentType",
    "RobotTask",
    "TaskAcknowledgment",
    "SynchronizedMotion",
    "MasterScheduler",
    "get_master_scheduler",
    # Multi-Robot Coordinator
    "RobotType",
    "RobotState",
    "CoordinationMode",
    "AllocationStrategy",
    "CollisionAvoidanceMethod",
    "Position3D",
    "Velocity3D",
    "RobotStatus",
    "CoordinatedTask",
    "Formation",
    "CollisionRisk",
    "MultiRobotCoordinator",
    "get_multi_robot_coordinator",
    # AGV Fleet Manager
    "AGVState",
    "AGVTaskType",
    "AGVTaskPriority",
    "AGVTaskStatus",
    "ZoneType",
    "AGVAllocationStrategy",
    "PathAlgorithm",
    "Position2D",
    "Velocity2D",
    "AGVSpecification",
    "AGVStatus",
    "Zone",
    "ChargingStation",
    "TransportTask",
    "PathSegment",
    "PlannedPath",
    "TrafficConflict",
    "PathPlanner",
    "AGVFleetManager",
    "get_agv_fleet_manager",
]
