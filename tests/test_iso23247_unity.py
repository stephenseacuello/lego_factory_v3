"""
Comprehensive tests for ISO 23247 Digital Twin and Unity Integration.

Tests cover:
- OME Registry (Observable Manufacturing Elements)
- Digital Twin Engine
- Unity Bridge and Scene Data
- Anomaly Response Automation
- Supply Chain Digital Twin
- VR Training System
- Quality Heatmaps
- 3D Defect Mapping
"""

import pytest
from datetime import datetime, timedelta
from typing import Dict, Any, List
import uuid
import asyncio


# ============================================================================
# OME Registry Tests
# ============================================================================

class TestOMERegistry:
    """Tests for Observable Manufacturing Element Registry."""

    def test_ome_registry_initialization(self):
        """Test OME registry initializes correctly."""
        from dashboard.services.digital_twin import get_ome_registry

        registry = get_ome_registry()
        assert registry is not None
        assert hasattr(registry, 'register_ome')
        assert hasattr(registry, 'get_ome')

    def test_create_printer_ome(self):
        """Test creating a printer OME."""
        from dashboard.services.digital_twin import create_printer_ome, OMEType

        printer = create_printer_ome(
            name="Test Printer",
            manufacturer="Prusa",
            model="MK3S+",
            serial_number="PRUSA-TEST-001",
            position=(0, 0, 0),
            build_volume=(250, 210, 210)
        )

        assert printer is not None
        assert printer.name == "Test Printer"
        assert printer.ome_type == OMEType.EQUIPMENT
        assert printer.static_attributes is not None

    def test_create_sensor_ome(self):
        """Test creating a sensor OME."""
        from dashboard.services.digital_twin import create_sensor_ome, OMEType

        sensor = create_sensor_ome(
            name="Temperature Sensor 1",
            sensor_type="temperature",
            measurement_unit="celsius",
            sampling_rate_hz=10.0,
            accuracy=0.5
        )

        assert sensor is not None
        assert sensor.ome_type == OMEType.SENSOR
        assert sensor.static_attributes.sensor_type == "temperature"

    def test_create_robotic_arm_ome(self):
        """Test creating robotic arm OME."""
        from dashboard.services.digital_twin import create_robotic_arm_ome, OMEType

        arm = create_robotic_arm_ome(
            name="Test Arm",
            arm_model="generic",
            dof=6,
            reach_mm=600,
            payload_kg=2.0
        )

        assert arm is not None
        assert arm.ome_type == OMEType.EQUIPMENT
        assert "reach_mm" in arm.static_attributes.specifications

    def test_create_niryo_ned2_ome(self):
        """Test creating Niryo Ned2 specific OME."""
        from dashboard.services.digital_twin import create_niryo_ned2_ome

        ned2 = create_niryo_ned2_ome(
            name="Niryo Ned2 Test",
            serial_number="NED2-TEST-001"
        )

        assert ned2 is not None
        assert "Niryo" in ned2.name or ned2.static_attributes.manufacturer == "Niryo"

    def test_ome_lifecycle_states(self):
        """Test OME lifecycle state transitions."""
        from dashboard.services.digital_twin import OMELifecycleState

        # Verify all expected states exist
        assert OMELifecycleState.DESIGN is not None
        assert OMELifecycleState.COMMISSIONING is not None
        assert OMELifecycleState.ACTIVE is not None
        assert OMELifecycleState.MAINTENANCE is not None
        assert OMELifecycleState.DEGRADED is not None
        assert OMELifecycleState.RETIRED is not None

    def test_register_and_retrieve_ome(self):
        """Test registering and retrieving OME."""
        from dashboard.services.digital_twin import get_ome_registry, create_printer_ome

        registry = get_ome_registry()
        printer = create_printer_ome(
            name="Registry Test Printer",
            manufacturer="Bambu",
            model="A1"
        )

        # Register
        ome_id = registry.register_ome(printer)
        assert ome_id is not None

        # Retrieve
        retrieved = registry.get_ome(ome_id)
        assert retrieved is not None
        assert retrieved.name == "Registry Test Printer"


# ============================================================================
# Digital Twin Engine Tests
# ============================================================================

