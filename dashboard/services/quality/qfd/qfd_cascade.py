"""
QFD Cascade - 4-Phase Quality Function Deployment.

LEGO MCP v6.0 World-Class Manufacturing Research Platform
Phase 2: Causal AI & Explainability Engine

4-Phase QFD Deployment for LEGO Manufacturing:
Phase 1: Product Planning (Customer -> Design)
Phase 2: Part Deployment (Design -> Parts)
Phase 3: Process Planning (Parts -> Process)
Phase 4: Production Planning (Process -> Production)
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
import logging

from .hoq_engine import (
    HouseOfQualityEngine, HouseOfQuality,
    CustomerRequirement, TechnicalRequirement, KanoType
)

logger = logging.getLogger(__name__)


@dataclass
class QFDPhase:
    """Single phase in QFD cascade."""
    phase_number: int
    phase_name: str
    hoq: HouseOfQuality
    inputs: List[str]  # Requirement IDs from previous phase
    outputs: List[str]  # Requirements passed to next phase


@dataclass
class QFDCascadeResult:
    """Complete 4-phase QFD deployment."""
    cascade_id: str
    project_name: str
    phases: List[QFDPhase]
    critical_path: List[str]  # High-priority items through all phases
    summary: Dict[str, Any]


class QFDCascade:
    """
    Execute 4-phase QFD cascade for LEGO manufacturing.

    Phase 1: Product Planning
    - WHATs: Customer requirements
    - HOWs: Design specifications

    Phase 2: Part Deployment
    - WHATs: Design specs (from Phase 1)
    - HOWs: Part characteristics

    Phase 3: Process Planning
    - WHATs: Part characteristics (from Phase 2)
    - HOWs: Process parameters

    Phase 4: Production Planning
    - WHATs: Process parameters (from Phase 3)
    - HOWs: Production requirements
    """

    def __init__(self):
        self.hoq_engine = HouseOfQualityEngine()

    def execute_cascade(self,
                        project_name: str,
                        customer_requirements: List[CustomerRequirement]) -> QFDCascadeResult:
        """
        Execute complete 4-phase QFD cascade.

        Args:
            project_name: Project identifier
            customer_requirements: Initial customer requirements

        Returns:
            QFDCascadeResult with all phases
        """
        import uuid
        cascade_id = str(uuid.uuid4())[:8]

        phases = []

        # Phase 1: Product Planning
        phase1 = self._execute_phase1(customer_requirements)
        phases.append(phase1)

        # Phase 2: Part Deployment
        phase2 = self._execute_phase2(phase1.hoq)
        phases.append(phase2)

        # Phase 3: Process Planning
        phase3 = self._execute_phase3(phase2.hoq)
        phases.append(phase3)

        # Phase 4: Production Planning
        phase4 = self._execute_phase4(phase3.hoq)
        phases.append(phase4)

        # Identify critical path
        critical_path = self._identify_critical_path(phases)

        result = QFDCascadeResult(
            cascade_id=cascade_id,
            project_name=project_name,
            phases=phases,
            critical_path=critical_path,
            summary=self._generate_summary(phases)
        )

        logger.info(f"QFD Cascade complete for {project_name}")
        return result

    def _execute_phase1(self,
                        customer_requirements: List[CustomerRequirement]) -> QFDPhase:
        """Phase 1: Product Planning - Customer to Design."""
        # Define design specifications (HOWs)
        design_specs = [
            TechnicalRequirement(
                req_id="DS_001",
                description="Stud diameter",
                unit="mm",
                target_value=4.8,
                direction="target",
                tolerance=0.02
            ),
            TechnicalRequirement(
                req_id="DS_002",
                description="Stud height",
                unit="mm",
                target_value=1.7,
                direction="target",
                tolerance=0.05
            ),
            TechnicalRequirement(
                req_id="DS_003",
                description="Clutch force",
                unit="N",
                target_value=2.0,
                direction="target",
                tolerance=0.5
            ),
            TechnicalRequirement(
                req_id="DS_004",
                description="Surface roughness Ra",
                unit="um",
                target_value=0.8,
                direction="minimize"
            ),
            TechnicalRequirement(
                req_id="DS_005",
                description="Color accuracy deltaE",
                unit="deltaE",
                target_value=1.0,
                direction="minimize"
            ),
            TechnicalRequirement(
                req_id="DS_006",
                description="Wall thickness",
                unit="mm",
                target_value=1.5,
                direction="target",
                tolerance=0.05
            ),
        ]

        hoq = self.hoq_engine.build_hoq(
            name="Phase 1: Product Planning",
            customer_reqs=customer_requirements,
            technical_reqs=design_specs
        )

        return QFDPhase(
            phase_number=1,
            phase_name="Product Planning",
            hoq=hoq,
            inputs=[cr.req_id for cr in customer_requirements],
            outputs=[tr.req_id for tr in design_specs]
        )

    def _execute_phase2(self, phase1_hoq: HouseOfQuality) -> QFDPhase:
        """Phase 2: Part Deployment - Design to Parts."""
        # Convert Phase 1 HOWs to Phase 2 WHATs
        part_requirements = []
        for tr in phase1_hoq.technical_requirements:
            importance = phase1_hoq.technical_importance.get(tr.req_id, 5)
            part_requirements.append(CustomerRequirement(
                req_id=f"PR_{tr.req_id}",
                description=f"Achieve {tr.description}: {tr.target_value} {tr.unit}",
                importance=importance / 10,  # Normalize
                kano_type=KanoType.ONE_DIMENSIONAL,
                category="design_spec"
            ))

        # Define part characteristics (HOWs)
        part_characteristics = [
            TechnicalRequirement(
                req_id="PC_001",
                description="Stud geometry tolerance",
                unit="mm",
                target_value=0.02,
                direction="minimize"
            ),
            TechnicalRequirement(
                req_id="PC_002",
                description="Material density",
                unit="g/cm3",
                target_value=1.24,
                direction="target"
            ),
            TechnicalRequirement(
                req_id="PC_003",
                description="Layer adhesion strength",
                unit="%",
                target_value=95,
                direction="maximize"
            ),
            TechnicalRequirement(
                req_id="PC_004",
                description="Internal fill percentage",
                unit="%",
                target_value=20,
                direction="target"
            ),
            TechnicalRequirement(
                req_id="PC_005",
                description="Perimeter count",
                unit="walls",
                target_value=3,
                direction="target"
            ),
        ]

        hoq = self.hoq_engine.build_hoq(
            name="Phase 2: Part Deployment",
            customer_reqs=part_requirements,
            technical_reqs=part_characteristics
        )

        return QFDPhase(
            phase_number=2,
            phase_name="Part Deployment",
            hoq=hoq,
            inputs=[pr.req_id for pr in part_requirements],
            outputs=[pc.req_id for pc in part_characteristics]
        )

    def _execute_phase3(self, phase2_hoq: HouseOfQuality) -> QFDPhase:
        """Phase 3: Process Planning - Parts to Process."""
        # Convert Phase 2 HOWs to Phase 3 WHATs
        process_requirements = []
        for tr in phase2_hoq.technical_requirements:
            importance = phase2_hoq.technical_importance.get(tr.req_id, 5)
            process_requirements.append(CustomerRequirement(
                req_id=f"PR_{tr.req_id}",
                description=f"Control {tr.description}",
                importance=importance / 10,
                kano_type=KanoType.ONE_DIMENSIONAL,
                category="part_spec"
            ))

        # Define process parameters (HOWs)
        process_parameters = [
            TechnicalRequirement(
                req_id="PP_001",
                description="Nozzle temperature",
                unit="C",
                target_value=200,
                direction="target",
                tolerance=5
            ),
            TechnicalRequirement(
                req_id="PP_002",
                description="Bed temperature",
                unit="C",
                target_value=60,
                direction="target",
                tolerance=5
            ),
            TechnicalRequirement(
                req_id="PP_003",
                description="Print speed",
                unit="mm/s",
                target_value=50,
                direction="target"
            ),
            TechnicalRequirement(
                req_id="PP_004",
                description="Layer height",
                unit="mm",
                target_value=0.2,
                direction="target"
            ),
            TechnicalRequirement(
                req_id="PP_005",
                description="Extrusion multiplier",
                unit="ratio",
                target_value=1.0,
                direction="target",
                tolerance=0.02
            ),
            TechnicalRequirement(
                req_id="PP_006",
                description="Cooling fan speed",
                unit="%",
                target_value=100,
                direction="target"
            ),
        ]

        hoq = self.hoq_engine.build_hoq(
            name="Phase 3: Process Planning",
            customer_reqs=process_requirements,
            technical_reqs=process_parameters
        )

        return QFDPhase(
            phase_number=3,
            phase_name="Process Planning",
            hoq=hoq,
            inputs=[pr.req_id for pr in process_requirements],
            outputs=[pp.req_id for pp in process_parameters]
        )

    def _execute_phase4(self, phase3_hoq: HouseOfQuality) -> QFDPhase:
        """Phase 4: Production Planning - Process to Production."""
        # Convert Phase 3 HOWs to Phase 4 WHATs
        production_requirements = []
        for tr in phase3_hoq.technical_requirements:
            importance = phase3_hoq.technical_importance.get(tr.req_id, 5)
            production_requirements.append(CustomerRequirement(
                req_id=f"PR_{tr.req_id}",
                description=f"Maintain {tr.description} at {tr.target_value} {tr.unit}",
                importance=importance / 10,
                kano_type=KanoType.ONE_DIMENSIONAL,
                category="process_param"
            ))

        # Define production requirements (HOWs)
        production_specs = [
            TechnicalRequirement(
                req_id="PD_001",
                description="Temperature control accuracy",
                unit="C",
                target_value=1,
                direction="minimize"
            ),
            TechnicalRequirement(
                req_id="PD_002",
                description="Calibration frequency",
                unit="hours",
                target_value=100,
                direction="minimize"
            ),
            TechnicalRequirement(
                req_id="PD_003",
                description="Inspection sampling rate",
                unit="%",
                target_value=10,
                direction="target"
            ),
            TechnicalRequirement(
                req_id="PD_004",
                description="SPC Cpk target",
                unit="ratio",
                target_value=1.33,
                direction="maximize"
            ),
            TechnicalRequirement(
                req_id="PD_005",
                description="Operator training hours",
                unit="hours",
                target_value=40,
                direction="target"
            ),
        ]

        hoq = self.hoq_engine.build_hoq(
            name="Phase 4: Production Planning",
            customer_reqs=production_requirements,
            technical_reqs=production_specs
        )

        return QFDPhase(
            phase_number=4,
            phase_name="Production Planning",
            hoq=hoq,
            inputs=[pr.req_id for pr in production_requirements],
            outputs=[ps.req_id for ps in production_specs]
        )

    def _identify_critical_path(self, phases: List[QFDPhase]) -> List[str]:
        """Identify critical path through all phases."""
        critical_path = []

        for phase in phases:
            # Get top 2 priority items from each phase
            priority_items = phase.hoq.get_priority_technicals(2)
            for item_id, score in priority_items:
                critical_path.append(f"P{phase.phase_number}:{item_id}")

        return critical_path

    def _generate_summary(self, phases: List[QFDPhase]) -> Dict[str, Any]:
        """Generate cascade summary."""
        return {
            'total_phases': len(phases),
            'total_requirements_analyzed': sum(
                len(p.hoq.customer_requirements) for p in phases
            ),
            'total_technical_specs': sum(
                len(p.hoq.technical_requirements) for p in phases
            ),
            'phase_summaries': [
                {
                    'phase': p.phase_number,
                    'name': p.phase_name,
                    'whats': len(p.hoq.customer_requirements),
                    'hows': len(p.hoq.technical_requirements),
                    'top_priority': p.hoq.get_priority_technicals(1)[0] if p.hoq.technical_importance else None
                }
                for p in phases
            ]
        }

    def export_cascade(self, result: QFDCascadeResult) -> Dict[str, Any]:
        """Export cascade to dictionary format."""
        return {
            'cascade_id': result.cascade_id,
            'project_name': result.project_name,
            'phases': [
                {
                    'phase_number': p.phase_number,
                    'phase_name': p.phase_name,
                    'hoq': self.hoq_engine.export_to_dict(p.hoq),
                    'inputs': p.inputs,
                    'outputs': p.outputs
                }
                for p in result.phases
            ],
            'critical_path': result.critical_path,
            'summary': result.summary
        }
