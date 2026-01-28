"""
Feature Store for Predictive Manufacturing.

Centralized feature engineering and storage for ML models.
"""

import logging
from dataclasses import dataclass, field
from typing import Optional, Dict, List, Any, Union
from datetime import datetime, timedelta
from enum import Enum
import json
import hashlib

logger = logging.getLogger(__name__)


class FeatureType(Enum):
    """Types of features."""
    NUMERIC = "numeric"
    CATEGORICAL = "categorical"
    TEMPORAL = "temporal"
    TEXT = "text"
    EMBEDDING = "embedding"


@dataclass
class FeatureDefinition:
    """Definition of a feature."""
    name: str
    feature_type: FeatureType
    description: str = ""
    unit: str = ""
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    categories: List[str] = field(default_factory=list)
    default_value: Any = None
    is_required: bool = True


@dataclass
class FeatureVector:
    """A vector of features for a single observation."""
    features: Dict[str, Any]
    timestamp: datetime = field(default_factory=datetime.now)
    entity_id: str = ""  # Machine, tool, part, etc.
    entity_type: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "features": self.features,
            "timestamp": self.timestamp.isoformat(),
            "entity_id": self.entity_id,
            "entity_type": self.entity_type,
            "metadata": self.metadata,
        }

    def get_hash(self) -> str:
        """Get hash of feature vector for deduplication."""
        content = json.dumps(self.features, sort_keys=True)
        return hashlib.md5(content.encode()).hexdigest()


@dataclass
class FeatureConfig:
    """Feature store configuration."""
    cache_ttl_seconds: int = 3600
    max_cache_size: int = 10000
    enable_persistence: bool = False
    persistence_path: str = "./feature_store"
    enable_versioning: bool = True