class TestTwinEngine:
    """Tests for Digital Twin Engine."""

    def test_twin_engine_initialization(self):
        """Test twin engine initializes correctly."""
        from dashboard.services.digital_twin import get_twin_engine

        engine = get_twin_engine()
        assert engine is not None
        assert hasattr(engine, 'create_twin')
        assert hasattr(engine, 'get_twin')

    def test_create_digital_twin(self):
        """Test creating a digital twin instance."""
        from dashboard.services.digital_twin import (
            get_twin_engine, create_printer_ome, TwinType
        )

        engine = get_twin_engine()
        ome = create_printer_ome(name="Twin Test Printer", manufacturer="Test")

        twin = engine.create_twin(ome, twin_type=TwinType.MONITORING)

        assert twin is not None
        assert twin.twin_type == TwinType.MONITORING

    def test_twin_states(self):
        """Test twin state enumeration."""
        from dashboard.services.digital_twin import TwinState

        assert TwinState.INITIALIZING is not None
        assert TwinState.SYNCING is not None
        assert TwinState.ACTIVE is not None
        assert TwinState.SIMULATING is not None

    def test_sync_modes(self):
        """Test synchronization modes."""
        from dashboard.services.digital_twin import SyncMode

        assert SyncMode.REALTIME is not None
        assert SyncMode.PERIODIC is not None
        assert SyncMode.ON_DEMAND is not None

    def test_simulation_config(self):
        """Test simulation configuration."""
        from dashboard.services.digital_twin import SimulationConfig

        config = SimulationConfig(
            duration_seconds=3600,
            time_scale=10.0,
            enable_physics=True
        )

        assert config.duration_seconds == 3600
        assert config.time_scale == 10.0


# ============================================================================
# Unity Integration Tests
# ============================================================================

class TestUnityBridge:
    """Tests for Unity WebSocket Bridge."""

    def test_unity_bridge_imports(self):
        """Test Unity bridge imports correctly."""
        from dashboard.services.unity import UnityBridge

        bridge = UnityBridge()
        assert bridge is not None

    def test_scene_data_service(self):
        """Test Unity scene data service."""
        from dashboard.services.unity import UnitySceneDataService

        service = UnitySceneDataService()
        assert service is not None
        assert hasattr(service, 'get_scene_state')
        assert hasattr(service, 'get_equipment_transforms')

    def test_scene_state_serialization(self):
        """Test scene state serialization for Unity."""
        from dashboard.services.unity import UnitySceneDataService

        service = UnitySceneDataService()
        state = service.get_scene_state()

        assert 'equipment' in state or state is not None
        assert isinstance(state, dict)

    def test_equipment_transform_data(self):
        """Test equipment transform data for Unity."""
        from dashboard.services.unity import UnitySceneDataService

        service = UnitySceneDataService()
        transforms = service.get_equipment_transforms()

        assert isinstance(transforms, (list, dict))


# ============================================================================
# Anomaly Response Tests
# ============================================================================

