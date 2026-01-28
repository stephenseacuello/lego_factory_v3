"""
Competitive Analysis - Benchmarking against competitors.

LEGO MCP v6.0 World-Class Manufacturing Research Platform
Phase 2: Causal AI, Explainability, FMEA & HOQ
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
from enum import Enum
import numpy as np
import logging

logger = logging.getLogger(__name__)


class CompetitorType(Enum):
    """Types of competitors."""
    DIRECT = "direct"  # Same product category
    INDIRECT = "indirect"  # Alternative solutions
    BENCHMARK = "benchmark"  # Industry leader (may not be direct competitor)


class PerformanceLevel(Enum):
    """Performance level ratings."""
    POOR = 1
    BELOW_AVERAGE = 2
    AVERAGE = 3
    GOOD = 4
    EXCELLENT = 5


@dataclass
class Competitor:
    """Competitor definition."""
    competitor_id: str
    name: str
    competitor_type: CompetitorType
    description: str = ""
    market_share: Optional[float] = None
    strengths: List[str] = field(default_factory=list)
    weaknesses: List[str] = field(default_factory=list)


@dataclass
class CompetitiveRating:
    """Rating for a competitor on a requirement."""
    competitor_id: str
    requirement_id: str
    rating: PerformanceLevel
    measured_value: Optional[float] = None
    notes: str = ""


@dataclass
class CompetitiveGap:
    """Gap between our product and competitor."""
    requirement_id: str
    requirement_name: str
    our_rating: PerformanceLevel
    best_competitor_rating: PerformanceLevel
    best_competitor_id: str
    gap: int  # Positive = we're behind
    priority: str  # 'high', 'medium', 'low'
    recommendation: str


class CompetitiveAnalyzer:
    """
    Competitive benchmarking for QFD.

    Features:
    - Multi-competitor comparison
    - Gap analysis
    - Strategic recommendations
    - Market positioning
    """

    def __init__(self):
        self._competitors: Dict[str, Competitor] = {}
        self._our_ratings: Dict[str, CompetitiveRating] = {}
        self._competitor_ratings: Dict[Tuple[str, str], CompetitiveRating] = {}
        self._customer_reqs: Dict[str, Dict] = {}
        self._technical_reqs: Dict[str, Dict] = {}
        self._load_default_competitors()

    def _load_default_competitors(self) -> None:
        """Load default LEGO-related competitors."""
        self.add_competitor(Competitor(
            competitor_id="COMP-001",
            name="Official LEGO",
            competitor_type=CompetitorType.BENCHMARK,
            description="The original LEGO brick manufacturer",
            market_share=0.70,
            strengths=["Brand recognition", "Quality consistency", "Compatibility"],
            weaknesses=["High price", "Limited customization"]
        ))

        self.add_competitor(Competitor(
            competitor_id="COMP-002",
            name="Generic Clone Brands",
            competitor_type=CompetitorType.DIRECT,
            description="Low-cost LEGO-compatible brick manufacturers",
            market_share=0.15,
            strengths=["Low price", "Wide availability"],
            weaknesses=["Inconsistent quality", "Poor clutch power", "Compatibility issues"]
        ))

        self.add_competitor(Competitor(
            competitor_id="COMP-003",
            name="Premium Alternatives",
            competitor_type=CompetitorType.DIRECT,
            description="High-quality alternative brick systems",
            market_share=0.08,
            strengths=["Innovative designs", "Good quality"],
            weaknesses=["Not LEGO-compatible", "Smaller ecosystem"]
        ))

        self.add_competitor(Competitor(
            competitor_id="COMP-004",
            name="3D Printed Custom",
            competitor_type=CompetitorType.INDIRECT,
            description="Custom 3D printed brick solutions",
            market_share=0.02,
            strengths=["Full customization", "Rapid prototyping"],
            weaknesses=["Lower quality", "Time-consuming", "Expertise required"]
        ))

    def add_competitor(self, competitor: Competitor) -> None:
        """Add competitor to analysis."""
        self._competitors[competitor.competitor_id] = competitor

    def set_customer_requirements(self,
                                  requirements: List[Dict[str, Any]]) -> None:
        """Set customer requirements for analysis."""
        self._customer_reqs = {r['id']: r for r in requirements}

    def set_technical_requirements(self,
                                   requirements: List[Dict[str, Any]]) -> None:
        """Set technical requirements for analysis."""
        self._technical_reqs = {r['id']: r for r in requirements}

    def rate_our_product(self,
                        requirement_id: str,
                        rating: PerformanceLevel,
                        measured_value: Optional[float] = None,
                        notes: str = "") -> None:
        """Rate our own product on a requirement."""
        self._our_ratings[requirement_id] = CompetitiveRating(
            competitor_id="OUR_PRODUCT",
            requirement_id=requirement_id,
            rating=rating,
            measured_value=measured_value,
            notes=notes
        )

    def rate_competitor(self,
                       competitor_id: str,
                       requirement_id: str,
                       rating: PerformanceLevel,
                       measured_value: Optional[float] = None,
                       notes: str = "") -> None:
        """Rate competitor on a requirement."""
        key = (competitor_id, requirement_id)
        self._competitor_ratings[key] = CompetitiveRating(
            competitor_id=competitor_id,
            requirement_id=requirement_id,
            rating=rating,
            measured_value=measured_value,
            notes=notes
        )

    def analyze_gaps(self) -> List[CompetitiveGap]:
        """Analyze competitive gaps."""
        gaps = []

        # Combine all requirements
        all_reqs = {**self._customer_reqs, **self._technical_reqs}

        for req_id, req_data in all_reqs.items():
            our_rating = self._our_ratings.get(req_id)
            if not our_rating:
                continue

            # Find best competitor rating
            best_competitor_id = None
            best_rating = PerformanceLevel.POOR

            for comp_id in self._competitors:
                comp_rating = self._competitor_ratings.get((comp_id, req_id))
                if comp_rating and comp_rating.rating.value > best_rating.value:
                    best_rating = comp_rating.rating
                    best_competitor_id = comp_id

            if best_competitor_id:
                gap_value = best_rating.value - our_rating.rating.value

                if gap_value != 0:
                    priority = 'high' if gap_value >= 2 else ('medium' if gap_value >= 1 else 'low')
                    if gap_value < 0:
                        priority = 'maintain'  # We're ahead

                    gaps.append(CompetitiveGap(
                        requirement_id=req_id,
                        requirement_name=req_data.get('name', req_id),
                        our_rating=our_rating.rating,
                        best_competitor_rating=best_rating,
                        best_competitor_id=best_competitor_id,
                        gap=gap_value,
                        priority=priority,
                        recommendation=self._generate_recommendation(
                            req_id, gap_value, our_rating.rating, best_rating
                        )
                    ))

        # Sort by gap (largest first)
        gaps.sort(key=lambda g: g.gap, reverse=True)
        return gaps

    def _generate_recommendation(self,
                                req_id: str,
                                gap: int,
                                our_rating: PerformanceLevel,
                                best_rating: PerformanceLevel) -> str:
        """Generate recommendation based on gap."""
        if gap <= 0:
            return "Maintain current advantage"
        elif gap == 1:
            return "Minor improvement needed to match competition"
        elif gap == 2:
            return "Significant improvement required - prioritize in development"
        else:
            return "Critical gap - requires immediate attention and investment"

    def get_competitive_matrix(self) -> Dict[str, Any]:
        """Get competitive matrix data for visualization."""
        all_reqs = {**self._customer_reqs, **self._technical_reqs}

        # Column for each competitor plus our product
        columns = [{'id': 'OUR_PRODUCT', 'name': 'Our Product'}]
        columns.extend([
            {'id': comp.competitor_id, 'name': comp.name}
            for comp in self._competitors.values()
        ])

        # Row for each requirement
        rows = []
        for req_id, req_data in all_reqs.items():
            row = {
                'id': req_id,
                'name': req_data.get('name', req_id),
                'importance': req_data.get('importance', 1),
                'ratings': {}
            }

            # Our rating
            our_rating = self._our_ratings.get(req_id)
            row['ratings']['OUR_PRODUCT'] = our_rating.rating.value if our_rating else None

            # Competitor ratings
            for comp_id in self._competitors:
                comp_rating = self._competitor_ratings.get((comp_id, req_id))
                row['ratings'][comp_id] = comp_rating.rating.value if comp_rating else None

            rows.append(row)

        return {
            'columns': columns,
            'rows': rows
        }

    def get_positioning_analysis(self) -> Dict[str, Any]:
        """Analyze market positioning."""
        all_reqs = {**self._customer_reqs, **self._technical_reqs}

        # Calculate average ratings
        scores = {'OUR_PRODUCT': []}
        for comp_id in self._competitors:
            scores[comp_id] = []

        for req_id in all_reqs:
            # Our rating
            our_rating = self._our_ratings.get(req_id)
            if our_rating:
                scores['OUR_PRODUCT'].append(our_rating.rating.value)

            # Competitor ratings
            for comp_id in self._competitors:
                comp_rating = self._competitor_ratings.get((comp_id, req_id))
                if comp_rating:
                    scores[comp_id].append(comp_rating.rating.value)

        # Calculate averages
        averages = {}
        for entity_id, ratings in scores.items():
            if ratings:
                averages[entity_id] = {
                    'average': np.mean(ratings),
                    'min': min(ratings),
                    'max': max(ratings),
                    'count': len(ratings)
                }

        # Determine positioning
        our_avg = averages.get('OUR_PRODUCT', {}).get('average', 0)
        all_avgs = [v['average'] for v in averages.values()]

        if our_avg >= max(all_avgs):
            position = "Market Leader"
        elif our_avg >= np.percentile(all_avgs, 75):
            position = "Strong Competitor"
        elif our_avg >= np.percentile(all_avgs, 50):
            position = "Average Performer"
        else:
            position = "Needs Improvement"

        return {
            'scores': averages,
            'position': position,
            'our_average': our_avg,
            'market_average': np.mean(all_avgs) if all_avgs else 0
        }

    def get_improvement_priorities(self) -> List[Dict[str, Any]]:
        """Get prioritized improvement list."""
        gaps = self.analyze_gaps()
        all_reqs = {**self._customer_reqs, **self._technical_reqs}

        priorities = []
        for gap in gaps:
            if gap.gap > 0:  # Only where we're behind
                req_data = all_reqs.get(gap.requirement_id, {})
                importance = req_data.get('importance', 1)

                # Priority score = gap * importance
                priority_score = gap.gap * importance

                priorities.append({
                    'requirement_id': gap.requirement_id,
                    'requirement_name': gap.requirement_name,
                    'gap': gap.gap,
                    'importance': importance,
                    'priority_score': priority_score,
                    'current_rating': gap.our_rating.name,
                    'target_rating': gap.best_competitor_rating.name,
                    'recommendation': gap.recommendation
                })

        # Sort by priority score
        priorities.sort(key=lambda p: p['priority_score'], reverse=True)
        return priorities

    def generate_strategy_report(self) -> str:
        """Generate strategic analysis report."""
        positioning = self.get_positioning_analysis()
        gaps = self.analyze_gaps()
        priorities = self.get_improvement_priorities()

        lines = ["# Competitive Analysis Report\n"]
        lines.append(f"Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M')}\n")

        # Positioning
        lines.append("## Market Position\n")
        lines.append(f"**Current Position:** {positioning['position']}")
        lines.append(f"**Our Average Score:** {positioning['our_average']:.2f}/5")
        lines.append(f"**Market Average:** {positioning['market_average']:.2f}/5\n")

        # Top competitors
        lines.append("## Competitor Summary\n")
        for comp_id, comp in self._competitors.items():
            score = positioning['scores'].get(comp_id, {}).get('average', 'N/A')
            lines.append(f"- **{comp.name}**: Score {score:.2f if isinstance(score, float) else score}")
            lines.append(f"  - Strengths: {', '.join(comp.strengths[:3])}")
            lines.append(f"  - Weaknesses: {', '.join(comp.weaknesses[:2])}\n")

        # Key gaps
        if gaps:
            lines.append("## Key Competitive Gaps\n")
            for gap in gaps[:5]:
                if gap.gap > 0:
                    lines.append(f"- **{gap.requirement_name}**: {gap.gap} level(s) behind")
                    lines.append(f"  - {gap.recommendation}\n")

        # Strategic priorities
        if priorities:
            lines.append("## Strategic Priorities\n")
            for i, p in enumerate(priorities[:5], 1):
                lines.append(f"{i}. **{p['requirement_name']}** (Priority Score: {p['priority_score']:.1f})")
                lines.append(f"   Current: {p['current_rating']} → Target: {p['target_rating']}\n")

        return "\n".join(lines)

    def export_to_dict(self) -> Dict[str, Any]:
        """Export analysis to dictionary."""
        return {
            'competitors': [
                {
                    'id': c.competitor_id,
                    'name': c.name,
                    'type': c.competitor_type.value,
                    'market_share': c.market_share,
                    'strengths': c.strengths,
                    'weaknesses': c.weaknesses
                }
                for c in self._competitors.values()
            ],
            'our_ratings': {
                r.requirement_id: r.rating.value
                for r in self._our_ratings.values()
            },
            'competitor_ratings': {
                f"{k[0]}_{k[1]}": r.rating.value
                for k, r in self._competitor_ratings.items()
            },
            'gaps': [
                {
                    'requirement': g.requirement_name,
                    'gap': g.gap,
                    'priority': g.priority
                }
                for g in self.analyze_gaps()
            ]
        }
