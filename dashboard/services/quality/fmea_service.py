"""
FMEA Service - Dynamic Failure Mode and Effects Analysis

LegoMCP World-Class Manufacturing System v5.0
Phase 10: FMEA Engine (Dynamic)

Manages FMEA with dynamic RPN calculation:
- Create and manage FMEA records
- Dynamic RPN with real-time factors
- Automated action triggering
- Risk trend analysis
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


@dataclass
class DynamicFactors:
    """Real-time factors affecting RPN."""
    machine_health: float = 1.0  # 1.0 = normal, >1 = degraded
    operator_skill: float = 1.0  # 1.0 = experienced, >1 = inexperienced
    material_quality: float = 1.0  # 1.0 = normal, >1 = suspect
    spc_trend: float = 1.0  # 1.0 = stable, >1 = trending OOC
    environmental: float = 1.0  # Temperature, humidity effects

    def total_factor(self) -> float:
        """Get combined factor."""
        return (
            self.machine_health *
            self.operator_skill *
            self.material_quality *
            self.spc_trend *
            self.environmental
        )


class FMEAService:
    """
    FMEA Management Service.

    Creates, manages, and analyzes FMEA records with dynamic RPN.
    """

    # RPN thresholds
    RPN_THRESHOLD_HIGH = 100
    RPN_THRESHOLD_CRITICAL = 200
    RPN_THRESHOLD_IMMEDIATE = 300

    # LEGO-specific failure modes
    LEGO_FAILURE_MODES = {
        'stud_undersized': {
            'description': 'Stud diameter below specification',
            'effect': 'Poor clutch, bricks fall apart',
            'cause': 'Under-extrusion, nozzle wear, temperature low',
            'severity': 7,
            'occurrence': 4,
            'detection': 5,
        },
        'stud_oversized': {
            'description': 'Stud diameter above specification',
            'effect': 'Bricks too tight, damage on assembly',
            'cause': 'Over-extrusion, temperature high',
            'severity': 6,
            'occurrence': 3,
            'detection': 5,
        },
        'warping': {
            'description': 'Part warping during cooling',
            'effect': 'Dimensional inaccuracy, poor fit',
            'cause': 'Uneven cooling, bed adhesion issues',
            'severity': 6,
            'occurrence': 5,
            'detection': 3,
        },
        'layer_adhesion': {
            'description': 'Poor layer adhesion (delamination)',
            'effect': 'Structural weakness, part failure',
            'cause': 'Temperature too low, print speed too high',
            'severity': 8,
            'occurrence': 3,
            'detection': 6,
        },
        'stringing': {
            'description': 'Stringing between features',
            'effect': 'Poor surface quality, cosmetic defect',
            'cause': 'Retraction settings, temperature high',
            'severity': 3,
            'occurrence': 6,
            'detection': 2,
        },
        'color_mismatch': {
            'description': 'Color does not match specification',
            'effect': 'Visual inconsistency in sets',
            'cause': 'Wrong filament, contamination, mixing',
            'severity': 5,
            'occurrence': 2,
            'detection': 2,
        },
        'surface_roughness': {
            'description': 'Surface rougher than specification',
            'effect': 'Poor tactile quality, visible layers',
            'cause': 'Layer height, speed, temperature',
            'severity': 4,
            'occurrence': 4,
            'detection': 3,
        },
        'missing_feature': {
            'description': 'Feature not printed or incomplete',
            'effect': 'Part non-functional',
            'cause': 'Print failure, slicer error',
            'severity': 9,
            'occurrence': 2,
            'detection': 4,
        },
    }

    def __init__(
        self,
        fmea_repository: Optional[Any] = None,
        event_bus: Optional[Any] = None,
        config: Optional[Dict[str, Any]] = None,
    ):
        self.repository = fmea_repository
        self.event_bus = event_bus
        self.config = config or {}

        # In-memory storage
        self._fmeas: Dict[str, Dict[str, Any]] = {}
        self._failure_modes: Dict[str, Dict[str, Any]] = {}
        self._actions: Dict[str, Dict[str, Any]] = {}

        # Current dynamic factors by work center
        self._dynamic_factors: Dict[str, DynamicFactors] = {}

    def create_fmea(
        self,
        part_id: str,
        part_name: str,
        fmea_type: str = "process",
    ) -> Dict[str, Any]:
        """Create a new FMEA record."""
        from uuid import uuid4

        fmea_id = str(uuid4())

        fmea = {
            'fmea_id': fmea_id,
            'fmea_type': fmea_type,
            'part_id': part_id,
            'part_name': part_name,
            'revision': '1.0',
            'failure_modes': [],
            'actions': [],
            'highest_rpn': 0,
            'highest_dynamic_rpn': 0.0,
            'status': 'draft',
            'created_at': datetime.utcnow().isoformat(),
            'updated_at': datetime.utcnow().isoformat(),
        }

        self._fmeas[fmea_id] = fmea
        logger.info(f"Created FMEA {fmea_id} for part {part_name}")

        return fmea

    def add_failure_mode(
        self,
        fmea_id: str,
        description: str,
        severity: int,
        occurrence: int,
        detection: int,
        effect: str = "",
        cause: str = "",
        controls: str = "",
        is_safety_critical: bool = False,
    ) -> Optional[Dict[str, Any]]:
        """Add a failure mode to an FMEA."""
        from uuid import uuid4

        fmea = self._fmeas.get(fmea_id)
        if not fmea:
            return None

        fm_id = str(uuid4())
        rpn = severity * occurrence * detection

        fm = {
            'failure_mode_id': fm_id,
            'fmea_id': fmea_id,
            'description': description,
            'severity': severity,
            'occurrence': occurrence,
            'detection': detection,
            'rpn': rpn,
            'dynamic_rpn': float(rpn),
            'machine_health_factor': 1.0,
            'operator_skill_factor': 1.0,
            'material_quality_factor': 1.0,
            'spc_trend_factor': 1.0,
            'potential_effect': effect,
            'potential_cause': cause,
            'current_controls': controls,
            'is_safety_critical': is_safety_critical,
            'status': 'active',
            'created_at': datetime.utcnow().isoformat(),
        }

        fmea['failure_modes'].append(fm)
        self._failure_modes[fm_id] = fm

        # Update FMEA metrics
        self._update_fmea_metrics(fmea_id)

        return fm

    def add_lego_failure_mode(
        self,
        fmea_id: str,
        mode_key: str,
    ) -> Optional[Dict[str, Any]]:
        """Add a predefined LEGO failure mode."""
        if mode_key not in self.LEGO_FAILURE_MODES:
            return None

        template = self.LEGO_FAILURE_MODES[mode_key]

        return self.add_failure_mode(
            fmea_id=fmea_id,
            description=template['description'],
            severity=template['severity'],
            occurrence=template['occurrence'],
            detection=template['detection'],
            effect=template['effect'],
            cause=template['cause'],
        )

    def update_dynamic_factors(
        self,
        work_center_id: str,
        factors: DynamicFactors,
    ) -> None:
        """Update dynamic factors for a work center."""
        self._dynamic_factors[work_center_id] = factors

        # Update all FMEAs that use this work center
        for fmea in self._fmeas.values():
            for fm in fmea['failure_modes']:
                fm['machine_health_factor'] = factors.machine_health
                fm['operator_skill_factor'] = factors.operator_skill
                fm['material_quality_factor'] = factors.material_quality
                fm['spc_trend_factor'] = factors.spc_trend

                # Recalculate dynamic RPN
                fm['dynamic_rpn'] = (
                    fm['rpn'] *
                    factors.total_factor()
                )

            self._update_fmea_metrics(fmea['fmea_id'])

    def _update_fmea_metrics(self, fmea_id: str) -> None:
        """Update FMEA summary metrics."""
        fmea = self._fmeas.get(fmea_id)
        if not fmea:
            return

        failure_modes = fmea['failure_modes']
        if failure_modes:
            fmea['highest_rpn'] = max(fm['rpn'] for fm in failure_modes)
            fmea['highest_dynamic_rpn'] = max(fm['dynamic_rpn'] for fm in failure_modes)
        else:
            fmea['highest_rpn'] = 0
            fmea['highest_dynamic_rpn'] = 0.0

        fmea['updated_at'] = datetime.utcnow().isoformat()

    def add_risk_action(
        self,
        failure_mode_id: str,
        action_type: str,
        description: str,
        trigger_threshold: float = 100.0,
        auto_execute: bool = False,
    ) -> Optional[Dict[str, Any]]:
        """Add a risk action for a failure mode."""
        from uuid import uuid4

        fm = self._failure_modes.get(failure_mode_id)
        if not fm:
            return None

        action_id = str(uuid4())

        action = {
            'action_id': action_id,
            'failure_mode_id': failure_mode_id,
            'action_type': action_type,
            'description': description,
            'trigger_threshold': trigger_threshold,
            'auto_execute': auto_execute,
            'status': 'pending',
            'created_at': datetime.utcnow().isoformat(),
        }

        self._actions[action_id] = action

        # Add to FMEA
        fmea = self._fmeas.get(fm['fmea_id'])
        if fmea:
            fmea['actions'].append(action)

        return action

    def check_triggered_actions(
        self,
        fmea_id: str,
    ) -> List[Dict[str, Any]]:
        """Check which actions should be triggered based on current RPN."""
        fmea = self._fmeas.get(fmea_id)
        if not fmea:
            return []

        triggered = []

        for fm in fmea['failure_modes']:
            for action in fmea['actions']:
                if action['failure_mode_id'] != fm['failure_mode_id']:
                    continue
                if action['status'] != 'pending':
                    continue

                if fm['dynamic_rpn'] >= action['trigger_threshold']:
                    triggered.append({
                        'action': action,
                        'failure_mode': fm,
                        'current_rpn': fm['dynamic_rpn'],
                        'threshold': action['trigger_threshold'],
                    })

                    if action['auto_execute']:
                        action['status'] = 'in_progress'
                        logger.warning(
                            f"Auto-executing action {action['action_id']}: "
                            f"{action['description']}"
                        )

        return triggered

    def get_risk_summary(self, fmea_id: str) -> Dict[str, Any]:
        """Get risk summary for an FMEA."""
        fmea = self._fmeas.get(fmea_id)
        if not fmea:
            return {}

        failure_modes = fmea['failure_modes']

        # Categorize by risk level
        high_risk = [fm for fm in failure_modes if fm['dynamic_rpn'] > self.RPN_THRESHOLD_HIGH]
        critical = [fm for fm in failure_modes if fm['dynamic_rpn'] > self.RPN_THRESHOLD_CRITICAL]
        immediate = [fm for fm in failure_modes if fm['dynamic_rpn'] > self.RPN_THRESHOLD_IMMEDIATE]

        return {
            'fmea_id': fmea_id,
            'total_failure_modes': len(failure_modes),
            'highest_rpn': fmea['highest_rpn'],
            'highest_dynamic_rpn': fmea['highest_dynamic_rpn'],
            'high_risk_count': len(high_risk),
            'critical_count': len(critical),
            'immediate_action_count': len(immediate),
            'open_actions': sum(
                1 for a in fmea['actions']
                if a['status'] in ['pending', 'in_progress']
            ),
            'risk_distribution': {
                'low': sum(1 for fm in failure_modes if fm['dynamic_rpn'] <= 50),
                'medium': sum(1 for fm in failure_modes if 50 < fm['dynamic_rpn'] <= 100),
                'high': sum(1 for fm in failure_modes if 100 < fm['dynamic_rpn'] <= 200),
                'critical': sum(1 for fm in failure_modes if fm['dynamic_rpn'] > 200),
            },
        }

    def get_fmea(self, fmea_id: str) -> Optional[Dict[str, Any]]:
        """Get FMEA by ID."""
        return self._fmeas.get(fmea_id)

    def get_fmeas_by_part(self, part_id: str) -> List[Dict[str, Any]]:
        """Get all FMEAs for a part."""
        return [
            fmea for fmea in self._fmeas.values()
            if fmea['part_id'] == part_id
        ]

    def get_high_risk_parts(self, threshold: float = 100) -> List[Dict[str, Any]]:
        """Get parts with high-risk failure modes."""
        high_risk = []

        for fmea in self._fmeas.values():
            if fmea['highest_dynamic_rpn'] > threshold:
                high_risk.append({
                    'fmea_id': fmea['fmea_id'],
                    'part_id': fmea['part_id'],
                    'part_name': fmea['part_name'],
                    'highest_rpn': fmea['highest_dynamic_rpn'],
                })

        high_risk.sort(key=lambda x: x['highest_rpn'], reverse=True)
        return high_risk

    def analyze_trend(
        self,
        fmea_id: str,
        failure_mode_id: str,
        history_days: int = 30,
    ) -> Dict[str, Any]:
        """Analyze RPN trend for a failure mode."""
        # In practice, would query historical data
        # Simplified implementation returns current state

        fm = self._failure_modes.get(failure_mode_id)
        if not fm:
            return {'status': 'not_found'}

        return {
            'failure_mode_id': failure_mode_id,
            'current_rpn': fm['rpn'],
            'current_dynamic_rpn': fm['dynamic_rpn'],
            'trend': 'stable',  # Would calculate from history
            'trend_direction': 0,  # -1: improving, 0: stable, 1: worsening
            'factors_impact': {
                'machine_health': fm['machine_health_factor'],
                'operator_skill': fm['operator_skill_factor'],
                'material_quality': fm['material_quality_factor'],
                'spc_trend': fm['spc_trend_factor'],
            },
        }

    def create_lego_pfmea(self, part_id: str, part_name: str) -> Dict[str, Any]:
        """Create a complete PFMEA with LEGO-specific failure modes."""
        fmea = self.create_fmea(part_id, part_name, fmea_type='process')

        # Add all LEGO failure modes
        for mode_key in self.LEGO_FAILURE_MODES:
            self.add_lego_failure_mode(fmea['fmea_id'], mode_key)

        # Add standard actions
        for fm in fmea['failure_modes']:
            if fm['rpn'] > 100:
                self.add_risk_action(
                    failure_mode_id=fm['failure_mode_id'],
                    action_type='inspection',
                    description=f"Add inspection for {fm['description']}",
                    trigger_threshold=100,
                )

            if fm['rpn'] > 150:
                self.add_risk_action(
                    failure_mode_id=fm['failure_mode_id'],
                    action_type='process_control',
                    description=f"Add SPC monitoring for {fm['description']}",
                    trigger_threshold=150,
                    auto_execute=True,
                )

        return fmea

    def get_summary(self) -> Dict[str, Any]:
        """Get overall FMEA summary."""
        total = len(self._fmeas)
        total_fms = len(self._failure_modes)
        total_actions = len(self._actions)

        high_risk = sum(
            1 for fmea in self._fmeas.values()
            if fmea['highest_dynamic_rpn'] > self.RPN_THRESHOLD_HIGH
        )

        return {
            'total_fmeas': total,
            'total_failure_modes': total_fms,
            'total_actions': total_actions,
            'high_risk_fmeas': high_risk,
            'thresholds': {
                'high': self.RPN_THRESHOLD_HIGH,
                'critical': self.RPN_THRESHOLD_CRITICAL,
                'immediate': self.RPN_THRESHOLD_IMMEDIATE,
            },
        }
