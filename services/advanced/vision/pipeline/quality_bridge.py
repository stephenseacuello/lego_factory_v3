"""
Quality Bridge - Vision to Quality Agent Integration

LegoMCP World-Class Manufacturing System v6.0
Phase 26: Vision AI & ML Training

Provides:
- Vision event transformation
- Quality agent integration
- Defect-to-quality mapping
- Alert generation
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Any, Callable
from enum import Enum
import threading
import uuid
from collections import defaultdict


class QualityEventType(Enum):
    """Quality event types from vision."""
    DEFECT_DETECTED = "defect_detected"
    QUALITY_ASSESSMENT = "quality_assessment"
    INSPECTION_COMPLETE = "inspection_complete"
    SPC_VIOLATION = "spc_violation"
    TREND_ALERT = "trend_alert"
    PASS = "pass"
    FAIL = "fail"


class DefectSeverity(Enum):
    """Defect severity levels."""
    COSMETIC = 1
    MINOR = 2
    MAJOR = 3
    CRITICAL = 4


class ActionType(Enum):
    """Recommended action types."""
    NONE = "none"
    MONITOR = "monitor"
    INSPECT = "inspect"
    ADJUST = "adjust"
    STOP = "stop"
    REWORK = "rework"
    SCRAP = "scrap"


@dataclass
class QualityBridgeConfig:
    """Quality bridge configuration."""
    enable_auto_alerts: bool = True
    defect_threshold: int = 3  # Max defects before alert
    quality_threshold: float = 0.7  # Min quality score
    severity_mapping: Dict[str, DefectSeverity] = field(default_factory=dict)
    action_mapping: Dict[str, ActionType] = field(default_factory=dict)


@dataclass
class VisionQualityEvent:
    """Quality event from vision system."""
    event_id: str
    event_type: QualityEventType
    source: str  # "vision_pipeline"
    entity_id: str
    timestamp: datetime
    quality_score: float
    defect_count: int
    defects: List[Dict[str, Any]]
    measurements: Dict[str, float]
    recommendations: List[str]
    severity: DefectSeverity
    action: ActionType
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class QualityDecision:
    """Quality decision from agent."""
    decision_id: str
    event_id: str
    decision: str  # "pass", "fail", "hold"
    confidence: float
    reasoning: str
    actions: List[str]
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class DefectMapping:
    """Mapping from vision defect to quality impact."""
    defect_type: str
    severity: DefectSeverity
    quality_impact: float
    action: ActionType
    description: str


class QualityBridge:
    """
    Bridge between Vision Pipeline and Quality Agent.

    Features:
    - Event transformation
    - Severity mapping
    - Action recommendation
    - Quality agent integration
    """

    def __init__(self, config: Optional[QualityBridgeConfig] = None):
        """
        Initialize quality bridge.

        Args:
            config: Bridge configuration
        """
        self.config = config or QualityBridgeConfig()

        # Defect mappings
        self._defect_mappings: Dict[str, DefectMapping] = {}
        self._init_default_mappings()

        # Event handlers
        self._event_handlers: List[Callable[[VisionQualityEvent], None]] = []

        # Event history
        self._event_history: List[VisionQualityEvent] = []
        self._decision_history: List[QualityDecision] = []

        # Statistics
        self._stats = {
            "events_processed": 0,
            "defects_reported": 0,
            "alerts_generated": 0,
            "decisions_made": 0,
        }

        # Thread safety
        self._lock = threading.RLock()

    def transform_pipeline_result(
        self,
        pipeline_result: Dict[str, Any],
        entity_id: str
    ) -> VisionQualityEvent:
        """
        Transform pipeline result to quality event.

        Args:
            pipeline_result: Result from vision pipeline
            entity_id: Entity identifier

        Returns:
            Quality event
        """
        with self._lock:
            self._stats["events_processed"] += 1

            detections = pipeline_result.get("detections", [])
            quality_score = pipeline_result.get("quality_score", 1.0)
            defect_count = pipeline_result.get("defect_count", 0)
            recommendations = pipeline_result.get("recommendations", [])

            # Extract defects
            defects = self._extract_defects(detections)
            self._stats["defects_reported"] += len(defects)

            # Calculate severity
            severity = self._calculate_severity(defects)

            # Determine action
            action = self._determine_action(defects, quality_score)

            # Determine event type
            if defect_count > 0:
                event_type = QualityEventType.DEFECT_DETECTED
            elif quality_score >= self.config.quality_threshold:
                event_type = QualityEventType.PASS
            else:
                event_type = QualityEventType.FAIL

            # Extract measurements
            measurements = self._extract_measurements(pipeline_result)

            event = VisionQualityEvent(
                event_id=str(uuid.uuid4()),
                event_type=event_type,
                source="vision_pipeline",
                entity_id=entity_id,
                timestamp=datetime.utcnow(),
                quality_score=quality_score,
                defect_count=defect_count,
                defects=defects,
                measurements=measurements,
                recommendations=recommendations,
                severity=severity,
                action=action,
                metadata={
                    "pipeline_id": pipeline_result.get("pipeline_id"),
                    "quality_grade": pipeline_result.get("metadata", {}).get("quality_grade"),
                },
            )

            # Store in history
            self._event_history.append(event)

            # Notify handlers
            self._notify_handlers(event)

            # Check for alert
            if self.config.enable_auto_alerts:
                self._check_alerts(event)

            return event

    def register_handler(
        self,
        handler: Callable[[VisionQualityEvent], None]
    ):
        """
        Register event handler.

        Args:
            handler: Handler function
        """
        self._event_handlers.append(handler)

    def make_decision(
        self,
        event: VisionQualityEvent
    ) -> QualityDecision:
        """
        Make quality decision based on event.

        Args:
            event: Quality event

        Returns:
            Quality decision
        """
        with self._lock:
            self._stats["decisions_made"] += 1

            # Decision logic
            if event.quality_score >= 0.9 and event.defect_count == 0:
                decision = "pass"
                confidence = 0.95
                reasoning = "High quality score with no defects"
                actions = []

            elif event.quality_score < self.config.quality_threshold:
                decision = "fail"
                confidence = 0.9
                reasoning = f"Quality score {event.quality_score:.2f} below threshold {self.config.quality_threshold}"
                actions = self._get_failure_actions(event)

            elif event.defect_count > self.config.defect_threshold:
                decision = "fail"
                confidence = 0.85
                reasoning = f"Defect count {event.defect_count} exceeds threshold {self.config.defect_threshold}"
                actions = self._get_failure_actions(event)

            elif event.severity == DefectSeverity.CRITICAL:
                decision = "fail"
                confidence = 0.95
                reasoning = "Critical defect detected"
                actions = ["immediate_stop", "supervisor_review"]

            else:
                decision = "hold"
                confidence = 0.7
                reasoning = "Manual review required"
                actions = ["manual_inspection"]

            quality_decision = QualityDecision(
                decision_id=str(uuid.uuid4()),
                event_id=event.event_id,
                decision=decision,
                confidence=confidence,
                reasoning=reasoning,
                actions=actions,
            )

            self._decision_history.append(quality_decision)

            return quality_decision

    def get_defect_mapping(self, defect_type: str) -> Optional[DefectMapping]:
        """Get mapping for a defect type."""
        return self._defect_mappings.get(defect_type)

    def add_defect_mapping(self, mapping: DefectMapping):
        """Add or update defect mapping."""
        self._defect_mappings[mapping.defect_type] = mapping

    def get_event_history(
        self,
        entity_id: Optional[str] = None,
        event_type: Optional[QualityEventType] = None,
        limit: int = 100
    ) -> List[VisionQualityEvent]:
        """Get event history."""
        events = self._event_history

        if entity_id:
            events = [e for e in events if e.entity_id == entity_id]

        if event_type:
            events = [e for e in events if e.event_type == event_type]

        return events[-limit:]

    def get_decision_history(
        self,
        limit: int = 100
    ) -> List[QualityDecision]:
        """Get decision history."""
        return self._decision_history[-limit:]

    def get_statistics(self) -> Dict[str, Any]:
        """Get bridge statistics."""
        return {
            **self._stats,
            "event_history_size": len(self._event_history),
            "decision_history_size": len(self._decision_history),
            "defect_mappings": len(self._defect_mappings),
            "registered_handlers": len(self._event_handlers),
        }

    def get_quality_summary(
        self,
        entity_id: str,
        hours: int = 24
    ) -> Dict[str, Any]:
        """
        Get quality summary for an entity.

        Args:
            entity_id: Entity identifier
            hours: Hours to summarize

        Returns:
            Quality summary
        """
        from datetime import timedelta

        cutoff = datetime.utcnow() - timedelta(hours=hours)

        events = [
            e for e in self._event_history
            if e.entity_id == entity_id and e.timestamp > cutoff
        ]

        if not events:
            return {"entity_id": entity_id, "no_data": True}

        total = len(events)
        passed = sum(1 for e in events if e.event_type == QualityEventType.PASS)
        failed = sum(1 for e in events if e.event_type == QualityEventType.FAIL)
        defect_events = sum(1 for e in events if e.event_type == QualityEventType.DEFECT_DETECTED)

        avg_quality = sum(e.quality_score for e in events) / total
        total_defects = sum(e.defect_count for e in events)

        return {
            "entity_id": entity_id,
            "period_hours": hours,
            "total_inspections": total,
            "passed": passed,
            "failed": failed,
            "defect_events": defect_events,
            "pass_rate": passed / total if total > 0 else 0,
            "average_quality_score": avg_quality,
            "total_defects": total_defects,
            "defects_per_inspection": total_defects / total if total > 0 else 0,
        }

    def _init_default_mappings(self):
        """Initialize default defect mappings."""
        mappings = [
            DefectMapping("layer_shift", DefectSeverity.MAJOR, 0.3, ActionType.STOP, "Z-axis layer misalignment"),
            DefectMapping("stringing", DefectSeverity.MINOR, 0.1, ActionType.MONITOR, "Material stringing between parts"),
            DefectMapping("warping", DefectSeverity.MAJOR, 0.25, ActionType.ADJUST, "Part warping from thermal stress"),
            DefectMapping("under_extrusion", DefectSeverity.MAJOR, 0.2, ActionType.ADJUST, "Insufficient material extrusion"),
            DefectMapping("over_extrusion", DefectSeverity.MINOR, 0.15, ActionType.ADJUST, "Excessive material extrusion"),
            DefectMapping("z_wobble", DefectSeverity.MAJOR, 0.2, ActionType.STOP, "Z-axis wobble pattern"),
            DefectMapping("blob", DefectSeverity.MINOR, 0.1, ActionType.MONITOR, "Material blob on surface"),
            DefectMapping("gap", DefectSeverity.MAJOR, 0.25, ActionType.STOP, "Gap in layer or between layers"),
        ]

        for m in mappings:
            self._defect_mappings[m.defect_type] = m

    def _extract_defects(
        self,
        detections: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Extract defects from detections."""
        defects = []

        defect_classes = {
            "layer_shift", "stringing", "warping",
            "under_extrusion", "over_extrusion", "z_wobble",
            "blob", "gap"
        }

        for det in detections:
            cls = det.get("class", "")
            if cls in defect_classes:
                mapping = self._defect_mappings.get(cls)

                defects.append({
                    "type": cls,
                    "confidence": det.get("confidence", 0),
                    "bbox": det.get("bbox"),
                    "severity": mapping.severity.value if mapping else 2,
                    "quality_impact": mapping.quality_impact if mapping else 0.1,
                    "description": mapping.description if mapping else "",
                })

        return defects

    def _extract_measurements(
        self,
        pipeline_result: Dict[str, Any]
    ) -> Dict[str, float]:
        """Extract measurements from pipeline result."""
        measurements = {}

        # Extract known measurements
        for key in ["layer_quality", "surface_quality", "quality_score"]:
            if key in pipeline_result:
                measurements[key] = pipeline_result[key]

        # From metadata
        metadata = pipeline_result.get("metadata", {})
        for key in ["layer_height", "width", "dimension_accuracy"]:
            if key in metadata:
                measurements[key] = metadata[key]

        return measurements

    def _calculate_severity(
        self,
        defects: List[Dict[str, Any]]
    ) -> DefectSeverity:
        """Calculate overall severity from defects."""
        if not defects:
            return DefectSeverity.COSMETIC

        max_severity = max(d.get("severity", 1) for d in defects)

        if max_severity >= 4:
            return DefectSeverity.CRITICAL
        elif max_severity >= 3:
            return DefectSeverity.MAJOR
        elif max_severity >= 2:
            return DefectSeverity.MINOR
        else:
            return DefectSeverity.COSMETIC

    def _determine_action(
        self,
        defects: List[Dict[str, Any]],
        quality_score: float
    ) -> ActionType:
        """Determine recommended action."""
        if not defects and quality_score >= 0.9:
            return ActionType.NONE

        # Check for critical defects
        critical = any(d.get("severity", 0) >= 4 for d in defects)
        if critical:
            return ActionType.STOP

        # Check for major defects
        major = any(d.get("severity", 0) >= 3 for d in defects)
        if major or quality_score < self.config.quality_threshold:
            return ActionType.INSPECT

        # Minor defects
        if defects:
            return ActionType.MONITOR

        return ActionType.NONE

    def _get_failure_actions(
        self,
        event: VisionQualityEvent
    ) -> List[str]:
        """Get actions for failure."""
        actions = []

        if event.severity == DefectSeverity.CRITICAL:
            actions.extend(["stop_production", "supervisor_alert"])
        elif event.severity == DefectSeverity.MAJOR:
            actions.extend(["pause_production", "inspection"])

        # Defect-specific actions
        for defect in event.defects:
            dtype = defect.get("type", "")
            if dtype == "layer_shift":
                actions.append("check_z_axis")
            elif dtype == "warping":
                actions.append("check_bed_temperature")
            elif dtype in ["under_extrusion", "over_extrusion"]:
                actions.append("check_flow_rate")

        return list(set(actions))

    def _notify_handlers(self, event: VisionQualityEvent):
        """Notify registered handlers."""
        for handler in self._event_handlers:
            try:
                handler(event)
            except Exception:
                pass

    def _check_alerts(self, event: VisionQualityEvent):
        """Check if alert should be generated."""
        if event.severity in [DefectSeverity.CRITICAL, DefectSeverity.MAJOR]:
            self._stats["alerts_generated"] += 1

        if event.defect_count > self.config.defect_threshold:
            self._stats["alerts_generated"] += 1


# Singleton instance
_quality_bridge: Optional[QualityBridge] = None


def get_quality_bridge() -> QualityBridge:
    """Get or create the quality bridge instance."""
    global _quality_bridge
    if _quality_bridge is None:
        _quality_bridge = QualityBridge()
    return _quality_bridge
