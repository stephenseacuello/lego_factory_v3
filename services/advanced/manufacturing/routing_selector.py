"""
Routing Selector - Optimal Routing Selection

LegoMCP World-Class Manufacturing System v5.0
Phase 9: Alternative Routings & Enhanced BOM

Selects optimal routing based on multiple criteria:
- Cost optimization
- Time optimization
- Quality/risk optimization
- Capacity availability
- Energy efficiency
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, date
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class SelectionCriterion(str, Enum):
    """Criteria for routing selection."""
    COST = "cost"
    TIME = "time"
    QUALITY = "quality"
    ENERGY = "energy"
    CAPACITY = "capacity"
    BALANCED = "balanced"


class SelectionContext(str, Enum):
    """Context for selection decision."""
    NORMAL = "normal"
    RUSH = "rush"
    HIGH_QUALITY = "high_quality"
    LOW_COST = "low_cost"
    GREEN = "green"  # Minimize carbon


@dataclass
class RoutingScore:
    """Scoring result for a routing."""
    routing_id: str
    routing_name: str

    # Individual scores (0-100, higher is better)
    cost_score: float = 50.0
    time_score: float = 50.0
    quality_score: float = 50.0
    energy_score: float = 50.0
    capacity_score: float = 50.0

    # Weighted total
    total_score: float = 50.0
    weighted_score: float = 50.0

    # Raw values
    estimated_cost: float = 0.0
    estimated_time_hours: float = 0.0
    risk_score: float = 0.0
    energy_kwh: float = 0.0
    capacity_utilization: float = 0.0

    # Recommendation
    is_recommended: bool = False
    recommendation_reason: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'routing_id': self.routing_id,
            'routing_name': self.routing_name,
            'cost_score': self.cost_score,
            'time_score': self.time_score,
            'quality_score': self.quality_score,
            'energy_score': self.energy_score,
            'capacity_score': self.capacity_score,
            'total_score': self.total_score,
            'weighted_score': self.weighted_score,
            'estimated_cost': self.estimated_cost,
            'estimated_time_hours': self.estimated_time_hours,
            'risk_score': self.risk_score,
            'is_recommended': self.is_recommended,
            'recommendation_reason': self.recommendation_reason,
        }


@dataclass
class SelectionRequest:
    """Request for routing selection."""
    part_id: str
    quantity: int
    due_date: Optional[date] = None
    context: SelectionContext = SelectionContext.NORMAL
    priority: str = "B"
    quality_level: str = "standard"

    # Custom weights (must sum to 1.0)
    weights: Dict[str, float] = field(default_factory=dict)

    # Constraints
    max_cost: Optional[float] = None
    max_time_hours: Optional[float] = None
    required_work_centers: List[str] = field(default_factory=list)
    excluded_work_centers: List[str] = field(default_factory=list)


@dataclass
class SelectionResult:
    """Result of routing selection."""
    request: SelectionRequest
    selected_routing_id: str
    selected_routing_name: str

    # All scores
    scores: List[RoutingScore] = field(default_factory=list)

    # Selection details
    selection_criteria: str = ""
    selection_reason: str = ""
    confidence: float = 0.0

    # Estimates for selected
    estimated_cost: float = 0.0
    estimated_time_hours: float = 0.0
    expected_completion: Optional[date] = None

    # Alternatives
    alternative_routing_ids: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'selected_routing_id': self.selected_routing_id,
            'selected_routing_name': self.selected_routing_name,
            'scores': [s.to_dict() for s in self.scores],
            'selection_criteria': self.selection_criteria,
            'selection_reason': self.selection_reason,
            'confidence': self.confidence,
            'estimated_cost': self.estimated_cost,
            'estimated_time_hours': self.estimated_time_hours,
            'expected_completion': (
                self.expected_completion.isoformat()
                if self.expected_completion else None
            ),
            'alternative_routing_ids': self.alternative_routing_ids,
        }


class RoutingSelector:
    """
    Routing Selector Service.

    Evaluates and selects optimal routing from alternatives
    based on multiple criteria and constraints.
    """

    # Default weights by context
    CONTEXT_WEIGHTS = {
        SelectionContext.NORMAL: {
            'cost': 0.30,
            'time': 0.25,
            'quality': 0.25,
            'energy': 0.10,
            'capacity': 0.10,
        },
        SelectionContext.RUSH: {
            'cost': 0.15,
            'time': 0.50,
            'quality': 0.20,
            'energy': 0.05,
            'capacity': 0.10,
        },
        SelectionContext.HIGH_QUALITY: {
            'cost': 0.15,
            'time': 0.15,
            'quality': 0.50,
            'energy': 0.10,
            'capacity': 0.10,
        },
        SelectionContext.LOW_COST: {
            'cost': 0.50,
            'time': 0.20,
            'quality': 0.15,
            'energy': 0.10,
            'capacity': 0.05,
        },
        SelectionContext.GREEN: {
            'cost': 0.20,
            'time': 0.15,
            'quality': 0.20,
            'energy': 0.35,
            'capacity': 0.10,
        },
    }

    def __init__(
        self,
        routing_repository: Optional[Any] = None,
        capacity_service: Optional[Any] = None,
        config: Optional[Dict[str, Any]] = None,
    ):
        self.routing_repository = routing_repository
        self.capacity_service = capacity_service
        self.config = config or {}

        # In-memory routing data (would come from repository)
        self._routings: Dict[str, Dict[str, Any]] = {}

    def add_routing(
        self,
        routing_id: str,
        part_id: str,
        name: str,
        cost_per_unit: float,
        time_per_unit_min: float,
        risk_score: float = 0.0,
        energy_kwh: float = 0.0,
        yield_percent: float = 99.0,
        work_centers: List[str] = None,
    ) -> None:
        """Add routing data for selection."""
        self._routings[routing_id] = {
            'routing_id': routing_id,
            'part_id': part_id,
            'name': name,
            'cost_per_unit': cost_per_unit,
            'time_per_unit_min': time_per_unit_min,
            'risk_score': risk_score,
            'energy_kwh': energy_kwh,
            'yield_percent': yield_percent,
            'work_centers': work_centers or [],
        }

    def select_routing(self, request: SelectionRequest) -> SelectionResult:
        """
        Select optimal routing for a request.

        Args:
            request: Selection request with criteria

        Returns:
            SelectionResult with recommended routing
        """
        # Get candidate routings for part
        candidates = self._get_candidates(request.part_id)

        if not candidates:
            logger.warning(f"No routings found for part {request.part_id}")
            return SelectionResult(
                request=request,
                selected_routing_id="",
                selected_routing_name="",
                selection_reason="No routings available",
            )

        # Apply constraints to filter candidates
        candidates = self._apply_constraints(candidates, request)

        if not candidates:
            logger.warning(f"No routings meet constraints for part {request.part_id}")
            return SelectionResult(
                request=request,
                selected_routing_id="",
                selected_routing_name="",
                selection_reason="No routings meet constraints",
            )

        # Score each candidate
        scores = []
        for routing in candidates:
            score = self._score_routing(routing, request)
            scores.append(score)

        # Sort by weighted score
        scores.sort(key=lambda s: s.weighted_score, reverse=True)

        # Select best
        best = scores[0]
        best.is_recommended = True
        best.recommendation_reason = self._generate_reason(best, request)

        result = SelectionResult(
            request=request,
            selected_routing_id=best.routing_id,
            selected_routing_name=best.routing_name,
            scores=scores,
            selection_criteria=request.context.value,
            selection_reason=best.recommendation_reason,
            confidence=min(0.99, best.weighted_score / 100),
            estimated_cost=best.estimated_cost,
            estimated_time_hours=best.estimated_time_hours,
            alternative_routing_ids=[s.routing_id for s in scores[1:3]],
        )

        logger.info(
            f"Selected routing {best.routing_name} for part {request.part_id} "
            f"(score: {best.weighted_score:.1f})"
        )

        return result

    def _get_candidates(self, part_id: str) -> List[Dict[str, Any]]:
        """Get candidate routings for a part."""
        return [
            r for r in self._routings.values()
            if r['part_id'] == part_id
        ]

    def _apply_constraints(
        self,
        candidates: List[Dict[str, Any]],
        request: SelectionRequest
    ) -> List[Dict[str, Any]]:
        """Filter candidates by constraints."""
        filtered = []

        for routing in candidates:
            # Cost constraint
            if request.max_cost:
                est_cost = routing['cost_per_unit'] * request.quantity
                if est_cost > request.max_cost:
                    continue

            # Time constraint
            if request.max_time_hours:
                est_time = (routing['time_per_unit_min'] * request.quantity) / 60
                if est_time > request.max_time_hours:
                    continue

            # Required work centers
            if request.required_work_centers:
                if not any(wc in routing['work_centers'] for wc in request.required_work_centers):
                    continue

            # Excluded work centers
            if request.excluded_work_centers:
                if any(wc in routing['work_centers'] for wc in request.excluded_work_centers):
                    continue

            filtered.append(routing)

        return filtered

    def _score_routing(
        self,
        routing: Dict[str, Any],
        request: SelectionRequest
    ) -> RoutingScore:
        """Score a routing against selection criteria."""
        # Get weights
        if request.weights:
            weights = request.weights
        else:
            weights = self.CONTEXT_WEIGHTS.get(
                request.context,
                self.CONTEXT_WEIGHTS[SelectionContext.NORMAL]
            )

        # Calculate raw values
        est_cost = routing['cost_per_unit'] * request.quantity
        est_time_hours = (routing['time_per_unit_min'] * request.quantity) / 60
        risk_score = routing['risk_score']
        energy = routing['energy_kwh'] * request.quantity

        # Score each dimension (higher is better)
        # Cost: inverse relationship
        cost_score = max(0, 100 - (est_cost / 10))  # Normalize

        # Time: inverse relationship
        time_score = max(0, 100 - (est_time_hours * 5))

        # Quality: inverse of risk
        quality_score = max(0, 100 - risk_score)

        # Energy: inverse relationship
        energy_score = max(0, 100 - (energy * 2))

        # Capacity: would check utilization (simplified)
        capacity_score = 70.0  # Default

        # Calculate weighted score
        total_score = (cost_score + time_score + quality_score + energy_score + capacity_score) / 5

        weighted_score = (
            cost_score * weights.get('cost', 0.2) +
            time_score * weights.get('time', 0.2) +
            quality_score * weights.get('quality', 0.2) +
            energy_score * weights.get('energy', 0.2) +
            capacity_score * weights.get('capacity', 0.2)
        )

        return RoutingScore(
            routing_id=routing['routing_id'],
            routing_name=routing['name'],
            cost_score=cost_score,
            time_score=time_score,
            quality_score=quality_score,
            energy_score=energy_score,
            capacity_score=capacity_score,
            total_score=total_score,
            weighted_score=weighted_score,
            estimated_cost=est_cost,
            estimated_time_hours=est_time_hours,
            risk_score=risk_score,
            energy_kwh=energy,
        )

    def _generate_reason(self, score: RoutingScore, request: SelectionRequest) -> str:
        """Generate recommendation reason."""
        reasons = []

        if request.context == SelectionContext.RUSH:
            reasons.append(f"fastest option at {score.estimated_time_hours:.1f} hours")
        elif request.context == SelectionContext.LOW_COST:
            reasons.append(f"lowest cost at ${score.estimated_cost:.2f}")
        elif request.context == SelectionContext.HIGH_QUALITY:
            reasons.append(f"lowest risk (score: {score.risk_score:.1f})")
        elif request.context == SelectionContext.GREEN:
            reasons.append(f"lowest energy at {score.energy_kwh:.2f} kWh")
        else:
            reasons.append(f"best balanced score ({score.weighted_score:.1f})")

        return "Selected: " + ", ".join(reasons)

    def compare_routings(
        self,
        part_id: str,
        quantity: int
    ) -> Dict[str, Any]:
        """
        Compare all routings for a part.

        Returns comparison table with all metrics.
        """
        candidates = self._get_candidates(part_id)

        comparison = {
            'part_id': part_id,
            'quantity': quantity,
            'routings': [],
        }

        for routing in candidates:
            est_cost = routing['cost_per_unit'] * quantity
            est_time_hours = (routing['time_per_unit_min'] * quantity) / 60
            est_energy = routing['energy_kwh'] * quantity

            comparison['routings'].append({
                'routing_id': routing['routing_id'],
                'name': routing['name'],
                'cost': est_cost,
                'time_hours': est_time_hours,
                'risk_score': routing['risk_score'],
                'energy_kwh': est_energy,
                'yield_percent': routing['yield_percent'],
                'work_centers': routing['work_centers'],
            })

        # Sort by cost default
        comparison['routings'].sort(key=lambda r: r['cost'])

        return comparison

    def get_selection_summary(self) -> Dict[str, Any]:
        """Get summary of routing selections."""
        parts = set(r['part_id'] for r in self._routings.values())

        return {
            'total_routings': len(self._routings),
            'parts_covered': len(parts),
            'contexts_available': [c.value for c in SelectionContext],
        }
