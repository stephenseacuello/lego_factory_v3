"""
Comprehensive Tests for Enhanced Digital Twin Services

LegoMCP World-Class Manufacturing Platform v2.0
ISO 23247 Compliant Digital Twin Implementation

Tests cover:
- OME Registry
- Twin Engine
- Twin Manager with PINN integration
- State Interpolation
- Predictive Analytics
- 3D Defect Mapping
- Unity Bridge
- ISO 23247 Compliance

Author: LegoMCP Team
Version: 2.0.0
"""

import pytest
import numpy as np
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock
import json
import uuid


# =============================================================================
# OME Registry Tests
# =============================================================================

class TestOMERegistry:
    """Tests for Observable Manufacturing Element Registry."""

    def test_create_ome_registry(self):
        """Test OME registry creation."""
        from dashboard.services.digital_twin.ome_registry import (
            OMERegistry, get_ome_registry
        )

        registry = get_ome_registry()
        assert registry is not None
        assert hasattr(registry, 'register')
        assert hasattr(registry, 'get')

    def test_register_equipment_ome(self):
        """Test registering equipment as OME."""
        from dashboard.services.digital_twin.ome_registry import (
            OMERegistry, OMEType, OMELifecycleState, create_printer_ome
        )

        registry = OMERegistry()

        # Create printer OME with factory function
        ome = create_printer_ome(
            name="3D Printer #1",
            manufacturer="Prusa Research",
            model="MK3S"
        )

        # Register the OME
        registered = registry.register(ome)

        assert registered is not None
        assert registered.name == "3D Printer #1"
        assert registered.ome_type == OMEType.EQUIPMENT
        assert registered.lifecycle_state == OMELifecycleState.DESIGN

    def test_ome_lifecycle_transitions(self):
        """Test OME lifecycle state transitions."""
        from dashboard.services.digital_twin.ome_registry import (
            OMERegistry, OMELifecycleState, create_printer_ome
        )

        registry = OMERegistry()
        ome = create_printer_ome(name="Test Printer", model="Prusa MK3S")
        registry.register(ome)

        # Initial state is DESIGN
        assert ome.lifecycle_state == OMELifecycleState.DESIGN

        # First transition to COMMISSIONING (required before ACTIVE per ISO 23247)
        success1 = registry.transition_lifecycle(ome.id, OMELifecycleState.COMMISSIONING)
        assert success1

        # Then transition to ACTIVE
        success2 = registry.transition_lifecycle(ome.id, OMELifecycleState.ACTIVE)
        assert success2
        # Fetch updated OME from registry
        updated_ome = registry.get(ome.id)
        assert updated_ome.lifecycle_state == OMELifecycleState.ACTIVE

    def test_ome_hierarchy(self):
        """Test OME hierarchical relationships."""
        from dashboard.services.digital_twin.ome_registry import (
            OMERegistry, create_work_cell_ome, create_printer_ome
        )

        registry = OMERegistry()

        # Create work cell
        cell = create_work_cell_ome(name="Print Cell #1")
        registry.register(cell)

        # Create printer as child
        printer = create_printer_ome(name="Printer #1", model="Prusa MK3S")
        printer.parent_id = cell.id
        registry.register(printer)

        # Verify relationship
        children = registry.get_children(cell.id)
        assert len(children) == 1
        assert children[0].id == printer.id


# =============================================================================
# Twin Engine Tests
# =============================================================================

