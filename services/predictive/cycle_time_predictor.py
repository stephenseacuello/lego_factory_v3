"""
Cycle Time Predictor for CNC Manufacturing.

Predicts job cycle times based on G-code features, machine type, and material.
"""

import logging
from dataclasses import dataclass, field
from typing import Optional, Dict, List, Any, Tuple
from datetime import datetime
from enum import Enum
import json
import math

logger = logging.getLogger(__name__)


@dataclass
class GCodeFeatures:
    """Features extracted from G-code for prediction."""
    line_count: int = 0
    move_count: int = 0
    rapid_count: int = 0
    cut_count: int = 0
    arc_count: int = 0
    tool_changes: int = 0
    total_distance: float = 0.0  # mm
    rapid_distance: float = 0.0  # mm
    cut_distance: float = 0.0  # mm
    max_feed_rate: float = 0.0  # mm/min
    avg_feed_rate: float = 0.0  # mm/min
    max_spindle_speed: float = 0.0  # rpm
    max_depth: float = 0.0  # mm
    x_range: float = 0.0  # mm
    y_range: float = 0.0  # mm
    z_range: float = 0.0  # mm

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "line_count": self.line_count,
            "move_count": self.move_count,
            "rapid_count": self.rapid_count,
            "cut_count": self.cut_count,
            "arc_count": self.arc_count,
            "tool_changes": self.tool_changes,
            "total_distance": self.total_distance,
            "rapid_distance": self.rapid_distance,
            "cut_distance": self.cut_distance,
            "max_feed_rate": self.max_feed_rate,
            "avg_feed_rate": self.avg_feed_rate,
            "max_spindle_speed": self.max_spindle_speed,
            "max_depth": self.max_depth,
            "x_range": self.x_range,
            "y_range": self.y_range,
            "z_range": self.z_range,
        }


