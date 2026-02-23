"""
Process FMEA - FMEA for 3D printing manufacturing process.

LEGO MCP v6.0 World-Class Manufacturing Research Platform
Phase 2: Causal AI & Explainability Engine

Focuses on: print parameters, equipment failures, material handling.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from enum import Enum
import logging

from .fmea_engine import FMEAEngine, FailureMode, FMEAAnalysis

logger = logging.getLogger(__name__)


class ProcessStep(Enum):
    """Manufacturing process steps."""
    MATERIAL_PREP = "material_preparation"
    SLICING = "slicing"
    PRINTER_SETUP = "printer_setup"
    PRINTING = "printing"
    COOLING = "cooling"
    REMOVAL = "part_removal"
    POST_PROCESS = "post_processing"
    INSPECTION = "inspection"
    PACKAGING = "packaging"


@dataclass
class PrintProcess:
    """3D printing process specification."""
    process_id: str
    printer_type: str
    material: str
    steps: List[Dict[str, Any]]
    parameters: Dict[str, Any]
    metadata: Dict[str, Any] = field(default_factory=dict)


class ProcessFMEA(FMEAEngine):
    """
    Process FMEA for 3D printing manufacturing.

    Analyzes process-related failure modes:
    - Print parameter variations
    - Equipment failures
    - Material handling issues
    - Environmental factors
    """

    def __init__(self):
        super().__init__()
        self._process_library = self._load_process_failure_library()

    def _load_process_failure_library(self) -> Dict[str, List[Dict]]:
        """Load process failure mode library."""
        return {
            ProcessStep.MATERIAL_PREP.value: [
                {
                    'mode': 'Material moisture absorption',
                    'effects': ['Stringing', 'Poor layer adhesion', 'Bubbles'],
                    'causes': ['Improper storage', 'No drying before use'],
                    'controls': ['Desiccant storage', 'Pre-print drying'],
                    'severity': 6,
                    'occurrence': 5,
                    'detection': 4
                },
                {
                    'mode': 'Wrong material loaded',
                    'effects': ['Wrong properties', 'Dimensional issues', 'Color mismatch'],
                    'causes': ['Operator error', 'Poor labeling'],
                    'controls': ['Material verification', 'Barcode scanning'],
                    'severity': 7,
                    'occurrence': 3,
                    'detection': 3
                }
            ],
            ProcessStep.PRINTER_SETUP.value: [
                {
                    'mode': 'Bed not level',
                    'effects': ['First layer issues', 'Part adhesion failure', 'Dimensional error'],
                    'causes': ['Mechanical drift', 'User error'],
                    'controls': ['Auto bed leveling', 'Pre-print verification'],
                    'severity': 7,
                    'occurrence': 4,
                    'detection': 3
                },
                {
                    'mode': 'Nozzle clog',
                    'effects': ['Underextrusion', 'Missing layers', 'Print failure'],
                    'causes': ['Material debris', 'Heat creep', 'Contamination'],
                    'controls': ['Nozzle cleaning schedule', 'Cold pulls'],
                    'severity': 8,
                    'occurrence': 4,
                    'detection': 5
                }
            ],
            ProcessStep.PRINTING.value: [
                {
                    'mode': 'Temperature variation',
                    'effects': ['Layer adhesion issues', 'Dimensional variation', 'Surface quality'],
                    'causes': ['Heater malfunction', 'Environmental drafts', 'PID tuning'],
                    'controls': ['Temperature monitoring', 'Enclosure'],
                    'severity': 7,
                    'occurrence': 4,
                    'detection': 2
                },
                {
                    'mode': 'Layer shift',
                    'effects': ['Part ruined', 'Dimensional failure', 'Visual defect'],
                    'causes': ['Belt tension', 'Motor skip', 'Obstruction'],
                    'controls': ['Belt tension check', 'Motor current tuning'],
                    'severity': 9,
                    'occurrence': 2,
                    'detection': 6
                },
                {
                    'mode': 'Adhesion failure',
                    'effects': ['Part detaches', 'Warping', 'Print failure'],
                    'causes': ['Bed temperature', 'Surface prep', 'First layer settings'],
                    'controls': ['Adhesion helpers', 'Brim/raft'],
                    'severity': 8,
                    'occurrence': 4,
                    'detection': 4
                }
            ],
            ProcessStep.COOLING.value: [
                {
                    'mode': 'Insufficient cooling',
                    'effects': ['Drooping', 'Poor overhangs', 'Stringing'],
                    'causes': ['Fan failure', 'Fan settings too low', 'Duct obstruction'],
                    'controls': ['Fan verification', 'Cooling test prints'],
                    'severity': 5,
                    'occurrence': 4,
                    'detection': 3
                },
                {
                    'mode': 'Excessive cooling',
                    'effects': ['Layer delamination', 'Warping', 'Poor adhesion'],
                    'causes': ['Enclosure not used', 'Fan too high for material'],
                    'controls': ['Material-specific profiles', 'Enclosure'],
                    'severity': 6,
                    'occurrence': 3,
                    'detection': 4
                }
            ],
            ProcessStep.INSPECTION.value: [
                {
                    'mode': 'Missed defect',
                    'effects': ['Defective part shipped', 'Customer complaint', 'Return'],
                    'causes': ['Human error', 'Inadequate inspection criteria'],
                    'controls': ['Inspection checklist', 'Vision system'],
                    'severity': 7,
                    'occurrence': 4,
                    'detection': 5
                }
            ]
        }

    def analyze_print_process(self, process: PrintProcess) -> FMEAAnalysis:
        """
        Perform comprehensive process FMEA on a print process.

        Args:
            process: PrintProcess specification

        Returns:
            FMEAAnalysis with identified failure modes
        """
        analysis = self.create_analysis(
            name=f"PFMEA - {process.process_id}",
            fmea_type="process",
            scope=f"3D printing process: {process.printer_type}",
            team=["Process Engineer", "Quality Engineer", "Operator"]
        )

        # Analyze each process step
        for step in process.steps:
            step_name = step.get('name', 'unknown')
            self._analyze_step(analysis.fmea_id, step_name, step, process)

        # Analyze step interactions
        self._analyze_step_interactions(analysis.fmea_id, process)

        # Analyze parameter-specific failures
        self._analyze_parameters(analysis.fmea_id, process.parameters)

        logger.info(
            f"PFMEA complete: {len(analysis.failure_modes)} failure modes identified"
        )
        return analysis

    def _analyze_step(self,
                      fmea_id: str,
                      step_name: str,
                      step_data: Dict[str, Any],
                      process: PrintProcess) -> List[FailureMode]:
        """Analyze failure modes for a process step."""
        failure_modes = []

        # Get library modes for this step
        library_modes = self._process_library.get(step_name, [])

        for mode in library_modes:
            fm = self.add_failure_mode(
                fmea_id=fmea_id,
                component=step_name,
                function=step_data.get('function', f"Execute {step_name}"),
                failure_mode=mode['mode'],
                effects=mode['effects'],
                causes=mode['causes'],
                controls=mode['controls'],
                severity=mode['severity'],
                occurrence=mode['occurrence'],
                detection=mode['detection']
            )
            failure_modes.append(fm)

        return failure_modes

    def _analyze_step_interactions(self,
                                   fmea_id: str,
                                   process: PrintProcess) -> List[FailureMode]:
        """Analyze failure modes from step interactions."""
        failure_modes = []

        # Material prep + Printing interaction
        fm = self.add_failure_mode(
            fmea_id=fmea_id,
            component="Step Interaction",
            function="Material-Process compatibility",
            failure_mode="Material properties degraded before printing completes",
            effects=[
                "Quality variation within print",
                "Layer adhesion variation",
                "Surface quality changes"
            ],
            causes=[
                "Long print time with hygroscopic material",
                "Material exposed during printing"
            ],
            controls=["Dry box feeding", "Print time limits for sensitive materials"],
            severity=6,
            occurrence=4,
            detection=5
        )
        failure_modes.append(fm)

        return failure_modes

    def _analyze_parameters(self,
                           fmea_id: str,
                           parameters: Dict[str, Any]) -> List[FailureMode]:
        """Analyze parameter-specific failure modes."""
        failure_modes = []

        # Temperature parameters
        if 'nozzle_temp' in parameters:
            temp = parameters['nozzle_temp']
            if temp > 240:
                fm = self.add_failure_mode(
                    fmea_id=fmea_id,
                    component="Temperature",
                    function="Maintain optimal melt state",
                    failure_mode=f"High nozzle temperature ({temp}C)",
                    effects=[
                        "Material degradation",
                        "Stringing",
                        "Oozing"
                    ],
                    causes=["Profile not optimized for material"],
                    controls=["Temperature tower calibration", "Material datasheet review"],
                    severity=5,
                    occurrence=4,
                    detection=3
                )
                failure_modes.append(fm)

        # Speed parameters
        if 'print_speed' in parameters:
            speed = parameters['print_speed']
            if speed > 80:
                fm = self.add_failure_mode(
                    fmea_id=fmea_id,
                    component="Speed",
                    function="Maintain print quality at speed",
                    failure_mode=f"High print speed ({speed}mm/s)",
                    effects=[
                        "Layer adhesion reduction",
                        "Dimensional accuracy loss",
                        "Ringing artifacts"
                    ],
                    causes=["Throughput optimization without quality validation"],
                    controls=["Speed tower testing", "Quality inspection"],
                    severity=6,
                    occurrence=5,
                    detection=3
                )
                failure_modes.append(fm)

        return failure_modes

    def get_control_plan(self, fmea_id: str) -> Dict[str, Any]:
        """
        Generate control plan from PFMEA.

        Maps high-risk failure modes to control measures.
        """
        analysis = self.get_analysis(fmea_id)
        if not analysis:
            return {}

        control_plan = {
            'fmea_id': fmea_id,
            'controls': []
        }

        high_rpn = analysis.get_high_rpn_items(threshold=80)

        for fm in high_rpn:
            control_plan['controls'].append({
                'process_step': fm.component,
                'failure_mode': fm.failure_mode,
                'rpn': fm.rpn,
                'control_method': fm.current_controls[0] if fm.current_controls else "TBD",
                'frequency': self._recommend_frequency(fm.rpn),
                'reaction_plan': fm.recommended_actions[0] if fm.recommended_actions else "TBD"
            })

        return control_plan

    def _recommend_frequency(self, rpn: int) -> str:
        """Recommend control frequency based on RPN."""
        if rpn >= 200:
            return "Every part"
        elif rpn >= 100:
            return "Every batch"
        elif rpn >= 50:
            return "Daily"
        else:
            return "Weekly"
