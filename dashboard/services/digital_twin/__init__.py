"""
Digital Twin Module
===================

LegoMCP PhD-Level Manufacturing Platform
Part of the Digital Twin Research (Phase 3)

This module implements ISO 23247-compliant digital twin capabilities for
manufacturing equipment and processes. A digital twin is a virtual replica
of physical assets that enables:

1. **Real-Time Monitoring**: Live equipment state and performance
2. **Predictive Maintenance**: Forecast failures before they occur
3. **Process Simulation**: Test changes virtually before implementation
4. **Performance Optimization**: Continuous improvement through analytics

ISO 23247 Compliance:
---------------------
The Digital Twin Framework for Manufacturing (ISO 23247) defines:
- Observable Manufacturing Element (OME): Physical asset
- Digital Twin Entity: Virtual representation
- Data Collection: Sensors and acquisition
- Synchronization: OME <-> DT state alignment

Architecture Layers:
--------------------

1. **Physical Layer**:
   - Manufacturing equipment (CNC, robots, conveyors)
   - Sensors (temperature, vibration, current)
   - Actuators and controllers

2. **Data Layer**:
   - Time-series databases (TimescaleDB)
   - Event sourcing (complete history)
   - Real-time streaming (Redis Streams)

3. **Model Layer**:
   - Physics-Informed Neural Networks (PINN)
   - Data-driven ML models
   - Hybrid physics + ML models

4. **Application Layer**:
   - Predictive maintenance
   - Anomaly detection
   - Process optimization
   - What-if simulation

Components:
-----------

1. **DigitalTwinManager**:
   - Equipment registration and lifecycle
   - State synchronization
   - Event handling
   - Query interface

2. **PredictiveMaintenanceService**:
   - Remaining Useful Life (RUL) prediction
   - Failure probability estimation
   - Maintenance scheduling
   - Alert generation

3. **Ontology System** (ontology/):
   - OWL-based manufacturing ontology
   - Knowledge graph (Neo4j)
   - SPARQL queries
   - Semantic reasoning

4. **ML Models** (ml/):
   - Physics-Informed Neural Networks
   - Anomaly detection (Isolation Forest, AutoEncoder)
   - RUL estimation (survival analysis)
   - Hybrid physics-ML models

5. **Synchronization** (sync/):
   - CRDT-based conflict resolution
   - Event sourcing with snapshots
   - Formal state machine verification
   - Real-time sync protocols

Example Usage:
--------------
    from services.digital_twin import (
        DigitalTwinManager,
        PredictiveMaintenanceService,
    )

    # Initialize digital twin manager
    manager = DigitalTwinManager()

    # Register equipment
    machine = manager.register_equipment(
        equipment_id="CNC-001",
        equipment_type="cnc_machine",
        sensors=["temperature", "vibration", "spindle_current"],
    )

    # Update state from sensors
    manager.update_state("CNC-001", {
        "temperature": 45.2,
        "vibration": 0.15,
        "spindle_current": 12.5,
    })

    # Predictive maintenance
    maintenance = PredictiveMaintenanceService()
    prediction = maintenance.predict_rul("CNC-001")
    print(f"Remaining useful life: {prediction.rul_hours:.0f} hours")

    # Anomaly detection
    anomalies = manager.detect_anomalies("CNC-001")
    if anomalies:
        print(f"Detected anomalies: {anomalies}")

Research Contributions:
-----------------------
- Novel PINN approach for manufacturing process modeling
- Ontology-based semantic digital twins
- CRDT-based distributed synchronization
- Hybrid physics-ML for improved accuracy

References:
-----------
- ISO 23247 (2021). Digital Twin Framework for Manufacturing
- Raissi, M. et al. (2019). Physics-Informed Neural Networks
- Tao, F. et al. (2018). Digital Twin in Industry: State-of-the-Art
- Shapiro, M. et al. (2011). Conflict-free Replicated Data Types

Author: LegoMCP Team
Version: 2.0.0
"""

# Core Digital Twin Services
from .twin_manager import DigitalTwinManager, get_twin_manager
from .event_store import EventStore
from .event_types import TwinEvent, EventCategory, EventPriority
from .sync_protocol import SyncProtocol

# Optional: TimeSeriesAdapter (requires database)
try:
    from .time_series import TimeSeriesAdapter, AggregationType
except ImportError:
    TimeSeriesAdapter = None
    AggregationType = None

# Optional: PredictiveMaintenanceService (requires database models)
try:
    from .maintenance_service import PredictiveMaintenanceService
except ImportError:
    PredictiveMaintenanceService = None

