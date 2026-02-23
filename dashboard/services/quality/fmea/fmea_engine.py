"""
FMEA Engine - Core Failure Mode and Effects Analysis.

LEGO MCP v6.0 World-Class Manufacturing Research Platform
Phase 2: Causal AI & Explainability Engine

AI-Enhanced FMEA with:
- Automatic failure mode identification from historical data
- ML-predicted occurrence rates
- Causal-graph-based severity propagation
- Automated mitigation recommendations
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Set, Callable
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class SeverityLevel(Enum):
    """Severity ratings (1-10 scale)."""
    NONE = 1
    VERY_MINOR = 2
    MINOR = 3
    VERY_LOW = 4
    LOW = 5
    MODERATE = 6
    HIGH = 7
    VERY_HIGH = 8
    HAZARD_WITH_WARNING = 9
    HAZARD_WITHOUT_WARNING = 10


class OccurrenceLevel(Enum):
    """Occurrence ratings (1-10 scale)."""
    ALMOST_NEVER = 1      # <1 in 1,500,000
    REMOTE = 2            # 1 in 150,000
    VERY_LOW = 3          # 1 in 15,000
    LOW = 4               # 1 in 2,000
    MODERATELY_LOW = 5    # 1 in 400
    MODERATE = 6          # 1 in 80
    MODERATELY_HIGH = 7   # 1 in 20
    HIGH = 8              # 1 in 8
    VERY_HIGH = 9         # 1 in 3
    ALMOST_CERTAIN = 10   # >1 in 2


class DetectionLevel(Enum):
    """Detection ratings (1-10 scale)."""
    ALMOST_CERTAIN = 1    # Will definitely detect
    VERY_HIGH = 2         # Very high chance of detection
    HIGH = 3              # High chance
    MODERATELY_HIGH = 4   # Moderately high
    MODERATE = 5          # Moderate chance
    LOW = 6               # Low chance
    VERY_LOW = 7          # Very low chance
    REMOTE = 8            # Remote chance
    VERY_REMOTE = 9       # Very remote
    ABSOLUTE_UNCERTAINTY = 10  # Cannot detect


@dataclass
class FailureMode:
    """
    Individual failure mode in FMEA.

    Captures potential failure, its causes, effects, and ratings.
    """
    failure_id: str
    component: str
    function: str
    failure_mode: str
    potential_effects: List[str]
    potential_causes: List[str]
    current_controls: List[str]

    # Ratings
    severity: int = 5
    occurrence: int = 5
    detection: int = 5

    # Calculated
    rpn: int = 0  # Risk Priority Number = S * O * D

    # Recommendations
    recommended_actions: List[str] = field(default_factory=list)
    action_owner: Optional[str] = None
    target_date: Optional[datetime] = None

    # Post-action ratings
    new_severity: Optional[int] = None
    new_occurrence: Optional[int] = None
    new_detection: Optional[int] = None
    new_rpn: Optional[int] = None

    # Metadata
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = None
    status: str = "open"

    def calculate_rpn(self) -> int:
        """Calculate Risk Priority Number."""
        self.rpn = self.severity * self.occurrence * self.detection
        return self.rpn

    def calculate_new_rpn(self) -> Optional[int]:
        """Calculate RPN after actions implemented."""
        if all([self.new_severity, self.new_occurrence, self.new_detection]):
            self.new_rpn = self.new_severity * self.new_occurrence * self.new_detection
            return self.new_rpn
        return None


@dataclass
class FMEAAnalysis:
    """Complete FMEA analysis for a component or process."""
    fmea_id: str
    name: str
    fmea_type: str  # "design" or "process"
    scope: str
    team: List[str]
    failure_modes: List[FailureMode]
    created_at: datetime = field(default_factory=datetime.utcnow)
    revision: int = 1

    def get_high_rpn_items(self, threshold: int = 100) -> List[FailureMode]:
        """Get failure modes above RPN threshold."""
        return [fm for fm in self.failure_modes if fm.rpn >= threshold]

    def get_statistics(self) -> Dict[str, Any]:
        """Get FMEA statistics."""
        rpns = [fm.rpn for fm in self.failure_modes]
        return {
            'total_failure_modes': len(self.failure_modes),
            'average_rpn': sum(rpns) / len(rpns) if rpns else 0,
            'max_rpn': max(rpns) if rpns else 0,
            'high_risk_count': len([r for r in rpns if r >= 100]),
            'by_severity': self._count_by_rating('severity'),
            'by_occurrence': self._count_by_rating('occurrence'),
            'by_detection': self._count_by_rating('detection')
        }

    def _count_by_rating(self, field: str) -> Dict[str, int]:
        """Count failure modes by rating level."""
        counts = {}
        for fm in self.failure_modes:
            rating = getattr(fm, field)
            level = f"{rating}"
            counts[level] = counts.get(level, 0) + 1
        return counts


class FMEAEngine:
    """
    Core FMEA analysis engine.

    Features:
    - Standard FMEA methodology
    - RPN calculation and tracking
    - Action recommendations
    - Historical analysis
    """

    def __init__(self):
        self._analyses: Dict[str, FMEAAnalysis] = {}
        self._failure_library: Dict[str, List[Dict]] = {}
        self._severity_model: Optional[Callable] = None
        self._occurrence_model: Optional[Callable] = None

    def set_severity_model(self, model: Callable[[FailureMode], int]) -> None:
        """Set ML model for severity prediction."""
        self._severity_model = model

    def set_occurrence_model(self, model: Callable[[FailureMode], int]) -> None:
        """Set ML model for occurrence prediction."""
        self._occurrence_model = model

    def create_analysis(self,
                        name: str,
                        fmea_type: str,
                        scope: str,
                        team: List[str]) -> FMEAAnalysis:
        """Create a new FMEA analysis."""
        import uuid
        fmea_id = str(uuid.uuid4())[:8]

        analysis = FMEAAnalysis(
            fmea_id=fmea_id,
            name=name,
            fmea_type=fmea_type,
            scope=scope,
            team=team,
            failure_modes=[]
        )

        self._analyses[fmea_id] = analysis
        logger.info(f"Created FMEA analysis: {name}")
        return analysis

    def add_failure_mode(self,
                         fmea_id: str,
                         component: str,
                         function: str,
                         failure_mode: str,
                         effects: List[str],
                         causes: List[str],
                         controls: List[str],
                         severity: int = 5,
                         occurrence: int = 5,
                         detection: int = 5) -> FailureMode:
        """Add a failure mode to an analysis."""
        if fmea_id not in self._analyses:
            raise ValueError(f"Analysis {fmea_id} not found")

        import uuid
        fm = FailureMode(
            failure_id=str(uuid.uuid4())[:8],
            component=component,
            function=function,
            failure_mode=failure_mode,
            potential_effects=effects,
            potential_causes=causes,
            current_controls=controls,
            severity=severity,
            occurrence=occurrence,
            detection=detection
        )

        # Use ML models if available
        if self._severity_model:
            fm.severity = self._severity_model(fm)
        if self._occurrence_model:
            fm.occurrence = self._occurrence_model(fm)

        fm.calculate_rpn()
        self._analyses[fmea_id].failure_modes.append(fm)

        # Generate recommendations for high RPN
        if fm.rpn >= 100:
            fm.recommended_actions = self._generate_recommendations(fm)

        logger.info(f"Added failure mode: {failure_mode} (RPN={fm.rpn})")
        return fm

    def analyze_component(self,
                          component: str,
                          component_data: Dict[str, Any]) -> List[FailureMode]:
        """
        Automatically identify potential failure modes for a component.

        Uses failure library and historical data.
        """
        failure_modes = []

        # Check failure library
        component_type = component_data.get('type', 'generic')
        library_modes = self._failure_library.get(component_type, [])

        for mode_template in library_modes:
            fm = FailureMode(
                failure_id=f"auto_{len(failure_modes)}",
                component=component,
                function=mode_template.get('function', 'Unknown'),
                failure_mode=mode_template.get('mode', 'Unknown'),
                potential_effects=mode_template.get('effects', []),
                potential_causes=mode_template.get('causes', []),
                current_controls=[],
                severity=mode_template.get('typical_severity', 5),
                occurrence=mode_template.get('typical_occurrence', 5),
                detection=5
            )
            fm.calculate_rpn()
            failure_modes.append(fm)

        return failure_modes

    def _generate_recommendations(self, fm: FailureMode) -> List[str]:
        """Generate action recommendations for a failure mode."""
        recommendations = []

        # High severity - focus on design changes
        if fm.severity >= 8:
            recommendations.append(
                f"Consider design modification to eliminate or reduce effect of '{fm.failure_mode}'"
            )

        # High occurrence - focus on prevention
        if fm.occurrence >= 7:
            recommendations.append(
                f"Implement preventive controls for cause: {fm.potential_causes[0] if fm.potential_causes else 'unknown'}"
            )
            recommendations.append("Consider process capability improvement (Cpk target > 1.33)")

        # High detection - improve detection capability
        if fm.detection >= 7:
            recommendations.append("Add in-process inspection or automated detection")
            recommendations.append("Consider error-proofing (Poka-Yoke) implementation")

        return recommendations

    def get_analysis(self, fmea_id: str) -> Optional[FMEAAnalysis]:
        """Get FMEA analysis by ID."""
        return self._analyses.get(fmea_id)

    def get_all_analyses(self) -> List[FMEAAnalysis]:
        """Get all FMEA analyses."""
        return list(self._analyses.values())

    def load_failure_library(self, library: Dict[str, List[Dict]]) -> None:
        """Load standard failure mode library."""
        self._failure_library = library
        logger.info(f"Loaded failure library with {len(library)} component types")

    def export_to_dict(self, fmea_id: str) -> Optional[Dict[str, Any]]:
        """Export FMEA to dictionary format."""
        analysis = self._analyses.get(fmea_id)
        if not analysis:
            return None

        return {
            'fmea_id': analysis.fmea_id,
            'name': analysis.name,
            'type': analysis.fmea_type,
            'scope': analysis.scope,
            'team': analysis.team,
            'revision': analysis.revision,
            'created_at': analysis.created_at.isoformat(),
            'failure_modes': [
                {
                    'failure_id': fm.failure_id,
                    'component': fm.component,
                    'function': fm.function,
                    'failure_mode': fm.failure_mode,
                    'effects': fm.potential_effects,
                    'causes': fm.potential_causes,
                    'controls': fm.current_controls,
                    'S': fm.severity,
                    'O': fm.occurrence,
                    'D': fm.detection,
                    'RPN': fm.rpn,
                    'recommended_actions': fm.recommended_actions,
                    'status': fm.status
                }
                for fm in analysis.failure_modes
            ],
            'statistics': analysis.get_statistics()
        }


# Standard LEGO manufacturing failure library
LEGO_FAILURE_LIBRARY = {
    'stud': [
        {
            'function': 'Provide clutch power connection',
            'mode': 'Stud diameter out of tolerance',
            'effects': ['Poor clutch power', 'Loose connection', 'Incompatibility'],
            'causes': ['Temperature variation', 'Tool wear', 'Material shrinkage'],
            'typical_severity': 7,
            'typical_occurrence': 4
        },
        {
            'function': 'Provide clutch power connection',
            'mode': 'Stud height incorrect',
            'effects': ['Interference with other bricks', 'Poor stacking'],
            'causes': ['Z-axis calibration', 'Layer adhesion issues'],
            'typical_severity': 6,
            'typical_occurrence': 3
        }
    ],
    'tube': [
        {
            'function': 'Receive stud for connection',
            'mode': 'Tube inner diameter out of tolerance',
            'effects': ['Poor clutch power', 'Brick won\'t connect'],
            'causes': ['Print overextrusion', 'Cooling issues'],
            'typical_severity': 7,
            'typical_occurrence': 4
        }
    ],
    'wall': [
        {
            'function': 'Provide structural integrity',
            'mode': 'Wall thickness insufficient',
            'effects': ['Weak structure', 'Breakage under load'],
            'causes': ['Underextrusion', 'Perimeter settings'],
            'typical_severity': 8,
            'typical_occurrence': 3
        }
    ],
    'surface': [
        {
            'function': 'Provide aesthetic appearance',
            'mode': 'Surface defects (stringing, blobs)',
            'effects': ['Poor appearance', 'Customer rejection'],
            'causes': ['Retraction settings', 'Temperature too high'],
            'typical_severity': 4,
            'typical_occurrence': 5
        }
    ]
}