@dataclass
class CycleTimePrediction:
    """Cycle time prediction result."""
    predicted_seconds: float
    confidence: float  # 0-1
    lower_bound_seconds: float  # 95% CI lower
    upper_bound_seconds: float  # 95% CI upper

    # Breakdown
    cut_time_seconds: float = 0.0
    rapid_time_seconds: float = 0.0
    tool_change_seconds: float = 0.0
    spindle_time_seconds: float = 0.0
    overhead_seconds: float = 0.0

    # Factors
    material_factor: float = 1.0
    machine_factor: float = 1.0
    complexity_factor: float = 1.0

    # Metadata
    method: str = "analytical"  # analytical, ml, hybrid
    model_version: str = ""
    features_used: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "predicted_seconds": self.predicted_seconds,
            "predicted_formatted": self.format_time(self.predicted_seconds),
            "confidence": self.confidence,
            "confidence_interval": {
                "lower": self.lower_bound_seconds,
                "upper": self.upper_bound_seconds,
                "lower_formatted": self.format_time(self.lower_bound_seconds),
                "upper_formatted": self.format_time(self.upper_bound_seconds),
            },
            "breakdown": {
                "cut_time": self.cut_time_seconds,
                "rapid_time": self.rapid_time_seconds,
                "tool_change_time": self.tool_change_seconds,
                "spindle_time": self.spindle_time_seconds,
                "overhead": self.overhead_seconds,
            },
            "factors": {
                "material": self.material_factor,
                "machine": self.machine_factor,
                "complexity": self.complexity_factor,
            },
            "method": self.method,
            "model_version": self.model_version,
            "warnings": self.warnings,
        }

    @staticmethod
    def format_time(seconds: float) -> str:
        """Format seconds to human-readable time."""
        if seconds < 60:
            return f"{seconds:.1f}s"
        elif seconds < 3600:
            mins = int(seconds // 60)
            secs = int(seconds % 60)
            return f"{mins}m {secs}s"
        else:
            hours = int(seconds // 3600)
            mins = int((seconds % 3600) // 60)
            return f"{hours}h {mins}m"


class CycleTimePredictor:
    """
    Predicts cycle times for CNC machining operations.

    Uses multiple methods:
    - Analytical: Physics-based calculation from G-code
    - ML: Historical data-driven prediction
    - Hybrid: Combines both approaches
    """

    # Material cutting speed factors (relative to aluminum)
    MATERIAL_FACTORS = {
        "aluminum": 1.0,
        "aluminium": 1.0,
        "steel": 2.0,
        "stainless": 2.5,
        "stainless steel": 2.5,
        "brass": 0.8,
        "copper": 0.9,
        "titanium": 4.0,
        "plastic": 0.5,
        "acrylic": 0.6,
        "wood": 0.4,
        "hardwood": 0.6,
        "softwood": 0.3,
        "composite": 1.5,
        "carbon fiber": 2.0,
        "cast iron": 1.8,
        "tool steel": 3.0,
    }

    # Machine type factors
    MACHINE_FACTORS = {
        "router": 0.9,  # Fast rapids
        "mill": 1.0,
        "lathe": 0.8,
        "laser": 0.3,  # Very fast
        "edm": 5.0,  # Very slow
        "waterjet": 2.0,
    }

    # Tool change times by machine type (seconds)
    TOOL_CHANGE_TIMES = {
        "router": 5.0,
        "mill": 8.0,
        "lathe": 6.0,
        "laser": 0.0,
        "edm": 30.0,
        "waterjet": 0.0,
    }

    def __init__(
        self,
        model_path: Optional[str] = None,
        use_ml: bool = False,
    ):
        """
        Initialize cycle time predictor.

        Args:
            model_path: Path to ML model (if using ML)
            use_ml: Whether to use ML predictions
        """
        self.model_path = model_path
        self.use_ml = use_ml
        self._model = None
        self._scaler = None

        if use_ml and model_path:
            self._load_model()

    def _load_model(self):
        """Load ML model from disk."""
        try:
            import joblib

            self._model = joblib.load(f"{self.model_path}/cycle_time_model.pkl")
            self._scaler = joblib.load(f"{self.model_path}/cycle_time_scaler.pkl")
            logger.info("Loaded cycle time ML model")
        except Exception as e:
            logger.warning(f"Could not load ML model: {e}")
            self.use_ml = False

    def extract_features(self, gcode: str) -> GCodeFeatures:
        """
        Extract features from G-code.

        Args:
            gcode: G-code program text

        Returns:
            Extracted features
        """
        features = GCodeFeatures()

        lines = gcode.strip().split('\n')
        features.line_count = len(lines)

        feed_rates = []
        spindle_speeds = []
        x_positions = []
        y_positions = []
        z_positions = []

        current_x = 0.0
        current_y = 0.0
        current_z = 0.0
        current_feed = 0.0
        is_rapid = False

        import re

        for line in lines:
            line = line.strip().upper()

            # Skip comments
            if not line or line.startswith('(') or line.startswith(';'):
                continue

            # Detect move type
            if 'G0' in line or 'G00' in line:
                is_rapid = True
                features.rapid_count += 1
                features.move_count += 1
            elif 'G1' in line or 'G01' in line:
                is_rapid = False
                features.cut_count += 1
                features.move_count += 1
            elif 'G2' in line or 'G02' in line or 'G3' in line or 'G03' in line:
                is_rapid = False
                features.arc_count += 1
                features.move_count += 1

            # Tool changes
            if 'M6' in line or 'M06' in line:
                features.tool_changes += 1

            # Extract coordinates and calculate distance
            new_x = current_x
            new_y = current_y
            new_z = current_z

            x_match = re.search(r'X(-?[\d.]+)', line)
            y_match = re.search(r'Y(-?[\d.]+)', line)
            z_match = re.search(r'Z(-?[\d.]+)', line)
            f_match = re.search(r'F([\d.]+)', line)
            s_match = re.search(r'S([\d.]+)', line)

            if x_match:
                new_x = float(x_match.group(1))
                x_positions.append(new_x)
            if y_match:
                new_y = float(y_match.group(1))
                y_positions.append(new_y)
            if z_match:
                new_z = float(z_match.group(1))
                z_positions.append(new_z)
            if f_match:
                current_feed = float(f_match.group(1))
                feed_rates.append(current_feed)
            if s_match:
                spindle_speeds.append(float(s_match.group(1)))

            # Calculate distance for this move
            distance = math.sqrt(
                (new_x - current_x) ** 2 +
                (new_y - current_y) ** 2 +
                (new_z - current_z) ** 2
            )

            features.total_distance += distance
            if is_rapid:
                features.rapid_distance += distance
            else:
                features.cut_distance += distance

            current_x, current_y, current_z = new_x, new_y, new_z

        # Calculate statistics
        if feed_rates:
            features.max_feed_rate = max(feed_rates)
            features.avg_feed_rate = sum(feed_rates) / len(feed_rates)
        if spindle_speeds:
            features.max_spindle_speed = max(spindle_speeds)
        if z_positions:
            features.max_depth = abs(min(z_positions))
        if x_positions:
            features.x_range = max(x_positions) - min(x_positions)
        if y_positions:
            features.y_range = max(y_positions) - min(y_positions)
        if z_positions:
            features.z_range = max(z_positions) - min(z_positions)

        return features

    def predict_analytical(
        self,
        features: GCodeFeatures,
        material: str = "aluminum",
        machine_type: str = "mill",
        rapid_rate: float = 5000.0,  # mm/min
    ) -> CycleTimePrediction:
        """
        Predict cycle time using analytical method.

        Args:
            features: G-code features
            material: Workpiece material
            machine_type: Type of CNC machine
            rapid_rate: Machine rapid traverse rate

        Returns:
            Cycle time prediction
        """
        warnings = []

        # Get factors
        material_factor = self.MATERIAL_FACTORS.get(material.lower(), 1.0)
        machine_factor = self.MACHINE_FACTORS.get(machine_type.lower(), 1.0)
        tool_change_time = self.TOOL_CHANGE_TIMES.get(machine_type.lower(), 10.0)

        # Calculate cut time
        if features.avg_feed_rate > 0:
            # Adjust feed rate by material factor
            effective_feed = features.avg_feed_rate / material_factor
            cut_time = (features.cut_distance / effective_feed) * 60  # seconds
        else:
            # Estimate from move count
            cut_time = features.cut_count * 2.0  # 2 seconds per cut
            warnings.append("No feed rate found, using estimate")

        # Calculate rapid time
        if rapid_rate > 0:
            rapid_time = (features.rapid_distance / rapid_rate) * 60
        else:
            rapid_time = features.rapid_count * 0.5  # 0.5 seconds per rapid

        # Calculate arc time (arcs typically slower)
        arc_time = features.arc_count * 1.5  # 1.5 seconds per arc average

        # Tool change time
        tool_change_total = features.tool_changes * tool_change_time

        # Spindle ramp up/down time
        spindle_time = features.tool_changes * 3.0  # 3 seconds per spindle change

        # Overhead (program load, probing, etc.)
        overhead = 10.0 + (features.line_count * 0.001)  # Base + per-line overhead

        # Calculate complexity factor
        complexity_factor = self._calculate_complexity(features)

        # Total time
        base_time = cut_time + rapid_time + arc_time + tool_change_total + spindle_time
        total_time = (base_time * machine_factor * complexity_factor) + overhead

        # Calculate confidence interval (wider for less data)
        confidence = 0.85  # Analytical confidence
        variance = 0.15 * total_time  # 15% variance

        if features.avg_feed_rate == 0:
            confidence -= 0.2
            variance *= 2

        return CycleTimePrediction(
            predicted_seconds=total_time,
            confidence=max(0.5, confidence),
            lower_bound_seconds=max(0, total_time - 1.96 * variance),
            upper_bound_seconds=total_time + 1.96 * variance,
            cut_time_seconds=cut_time * machine_factor,
            rapid_time_seconds=rapid_time,
            tool_change_seconds=tool_change_total,
            spindle_time_seconds=spindle_time,
            overhead_seconds=overhead,
            material_factor=material_factor,
            machine_factor=machine_factor,
            complexity_factor=complexity_factor,
            method="analytical",
            model_version="1.0.0",
            features_used=["cut_distance", "rapid_distance", "tool_changes", "feed_rate"],
            warnings=warnings,
        )

    def predict_ml(
        self,
        features: GCodeFeatures,
        material: str = "aluminum",
        machine_type: str = "mill",
    ) -> Optional[CycleTimePrediction]:
        """
        Predict cycle time using ML model.

        Args:
            features: G-code features
            material: Workpiece material
            machine_type: Type of CNC machine

        Returns:
            Cycle time prediction or None if ML not available
        """
        if not self.use_ml or self._model is None:
            return None

        try:
            # Prepare feature vector
            feature_vector = [
                features.line_count,
                features.move_count,
                features.cut_count,
                features.rapid_count,
                features.arc_count,
                features.tool_changes,
                features.total_distance,
                features.cut_distance,
                features.rapid_distance,
                features.avg_feed_rate,
                features.max_feed_rate,
                features.max_depth,
                self.MATERIAL_FACTORS.get(material.lower(), 1.0),
                self.MACHINE_FACTORS.get(machine_type.lower(), 1.0),
            ]

            # Scale features
            import numpy as np
            X = np.array(feature_vector).reshape(1, -1)
            if self._scaler:
                X = self._scaler.transform(X)

            # Predict
            prediction = self._model.predict(X)[0]

            # Get confidence interval if available
            if hasattr(self._model, 'predict_proba'):
                # For models with uncertainty estimation
                lower = prediction * 0.8
                upper = prediction * 1.2
                confidence = 0.9
            else:
                lower = prediction * 0.85
                upper = prediction * 1.15
                confidence = 0.85

            return CycleTimePrediction(
                predicted_seconds=prediction,
                confidence=confidence,
                lower_bound_seconds=lower,
                upper_bound_seconds=upper,
                method="ml",
                model_version=getattr(self._model, '__version__', '1.0'),
                features_used=list(range(14)),
            )

        except Exception as e:
            logger.error(f"ML prediction failed: {e}")
            return None

    def predict(
        self,
        gcode: str,
        material: str = "aluminum",
        machine_type: str = "mill",
        rapid_rate: float = 5000.0,
        method: str = "auto",
    ) -> CycleTimePrediction:
        """
        Predict cycle time for G-code program.

        Args:
            gcode: G-code program text
            material: Workpiece material
            machine_type: Type of CNC machine
            rapid_rate: Machine rapid traverse rate
            method: Prediction method (auto, analytical, ml, hybrid)

        Returns:
            Cycle time prediction
        """
        # Extract features
        features = self.extract_features(gcode)

        # Choose method
        if method == "auto":
            method = "ml" if self.use_ml else "analytical"

        if method == "ml":
            ml_result = self.predict_ml(features, material, machine_type)
            if ml_result:
                return ml_result
            # Fall back to analytical
            method = "analytical"

        if method == "analytical":
            return self.predict_analytical(
                features, material, machine_type, rapid_rate
            )

        if method == "hybrid":
            # Combine ML and analytical
            analytical = self.predict_analytical(
                features, material, machine_type, rapid_rate
            )
            ml_result = self.predict_ml(features, material, machine_type)

            if ml_result:
                # Weighted average
                ml_weight = ml_result.confidence
                ana_weight = analytical.confidence

                total_weight = ml_weight + ana_weight
                combined = (
                    (ml_result.predicted_seconds * ml_weight) +
                    (analytical.predicted_seconds * ana_weight)
                ) / total_weight

                return CycleTimePrediction(
                    predicted_seconds=combined,
                    confidence=(ml_result.confidence + analytical.confidence) / 2,
                    lower_bound_seconds=min(
                        ml_result.lower_bound_seconds,
                        analytical.lower_bound_seconds
                    ),
                    upper_bound_seconds=max(
                        ml_result.upper_bound_seconds,
                        analytical.upper_bound_seconds
                    ),
                    method="hybrid",
                    model_version="1.0.0",
                    features_used=analytical.features_used,
                )

            return analytical

        return self.predict_analytical(features, material, machine_type, rapid_rate)

    def _calculate_complexity(self, features: GCodeFeatures) -> float:
        """
        Calculate machining complexity factor.

        Higher complexity = longer time due to:
        - Many small moves
        - Complex geometry (arcs)
        - Deep Z operations
        """
        complexity = 1.0

        # Arc complexity
        if features.move_count > 0:
            arc_ratio = features.arc_count / features.move_count
            complexity += arc_ratio * 0.2

        # Move density (lots of short moves = complex)
        if features.total_distance > 0:
            avg_move_length = features.total_distance / max(1, features.move_count)
            if avg_move_length < 1.0:  # Very short moves
                complexity += 0.15
            elif avg_move_length < 5.0:  # Short moves
                complexity += 0.05

        # Depth complexity
        if features.max_depth > 50:  # Deep pockets
            complexity += 0.1

        return min(1.5, complexity)  # Cap at 1.5x

    def compare_estimates(
        self,
        gcode: str,
        material: str = "aluminum",
        machine_type: str = "mill",
    ) -> Dict[str, Any]:
        """
        Compare analytical and ML estimates.

        Useful for validating ML model accuracy.
        """
        features = self.extract_features(gcode)

        analytical = self.predict_analytical(features, material, machine_type)
        ml_result = self.predict_ml(features, material, machine_type)

        comparison = {
            "features": features.to_dict(),
            "analytical": analytical.to_dict(),
            "ml": ml_result.to_dict() if ml_result else None,
        }

        if ml_result:
            diff = abs(ml_result.predicted_seconds - analytical.predicted_seconds)
            pct_diff = diff / analytical.predicted_seconds * 100
            comparison["difference"] = {
                "absolute_seconds": diff,
                "percentage": pct_diff,
                "agreement": pct_diff < 20,  # Within 20%
            }

        return comparison