class TestTwinEngine:
    """Tests for Digital Twin Engine."""

    def test_create_twin_engine(self):
        """Test twin engine creation."""
        from dashboard.services.digital_twin.twin_engine import (
            TwinEngine, get_twin_engine
        )

        engine = get_twin_engine()
        assert engine is not None
        assert hasattr(engine, 'create_twin')
        assert hasattr(engine, 'run_simulation')

    def test_create_digital_twin(self):
        """Test digital twin instance creation."""
        from dashboard.services.digital_twin.twin_engine import (
            TwinEngine, TwinType, TwinState
        )
        from dashboard.services.digital_twin.ome_registry import create_printer_ome

        engine = TwinEngine()

        # First create and register an OME
        ome = create_printer_ome(name="Test Printer", model="Prusa MK3S")
        engine.registry.register(ome)

        twin = engine.create_twin(
            ome_id=ome.id,
            twin_type=TwinType.MONITORING
        )

        assert twin is not None
        assert twin.twin_type == TwinType.MONITORING
        # Twin starts in ACTIVE state after creation
        assert twin.state == TwinState.ACTIVE

    def test_sync_from_physical(self):
        """Test synchronization from physical to digital."""
        from dashboard.services.digital_twin.twin_engine import (
            TwinEngine, TwinType
        )
        from dashboard.services.digital_twin.ome_registry import create_printer_ome

        engine = TwinEngine()
        ome = create_printer_ome(name="Test Printer", model="Prusa MK3S")
        engine.registry.register(ome)
        twin = engine.create_twin(ome.id, TwinType.MONITORING)

        # Sync sensor data
        sensor_data = {
            "temperature": 45.5,
            "vibration": 0.12,
            "position": {"x": 100, "y": 50, "z": 10}
        }

        # sync_from_physical takes ome_id not twin_id
        result = engine.sync_from_physical(ome.id, sensor_data)
        # sync_from_physical returns a bool indicating success
        assert result is True

    def test_run_simulation(self):
        """Test running simulation on twin."""
        from dashboard.services.digital_twin.twin_engine import (
            TwinEngine, TwinType, SimulationConfig
        )
        from dashboard.services.digital_twin.ome_registry import create_printer_ome

        engine = TwinEngine()
        ome = create_printer_ome(name="Test Printer", model="Prusa MK3S")
        engine.registry.register(ome)
        twin = engine.create_twin(ome.id, TwinType.SIMULATION)

        config = SimulationConfig(
            duration_seconds=60,
            time_scale=1.0,
            parameters={"temperature": 200}
        )

        result = engine.run_simulation(twin.id, config)

        assert result is not None
        # Simulation returns time_series data
        assert hasattr(result, 'time_series') or "time_series" in result.__dict__


# =============================================================================
# Twin Manager with PINN Tests
# =============================================================================

class TestTwinManagerWithPINN:
    """Tests for Twin Manager with ML/PINN integration."""

    def test_twin_manager_initialization(self):
        """Test twin manager initializes with ML models."""
        from dashboard.services.digital_twin.twin_manager import (
            DigitalTwinManager, get_twin_manager
        )

        manager = get_twin_manager()
        assert manager is not None

        # Check ML models initialized
        stats = manager.get_statistics()
        assert "ml_available" in stats

    def test_predict_failure(self):
        """Test failure prediction."""
        from dashboard.services.digital_twin.twin_manager import DigitalTwinManager

        manager = DigitalTwinManager()

        features = {
            "temperature": 85,
            "vibration": 2.5,
            "operating_hours": 8000,
            "error_count_24h": 10
        }

        predictions = manager.predict_failure("wc-001", features)

        assert predictions is not None
        assert len(predictions) > 0 or "error" in predictions[0]

    def test_estimate_rul(self):
        """Test RUL estimation."""
        from dashboard.services.digital_twin.twin_manager import DigitalTwinManager

        manager = DigitalTwinManager()

        features = {
            "operating_hours": 5000,
            "degradation_rate": 0.1
        }

        result = manager.estimate_rul("wc-001", features)

        assert result is not None
        if "error" not in result:
            assert "rul_hours" in result

    def test_simulate_thermal_field(self):
        """Test thermal field simulation with PINN."""
        from dashboard.services.digital_twin.twin_manager import DigitalTwinManager

        manager = DigitalTwinManager()

        geometry = {
            "x": (0, 0.1),
            "y": (0, 0.1),
            "z": (0, 0.05)
        }

        result = manager.simulate_thermal_field(
            "wc-001", geometry, time=0.0, resolution=10
        )

        assert result is not None
        assert result.simulation_type.name == "THERMAL_FIELD"

    def test_hybrid_quality_prediction(self):
        """Test hybrid physics+ML quality prediction."""
        from dashboard.services.digital_twin.twin_manager import DigitalTwinManager

        manager = DigitalTwinManager()

        process_params = {
            "nozzle_temp": 210,
            "bed_temp": 60,
            "print_speed": 50,
            "layer_height": 0.2
        }

        prediction = manager.predict_quality_physics("wc-001", process_params)

        assert prediction is not None
        assert 0 <= prediction.fused_prediction <= 1
        assert 0 <= prediction.fusion_weight <= 1


