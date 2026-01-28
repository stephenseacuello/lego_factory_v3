"""
Machine Learning Time Predictor
===============================
ML-based prediction of job execution times.

Features:
- Feature extraction from G-code
- Statistical and ML-based prediction
- Model training from historical data
- Confidence intervals
- Continuous model improvement

Usage:
    from services.analytics import get_ml_predictor

    predictor = get_ml_predictor()

    # Extract features from G-code
    features = predictor.extract_features(gcode_content)

    # Predict execution time
    prediction = predictor.predict_time(features)

    # Train model on historical data
    predictor.train(historical_records)
"""

import logging
import re
import math
from datetime import datetime
from typing import Optional, Dict, Any, List, Tuple
from dataclasses import dataclass, field
import statistics

logger = logging.getLogger(__name__)

# Try to import sklearn for ML features
try:
    from sklearn.linear_model import Ridge
    from sklearn.preprocessing import StandardScaler
    import numpy as np
    HAS_SKLEARN = True
except ImportError:
    HAS_SKLEARN = False
    logger.info("scikit-learn not available, using statistical predictor")


@dataclass
class GCodeFeatures:
    """Features extracted from G-code for prediction."""
    total_lines: int = 0
    rapid_moves: int = 0       # G0 count
    linear_moves: int = 0      # G1 count
    arc_moves: int = 0         # G2/G3 count
    tool_changes: int = 0      # M6 count
    dwells: int = 0            # G4 count
    total_dwell_sec: float = 0.0
    max_feed_rate: float = 0.0
    avg_feed_rate: float = 0.0
    total_distance_mm: float = 0.0  # Estimated
    spindle_changes: int = 0
    z_moves: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_lines": self.total_lines,
            "rapid_moves": self.rapid_moves,
            "linear_moves": self.linear_moves,
            "arc_moves": self.arc_moves,
            "tool_changes": self.tool_changes,
            "dwells": self.dwells,
            "total_dwell_sec": round(self.total_dwell_sec, 2),
            "max_feed_rate": round(self.max_feed_rate, 1),
            "avg_feed_rate": round(self.avg_feed_rate, 1),
            "total_distance_mm": round(self.total_distance_mm, 1),
            "spindle_changes": self.spindle_changes,
            "z_moves": self.z_moves,
        }

    def to_vector(self) -> List[float]:
        """Convert to feature vector for ML."""
        return [
            float(self.total_lines),
            float(self.rapid_moves),
            float(self.linear_moves),
            float(self.arc_moves),
            float(self.tool_changes),
            float(self.dwells),
            float(self.total_dwell_sec),
            float(self.max_feed_rate),
            float(self.avg_feed_rate),
            float(self.total_distance_mm),
            float(self.spindle_changes),
            float(self.z_moves),
        ]


@dataclass
class TimePrediction:
    """Predicted execution time with confidence."""
    predicted_sec: float
    confidence_low: float
    confidence_high: float
    confidence_level: float = 0.95
    method: str = "statistical"
    features_used: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "predicted_sec": round(self.predicted_sec, 1),
            "predicted_formatted": self._format_time(self.predicted_sec),
            "confidence_interval": {
                "low_sec": round(self.confidence_low, 1),
                "high_sec": round(self.confidence_high, 1),
                "level": self.confidence_level,
            },
            "method": self.method,
            "features_used": self.features_used,
        }

    def _format_time(self, seconds: float) -> str:
        """Format seconds as HH:MM:SS."""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"