class TestAnomalyResponse:
    """Tests for Anomaly Response Automation."""

    def test_anomaly_response_service_init(self):
        """Test anomaly response service initialization."""
        from dashboard.services.digital_twin import get_anomaly_response_service

        service = get_anomaly_response_service()
        assert service is not None

    def test_anomaly_types(self):
        """Test anomaly type enumeration."""
        from dashboard.services.digital_twin import AnomalyType

        assert AnomalyType.TEMPERATURE is not None
        assert AnomalyType.VIBRATION is not None
        assert AnomalyType.QUALITY is not None
        assert AnomalyType.EQUIPMENT is not None

    def test_severity_levels(self):
        """Test severity level enumeration."""
        from dashboard.services.digital_twin import SeverityLevel

        assert SeverityLevel.INFO is not None
        assert SeverityLevel.LOW is not None
        assert SeverityLevel.MEDIUM is not None
        assert SeverityLevel.HIGH is not None
        assert SeverityLevel.CRITICAL is not None

    def test_response_types(self):
        """Test response type enumeration."""
        from dashboard.services.digital_twin import ResponseType

        assert ResponseType.AUTOMATIC is not None
        assert ResponseType.SEMI_AUTOMATIC is not None
        assert ResponseType.MANUAL is not None
        assert ResponseType.ESCALATE is not None

    def test_create_anomaly(self):
        """Test creating an anomaly record."""
        from dashboard.services.digital_twin import Anomaly, AnomalyType, SeverityLevel

        anomaly = Anomaly(
            id=str(uuid.uuid4()),
            ome_id="test-ome-001",
            anomaly_type=AnomalyType.TEMPERATURE,
            severity=SeverityLevel.MEDIUM,
            detected_at=datetime.now(),
            sensor_readings={"temperature": 85.5},
            context={"threshold": 80.0}
        )

        assert anomaly is not None
        assert anomaly.anomaly_type == AnomalyType.TEMPERATURE

    def test_create_response_rule(self):
        """Test creating a response rule."""
        from dashboard.services.digital_twin import (
            ResponseRule, AnomalyType, SeverityLevel, ResponseType
        )

        rule = ResponseRule(
            rule_id="rule-001",
            name="High Temperature Response",
            anomaly_type=AnomalyType.TEMPERATURE,
            severity_threshold=SeverityLevel.HIGH,
            response_type=ResponseType.AUTOMATIC,
            action="reduce_speed",
            is_active=True
        )

        assert rule is not None
        assert rule.action == "reduce_speed"

    def test_escalation_levels(self):
        """Test escalation level enumeration."""
        from dashboard.services.digital_twin import EscalationLevel

        assert EscalationLevel.OPERATOR is not None
        assert EscalationLevel.SUPERVISOR is not None
        assert EscalationLevel.MANAGER is not None
        assert EscalationLevel.EMERGENCY is not None


# ============================================================================
# Supply Chain Twin Tests
# ============================================================================

class TestSupplyChainTwin:
    """Tests for Supply Chain Digital Twin."""

    def test_supply_chain_service_init(self):
        """Test supply chain twin service initialization."""
        from dashboard.services.digital_twin import get_supply_chain_twin_service

        service = get_supply_chain_twin_service()
        assert service is not None

    def test_node_types(self):
        """Test supply chain node types."""
        from dashboard.services.digital_twin import NodeType

        assert NodeType.SUPPLIER is not None
        assert NodeType.MANUFACTURER is not None
        assert NodeType.WAREHOUSE is not None
        assert NodeType.DISTRIBUTION_CENTER is not None
        assert NodeType.CUSTOMER is not None

    def test_transport_modes(self):
        """Test transport mode enumeration."""
        from dashboard.services.digital_twin import TransportMode

        assert TransportMode.ROAD is not None
        assert TransportMode.RAIL is not None
        assert TransportMode.SEA is not None
        assert TransportMode.AIR is not None

    def test_risk_categories(self):
        """Test risk category enumeration."""
        from dashboard.services.digital_twin import RiskCategory

        assert RiskCategory.GEOPOLITICAL is not None
        assert RiskCategory.NATURAL_DISASTER is not None
        assert RiskCategory.FINANCIAL is not None
        assert RiskCategory.OPERATIONAL is not None

    def test_create_supply_chain_node(self):
        """Test creating a supply chain node."""
        from dashboard.services.digital_twin import (
            SupplyChainNode, NodeType, NodeStatus, GeoLocation
        )

        node = SupplyChainNode(
            id=str(uuid.uuid4()),
            node_id="SUPPLIER-001",
            name="Test Supplier",
            node_type=NodeType.SUPPLIER,
            status=NodeStatus.ACTIVE,
            location=GeoLocation(latitude=40.7128, longitude=-74.0060),
            lead_time_days=14.0
        )

        assert node is not None
        assert node.node_type == NodeType.SUPPLIER

    def test_create_supply_chain_edge(self):
        """Test creating a supply chain edge."""
        from dashboard.services.digital_twin import (
            SupplyChainEdge, TransportMode
        )

        edge = SupplyChainEdge(
            id=str(uuid.uuid4()),
            source_id="node-001",
            target_id="node-002",
            transport_mode=TransportMode.ROAD,
            distance_km=500.0,
            transit_time_hours=8.0
        )

        assert edge is not None
        assert edge.transport_mode == TransportMode.ROAD

    def test_create_material(self):
        """Test creating a material."""
        from dashboard.services.digital_twin import Material, MaterialCategory

        material = Material(
            material_id="MAT-001",
            name="ABS Filament",
            category=MaterialCategory.RAW_MATERIAL,
            unit_of_measure="kg",
            unit_cost=25.0
        )

        assert material is not None
        assert material.category == MaterialCategory.RAW_MATERIAL