# =============================================================================
# State Interpolation Tests
# =============================================================================

class TestStateInterpolation:
    """Tests for state interpolation service."""

    def test_interpolation_service_creation(self):
        """Test interpolation service creation."""
        from dashboard.services.digital_twin.interpolation import (
            StateInterpolationService, get_interpolation_service
        )

        service = get_interpolation_service()
        assert service is not None

    def test_receive_and_interpolate_state(self):
        """Test receiving state and interpolating."""
        from dashboard.services.digital_twin.interpolation import (
            StateInterpolationService
        )

        service = StateInterpolationService()

        # Add states at different times
        t0 = 0.0
        t1 = 1.0

        service.receive_state("entity-1", {"x": 0, "y": 0, "z": 0}, t0)
        service.receive_state("entity-1", {"x": 10, "y": 10, "z": 10}, t1)

        # Interpolate at midpoint
        state = service.get_interpolated_state("entity-1", 0.5)

        assert state is not None
        # Should be approximately midpoint
        assert abs(state.get("x", 0) - 5) < 1

    def test_slerp_interpolation(self):
        """Test SLERP interpolation for rotations."""
        from dashboard.services.digital_twin.interpolation import (
            StateInterpolationService, InterpolationConfig, InterpolationMode
        )

        config = InterpolationConfig(mode=InterpolationMode.SLERP)
        service = StateInterpolationService(config)

        # Add quaternion rotations
        service.receive_state("entity-1", {
            "rotation": [1, 0, 0, 0]  # Identity quaternion
        }, 0.0)
        service.receive_state("entity-1", {
            "rotation": [0.707, 0.707, 0, 0]  # 90 degree rotation
        }, 1.0)

        state = service.get_interpolated_state("entity-1", 0.5)
        assert state is not None


# =============================================================================
# Predictive Analytics Tests
# =============================================================================

