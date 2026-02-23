"""
Design FMEA - FMEA for LEGO brick design.

LEGO MCP v6.0 World-Class Manufacturing Research Platform
Phase 2: Causal AI & Explainability Engine

Focuses on: dimensional tolerances, material selection, clutch power design.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
import logging

from .fmea_engine import FMEAEngine, FailureMode, FMEAAnalysis, LEGO_FAILURE_LIBRARY

logger = logging.getLogger(__name__)


@dataclass
class BrickDesign:
    """LEGO brick design specification."""
    brick_id: str
    brick_type: str  # e.g., "2x4", "1x2", "plate_2x4"
    studs: Dict[str, Any]  # Stud geometry specs
    tubes: Dict[str, Any]  # Anti-stud tube specs
    walls: Dict[str, Any]  # Wall specs
    material: str
    color: str
    metadata: Dict[str, Any] = field(default_factory=dict)


class DesignFMEA(FMEAEngine):
    """
    Design FMEA specifically for LEGO brick development.

    Analyzes design-related failure modes:
    - Dimensional specifications
    - Material selection
    - Clutch power design
    - Compatibility with official LEGO
    """

    def __init__(self):
        super().__init__()
        self.load_failure_library(LEGO_FAILURE_LIBRARY)
        self._design_rules = self._load_design_rules()

    def _load_design_rules(self) -> Dict[str, Any]:
        """Load LEGO design rules and specifications."""
        return {
            'stud': {
                'diameter': {'nominal': 4.8, 'tolerance': 0.02},
                'height': {'nominal': 1.7, 'tolerance': 0.05},
                'pitch': {'nominal': 8.0, 'tolerance': 0.02}
            },
            'tube': {
                'outer_diameter': {'nominal': 6.51, 'tolerance': 0.05},
                'inner_diameter': {'nominal': 4.8, 'tolerance': 0.02}
            },
            'wall': {
                'thickness': {'nominal': 1.5, 'tolerance': 0.05}
            },
            'clutch_power': {
                'min_force': 0.5,  # Newtons
                'optimal_min': 1.0,
                'optimal_max': 3.0,
                'max_force': 5.0
            }
        }

    def analyze_brick_design(self, design: BrickDesign) -> FMEAAnalysis:
        """
        Perform comprehensive design FMEA on a brick design.

        Args:
            design: BrickDesign specification

        Returns:
            FMEAAnalysis with identified failure modes
        """
        # Create analysis
        analysis = self.create_analysis(
            name=f"DFMEA - {design.brick_type}",
            fmea_type="design",
            scope=f"LEGO brick design: {design.brick_id}",
            team=["Design Engineer", "Quality Engineer"]
        )

        # Analyze each component
        stud_fms = self._analyze_studs(analysis.fmea_id, design)
        tube_fms = self._analyze_tubes(analysis.fmea_id, design)
        wall_fms = self._analyze_walls(analysis.fmea_id, design)
        material_fms = self._analyze_material(analysis.fmea_id, design)

        logger.info(
            f"DFMEA complete: {len(analysis.failure_modes)} failure modes identified"
        )
        return analysis

    def _analyze_studs(self, fmea_id: str, design: BrickDesign) -> List[FailureMode]:
        """Analyze stud geometry failure modes."""
        failure_modes = []
        stud_specs = design.studs
        rules = self._design_rules['stud']

        # Check diameter specification
        if 'diameter' in stud_specs:
            nominal = stud_specs['diameter']
            target = rules['diameter']['nominal']
            tolerance = rules['diameter']['tolerance']

            if abs(nominal - target) > tolerance:
                fm = self.add_failure_mode(
                    fmea_id=fmea_id,
                    component="Stud",
                    function="Provide interference fit with tube",
                    failure_mode=f"Diameter spec ({nominal}mm) deviates from nominal ({target}mm)",
                    effects=[
                        "Reduced clutch power" if nominal < target else "Excessive clutch power",
                        "Incompatibility with official LEGO",
                        "Customer complaints"
                    ],
                    causes=[
                        "Incorrect design specification",
                        "Compensation for manufacturing process not applied"
                    ],
                    controls=["Design review", "Tolerance analysis"],
                    severity=8,
                    occurrence=3,
                    detection=2
                )
                failure_modes.append(fm)

        # Check height specification
        if 'height' in stud_specs:
            nominal = stud_specs['height']
            target = rules['height']['nominal']

            if abs(nominal - target) > rules['height']['tolerance']:
                fm = self.add_failure_mode(
                    fmea_id=fmea_id,
                    component="Stud",
                    function="Allow proper brick stacking",
                    failure_mode=f"Height spec ({nominal}mm) outside tolerance",
                    effects=[
                        "Improper stacking",
                        "Visual gaps or interference"
                    ],
                    causes=["Incorrect design specification"],
                    controls=["Design review"],
                    severity=6,
                    occurrence=2,
                    detection=2
                )
                failure_modes.append(fm)

        # Add standard stud failure modes from library
        for mode in self._failure_library.get('stud', []):
            fm = self.add_failure_mode(
                fmea_id=fmea_id,
                component="Stud",
                function=mode['function'],
                failure_mode=mode['mode'],
                effects=mode['effects'],
                causes=mode['causes'],
                controls=["Design verification"],
                severity=mode['typical_severity'],
                occurrence=mode['typical_occurrence'],
                detection=5
            )
            failure_modes.append(fm)

        return failure_modes

    def _analyze_tubes(self, fmea_id: str, design: BrickDesign) -> List[FailureMode]:
        """Analyze anti-stud tube failure modes."""
        failure_modes = []
        tube_specs = design.tubes
        rules = self._design_rules['tube']

        # Check inner diameter (critical for clutch)
        if 'inner_diameter' in tube_specs:
            nominal = tube_specs['inner_diameter']
            target = rules['inner_diameter']['nominal']
            tolerance = rules['inner_diameter']['tolerance']

            if abs(nominal - target) > tolerance:
                fm = self.add_failure_mode(
                    fmea_id=fmea_id,
                    component="Anti-stud Tube",
                    function="Receive stud for connection",
                    failure_mode=f"Inner diameter ({nominal}mm) outside tolerance",
                    effects=[
                        "Clutch power out of specification",
                        "Connection failure or excessive force required"
                    ],
                    causes=["Design tolerance stack-up", "FDM compensation not applied"],
                    controls=["Tolerance analysis", "Prototype testing"],
                    severity=8,
                    occurrence=4,
                    detection=3
                )
                failure_modes.append(fm)

        return failure_modes

    def _analyze_walls(self, fmea_id: str, design: BrickDesign) -> List[FailureMode]:
        """Analyze wall structure failure modes."""
        failure_modes = []
        wall_specs = design.walls
        rules = self._design_rules['wall']

        if 'thickness' in wall_specs:
            thickness = wall_specs['thickness']
            target = rules['thickness']['nominal']

            if thickness < target - rules['thickness']['tolerance']:
                fm = self.add_failure_mode(
                    fmea_id=fmea_id,
                    component="Wall",
                    function="Provide structural integrity",
                    failure_mode=f"Wall thickness ({thickness}mm) below minimum",
                    effects=[
                        "Reduced structural strength",
                        "Potential breakage during use",
                        "Deformation under load"
                    ],
                    causes=["Weight reduction optimization", "Cost reduction"],
                    controls=["FEA analysis", "Drop testing"],
                    severity=9,
                    occurrence=3,
                    detection=2
                )
                failure_modes.append(fm)

        return failure_modes

    def _analyze_material(self, fmea_id: str, design: BrickDesign) -> List[FailureMode]:
        """Analyze material-related failure modes."""
        failure_modes = []
        material = design.material.lower()

        # Material-specific failure modes
        if 'pla' in material:
            fm = self.add_failure_mode(
                fmea_id=fmea_id,
                component="Material",
                function="Provide mechanical properties",
                failure_mode="PLA heat sensitivity",
                effects=[
                    "Deformation above 55C",
                    "Not suitable for high-temp environments"
                ],
                causes=["Material selection based on cost/availability"],
                controls=["Material specification review", "Application guidelines"],
                severity=5,
                occurrence=3,
                detection=1
            )
            failure_modes.append(fm)

        elif 'abs' in material:
            fm = self.add_failure_mode(
                fmea_id=fmea_id,
                component="Material",
                function="Provide dimensional stability",
                failure_mode="ABS warping during cooling",
                effects=[
                    "Dimensional inaccuracy",
                    "Clutch power variation"
                ],
                causes=["Uneven cooling", "Part geometry"],
                controls=["Process parameter optimization", "Enclosure use"],
                severity=6,
                occurrence=5,
                detection=3
            )
            failure_modes.append(fm)

        return failure_modes

    def validate_against_lego_specs(self, design: BrickDesign) -> Dict[str, Any]:
        """
        Validate design against official LEGO specifications.

        Returns validation report.
        """
        report = {
            'brick_id': design.brick_id,
            'compliant': True,
            'deviations': [],
            'warnings': []
        }

        rules = self._design_rules

        # Check stud diameter
        if 'diameter' in design.studs:
            deviation = abs(design.studs['diameter'] - rules['stud']['diameter']['nominal'])
            if deviation > rules['stud']['diameter']['tolerance']:
                report['compliant'] = False
                report['deviations'].append({
                    'parameter': 'stud_diameter',
                    'specified': design.studs['diameter'],
                    'nominal': rules['stud']['diameter']['nominal'],
                    'tolerance': rules['stud']['diameter']['tolerance'],
                    'deviation': deviation
                })

        # Check tube inner diameter
        if 'inner_diameter' in design.tubes:
            deviation = abs(design.tubes['inner_diameter'] - rules['tube']['inner_diameter']['nominal'])
            if deviation > rules['tube']['inner_diameter']['tolerance']:
                report['compliant'] = False
                report['deviations'].append({
                    'parameter': 'tube_inner_diameter',
                    'specified': design.tubes['inner_diameter'],
                    'nominal': rules['tube']['inner_diameter']['nominal'],
                    'tolerance': rules['tube']['inner_diameter']['tolerance'],
                    'deviation': deviation
                })

        return report
