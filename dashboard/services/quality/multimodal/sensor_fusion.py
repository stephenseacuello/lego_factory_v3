"""
Sensor Fusion for Manufacturing Quality Prediction.

Combines multiple sensor modalities (temperature, vibration, current, etc.)
with vision data for comprehensive quality assessment.

Research Value:
- Novel sensor fusion for additive manufacturing
- Real-time multi-sensor quality prediction
- Correlation discovery across modalities

References:
- Hall, D.L. (2004). Mathematical Techniques in Multisensor Data Fusion
- Khaleghi, B., et al. (2013). Multisensor Data Fusion: A Review
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any
from enum import Enum, auto
from datetime import datetime
import math
import random


class SensorType(Enum):
    """Types of manufacturing sensors."""
    TEMPERATURE = auto()
    VIBRATION = auto()
    CURRENT = auto()
    ACOUSTIC = auto()
    FORCE = auto()
    PRESSURE = auto()
    HUMIDITY = auto()
    OPTICAL = auto()
    PROXIMITY = auto()


class FusionLevel(Enum):
    """Level at which sensor fusion occurs."""
    DATA_LEVEL = auto()  # Raw data fusion
    FEATURE_LEVEL = auto()  # Feature extraction then fusion
    DECISION_LEVEL = auto()  # Independent decisions then fusion


@dataclass
class SensorConfig:
    """Configuration for sensor fusion."""

    # Sensors to use
    active_sensors: List[SensorType] = field(default_factory=lambda: [
        SensorType.TEMPERATURE,
        SensorType.VIBRATION,
        SensorType.CURRENT,
    ])

    # Fusion parameters
    fusion_level: FusionLevel = FusionLevel.FEATURE_LEVEL
    fusion_dim: int = 256
    use_attention: bool = True

    # Temporal parameters
    window_size: int = 100  # Samples per window
    sample_rate_hz: float = 1000.0

    # Vision integration
    include_vision: bool = True
    vision_feature_dim: int = 2048


@dataclass
class SensorReading:
    """Single sensor reading with metadata."""

    sensor_type: SensorType
    value: float
    timestamp: datetime
    unit: str
    sensor_id: str
    quality: float = 1.0  # Data quality indicator (0-1)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SensorWindow:
    """Window of sensor readings for temporal analysis."""

    sensor_type: SensorType
    values: List[float]
    timestamps: List[datetime]
    start_time: datetime
    end_time: datetime
    sample_rate: float

    def get_statistics(self) -> Dict[str, float]:
        """Compute window statistics."""
        if not self.values:
            return {}

        values = self.values
        n = len(values)

        mean = sum(values) / n
        variance = sum((v - mean) ** 2 for v in values) / n
        std = math.sqrt(variance)

        sorted_vals = sorted(values)

        return {
            "mean": mean,
            "std": std,
            "min": min(values),
            "max": max(values),
            "range": max(values) - min(values),
            "median": sorted_vals[n // 2],
            "rms": math.sqrt(sum(v ** 2 for v in values) / n),
        }


@dataclass
class FusedFeatures:
    """Fused feature vector from multiple sensors."""

    features: Any  # Feature tensor
    feature_dim: int
    source_modalities: List[str]
    timestamp: datetime
    confidence: float = 1.0
    metadata: Dict[str, Any] = field(default_factory=dict)


class SensorEncoder:
    """
    Encoder for individual sensor modality.

    Extracts features from raw sensor signals.
    """

    def __init__(self, sensor_type: SensorType, output_dim: int = 64):
        self.sensor_type = sensor_type
        self.output_dim = output_dim

        # Sensor-specific parameters
        self.processing_params = self._get_processing_params()

    def _get_processing_params(self) -> Dict[str, Any]:
        """Get processing parameters for sensor type."""
        params = {
            SensorType.TEMPERATURE: {
                "normalize_range": (0, 300),  # Celsius
                "features": ["mean", "trend", "deviation"],
            },
            SensorType.VIBRATION: {
                "normalize_range": (-10, 10),  # g
                "features": ["rms", "peak", "frequency"],
            },
            SensorType.CURRENT: {
                "normalize_range": (0, 10),  # Amps
                "features": ["mean", "rms", "thd"],  # THD = total harmonic distortion
            },
            SensorType.ACOUSTIC: {
                "normalize_range": (0, 120),  # dB
                "features": ["spl", "frequency", "harmonics"],
            },
            SensorType.FORCE: {
                "normalize_range": (0, 1000),  # N
                "features": ["peak", "mean", "impulse"],
            },
        }

        return params.get(self.sensor_type, {
            "normalize_range": (-1, 1),
            "features": ["mean", "std", "range"],
        })

    def encode(self, window: SensorWindow) -> Any:
        """
        Encode sensor window to feature vector.

        Args:
            window: Window of sensor readings

        Returns:
            Feature vector
        """
        # Extract statistical features
        stats = window.get_statistics()

        # Normalize based on sensor type
        norm_range = self.processing_params["normalize_range"]

        # Extract features based on sensor type
        features = []
        for feat_name in self.processing_params.get("features", ["mean", "std"]):
            if feat_name in stats:
                # Normalize to [0, 1]
                raw = stats[feat_name]
                normalized = (raw - norm_range[0]) / (norm_range[1] - norm_range[0])
                features.append(max(0, min(1, normalized)))
            else:
                features.append(0.5)  # Default

        # Pad to output dimension
        while len(features) < self.output_dim:
            features.append(0.0)

        return features[:self.output_dim]

    def get_output_dim(self) -> int:
        """Get encoder output dimension."""
        return self.output_dim


class VisionEncoder:
    """
    Encoder for vision modality.

    Extracts features from camera images.
    """

    def __init__(self, output_dim: int = 2048, backbone: str = "resnet50"):
        self.output_dim = output_dim
        self.backbone = backbone

    def encode(self, image: Any) -> Any:
        """
        Encode image to feature vector.

        Args:
            image: Input image

        Returns:
            Feature vector
        """
        # Simulated feature extraction
        features = [random.gauss(0, 1) for _ in range(self.output_dim)]
        return features

    def get_output_dim(self) -> int:
        """Get encoder output dimension."""
        return self.output_dim


class FusionModule:
    """
    Module for fusing features from multiple modalities.

    Supports various fusion strategies.
    """

    def __init__(
        self,
        input_dims: Dict[str, int],
        output_dim: int,
        fusion_type: str = "attention"
    ):
        self.input_dims = input_dims
        self.output_dim = output_dim
        self.fusion_type = fusion_type

        # Total input dimension
        self.total_input_dim = sum(input_dims.values())

    def fuse(self, features: Dict[str, Any]) -> Any:
        """
        Fuse features from multiple modalities.

        Args:
            features: Dictionary of modality features

        Returns:
            Fused feature vector
        """
        if self.fusion_type == "concatenate":
            return self._concat_fusion(features)
        elif self.fusion_type == "attention":
            return self._attention_fusion(features)
        elif self.fusion_type == "gated":
            return self._gated_fusion(features)
        else:
            return self._concat_fusion(features)

    def _concat_fusion(self, features: Dict[str, Any]) -> Any:
        """Simple concatenation fusion."""
        all_features = []
        for modality in sorted(features.keys()):
            if isinstance(features[modality], list):
                all_features.extend(features[modality])
            else:
                all_features.append(features[modality])

        return all_features[:self.output_dim]

    def _attention_fusion(self, features: Dict[str, Any]) -> Any:
        """Attention-based fusion."""
        # Compute attention weights (simulated)
        modalities = list(features.keys())
        weights = [1.0 / len(modalities)] * len(modalities)

        # Weighted combination
        fused = [0.0] * self.output_dim

        for modality, weight in zip(modalities, weights):
            mod_features = features[modality]
            if isinstance(mod_features, list):
                for i in range(min(len(mod_features), self.output_dim)):
                    fused[i] += weight * mod_features[i]

        return fused

    def _gated_fusion(self, features: Dict[str, Any]) -> Any:
        """Gated fusion with learnable gates."""
        # Simulated gating
        return self._attention_fusion(features)


class SensorFusion:
    """
    Multi-sensor fusion for quality prediction.

    Combines data from multiple sensors with optional
    vision integration for comprehensive quality assessment.

    Research Value:
    - Novel sensor fusion architecture
    - Real-time multi-modal processing
    - Explainable sensor contributions
    """

    def __init__(self, config: Optional[SensorConfig] = None):
        self.config = config or SensorConfig()

        # Initialize encoders for each sensor
        self.sensor_encoders: Dict[SensorType, SensorEncoder] = {}
        for sensor_type in self.config.active_sensors:
            self.sensor_encoders[sensor_type] = SensorEncoder(sensor_type, output_dim=64)

        # Vision encoder if enabled
        self.vision_encoder = None
        if self.config.include_vision:
            self.vision_encoder = VisionEncoder(self.config.vision_feature_dim)

        # Build fusion module
        input_dims = {s.name: 64 for s in self.config.active_sensors}
        if self.config.include_vision:
            input_dims["VISION"] = self.config.vision_feature_dim

        self.fusion_module = FusionModule(
            input_dims=input_dims,
            output_dim=self.config.fusion_dim,
            fusion_type="attention" if self.config.use_attention else "concatenate"
        )

        # Sensor buffers for windowing
        self.sensor_buffers: Dict[SensorType, List[SensorReading]] = {
            s: [] for s in self.config.active_sensors
        }

    def add_reading(self, reading: SensorReading):
        """Add sensor reading to buffer."""
        if reading.sensor_type in self.sensor_buffers:
            self.sensor_buffers[reading.sensor_type].append(reading)

            # Limit buffer size
            max_size = self.config.window_size * 2
            if len(self.sensor_buffers[reading.sensor_type]) > max_size:
                self.sensor_buffers[reading.sensor_type] = \
                    self.sensor_buffers[reading.sensor_type][-max_size:]

    def get_window(self, sensor_type: SensorType) -> Optional[SensorWindow]:
        """Get current window of readings for sensor."""
        readings = self.sensor_buffers.get(sensor_type, [])

        if len(readings) < self.config.window_size:
            return None

        window_readings = readings[-self.config.window_size:]

        return SensorWindow(
            sensor_type=sensor_type,
            values=[r.value for r in window_readings],
            timestamps=[r.timestamp for r in window_readings],
            start_time=window_readings[0].timestamp,
            end_time=window_readings[-1].timestamp,
            sample_rate=self.config.sample_rate_hz
        )

    def extract_features(
        self,
        image: Optional[Any] = None
    ) -> Optional[FusedFeatures]:
        """
        Extract and fuse features from all modalities.

        Args:
            image: Optional camera image

        Returns:
            Fused features or None if insufficient data
        """
        modality_features: Dict[str, Any] = {}
        source_modalities = []

        # Extract sensor features
        for sensor_type, encoder in self.sensor_encoders.items():
            window = self.get_window(sensor_type)
            if window is not None:
                features = encoder.encode(window)
                modality_features[sensor_type.name] = features
                source_modalities.append(sensor_type.name)

        # Extract vision features if available
        if self.config.include_vision and image is not None and self.vision_encoder:
            vision_features = self.vision_encoder.encode(image)
            modality_features["VISION"] = vision_features
            source_modalities.append("VISION")

        if not modality_features:
            return None

        # Fuse features
        fused = self.fusion_module.fuse(modality_features)

        return FusedFeatures(
            features=fused,
            feature_dim=self.config.fusion_dim,
            source_modalities=source_modalities,
            timestamp=datetime.now(),
            confidence=len(source_modalities) / (len(self.config.active_sensors) +
                                                   (1 if self.config.include_vision else 0))
        )

    def predict_quality(
        self,
        image: Optional[Any] = None
    ) -> Dict[str, Any]:
        """
        Predict quality from fused sensor data.

        Args:
            image: Optional camera image

        Returns:
            Quality prediction with confidence
        """
        fused = self.extract_features(image)

        if fused is None:
            return {
                "quality_score": None,
                "error": "Insufficient sensor data",
            }

        # Simulated quality prediction from fused features
        quality_score = random.uniform(0.7, 1.0)

        # Contribution analysis
        contributions = {}
        for modality in fused.source_modalities:
            contributions[modality] = random.uniform(0.1, 0.4)

        # Normalize contributions
        total = sum(contributions.values())
        contributions = {k: v / total for k, v in contributions.items()}

        return {
            "quality_score": round(quality_score, 4),
            "confidence": round(fused.confidence, 3),
            "modality_contributions": contributions,
            "num_modalities": len(fused.source_modalities),
            "timestamp": fused.timestamp.isoformat(),
        }

    def get_sensor_status(self) -> Dict[str, Any]:
        """Get status of all sensors."""
        status = {}

        for sensor_type in self.config.active_sensors:
            buffer = self.sensor_buffers[sensor_type]
            status[sensor_type.name] = {
                "buffer_size": len(buffer),
                "window_ready": len(buffer) >= self.config.window_size,
                "last_reading": buffer[-1].timestamp.isoformat() if buffer else None,
            }

        return status


class ManufacturingSensorFusion(SensorFusion):
    """
    Manufacturing-specific sensor fusion.

    Extends sensor fusion with domain knowledge about
    3D printing process parameters and their effects on quality.

    Research Value:
    - Process-aware sensor fusion
    - Causal modeling of sensor-quality relationships
    - Predictive maintenance integration
    """

    def __init__(self, config: Optional[SensorConfig] = None):
        if config is None:
            config = SensorConfig(
                active_sensors=[
                    SensorType.TEMPERATURE,
                    SensorType.VIBRATION,
                    SensorType.CURRENT,
                    SensorType.ACOUSTIC,
                ]
            )
        super().__init__(config)

        # Manufacturing-specific thresholds
        self.quality_thresholds = {
            SensorType.TEMPERATURE: {"min": 190, "max": 230, "optimal": 210},
            SensorType.VIBRATION: {"max_rms": 0.5},
            SensorType.CURRENT: {"max_deviation": 0.2},
            SensorType.ACOUSTIC: {"max_spl": 85},
        }

        # Process state tracking
        self.process_state = {
            "is_printing": False,
            "layer_number": 0,
            "elapsed_time_s": 0,
        }

    def update_process_state(
        self,
        is_printing: bool = None,
        layer_number: int = None,
        elapsed_time_s: float = None
    ):
        """Update current process state."""
        if is_printing is not None:
            self.process_state["is_printing"] = is_printing
        if layer_number is not None:
            self.process_state["layer_number"] = layer_number
        if elapsed_time_s is not None:
            self.process_state["elapsed_time_s"] = elapsed_time_s

    def check_sensor_limits(self) -> Dict[str, Any]:
        """
        Check if sensor readings are within acceptable limits.

        Returns early warning for out-of-spec conditions.
        """
        warnings = []
        alerts = []

        for sensor_type in self.config.active_sensors:
            window = self.get_window(sensor_type)
            if window is None:
                continue

            stats = window.get_statistics()
            thresholds = self.quality_thresholds.get(sensor_type, {})

            # Check temperature
            if sensor_type == SensorType.TEMPERATURE:
                if "min" in thresholds and stats["mean"] < thresholds["min"]:
                    warnings.append(f"Temperature below minimum: {stats['mean']:.1f}°C")
                if "max" in thresholds and stats["mean"] > thresholds["max"]:
                    alerts.append(f"Temperature above maximum: {stats['mean']:.1f}°C")

            # Check vibration
            elif sensor_type == SensorType.VIBRATION:
                if "max_rms" in thresholds and stats["rms"] > thresholds["max_rms"]:
                    warnings.append(f"Excessive vibration: {stats['rms']:.3f}g RMS")

            # Check current
            elif sensor_type == SensorType.CURRENT:
                if "max_deviation" in thresholds:
                    cv = stats["std"] / stats["mean"] if stats["mean"] > 0 else 0
                    if cv > thresholds["max_deviation"]:
                        warnings.append(f"Current instability: {cv:.2%} CV")

        return {
            "status": "alert" if alerts else ("warning" if warnings else "ok"),
            "warnings": warnings,
            "alerts": alerts,
            "timestamp": datetime.now().isoformat(),
        }

    def predict_defect_probability(
        self,
        image: Optional[Any] = None
    ) -> Dict[str, float]:
        """
        Predict probability of specific defect types.

        Uses sensor patterns correlated with defect types.
        """
        quality_result = self.predict_quality(image)

        if quality_result.get("quality_score") is None:
            return {}

        # Defect probabilities based on sensor patterns (simulated)
        defect_probs = {
            "under_extrusion": 0.0,
            "over_extrusion": 0.0,
            "stringing": 0.0,
            "layer_adhesion": 0.0,
            "warping": 0.0,
            "nozzle_clog": 0.0,
        }

        # Analyze temperature
        temp_window = self.get_window(SensorType.TEMPERATURE)
        if temp_window:
            stats = temp_window.get_statistics()
            optimal = self.quality_thresholds[SensorType.TEMPERATURE]["optimal"]

            if stats["mean"] < optimal - 15:
                defect_probs["under_extrusion"] += 0.3
                defect_probs["layer_adhesion"] += 0.2
            elif stats["mean"] > optimal + 15:
                defect_probs["stringing"] += 0.3
                defect_probs["over_extrusion"] += 0.2

            if stats["std"] > 5:  # Temperature instability
                defect_probs["layer_adhesion"] += 0.2

        # Analyze vibration
        vib_window = self.get_window(SensorType.VIBRATION)
        if vib_window:
            stats = vib_window.get_statistics()
            if stats["rms"] > 0.3:
                defect_probs["layer_adhesion"] += 0.2
                defect_probs["stringing"] += 0.1

        # Analyze current
        current_window = self.get_window(SensorType.CURRENT)
        if current_window:
            stats = current_window.get_statistics()
            cv = stats["std"] / stats["mean"] if stats["mean"] > 0 else 0

            if cv > 0.15:
                defect_probs["nozzle_clog"] += 0.3
                defect_probs["under_extrusion"] += 0.2

        # Normalize
        for defect in defect_probs:
            defect_probs[defect] = min(0.99, defect_probs[defect])

        return defect_probs

    def get_process_insights(self) -> Dict[str, Any]:
        """
        Get insights about current process health.

        Combines sensor data with process knowledge.
        """
        limit_check = self.check_sensor_limits()
        defect_probs = self.predict_defect_probability()

        # Calculate overall process health
        max_defect_prob = max(defect_probs.values()) if defect_probs else 0
        health_score = 1.0 - max_defect_prob

        if limit_check["status"] == "alert":
            health_score *= 0.5
        elif limit_check["status"] == "warning":
            health_score *= 0.8

        # Generate recommendations
        recommendations = []

        if defect_probs.get("under_extrusion", 0) > 0.3:
            recommendations.append("Consider increasing nozzle temperature or decreasing print speed")

        if defect_probs.get("stringing", 0) > 0.3:
            recommendations.append("Try reducing temperature or increasing retraction")

        if defect_probs.get("nozzle_clog", 0) > 0.3:
            recommendations.append("Check filament path for debris or perform cold pull")

        return {
            "health_score": round(health_score, 3),
            "status": limit_check["status"],
            "defect_risks": defect_probs,
            "warnings": limit_check["warnings"],
            "alerts": limit_check["alerts"],
            "recommendations": recommendations,
            "process_state": self.process_state,
        }


# Module exports
__all__ = [
    # Enums
    "SensorType",
    "FusionLevel",
    # Data classes
    "SensorConfig",
    "SensorReading",
    "SensorWindow",
    "FusedFeatures",
    # Classes
    "SensorEncoder",
    "VisionEncoder",
    "FusionModule",
    "SensorFusion",
    "ManufacturingSensorFusion",
]
