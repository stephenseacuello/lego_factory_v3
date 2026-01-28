"""
Prediction Explainer for CNC Manufacturing.

Uses Claude AI to explain ML predictions in natural language.
"""

import logging
from dataclasses import dataclass, field
from typing import Optional, Dict, List, Any
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class FeatureContribution:
    """A feature's contribution to a prediction."""
    name: str
    value: Any
    contribution: float  # Positive = increases prediction, negative = decreases
    importance: float  # 0-1, how important this feature is overall
    category: str = ""  # e.g., "cutting_parameters", "sensor_data"

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "value": self.value,
            "contribution": self.contribution,
            "importance": self.importance,
            "category": self.category,
        }


@dataclass
class Explanation:
    """Natural language explanation of a prediction."""
    prediction_type: str  # cycle_time, tool_wear, quality, maintenance
    summary: str
    key_factors: List[str]
    detailed_explanation: str
    recommendations: List[str]

    # Feature analysis
    feature_contributions: List[FeatureContribution] = field(default_factory=list)

    # Confidence assessment
    confidence_explanation: str = ""
    uncertainty_sources: List[str] = field(default_factory=list)

    # Comparisons
    vs_historical: str = ""
    vs_optimal: str = ""

    generated_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "prediction_type": self.prediction_type,
            "summary": self.summary,
            "key_factors": self.key_factors,
            "detailed_explanation": self.detailed_explanation,
            "recommendations": self.recommendations,
            "feature_contributions": [f.to_dict() for f in self.feature_contributions],
            "confidence": {
                "explanation": self.confidence_explanation,
                "uncertainty_sources": self.uncertainty_sources,
            },
            "comparisons": {
                "vs_historical": self.vs_historical,
                "vs_optimal": self.vs_optimal,
            },
            "generated_at": self.generated_at.isoformat(),
        }