# ISO 23247 Compliant Components
from .ome_registry import (
    ObservableManufacturingElement,
    OMERegistry,
    OMEType,
    OMELifecycleState,
    CapabilityType,
    StaticAttributes,
    DynamicAttributes,
    Geometry3D,
    BehaviorModel,
    get_ome_registry,
    create_printer_ome,
    create_sensor_ome,
    create_work_cell_ome,
    # Robotic Arm OME Factory Functions
    create_robotic_arm_ome,
    create_niryo_ned2_ome,
    create_xarm_lite6_ome,
    create_end_effector_ome,
)
from .twin_engine import (
    TwinEngine,
    DigitalTwinInstance,
    TwinType,
    TwinState,
    SyncMode,
    SimulationConfig,
    SimulationResult,
    PredictionResult,
    get_twin_engine,
)

# Ontology System
from .ontology import (
    ManufacturingOntology,
    OntologyMapper,
    KnowledgeGraph,
)

# ML Models (optional - requires PyTorch)
try:
    from .ml import (
        PhysicsInformedNN,
        PhysicsConstraint,
        HybridModel,
        AnomalyDetector,
        RULEstimator,
        FailurePredictor,
        get_failure_predictor,
        get_rul_estimator,
        get_anomaly_detector,
    )
except ImportError:
    PhysicsInformedNN = None
    PhysicsConstraint = None
    HybridModel = None
    AnomalyDetector = None
    RULEstimator = None
    FailurePredictor = None
    get_failure_predictor = None
    get_rul_estimator = None
    get_anomaly_detector = None

# Synchronization (optional)
try:
    from .sync import (
        CRDTConflictResolver,
        StateMachine,
    )
except ImportError:
    CRDTConflictResolver = None
    StateMachine = None

# Real-Time Twin Synchronization (v6.0)
from .realtime_sync import (
    RealtimeTwinSync,
    MultiTwinSyncManager,
    FeedbackIntegrator,
    TwinState as RealtimeTwinState,
    SyncState,
    SyncMetrics,
    UpdateSource,
)

# State Interpolation (for 60fps Unity visualization)
try:
    from .interpolation import (
        StateInterpolationService,
        InterpolationMode,
        StateSnapshot,
        InterpolationConfig,
        get_interpolation_service,
    )
except ImportError:
    StateInterpolationService = None
    InterpolationMode = None
    StateSnapshot = None
    InterpolationConfig = None
    get_interpolation_service = None

# Time Synchronization (distributed clock sync)
try:
    from .time_sync import (
        TimeSyncService,
        TimeSyncConfig,
        VectorClock,
        HybridLogicalClock,
        ClockSource,
        SyncQuality,
        TimeOffset,
        get_time_sync_service,
    )
except ImportError:
    TimeSyncService = None
    TimeSyncConfig = None
    VectorClock = None
    HybridLogicalClock = None
    ClockSource = None
    SyncQuality = None
    TimeOffset = None
    get_time_sync_service = None

# Predictive Analytics Service
from .predictive_analytics import (
    PredictiveAnalyticsService,
    PredictionCategory,
    PredictionResult as AnalyticsPredictionResult,
    PredictiveAlert,
    AlertPriority,
    MaintenanceRecommendation,
    EnergyForecast,
    QualityForecast,
    get_predictive_analytics_service,
)

# Anomaly Response Automation
from .anomaly_response import (
    AnomalyResponseService,
    AnomalyType,
    SeverityLevel,
    ResponseType,
    ResponseStatus,
    EscalationLevel,
    Anomaly,
    ResponseAction,
    ResponseExecution,
    ResponseRule,
    EscalationManager,
    MLResponseSuggester,
    get_anomaly_response_service,
)

# Supply Chain Digital Twin
from .supply_chain_twin import (
    SupplyChainTwinService,
    SupplyChainNode,
    SupplyChainEdge,
    NodeType,
    NodeStatus,
    TransportMode,
    RiskCategory,
    MaterialCategory,
    GeoLocation,
    Material,
    InventoryLevel,
    RiskFactor,
    Shipment,
    DisruptionScenario,
    get_supply_chain_twin_service,
)

# V8 Physics-Informed Neural Networks
try:
    from .pinn_model import (
        PINNModel,
        PhysicsConstraint as PINNPhysicsConstraint,
        ThermalDynamicsModel,
        KinematicChainModel,
        MaterialFlowModel,
        DegradationModel,
        PINNTrainer,
        get_pinn_model,
    )
except ImportError:
    PINNModel = None
    PINNPhysicsConstraint = None
    ThermalDynamicsModel = None
    KinematicChainModel = None
    MaterialFlowModel = None
    DegradationModel = None
    PINNTrainer = None
    get_pinn_model = None

# V8 ISO 23247 Ontology
try:
    from .twin_ontology import (
        TwinOntologyManager,
        ObservableManufacturingElement as OntologyOME,
        DigitalTwinEntity,
        EntityRelation,
        SemanticQuery,
        create_ontology_manager,
    )
except ImportError:
    TwinOntologyManager = None
    OntologyOME = None
    DigitalTwinEntity = None
    EntityRelation = None
    SemanticQuery = None
    create_ontology_manager = None

