"""
V8 Autonomous Factory Services
==============================

Autonomous capabilities for the smart factory:
- Self-healing and fault recovery
- Predictive maintenance
- Autonomous scheduling optimization
- Quality control automation
- Fleet management

Author: LEGO MCP Engineering Team
Version: 8.0.0
"""

from .self_healing import (
    CircuitState,
    HealthLevel,
    RecoveryAction,
    FaultType,
    Fault,
    RecoveryPlan,
    ComponentHealth,
    CircuitBreaker,
    SelfHealingOrchestrator,
    get_self_healing_orchestrator,
    self_healing,
)

from .predictive_maintenance import (
    MaintenanceType,
    MaintenancePriority,
    EquipmentCondition,
    FailureMode,
    SensorType,
    SensorReading,
    EquipmentHealth,
    MaintenanceWorkOrder,
    AnomalyDetection,
    PredictiveMaintenanceEngine,
    get_predictive_maintenance_engine,
)

from .sensor_fusion import (
    SensorType as FusionSensorType,
    FusionMethod,
    SensorStatus,
    AnomalyType as FusionAnomalyType,
    SensorConfig,
    SensorReading as FusionSensorReading,
    FusedState,
    SensorAnomaly,
    CalibrationResult,
    KalmanFilter,
    ComplementaryFilter,
    SensorFusionEngine,
    get_sensor_fusion_engine,
)

from .scheduling_optimizer import (
    ScheduleType,
    OptimizationObjective,
    JobStatus,
    JobPriority,
    MachineStatus,
    ConstraintType,
    Operation,
    Job,
    Machine,
    ScheduledOperation,
    Schedule,
    Constraint,
    ScheduleMetrics,
    SchedulingOptimizer,
    get_scheduling_optimizer,
)

from .quality_controller import (
    QualityLevel,
    ControlChartType,
    InspectionType,
    DefectSeverity,
    DefectType,
    ControlStatus,
    InspectionResult,
    QualitySpecification,
    Measurement,
    Defect,
    ControlLimit,
    CapabilityMetrics,
    InspectionPlan,
    InspectionRecord,
    QualityAlert,
    SPCController,
    AutonomousQualityController,
    get_quality_controller,
)

__all__ = [
    # Self-Healing
    'CircuitState',
    'HealthLevel',
    'RecoveryAction',
    'FaultType',
    'Fault',
    'RecoveryPlan',
    'ComponentHealth',
    'CircuitBreaker',
    'SelfHealingOrchestrator',
    'get_self_healing_orchestrator',
    'self_healing',
    # Predictive Maintenance
    'MaintenanceType',
    'MaintenancePriority',
    'EquipmentCondition',
    'FailureMode',
    'SensorType',
    'SensorReading',
    'EquipmentHealth',
    'MaintenanceWorkOrder',
    'AnomalyDetection',
    'PredictiveMaintenanceEngine',
    'get_predictive_maintenance_engine',
    # Sensor Fusion
    'FusionSensorType',
    'FusionMethod',
    'SensorStatus',
    'FusionAnomalyType',
    'SensorConfig',
    'FusionSensorReading',
    'FusedState',
    'SensorAnomaly',
    'CalibrationResult',
    'KalmanFilter',
    'ComplementaryFilter',
    'SensorFusionEngine',
    'get_sensor_fusion_engine',
    # Scheduling Optimizer
    'ScheduleType',
    'OptimizationObjective',
    'JobStatus',
    'JobPriority',
    'MachineStatus',
    'ConstraintType',
    'Operation',
    'Job',
    'Machine',
    'ScheduledOperation',
    'Schedule',
    'Constraint',
    'ScheduleMetrics',
    'SchedulingOptimizer',
    'get_scheduling_optimizer',
    # Quality Controller
    'QualityLevel',
    'ControlChartType',
    'InspectionType',
    'DefectSeverity',
    'DefectType',
    'ControlStatus',
    'InspectionResult',
    'QualitySpecification',
    'Measurement',
    'Defect',
    'ControlLimit',
    'CapabilityMetrics',
    'InspectionPlan',
    'InspectionRecord',
    'QualityAlert',
    'SPCController',
    'AutonomousQualityController',
    'get_quality_controller',
]

__version__ = '8.0.0'