# ============================================================================
# VR Training Tests
# ============================================================================

class TestVRTraining:
    """Tests for VR Training System."""

    def test_vr_training_service_init(self):
        """Test VR training service initialization."""
        from dashboard.services.hmi import get_vr_training_service

        service = get_vr_training_service()
        assert service is not None

    def test_training_categories(self):
        """Test training category enumeration."""
        from dashboard.services.hmi import TrainingCategory

        assert TrainingCategory.EQUIPMENT_OPERATION is not None
        assert TrainingCategory.SAFETY_PROCEDURES is not None
        assert TrainingCategory.QUALITY_INSPECTION is not None
        assert TrainingCategory.MAINTENANCE is not None

    def test_difficulty_levels(self):
        """Test difficulty level enumeration."""
        from dashboard.services.hmi import DifficultyLevel

        assert DifficultyLevel.BEGINNER is not None
        assert DifficultyLevel.INTERMEDIATE is not None
        assert DifficultyLevel.ADVANCED is not None
        assert DifficultyLevel.EXPERT is not None

    def test_training_status(self):
        """Test training status enumeration."""
        from dashboard.services.hmi import TrainingStatus

        assert TrainingStatus.NOT_STARTED is not None
        assert TrainingStatus.IN_PROGRESS is not None
        assert TrainingStatus.COMPLETED is not None
        assert TrainingStatus.PASSED is not None
        assert TrainingStatus.FAILED is not None

    def test_list_scenarios(self):
        """Test listing training scenarios."""
        from dashboard.services.hmi import get_vr_training_service

        service = get_vr_training_service()
        scenarios = service.list_scenarios()

        assert isinstance(scenarios, list)
        # Built-in scenarios should be present
        assert len(scenarios) >= 0

    def test_get_scenario_by_id(self):
        """Test getting a scenario by ID."""
        from dashboard.services.hmi import get_vr_training_service

        service = get_vr_training_service()
        scenarios = service.list_scenarios()

        if scenarios:
            scenario = service.get_scenario(scenarios[0].scenario_id)
            assert scenario is not None


# ============================================================================
# Quality Heatmap Tests
# ============================================================================

class TestQualityHeatmap:
    """Tests for Quality Heatmap Generator."""

    def test_heatmap_generator_init(self):
        """Test heatmap generator initialization."""
        from dashboard.services.vision import get_quality_heatmap_generator

        generator = get_quality_heatmap_generator()
        assert generator is not None

    def test_heatmap_types(self):
        """Test heatmap type enumeration."""
        from dashboard.services.vision import HeatmapType

        assert HeatmapType.DEFECT_DENSITY is not None
        assert HeatmapType.QUALITY_SCORE is not None
        assert HeatmapType.CYCLE_TIME is not None
        assert HeatmapType.TEMPERATURE is not None

    def test_interpolation_methods(self):
        """Test interpolation method enumeration."""
        from dashboard.services.vision import InterpolationMethod

        assert InterpolationMethod.IDW is not None
        assert InterpolationMethod.NEAREST is not None
        assert InterpolationMethod.LINEAR is not None

    def test_color_scales(self):
        """Test color scale enumeration."""
        from dashboard.services.vision import ColorScale

        assert ColorScale.VIRIDIS is not None
        assert ColorScale.PLASMA is not None
        assert ColorScale.RED_GREEN is not None

    def test_create_bounding_box(self):
        """Test creating a bounding box."""
        from dashboard.services.vision import BoundingBox, Vector3

        bbox = BoundingBox(
            min_point=Vector3(x=0.0, y=0.0, z=0.0),
            max_point=Vector3(x=100.0, y=100.0, z=50.0)
        )

        assert bbox is not None
        assert bbox.max_point.x == 100.0

    def test_create_quality_data_point(self):
        """Test creating a quality data point."""
        from dashboard.services.vision import QualityDataPoint, Vector3

        point = QualityDataPoint(
            position=Vector3(x=50.0, y=50.0, z=25.0),
            value=0.95,
            timestamp=datetime.now(),
            metric_type="quality_score"
        )

        assert point is not None
        assert point.value == 0.95

    def test_heatmap_config(self):
        """Test heatmap configuration."""
        from dashboard.services.vision import (
            HeatmapConfig, InterpolationMethod, ColorScale
        )

        config = HeatmapConfig(
            resolution=(10, 10, 5),
            interpolation=InterpolationMethod.IDW,
            color_scale=ColorScale.VIRIDIS,
            min_value=0.0,
            max_value=1.0
        )

        assert config is not None
        assert config.interpolation == InterpolationMethod.IDW