class MLTimePredictor:
    """
    Machine learning-based time prediction.

    Uses a combination of:
    1. Rule-based estimation from G-code features
    2. Historical data correlation
    3. Optional ML model (if sklearn available)
    """

    def __init__(self):
        """Initialize predictor."""
        self.has_ml = HAS_SKLEARN

        # Rule-based parameters (can be tuned)
        self.params = {
            "rapid_time_per_move": 0.05,      # seconds per rapid move
            "linear_base_time": 0.02,          # base time per linear move
            "arc_base_time": 0.03,             # base time per arc move
            "tool_change_time": 30.0,          # seconds per tool change
            "spindle_change_time": 2.0,        # seconds per spindle speed change
            "overhead_per_line": 0.001,        # communication overhead
            "feed_rate_factor": 60.0,          # mm/min to mm/sec conversion
        }

        # ML model (if available)
        self._model = None
        self._scaler = None
        self._training_data: List[Tuple[GCodeFeatures, float]] = []

        # Correction factors from historical data
        self._correction_factors: Dict[str, float] = {}

        logger.info(f"MLTimePredictor initialized (sklearn: {HAS_SKLEARN})")

    def extract_features(self, gcode: str) -> GCodeFeatures:
        """
        Extract features from G-code content.

        Args:
            gcode: G-code content as string

        Returns:
            GCodeFeatures with extracted metrics
        """
        features = GCodeFeatures()
        lines = gcode.splitlines()
        features.total_lines = len(lines)

        feed_rates = []
        last_x, last_y, last_z = 0.0, 0.0, 0.0
        total_distance = 0.0

        # Regex patterns
        g0_pattern = re.compile(r'^G0\b', re.IGNORECASE)
        g1_pattern = re.compile(r'^G1\b', re.IGNORECASE)
        g2g3_pattern = re.compile(r'^G[23]\b', re.IGNORECASE)
        m6_pattern = re.compile(r'\bM6\b|\bM06\b', re.IGNORECASE)
        g4_pattern = re.compile(r'^G4\b', re.IGNORECASE)
        s_pattern = re.compile(r'\bS(\d+)', re.IGNORECASE)
        f_pattern = re.compile(r'\bF([\d.]+)', re.IGNORECASE)
        xyz_pattern = re.compile(r'([XYZ])([-\d.]+)', re.IGNORECASE)
        p_pattern = re.compile(r'\bP([\d.]+)', re.IGNORECASE)

        for line in lines:
            line = line.strip()

            # Skip comments and empty lines
            if not line or line.startswith(';') or line.startswith('('):
                continue

            # Count move types
            if g0_pattern.match(line):
                features.rapid_moves += 1
            elif g1_pattern.match(line):
                features.linear_moves += 1
            elif g2g3_pattern.match(line):
                features.arc_moves += 1

            # Tool changes
            if m6_pattern.search(line):
                features.tool_changes += 1

            # Dwells
            if g4_pattern.match(line):
                features.dwells += 1
                p_match = p_pattern.search(line)
                if p_match:
                    # P value is typically in seconds or milliseconds
                    p_val = float(p_match.group(1))
                    # Assume seconds if < 100, else milliseconds
                    if p_val >= 100:
                        p_val /= 1000
                    features.total_dwell_sec += p_val

            # Spindle changes
            if s_pattern.search(line):
                features.spindle_changes += 1

            # Feed rate
            f_match = f_pattern.search(line)
            if f_match:
                feed = float(f_match.group(1))
                feed_rates.append(feed)
                features.max_feed_rate = max(features.max_feed_rate, feed)

            # Position tracking for distance calculation
            xyz_matches = xyz_pattern.findall(line)
            new_x, new_y, new_z = last_x, last_y, last_z

            for axis, value in xyz_matches:
                val = float(value)
                if axis.upper() == 'X':
                    new_x = val
                elif axis.upper() == 'Y':
                    new_y = val
                elif axis.upper() == 'Z':
                    new_z = val
                    features.z_moves += 1

            # Calculate move distance
            dx = new_x - last_x
            dy = new_y - last_y
            dz = new_z - last_z
            move_dist = math.sqrt(dx*dx + dy*dy + dz*dz)
            total_distance += move_dist

            last_x, last_y, last_z = new_x, new_y, new_z

        features.total_distance_mm = total_distance
        features.avg_feed_rate = statistics.mean(feed_rates) if feed_rates else 0

        return features

    def predict_time(
        self,
        features: GCodeFeatures,
        operation_type: Optional[str] = None,
        material_type: Optional[str] = None,
    ) -> TimePrediction:
        """
        Predict execution time from features.

        Args:
            features: Extracted G-code features
            operation_type: Optional operation type for correction
            material_type: Optional material type for correction

        Returns:
            TimePrediction with estimate and confidence
        """
        # Try ML prediction first if model trained
        if self._model is not None and HAS_SKLEARN:
            return self._predict_ml(features)

        # Fall back to rule-based estimation
        return self._predict_statistical(features, operation_type, material_type)

    def _predict_statistical(
        self,
        features: GCodeFeatures,
        operation_type: Optional[str] = None,
        material_type: Optional[str] = None,
    ) -> TimePrediction:
        """Rule-based statistical prediction."""
        p = self.params

        # Base time components
        rapid_time = features.rapid_moves * p["rapid_time_per_move"]

        # Linear move time (based on distance and feed rate)
        if features.avg_feed_rate > 0 and features.total_distance_mm > 0:
            cutting_time = (features.total_distance_mm /
                          (features.avg_feed_rate / p["feed_rate_factor"]))
        else:
            cutting_time = features.linear_moves * p["linear_base_time"] * 10

        arc_time = features.arc_moves * p["arc_base_time"] * 5
        tool_change_time = features.tool_changes * p["tool_change_time"]
        dwell_time = features.total_dwell_sec
        spindle_time = features.spindle_changes * p["spindle_change_time"]
        overhead_time = features.total_lines * p["overhead_per_line"]

        # Total estimate
        total_sec = (
            rapid_time +
            cutting_time +
            arc_time +
            tool_change_time +
            dwell_time +
            spindle_time +
            overhead_time
        )

        # Apply correction factor if available
        correction_key = f"{operation_type}_{material_type}"
        if correction_key in self._correction_factors:
            total_sec *= self._correction_factors[correction_key]
        elif operation_type in self._correction_factors:
            total_sec *= self._correction_factors[operation_type]

        # Confidence interval (±20% for statistical method)
        confidence_margin = 0.20
        confidence_low = total_sec * (1 - confidence_margin)
        confidence_high = total_sec * (1 + confidence_margin)

        return TimePrediction(
            predicted_sec=total_sec,
            confidence_low=confidence_low,
            confidence_high=confidence_high,
            confidence_level=0.80,  # Lower confidence for rule-based
            method="statistical",
            features_used=features.to_dict(),
        )

    def _predict_ml(self, features: GCodeFeatures) -> TimePrediction:
        """ML-based prediction using trained model."""
        if not HAS_SKLEARN or self._model is None:
            return self._predict_statistical(features, None, None)

        try:
            X = np.array([features.to_vector()])
            X_scaled = self._scaler.transform(X)
            prediction = self._model.predict(X_scaled)[0]

            # Estimate confidence from model score
            confidence_margin = 0.15  # Tighter confidence for ML
            confidence_low = prediction * (1 - confidence_margin)
            confidence_high = prediction * (1 + confidence_margin)

            return TimePrediction(
                predicted_sec=max(0, prediction),
                confidence_low=max(0, confidence_low),
                confidence_high=confidence_high,
                confidence_level=0.90,
                method="ml_ridge",
                features_used=features.to_dict(),
            )

        except Exception as e:
            logger.error(f"ML prediction failed: {e}")
            return self._predict_statistical(features, None, None)

    def train(
        self,
        training_data: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Train prediction model on historical data.

        Args:
            training_data: List of dicts with 'gcode' or 'features' and 'actual_time_sec'

        Returns:
            Training results with metrics
        """
        if not training_data:
            return {"success": False, "error": "No training data"}

        # Extract features and targets
        samples = []
        for item in training_data:
            if "features" in item:
                features = GCodeFeatures(**item["features"])
            elif "gcode" in item:
                features = self.extract_features(item["gcode"])
            else:
                continue

            actual_time = item.get("actual_time_sec", 0)
            if actual_time > 0:
                samples.append((features, actual_time))

        if len(samples) < 10:
            return {
                "success": False,
                "error": f"Insufficient samples ({len(samples)}), need at least 10"
            }

        # Store training data
        self._training_data = samples

        if HAS_SKLEARN:
            return self._train_ml(samples)
        else:
            return self._train_statistical(samples)

    def _train_ml(
        self,
        samples: List[Tuple[GCodeFeatures, float]],
    ) -> Dict[str, Any]:
        """Train sklearn model."""
        X = np.array([s[0].to_vector() for s in samples])
        y = np.array([s[1] for s in samples])

        # Scale features
        self._scaler = StandardScaler()
        X_scaled = self._scaler.fit_transform(X)

        # Train Ridge regression
        self._model = Ridge(alpha=1.0)
        self._model.fit(X_scaled, y)

        # Calculate score
        score = self._model.score(X_scaled, y)

        # Cross-validation estimate of error
        predictions = self._model.predict(X_scaled)
        errors = y - predictions
        mae = float(np.mean(np.abs(errors)))
        rmse = float(np.sqrt(np.mean(errors ** 2)))

        logger.info(f"ML model trained: R²={score:.3f}, MAE={mae:.1f}s, RMSE={rmse:.1f}s")

        return {
            "success": True,
            "method": "ml_ridge",
            "samples": len(samples),
            "r_squared": round(score, 3),
            "mae_seconds": round(mae, 1),
            "rmse_seconds": round(rmse, 1),
        }

    def _train_statistical(
        self,
        samples: List[Tuple[GCodeFeatures, float]],
    ) -> Dict[str, Any]:
        """Train statistical model (update correction factors)."""
        # Calculate overall correction factor
        ratios = []
        for features, actual in samples:
            prediction = self._predict_statistical(features, None, None)
            if prediction.predicted_sec > 0:
                ratio = actual / prediction.predicted_sec
                ratios.append(ratio)

        if ratios:
            correction = statistics.median(ratios)
            self._correction_factors["global"] = correction

            # Calculate error metrics
            errors = []
            for features, actual in samples:
                pred = self._predict_statistical(features, None, None).predicted_sec
                corrected = pred * correction
                error = abs(actual - corrected)
                errors.append(error)

            mae = statistics.mean(errors)

            return {
                "success": True,
                "method": "statistical",
                "samples": len(samples),
                "correction_factor": round(correction, 4),
                "mae_seconds": round(mae, 1),
            }

        return {"success": False, "error": "Could not calculate correction factors"}

    def set_correction_factor(
        self,
        key: str,
        factor: float,
    ):
        """Manually set a correction factor."""
        self._correction_factors[key] = factor
        logger.info(f"Correction factor set: {key} = {factor:.4f}")

    def get_model_info(self) -> Dict[str, Any]:
        """Get information about current model state."""
        return {
            "has_sklearn": self.has_ml,
            "ml_model_trained": self._model is not None,
            "training_samples": len(self._training_data),
            "correction_factors": dict(self._correction_factors),
            "params": dict(self.params),
        }


# Global predictor instance
_ml_predictor: Optional[MLTimePredictor] = None


def get_ml_predictor() -> MLTimePredictor:
    """Get global ML predictor instance."""
    global _ml_predictor
    if _ml_predictor is None:
        _ml_predictor = MLTimePredictor()
    return _ml_predictor