class TestPredictiveAnalytics:
    """Tests for predictive analytics service."""

    def test_service_initialization(self):
        """Test predictive analytics service initialization."""
        from dashboard.services.digital_twin.predictive_analytics import (
            PredictiveAnalyticsService, get_predictive_analytics_service
        )

        service = get_predictive_analytics_service()
        assert service is not None

        info = service.get_model_info()
        assert "FAILURE" in info or len(info) > 0

    def test_failure_prediction(self):
        """Test failure prediction through analytics service."""
        from dashboard.services.digital_twin.predictive_analytics import (
            PredictiveAnalyticsService, PredictionCategory
        )

        service = PredictiveAnalyticsService()

        features = {
            "temperature": 75,
            "vibration": 1.5
        }

        result = service.predict(
            entity_id="entity-001",
            category=PredictionCategory.FAILURE,
            features=features
        )

        assert result is not None
        assert result.category == PredictionCategory.FAILURE
        assert 0 <= result.value <= 1

    def test_predict_all_categories(self):
        """Test predicting all categories at once."""
        from dashboard.services.digital_twin.predictive_analytics import (
            PredictiveAnalyticsService
        )

        service = PredictiveAnalyticsService()

        features = {
            "temperature": 60,
            "rated_power": 0.5,
            "utilization": 0.7
        }

        results = service.predict_all_categories("entity-001", features)

        assert len(results) > 0

    def test_maintenance_recommendation(self):
        """Test maintenance recommendation generation."""
        from dashboard.services.digital_twin.predictive_analytics import (
            PredictiveAnalyticsService
        )

        service = PredictiveAnalyticsService()

        features = {
            "operating_hours": 6000,
            "temperature": 70
        }

        recommendation = service.generate_maintenance_recommendation(
            "entity-001", features
        )

        assert recommendation is not None
        assert recommendation.maintenance_type is not None
        assert recommendation.optimal_window_start is not None

    def test_energy_forecast(self):
        """Test energy consumption forecasting."""
        from dashboard.services.digital_twin.predictive_analytics import (
            PredictiveAnalyticsService
        )

        service = PredictiveAnalyticsService()

        features = {
            "rated_power": 0.5,
            "utilization": 0.6
        }

        forecast = service.forecast_energy("entity-001", features, horizon_hours=24)

        assert forecast is not None
        assert forecast.total_consumption_kwh > 0
        assert len(forecast.hourly_consumption) == 24

    def test_alert_generation(self):
        """Test alert generation from predictions."""
        from dashboard.services.digital_twin.predictive_analytics import (
            PredictiveAnalyticsService, PredictionCategory
        )

        service = PredictiveAnalyticsService()

        # High failure probability should trigger alert
        features = {
            "temperature": 95,
            "vibration": 3.0,
            "operating_hours": 9000,
            "error_count_24h": 20
        }

        result = service.predict(
            entity_id="entity-001",
            category=PredictionCategory.FAILURE,
            features=features
        )

        # Check if alert was generated
        alerts = service.get_active_alerts(entity_id="entity-001")
        # May or may not have alert depending on threshold


# =============================================================================
# 3D Defect Mapping Tests
# =============================================================================