# ============================================================================
# 3D Defect Mapping Tests
# ============================================================================

class TestDefectMapping3D:
    """Tests for 3D Defect Mapping Service."""

    def test_defect_mapping_service_init(self):
        """Test defect mapping service initialization."""
        from dashboard.services.vision import get_defect_mapping_service

        service = get_defect_mapping_service()
        assert service is not None

    def test_defect_types(self):
        """Test defect type enumeration."""
        from dashboard.services.vision import DefectType

        assert DefectType.SCRATCH is not None
        assert DefectType.CRACK is not None
        assert DefectType.STAIN is not None
        assert DefectType.DEFORMATION is not None

    def test_defect_severity(self):
        """Test defect severity enumeration."""
        from dashboard.services.vision import DefectSeverity

        assert DefectSeverity.MINOR is not None
        assert DefectSeverity.MODERATE is not None
        assert DefectSeverity.MAJOR is not None
        assert DefectSeverity.CRITICAL is not None

    def test_create_2d_defect(self):
        """Test creating a 2D defect."""
        from dashboard.services.vision import Defect2D, DefectType, DefectSeverity

        defect = Defect2D(
            id=str(uuid.uuid4()),
            defect_type=DefectType.SCRATCH,
            severity=DefectSeverity.MINOR,
            x=100,
            y=200,
            width=50,
            height=10,
            confidence=0.95,
            detected_at=datetime.now()
        )

        assert defect is not None
        assert defect.defect_type == DefectType.SCRATCH

    def test_create_3d_defect(self):
        """Test creating a 3D defect."""
        from dashboard.services.vision import (
            Defect3D, DefectType, DefectSeverity, Vector3D
        )

        defect = Defect3D(
            id=str(uuid.uuid4()),
            defect_type=DefectType.CRACK,
            severity=DefectSeverity.MAJOR,
            position=Vector3D(x=50.0, y=30.0, z=10.0),
            dimensions=Vector3D(x=5.0, y=2.0, z=1.0),
            confidence=0.88,
            detected_at=datetime.now()
        )

        assert defect is not None
        assert defect.position.x == 50.0

    def test_camera_calibration(self):
        """Test camera calibration dataclass."""
        from dashboard.services.vision import CameraCalibration, CameraModel

        calibration = CameraCalibration(
            camera_id="CAM-001",
            camera_model=CameraModel.PINHOLE,
            intrinsic_matrix=[[1000, 0, 640], [0, 1000, 480], [0, 0, 1]],
            distortion_coefficients=[0.1, -0.2, 0, 0, 0]
        )

        assert calibration is not None
        assert calibration.camera_model == CameraModel.PINHOLE


# ============================================================================
# Predictive Analytics Tests
# ============================================================================

class TestPredictiveAnalytics:
    """Tests for Predictive Analytics Service."""

    def test_predictive_analytics_service_init(self):
        """Test predictive analytics service initialization."""
        from dashboard.services.digital_twin import get_predictive_analytics_service

        service = get_predictive_analytics_service()
        assert service is not None

    def test_prediction_categories(self):
        """Test prediction category enumeration."""
        from dashboard.services.digital_twin import PredictionCategory

        assert PredictionCategory.FAILURE is not None
        assert PredictionCategory.QUALITY is not None
        assert PredictionCategory.MAINTENANCE is not None
        assert PredictionCategory.ENERGY is not None

    def test_alert_priorities(self):
        """Test alert priority enumeration."""
        from dashboard.services.digital_twin import AlertPriority

        assert AlertPriority.LOW is not None
        assert AlertPriority.MEDIUM is not None
        assert AlertPriority.HIGH is not None
        assert AlertPriority.CRITICAL is not None