# V8 Advanced State Synchronization
from .advanced_sync import (
    ShadowStateMode,
    MergeStrategy,
    DiffType,
    FederationRole,
    SyncDirection,
    VectorClock as AdvancedVectorClock,
    LWWRegister,
    GCounter,
    ORSet,
    StateDiff,
    StatePatch,
    ShadowState,
    FederatedTwin,
    SyncTransaction,
    AdvancedStateSynchronizer,
    get_advanced_synchronizer,
)

__all__ = [
    # Core Services
    "DigitalTwinManager",
    "PredictiveMaintenanceService",
    "EventStore",
    "TwinEvent",
    "EventCategory",
    "EventPriority",
    "TimeSeriesAdapter",
    "AggregationType",
    "SyncProtocol",
    "get_twin_manager",

    # ISO 23247 OME Registry
    "ObservableManufacturingElement",
    "OMERegistry",
    "OMEType",
    "OMELifecycleState",
    "CapabilityType",
    "StaticAttributes",
    "DynamicAttributes",
    "Geometry3D",
    "BehaviorModel",
    "get_ome_registry",
    "create_printer_ome",
    "create_sensor_ome",
    "create_work_cell_ome",
    # Robotic Arm OME Factory Functions
    "create_robotic_arm_ome",
    "create_niryo_ned2_ome",
    "create_xarm_lite6_ome",
    "create_end_effector_ome",

    # Digital Twin Engine
    "TwinEngine",
    "DigitalTwinInstance",
    "TwinType",
    "TwinState",
    "SyncMode",
    "SimulationConfig",
    "SimulationResult",
    "PredictionResult",
    "get_twin_engine",

    # Ontology
    "ManufacturingOntology",
    "OntologyMapper",
    "KnowledgeGraph",

    # ML Models
    "PhysicsInformedNN",
    "PhysicsConstraint",
    "HybridModel",
    "AnomalyDetector",
    "RULEstimator",
    "FailurePredictor",
    "get_failure_predictor",
    "get_rul_estimator",
    "get_anomaly_detector",

    # Synchronization
    "CRDTConflictResolver",
    "StateMachine",

    # Real-Time Sync (v6.0)
    "RealtimeTwinSync",
    "MultiTwinSyncManager",
    "FeedbackIntegrator",
    "RealtimeTwinState",
    "SyncState",
    "SyncMetrics",
    "UpdateSource",

    # State Interpolation
    "StateInterpolationService",
    "InterpolationMode",
    "StateSnapshot",
    "InterpolationConfig",
    "get_interpolation_service",

    # Time Synchronization
    "TimeSyncService",
    "TimeSyncConfig",
    "VectorClock",
    "HybridLogicalClock",
    "ClockSource",
    "SyncQuality",
    "TimeOffset",
    "get_time_sync_service",

    # Predictive Analytics
    "PredictiveAnalyticsService",
    "PredictionCategory",
    "AnalyticsPredictionResult",
    "PredictiveAlert",
    "AlertPriority",
    "MaintenanceRecommendation",
    "MaintenanceAction",
    "EnergyForecast",
    "QualityForecast",
    "get_predictive_analytics_service",

    # Anomaly Response
    "AnomalyResponseService",
    "AnomalyType",
    "SeverityLevel",
    "ResponseType",
    "ResponseStatus",
    "EscalationLevel",
    "Anomaly",
    "ResponseAction",
    "ResponseExecution",
    "ResponseRule",
    "EscalationManager",
    "MLResponseSuggester",
    "get_anomaly_response_service",

    # Supply Chain Twin
    "SupplyChainTwinService",
    "SupplyChainNode",
    "SupplyChainEdge",
    "NodeType",
    "NodeStatus",
    "TransportMode",
    "RiskCategory",
    "MaterialCategory",
    "GeoLocation",
    "Material",
    "InventoryLevel",
    "RiskFactor",
    "Shipment",
    "DisruptionScenario",
    "get_supply_chain_twin_service",

    # V8 Physics-Informed Neural Networks
    "PINNModel",
    "PINNPhysicsConstraint",
    "ThermalDynamicsModel",
    "KinematicChainModel",
    "MaterialFlowModel",
    "DegradationModel",
    "PINNTrainer",
    "get_pinn_model",

    # V8 ISO 23247 Ontology
    "TwinOntologyManager",
    "OntologyOME",
    "DigitalTwinEntity",
    "EntityRelation",
    "SemanticQuery",
    "create_ontology_manager",

    # V8 Advanced State Synchronization
    "ShadowStateMode",
    "MergeStrategy",
    "DiffType",
    "FederationRole",
    "SyncDirection",
    "AdvancedVectorClock",
    "LWWRegister",
    "GCounter",
    "ORSet",
    "StateDiff",
    "StatePatch",
    "ShadowState",
    "FederatedTwin",
    "SyncTransaction",
    "AdvancedStateSynchronizer",
    "get_advanced_synchronizer",
]

__version__ = "8.0.0"
__author__ = "LegoMCP Team"