class PredictionExplainer:
    """
    Generates natural language explanations for ML predictions.

    Uses Claude AI for generating explanations when available,
    falls back to template-based explanations otherwise.
    """

    def __init__(
        self,
        anthropic_api_key: Optional[str] = None,
    ):
        """
        Initialize prediction explainer.

        Args:
            anthropic_api_key: Anthropic API key for Claude
        """
        self.api_key = anthropic_api_key
        self._client = None

        if anthropic_api_key:
            try:
                import anthropic
                self._client = anthropic.Anthropic(api_key=anthropic_api_key)
            except ImportError:
                logger.warning("anthropic package not installed")

    async def explain_cycle_time(
        self,
        predicted_seconds: float,
        confidence: float,
        features: Dict[str, Any],
        breakdown: Dict[str, float],
        material: str = "aluminum",
        machine_type: str = "mill",
    ) -> Explanation:
        """
        Explain a cycle time prediction.

        Args:
            predicted_seconds: Predicted cycle time
            confidence: Prediction confidence
            features: G-code features used
            breakdown: Time breakdown by operation type
            material: Workpiece material
            machine_type: Type of machine

        Returns:
            Explanation object
        """
        # Calculate feature contributions
        contributions = self._calculate_cycle_time_contributions(features, breakdown)

        # Generate key factors
        key_factors = []
        if breakdown.get("cut_time", 0) > predicted_seconds * 0.5:
            key_factors.append("Cutting operations dominate cycle time")
        if features.get("tool_changes", 0) > 3:
            key_factors.append(f"{features['tool_changes']} tool changes add significant time")
        if features.get("arc_count", 0) > features.get("cut_count", 0) * 0.3:
            key_factors.append("High arc content increases machining complexity")

        # Generate summary
        minutes = predicted_seconds / 60
        summary = f"Estimated cycle time is {minutes:.1f} minutes for {material} on {machine_type}"

        # Try AI explanation if available
        if self._client:
            detailed = await self._generate_ai_explanation(
                "cycle_time",
                {
                    "predicted_seconds": predicted_seconds,
                    "confidence": confidence,
                    "features": features,
                    "breakdown": breakdown,
                    "material": material,
                    "machine_type": machine_type,
                }
            )
        else:
            detailed = self._generate_cycle_time_explanation_template(
                predicted_seconds, features, breakdown, material
            )

        # Generate recommendations
        recommendations = []
        if breakdown.get("rapid_time", 0) > predicted_seconds * 0.2:
            recommendations.append("Consider optimizing rapid moves to reduce air cutting")
        if features.get("tool_changes", 0) > 5:
            recommendations.append("Group operations to minimize tool changes")
        if features.get("avg_feed_rate", 0) < 200:
            recommendations.append("Review feed rates - may be conservative for material")

        # Confidence explanation
        confidence_explanation = self._explain_confidence(confidence, "cycle_time")

        return Explanation(
            prediction_type="cycle_time",
            summary=summary,
            key_factors=key_factors,
            detailed_explanation=detailed,
            recommendations=recommendations,
            feature_contributions=contributions,
            confidence_explanation=confidence_explanation,
            uncertainty_sources=self._identify_uncertainty_sources(features),
        )

    async def explain_tool_wear(
        self,
        wear_percentage: float,
        remaining_life_minutes: float,
        factors: Dict[str, float],
        tool_info: Dict[str, Any],
        material: str = "aluminum",
    ) -> Explanation:
        """
        Explain a tool wear prediction.

        Args:
            wear_percentage: Predicted wear percentage
            remaining_life_minutes: Remaining tool life
            factors: Contributing wear factors
            tool_info: Tool specifications
            material: Material being cut

        Returns:
            Explanation object
        """
        # Determine wear severity
        if wear_percentage < 30:
            severity = "minimal"
            status = "good condition"
        elif wear_percentage < 60:
            severity = "moderate"
            status = "acceptable condition"
        elif wear_percentage < 80:
            severity = "significant"
            status = "should be replaced soon"
        else:
            severity = "high"
            status = "needs immediate replacement"

        # Generate summary
        summary = (
            f"Tool shows {severity} wear ({wear_percentage:.1f}%) and is in {status}. "
            f"Estimated remaining life: {remaining_life_minutes:.0f} minutes"
        )

        # Key factors
        key_factors = []
        if factors.get("time_based", 0) > factors.get("distance_based", 0):
            key_factors.append("Time-based wear is the primary driver")
        else:
            key_factors.append("Distance-based wear is the primary driver")

        if factors.get("sensor_based", 0) > 30:
            key_factors.append("Sensor readings indicate accelerated wear")

        if factors.get("material_adjustment", 0) > 5:
            key_factors.append(f"Cutting {material} increases wear rate significantly")

        # Feature contributions
        contributions = [
            FeatureContribution(
                name="Runtime wear",
                value=f"{factors.get('time_based', 0):.1f}%",
                contribution=factors.get('time_based', 0),
                importance=0.3,
                category="usage",
            ),
            FeatureContribution(
                name="Distance wear",
                value=f"{factors.get('distance_based', 0):.1f}%",
                contribution=factors.get('distance_based', 0),
                importance=0.4,
                category="usage",
            ),
            FeatureContribution(
                name="Sensor-indicated wear",
                value=f"{factors.get('sensor_based', 0):.1f}%",
                contribution=factors.get('sensor_based', 0),
                importance=0.3,
                category="condition",
            ),
        ]

        # Detailed explanation
        if self._client:
            detailed = await self._generate_ai_explanation(
                "tool_wear",
                {
                    "wear_percentage": wear_percentage,
                    "remaining_life": remaining_life_minutes,
                    "factors": factors,
                    "tool_info": tool_info,
                    "material": material,
                }
            )
        else:
            detailed = self._generate_tool_wear_explanation_template(
                wear_percentage, remaining_life_minutes, factors, tool_info, material
            )

        # Recommendations
        recommendations = []
        if wear_percentage > 70:
            recommendations.append("Schedule tool replacement before next production run")
        if factors.get("sensor_based", 0) > 40:
            recommendations.append("Check for chatter or unusual cutting conditions")
        if remaining_life_minutes < 30:
            recommendations.append("Replace tool immediately to avoid part quality issues")

        return Explanation(
            prediction_type="tool_wear",
            summary=summary,
            key_factors=key_factors,
            detailed_explanation=detailed,
            recommendations=recommendations,
            feature_contributions=contributions,
            confidence_explanation=self._explain_confidence(0.85, "tool_wear"),
        )

    async def explain_quality(
        self,
        quality_score: float,
        defect_probability: float,
        risk_factors: Dict[str, float],
        process_params: Dict[str, Any],
    ) -> Explanation:
        """
        Explain a quality prediction.

        Args:
            quality_score: Predicted quality score (0-100)
            defect_probability: Probability of defect
            risk_factors: Risk scores by category
            process_params: Current process parameters

        Returns:
            Explanation object
        """
        # Generate summary
        if defect_probability < 0.1:
            risk_level = "low risk"
        elif defect_probability < 0.3:
            risk_level = "moderate risk"
        else:
            risk_level = "high risk"

        summary = (
            f"Quality prediction: {quality_score:.0f}/100 with {risk_level} of defects "
            f"({defect_probability*100:.1f}% probability)"
        )

        # Key factors
        key_factors = []
        if risk_factors.get("chatter", 0) > 0.3:
            key_factors.append("Chatter risk may affect surface finish")
        if risk_factors.get("thermal_distortion", 0) > 0.3:
            key_factors.append("Thermal effects may impact dimensional accuracy")
        if risk_factors.get("tool_deflection", 0) > 0.3:
            key_factors.append("Tool deflection risk for accuracy")
        if risk_factors.get("surface_roughness", 0) > 0.3:
            key_factors.append("Surface finish may exceed specification")

        # Feature contributions
        contributions = [
            FeatureContribution(
                name="Chatter risk",
                value=f"{risk_factors.get('chatter', 0)*100:.0f}%",
                contribution=-risk_factors.get('chatter', 0) * 30,
                importance=0.25,
                category="vibration",
            ),
            FeatureContribution(
                name="Thermal risk",
                value=f"{risk_factors.get('thermal_distortion', 0)*100:.0f}%",
                contribution=-risk_factors.get('thermal_distortion', 0) * 20,
                importance=0.2,
                category="thermal",
            ),
            FeatureContribution(
                name="Deflection risk",
                value=f"{risk_factors.get('tool_deflection', 0)*100:.0f}%",
                contribution=-risk_factors.get('tool_deflection', 0) * 25,
                importance=0.25,
                category="mechanical",
            ),
        ]

        # Detailed explanation
        if self._client:
            detailed = await self._generate_ai_explanation(
                "quality",
                {
                    "quality_score": quality_score,
                    "defect_probability": defect_probability,
                    "risk_factors": risk_factors,
                    "process_params": process_params,
                }
            )
        else:
            detailed = self._generate_quality_explanation_template(
                quality_score, defect_probability, risk_factors
            )

        # Recommendations based on risks
        recommendations = []
        if risk_factors.get("chatter", 0) > 0.3:
            recommendations.append("Reduce spindle speed or adjust depth of cut to minimize chatter")
        if risk_factors.get("thermal_distortion", 0) > 0.3:
            recommendations.append("Increase coolant flow or reduce cutting speed")
        if risk_factors.get("tool_deflection", 0) > 0.3:
            recommendations.append("Use shorter tool or reduce cutting depth")

        return Explanation(
            prediction_type="quality",
            summary=summary,
            key_factors=key_factors,
            detailed_explanation=detailed,
            recommendations=recommendations,
            feature_contributions=contributions,
            confidence_explanation=self._explain_confidence(0.8, "quality"),
        )

    async def explain_maintenance(
        self,
        health_score: float,
        failure_risk: float,
        days_until_maintenance: float,
        component_health: Dict[str, float],
        anomalies: List[str],
    ) -> Explanation:
        """
        Explain a maintenance prediction.

        Args:
            health_score: Overall machine health (0-100)
            failure_risk: Probability of failure
            days_until_maintenance: Days until next maintenance needed
            component_health: Health scores by component
            anomalies: Detected anomalies

        Returns:
            Explanation object
        """
        # Generate summary
        if failure_risk < 0.1:
            risk_status = "low failure risk"
        elif failure_risk < 0.3:
            risk_status = "moderate failure risk"
        else:
            risk_status = "elevated failure risk"

        summary = (
            f"Machine health: {health_score:.0f}/100 with {risk_status}. "
            f"Next maintenance recommended in {days_until_maintenance:.0f} days"
        )

        # Key factors
        key_factors = []
        weakest_component = min(component_health.items(), key=lambda x: x[1])
        key_factors.append(f"{weakest_component[0]} is weakest component at {weakest_component[1]:.0f}% health")

        if anomalies:
            key_factors.append(f"{len(anomalies)} anomaly(ies) detected requiring attention")

        if failure_risk > 0.3:
            key_factors.append("Elevated failure risk based on sensor trends")

        # Feature contributions
        contributions = [
            FeatureContribution(
                name=component,
                value=f"{health:.0f}%",
                contribution=health - 100,  # Negative if below 100
                importance=0.2,
                category="component_health",
            )
            for component, health in component_health.items()
        ]

        # Detailed explanation
        if self._client:
            detailed = await self._generate_ai_explanation(
                "maintenance",
                {
                    "health_score": health_score,
                    "failure_risk": failure_risk,
                    "days_until_maintenance": days_until_maintenance,
                    "component_health": component_health,
                    "anomalies": anomalies,
                }
            )
        else:
            detailed = self._generate_maintenance_explanation_template(
                health_score, failure_risk, component_health, anomalies
            )

        # Recommendations
        recommendations = []
        if weakest_component[1] < 70:
            recommendations.append(f"Prioritize {weakest_component[0]} inspection")
        for anomaly in anomalies[:3]:  # Top 3 anomalies
            recommendations.append(f"Investigate: {anomaly}")
        if failure_risk > 0.3:
            recommendations.append("Schedule preventive maintenance within 7 days")

        return Explanation(
            prediction_type="maintenance",
            summary=summary,
            key_factors=key_factors,
            detailed_explanation=detailed,
            recommendations=recommendations,
            feature_contributions=contributions,
            confidence_explanation=self._explain_confidence(0.85, "maintenance"),
        )

    async def _generate_ai_explanation(
        self,
        prediction_type: str,
        context: Dict[str, Any],
    ) -> str:
        """Generate explanation using Claude AI."""
        if not self._client:
            return ""

        try:
            prompt = f"""You are an expert manufacturing engineer explaining a {prediction_type} prediction to a CNC operator.

Context:
{context}

Provide a clear, concise explanation (2-3 paragraphs) that:
1. Explains what the prediction means in practical terms
2. Identifies the main factors driving the prediction
3. Suggests what the operator should pay attention to

Use shop floor language and avoid overly technical jargon."""

            response = self._client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=500,
                messages=[{"role": "user", "content": prompt}],
            )

            return response.content[0].text

        except Exception as e:
            logger.error(f"AI explanation failed: {e}")
            return ""

    def _calculate_cycle_time_contributions(
        self,
        features: Dict[str, Any],
        breakdown: Dict[str, float],
    ) -> List[FeatureContribution]:
        """Calculate feature contributions for cycle time."""
        total = sum(breakdown.values())
        if total == 0:
            return []

        contributions = []

        if "cut_time" in breakdown:
            contributions.append(FeatureContribution(
                name="Cutting time",
                value=f"{breakdown['cut_time']:.0f}s",
                contribution=breakdown['cut_time'] / total * 100,
                importance=0.4,
                category="cutting",
            ))

        if "rapid_time" in breakdown:
            contributions.append(FeatureContribution(
                name="Rapid moves",
                value=f"{breakdown['rapid_time']:.0f}s",
                contribution=breakdown['rapid_time'] / total * 100,
                importance=0.2,
                category="motion",
            ))

        if "tool_change_time" in breakdown:
            contributions.append(FeatureContribution(
                name="Tool changes",
                value=f"{breakdown['tool_change_time']:.0f}s",
                contribution=breakdown['tool_change_time'] / total * 100,
                importance=0.15,
                category="setup",
            ))

        return contributions

    def _explain_confidence(self, confidence: float, prediction_type: str) -> str:
        """Explain confidence level."""
        if confidence > 0.9:
            return f"High confidence prediction based on complete data and validated model"
        elif confidence > 0.8:
            return f"Good confidence - prediction based on adequate historical data"
        elif confidence > 0.7:
            return f"Moderate confidence - some uncertainty due to limited sensor data"
        else:
            return f"Lower confidence - recommend validating with additional measurements"

    def _identify_uncertainty_sources(self, features: Dict[str, Any]) -> List[str]:
        """Identify sources of uncertainty in prediction."""
        sources = []

        if features.get("avg_feed_rate", 0) == 0:
            sources.append("Missing feed rate data")
        if features.get("tool_changes", 0) == 0 and features.get("move_count", 0) > 100:
            sources.append("Tool change count may be underestimated")

        return sources

    def _generate_cycle_time_explanation_template(
        self,
        predicted_seconds: float,
        features: Dict[str, Any],
        breakdown: Dict[str, float],
        material: str,
    ) -> str:
        """Generate template-based cycle time explanation."""
        minutes = predicted_seconds / 60

        explanation = f"The predicted cycle time of {minutes:.1f} minutes is based on "
        explanation += f"analysis of the G-code which contains {features.get('move_count', 0)} moves "
        explanation += f"covering {features.get('cut_distance', 0):.0f}mm of cutting distance. "

        if breakdown.get('cut_time', 0) > predicted_seconds * 0.6:
            explanation += "The majority of time is spent in cutting operations, "
            explanation += "which is typical for material removal-intensive operations. "
        else:
            explanation += "A significant portion of time is spent in non-cutting moves, "
            explanation += "which may indicate opportunities for optimization. "

        explanation += f"Cutting {material} affects the cycle time through its machinability characteristics."

        return explanation

    def _generate_tool_wear_explanation_template(
        self,
        wear_percentage: float,
        remaining_life: float,
        factors: Dict[str, float],
        tool_info: Dict[str, Any],
        material: str,
    ) -> str:
        """Generate template-based tool wear explanation."""
        explanation = f"The tool shows {wear_percentage:.1f}% wear, "

        if factors.get('time_based', 0) > factors.get('distance_based', 0):
            explanation += "primarily driven by runtime duration. "
        else:
            explanation += "primarily driven by cutting distance traveled. "

        if factors.get('sensor_based', 0) > 20:
            explanation += "Sensor readings indicate additional wear beyond normal usage patterns. "

        explanation += f"Cutting {material} "
        if material.lower() in ['steel', 'stainless', 'titanium']:
            explanation += "accelerates wear compared to softer materials. "
        else:
            explanation += "has moderate impact on wear rate. "

        explanation += f"Based on current trends, the tool should last approximately "
        explanation += f"{remaining_life:.0f} more minutes of cutting."

        return explanation

    def _generate_quality_explanation_template(
        self,
        quality_score: float,
        defect_probability: float,
        risk_factors: Dict[str, float],
    ) -> str:
        """Generate template-based quality explanation."""
        explanation = f"The quality prediction of {quality_score:.0f}/100 "
        explanation += f"indicates a {defect_probability*100:.0f}% probability of producing a defective part. "

        highest_risk = max(risk_factors.items(), key=lambda x: x[1])
        explanation += f"The primary quality risk is {highest_risk[0].replace('_', ' ')}, "
        explanation += f"which contributes significantly to the overall risk assessment. "

        if defect_probability < 0.1:
            explanation += "Overall, conditions are favorable for producing good quality parts."
        elif defect_probability < 0.3:
            explanation += "Some adjustment to process parameters may improve quality consistency."
        else:
            explanation += "Process parameters should be reviewed before production to reduce defect risk."

        return explanation

    def _generate_maintenance_explanation_template(
        self,
        health_score: float,
        failure_risk: float,
        component_health: Dict[str, float],
        anomalies: List[str],
    ) -> str:
        """Generate template-based maintenance explanation."""
        explanation = f"The machine's overall health score of {health_score:.0f}/100 "

        if health_score > 80:
            explanation += "indicates good operating condition. "
        elif health_score > 60:
            explanation += "suggests some maintenance attention is needed. "
        else:
            explanation += "indicates significant maintenance is required. "

        if component_health:
            weakest = min(component_health.items(), key=lambda x: x[1])
            explanation += f"The {weakest[0]} component shows the most wear at {weakest[1]:.0f}% health. "

        if anomalies:
            explanation += f"We detected {len(anomalies)} anomalies that warrant investigation, "
            explanation += f"including: {anomalies[0]}. "

        explanation += f"The failure risk of {failure_risk*100:.0f}% is based on sensor trends "
        explanation += "and historical maintenance patterns."

        return explanation
