"""
Temporal Fusion for Manufacturing Quality Prediction.

Fuses time-series sensor data with image sequences for
temporal-aware quality prediction.

Research Value:
- Novel spatio-temporal fusion for manufacturing
- Layer-by-layer quality tracking
- Temporal defect pattern detection

References:
- Lim, B., et al. (2021). Temporal Fusion Transformers for Interpretable Multi-horizon Time Series Forecasting
- Bertasius, G., et al. (2021). Is Space-Time Attention All You Need for Video Understanding?
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any
from enum import Enum, auto
import math
import random
from datetime import datetime, timedelta


class TemporalAggregation(Enum):
    """Methods for temporal aggregation."""
    LAST = auto()  # Use last timestep
    MEAN = auto()  # Average across time
    ATTENTION = auto()  # Attention-weighted
    LSTM = auto()  # LSTM hidden state
    TRANSFORMER = auto()  # Transformer with temporal encoding


@dataclass
class TemporalConfig:
    """Configuration for temporal fusion."""

    # Sequence parameters
    sequence_length: int = 100  # Time steps
    image_sequence_length: int = 10  # Number of images
    feature_dim: int = 256

    # Temporal model
    aggregation: TemporalAggregation = TemporalAggregation.ATTENTION
    num_layers: int = 2
    num_heads: int = 8

    # Output
    output_dim: int = 128
    predict_horizon: int = 5  # Future prediction steps


@dataclass
class TemporalFeature:
    """Time-stamped feature vector."""

    features: Any
    timestamp: datetime
    timestep: int
    modality: str
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TemporalSequence:
    """Sequence of temporal features."""

    features: List[TemporalFeature]
    modality: str
    start_time: datetime
    end_time: datetime
    sample_rate: float = 1.0  # Hz

    def get_feature_matrix(self) -> Any:
        """Get features as matrix [seq_len, feature_dim]."""
        return [f.features for f in self.features]

    def get_statistics(self) -> Dict[str, float]:
        """Compute sequence statistics."""
        if not self.features:
            return {}

        # Flatten features
        all_values = []
        for f in self.features:
            if isinstance(f.features, list):
                all_values.extend(f.features)

        if not all_values:
            return {}

        return {
            "mean": sum(all_values) / len(all_values),
            "std": math.sqrt(sum((v - sum(all_values) / len(all_values)) ** 2
                                  for v in all_values) / len(all_values)),
            "min": min(all_values),
            "max": max(all_values),
            "length": len(self.features),
        }


class TimeSeriesEncoder:
    """
    Encoder for time-series sensor data.

    Extracts temporal patterns from sensor sequences.
    """

    def __init__(
        self,
        input_dim: int,
        hidden_dim: int,
        output_dim: int,
        num_layers: int = 2
    ):
        self.input_dim = input_dim
        self.hidden_dim = hidden_dim
        self.output_dim = output_dim
        self.num_layers = num_layers

    def encode(self, sequence: TemporalSequence) -> Any:
        """
        Encode time-series to fixed representation.

        Args:
            sequence: Input time-series

        Returns:
            Encoded representation
        """
        # Simulated LSTM/Transformer encoding
        seq_len = len(sequence.features)

        # Process through layers
        hidden = [[random.gauss(0, 1) for _ in range(self.hidden_dim)]
                  for _ in range(seq_len)]

        # Final output
        output = [random.gauss(0, 1) for _ in range(self.output_dim)]

        return {
            "sequence_encoding": hidden,
            "final_state": output,
            "sequence_length": seq_len,
        }

    def get_output_dim(self) -> int:
        """Get encoder output dimension."""
        return self.output_dim


class ImageSequenceEncoder:
    """
    Encoder for image sequences.

    Extracts spatio-temporal features from video or image series.
    """

    def __init__(
        self,
        spatial_dim: int = 2048,
        temporal_dim: int = 256,
        output_dim: int = 512
    ):
        self.spatial_dim = spatial_dim
        self.temporal_dim = temporal_dim
        self.output_dim = output_dim

    def encode(
        self,
        images: List[Any],
        timestamps: Optional[List[datetime]] = None
    ) -> Any:
        """
        Encode image sequence.

        Args:
            images: List of images
            timestamps: Optional timestamps

        Returns:
            Spatio-temporal representation
        """
        num_images = len(images)

        # Extract spatial features for each frame
        spatial_features = []
        for img in images:
            features = [random.gauss(0, 1) for _ in range(self.spatial_dim)]
            spatial_features.append(features)

        # Temporal aggregation
        temporal_features = []
        for t in range(num_images):
            # Simulated temporal attention
            temp_feat = [random.gauss(0, 1) for _ in range(self.temporal_dim)]
            temporal_features.append(temp_feat)

        # Final fusion
        output = [random.gauss(0, 1) for _ in range(self.output_dim)]

        return {
            "spatial_features": spatial_features,
            "temporal_features": temporal_features,
            "fused_representation": output,
            "num_frames": num_images,
        }

    def get_output_dim(self) -> int:
        """Get encoder output dimension."""
        return self.output_dim


class TemporalAttention:
    """
    Attention mechanism for temporal sequences.

    Learns to focus on important time steps.
    """

    def __init__(self, hidden_dim: int, num_heads: int = 8):
        self.hidden_dim = hidden_dim
        self.num_heads = num_heads
        self.head_dim = hidden_dim // num_heads

    def forward(
        self,
        query: Any,
        key: Any,
        value: Any,
        temporal_mask: Optional[Any] = None
    ) -> Tuple[Any, Any]:
        """
        Apply temporal attention.

        Args:
            query: Query tensor
            key: Key tensor
            value: Value tensor
            temporal_mask: Causal mask for autoregressive

        Returns:
            Attended output and attention weights
        """
        seq_len = len(query) if isinstance(query, list) else 1

        # Simulated attention
        attention_weights = [[random.uniform(0, 1) for _ in range(seq_len)]
                             for _ in range(seq_len)]

        # Normalize
        for i in range(seq_len):
            total = sum(attention_weights[i])
            if total > 0:
                attention_weights[i] = [w / total for w in attention_weights[i]]

        # Output
        output = [[random.gauss(0, 1) for _ in range(self.hidden_dim)]
                  for _ in range(seq_len)]

        return output, attention_weights


class TemporalFusion:
    """
    Temporal fusion for multi-modal manufacturing data.

    Combines time-series sensor data with image sequences
    for temporal-aware quality prediction.

    Research Value:
    - Novel temporal fusion architecture
    - Layer-by-layer quality tracking
    - Early defect detection from temporal patterns
    """

    def __init__(self, config: Optional[TemporalConfig] = None):
        self.config = config or TemporalConfig()

        # Time-series encoder
        self.ts_encoder = TimeSeriesEncoder(
            input_dim=64,
            hidden_dim=128,
            output_dim=self.config.feature_dim
        )

        # Image sequence encoder
        self.img_encoder = ImageSequenceEncoder(
            spatial_dim=2048,
            temporal_dim=256,
            output_dim=self.config.feature_dim
        )

        # Temporal attention
        self.temporal_attention = TemporalAttention(
            hidden_dim=self.config.feature_dim,
            num_heads=self.config.num_heads
        )

        # Fusion layer
        self.fusion_dim = self.config.feature_dim * 2

    def fuse(
        self,
        sensor_sequence: TemporalSequence,
        image_sequence: Optional[List[Any]] = None
    ) -> Dict[str, Any]:
        """
        Fuse sensor and image sequences.

        Args:
            sensor_sequence: Time-series sensor data
            image_sequence: Optional image sequence

        Returns:
            Fused temporal representation
        """
        # Encode sensor sequence
        sensor_encoding = self.ts_encoder.encode(sensor_sequence)

        # Encode image sequence if available
        img_encoding = None
        if image_sequence:
            img_encoding = self.img_encoder.encode(image_sequence)

        # Cross-modal temporal attention
        if img_encoding:
            # Align sensor and image temporal features
            attended, weights = self.temporal_attention.forward(
                sensor_encoding["sequence_encoding"],
                img_encoding["temporal_features"],
                img_encoding["temporal_features"]
            )
        else:
            attended = sensor_encoding["sequence_encoding"]
            weights = None

        # Final fusion
        if img_encoding:
            fused = sensor_encoding["final_state"] + img_encoding["fused_representation"]
        else:
            fused = sensor_encoding["final_state"]

        return {
            "fused_features": fused[:self.config.output_dim],
            "sensor_encoding": sensor_encoding["final_state"],
            "image_encoding": img_encoding["fused_representation"] if img_encoding else None,
            "attention_weights": weights,
            "sequence_length": sensor_encoding["sequence_length"],
        }

    def predict_quality_trajectory(
        self,
        sensor_sequence: TemporalSequence,
        image_sequence: Optional[List[Any]] = None
    ) -> Dict[str, Any]:
        """
        Predict quality over time (trajectory).

        Useful for tracking layer-by-layer quality in 3D printing.
        """
        fused = self.fuse(sensor_sequence, image_sequence)

        # Simulated quality trajectory
        seq_len = fused["sequence_length"]
        quality_scores = []

        base_quality = random.uniform(0.8, 0.95)
        for t in range(seq_len):
            # Quality with some temporal variation
            noise = random.gauss(0, 0.02)
            trend = -0.001 * t  # Slight degradation over time
            quality_scores.append(max(0, min(1, base_quality + noise + trend)))

        # Detect quality drops
        anomalies = []
        for t in range(1, len(quality_scores)):
            if quality_scores[t] < quality_scores[t - 1] - 0.05:
                anomalies.append({
                    "timestep": t,
                    "quality_drop": quality_scores[t - 1] - quality_scores[t],
                })

        return {
            "quality_trajectory": quality_scores,
            "final_quality": quality_scores[-1] if quality_scores else None,
            "min_quality": min(quality_scores) if quality_scores else None,
            "anomalies": anomalies,
            "num_timesteps": seq_len,
        }


class SpatioTemporalFusion:
    """
    Full spatio-temporal fusion for manufacturing.

    Combines spatial (image) and temporal (sensor) information
    with hierarchical attention mechanisms.

    Research Value:
    - Novel spatio-temporal architecture for manufacturing
    - Hierarchical attention for multi-scale features
    - Real-time quality prediction during printing
    """

    def __init__(self, config: Optional[TemporalConfig] = None):
        self.config = config or TemporalConfig()

        # Base temporal fusion
        self.temporal_fusion = TemporalFusion(config)

        # Spatial encoder for individual frames
        self.spatial_encoder = ImageSequenceEncoder(
            spatial_dim=2048,
            temporal_dim=256,
            output_dim=self.config.feature_dim
        )

        # Spatio-temporal attention
        self.st_attention = TemporalAttention(
            hidden_dim=self.config.feature_dim,
            num_heads=self.config.num_heads
        )

    def encode_layer_sequence(
        self,
        layer_images: List[Any],
        layer_sensors: List[TemporalSequence]
    ) -> Dict[str, Any]:
        """
        Encode layer-by-layer printing sequence.

        Args:
            layer_images: Image for each layer
            layer_sensors: Sensor data for each layer

        Returns:
            Layer-wise and aggregated encodings
        """
        num_layers = len(layer_images)

        layer_encodings = []

        for i in range(num_layers):
            # Encode each layer
            if i < len(layer_sensors):
                sensor_seq = layer_sensors[i]
            else:
                # Create dummy sequence
                sensor_seq = TemporalSequence(
                    features=[],
                    modality="sensor",
                    start_time=datetime.now(),
                    end_time=datetime.now()
                )

            layer_enc = self.temporal_fusion.fuse(
                sensor_sequence=sensor_seq,
                image_sequence=[layer_images[i]] if i < len(layer_images) else None
            )

            layer_encodings.append(layer_enc)

        # Aggregate across layers
        if layer_encodings:
            layer_features = [enc["fused_features"] for enc in layer_encodings]
            aggregated, weights = self.st_attention.forward(
                layer_features, layer_features, layer_features
            )
        else:
            aggregated = []
            weights = None

        return {
            "layer_encodings": layer_encodings,
            "aggregated_encoding": aggregated[-1] if aggregated else None,
            "layer_attention_weights": weights,
            "num_layers": num_layers,
        }

    def predict_part_quality(
        self,
        layer_images: List[Any],
        layer_sensors: List[TemporalSequence]
    ) -> Dict[str, Any]:
        """
        Predict final part quality from layer sequence.

        Args:
            layer_images: Image for each layer
            layer_sensors: Sensor data for each layer

        Returns:
            Part quality prediction with layer analysis
        """
        encoding = self.encode_layer_sequence(layer_images, layer_sensors)

        # Predict layer-wise quality
        layer_qualities = []
        for i, enc in enumerate(encoding["layer_encodings"]):
            # Simulated quality prediction for each layer
            quality = random.uniform(0.7, 1.0)
            layer_qualities.append({
                "layer": i + 1,
                "quality": round(quality, 3),
            })

        # Final part quality (weighted by layer importance)
        if layer_qualities:
            # Later layers often more important for surface quality
            weights = [1.0 + 0.5 * (i / len(layer_qualities))
                       for i in range(len(layer_qualities))]
            total_weight = sum(weights)
            part_quality = sum(
                lq["quality"] * w
                for lq, w in zip(layer_qualities, weights)
            ) / total_weight
        else:
            part_quality = 0.0

        # Identify problematic layers
        problematic_layers = [
            lq for lq in layer_qualities if lq["quality"] < 0.8
        ]

        return {
            "part_quality": round(part_quality, 3),
            "layer_qualities": layer_qualities,
            "num_layers": encoding["num_layers"],
            "problematic_layers": problematic_layers,
            "quality_grade": self._quality_to_grade(part_quality),
        }

    def _quality_to_grade(self, quality: float) -> str:
        """Convert quality score to grade."""
        if quality >= 0.95:
            return "A"
        elif quality >= 0.85:
            return "B"
        elif quality >= 0.75:
            return "C"
        elif quality >= 0.65:
            return "D"
        else:
            return "F"

    def predict_future_quality(
        self,
        current_layers: int,
        total_layers: int,
        layer_images: List[Any],
        layer_sensors: List[TemporalSequence]
    ) -> Dict[str, Any]:
        """
        Predict quality of remaining layers.

        Useful for early warning during printing.
        """
        encoding = self.encode_layer_sequence(layer_images, layer_sensors)

        # Analyze trend from current layers
        if len(encoding["layer_encodings"]) < 3:
            trend = 0.0
        else:
            # Simulated trend analysis
            trend = random.uniform(-0.02, 0.02)

        # Predict remaining layers
        remaining_layers = total_layers - current_layers
        predicted_qualities = []

        base_quality = random.uniform(0.75, 0.95)
        for i in range(remaining_layers):
            predicted_quality = base_quality + trend * i
            predicted_quality = max(0.5, min(1.0, predicted_quality))
            predicted_qualities.append(round(predicted_quality, 3))

        # Risk assessment
        min_predicted = min(predicted_qualities) if predicted_qualities else 1.0
        risk_level = "low" if min_predicted > 0.8 else ("medium" if min_predicted > 0.65 else "high")

        return {
            "current_layer": current_layers,
            "total_layers": total_layers,
            "remaining_layers": remaining_layers,
            "predicted_qualities": predicted_qualities,
            "trend": round(trend, 4),
            "risk_level": risk_level,
            "recommendation": self._get_recommendation(trend, min_predicted),
        }

    def _get_recommendation(self, trend: float, min_quality: float) -> str:
        """Get recommendation based on prediction."""
        if trend < -0.01 and min_quality < 0.7:
            return "Consider pausing print for inspection"
        elif trend < 0:
            return "Monitor closely - quality declining"
        elif min_quality < 0.8:
            return "Quality below optimal - check process parameters"
        else:
            return "Process running normally"


# Module exports
__all__ = [
    # Enums
    "TemporalAggregation",
    # Data classes
    "TemporalConfig",
    "TemporalFeature",
    "TemporalSequence",
    # Classes
    "TimeSeriesEncoder",
    "ImageSequenceEncoder",
    "TemporalAttention",
    "TemporalFusion",
    "SpatioTemporalFusion",
]
