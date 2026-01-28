"""
Scenario Manager Service
========================

Manages what-if scenarios for co-simulation:
- Scenario creation and storage
- Parameter variation
- Scenario comparison
- Result analysis

Author: LEGO MCP Engineering Team
Version: 8.0.0
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple
import uuid
import json

logger = logging.getLogger(__name__)


class ScenarioType(Enum):
    """Types of scenarios"""
    WHAT_IF = "what_if"                      # Single parameter change
    SENSITIVITY = "sensitivity"              # Parameter sweep
    MONTE_CARLO = "monte_carlo"              # Stochastic analysis
    OPTIMIZATION = "optimization"            # Find optimal params
    STRESS_TEST = "stress_test"              # Edge case testing
    COMPARISON = "comparison"                # A/B comparison


class ScenarioStatus(Enum):
    """Scenario lifecycle status"""
    DRAFT = "draft"
    READY = "ready"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    ARCHIVED = "archived"


@dataclass
class ParameterVariation:
    """Definition of a parameter variation"""
    name: str
    base_value: float
    variations: List[float]  # Absolute values or percentages
    is_percentage: bool = False
    description: str = ""

    def get_absolute_values(self) -> List[float]:
        """Get absolute values for all variations"""
        if self.is_percentage:
            return [self.base_value * (1 + v/100) for v in self.variations]
        return self.variations

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "base_value": self.base_value,
            "variations": self.variations,
            "is_percentage": self.is_percentage,
            "description": self.description,
            "absolute_values": self.get_absolute_values()
        }


@dataclass
class Scenario:
    """Scenario definition"""
    id: str
    name: str
    description: str
    scenario_type: ScenarioType
    status: ScenarioStatus
    created_at: datetime
    updated_at: datetime
    created_by: str
    base_parameters: Dict[str, Any]
    variations: List[ParameterVariation]
    constraints: Dict[str, Any]
    simulation_config: Dict[str, Any]
    results: Optional[Dict[str, Any]] = None
    completed_at: Optional[datetime] = None
    tags: List[str] = field(default_factory=list)
    parent_scenario_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "scenario_type": self.scenario_type.value,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "created_by": self.created_by,
            "base_parameters": self.base_parameters,
            "variations": [v.to_dict() for v in self.variations],
            "constraints": self.constraints,
            "simulation_config": self.simulation_config,
            "results": self.results,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "tags": self.tags,
            "parent_scenario_id": self.parent_scenario_id
        }


@dataclass
class ScenarioComparison:
    """Comparison between scenarios"""
    id: str
    name: str
    scenario_ids: List[str]
    created_at: datetime
    metrics_compared: List[str]
    comparison_results: Dict[str, Any]
    winner: Optional[str] = None
    analysis: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "scenario_ids": self.scenario_ids,
            "created_at": self.created_at.isoformat(),
            "metrics_compared": self.metrics_compared,
            "comparison_results": self.comparison_results,
            "winner": self.winner,
            "analysis": self.analysis
        }


class ScenarioManager:
    """
    Manages simulation scenarios and their results.

    Provides scenario creation, execution, and comparison capabilities.
    """

    # Default scenario templates
    TEMPLATES = {
        "throughput_optimization": {
            "name": "Throughput Optimization",
            "description": "Optimize production throughput",
            "type": ScenarioType.OPTIMIZATION,
            "variations": [
                {"name": "batch_size", "base": 10, "range": [5, 10, 15, 20, 25]},
                {"name": "cycle_time", "base": 30, "range": [-20, -10, 0, 10, 20], "percentage": True}
            ]
        },
        "capacity_stress_test": {
            "name": "Capacity Stress Test",
            "description": "Test system under high load",
            "type": ScenarioType.STRESS_TEST,
            "variations": [
                {"name": "demand_multiplier", "base": 1.0, "range": [1.5, 2.0, 2.5, 3.0]}
            ]
        },
        "quality_sensitivity": {
            "name": "Quality Sensitivity Analysis",
            "description": "Analyze impact of quality parameters",
            "type": ScenarioType.SENSITIVITY,
            "variations": [
                {"name": "inspection_rate", "base": 0.1, "range": [0.05, 0.1, 0.15, 0.2, 0.25]},
                {"name": "rework_capacity", "base": 5, "range": [3, 5, 7, 10]}
            ]
        },
        "maintenance_impact": {
            "name": "Maintenance Impact Analysis",
            "description": "Analyze preventive maintenance impact",
            "type": ScenarioType.WHAT_IF,
            "variations": [
                {"name": "pm_frequency_hours", "base": 168, "range": [84, 168, 336, 504]},
                {"name": "pm_duration_hours", "base": 2, "range": [1, 2, 4]}
            ]
        }
    }

    def __init__(self):
        """Initialize scenario manager"""
        self._scenarios: Dict[str, Scenario] = {}
        self._comparisons: Dict[str, ScenarioComparison] = {}

    def create_scenario(
        self,
        name: str,
        description: str,
        scenario_type: ScenarioType,
        base_parameters: Dict[str, Any],
        variations: List[Dict[str, Any]],
        created_by: str = "system",
        constraints: Dict[str, Any] = None,
        simulation_config: Dict[str, Any] = None,
        tags: List[str] = None,
        parent_scenario_id: str = None
    ) -> Scenario:
        """
        Create a new scenario.

        Args:
            name: Scenario name
            description: Scenario description
            scenario_type: Type of scenario
            base_parameters: Base parameter values
            variations: Parameter variations to test
            created_by: User creating the scenario
            constraints: Constraints to apply
            simulation_config: Simulation configuration
            tags: Scenario tags
            parent_scenario_id: Parent scenario if derived

        Returns:
            Created Scenario object
        """
        # Parse variations
        parsed_variations = []
        for var in variations:
            parsed_variations.append(ParameterVariation(
                name=var["name"],
                base_value=var.get("base", var.get("base_value", 0)),
                variations=var.get("range", var.get("variations", [])),
                is_percentage=var.get("percentage", var.get("is_percentage", False)),
                description=var.get("description", "")
            ))

        now = datetime.now()
        scenario = Scenario(
            id=str(uuid.uuid4()),
            name=name,
            description=description,
            scenario_type=scenario_type,
            status=ScenarioStatus.DRAFT,
            created_at=now,
            updated_at=now,
            created_by=created_by,
            base_parameters=base_parameters,
            variations=parsed_variations,
            constraints=constraints or {},
            simulation_config=simulation_config or {},
            tags=tags or [],
            parent_scenario_id=parent_scenario_id
        )

        self._scenarios[scenario.id] = scenario
        logger.info(f"Scenario created: {scenario.id} - {name}")

        return scenario

    def create_from_template(
        self,
        template_name: str,
        base_parameters: Dict[str, Any],
        created_by: str = "system",
        customizations: Dict[str, Any] = None
    ) -> Scenario:
        """
        Create scenario from a template.

        Args:
            template_name: Name of the template
            base_parameters: Base parameter values
            created_by: User creating the scenario
            customizations: Override template values

        Returns:
            Created Scenario object
        """
        template = self.TEMPLATES.get(template_name)
        if not template:
            raise ValueError(f"Unknown template: {template_name}")

        # Merge customizations
        name = customizations.get("name", template["name"]) if customizations else template["name"]
        description = customizations.get("description", template["description"]) if customizations else template["description"]
        variations = customizations.get("variations", template["variations"]) if customizations else template["variations"]

        return self.create_scenario(
            name=name,
            description=description,
            scenario_type=template["type"],
            base_parameters=base_parameters,
            variations=variations,
            created_by=created_by
        )

    def update_scenario(
        self,
        scenario_id: str,
        updates: Dict[str, Any]
    ) -> Optional[Scenario]:
        """
        Update a scenario.

        Args:
            scenario_id: Scenario ID
            updates: Fields to update

        Returns:
            Updated Scenario or None
        """
        scenario = self._scenarios.get(scenario_id)
        if not scenario:
            return None

        if scenario.status not in [ScenarioStatus.DRAFT, ScenarioStatus.READY]:
            logger.warning(f"Cannot update scenario in status: {scenario.status}")
            return None

        for key, value in updates.items():
            if hasattr(scenario, key):
                setattr(scenario, key, value)

        scenario.updated_at = datetime.now()
        return scenario

    def mark_ready(self, scenario_id: str) -> Optional[Scenario]:
        """Mark scenario as ready for execution"""
        scenario = self._scenarios.get(scenario_id)
        if scenario and scenario.status == ScenarioStatus.DRAFT:
            scenario.status = ScenarioStatus.READY
            scenario.updated_at = datetime.now()
            return scenario
        return None

    def start_scenario(self, scenario_id: str) -> Optional[Scenario]:
        """Mark scenario as running"""
        scenario = self._scenarios.get(scenario_id)
        if scenario and scenario.status == ScenarioStatus.READY:
            scenario.status = ScenarioStatus.RUNNING
            scenario.updated_at = datetime.now()
            return scenario
        return None

    def complete_scenario(
        self,
        scenario_id: str,
        results: Dict[str, Any],
        success: bool = True
    ) -> Optional[Scenario]:
        """
        Complete a scenario with results.

        Args:
            scenario_id: Scenario ID
            results: Simulation results
            success: Whether simulation succeeded

        Returns:
            Updated Scenario or None
        """
        scenario = self._scenarios.get(scenario_id)
        if not scenario:
            return None

        scenario.results = results
        scenario.status = ScenarioStatus.COMPLETED if success else ScenarioStatus.FAILED
        scenario.completed_at = datetime.now()
        scenario.updated_at = datetime.now()

        return scenario

    def get_scenario(self, scenario_id: str) -> Optional[Scenario]:
        """Get scenario by ID"""
        return self._scenarios.get(scenario_id)

    def list_scenarios(
        self,
        status: ScenarioStatus = None,
        scenario_type: ScenarioType = None,
        tags: List[str] = None,
        created_by: str = None,
        limit: int = 100
    ) -> List[Scenario]:
        """
        List scenarios with optional filtering.

        Args:
            status: Filter by status
            scenario_type: Filter by type
            tags: Filter by tags (any match)
            created_by: Filter by creator
            limit: Maximum results

        Returns:
            List of matching scenarios
        """
        scenarios = list(self._scenarios.values())

        if status:
            scenarios = [s for s in scenarios if s.status == status]
        if scenario_type:
            scenarios = [s for s in scenarios if s.scenario_type == scenario_type]
        if tags:
            scenarios = [s for s in scenarios if any(t in s.tags for t in tags)]
        if created_by:
            scenarios = [s for s in scenarios if s.created_by == created_by]

        # Sort by creation time, newest first
        scenarios.sort(key=lambda s: s.created_at, reverse=True)

        return scenarios[:limit]

    def compare_scenarios(
        self,
        scenario_ids: List[str],
        metrics: List[str],
        name: str = "Scenario Comparison"
    ) -> ScenarioComparison:
        """
        Compare multiple scenarios.

        Args:
            scenario_ids: IDs of scenarios to compare
            metrics: Metrics to compare
            name: Comparison name

        Returns:
            ScenarioComparison object
        """
        scenarios = [
            self._scenarios.get(sid)
            for sid in scenario_ids
            if sid in self._scenarios
        ]

        if len(scenarios) < 2:
            raise ValueError("Need at least 2 scenarios to compare")

        # Build comparison results
        comparison_results = {}
        for metric in metrics:
            metric_values = {}
            for scenario in scenarios:
                if scenario.results:
                    value = self._extract_metric(scenario.results, metric)
                    metric_values[scenario.id] = {
                        "name": scenario.name,
                        "value": value
                    }
            comparison_results[metric] = metric_values

        # Determine winner (highest overall score)
        scores = {}
        for scenario in scenarios:
            if scenario.results:
                scores[scenario.id] = self._calculate_scenario_score(
                    scenario.results, metrics
                )

        winner = max(scores.keys(), key=lambda k: scores[k]) if scores else None

        # Generate analysis
        analysis = self._generate_comparison_analysis(
            scenarios, comparison_results, winner
        )

        comparison = ScenarioComparison(
            id=str(uuid.uuid4()),
            name=name,
            scenario_ids=scenario_ids,
            created_at=datetime.now(),
            metrics_compared=metrics,
            comparison_results=comparison_results,
            winner=winner,
            analysis=analysis
        )

        self._comparisons[comparison.id] = comparison
        return comparison

    def _extract_metric(self, results: Dict[str, Any], metric: str) -> Optional[float]:
        """Extract a metric value from results"""
        # Handle nested metrics with dot notation
        parts = metric.split(".")
        value = results

        for part in parts:
            if isinstance(value, dict):
                value = value.get(part)
            else:
                return None

        return value if isinstance(value, (int, float)) else None

    def _calculate_scenario_score(
        self,
        results: Dict[str, Any],
        metrics: List[str]
    ) -> float:
        """Calculate overall scenario score"""
        scores = []
        for metric in metrics:
            value = self._extract_metric(results, metric)
            if value is not None:
                scores.append(value)

        return sum(scores) / len(scores) if scores else 0.0

    def _generate_comparison_analysis(
        self,
        scenarios: List[Scenario],
        comparison_results: Dict[str, Any],
        winner: Optional[str]
    ) -> str:
        """Generate textual analysis of comparison"""
        lines = ["## Scenario Comparison Analysis\n"]

        # Winner summary
        if winner:
            winner_scenario = next(
                (s for s in scenarios if s.id == winner), None
            )
            if winner_scenario:
                lines.append(f"**Best Performing Scenario:** {winner_scenario.name}\n")

        # Metric breakdown
        lines.append("\n### Metric Comparison\n")
        for metric, values in comparison_results.items():
            lines.append(f"\n**{metric}:**")
            for scenario_id, data in values.items():
                value = data.get("value", "N/A")
                name = data.get("name", scenario_id[:8])
                lines.append(f"  - {name}: {value}")

        # Recommendations
        lines.append("\n### Recommendations\n")
        lines.append("- Consider the winning scenario for production deployment")
        lines.append("- Validate results with additional simulations")
        lines.append("- Review parameter sensitivity for fine-tuning")

        return "\n".join(lines)

    def get_comparison(self, comparison_id: str) -> Optional[ScenarioComparison]:
        """Get comparison by ID"""
        return self._comparisons.get(comparison_id)

    def archive_scenario(self, scenario_id: str) -> Optional[Scenario]:
        """Archive a scenario"""
        scenario = self._scenarios.get(scenario_id)
        if scenario:
            scenario.status = ScenarioStatus.ARCHIVED
            scenario.updated_at = datetime.now()
        return scenario

    def delete_scenario(self, scenario_id: str) -> bool:
        """Delete a scenario"""
        if scenario_id in self._scenarios:
            del self._scenarios[scenario_id]
            return True
        return False

    def clone_scenario(
        self,
        scenario_id: str,
        new_name: str,
        created_by: str = "system"
    ) -> Optional[Scenario]:
        """
        Clone an existing scenario.

        Args:
            scenario_id: Source scenario ID
            new_name: Name for the clone
            created_by: User creating the clone

        Returns:
            Cloned Scenario or None
        """
        source = self._scenarios.get(scenario_id)
        if not source:
            return None

        return self.create_scenario(
            name=new_name,
            description=f"Clone of {source.name}",
            scenario_type=source.scenario_type,
            base_parameters=source.base_parameters.copy(),
            variations=[v.to_dict() for v in source.variations],
            created_by=created_by,
            constraints=source.constraints.copy(),
            simulation_config=source.simulation_config.copy(),
            tags=source.tags.copy(),
            parent_scenario_id=scenario_id
        )

    def export_scenario(self, scenario_id: str) -> Optional[str]:
        """Export scenario as JSON"""
        scenario = self._scenarios.get(scenario_id)
        if scenario:
            return json.dumps(scenario.to_dict(), indent=2)
        return None

    def import_scenario(
        self,
        json_data: str,
        created_by: str = "system"
    ) -> Optional[Scenario]:
        """
        Import scenario from JSON.

        Args:
            json_data: JSON string
            created_by: User importing

        Returns:
            Imported Scenario or None
        """
        try:
            data = json.loads(json_data)
            return self.create_scenario(
                name=data["name"],
                description=data["description"],
                scenario_type=ScenarioType(data["scenario_type"]),
                base_parameters=data["base_parameters"],
                variations=data["variations"],
                created_by=created_by,
                constraints=data.get("constraints", {}),
                simulation_config=data.get("simulation_config", {}),
                tags=data.get("tags", [])
            )
        except Exception as e:
            logger.error(f"Failed to import scenario: {e}")
            return None


# Singleton instance
_scenario_manager: Optional[ScenarioManager] = None


def get_scenario_manager() -> ScenarioManager:
    """Get or create the singleton scenario manager instance"""
    global _scenario_manager
    if _scenario_manager is None:
        _scenario_manager = ScenarioManager()
    return _scenario_manager