class FeatureStore:
    """
    Centralized feature store for manufacturing ML models.

    Features:
    - Feature definition and validation
    - Temporal feature aggregation
    - Feature caching
    - Feature versioning
    """

    # Standard feature definitions for CNC manufacturing
    STANDARD_FEATURES = {
        # G-code features
        "gcode_line_count": FeatureDefinition(
            name="gcode_line_count",
            feature_type=FeatureType.NUMERIC,
            description="Total lines in G-code program",
            min_value=0,
        ),
        "gcode_move_count": FeatureDefinition(
            name="gcode_move_count",
            feature_type=FeatureType.NUMERIC,
            description="Number of G0/G1/G2/G3 moves",
            min_value=0,
        ),
        "total_distance": FeatureDefinition(
            name="total_distance",
            feature_type=FeatureType.NUMERIC,
            description="Total toolpath distance",
            unit="mm",
            min_value=0,
        ),
        "rapid_distance": FeatureDefinition(
            name="rapid_distance",
            feature_type=FeatureType.NUMERIC,
            description="Total rapid (G0) distance",
            unit="mm",
            min_value=0,
        ),
        "cut_distance": FeatureDefinition(
            name="cut_distance",
            feature_type=FeatureType.NUMERIC,
            description="Total cutting distance",
            unit="mm",
            min_value=0,
        ),
        "avg_feed_rate": FeatureDefinition(
            name="avg_feed_rate",
            feature_type=FeatureType.NUMERIC,
            description="Average feed rate",
            unit="mm/min",
            min_value=0,
        ),
        "max_feed_rate": FeatureDefinition(
            name="max_feed_rate",
            feature_type=FeatureType.NUMERIC,
            description="Maximum feed rate",
            unit="mm/min",
            min_value=0,
        ),
        "tool_changes": FeatureDefinition(
            name="tool_changes",
            feature_type=FeatureType.NUMERIC,
            description="Number of tool changes",
            min_value=0,
        ),

        # Machine features
        "machine_type": FeatureDefinition(
            name="machine_type",
            feature_type=FeatureType.CATEGORICAL,
            description="Type of CNC machine",
            categories=["mill", "lathe", "router", "laser", "edm"],
        ),
        "spindle_load": FeatureDefinition(
            name="spindle_load",
            feature_type=FeatureType.NUMERIC,
            description="Current spindle load",
            unit="%",
            min_value=0,
            max_value=150,
        ),
        "spindle_speed": FeatureDefinition(
            name="spindle_speed",
            feature_type=FeatureType.NUMERIC,
            description="Spindle RPM",
            unit="rpm",
            min_value=0,
        ),
        "axis_load_x": FeatureDefinition(
            name="axis_load_x",
            feature_type=FeatureType.NUMERIC,
            description="X-axis servo load",
            unit="%",
            min_value=0,
            max_value=150,
        ),
        "axis_load_y": FeatureDefinition(
            name="axis_load_y",
            feature_type=FeatureType.NUMERIC,
            description="Y-axis servo load",
            unit="%",
            min_value=0,
            max_value=150,
        ),
        "axis_load_z": FeatureDefinition(
            name="axis_load_z",
            feature_type=FeatureType.NUMERIC,
            description="Z-axis servo load",
            unit="%",
            min_value=0,
            max_value=150,
        ),

        # Material features
        "material": FeatureDefinition(
            name="material",
            feature_type=FeatureType.CATEGORICAL,
            description="Workpiece material",
            categories=[
                "aluminum", "steel", "stainless", "brass", "copper",
                "titanium", "plastic", "wood", "composite"
            ],
        ),
        "material_hardness": FeatureDefinition(
            name="material_hardness",
            feature_type=FeatureType.NUMERIC,
            description="Material hardness (HRC/HB)",
            min_value=0,
        ),

        # Tool features
        "tool_diameter": FeatureDefinition(
            name="tool_diameter",
            feature_type=FeatureType.NUMERIC,
            description="Cutting tool diameter",
            unit="mm",
            min_value=0,
        ),
        "tool_length": FeatureDefinition(
            name="tool_length",
            feature_type=FeatureType.NUMERIC,
            description="Tool length",
            unit="mm",
            min_value=0,
        ),
        "tool_type": FeatureDefinition(
            name="tool_type",
            feature_type=FeatureType.CATEGORICAL,
            description="Type of cutting tool",
            categories=[
                "endmill", "ballnose", "drill", "tap", "reamer",
                "facemill", "insert", "chamfer", "engraver"
            ],
        ),
        "tool_flutes": FeatureDefinition(
            name="tool_flutes",
            feature_type=FeatureType.NUMERIC,
            description="Number of flutes",
            min_value=1,
            max_value=12,
        ),
        "tool_runtime": FeatureDefinition(
            name="tool_runtime",
            feature_type=FeatureType.NUMERIC,
            description="Total runtime of current tool",
            unit="minutes",
            min_value=0,
        ),
        "tool_cut_distance": FeatureDefinition(
            name="tool_cut_distance",
            feature_type=FeatureType.NUMERIC,
            description="Total cutting distance of tool",
            unit="mm",
            min_value=0,
        ),

        # Sensor features
        "vibration_x": FeatureDefinition(
            name="vibration_x",
            feature_type=FeatureType.NUMERIC,
            description="X-axis vibration amplitude",
            unit="g",
            min_value=0,
        ),
        "vibration_y": FeatureDefinition(
            name="vibration_y",
            feature_type=FeatureType.NUMERIC,
            description="Y-axis vibration amplitude",
            unit="g",
            min_value=0,
        ),
        "vibration_z": FeatureDefinition(
            name="vibration_z",
            feature_type=FeatureType.NUMERIC,
            description="Z-axis vibration amplitude",
            unit="g",
            min_value=0,
        ),
        "temperature_spindle": FeatureDefinition(
            name="temperature_spindle",
            feature_type=FeatureType.NUMERIC,
            description="Spindle temperature",
            unit="°C",
            min_value=-40,
            max_value=150,
        ),
        "temperature_ambient": FeatureDefinition(
            name="temperature_ambient",
            feature_type=FeatureType.NUMERIC,
            description="Ambient temperature",
            unit="°C",
            min_value=-40,
            max_value=60,
        ),
        "coolant_pressure": FeatureDefinition(
            name="coolant_pressure",
            feature_type=FeatureType.NUMERIC,
            description="Coolant pressure",
            unit="bar",
            min_value=0,
        ),
        "coolant_flow": FeatureDefinition(
            name="coolant_flow",
            feature_type=FeatureType.NUMERIC,
            description="Coolant flow rate",
            unit="L/min",
            min_value=0,
        ),

        # Historical features
        "historical_cycle_time_avg": FeatureDefinition(
            name="historical_cycle_time_avg",
            feature_type=FeatureType.NUMERIC,
            description="Historical average cycle time for similar jobs",
            unit="seconds",
            min_value=0,
        ),
        "historical_scrap_rate": FeatureDefinition(
            name="historical_scrap_rate",
            feature_type=FeatureType.NUMERIC,
            description="Historical scrap rate for similar jobs",
            unit="%",
            min_value=0,
            max_value=100,
        ),
    }

    def __init__(self, config: Optional[FeatureConfig] = None):
        """Initialize feature store."""
        self.config = config or FeatureConfig()

        # Feature registry
        self._definitions: Dict[str, FeatureDefinition] = dict(self.STANDARD_FEATURES)

        # Feature cache
        self._cache: Dict[str, FeatureVector] = {}
        self._cache_timestamps: Dict[str, datetime] = {}

        # Feature history for temporal aggregation
        self._history: Dict[str, List[FeatureVector]] = {}

    def register_feature(self, definition: FeatureDefinition):
        """Register a new feature definition."""
        self._definitions[definition.name] = definition
        logger.info(f"Registered feature: {definition.name}")

    def get_definition(self, name: str) -> Optional[FeatureDefinition]:
        """Get feature definition by name."""
        return self._definitions.get(name)

    def validate_features(
        self,
        features: Dict[str, Any],
        strict: bool = False,
    ) -> tuple[bool, List[str]]:
        """
        Validate feature values against definitions.

        Returns:
            Tuple of (is_valid, error_messages)
        """
        errors = []

        for name, value in features.items():
            definition = self._definitions.get(name)

            if definition is None:
                if strict:
                    errors.append(f"Unknown feature: {name}")
                continue

            # Type validation
            if definition.feature_type == FeatureType.NUMERIC:
                if not isinstance(value, (int, float)):
                    errors.append(f"{name}: expected numeric, got {type(value).__name__}")
                    continue

                if definition.min_value is not None and value < definition.min_value:
                    errors.append(f"{name}: value {value} below minimum {definition.min_value}")

                if definition.max_value is not None and value > definition.max_value:
                    errors.append(f"{name}: value {value} above maximum {definition.max_value}")

            elif definition.feature_type == FeatureType.CATEGORICAL:
                if definition.categories and value not in definition.categories:
                    errors.append(f"{name}: value '{value}' not in {definition.categories}")

        # Check required features
        if strict:
            for name, definition in self._definitions.items():
                if definition.is_required and name not in features:
                    errors.append(f"Missing required feature: {name}")

        return len(errors) == 0, errors

    def normalize_features(
        self,
        features: Dict[str, Any],
        fill_defaults: bool = True,
    ) -> Dict[str, Any]:
        """
        Normalize feature values.

        - Fill missing values with defaults
        - Clip numeric values to valid ranges
        - Encode categorical values
        """
        normalized = dict(features)

        for name, definition in self._definitions.items():
            if name not in normalized:
                if fill_defaults and definition.default_value is not None:
                    normalized[name] = definition.default_value
                continue

            value = normalized[name]

            # Clip numeric values
            if definition.feature_type == FeatureType.NUMERIC:
                if definition.min_value is not None:
                    value = max(value, definition.min_value)
                if definition.max_value is not None:
                    value = min(value, definition.max_value)
                normalized[name] = value

        return normalized

    def store_vector(self, vector: FeatureVector):
        """Store a feature vector."""
        # Add to cache
        cache_key = f"{vector.entity_type}:{vector.entity_id}"
        self._cache[cache_key] = vector
        self._cache_timestamps[cache_key] = datetime.now()

        # Add to history for temporal aggregation
        if cache_key not in self._history:
            self._history[cache_key] = []
        self._history[cache_key].append(vector)

        # Limit history size
        max_history = 1000
        if len(self._history[cache_key]) > max_history:
            self._history[cache_key] = self._history[cache_key][-max_history:]

        # Evict old cache entries
        self._evict_cache()

    def get_latest(
        self,
        entity_id: str,
        entity_type: str = "",
    ) -> Optional[FeatureVector]:
        """Get latest feature vector for an entity."""
        cache_key = f"{entity_type}:{entity_id}"

        # Check cache freshness
        if cache_key in self._cache:
            timestamp = self._cache_timestamps.get(cache_key)
            if timestamp:
                age = (datetime.now() - timestamp).total_seconds()
                if age <= self.config.cache_ttl_seconds:
                    return self._cache[cache_key]

        return None

    def get_history(
        self,
        entity_id: str,
        entity_type: str = "",
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 100,
    ) -> List[FeatureVector]:
        """Get historical feature vectors."""
        cache_key = f"{entity_type}:{entity_id}"
        history = self._history.get(cache_key, [])

        # Filter by time range
        if start_time or end_time:
            filtered = []
            for vector in history:
                if start_time and vector.timestamp < start_time:
                    continue
                if end_time and vector.timestamp > end_time:
                    continue
                filtered.append(vector)
            history = filtered

        return history[-limit:]

    def aggregate_temporal(
        self,
        entity_id: str,
        entity_type: str = "",
        window: timedelta = timedelta(hours=1),
        aggregations: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """
        Aggregate features over a time window.

        Args:
            entity_id: Entity identifier
            entity_type: Entity type
            window: Time window for aggregation
            aggregations: Feature name -> aggregation type mapping
                         (mean, max, min, sum, std, count)
        """
        start_time = datetime.now() - window
        history = self.get_history(
            entity_id, entity_type,
            start_time=start_time,
            limit=10000,
        )

        if not history:
            logger.debug(f"No history found for entity {entity_id} in window")
            return {}

        # Default aggregations
        if aggregations is None:
            aggregations = {
                name: "mean"
                for name, defn in self._definitions.items()
                if defn.feature_type == FeatureType.NUMERIC
            }

        result = {}

        for feature_name, agg_type in aggregations.items():
            values = []
            for vector in history:
                if feature_name in vector.features:
                    value = vector.features[feature_name]
                    if isinstance(value, (int, float)):
                        values.append(value)

            if not values:
                continue

            if agg_type == "mean":
                result[f"{feature_name}_mean"] = sum(values) / len(values)
            elif agg_type == "max":
                result[f"{feature_name}_max"] = max(values)
            elif agg_type == "min":
                result[f"{feature_name}_min"] = min(values)
            elif agg_type == "sum":
                result[f"{feature_name}_sum"] = sum(values)
            elif agg_type == "std":
                mean = sum(values) / len(values)
                variance = sum((x - mean) ** 2 for x in values) / len(values)
                result[f"{feature_name}_std"] = variance ** 0.5
            elif agg_type == "count":
                result[f"{feature_name}_count"] = len(values)

        return result

    def extract_gcode_features(self, gcode: str) -> Dict[str, Any]:
        """
        Extract features from G-code program.

        Returns:
            Dict of extracted features
        """
        features = {
            "gcode_line_count": 0,
            "gcode_move_count": 0,
            "rapid_move_count": 0,
            "cut_move_count": 0,
            "arc_move_count": 0,
            "tool_changes": 0,
            "spindle_commands": 0,
            "coolant_commands": 0,
            "max_feed_rate": 0,
            "avg_feed_rate": 0,
            "max_spindle_speed": 0,
            "z_depth_max": 0,
        }

        feed_rates = []
        spindle_speeds = []
        z_values = []

        lines = gcode.strip().split('\n')
        features["gcode_line_count"] = len(lines)

        for line in lines:
            line = line.strip().upper()

            # Skip comments and empty lines
            if not line or line.startswith('(') or line.startswith(';'):
                continue

            # Count moves
            if 'G0' in line or 'G00' in line:
                features["rapid_move_count"] += 1
                features["gcode_move_count"] += 1
            elif 'G1' in line or 'G01' in line:
                features["cut_move_count"] += 1
                features["gcode_move_count"] += 1
            elif 'G2' in line or 'G02' in line or 'G3' in line or 'G03' in line:
                features["arc_move_count"] += 1
                features["gcode_move_count"] += 1

            # Tool changes
            if 'M6' in line or 'M06' in line or line.startswith('T'):
                features["tool_changes"] += 1

            # Spindle commands
            if 'M3' in line or 'M03' in line or 'M4' in line or 'M04' in line:
                features["spindle_commands"] += 1

            # Coolant commands
            if 'M7' in line or 'M07' in line or 'M8' in line or 'M08' in line:
                features["coolant_commands"] += 1

            # Extract feed rate
            if 'F' in line:
                try:
                    import re
                    match = re.search(r'F([\d.]+)', line)
                    if match:
                        feed_rates.append(float(match.group(1)))
                except (ValueError, re.error):
                    pass

            # Extract spindle speed
            if 'S' in line:
                try:
                    import re
                    match = re.search(r'S([\d.]+)', line)
                    if match:
                        spindle_speeds.append(float(match.group(1)))
                except (ValueError, re.error):
                    pass

            # Extract Z values
            if 'Z' in line:
                try:
                    import re
                    match = re.search(r'Z(-?[\d.]+)', line)
                    if match:
                        z_values.append(float(match.group(1)))
                except (ValueError, re.error):
                    pass

        if feed_rates:
            features["max_feed_rate"] = max(feed_rates)
            features["avg_feed_rate"] = sum(feed_rates) / len(feed_rates)

        if spindle_speeds:
            features["max_spindle_speed"] = max(spindle_speeds)

        if z_values:
            features["z_depth_max"] = abs(min(z_values))

        return features

    def _evict_cache(self):
        """Evict old cache entries."""
        if len(self._cache) <= self.config.max_cache_size:
            return

        # Remove oldest entries
        now = datetime.now()
        expired = [
            key for key, timestamp in self._cache_timestamps.items()
            if (now - timestamp).total_seconds() > self.config.cache_ttl_seconds
        ]

        for key in expired:
            self._cache.pop(key, None)
            self._cache_timestamps.pop(key, None)

    def get_feature_names(self) -> List[str]:
        """Get all registered feature names."""
        return list(self._definitions.keys())

    def get_feature_info(self) -> Dict[str, Dict[str, Any]]:
        """Get information about all features."""
        return {
            name: {
                "type": defn.feature_type.value,
                "description": defn.description,
                "unit": defn.unit,
                "required": defn.is_required,
            }
            for name, defn in self._definitions.items()
        }