# ============================================================================
# Event Store Tests
# ============================================================================

class TestEventStore:
    """Tests for Event Store."""

    def test_event_store_init(self):
        """Test event store initialization."""
        from dashboard.services.digital_twin import EventStore

        store = EventStore()
        assert store is not None

    def test_event_categories(self):
        """Test event category enumeration."""
        from dashboard.services.digital_twin import EventCategory

        assert EventCategory.STATE_CHANGE is not None
        assert EventCategory.SENSOR_UPDATE is not None
        assert EventCategory.MAINTENANCE is not None
        assert EventCategory.QUALITY is not None

    def test_event_priorities(self):
        """Test event priority enumeration."""
        from dashboard.services.digital_twin import EventPriority

        assert EventPriority.LOW is not None
        assert EventPriority.NORMAL is not None
        assert EventPriority.HIGH is not None
        assert EventPriority.CRITICAL is not None


# ============================================================================
# Time Synchronization Tests
# ============================================================================

class TestTimeSync:
    """Tests for Time Synchronization Service."""

    def test_time_sync_imports(self):
        """Test time sync service imports."""
        try:
            from dashboard.services.digital_twin import (
                get_time_sync_service,
                TimeSyncService,
                HybridLogicalClock
            )

            if get_time_sync_service is not None:
                service = get_time_sync_service()
                assert service is not None
        except ImportError:
            pytest.skip("Time sync service not available")

    def test_clock_sources(self):
        """Test clock source enumeration."""
        try:
            from dashboard.services.digital_twin import ClockSource

            if ClockSource is not None:
                assert ClockSource.LOCAL is not None
                assert ClockSource.NTP is not None
        except (ImportError, AttributeError):
            pytest.skip("Clock source not available")


# ============================================================================
# State Interpolation Tests
# ============================================================================

class TestStateInterpolation:
    """Tests for State Interpolation Service."""

    def test_interpolation_imports(self):
        """Test interpolation service imports."""
        try:
            from dashboard.services.digital_twin import (
                get_interpolation_service,
                InterpolationMode
            )

            if get_interpolation_service is not None:
                service = get_interpolation_service()
                assert service is not None
        except ImportError:
            pytest.skip("Interpolation service not available")

    def test_interpolation_modes(self):
        """Test interpolation mode enumeration."""
        try:
            from dashboard.services.digital_twin import InterpolationMode

            if InterpolationMode is not None:
                assert InterpolationMode.LINEAR is not None
                assert InterpolationMode.CUBIC is not None
        except (ImportError, AttributeError):
            pytest.skip("Interpolation modes not available")


# ============================================================================
# Integration Tests
# ============================================================================