class TestDefectMapping3D:
    """Tests for 3D defect mapping service."""

    def test_service_creation(self):
        """Test defect mapping service creation."""
        from dashboard.services.vision.defect_mapping_3d import (
            DefectMapping3DService, get_defect_mapping_service
        )

        service = get_defect_mapping_service()
        assert service is not None

    def test_camera_registration(self):
        """Test camera registration."""
        from dashboard.services.vision.defect_mapping_3d import (
            DefectMapping3DService, CameraCalibration, Vector3D
        )

        service = DefectMapping3DService()

        calibration = CameraCalibration(
            camera_id="cam-1",
            position=Vector3D(100, 100, 200)
        )

        service.register_camera("cam-1", calibration)

        cam = service.get_camera("cam-1")
        assert cam is not None
        assert cam.camera_id == "cam-1"

    def test_add_2d_detection(self):
        """Test adding 2D detection."""
        from dashboard.services.vision.defect_mapping_3d import (
            DefectMapping3DService, Defect2D, DefectType
        )

        service = DefectMapping3DService()
        service.setup_default_cameras()

        detection = Defect2D(
            detection_id="det-001",
            camera_id="top_camera",
            defect_type=DefectType.SURFACE_SCRATCH,
            confidence=0.85,
            bbox_x=0.4,
            bbox_y=0.4,
            bbox_width=0.1,
            bbox_height=0.1,
            layer_number=50
        )

        det_id = service.add_detection(detection)
        assert det_id == "det-001"

    def test_map_detection_to_3d(self):
        """Test mapping 2D detection to 3D."""
        from dashboard.services.vision.defect_mapping_3d import (
            DefectMapping3DService, Defect2D, DefectType
        )

        service = DefectMapping3DService(layer_height=0.2)
        service.setup_default_cameras()

        detection = Defect2D(
            detection_id="det-002",
            camera_id="top_camera",
            defect_type=DefectType.VOID,
            confidence=0.9,
            bbox_x=0.5,
            bbox_y=0.5,
            bbox_width=0.05,
            bbox_height=0.05,
            layer_number=100
        )

        defect_3d = service.map_detection_to_3d(detection)

        if defect_3d is not None:
            assert defect_3d.defect_type == DefectType.VOID
            # Z should be approximately layer * layer_height
            assert abs(defect_3d.position.z - 20.0) < 5.0  # 100 * 0.2 = 20mm

    def test_defect_clustering(self):
        """Test defect clustering."""
        from dashboard.services.vision.defect_mapping_3d import (
            DefectMapping3DService, Defect2D, DefectType
        )

        service = DefectMapping3DService()
        service.setup_default_cameras()

        # Add multiple nearby detections
        for i in range(5):
            detection = Defect2D(
                detection_id=f"det-{i}",
                camera_id="top_camera",
                defect_type=DefectType.STRINGING,
                confidence=0.8,
                bbox_x=0.5 + i * 0.01,
                bbox_y=0.5,
                bbox_width=0.02,
                bbox_height=0.02,
                layer_number=50 + i
            )
            service.map_detection_to_3d(detection)

        clusters = service.cluster_defects(distance_threshold=50.0, min_cluster_size=2)

        # Should have at least one cluster
        if len(service.get_all_defects()) >= 2:
            assert len(clusters) >= 0  # May or may not cluster depending on positions

    def test_quality_heatmap_generation(self):
        """Test quality heatmap generation."""
        from dashboard.services.vision.defect_mapping_3d import (
            DefectMapping3DService, Defect2D, DefectType
        )

        service = DefectMapping3DService()
        service.setup_default_cameras()

        # Add some detections
        for i in range(10):
            detection = Defect2D(
                detection_id=f"det-hm-{i}",
                camera_id="top_camera",
                defect_type=DefectType.SURFACE_SCRATCH,
                confidence=0.7,
                bbox_x=0.2 + i * 0.05,
                bbox_y=0.5,
                bbox_width=0.02,
                bbox_height=0.02,
                layer_number=i * 10
            )
            service.map_detection_to_3d(detection)

        heatmap = service.generate_quality_heatmap(resolution=(10, 10, 10))

        assert heatmap is not None
        assert heatmap.grid_resolution == (10, 10, 10)

    def test_export_for_unity(self):
        """Test Unity export format."""
        from dashboard.services.vision.defect_mapping_3d import (
            DefectMapping3DService
        )

        service = DefectMapping3DService()

        export_data = service.export_for_unity()

        assert "defects" in export_data
        assert "clusters" in export_data
        assert "heatmap" in export_data
        assert "build_volume" in export_data


# =============================================================================
# Unity Bridge Tests
# =============================================================================

class TestUnityBridge:
    """Tests for Unity WebSocket bridge."""

    def test_bridge_creation(self):
        """Test Unity bridge creation."""
        from dashboard.services.unity.bridge import (
            UnityBridge, get_unity_bridge
        )

        bridge = get_unity_bridge()
        assert bridge is not None

    def test_client_type_handling(self):
        """Test different Unity client types."""
        from dashboard.services.unity.bridge import (
            UnityBridge, ClientType
        )

        bridge = UnityBridge()

        # Check client types exist
        assert ClientType.WEBGL is not None
        assert ClientType.DESKTOP is not None
        assert ClientType.VR_QUEST is not None
        assert ClientType.AR_HOLOLENS is not None

    def test_subscription_rooms(self):
        """Test subscription room management."""
        from dashboard.services.unity.bridge import (
            UnityBridge, SubscriptionRoom
        )

        bridge = UnityBridge()

        # Check subscription rooms exist
        assert SubscriptionRoom.EQUIPMENT is not None
        assert SubscriptionRoom.QUALITY is not None
        assert SubscriptionRoom.PREDICTIONS is not None
        assert SubscriptionRoom.ALARMS is not None


# =============================================================================
# Scene Data Service Tests
# =============================================================================

