"""
Failure Mode Library - Standard failure mode database.

LEGO MCP v6.0 World-Class Manufacturing Research Platform
Phase 2: Causal AI, Explainability, FMEA & HOQ
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Set
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class FailureCategory(Enum):
    """Categories of failure modes."""
    DIMENSIONAL = "dimensional"
    SURFACE = "surface"
    STRUCTURAL = "structural"
    MATERIAL = "material"
    FUNCTIONAL = "functional"
    AESTHETIC = "aesthetic"
    THERMAL = "thermal"
    MECHANICAL = "mechanical"


class ProcessType(Enum):
    """Manufacturing process types."""
    FDM = "fdm"
    SLA = "sla"
    SLS = "sls"
    INJECTION_MOLDING = "injection_molding"
    CNC = "cnc"
    ASSEMBLY = "assembly"


@dataclass
class FailureMode:
    """Standard failure mode definition."""
    failure_id: str
    name: str
    description: str
    category: FailureCategory
    applicable_processes: List[ProcessType]
    typical_severity: int  # 1-10
    typical_occurrence: int  # 1-10
    typical_detection: int  # 1-10
    potential_causes: List[str]
    potential_effects: List[str]
    recommended_controls: List[str]
    keywords: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class FailureModeMatch:
    """Match result from library search."""
    failure_mode: FailureMode
    relevance_score: float
    matched_keywords: List[str]


class FailureModeLibrary:
    """
    Standard failure mode database for LEGO manufacturing.

    Features:
    - Pre-defined failure modes by category
    - FDM/3D printing specific failures
    - LEGO brick-specific failures
    - Searchable by keywords
    """

    def __init__(self):
        self._library: Dict[str, FailureMode] = {}
        self._by_category: Dict[FailureCategory, List[str]] = {}
        self._by_process: Dict[ProcessType, List[str]] = {}
        self._load_standard_library()

    def _load_standard_library(self) -> None:
        """Load standard failure modes."""
        # Dimensional failures
        self._add_failure_mode(FailureMode(
            failure_id="DIM-001",
            name="Stud diameter out of tolerance",
            description="LEGO stud diameter deviates from 4.8mm specification",
            category=FailureCategory.DIMENSIONAL,
            applicable_processes=[ProcessType.FDM, ProcessType.SLA, ProcessType.INJECTION_MOLDING],
            typical_severity=8,
            typical_occurrence=4,
            typical_detection=3,
            potential_causes=[
                "Incorrect flow rate",
                "Thermal expansion",
                "Printer calibration error",
                "Material shrinkage"
            ],
            potential_effects=[
                "Poor clutch power",
                "Incompatibility with official LEGO",
                "Loose brick connections"
            ],
            recommended_controls=[
                "Dimensional inspection",
                "Flow rate calibration",
                "Temperature compensation"
            ],
            keywords=["stud", "diameter", "tolerance", "clutch"]
        ))

        self._add_failure_mode(FailureMode(
            failure_id="DIM-002",
            name="Anti-stud tube diameter deviation",
            description="Inner tube diameter deviates from specification",
            category=FailureCategory.DIMENSIONAL,
            applicable_processes=[ProcessType.FDM, ProcessType.SLA, ProcessType.INJECTION_MOLDING],
            typical_severity=8,
            typical_occurrence=4,
            typical_detection=4,
            potential_causes=[
                "Print shrinkage",
                "Support removal damage",
                "Layer misalignment"
            ],
            potential_effects=[
                "Poor brick compatibility",
                "Weak connections",
                "Assembly difficulty"
            ],
            recommended_controls=[
                "Internal diameter gauge",
                "Print compensation factors",
                "Support optimization"
            ],
            keywords=["tube", "anti-stud", "diameter", "internal"]
        ))

        self._add_failure_mode(FailureMode(
            failure_id="DIM-003",
            name="Overall brick height variation",
            description="Total brick height exceeds tolerance of +/- 0.02mm",
            category=FailureCategory.DIMENSIONAL,
            applicable_processes=[ProcessType.FDM, ProcessType.SLA],
            typical_severity=7,
            typical_occurrence=3,
            typical_detection=2,
            potential_causes=[
                "Z-axis calibration",
                "First layer adhesion",
                "Bed leveling issues"
            ],
            potential_effects=[
                "Stacking issues",
                "Uneven builds",
                "Visual defects"
            ],
            recommended_controls=[
                "Height measurement",
                "Z-offset calibration",
                "Bed leveling verification"
            ],
            keywords=["height", "z-axis", "stacking", "level"]
        ))

        # Surface failures
        self._add_failure_mode(FailureMode(
            failure_id="SRF-001",
            name="Layer lines visible",
            description="Visible layer lines on vertical surfaces",
            category=FailureCategory.SURFACE,
            applicable_processes=[ProcessType.FDM],
            typical_severity=4,
            typical_occurrence=7,
            typical_detection=1,
            potential_causes=[
                "Layer height too high",
                "Extrusion inconsistency",
                "Vibration during print"
            ],
            potential_effects=[
                "Poor aesthetics",
                "Rough surface feel",
                "Potential weak points"
            ],
            recommended_controls=[
                "Reduce layer height",
                "Anti-vibration mounts",
                "Post-processing"
            ],
            keywords=["layer", "lines", "surface", "visible", "roughness"]
        ))

        self._add_failure_mode(FailureMode(
            failure_id="SRF-002",
            name="Stringing between features",
            description="Thin strings of material between print features",
            category=FailureCategory.SURFACE,
            applicable_processes=[ProcessType.FDM],
            typical_severity=3,
            typical_occurrence=5,
            typical_detection=1,
            potential_causes=[
                "Insufficient retraction",
                "Temperature too high",
                "Travel speed too slow"
            ],
            potential_effects=[
                "Poor appearance",
                "Extra post-processing",
                "Potential stud interference"
            ],
            recommended_controls=[
                "Retraction tuning",
                "Temperature optimization",
                "Increase travel speed"
            ],
            keywords=["stringing", "oozing", "retraction", "travel"]
        ))

        self._add_failure_mode(FailureMode(
            failure_id="SRF-003",
            name="Surface pitting/voids",
            description="Small holes or voids on surface",
            category=FailureCategory.SURFACE,
            applicable_processes=[ProcessType.FDM, ProcessType.SLA],
            typical_severity=5,
            typical_occurrence=3,
            typical_detection=2,
            potential_causes=[
                "Moisture in filament",
                "Under-extrusion",
                "Trapped air bubbles"
            ],
            potential_effects=[
                "Structural weakness",
                "Poor appearance",
                "Potential crack initiation"
            ],
            recommended_controls=[
                "Filament drying",
                "Flow rate adjustment",
                "Material storage control"
            ],
            keywords=["pitting", "voids", "holes", "surface", "moisture"]
        ))

        # Structural failures
        self._add_failure_mode(FailureMode(
            failure_id="STR-001",
            name="Layer delamination",
            description="Separation between printed layers",
            category=FailureCategory.STRUCTURAL,
            applicable_processes=[ProcessType.FDM],
            typical_severity=9,
            typical_occurrence=3,
            typical_detection=4,
            potential_causes=[
                "Print temperature too low",
                "Cooling too aggressive",
                "Poor bed adhesion causing warping"
            ],
            potential_effects=[
                "Part failure under load",
                "Complete brick separation",
                "Safety hazard"
            ],
            recommended_controls=[
                "Temperature optimization",
                "Layer adhesion testing",
                "Enclosure usage"
            ],
            keywords=["delamination", "layer", "adhesion", "separation"]
        ))

        self._add_failure_mode(FailureMode(
            failure_id="STR-002",
            name="Warping/curling",
            description="Part edges lift from build plate or curl",
            category=FailureCategory.STRUCTURAL,
            applicable_processes=[ProcessType.FDM],
            typical_severity=6,
            typical_occurrence=5,
            typical_detection=2,
            potential_causes=[
                "Bed temperature too low",
                "Drafts/cooling",
                "Material shrinkage",
                "Poor bed adhesion"
            ],
            potential_effects=[
                "Dimensional inaccuracy",
                "Print failure",
                "Poor brick fit"
            ],
            recommended_controls=[
                "Heated bed",
                "Enclosure",
                "Bed adhesion solutions"
            ],
            keywords=["warping", "curling", "adhesion", "shrinkage"]
        ))

        self._add_failure_mode(FailureMode(
            failure_id="STR-003",
            name="Stud breakage",
            description="Studs break during use or handling",
            category=FailureCategory.STRUCTURAL,
            applicable_processes=[ProcessType.FDM, ProcessType.SLA],
            typical_severity=9,
            typical_occurrence=2,
            typical_detection=5,
            potential_causes=[
                "Insufficient wall thickness",
                "Poor layer adhesion at stud base",
                "Material brittleness"
            ],
            potential_effects=[
                "Brick unusable",
                "Safety hazard (small parts)",
                "User dissatisfaction"
            ],
            recommended_controls=[
                "Stud-specific strength testing",
                "Design reinforcement",
                "Material selection"
            ],
            keywords=["stud", "break", "strength", "structural"]
        ))

        # Material failures
        self._add_failure_mode(FailureMode(
            failure_id="MAT-001",
            name="Color inconsistency",
            description="Visible color variation within or between parts",
            category=FailureCategory.MATERIAL,
            applicable_processes=[ProcessType.FDM, ProcessType.INJECTION_MOLDING],
            typical_severity=4,
            typical_occurrence=4,
            typical_detection=1,
            potential_causes=[
                "Filament batch variation",
                "Temperature fluctuation",
                "Material degradation"
            ],
            potential_effects=[
                "Poor aesthetics",
                "Build inconsistency",
                "User complaints"
            ],
            recommended_controls=[
                "Batch control",
                "Color measurement (Delta E)",
                "Material traceability"
            ],
            keywords=["color", "consistency", "variation", "aesthetic"]
        ))

        self._add_failure_mode(FailureMode(
            failure_id="MAT-002",
            name="Material contamination",
            description="Foreign particles or mixed materials in print",
            category=FailureCategory.MATERIAL,
            applicable_processes=[ProcessType.FDM, ProcessType.INJECTION_MOLDING],
            typical_severity=7,
            typical_occurrence=2,
            typical_detection=4,
            potential_causes=[
                "Dirty nozzle",
                "Material changeover",
                "Environmental contamination"
            ],
            potential_effects=[
                "Weak spots",
                "Surface defects",
                "Color specks"
            ],
            recommended_controls=[
                "Nozzle purging",
                "Material handling procedures",
                "Clean room protocols"
            ],
            keywords=["contamination", "foreign", "particle", "mixed"]
        ))

        # Functional failures
        self._add_failure_mode(FailureMode(
            failure_id="FUN-001",
            name="Insufficient clutch power",
            description="Bricks don't grip firmly when connected",
            category=FailureCategory.FUNCTIONAL,
            applicable_processes=[ProcessType.FDM, ProcessType.SLA, ProcessType.INJECTION_MOLDING],
            typical_severity=9,
            typical_occurrence=4,
            typical_detection=2,
            potential_causes=[
                "Stud diameter too small",
                "Tube diameter too large",
                "Material too flexible"
            ],
            potential_effects=[
                "Bricks fall apart",
                "Poor play experience",
                "Incompatibility with LEGO"
            ],
            recommended_controls=[
                "Clutch force testing",
                "Dimensional verification",
                "Material stiffness testing"
            ],
            keywords=["clutch", "grip", "connection", "loose"]
        ))

        self._add_failure_mode(FailureMode(
            failure_id="FUN-002",
            name="Excessive clutch power",
            description="Bricks are too difficult to separate",
            category=FailureCategory.FUNCTIONAL,
            applicable_processes=[ProcessType.FDM, ProcessType.SLA, ProcessType.INJECTION_MOLDING],
            typical_severity=6,
            typical_occurrence=3,
            typical_detection=2,
            potential_causes=[
                "Stud diameter too large",
                "Tube diameter too small",
                "Surface roughness increasing friction"
            ],
            potential_effects=[
                "Difficult to disassemble",
                "User frustration",
                "Potential damage during separation"
            ],
            recommended_controls=[
                "Clutch force testing",
                "Dimensional calibration",
                "Surface finish control"
            ],
            keywords=["clutch", "tight", "difficult", "separate"]
        ))

        # Thermal failures
        self._add_failure_mode(FailureMode(
            failure_id="THM-001",
            name="Thermal distortion",
            description="Part warps or distorts due to heat during or after printing",
            category=FailureCategory.THERMAL,
            applicable_processes=[ProcessType.FDM],
            typical_severity=6,
            typical_occurrence=3,
            typical_detection=2,
            potential_causes=[
                "Uneven cooling",
                "High internal stress",
                "Material with high thermal expansion"
            ],
            potential_effects=[
                "Dimensional inaccuracy",
                "Brick fit issues",
                "Warped appearance"
            ],
            recommended_controls=[
                "Controlled cooling",
                "Annealing process",
                "Material selection"
            ],
            keywords=["thermal", "distortion", "heat", "cooling", "warp"]
        ))

        logger.info(f"Loaded {len(self._library)} standard failure modes")

    def _add_failure_mode(self, fm: FailureMode) -> None:
        """Add failure mode to library."""
        self._library[fm.failure_id] = fm

        # Index by category
        if fm.category not in self._by_category:
            self._by_category[fm.category] = []
        self._by_category[fm.category].append(fm.failure_id)

        # Index by process
        for process in fm.applicable_processes:
            if process not in self._by_process:
                self._by_process[process] = []
            self._by_process[process].append(fm.failure_id)

    def get_failure_mode(self, failure_id: str) -> Optional[FailureMode]:
        """Get failure mode by ID."""
        return self._library.get(failure_id)

    def get_by_category(self, category: FailureCategory) -> List[FailureMode]:
        """Get all failure modes in category."""
        fm_ids = self._by_category.get(category, [])
        return [self._library[fid] for fid in fm_ids]

    def get_by_process(self, process: ProcessType) -> List[FailureMode]:
        """Get all failure modes for process type."""
        fm_ids = self._by_process.get(process, [])
        return [self._library[fid] for fid in fm_ids]

    def search(self,
               query: str,
               process: Optional[ProcessType] = None,
               category: Optional[FailureCategory] = None,
               max_results: int = 10) -> List[FailureModeMatch]:
        """
        Search failure modes by keywords.

        Args:
            query: Search query
            process: Filter by process type
            category: Filter by category
            max_results: Maximum results to return

        Returns:
            Ranked list of matching failure modes
        """
        query_terms = set(query.lower().split())
        matches = []

        for fm in self._library.values():
            # Apply filters
            if process and process not in fm.applicable_processes:
                continue
            if category and fm.category != category:
                continue

            # Score match
            all_keywords = set(kw.lower() for kw in fm.keywords)
            all_keywords.add(fm.name.lower())
            all_keywords.update(word.lower() for word in fm.description.split())

            matched = query_terms & all_keywords
            if matched:
                score = len(matched) / len(query_terms)
                matches.append(FailureModeMatch(
                    failure_mode=fm,
                    relevance_score=score,
                    matched_keywords=list(matched)
                ))

        # Sort by relevance
        matches.sort(key=lambda m: m.relevance_score, reverse=True)
        return matches[:max_results]

    def get_related_failures(self, failure_id: str) -> List[FailureMode]:
        """Get failure modes related to given one."""
        fm = self._library.get(failure_id)
        if not fm:
            return []

        related = []
        for other in self._library.values():
            if other.failure_id == failure_id:
                continue

            # Same category
            if other.category == fm.category:
                related.append(other)
                continue

            # Overlapping keywords
            overlap = set(fm.keywords) & set(other.keywords)
            if len(overlap) >= 2:
                related.append(other)

        return related

    def add_custom_failure_mode(self, fm: FailureMode) -> None:
        """Add custom failure mode to library."""
        if fm.failure_id in self._library:
            raise ValueError(f"Failure mode {fm.failure_id} already exists")
        self._add_failure_mode(fm)
        logger.info(f"Added custom failure mode: {fm.failure_id}")

    def get_all_ids(self) -> List[str]:
        """Get all failure mode IDs."""
        return list(self._library.keys())

    def get_statistics(self) -> Dict[str, Any]:
        """Get library statistics."""
        return {
            'total_failure_modes': len(self._library),
            'by_category': {
                cat.value: len(ids) for cat, ids in self._by_category.items()
            },
            'by_process': {
                proc.value: len(ids) for proc, ids in self._by_process.items()
            }
        }
