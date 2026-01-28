"""
LEGO Factory v3 - Feature Store Unit Tests
==========================================
Tests for predictive feature store functionality.
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

from services.predictive.feature_store import (
    FeatureStore,
    FeatureDefinition,
    FeatureVector,
    FeatureConfig,
    FeatureType,
)


class TestFeatureDefinition:
    """Test FeatureDefinition dataclass."""

    def test_numeric_feature_definition(self):
        """Test creating a numeric feature definition."""
        feature = FeatureDefinition(
            name="temperature",
            feature_type=FeatureType.NUMERIC,
            description="Sensor temperature",
            unit="°C",
            min_value=0,
            max_value=100,
        )
        assert feature.name == "temperature"
        assert feature.feature_type == FeatureType.NUMERIC
        assert feature.min_value == 0
        assert feature.max_value == 100

    def test_categorical_feature_definition(self):
        """Test creating a categorical feature definition."""
        feature = FeatureDefinition(
            name="material",
            feature_type=FeatureType.CATEGORICAL,
            description="Material type",
            categories=["aluminum", "steel", "brass"],
        )
        assert feature.name == "material"
        assert feature.feature_type == FeatureType.CATEGORICAL
        assert len(feature.categories) == 3
        assert "aluminum" in feature.categories


class TestFeatureVector:
    """Test FeatureVector dataclass."""

    def test_feature_vector_creation(self):
        """Test creating a feature vector."""
        features = {
            "temperature": 25.5,
            "pressure": 101.3,
            "humidity": 45,
        }
        vector = FeatureVector(
            features=features,
            entity_id="machine-001",
            entity_type="cnc_mill",
        )
        assert vector.features == features
        assert vector.entity_id == "machine-001"
        assert vector.entity_type == "cnc_mill"
        assert isinstance(vector.timestamp, datetime)

    def test_feature_vector_to_dict(self):
        """Test converting feature vector to dictionary."""
        vector = FeatureVector(
            features={"temp": 25.0},
            entity_id="sensor-001",
            entity_type="temperature_sensor",
            metadata={"location": "zone-a"},
        )
        result = vector.to_dict()
        assert "features" in result
        assert result["features"]["temp"] == 25.0
        assert result["entity_id"] == "sensor-001"
        assert "timestamp" in result
        assert result["metadata"]["location"] == "zone-a"

    def test_feature_vector_hash(self):
        """Test feature vector hash generation."""
        vector1 = FeatureVector(features={"a": 1, "b": 2})
        vector2 = FeatureVector(features={"a": 1, "b": 2})
        vector3 = FeatureVector(features={"a": 1, "b": 3})

        # Same features should have same hash
        assert vector1.get_hash() == vector2.get_hash()
        # Different features should have different hash
        assert vector1.get_hash() != vector3.get_hash()


class TestFeatureStore:
    """Test FeatureStore class."""

    @pytest.fixture
    def feature_store(self):
        """Create a feature store instance."""
        config = FeatureConfig(
            cache_ttl_seconds=3600,
            max_cache_size=1000,
            enable_persistence=False,
        )
        return FeatureStore(config)

    def test_feature_store_initialization(self, feature_store):
        """Test feature store initializes with standard features."""
        assert feature_store is not None
        # Should have standard features registered
        assert len(feature_store._definitions) > 0
        assert "spindle_load" in feature_store._definitions
        assert "temperature_spindle" in feature_store._definitions

    def test_register_custom_feature(self, feature_store):
        """Test registering a custom feature definition."""
        custom_feature = FeatureDefinition(
            name="custom_metric",
            feature_type=FeatureType.NUMERIC,
            description="A custom metric",
            min_value=0,
            max_value=1000,
        )
        feature_store.register_feature(custom_feature)
        assert "custom_metric" in feature_store._definitions
        assert feature_store.get_definition("custom_metric") == custom_feature

    def test_get_definition_existing(self, feature_store):
        """Test getting an existing feature definition."""
        definition = feature_store.get_definition("spindle_load")
        assert definition is not None
        assert definition.name == "spindle_load"
        assert definition.feature_type == FeatureType.NUMERIC

    def test_get_definition_nonexistent(self, feature_store):
        """Test getting a non-existent feature definition returns None."""
        definition = feature_store.get_definition("nonexistent_feature")
        assert definition is None

    def test_standard_features_have_correct_types(self, feature_store):
        """Test that standard features have appropriate types."""
        # Numeric features
        numeric_features = [
            "gcode_line_count", "spindle_load", "vibration_x",
            "tool_diameter", "coolant_pressure",
        ]
        for name in numeric_features:
            defn = feature_store.get_definition(name)
            assert defn is not None, f"Feature {name} not found"
            assert defn.feature_type == FeatureType.NUMERIC

        # Categorical features
        categorical_features = ["machine_type", "material", "tool_type"]
        for name in categorical_features:
            defn = feature_store.get_definition(name)
            assert defn is not None, f"Feature {name} not found"
            assert defn.feature_type == FeatureType.CATEGORICAL
            assert len(defn.categories) > 0

    def test_feature_validation_bounds(self, feature_store):
        """Test that feature definitions have valid bounds."""
        for name, defn in feature_store._definitions.items():
            if defn.feature_type == FeatureType.NUMERIC:
                if defn.min_value is not None and defn.max_value is not None:
                    assert defn.min_value <= defn.max_value, (
                        f"Feature {name} has invalid bounds: "
                        f"min={defn.min_value}, max={defn.max_value}"
                    )


class TestFeatureConfig:
    """Test FeatureConfig dataclass."""

    def test_default_config(self):
        """Test default configuration values."""
        config = FeatureConfig()
        assert config.cache_ttl_seconds == 3600
        assert config.max_cache_size == 10000
        assert config.enable_persistence is False
        assert config.enable_versioning is True

    def test_custom_config(self):
        """Test custom configuration values."""
        config = FeatureConfig(
            cache_ttl_seconds=7200,
            max_cache_size=5000,
            enable_persistence=True,
            persistence_path="/custom/path",
        )
        assert config.cache_ttl_seconds == 7200
        assert config.max_cache_size == 5000
        assert config.enable_persistence is True
        assert config.persistence_path == "/custom/path"


class TestFeatureType:
    """Test FeatureType enum."""

    def test_feature_types_exist(self):
        """Test all expected feature types exist."""
        assert FeatureType.NUMERIC.value == "numeric"
        assert FeatureType.CATEGORICAL.value == "categorical"
        assert FeatureType.TEMPORAL.value == "temporal"
        assert FeatureType.TEXT.value == "text"
        assert FeatureType.EMBEDDING.value == "embedding"

    def test_feature_type_values_unique(self):
        """Test all feature type values are unique."""
        values = [ft.value for ft in FeatureType]
        assert len(values) == len(set(values))
