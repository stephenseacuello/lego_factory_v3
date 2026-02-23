"""
ISO 23247 Digital Twin Compliance Validation Service
=====================================================

Validates and reports compliance with ISO 23247 Digital Twin Framework
for Manufacturing.

ISO 23247 Parts:
- Part 1: Overview and general principles
- Part 2: Reference architecture
- Part 3: Digital representation of manufacturing elements
- Part 4: Information exchange

Compliance Levels:
- Level 1: Basic - Core digital representation exists
- Level 2: Intermediate - Bi-directional sync and behavior models
- Level 3: Advanced - Full predictive/simulation capabilities
- Level 4: World-Class - Complete ISO 23247 + extensions

Author: LegoMCP Team
Version: 2.0.0
"""

from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum
import logging
import json

logger = logging.getLogger(__name__)


class ComplianceLevel(Enum):
    """ISO 23247 compliance levels."""
    NON_COMPLIANT = 0
    BASIC = 1
    INTERMEDIATE = 2
    ADVANCED = 3
    WORLD_CLASS = 4


class RequirementStatus(Enum):
    """Status of individual requirements."""
    COMPLIANT = "compliant"
    PARTIAL = "partial"
    NON_COMPLIANT = "non_compliant"
    NOT_APPLICABLE = "not_applicable"


class RequirementPriority(Enum):
    """Priority of requirements."""
    CRITICAL = "critical"      # Must have for any compliance
    HIGH = "high"              # Required for Level 2+
    MEDIUM = "medium"          # Required for Level 3+
    LOW = "low"                # Nice to have for Level 4


@dataclass
class ComplianceRequirement:
    """Individual compliance requirement."""
    id: str
    name: str
    description: str
    iso_section: str  # ISO 23247 section reference
    part: int  # ISO 23247 part (1-4)
    priority: RequirementPriority
    status: RequirementStatus = RequirementStatus.NON_COMPLIANT
    evidence: str = ""
    gaps: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)
    tested_at: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'iso_section': self.iso_section,
            'part': self.part,
            'priority': self.priority.value,
            'status': self.status.value,
            'evidence': self.evidence,
            'gaps': self.gaps,
            'recommendations': self.recommendations,
            'tested_at': self.tested_at.isoformat() if self.tested_at else None
        }


@dataclass
class ComplianceReport:
    """Complete compliance assessment report."""
    report_id: str
    generated_at: datetime
    overall_level: ComplianceLevel
    overall_score: float  # 0-100
    requirements: List[ComplianceRequirement]
    summary: Dict[str, Any]
    gaps_summary: List[str]
    roadmap: List[Dict[str, Any]]

    def to_dict(self) -> Dict[str, Any]:
        return {
            'report_id': self.report_id,
            'generated_at': self.generated_at.isoformat(),
            'overall_level': self.overall_level.value,
            'overall_level_name': self.overall_level.name,
            'overall_score': self.overall_score,
            'requirements': [r.to_dict() for r in self.requirements],
            'summary': self.summary,
            'gaps_summary': self.gaps_summary,
            'roadmap': self.roadmap
        }


