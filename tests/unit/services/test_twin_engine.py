"""
LEGO Factory v3 - Digital Twin Engine Unit Tests
================================================
Tests for digital twin engine functionality.
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch, PropertyMock

from services.advanced.digital_twin.twin_engine import (
    TwinEngine,
    DigitalTwinInstance,
    TwinType,
    TwinState,
    SyncMode,
    SimulationConfig,
    RuleBasedModel,
    PhysicsModel,
    BehaviorModelInterface,
)


class TestTwinType:
    """Test TwinType enum."""

    def test_twin_types_exist(self):
        """Test all expected twin types exist."""
        assert TwinType.MONITORING.value == "monitoring"
        assert TwinType.SIMULATION.value == "simulation"
        assert TwinType.PREDICTIVE.value == "predictive"
        assert TwinType.OPTIMIZATION.value == "optimization"
        assert TwinType.TRAINING.value == "training"


class TestTwinState:
    """Test TwinState enum."""

    def test_twin_states_exist(self):
        """Test all expected twin states exist."""
        assert TwinState.INITIALIZING.value == "initializing"
        assert TwinState.SYNCING.value == "syncing"
        assert TwinState.ACTIVE.value == "active"
        assert TwinState.PAUSED.value == "paused"
        assert TwinState.SIMULATING.value == "simulating"
        assert TwinState.ERROR.value == "error"
        assert TwinState.STOPPED.value == "stopped"


class TestSyncMode:
    """Test SyncMode enum."""

    def test_sync_modes_exist(self):
        """Test all expected sync modes exist."""
        assert SyncMode.REALTIME.value == "realtime"
        assert SyncMode.PERIODIC.value == "periodic"
        assert SyncMode.ON_DEMAND.value == "on_demand"
        assert SyncMode.PLAYBACK.value == "playback"


class TestSimulationConfig:
    """Test SimulationConfig dataclass."""

    def test_default_config(self):
        """Test default simulation configuration."""
        config = SimulationConfig()
        assert config.duration_seconds == 3600.0
        assert config.time_scale == 1.0
        assert config.record_interval_seconds == 1.0
        assert config.random_seed is None

    def test_custom_config(self):
        """Test custom simulation configuration."""
        config = SimulationConfig(
            duration_seconds=7200.0,
            time_scale=10.0,
            initial_state={"temp": 25.0},
            parameters={"speed": 100},
            random_seed=42,
        )
        assert config.duration_seconds == 7200.0
        assert config.time_scale == 10.0
        assert config.initial_state["temp"] == 25.0
        assert config.random_seed == 42


class TestRuleBasedModel:
    """Test RuleBasedModel class."""

    def test_rule_based_model_creation(self):
        """Test creating a rule-based model."""
        model = RuleBasedModel()
        assert model.rules == []

    def test_add_rule(self):
        """Test adding rules to model."""
        model = RuleBasedModel()
        model.add_rule(
            condition={"status": "running"},
            action={"power": 100},
            priority=1,
        )
        assert len(model.rules) == 1
        assert model.rules[0]["priority"] == 1

    def test_rule_priority_sorting(self):
        """Test rules are sorted by priority."""
        model = RuleBasedModel()
        model.add_rule(condition={"a": 1}, action={"b": 1}, priority=1)
        model.add_rule(condition={"a": 2}, action={"b": 2}, priority=3)
        model.add_rule(condition={"a": 3}, action={"b": 3}, priority=2)

        # Highest priority first
        assert model.rules[0]["priority"] == 3
        assert model.rules[1]["priority"] == 2
        assert model.rules[2]["priority"] == 1

    def test_predict_applies_matching_rule(self):
        """Test predict applies matching rules."""
        model = RuleBasedModel()
        model.add_rule(
            condition={"status": "idle"},
            action={"power": 0},
        )
        model.add_rule(
            condition={"status": "running"},
            action={"power": 100},
        )

        state = {"status": "running", "power": 50}
        new_state = model.predict(state, dt=1.0)
        assert new_state["power"] == 100

    def test_predict_no_matching_rule(self):
        """Test predict with no matching rules returns state unchanged."""
        model = RuleBasedModel()
        model.add_rule(
            condition={"status": "running"},
            action={"power": 100},
        )

        state = {"status": "idle", "power": 50}
        new_state = model.predict(state, dt=1.0)
        assert new_state["power"] == 50  # Unchanged

    def test_get_constraints(self):
        """Test get_constraints returns empty list for rule-based model."""
        model = RuleBasedModel()
        assert model.get_constraints() == []


class TestPhysicsModel:
    """Test PhysicsModel class."""

    def test_physics_model_creation(self):
        """Test creating a physics model."""
        model = PhysicsModel()
        assert model.thermal_conductivity == 0.1
        assert model.cooling_rate == 0.05
        assert model.heating_rate == 0.2
        assert model.ambient_temp == 22.0

    def test_physics_model_custom_params(self):
        """Test physics model with custom parameters."""
        model = PhysicsModel(model_params={
            "thermal_conductivity": 0.2,
            "ambient_temp": 25.0,
        })
        assert model.thermal_conductivity == 0.2
        assert model.ambient_temp == 25.0

    def test_predict_temperature_cooling(self):
        """Test temperature cooling dynamics."""
        model = PhysicsModel()
        state = {
            "temperatures": {"hotend": 200.0},
            "target_temperatures": {"hotend": 22.0},  # Ambient
            "heating_active": False,
            "positions": {},
            "status": "idle",
        }
        new_state = model.predict(state, dt=1.0)
        # Temperature should decrease toward ambient
        assert new_state["temperatures"]["hotend"] < 200.0

    def test_predict_temperature_heating(self):
        """Test temperature heating dynamics."""
        model = PhysicsModel()
        state = {
            "temperatures": {"hotend": 22.0},
            "target_temperatures": {"hotend": 200.0},
            "heating_active": True,
            "positions": {},
            "status": "printing",
        }
        new_state = model.predict(state, dt=1.0)
        # Temperature should increase toward target
        assert new_state["temperatures"]["hotend"] > 22.0

    def test_predict_position_movement(self):
        """Test position movement dynamics."""
        model = PhysicsModel()
        state = {
            "temperatures": {},
            "positions": {"x": 0.0, "y": 0.0},
            "target_positions": {"x": 100.0, "y": 50.0},
            "speed": 50.0,  # mm/s
            "status": "printing",
        }
        new_state = model.predict(state, dt=1.0)
        # Positions should move toward targets
        assert new_state["positions"]["x"] > 0.0
        assert new_state["positions"]["y"] > 0.0

    def test_get_constraints(self):
        """Test physics model returns constraints."""
        model = PhysicsModel()
        constraints = model.get_constraints()
        assert len(constraints) == 3
        constraint_types = [c["type"] for c in constraints]
        assert "temperature" in constraint_types
        assert "position" in constraint_types
        assert "power" in constraint_types


class TestDigitalTwinInstance:
    """Test DigitalTwinInstance class."""

    def test_twin_instance_creation(self):
        """Test creating a digital twin instance."""
        twin = DigitalTwinInstance(
            ome_id="machine-001",
            twin_type=TwinType.MONITORING,
        )
        assert twin.ome_id == "machine-001"
        assert twin.twin_type == TwinType.MONITORING
        assert twin.state == TwinState.INITIALIZING
        assert isinstance(twin.id, str)
        assert len(twin.id) > 0

    def test_update_state(self):
        """Test updating twin state."""
        twin = DigitalTwinInstance(ome_id="machine-001")
        twin.update_state({"temperature": 25.0, "pressure": 100.0})

        assert twin.current_state["temperature"] == 25.0
        assert twin.current_state["pressure"] == 100.0
        assert twin.total_updates == 1

    def test_update_state_tracks_history(self):
        """Test state updates are tracked in history."""
        twin = DigitalTwinInstance(ome_id="machine-001")
        twin.update_state({"temp": 20.0})
        twin.update_state({"temp": 25.0})
        twin.update_state({"temp": 30.0})

        assert len(twin.state_history) == 3
        assert twin.total_updates == 3

    def test_state_history_size_limit(self):
        """Test state history respects size limit."""
        twin = DigitalTwinInstance(ome_id="machine-001", max_history_size=5)

        for i in range(10):
            twin.update_state({"value": i})

        assert len(twin.state_history) == 5

    def test_step_with_behavior_model(self):
        """Test stepping simulation with behavior model."""
        model = RuleBasedModel()
        model.add_rule(
            condition={},  # Always matches
            action={"step_count": 1},
        )

        twin = DigitalTwinInstance(
            ome_id="machine-001",
            behavior_model=model,
        )
        twin.current_state = {"step_count": 0}

        result = twin.step(dt=1.0)
        assert result["step_count"] == 1

    def test_step_without_behavior_model(self):
        """Test stepping without behavior model returns current state."""
        twin = DigitalTwinInstance(ome_id="machine-001")
        twin.current_state = {"value": 42}

        result = twin.step(dt=1.0)
        assert result["value"] == 42

    def test_predict_future(self):
        """Test predicting future states."""
        model = PhysicsModel()
        twin = DigitalTwinInstance(
            ome_id="machine-001",
            behavior_model=model,
        )
        twin.current_state = {
            "temperatures": {"hotend": 200.0},
            "target_temperatures": {"hotend": 22.0},
            "heating_active": False,
            "positions": {},
            "status": "idle",
        }

        predictions = twin.predict_future(horizon_seconds=10.0, steps=10)
        assert len(predictions) == 10
        # Temperature should decrease over time
        first_temp = predictions[0]["state"]["temperatures"]["hotend"]
        last_temp = predictions[-1]["state"]["temperatures"]["hotend"]
        assert last_temp < first_temp

    def test_to_dict(self):
        """Test converting twin to dictionary."""
        twin = DigitalTwinInstance(
            ome_id="machine-001",
            twin_type=TwinType.SIMULATION,
            sync_mode=SyncMode.PERIODIC,
        )
        result = twin.to_dict()

        assert result["ome_id"] == "machine-001"
        assert result["twin_type"] == "simulation"
        assert result["sync_mode"] == "periodic"
        assert "id" in result
        assert "created_at" in result


class TestTwinEngine:
    """Test TwinEngine class."""

    @pytest.fixture
    def mock_registry(self):
        """Create a mock OME registry."""
        registry = MagicMock()

        # Create mock OME
        mock_ome = MagicMock()
        mock_ome.id = "ome-001"
        mock_ome.namespace = "default"
        mock_ome.twin_instance_ids = []
        mock_ome.dynamic_attributes = MagicMock()
        mock_ome.dynamic_attributes.status = "idle"
        mock_ome.dynamic_attributes.temperatures = {"hotend": 22.0}
        mock_ome.dynamic_attributes.positions = {"x": 0, "y": 0, "z": 0}
        mock_ome.dynamic_attributes.speeds = {}
        mock_ome.dynamic_attributes.oee = 0.85
        mock_ome.dynamic_attributes.health_score = 95
        mock_ome.dynamic_attributes.power_consumption_watts = 50
        mock_ome.dynamic_attributes.current_job_id = None
        mock_ome.dynamic_attributes.to_dict.return_value = {}
        mock_ome.lifecycle_state = MagicMock()
        mock_ome.lifecycle_state.value = "active"

        registry.get.return_value = mock_ome
        registry.get_all.return_value = [mock_ome]
        registry.add_event_listener = MagicMock()
        registry.get_unity_scene_data.return_value = {"equipment": []}

        return registry

    @pytest.fixture
    def twin_engine(self, mock_registry):
        """Create a twin engine instance."""
        return TwinEngine(ome_registry=mock_registry)

    def test_engine_initialization(self, twin_engine):
        """Test twin engine initializes correctly."""
        assert twin_engine is not None
        assert len(twin_engine._twins) == 0
        assert twin_engine._sync_running is False

    def test_create_twin(self, twin_engine):
        """Test creating a digital twin."""
        twin = twin_engine.create_twin(
            ome_id="ome-001",
            twin_type=TwinType.MONITORING,
        )

        assert twin is not None
        assert twin.ome_id == "ome-001"
        assert twin.twin_type == TwinType.MONITORING
        assert twin.state == TwinState.ACTIVE
        assert twin.id in twin_engine._twins

    def test_create_twin_invalid_ome(self, twin_engine, mock_registry):
        """Test creating twin for invalid OME raises error."""
        mock_registry.get.return_value = None

        with pytest.raises(ValueError, match="not found"):
            twin_engine.create_twin(ome_id="invalid-ome")

    def test_get_twin(self, twin_engine):
        """Test getting a twin by ID."""
        created = twin_engine.create_twin(ome_id="ome-001")
        retrieved = twin_engine.get_twin(created.id)

        assert retrieved is created

    def test_get_twin_not_found(self, twin_engine):
        """Test getting non-existent twin returns None."""
        result = twin_engine.get_twin("nonexistent-id")
        assert result is None

    def test_get_twins_for_ome(self, twin_engine):
        """Test getting all twins for an OME."""
        twin1 = twin_engine.create_twin(ome_id="ome-001")
        twin2 = twin_engine.create_twin(ome_id="ome-001")

        twins = twin_engine.get_twins_for_ome("ome-001")
        assert len(twins) == 2
        assert twin1 in twins
        assert twin2 in twins

    def test_delete_twin(self, twin_engine):
        """Test deleting a twin."""
        twin = twin_engine.create_twin(ome_id="ome-001")
        twin_id = twin.id

        result = twin_engine.delete_twin(twin_id)
        assert result is True
        assert twin_engine.get_twin(twin_id) is None

    def test_delete_twin_not_found(self, twin_engine):
        """Test deleting non-existent twin returns False."""
        result = twin_engine.delete_twin("nonexistent-id")
        assert result is False

    def test_pause_and_resume_twin(self, twin_engine):
        """Test pausing and resuming a twin."""
        twin = twin_engine.create_twin(ome_id="ome-001")

        # Pause
        result = twin_engine.pause_twin(twin.id)
        assert result is True
        assert twin.state == TwinState.PAUSED

        # Resume
        result = twin_engine.resume_twin(twin.id)
        assert result is True
        assert twin.state == TwinState.ACTIVE

    def test_get_all_twins(self, twin_engine):
        """Test getting all twins."""
        twin_engine.create_twin(ome_id="ome-001")
        twin_engine.create_twin(ome_id="ome-001")

        all_twins = twin_engine.get_all_twins()
        assert len(all_twins) == 2

    def test_get_active_twins(self, twin_engine):
        """Test getting active twins."""
        twin1 = twin_engine.create_twin(ome_id="ome-001")
        twin2 = twin_engine.create_twin(ome_id="ome-001")
        twin_engine.pause_twin(twin2.id)

        active = twin_engine.get_active_twins()
        assert len(active) == 1
        assert twin1 in active

    def test_get_metrics(self, twin_engine):
        """Test getting engine metrics."""
        twin_engine.create_twin(ome_id="ome-001")

        metrics = twin_engine.get_metrics()
        assert "twins_active" in metrics
        assert metrics["twins_active"] == 1
        assert "twins_by_type" in metrics
        assert "twins_by_state" in metrics

    def test_add_event_listener(self, twin_engine):
        """Test adding event listener."""
        callback = MagicMock()
        listener_id = twin_engine.add_event_listener(callback)

        assert listener_id is not None
        assert len(twin_engine._event_listeners) == 1

    def test_remove_event_listener(self, twin_engine):
        """Test removing event listener."""
        callback = MagicMock()
        listener_id = twin_engine.add_event_listener(callback)

        twin_engine.remove_event_listener(listener_id)
        assert len(twin_engine._event_listeners) == 0