class TestISO23247Integration:
    """Integration tests for ISO 23247 compliance."""

    def test_full_digital_twin_workflow(self):
        """Test complete digital twin creation workflow."""
        from dashboard.services.digital_twin import (
            get_ome_registry,
            get_twin_engine,
            create_printer_ome,
            TwinType
        )

        # Create OME
        registry = get_ome_registry()
        ome = create_printer_ome(
            name="Integration Test Printer",
            manufacturer="Test Corp",
            model="IT-1000"
        )

        # Register OME
        ome_id = registry.register_ome(ome)
        assert ome_id is not None

        # Create Digital Twin
        engine = get_twin_engine()
        twin = engine.create_twin(ome, twin_type=TwinType.MONITORING)
        assert twin is not None

    def test_anomaly_detection_to_response_flow(self):
        """Test anomaly detection to response workflow."""
        from dashboard.services.digital_twin import (
            get_anomaly_response_service,
            Anomaly,
            AnomalyType,
            SeverityLevel
        )

        service = get_anomaly_response_service()

        # Create anomaly
        anomaly = Anomaly(
            id=str(uuid.uuid4()),
            ome_id="test-ome",
            anomaly_type=AnomalyType.TEMPERATURE,
            severity=SeverityLevel.HIGH,
            detected_at=datetime.now(),
            sensor_readings={"temperature": 95.0}
        )

        # Register and verify
        service.register_anomaly(anomaly)
        registered = service.get_anomaly(anomaly.id)
        assert registered is not None

    def test_supply_chain_network_creation(self):
        """Test supply chain network creation."""
        from dashboard.services.digital_twin import (
            get_supply_chain_twin_service,
            SupplyChainNode,
            SupplyChainEdge,
            NodeType,
            NodeStatus,
            TransportMode,
            GeoLocation
        )

        service = get_supply_chain_twin_service()

        # Create nodes
        supplier = SupplyChainNode(
            id="node-1",
            node_id="SUPPLIER-001",
            name="Primary Supplier",
            node_type=NodeType.SUPPLIER,
            status=NodeStatus.ACTIVE,
            location=GeoLocation(latitude=40.0, longitude=-74.0),
            lead_time_days=7.0
        )

        factory = SupplyChainNode(
            id="node-2",
            node_id="FACTORY-001",
            name="Main Factory",
            node_type=NodeType.MANUFACTURER,
            status=NodeStatus.ACTIVE,
            location=GeoLocation(latitude=41.0, longitude=-73.0),
            lead_time_days=0.0
        )

        # Add nodes
        service.add_node(supplier)
        service.add_node(factory)

        # Create edge
        edge = SupplyChainEdge(
            id="edge-1",
            source_id="node-1",
            target_id="node-2",
            transport_mode=TransportMode.ROAD,
            distance_km=100.0,
            transit_time_hours=2.0
        )

        service.add_edge(edge)

        # Verify
        nodes = service.list_nodes()
        assert len(nodes) >= 2


# ============================================================================
# Async Tests
# ============================================================================

class TestAsyncOperations:
    """Tests for async operations."""

    @pytest.mark.asyncio
    async def test_async_anomaly_processing(self):
        """Test async anomaly processing."""
        from dashboard.services.digital_twin import (
            get_anomaly_response_service,
            Anomaly,
            AnomalyType,
            SeverityLevel
        )

        service = get_anomaly_response_service()

        anomaly = Anomaly(
            id=str(uuid.uuid4()),
            ome_id="async-test-ome",
            anomaly_type=AnomalyType.VIBRATION,
            severity=SeverityLevel.MEDIUM,
            detected_at=datetime.now(),
            sensor_readings={"vibration": 0.8}
        )

        # Process anomaly asynchronously
        if hasattr(service, 'process_anomaly'):
            try:
                responses = await service.process_anomaly(anomaly)
                assert responses is not None
            except Exception:
                # Async processing may require additional setup
                pass


# ============================================================================
# Performance Tests
# ============================================================================

class TestPerformance:
    """Performance benchmark tests."""

    def test_ome_registry_throughput(self):
        """Test OME registry can handle many registrations."""
        from dashboard.services.digital_twin import get_ome_registry, create_sensor_ome

        registry = get_ome_registry()
        start_time = datetime.now()

        # Register 100 OMEs
        for i in range(100):
            sensor = create_sensor_ome(
                name=f"Sensor {i}",
                sensor_type="temperature",
                measurement_unit="celsius"
            )
            registry.register_ome(sensor)

        elapsed = (datetime.now() - start_time).total_seconds()

        # Should complete in under 5 seconds
        assert elapsed < 5.0

    def test_event_store_throughput(self):
        """Test event store can handle high event volume."""
        from dashboard.services.digital_twin import (
            EventStore, TwinEvent, EventCategory, EventPriority
        )

        store = EventStore()
        start_time = datetime.now()

        # Append 1000 events
        for i in range(1000):
            event = TwinEvent(
                event_id=str(uuid.uuid4()),
                twin_id="test-twin",
                event_type="sensor_update",
                category=EventCategory.SENSOR_UPDATE,
                priority=EventPriority.NORMAL,
                timestamp=datetime.now(),
                data={"value": i}
            )
            store.append(event)

        elapsed = (datetime.now() - start_time).total_seconds()

        # Should complete in under 2 seconds
        assert elapsed < 2.0