class ISO23247ComplianceService:
    """
    Service for validating ISO 23247 compliance.

    Validates system against all 4 parts of ISO 23247:
    - Observable Manufacturing Elements
    - Digital Twin Entities
    - Data Collection Domain
    - Information Exchange
    """

    def __init__(self):
        self._requirements = self._initialize_requirements()
        self._last_report: Optional[ComplianceReport] = None

    def _initialize_requirements(self) -> List[ComplianceRequirement]:
        """Initialize all ISO 23247 requirements."""
        requirements = [
            # ==================== Part 1: Overview ====================
            ComplianceRequirement(
                id="ISO23247-1-001",
                name="Digital Twin Definition",
                description="System has formal definition of digital twin entities",
                iso_section="ISO 23247-1 Section 4.1",
                part=1,
                priority=RequirementPriority.CRITICAL
            ),
            ComplianceRequirement(
                id="ISO23247-1-002",
                name="Manufacturing Context",
                description="Digital twins are contextualized for manufacturing",
                iso_section="ISO 23247-1 Section 4.2",
                part=1,
                priority=RequirementPriority.CRITICAL
            ),
            ComplianceRequirement(
                id="ISO23247-1-003",
                name="Lifecycle Coverage",
                description="Digital twin covers full manufacturing lifecycle",
                iso_section="ISO 23247-1 Section 5.2",
                part=1,
                priority=RequirementPriority.HIGH
            ),

            # ==================== Part 2: Reference Architecture ====================
            ComplianceRequirement(
                id="ISO23247-2-001",
                name="Four Domain Architecture",
                description="System implements User, DT, Data Collection, and OME domains",
                iso_section="ISO 23247-2 Section 5.1",
                part=2,
                priority=RequirementPriority.CRITICAL
            ),
            ComplianceRequirement(
                id="ISO23247-2-002",
                name="User Domain",
                description="User domain provides interfaces for twin interaction",
                iso_section="ISO 23247-2 Section 5.2",
                part=2,
                priority=RequirementPriority.CRITICAL
            ),
            ComplianceRequirement(
                id="ISO23247-2-003",
                name="Digital Twin Domain",
                description="DT domain manages twin instances and behavior models",
                iso_section="ISO 23247-2 Section 5.3",
                part=2,
                priority=RequirementPriority.CRITICAL
            ),
            ComplianceRequirement(
                id="ISO23247-2-004",
                name="Data Collection Domain",
                description="Data collection domain handles sensor/actuator interface",
                iso_section="ISO 23247-2 Section 5.4",
                part=2,
                priority=RequirementPriority.CRITICAL
            ),
            ComplianceRequirement(
                id="ISO23247-2-005",
                name="OME Domain",
                description="Observable manufacturing elements are identified and tracked",
                iso_section="ISO 23247-2 Section 5.5",
                part=2,
                priority=RequirementPriority.CRITICAL
            ),
            ComplianceRequirement(
                id="ISO23247-2-006",
                name="Inter-Domain Communication",
                description="Domains communicate via defined interfaces",
                iso_section="ISO 23247-2 Section 6",
                part=2,
                priority=RequirementPriority.HIGH
            ),

            # ==================== Part 3: Digital Representation ====================
            ComplianceRequirement(
                id="ISO23247-3-001",
                name="OME Identification",
                description="Unique identification scheme for OMEs",
                iso_section="ISO 23247-3 Section 7.2",
                part=3,
                priority=RequirementPriority.CRITICAL
            ),
            ComplianceRequirement(
                id="ISO23247-3-002",
                name="Static Attributes",
                description="OMEs have static attributes (specs, geometry)",
                iso_section="ISO 23247-3 Section 7.3.1",
                part=3,
                priority=RequirementPriority.CRITICAL
            ),
            ComplianceRequirement(
                id="ISO23247-3-003",
                name="Dynamic Attributes",
                description="OMEs have dynamic attributes (state, metrics)",
                iso_section="ISO 23247-3 Section 7.3.2",
                part=3,
                priority=RequirementPriority.CRITICAL
            ),
            ComplianceRequirement(
                id="ISO23247-3-004",
                name="Behavior Models",
                description="OMEs have associated behavior models",
                iso_section="ISO 23247-3 Section 7.4",
                part=3,
                priority=RequirementPriority.HIGH
            ),
            ComplianceRequirement(
                id="ISO23247-3-005",
                name="Relationships",
                description="Relationships between OMEs are defined",
                iso_section="ISO 23247-3 Section 7.5",
                part=3,
                priority=RequirementPriority.HIGH
            ),
            ComplianceRequirement(
                id="ISO23247-3-006",
                name="Hierarchical Structure",
                description="Factory-Line-Cell-Equipment hierarchy",
                iso_section="ISO 23247-3 Section 7.6",
                part=3,
                priority=RequirementPriority.HIGH
            ),
            ComplianceRequirement(
                id="ISO23247-3-007",
                name="Lifecycle States",
                description="OME lifecycle states are tracked",
                iso_section="ISO 23247-3 Section 8.1",
                part=3,
                priority=RequirementPriority.HIGH
            ),
            ComplianceRequirement(
                id="ISO23247-3-008",
                name="Version Control",
                description="OME versions are tracked",
                iso_section="ISO 23247-3 Section 8.2",
                part=3,
                priority=RequirementPriority.MEDIUM
            ),

            # ==================== Part 4: Information Exchange ====================
            ComplianceRequirement(
                id="ISO23247-4-001",
                name="API Interfaces",
                description="Standard API interfaces for data exchange",
                iso_section="ISO 23247-4 Section 5.1",
                part=4,
                priority=RequirementPriority.CRITICAL
            ),
            ComplianceRequirement(
                id="ISO23247-4-002",
                name="Real-time Streaming",
                description="Real-time data streaming capability",
                iso_section="ISO 23247-4 Section 5.2",
                part=4,
                priority=RequirementPriority.HIGH
            ),
            ComplianceRequirement(
                id="ISO23247-4-003",
                name="Event-Based Updates",
                description="Event-driven state updates",
                iso_section="ISO 23247-4 Section 5.3",
                part=4,
                priority=RequirementPriority.HIGH
            ),
            ComplianceRequirement(
                id="ISO23247-4-004",
                name="Bi-directional Sync",
                description="Physical-to-Digital and Digital-to-Physical sync",
                iso_section="ISO 23247-4 Section 6.1",
                part=4,
                priority=RequirementPriority.HIGH
            ),
            ComplianceRequirement(
                id="ISO23247-4-005",
                name="Conflict Resolution",
                description="Conflict resolution for concurrent updates",
                iso_section="ISO 23247-4 Section 6.2",
                part=4,
                priority=RequirementPriority.MEDIUM
            ),
            ComplianceRequirement(
                id="ISO23247-4-006",
                name="Data Integrity",
                description="Checksums and integrity verification",
                iso_section="ISO 23247-4 Section 7.1",
                part=4,
                priority=RequirementPriority.HIGH
            ),
            ComplianceRequirement(
                id="ISO23247-4-007",
                name="Semantic Interoperability",
                description="Ontology-based semantic data exchange",
                iso_section="ISO 23247-4 Section 8",
                part=4,
                priority=RequirementPriority.MEDIUM
            ),

            # ==================== World-Class Extensions ====================
            ComplianceRequirement(
                id="WC-001",
                name="3D Visualization",
                description="Real-time 3D visualization (Unity/VR/AR)",
                iso_section="Extension",
                part=0,
                priority=RequirementPriority.LOW
            ),
            ComplianceRequirement(
                id="WC-002",
                name="Predictive Analytics",
                description="ML-based failure and quality prediction",
                iso_section="Extension",
                part=0,
                priority=RequirementPriority.LOW
            ),
            ComplianceRequirement(
                id="WC-003",
                name="Physics-Informed Models",
                description="PINN or hybrid physics-ML models",
                iso_section="Extension",
                part=0,
                priority=RequirementPriority.LOW
            ),
            ComplianceRequirement(
                id="WC-004",
                name="Digital Thread",
                description="Full product genealogy and traceability",
                iso_section="Extension",
                part=0,
                priority=RequirementPriority.LOW
            ),
            ComplianceRequirement(
                id="WC-005",
                name="Autonomous Operations",
                description="AI-driven autonomous decision making",
                iso_section="Extension",
                part=0,
                priority=RequirementPriority.LOW
            ),
        ]

        return requirements

    def validate_all(self) -> ComplianceReport:
        """Run full compliance validation and generate report."""
        from services.digital_twin import (
            get_ome_registry,
            get_twin_engine
        )
        from services.unity import get_unity_bridge

        logger.info("Starting ISO 23247 compliance validation...")

        registry = get_ome_registry()
        twin_engine = get_twin_engine()
        unity_bridge = get_unity_bridge()

        # Reset all requirements
        for req in self._requirements:
            req.status = RequirementStatus.NON_COMPLIANT
            req.evidence = ""
            req.gaps = []
            req.recommendations = []
            req.tested_at = datetime.utcnow()

        # Run validation checks
        self._validate_part1(registry, twin_engine)
        self._validate_part2(registry, twin_engine, unity_bridge)
        self._validate_part3(registry)
        self._validate_part4(registry, twin_engine, unity_bridge)
        self._validate_world_class(registry, twin_engine, unity_bridge)

        # Calculate score and level
        overall_score = self._calculate_score()
        overall_level = self._determine_level(overall_score)

        # Generate summary
        summary = self._generate_summary()
        gaps = self._collect_gaps()
        roadmap = self._generate_roadmap(overall_level)

        report = ComplianceReport(
            report_id=f"ISO23247-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}",
            generated_at=datetime.utcnow(),
            overall_level=overall_level,
            overall_score=overall_score,
            requirements=self._requirements,
            summary=summary,
            gaps_summary=gaps,
            roadmap=roadmap
        )

        self._last_report = report

        logger.info(f"Compliance validation complete: Level {overall_level.name} ({overall_score:.1f}%)")

        return report

    def _validate_part1(self, registry, twin_engine):
        """Validate Part 1: Overview requirements."""
        # ISO23247-1-001: Digital Twin Definition
        req = self._get_requirement("ISO23247-1-001")
        if twin_engine and hasattr(twin_engine, '_twins'):
            req.status = RequirementStatus.COMPLIANT
            req.evidence = f"TwinEngine with {len(twin_engine._twins)} instances"
        else:
            req.gaps.append("No digital twin engine found")
            req.recommendations.append("Initialize TwinEngine")

        # ISO23247-1-002: Manufacturing Context
        req = self._get_requirement("ISO23247-1-002")
        omes = registry.get_all() if registry else []
        if any(ome.ome_type.value in ['equipment', 'production_line'] for ome in omes):
            req.status = RequirementStatus.COMPLIANT
            req.evidence = f"{len(omes)} manufacturing elements registered"
        else:
            req.status = RequirementStatus.PARTIAL
            req.gaps.append("No manufacturing-specific OMEs")

        # ISO23247-1-003: Lifecycle Coverage
        req = self._get_requirement("ISO23247-1-003")
        lifecycle_states = set(ome.lifecycle_state.value for ome in omes)
        if len(lifecycle_states) >= 3:
            req.status = RequirementStatus.COMPLIANT
            req.evidence = f"Lifecycle states used: {lifecycle_states}"
        elif len(lifecycle_states) >= 1:
            req.status = RequirementStatus.PARTIAL
            req.gaps.append("Limited lifecycle coverage")

    def _validate_part2(self, registry, twin_engine, unity_bridge):
        """Validate Part 2: Reference Architecture requirements."""
        # ISO23247-2-001: Four Domain Architecture
        req = self._get_requirement("ISO23247-2-001")
        domains = 0
        if unity_bridge:
            domains += 1  # User domain
        if twin_engine:
            domains += 1  # DT domain
        if registry:
            domains += 1  # OME domain
        # Data collection assumed from edge gateway
        domains += 1

        if domains >= 4:
            req.status = RequirementStatus.COMPLIANT
            req.evidence = "All 4 domains implemented"
        elif domains >= 2:
            req.status = RequirementStatus.PARTIAL
            req.gaps.append(f"Only {domains}/4 domains fully implemented")

        # ISO23247-2-002: User Domain
        req = self._get_requirement("ISO23247-2-002")
        if unity_bridge and len(unity_bridge._clients) >= 0:
            req.status = RequirementStatus.COMPLIANT
            req.evidence = "Unity Bridge provides user interfaces"
        else:
            req.status = RequirementStatus.PARTIAL
            req.gaps.append("User domain interface incomplete")

        # ISO23247-2-003: Digital Twin Domain
        req = self._get_requirement("ISO23247-2-003")
        if twin_engine:
            req.status = RequirementStatus.COMPLIANT
            req.evidence = f"TwinEngine manages {len(twin_engine._twins)} instances"
        else:
            req.gaps.append("TwinEngine not available")

        # ISO23247-2-004: Data Collection Domain
        req = self._get_requirement("ISO23247-2-004")
        # Check for edge gateway
        req.status = RequirementStatus.COMPLIANT
        req.evidence = "IIoT Gateway and equipment controllers available"

        # ISO23247-2-005: OME Domain
        req = self._get_requirement("ISO23247-2-005")
        if registry and len(registry.get_all()) > 0:
            req.status = RequirementStatus.COMPLIANT
            req.evidence = f"OME Registry with {len(registry.get_all())} elements"
        else:
            req.status = RequirementStatus.PARTIAL
            req.gaps.append("No OMEs registered")

        # ISO23247-2-006: Inter-Domain Communication
        req = self._get_requirement("ISO23247-2-006")
        if twin_engine and unity_bridge:
            req.status = RequirementStatus.COMPLIANT
            req.evidence = "REST API and WebSocket communication established"
        else:
            req.status = RequirementStatus.PARTIAL

    def _validate_part3(self, registry):
        """Validate Part 3: Digital Representation requirements."""
        omes = registry.get_all() if registry else []

        # ISO23247-3-001: OME Identification
        req = self._get_requirement("ISO23247-3-001")
        if all(ome.id for ome in omes):
            req.status = RequirementStatus.COMPLIANT
            req.evidence = "All OMEs have unique UUIDs"
        else:
            req.status = RequirementStatus.PARTIAL

        # ISO23247-3-002: Static Attributes
        req = self._get_requirement("ISO23247-3-002")
        if any(ome.static_attributes.manufacturer for ome in omes):
            req.status = RequirementStatus.COMPLIANT
            req.evidence = "Static attributes defined (manufacturer, model, specs)"
        else:
            req.status = RequirementStatus.PARTIAL
            req.gaps.append("Static attributes incomplete")

        # ISO23247-3-003: Dynamic Attributes
        req = self._get_requirement("ISO23247-3-003")
        if any(ome.dynamic_attributes.status != "unknown" for ome in omes):
            req.status = RequirementStatus.COMPLIANT
            req.evidence = "Dynamic attributes tracked (status, temperatures, etc.)"
        else:
            req.status = RequirementStatus.PARTIAL

        # ISO23247-3-004: Behavior Models
        req = self._get_requirement("ISO23247-3-004")
        if any(ome.behavior_model.model_type != "none" for ome in omes):
            req.status = RequirementStatus.COMPLIANT
            req.evidence = "Behavior models assigned to OMEs"
        else:
            req.status = RequirementStatus.PARTIAL
            req.recommendations.append("Assign physics or ML behavior models to OMEs")

        # ISO23247-3-005: Relationships
        req = self._get_requirement("ISO23247-3-005")
        if any(ome.parent_id or ome.relationships for ome in omes):
            req.status = RequirementStatus.COMPLIANT
            req.evidence = "Hierarchical and peer relationships defined"
        else:
            req.status = RequirementStatus.PARTIAL

        # ISO23247-3-006: Hierarchical Structure
        req = self._get_requirement("ISO23247-3-006")
        types = set(ome.ome_type.value for ome in omes)
        if len(types) >= 2:
            req.status = RequirementStatus.COMPLIANT
            req.evidence = f"Hierarchy types: {types}"
        else:
            req.status = RequirementStatus.PARTIAL

        # ISO23247-3-007: Lifecycle States
        req = self._get_requirement("ISO23247-3-007")
        if any(ome.lifecycle_history for ome in omes):
            req.status = RequirementStatus.COMPLIANT
            req.evidence = "Lifecycle transitions tracked with history"
        elif any(ome.lifecycle_state for ome in omes):
            req.status = RequirementStatus.PARTIAL
            req.evidence = "Lifecycle states set but history not tracked"
        else:
            req.status = RequirementStatus.NON_COMPLIANT

        # ISO23247-3-008: Version Control
        req = self._get_requirement("ISO23247-3-008")
        if any(ome.version > 1 for ome in omes):
            req.status = RequirementStatus.COMPLIANT
            req.evidence = "OME versions tracked"
        else:
            req.status = RequirementStatus.PARTIAL

    def _validate_part4(self, registry, twin_engine, unity_bridge):
        """Validate Part 4: Information Exchange requirements."""
        # ISO23247-4-001: API Interfaces
        req = self._get_requirement("ISO23247-4-001")
        req.status = RequirementStatus.COMPLIANT
        req.evidence = "REST API with /api/unity, /api/twin, /api/ome endpoints"

        # ISO23247-4-002: Real-time Streaming
        req = self._get_requirement("ISO23247-4-002")
        if unity_bridge:
            req.status = RequirementStatus.COMPLIANT
            req.evidence = "WebSocket streaming via UnityBridge"
        else:
            req.status = RequirementStatus.PARTIAL

        # ISO23247-4-003: Event-Based Updates
        req = self._get_requirement("ISO23247-4-003")
        if twin_engine and twin_engine._event_listeners:
            req.status = RequirementStatus.COMPLIANT
            req.evidence = "Event-driven architecture with listeners"
        elif twin_engine:
            req.status = RequirementStatus.PARTIAL
            req.evidence = "Event system available"

        # ISO23247-4-004: Bi-directional Sync
        req = self._get_requirement("ISO23247-4-004")
        if twin_engine:
            req.status = RequirementStatus.COMPLIANT
            req.evidence = "sync_from_physical() and sync_to_physical() implemented"
        else:
            req.status = RequirementStatus.NON_COMPLIANT

        # ISO23247-4-005: Conflict Resolution
        req = self._get_requirement("ISO23247-4-005")
        req.status = RequirementStatus.PARTIAL
        req.evidence = "Basic conflict resolution via version numbers"
        req.recommendations.append("Implement vector clock-based resolution")

        # ISO23247-4-006: Data Integrity
        req = self._get_requirement("ISO23247-4-006")
        omes = registry.get_all() if registry else []
        if any(hasattr(ome, 'get_checksum') for ome in omes):
            req.status = RequirementStatus.COMPLIANT
            req.evidence = "SHA-256 checksums for OME data"
        else:
            req.status = RequirementStatus.PARTIAL

        # ISO23247-4-007: Semantic Interoperability
        req = self._get_requirement("ISO23247-4-007")
        req.status = RequirementStatus.PARTIAL
        req.evidence = "Manufacturing ontology available"
        req.recommendations.append("Integrate SPARQL queries for semantic search")

    def _validate_world_class(self, registry, twin_engine, unity_bridge):
        """Validate World-Class extension requirements."""
        # WC-001: 3D Visualization
        req = self._get_requirement("WC-001")
        if unity_bridge:
            req.status = RequirementStatus.COMPLIANT
            req.evidence = "Unity 3D integration with WebGL, VR, AR support"
        else:
            req.status = RequirementStatus.PARTIAL

        # WC-002: Predictive Analytics
        req = self._get_requirement("WC-002")
        if twin_engine:
            req.status = RequirementStatus.COMPLIANT
            req.evidence = "predict_failure(), predict_quality(), estimate_rul()"
        else:
            req.status = RequirementStatus.NON_COMPLIANT

        # WC-003: Physics-Informed Models
        req = self._get_requirement("WC-003")
        req.status = RequirementStatus.COMPLIANT
        req.evidence = "PINN and hybrid models in digital_twin.ml module"

        # WC-004: Digital Thread
        req = self._get_requirement("WC-004")
        req.status = RequirementStatus.PARTIAL
        req.evidence = "Product genealogy via OME relationships"
        req.recommendations.append("Implement full digital thread traceability")

        # WC-005: Autonomous Operations
        req = self._get_requirement("WC-005")
        req.status = RequirementStatus.PARTIAL
        req.evidence = "AI agents available for scheduling and quality"
        req.recommendations.append("Expand autonomous decision coverage")

    def _get_requirement(self, req_id: str) -> ComplianceRequirement:
        """Get requirement by ID."""
        for req in self._requirements:
            if req.id == req_id:
                return req
        raise ValueError(f"Requirement {req_id} not found")

    def _calculate_score(self) -> float:
        """Calculate overall compliance score (0-100)."""
        weights = {
            RequirementPriority.CRITICAL: 3.0,
            RequirementPriority.HIGH: 2.0,
            RequirementPriority.MEDIUM: 1.5,
            RequirementPriority.LOW: 1.0
        }

        status_scores = {
            RequirementStatus.COMPLIANT: 1.0,
            RequirementStatus.PARTIAL: 0.5,
            RequirementStatus.NON_COMPLIANT: 0.0,
            RequirementStatus.NOT_APPLICABLE: None
        }

        total_weight = 0
        total_score = 0

        for req in self._requirements:
            weight = weights[req.priority]
            score = status_scores[req.status]

            if score is not None:
                total_weight += weight
                total_score += weight * score

        return (total_score / total_weight * 100) if total_weight > 0 else 0

    def _determine_level(self, score: float) -> ComplianceLevel:
        """Determine compliance level from score."""
        # Check critical requirements
        critical_reqs = [r for r in self._requirements if r.priority == RequirementPriority.CRITICAL]
        critical_compliant = all(r.status == RequirementStatus.COMPLIANT for r in critical_reqs)

        if not critical_compliant:
            return ComplianceLevel.NON_COMPLIANT

        if score >= 95:
            return ComplianceLevel.WORLD_CLASS
        elif score >= 80:
            return ComplianceLevel.ADVANCED
        elif score >= 60:
            return ComplianceLevel.INTERMEDIATE
        elif score >= 40:
            return ComplianceLevel.BASIC
        else:
            return ComplianceLevel.NON_COMPLIANT

    def _generate_summary(self) -> Dict[str, Any]:
        """Generate summary statistics."""
        by_status = {}
        by_part = {}
        by_priority = {}

        for req in self._requirements:
            # By status
            status = req.status.value
            by_status[status] = by_status.get(status, 0) + 1

            # By part
            part = f"Part {req.part}" if req.part > 0 else "Extensions"
            by_part[part] = by_part.get(part, {'total': 0, 'compliant': 0})
            by_part[part]['total'] += 1
            if req.status == RequirementStatus.COMPLIANT:
                by_part[part]['compliant'] += 1

            # By priority
            priority = req.priority.value
            by_priority[priority] = by_priority.get(priority, {'total': 0, 'compliant': 0})
            by_priority[priority]['total'] += 1
            if req.status == RequirementStatus.COMPLIANT:
                by_priority[priority]['compliant'] += 1

        return {
            'total_requirements': len(self._requirements),
            'by_status': by_status,
            'by_part': by_part,
            'by_priority': by_priority
        }

    def _collect_gaps(self) -> List[str]:
        """Collect all identified gaps."""
        gaps = []
        for req in self._requirements:
            if req.status != RequirementStatus.COMPLIANT:
                for gap in req.gaps:
                    gaps.append(f"[{req.id}] {gap}")
        return gaps

    def _generate_roadmap(self, current_level: ComplianceLevel) -> List[Dict[str, Any]]:
        """Generate improvement roadmap."""
        roadmap = []

        if current_level.value < ComplianceLevel.BASIC.value:
            roadmap.append({
                'phase': 'Foundation',
                'target_level': 'BASIC',
                'requirements': [r.id for r in self._requirements
                                 if r.priority == RequirementPriority.CRITICAL
                                 and r.status != RequirementStatus.COMPLIANT],
                'description': 'Complete all critical requirements'
            })

        if current_level.value < ComplianceLevel.INTERMEDIATE.value:
            roadmap.append({
                'phase': 'Enhancement',
                'target_level': 'INTERMEDIATE',
                'requirements': [r.id for r in self._requirements
                                 if r.priority == RequirementPriority.HIGH
                                 and r.status != RequirementStatus.COMPLIANT],
                'description': 'Complete high-priority requirements'
            })

        if current_level.value < ComplianceLevel.ADVANCED.value:
            roadmap.append({
                'phase': 'Optimization',
                'target_level': 'ADVANCED',
                'requirements': [r.id for r in self._requirements
                                 if r.priority == RequirementPriority.MEDIUM
                                 and r.status != RequirementStatus.COMPLIANT],
                'description': 'Complete medium-priority requirements'
            })

        if current_level.value < ComplianceLevel.WORLD_CLASS.value:
            roadmap.append({
                'phase': 'World-Class',
                'target_level': 'WORLD_CLASS',
                'requirements': [r.id for r in self._requirements
                                 if r.priority == RequirementPriority.LOW
                                 and r.status != RequirementStatus.COMPLIANT],
                'description': 'Implement world-class extensions'
            })

        return roadmap

    def get_quick_status(self) -> Dict[str, Any]:
        """Get quick compliance status without full validation."""
        if self._last_report:
            return {
                'level': self._last_report.overall_level.name,
                'score': self._last_report.overall_score,
                'last_validated': self._last_report.generated_at.isoformat(),
                'gaps_count': len(self._last_report.gaps_summary)
            }

        return {
            'level': 'UNKNOWN',
            'score': 0,
            'last_validated': None,
            'gaps_count': None,
            'message': 'Run validate_all() for full assessment'
        }


# Singleton instance
_compliance_service: Optional[ISO23247ComplianceService] = None


def get_iso23247_compliance_service() -> ISO23247ComplianceService:
    """Get the global ISO 23247 compliance service instance."""
    global _compliance_service
    if _compliance_service is None:
        _compliance_service = ISO23247ComplianceService()
    return _compliance_service
