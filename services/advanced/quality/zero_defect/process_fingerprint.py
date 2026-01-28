"""
Process Fingerprint - Production Run Signature Analysis

LegoMCP World-Class Manufacturing System v5.0
Phase 21: Zero-Defect Manufacturing

Creates and compares process signatures:
- Golden batch fingerprint from known-good runs
- Real-time fingerprint comparison
- Drift detection and alerting
- Process capability tracking
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class ProcessFeatures:
    """Features extracted from a production run."""
    run_id: str
    timestamp: datetime
    part_id: str
    machine_id: str

    # Temperature features
    avg_nozzle_temp: float = 210.0
    std_nozzle_temp: float = 0.5
    max_nozzle_temp: float = 212.0
    min_nozzle_temp: float = 208.0

    # Speed features
    avg_print_speed: float = 40.0
    std_print_speed: float = 1.0

    # Extrusion features
    avg_flow_rate: float = 100.0
    std_flow_rate: float = 1.0
    total_extrusion_length: float = 0.0

    # Time features
    total_time_seconds: float = 0.0
    avg_layer_time: float = 0.0
    std_layer_time: float = 0.0

    # Quality outcomes
    final_quality_score: float = 100.0
    defect_count: int = 0
    first_pass_yield: float = 100.0

    # Derived features
    temp_stability: float = 1.0  # Lower is more stable
    speed_consistency: float = 1.0
    process_stability_index: float = 1.0

    def to_vector(self) -> np.ndarray:
        """Convert to feature vector."""
        return np.array([
            self.avg_nozzle_temp,
            self.std_nozzle_temp,
            self.avg_print_speed,
            self.std_print_speed,
            self.avg_flow_rate,
            self.std_flow_rate,
            self.avg_layer_time,
            self.std_layer_time,
            self.temp_stability,
            self.speed_consistency,
        ], dtype=np.float32)


@dataclass
class Fingerprint:
    """Process fingerprint from known-good runs."""
    fingerprint_id: str
    part_id: str
    machine_id: str
    created_at: datetime
    sample_count: int

    # Statistical profile
    feature_means: np.ndarray
    feature_stds: np.ndarray
    feature_names: List[str]

    # Correlation structure
    covariance_matrix: Optional[np.ndarray] = None

    # Thresholds
    warning_threshold: float = 2.0  # Standard deviations
    critical_threshold: float = 3.0

    # Metadata
    quality_targets: Dict[str, float] = field(default_factory=dict)

    def get_distance(self, features: ProcessFeatures) -> float:
        """Calculate Mahalanobis distance to fingerprint."""
        feature_vector = features.to_vector()

        # Standardized distance
        diff = feature_vector - self.feature_means
        standardized = diff / (self.feature_stds + 1e-10)

        # Euclidean distance in standardized space
        distance = np.sqrt(np.sum(standardized ** 2))

        return float(distance)

    def is_within_spec(self, features: ProcessFeatures) -> Tuple[bool, float]:
        """Check if features are within specification."""
        distance = self.get_distance(features)
        return distance <= self.warning_threshold, distance


@dataclass
class DriftAnalysis:
    """Analysis of process drift over time."""
    analysis_timestamp: datetime
    part_id: str
    machine_id: str

    # Drift metrics
    is_drifting: bool = False
    drift_direction: str = "none"  # none, increasing, decreasing
    drift_rate: float = 0.0  # per hour
    drift_significance: float = 0.0  # 0-1

    # Per-feature drift
    feature_drifts: Dict[str, float] = field(default_factory=dict)
    drifting_features: List[str] = field(default_factory=list)

    # Trend
    trend_slope: float = 0.0
    trend_r_squared: float = 0.0

    # Recommendations
    recommended_action: str = "none"
    urgency: str = "low"


class ProcessFingerprint:
    """
    Creates and manages process fingerprints.

    A fingerprint represents the "signature" of a good production run,
    used for comparison and drift detection.
    """

    FEATURE_NAMES = [
        'avg_nozzle_temp',
        'std_nozzle_temp',
        'avg_print_speed',
        'std_print_speed',
        'avg_flow_rate',
        'std_flow_rate',
        'avg_layer_time',
        'std_layer_time',
        'temp_stability',
        'speed_consistency',
    ]

    def __init__(
        self,
        min_samples: int = 10,
        config: Optional[Dict[str, Any]] = None,
    ):
        self.min_samples = min_samples
        self.config = config or {}

        # Stored fingerprints
        self._fingerprints: Dict[str, Fingerprint] = {}

        # Historical data for fingerprint creation
        self._good_runs: Dict[str, List[ProcessFeatures]] = {}

    def add_good_run(
        self,
        features: ProcessFeatures,
        quality_verified: bool = True
    ) -> None:
        """Add a verified good run for fingerprint creation."""
        if not quality_verified:
            return

        key = f"{features.part_id}:{features.machine_id}"
        if key not in self._good_runs:
            self._good_runs[key] = []

        self._good_runs[key].append(features)
        logger.debug(f"Added good run for {key}. Total: {len(self._good_runs[key])}")

    def create_fingerprint(
        self,
        part_id: str,
        machine_id: str,
        force: bool = False
    ) -> Optional[Fingerprint]:
        """
        Create fingerprint from accumulated good runs.

        Args:
            part_id: Part identifier
            machine_id: Machine identifier
            force: Create even with fewer than min_samples

        Returns:
            Created fingerprint or None if insufficient data
        """
        from uuid import uuid4

        key = f"{part_id}:{machine_id}"
        runs = self._good_runs.get(key, [])

        if len(runs) < self.min_samples and not force:
            logger.warning(f"Insufficient samples for fingerprint: {len(runs)} < {self.min_samples}")
            return None

        if not runs:
            return None

        # Convert to matrix
        feature_matrix = np.array([r.to_vector() for r in runs])

        # Calculate statistics
        means = np.mean(feature_matrix, axis=0)
        stds = np.std(feature_matrix, axis=0)

        # Calculate covariance if enough samples
        cov = None
        if len(runs) >= 20:
            cov = np.cov(feature_matrix.T)

        fingerprint = Fingerprint(
            fingerprint_id=str(uuid4()),
            part_id=part_id,
            machine_id=machine_id,
            created_at=datetime.utcnow(),
            sample_count=len(runs),
            feature_means=means,
            feature_stds=stds,
            feature_names=self.FEATURE_NAMES.copy(),
            covariance_matrix=cov,
            quality_targets={
                'min_quality_score': 95.0,
                'max_defect_rate': 0.02,
            },
        )

        self._fingerprints[key] = fingerprint
        logger.info(f"Created fingerprint for {key} from {len(runs)} samples")

        return fingerprint

    def get_fingerprint(self, part_id: str, machine_id: str) -> Optional[Fingerprint]:
        """Get fingerprint for part/machine combination."""
        key = f"{part_id}:{machine_id}"
        return self._fingerprints.get(key)

    def compare_to_fingerprint(
        self,
        current: ProcessFeatures,
        fingerprint: Optional[Fingerprint] = None
    ) -> Dict[str, Any]:
        """
        Compare current run to fingerprint.

        Returns similarity analysis.
        """
        if fingerprint is None:
            fingerprint = self.get_fingerprint(current.part_id, current.machine_id)

        if fingerprint is None:
            return {
                'status': 'no_fingerprint',
                'message': 'No fingerprint available for comparison',
            }

        distance = fingerprint.get_distance(current)
        within_spec, _ = fingerprint.is_within_spec(current)

        # Per-feature comparison
        current_vector = current.to_vector()
        feature_deviations = {}

        for i, name in enumerate(fingerprint.feature_names):
            deviation = (current_vector[i] - fingerprint.feature_means[i]) / (fingerprint.feature_stds[i] + 1e-10)
            feature_deviations[name] = float(deviation)

        # Find outlier features
        outlier_features = [
            name for name, dev in feature_deviations.items()
            if abs(dev) > fingerprint.warning_threshold
        ]

        # Determine status
        if distance <= fingerprint.warning_threshold:
            status = 'good'
            similarity = 100 - (distance / fingerprint.warning_threshold * 30)
        elif distance <= fingerprint.critical_threshold:
            status = 'warning'
            similarity = 70 - ((distance - fingerprint.warning_threshold) /
                             (fingerprint.critical_threshold - fingerprint.warning_threshold) * 30)
        else:
            status = 'critical'
            similarity = max(0, 40 - (distance - fingerprint.critical_threshold) * 10)

        return {
            'status': status,
            'distance': float(distance),
            'similarity_percent': float(max(0, min(100, similarity))),
            'within_spec': within_spec,
            'feature_deviations': feature_deviations,
            'outlier_features': outlier_features,
            'fingerprint_samples': fingerprint.sample_count,
        }


class FingerprintMatcher:
    """
    Matches production runs against fingerprints and detects drift.
    """

    def __init__(
        self,
        fingerprint_store: ProcessFingerprint,
        history_window: int = 50,
    ):
        self.store = fingerprint_store
        self.history_window = history_window

        # Recent runs for drift analysis
        self._recent_runs: Dict[str, List[Tuple[datetime, ProcessFeatures]]] = {}

    def match(self, features: ProcessFeatures) -> Dict[str, Any]:
        """Match current run against fingerprint."""
        # Get fingerprint
        fingerprint = self.store.get_fingerprint(features.part_id, features.machine_id)

        # Compare
        comparison = self.store.compare_to_fingerprint(features, fingerprint)

        # Store for drift analysis
        key = f"{features.part_id}:{features.machine_id}"
        if key not in self._recent_runs:
            self._recent_runs[key] = []

        self._recent_runs[key].append((features.timestamp, features))

        # Keep window size
        if len(self._recent_runs[key]) > self.history_window:
            self._recent_runs[key] = self._recent_runs[key][-self.history_window:]

        return comparison

    def detect_drift(
        self,
        part_id: str,
        machine_id: str,
    ) -> DriftAnalysis:
        """Detect process drift from recent runs."""
        key = f"{part_id}:{machine_id}"
        runs = self._recent_runs.get(key, [])

        analysis = DriftAnalysis(
            analysis_timestamp=datetime.utcnow(),
            part_id=part_id,
            machine_id=machine_id,
        )

        if len(runs) < 10:
            analysis.recommended_action = "Insufficient data for drift analysis"
            return analysis

        # Get fingerprint for comparison
        fingerprint = self.store.get_fingerprint(part_id, machine_id)
        if fingerprint is None:
            analysis.recommended_action = "No fingerprint for drift comparison"
            return analysis

        # Analyze each feature
        timestamps = np.array([(r[0] - runs[0][0]).total_seconds() / 3600 for r in runs])  # Hours
        features_matrix = np.array([r[1].to_vector() for r in runs])

        drifting_features = []
        feature_drifts = {}

        for i, name in enumerate(ProcessFingerprint.FEATURE_NAMES):
            values = features_matrix[:, i]

            # Linear regression for trend
            slope, intercept = np.polyfit(timestamps, values, 1)
            predicted = slope * timestamps + intercept
            residuals = values - predicted
            ss_res = np.sum(residuals ** 2)
            ss_tot = np.sum((values - np.mean(values)) ** 2)
            r_squared = 1 - (ss_res / (ss_tot + 1e-10))

            # Normalize slope by feature std
            normalized_slope = slope / (fingerprint.feature_stds[i] + 1e-10)
            feature_drifts[name] = float(normalized_slope)

            # Check if significant drift
            if abs(normalized_slope) > 0.1 and r_squared > 0.5:
                drifting_features.append(name)

        analysis.feature_drifts = feature_drifts
        analysis.drifting_features = drifting_features

        if drifting_features:
            analysis.is_drifting = True

            # Determine overall drift direction
            avg_drift = np.mean(list(feature_drifts.values()))
            if avg_drift > 0.05:
                analysis.drift_direction = "increasing"
            elif avg_drift < -0.05:
                analysis.drift_direction = "decreasing"

            analysis.drift_rate = float(abs(avg_drift))
            analysis.drift_significance = min(1.0, len(drifting_features) / 5)

            # Recommendations
            if analysis.drift_significance > 0.5:
                analysis.recommended_action = "Process recalibration recommended"
                analysis.urgency = "high"
            else:
                analysis.recommended_action = "Monitor closely"
                analysis.urgency = "medium"

        return analysis

    def get_trend(
        self,
        part_id: str,
        machine_id: str,
        feature_name: str,
    ) -> Dict[str, Any]:
        """Get trend for a specific feature."""
        key = f"{part_id}:{machine_id}"
        runs = self._recent_runs.get(key, [])

        if len(runs) < 5:
            return {'status': 'insufficient_data'}

        feature_idx = ProcessFingerprint.FEATURE_NAMES.index(feature_name)
        timestamps = [(r[0] - runs[0][0]).total_seconds() / 3600 for r in runs]
        values = [r[1].to_vector()[feature_idx] for r in runs]

        slope, intercept = np.polyfit(timestamps, values, 1)

        return {
            'feature': feature_name,
            'samples': len(runs),
            'current_value': values[-1],
            'trend_slope': float(slope),
            'trend_direction': 'increasing' if slope > 0 else 'decreasing',
            'first_value': values[0],
            'last_value': values[-1],
            'min_value': min(values),
            'max_value': max(values),
        }


class GoldenBatchComparison:
    """
    Compare current production to golden batch reference.

    A "golden batch" represents the ideal production run with
    perfect quality outcomes.
    """

    def __init__(self, fingerprint_store: ProcessFingerprint):
        self.store = fingerprint_store
        self._golden_batches: Dict[str, ProcessFeatures] = {}

    def set_golden_batch(self, features: ProcessFeatures) -> None:
        """Set a run as the golden batch reference."""
        key = f"{features.part_id}:{features.machine_id}"
        self._golden_batches[key] = features
        logger.info(f"Set golden batch for {key}")

    def compare_to_golden(
        self,
        current: ProcessFeatures
    ) -> Dict[str, Any]:
        """Compare current run to golden batch."""
        key = f"{current.part_id}:{current.machine_id}"
        golden = self._golden_batches.get(key)

        if golden is None:
            return {
                'status': 'no_golden_batch',
                'message': 'No golden batch reference set',
            }

        current_vector = current.to_vector()
        golden_vector = golden.to_vector()

        # Calculate differences
        differences = {}
        for i, name in enumerate(ProcessFingerprint.FEATURE_NAMES):
            diff = current_vector[i] - golden_vector[i]
            pct_diff = diff / (golden_vector[i] + 1e-10) * 100
            differences[name] = {
                'golden': float(golden_vector[i]),
                'current': float(current_vector[i]),
                'difference': float(diff),
                'percent_difference': float(pct_diff),
            }

        # Overall similarity
        euclidean_dist = np.linalg.norm(current_vector - golden_vector)
        max_dist = np.linalg.norm(golden_vector)  # Rough scaling
        similarity = max(0, 100 - (euclidean_dist / (max_dist + 1e-10) * 100))

        return {
            'status': 'compared',
            'similarity_percent': float(similarity),
            'differences': differences,
            'golden_quality_score': golden.final_quality_score,
            'current_quality_score': current.final_quality_score,
            'quality_gap': golden.final_quality_score - current.final_quality_score,
        }
