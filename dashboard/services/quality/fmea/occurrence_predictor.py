"""
Occurrence Predictor - ML-based occurrence prediction.

LEGO MCP v6.0 World-Class Manufacturing Research Platform
Phase 2: Causal AI, Explainability, FMEA & HOQ
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
import numpy as np
import logging

logger = logging.getLogger(__name__)


@dataclass
class OccurrenceFeatures:
    """Features for occurrence prediction."""
    process_capability: float  # Cpk
    historical_rate: float  # Historical occurrence rate
    complexity_score: float  # Design/process complexity
    material_variation: float  # Material batch variation
    equipment_age: float  # Normalized equipment age
    operator_experience: float  # Operator skill level
    environmental_factors: float  # Temperature, humidity stability
    maintenance_status: float  # Equipment maintenance status


@dataclass
class OccurrencePrediction:
    """Occurrence prediction result."""
    failure_mode: str
    occurrence_rating: int  # 1-10 FMEA scale
    probability: float  # Actual probability 0-1
    confidence: float
    contributing_factors: Dict[str, float]
    recommendations: List[str]
    timestamp: datetime = field(default_factory=datetime.utcnow)


class OccurrencePredictor:
    """
    ML-based occurrence prediction for FMEA.

    Features:
    - Process capability analysis
    - Historical data learning
    - Feature importance ranking
    - Recommendation generation
    """

    def __init__(self):
        self._model_weights: Dict[str, float] = {}
        self._historical_data: List[Dict] = []
        self._process_baselines: Dict[str, float] = {}
        self._load_default_model()

    def _load_default_model(self) -> None:
        """Load default prediction model weights."""
        # Feature weights for occurrence prediction
        self._model_weights = {
            'process_capability': -0.3,  # Higher Cpk = lower occurrence
            'historical_rate': 0.4,  # Historical rate is strong predictor
            'complexity_score': 0.15,  # More complex = higher occurrence
            'material_variation': 0.1,
            'equipment_age': 0.08,
            'operator_experience': -0.05,  # More experience = lower occurrence
            'environmental_factors': 0.07,
            'maintenance_status': -0.05  # Better maintenance = lower occurrence
        }

        # Baseline occurrence rates by process type
        self._process_baselines = {
            'fdm': 0.02,  # 2% baseline defect rate for FDM
            'sla': 0.015,
            'sls': 0.018,
            'injection_molding': 0.005,
            'cnc': 0.008,
            'assembly': 0.01
        }

    def predict(self,
                failure_mode: str,
                features: OccurrenceFeatures,
                process_type: str = 'fdm') -> OccurrencePrediction:
        """
        Predict occurrence rating for failure mode.

        Args:
            failure_mode: Failure mode identifier
            features: Occurrence features
            process_type: Manufacturing process type

        Returns:
            Occurrence prediction with rating and recommendations
        """
        # Get baseline probability
        baseline = self._process_baselines.get(process_type, 0.02)

        # Calculate feature contributions
        contributions = {}
        total_adjustment = 0

        feature_dict = {
            'process_capability': features.process_capability,
            'historical_rate': features.historical_rate,
            'complexity_score': features.complexity_score,
            'material_variation': features.material_variation,
            'equipment_age': features.equipment_age,
            'operator_experience': features.operator_experience,
            'environmental_factors': features.environmental_factors,
            'maintenance_status': features.maintenance_status
        }

        for feature_name, value in feature_dict.items():
            weight = self._model_weights.get(feature_name, 0)
            contribution = weight * value
            contributions[feature_name] = contribution
            total_adjustment += contribution

        # Calculate probability
        probability = baseline * (1 + total_adjustment)
        probability = max(0.0001, min(0.99, probability))

        # Convert to FMEA occurrence rating (1-10)
        occurrence_rating = self._probability_to_rating(probability)

        # Calculate confidence
        confidence = self._calculate_confidence(features)

        # Generate recommendations
        recommendations = self._generate_recommendations(
            contributions, features, occurrence_rating
        )

        return OccurrencePrediction(
            failure_mode=failure_mode,
            occurrence_rating=occurrence_rating,
            probability=probability,
            confidence=confidence,
            contributing_factors=contributions,
            recommendations=recommendations
        )

    def _probability_to_rating(self, probability: float) -> int:
        """
        Convert probability to FMEA occurrence rating.

        Standard AIAG FMEA occurrence ratings:
        1: <= 1 in 1,000,000 (virtually impossible)
        2: 1 in 500,000
        3: 1 in 100,000
        4: 1 in 10,000
        5: 1 in 2,000
        6: 1 in 500
        7: 1 in 100
        8: 1 in 50
        9: 1 in 10
        10: >= 1 in 2 (very high)
        """
        thresholds = [
            (0.000001, 1),   # 1 in 1,000,000
            (0.000002, 2),   # 1 in 500,000
            (0.00001, 3),    # 1 in 100,000
            (0.0001, 4),     # 1 in 10,000
            (0.0005, 5),     # 1 in 2,000
            (0.002, 6),      # 1 in 500
            (0.01, 7),       # 1 in 100
            (0.02, 8),       # 1 in 50
            (0.1, 9),        # 1 in 10
            (1.0, 10)        # 1 in 2 or worse
        ]

        for threshold, rating in thresholds:
            if probability <= threshold:
                return rating
        return 10

    def _calculate_confidence(self, features: OccurrenceFeatures) -> float:
        """Calculate prediction confidence."""
        confidence = 0.6  # Base confidence

        # Historical data increases confidence
        if features.historical_rate > 0:
            confidence += 0.15

        # Good process capability data increases confidence
        if 0 < features.process_capability < 5:
            confidence += 0.1

        # Known equipment status increases confidence
        if features.maintenance_status > 0:
            confidence += 0.05

        return min(0.95, confidence)

    def _generate_recommendations(self,
                                  contributions: Dict[str, float],
                                  features: OccurrenceFeatures,
                                  rating: int) -> List[str]:
        """Generate recommendations to reduce occurrence."""
        recommendations = []

        # Sort contributions by absolute impact
        sorted_factors = sorted(
            contributions.items(),
            key=lambda x: abs(x[1]),
            reverse=True
        )

        for factor, contribution in sorted_factors[:3]:
            if contribution > 0:  # This factor increases occurrence
                rec = self._get_factor_recommendation(factor, features)
                if rec:
                    recommendations.append(rec)

        # Add rating-specific recommendations
        if rating >= 8:
            recommendations.append(
                "Critical: Implement additional process controls immediately"
            )
        elif rating >= 6:
            recommendations.append(
                "Consider implementing statistical process control (SPC)"
            )

        return recommendations

    def _get_factor_recommendation(self,
                                   factor: str,
                                   features: OccurrenceFeatures) -> Optional[str]:
        """Get recommendation for specific factor."""
        recommendations = {
            'process_capability': (
                f"Improve process capability (current Cpk: {features.process_capability:.2f}). "
                "Target Cpk >= 1.33"
            ),
            'historical_rate': (
                "Review historical failures and implement corrective actions"
            ),
            'complexity_score': (
                "Simplify design or process to reduce complexity"
            ),
            'material_variation': (
                "Implement tighter material controls and incoming inspection"
            ),
            'equipment_age': (
                "Schedule equipment upgrade or enhanced maintenance"
            ),
            'operator_experience': (
                "Provide additional operator training and work instructions"
            ),
            'environmental_factors': (
                "Improve environmental controls (temperature, humidity)"
            ),
            'maintenance_status': (
                "Improve preventive maintenance schedule"
            )
        }
        return recommendations.get(factor)

    def predict_from_historical(self,
                                failure_mode: str,
                                historical_counts: List[Tuple[datetime, int]],
                                total_units: int) -> OccurrencePrediction:
        """
        Predict occurrence from historical failure counts.

        Args:
            failure_mode: Failure mode identifier
            historical_counts: List of (date, failure_count) tuples
            total_units: Total units produced

        Returns:
            Occurrence prediction
        """
        if not historical_counts:
            # No data - return moderate estimate
            return OccurrencePrediction(
                failure_mode=failure_mode,
                occurrence_rating=5,
                probability=0.001,
                confidence=0.3,
                contributing_factors={'no_data': 1.0},
                recommendations=["Collect historical failure data"]
            )

        # Calculate historical rate
        total_failures = sum(count for _, count in historical_counts)
        historical_rate = total_failures / total_units if total_units > 0 else 0

        # Calculate trend
        if len(historical_counts) >= 3:
            recent = historical_counts[-3:]
            older = historical_counts[:-3] if len(historical_counts) > 3 else historical_counts[:1]
            recent_rate = sum(c for _, c in recent) / 3
            older_rate = sum(c for _, c in older) / len(older)
            trend = recent_rate / (older_rate + 0.0001)
        else:
            trend = 1.0

        # Adjust probability based on trend
        probability = historical_rate * trend
        occurrence_rating = self._probability_to_rating(probability)

        recommendations = []
        if trend > 1.2:
            recommendations.append("Warning: Occurrence rate is increasing")
        elif trend < 0.8:
            recommendations.append("Positive: Occurrence rate is decreasing")

        return OccurrencePrediction(
            failure_mode=failure_mode,
            occurrence_rating=occurrence_rating,
            probability=probability,
            confidence=min(0.9, 0.5 + len(historical_counts) * 0.05),
            contributing_factors={'historical_rate': historical_rate, 'trend': trend},
            recommendations=recommendations
        )

    def update_from_observation(self,
                               failure_mode: str,
                               occurred: bool,
                               features: OccurrenceFeatures) -> None:
        """Update model with new observation."""
        self._historical_data.append({
            'failure_mode': failure_mode,
            'occurred': occurred,
            'features': features,
            'timestamp': datetime.utcnow()
        })

        # Retrain if enough new data
        if len(self._historical_data) % 100 == 0:
            self._retrain_model()

    def _retrain_model(self) -> None:
        """Retrain model with historical data."""
        if len(self._historical_data) < 50:
            return

        # Simple online learning update
        # Calculate feature correlations with occurrence
        for feature_name in self._model_weights.keys():
            feature_values = []
            outcomes = []

            for obs in self._historical_data[-100:]:
                features = obs['features']
                value = getattr(features, feature_name, None)
                if value is not None:
                    feature_values.append(value)
                    outcomes.append(1 if obs['occurred'] else 0)

            if len(feature_values) > 10:
                # Update weight based on correlation
                correlation = np.corrcoef(feature_values, outcomes)[0, 1]
                if not np.isnan(correlation):
                    current_weight = self._model_weights[feature_name]
                    # Blend with observed correlation
                    self._model_weights[feature_name] = (
                        0.9 * current_weight + 0.1 * correlation
                    )

        logger.info("Model retrained with new observations")

    def get_statistics(self) -> Dict[str, Any]:
        """Get predictor statistics."""
        return {
            'observations_count': len(self._historical_data),
            'model_weights': self._model_weights.copy(),
            'process_baselines': self._process_baselines.copy()
        }