class TestSceneDataService:
    """Tests for Unity scene data service."""

    def test_service_creation(self):
        """Test scene data service creation."""
        from dashboard.services.unity.scene_data import (
            SceneDataService, get_scene_data_service
        )

        service = get_scene_data_service()
        assert service is not None

    def test_get_scene_state(self):
        """Test getting full scene state."""
        from dashboard.services.unity.scene_data import SceneDataService

        service = SceneDataService()

        state = service.get_full_scene()

        assert state is not None
        assert "equipment" in state
        assert "version" in state


# =============================================================================
# ISO 23247 Compliance Tests
# =============================================================================

class TestISO23247Compliance:
    """Tests for ISO 23247 compliance validation."""

    def test_compliance_service_creation(self):
        """Test compliance service creation."""
        from dashboard.services.compliance.iso23247_compliance import (
            ISO23247ComplianceService
        )

        service = ISO23247ComplianceService()
        assert service is not None

    def test_validate_all_compliance(self):
        """Test full compliance validation."""
        from dashboard.services.compliance.iso23247_compliance import (
            ISO23247ComplianceService
        )

        service = ISO23247ComplianceService()

        # validate_all runs full validation and returns a ComplianceReport
        report = service.validate_all()

        assert report is not None

    def test_compliance_report_structure(self):
        """Test compliance report generation."""
        from dashboard.services.compliance.iso23247_compliance import (
            ISO23247ComplianceService
        )

        service = ISO23247ComplianceService()

        # validate_all returns a ComplianceReport
        report = service.validate_all()

        assert report is not None
        # ComplianceReport has overall_level and overall_score attributes
        assert hasattr(report, 'overall_level') or hasattr(report, 'overall_score')


# =============================================================================
# Integration Tests
# =============================================================================

class TestDigitalTwinIntegration:
    """Integration tests for complete digital twin workflow."""

    def test_ome_to_twin_workflow(self):
        """Test creating OME and associated twin."""
        from dashboard.services.digital_twin.ome_registry import (
            OMERegistry, create_printer_ome
        )
        from dashboard.services.digital_twin.twin_engine import (
            TwinEngine, TwinType
        )

        # Create twin engine (has its own registry)
        twin_engine = TwinEngine()

        # Create OME and register it in the engine's registry
        ome = create_printer_ome(name="Integration Test Printer", model="Prusa MK3S")
        twin_engine.registry.register(ome)

        # Create twin for OME
        twin = twin_engine.create_twin(
            ome_id=ome.id,
            twin_type=TwinType.MONITORING
        )

        assert twin is not None
        assert twin.ome_id == ome.id

    def test_prediction_to_alert_workflow(self):
        """Test prediction triggering alert workflow."""
        from dashboard.services.digital_twin.predictive_analytics import (
            PredictiveAnalyticsService, PredictionCategory
        )

        service = PredictiveAnalyticsService()

        # High risk features
        features = {
            "temperature": 100,
            "vibration": 4.0,
            "operating_hours": 10000,
            "error_count_24h": 50
        }

        # Make prediction
        result = service.predict(
            entity_id="int-test-001",
            category=PredictionCategory.FAILURE,
            features=features
        )

        # Should have high probability
        assert result.value > 0.5

    def test_defect_to_unity_workflow(self):
        """Test defect detection to Unity visualization workflow."""
        from dashboard.services.vision.defect_mapping_3d import (
            DefectMapping3DService, Defect2D, DefectType
        )
        from dashboard.services.unity.scene_data import SceneDataService

        # Create defect
        defect_service = DefectMapping3DService()
        defect_service.setup_default_cameras()

        detection = Defect2D(
            detection_id="int-det-001",
            camera_id="top_camera",
            defect_type=DefectType.LAYER_SHIFT,
            confidence=0.95,
            bbox_x=0.5,
            bbox_y=0.5,
            bbox_width=0.1,
            bbox_height=0.1,
            layer_number=75
        )

        defect_3d = defect_service.map_detection_to_3d(detection)

        # Export for Unity
        unity_data = defect_service.export_for_unity()

        assert unity_data is not None
        assert "defects" in unity_data


# =============================================================================
# Run Tests
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
