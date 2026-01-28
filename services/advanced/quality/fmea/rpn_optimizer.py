"""
RPN Optimizer - Risk Priority Number reduction recommendations.

LEGO MCP v6.0 World-Class Manufacturing Research Platform
Phase 2: Causal AI & Explainability Engine

AI-powered recommendations for reducing RPN scores.
"""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple
import logging

from .fmea_engine import FailureMode, FMEAAnalysis

logger = logging.getLogger(__name__)


@dataclass
class RPNReductionAction:
    """Recommended action to reduce RPN."""
    action_id: str
    failure_mode_id: str
    action_type: str  # severity, occurrence, detection
    action_description: str
    expected_reduction: int  # Expected reduction in rating
    implementation_cost: str  # low, medium, high
    implementation_effort: str  # low, medium, high
    effectiveness_score: float  # 0-1
    priority: int  # 1 = highest


class RPNOptimizer:
    """
    Optimize RPN scores through intelligent recommendations.

    Features:
    - Target-based RPN reduction
    - Cost-benefit analysis
    - Prioritized action lists
    - Pareto analysis
    """

    def __init__(self, target_rpn: int = 100):
        self.target_rpn = target_rpn
        self._action_library = self._load_action_library()

    def _load_action_library(self) -> Dict[str, List[Dict]]:
        """Load library of RPN reduction actions."""
        return {
            'severity': [
                {
                    'condition': lambda fm: fm.severity >= 8,
                    'action': "Implement design change to eliminate failure mode",
                    'reduction': 3,
                    'cost': 'high',
                    'effort': 'high',
                    'effectiveness': 0.9
                },
                {
                    'condition': lambda fm: fm.severity >= 6,
                    'action': "Add redundancy or safety margin to design",
                    'reduction': 2,
                    'cost': 'medium',
                    'effort': 'medium',
                    'effectiveness': 0.7
                }
            ],
            'occurrence': [
                {
                    'condition': lambda fm: fm.occurrence >= 7,
                    'action': "Implement statistical process control (SPC)",
                    'reduction': 2,
                    'cost': 'medium',
                    'effort': 'medium',
                    'effectiveness': 0.8
                },
                {
                    'condition': lambda fm: fm.occurrence >= 5,
                    'action': "Add preventive maintenance schedule",
                    'reduction': 2,
                    'cost': 'low',
                    'effort': 'low',
                    'effectiveness': 0.7
                },
                {
                    'condition': lambda fm: fm.occurrence >= 5,
                    'action': "Implement error-proofing (Poka-Yoke)",
                    'reduction': 3,
                    'cost': 'medium',
                    'effort': 'medium',
                    'effectiveness': 0.85
                },
                {
                    'condition': lambda fm: 'calibration' in ' '.join(fm.potential_causes).lower(),
                    'action': "Increase calibration frequency",
                    'reduction': 2,
                    'cost': 'low',
                    'effort': 'low',
                    'effectiveness': 0.75
                }
            ],
            'detection': [
                {
                    'condition': lambda fm: fm.detection >= 7,
                    'action': "Add in-process inspection point",
                    'reduction': 3,
                    'cost': 'medium',
                    'effort': 'low',
                    'effectiveness': 0.85
                },
                {
                    'condition': lambda fm: fm.detection >= 5,
                    'action': "Implement automated vision inspection",
                    'reduction': 4,
                    'cost': 'high',
                    'effort': 'high',
                    'effectiveness': 0.9
                },
                {
                    'condition': lambda fm: fm.detection >= 5,
                    'action': "Add sensor-based monitoring",
                    'reduction': 3,
                    'cost': 'medium',
                    'effort': 'medium',
                    'effectiveness': 0.8
                }
            ]
        }

    def analyze(self, analysis: FMEAAnalysis) -> Dict[str, Any]:
        """
        Analyze FMEA and generate RPN reduction plan.

        Returns comprehensive optimization report.
        """
        high_rpn = analysis.get_high_rpn_items(self.target_rpn)

        if not high_rpn:
            return {
                'status': 'acceptable',
                'message': f'All failure modes below RPN threshold ({self.target_rpn})',
                'actions': []
            }

        # Generate actions for each high RPN item
        all_actions = []
        for fm in high_rpn:
            actions = self.recommend_actions(fm)
            all_actions.extend(actions)

        # Prioritize actions
        prioritized = self._prioritize_actions(all_actions)

        # Calculate potential improvement
        total_rpn = sum(fm.rpn for fm in analysis.failure_modes)
        high_rpn_sum = sum(fm.rpn for fm in high_rpn)
        potential_reduction = sum(a.expected_reduction * 10 for a in prioritized[:5])

        return {
            'status': 'action_required',
            'summary': {
                'total_failure_modes': len(analysis.failure_modes),
                'high_rpn_count': len(high_rpn),
                'total_rpn': total_rpn,
                'high_rpn_sum': high_rpn_sum,
                'potential_reduction': potential_reduction
            },
            'pareto': self._pareto_analysis(analysis),
            'actions': [
                {
                    'action_id': a.action_id,
                    'failure_mode_id': a.failure_mode_id,
                    'type': a.action_type,
                    'description': a.action_description,
                    'expected_reduction': a.expected_reduction,
                    'cost': a.implementation_cost,
                    'effort': a.implementation_effort,
                    'priority': a.priority
                }
                for a in prioritized
            ],
            'quick_wins': [
                a for a in prioritized
                if a.implementation_cost == 'low' and a.implementation_effort == 'low'
            ][:3]
        }

    def recommend_actions(self, fm: FailureMode) -> List[RPNReductionAction]:
        """
        Recommend actions to reduce RPN for a specific failure mode.
        """
        actions = []
        action_count = 0

        # Determine which factor to target
        factors = self._identify_target_factors(fm)

        for factor in factors:
            library = self._action_library.get(factor, [])
            for template in library:
                if template['condition'](fm):
                    action = RPNReductionAction(
                        action_id=f"{fm.failure_id}_A{action_count}",
                        failure_mode_id=fm.failure_id,
                        action_type=factor,
                        action_description=template['action'],
                        expected_reduction=template['reduction'],
                        implementation_cost=template['cost'],
                        implementation_effort=template['effort'],
                        effectiveness_score=template['effectiveness'],
                        priority=0  # Will be set by prioritization
                    )
                    actions.append(action)
                    action_count += 1

        return actions

    def _identify_target_factors(self, fm: FailureMode) -> List[str]:
        """
        Identify which RPN factors to target.

        Returns factors in order of recommended focus.
        """
        factors = []

        # Generally target occurrence first (prevention)
        # Then detection (find before customer)
        # Severity last (often requires design change)

        scores = [
            ('occurrence', fm.occurrence),
            ('detection', fm.detection),
            ('severity', fm.severity)
        ]

        # Sort by score descending, prioritize occurrence ties
        scores.sort(key=lambda x: (-x[1], ['occurrence', 'detection', 'severity'].index(x[0])))

        return [s[0] for s in scores if s[1] >= 4]

    def _prioritize_actions(self, actions: List[RPNReductionAction]) -> List[RPNReductionAction]:
        """Prioritize actions by effectiveness vs cost."""
        for action in actions:
            # Score based on effectiveness, reduction, and inverse of cost
            cost_factor = {'low': 1.0, 'medium': 0.7, 'high': 0.5}
            effort_factor = {'low': 1.0, 'medium': 0.7, 'high': 0.5}

            score = (
                action.effectiveness_score *
                action.expected_reduction *
                cost_factor.get(action.implementation_cost, 0.5) *
                effort_factor.get(action.implementation_effort, 0.5)
            )
            action.priority = int(10 - score * 10)  # 1 = highest priority

        actions.sort(key=lambda a: a.priority)

        # Assign sequential priorities
        for i, action in enumerate(actions):
            action.priority = i + 1

        return actions

    def _pareto_analysis(self, analysis: FMEAAnalysis) -> Dict[str, Any]:
        """
        Perform Pareto analysis on failure modes.

        Identify the 20% of failure modes causing 80% of risk.
        """
        sorted_fms = sorted(analysis.failure_modes, key=lambda x: -x.rpn)
        total_rpn = sum(fm.rpn for fm in sorted_fms)

        if total_rpn == 0:
            return {'vital_few': [], 'trivial_many': []}

        cumulative = 0
        vital_few = []
        trivial_many = []

        for fm in sorted_fms:
            cumulative += fm.rpn
            if cumulative <= total_rpn * 0.8:
                vital_few.append({
                    'failure_id': fm.failure_id,
                    'failure_mode': fm.failure_mode,
                    'rpn': fm.rpn,
                    'cumulative_pct': cumulative / total_rpn * 100
                })
            else:
                trivial_many.append(fm.failure_id)

        return {
            'vital_few': vital_few,
            'vital_few_count': len(vital_few),
            'trivial_many_count': len(trivial_many),
            'focus_message': f"Focus on top {len(vital_few)} failure modes to address 80% of risk"
        }

    def simulate_improvement(self,
                            fm: FailureMode,
                            actions: List[RPNReductionAction]) -> Dict[str, Any]:
        """
        Simulate RPN improvement from implementing actions.
        """
        current_rpn = fm.rpn
        new_severity = fm.severity
        new_occurrence = fm.occurrence
        new_detection = fm.detection

        for action in actions:
            if action.action_type == 'severity':
                new_severity = max(1, new_severity - action.expected_reduction)
            elif action.action_type == 'occurrence':
                new_occurrence = max(1, new_occurrence - action.expected_reduction)
            elif action.action_type == 'detection':
                new_detection = max(1, new_detection - action.expected_reduction)

        new_rpn = new_severity * new_occurrence * new_detection

        return {
            'current_rpn': current_rpn,
            'new_rpn': new_rpn,
            'reduction': current_rpn - new_rpn,
            'reduction_pct': (current_rpn - new_rpn) / current_rpn * 100 if current_rpn > 0 else 0,
            'new_ratings': {
                'S': new_severity,
                'O': new_occurrence,
                'D': new_detection
            },
            'meets_target': new_rpn < self.target_rpn
        }
