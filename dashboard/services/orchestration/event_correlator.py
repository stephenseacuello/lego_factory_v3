"""
Event Correlator Service
========================

Correlates events across multiple systems to:
- Identify root causes
- Detect patterns
- Trigger coordinated responses
- Build event timelines

Author: LEGO MCP Engineering Team
Version: 8.0.0
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set
import threading
import uuid
from collections import defaultdict

logger = logging.getLogger(__name__)


class EventType(Enum):
    """Types of events"""
    MACHINE = "machine"
    QUALITY = "quality"
    SCHEDULING = "scheduling"
    INVENTORY = "inventory"
    MAINTENANCE = "maintenance"
    SAFETY = "safety"
    AI = "ai"
    SYSTEM = "system"


class EventSeverity(Enum):
    """Event severity levels"""
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class Event:
    """Individual event"""
    id: str
    event_type: EventType
    severity: EventSeverity
    source: str
    message: str
    timestamp: datetime
    entity_type: str = ""
    entity_id: str = ""
    data: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    correlation_id: Optional[str] = None
    causation_id: Optional[str] = None
    trace_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "event_type": self.event_type.value,
            "severity": self.severity.value,
            "source": self.source,
            "message": self.message,
            "timestamp": self.timestamp.isoformat(),
            "entity_type": self.entity_type,
            "entity_id": self.entity_id,
            "data": self.data,
            "tags": self.tags,
            "correlation_id": self.correlation_id,
            "causation_id": self.causation_id,
            "trace_id": self.trace_id
        }


@dataclass
class CorrelatedEvent:
    """Group of correlated events"""
    id: str
    root_event_id: str
    event_ids: List[str]
    correlation_type: str  # causal, temporal, spatial, semantic
    confidence: float
    created_at: datetime
    analysis: Dict[str, Any]
    root_cause: Optional[str] = None
    impact_assessment: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "root_event_id": self.root_event_id,
            "event_ids": self.event_ids,
            "correlation_type": self.correlation_type,
            "confidence": self.confidence,
            "created_at": self.created_at.isoformat(),
            "analysis": self.analysis,
            "root_cause": self.root_cause,
            "impact_assessment": self.impact_assessment
        }


@dataclass
class CorrelationRule:
    """Rule for correlating events"""
    id: str
    name: str
    description: str
    event_types: List[EventType]
    entity_match: bool  # Require same entity
    time_window_seconds: float
    min_events: int
    conditions: Dict[str, Any]
    action: str  # What to do when correlation found
    enabled: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "event_types": [et.value for et in self.event_types],
            "entity_match": self.entity_match,
            "time_window_seconds": self.time_window_seconds,
            "min_events": self.min_events,
            "conditions": self.conditions,
            "action": self.action,
            "enabled": self.enabled
        }


class EventCorrelator:
    """
    Correlates events across systems to identify patterns and root causes.

    Uses multiple correlation strategies:
    - Temporal: Events within a time window
    - Causal: Events that cause other events
    - Spatial: Events from related entities
    - Semantic: Events with similar content
    """

    # Default correlation rules
    DEFAULT_RULES = [
        {
            "id": "quality_cascade",
            "name": "Quality Cascade Detection",
            "description": "Detect quality issues cascading across stations",
            "event_types": [EventType.QUALITY],
            "entity_match": False,
            "time_window_seconds": 300,
            "min_events": 3,
            "conditions": {"severity": ["warning", "error"]},
            "action": "alert"
        },
        {
            "id": "machine_quality_correlation",
            "name": "Machine-Quality Correlation",
            "description": "Correlate machine issues with quality defects",
            "event_types": [EventType.MACHINE, EventType.QUALITY],
            "entity_match": True,
            "time_window_seconds": 600,
            "min_events": 2,
            "conditions": {},
            "action": "root_cause_analysis"
        },
        {
            "id": "maintenance_prediction",
            "name": "Maintenance Prediction Pattern",
            "description": "Detect patterns indicating need for maintenance",
            "event_types": [EventType.MACHINE, EventType.MAINTENANCE],
            "entity_match": True,
            "time_window_seconds": 3600,
            "min_events": 5,
            "conditions": {"severity": ["warning"]},
            "action": "predict_maintenance"
        },
        {
            "id": "safety_escalation",
            "name": "Safety Event Escalation",
            "description": "Detect escalating safety concerns",
            "event_types": [EventType.SAFETY],
            "entity_match": False,
            "time_window_seconds": 1800,
            "min_events": 2,
            "conditions": {},
            "action": "immediate_alert"
        }
    ]

    def __init__(
        self,
        correlation_window: float = 300.0,
        max_events: int = 10000
    ):
        """
        Initialize correlator.

        Args:
            correlation_window: Default time window for correlation (seconds)
            max_events: Maximum events to keep in memory
        """
        self._events: Dict[str, Event] = {}
        self._correlations: Dict[str, CorrelatedEvent] = {}
        self._rules: Dict[str, CorrelationRule] = {}
        self._correlation_window = correlation_window
        self._max_events = max_events
        self._lock = threading.RLock()
        self._callbacks: List[Callable[[CorrelatedEvent], None]] = []

        # Indexes for fast lookup
        self._by_type: Dict[EventType, Set[str]] = defaultdict(set)
        self._by_entity: Dict[str, Set[str]] = defaultdict(set)
        self._by_time: List[str] = []  # Sorted by timestamp

        # Load default rules
        self._load_default_rules()

    def _load_default_rules(self):
        """Load default correlation rules"""
        for rule_def in self.DEFAULT_RULES:
            rule = CorrelationRule(
                id=rule_def["id"],
                name=rule_def["name"],
                description=rule_def["description"],
                event_types=[EventType(et) if isinstance(et, str) else et
                            for et in rule_def["event_types"]],
                entity_match=rule_def["entity_match"],
                time_window_seconds=rule_def["time_window_seconds"],
                min_events=rule_def["min_events"],
                conditions=rule_def["conditions"],
                action=rule_def["action"]
            )
            self._rules[rule.id] = rule

    def add_event(self, event: Event) -> List[CorrelatedEvent]:
        """
        Add an event and check for correlations.

        Args:
            event: Event to add

        Returns:
            List of new correlations found
        """
        with self._lock:
            # Store event
            self._events[event.id] = event
            self._by_type[event.event_type].add(event.id)

            if event.entity_id:
                entity_key = f"{event.entity_type}:{event.entity_id}"
                self._by_entity[entity_key].add(event.id)

            self._by_time.append(event.id)

            # Trim old events
            self._trim_old_events()

            # Check for correlations
            correlations = self._check_correlations(event)

            # Notify callbacks
            for correlation in correlations:
                self._notify_correlation(correlation)

            return correlations

    def create_event(
        self,
        event_type: EventType,
        severity: EventSeverity,
        source: str,
        message: str,
        entity_type: str = "",
        entity_id: str = "",
        data: Dict[str, Any] = None,
        tags: List[str] = None,
        correlation_id: str = None,
        causation_id: str = None,
        trace_id: str = None
    ) -> Event:
        """
        Create and add a new event.

        Args:
            event_type: Type of event
            severity: Severity level
            source: Event source
            message: Event message
            entity_type: Entity type
            entity_id: Entity ID
            data: Additional data
            tags: Event tags
            correlation_id: Correlation ID
            causation_id: Causation ID
            trace_id: Trace ID

        Returns:
            Created Event
        """
        event = Event(
            id=str(uuid.uuid4()),
            event_type=event_type,
            severity=severity,
            source=source,
            message=message,
            timestamp=datetime.now(),
            entity_type=entity_type,
            entity_id=entity_id,
            data=data or {},
            tags=tags or [],
            correlation_id=correlation_id,
            causation_id=causation_id,
            trace_id=trace_id
        )

        self.add_event(event)
        return event

    def _check_correlations(self, new_event: Event) -> List[CorrelatedEvent]:
        """Check if new event creates correlations"""
        correlations = []

        for rule in self._rules.values():
            if not rule.enabled:
                continue

            if new_event.event_type not in rule.event_types:
                continue

            correlation = self._evaluate_rule(new_event, rule)
            if correlation:
                correlations.append(correlation)

        return correlations

    def _evaluate_rule(
        self,
        trigger_event: Event,
        rule: CorrelationRule
    ) -> Optional[CorrelatedEvent]:
        """Evaluate a correlation rule against trigger event"""
        cutoff = trigger_event.timestamp - timedelta(seconds=rule.time_window_seconds)

        # Find candidate events
        candidates = []
        for event_type in rule.event_types:
            event_ids = self._by_type.get(event_type, set())
            for event_id in event_ids:
                if event_id == trigger_event.id:
                    continue

                event = self._events.get(event_id)
                if not event:
                    continue

                if event.timestamp < cutoff:
                    continue

                # Check entity match if required
                if rule.entity_match:
                    if (event.entity_type != trigger_event.entity_type or
                        event.entity_id != trigger_event.entity_id):
                        continue

                # Check conditions
                if self._check_conditions(event, rule.conditions):
                    candidates.append(event)

        # Check minimum events
        if len(candidates) + 1 < rule.min_events:
            return None

        # Create correlation
        event_ids = [e.id for e in candidates] + [trigger_event.id]
        root_event = min(candidates + [trigger_event], key=lambda e: e.timestamp)

        analysis = self._analyze_correlation(candidates + [trigger_event], rule)

        correlation = CorrelatedEvent(
            id=str(uuid.uuid4()),
            root_event_id=root_event.id,
            event_ids=event_ids,
            correlation_type=self._determine_correlation_type(rule),
            confidence=self._calculate_confidence(candidates + [trigger_event], rule),
            created_at=datetime.now(),
            analysis=analysis,
            root_cause=analysis.get("root_cause"),
            impact_assessment=analysis.get("impact")
        )

        self._correlations[correlation.id] = correlation

        # Execute rule action
        self._execute_action(correlation, rule)

        return correlation

    def _check_conditions(self, event: Event, conditions: Dict[str, Any]) -> bool:
        """Check if event matches conditions"""
        for key, expected in conditions.items():
            if key == "severity":
                if event.severity.value not in expected:
                    return False
            elif key == "tags":
                if not any(t in event.tags for t in expected):
                    return False
            elif key in event.data:
                if event.data[key] != expected:
                    return False

        return True

    def _determine_correlation_type(self, rule: CorrelationRule) -> str:
        """Determine correlation type based on rule"""
        if rule.entity_match:
            return "causal"
        elif len(rule.event_types) > 1:
            return "semantic"
        else:
            return "temporal"

    def _calculate_confidence(
        self,
        events: List[Event],
        rule: CorrelationRule
    ) -> float:
        """Calculate correlation confidence"""
        # Base confidence from event count
        event_count_factor = min(1.0, len(events) / (rule.min_events * 2))

        # Time proximity factor
        if len(events) > 1:
            timestamps = [e.timestamp for e in events]
            time_range = (max(timestamps) - min(timestamps)).total_seconds()
            time_factor = 1.0 - (time_range / rule.time_window_seconds)
        else:
            time_factor = 1.0

        # Severity factor
        high_severity = sum(1 for e in events if e.severity in
                          [EventSeverity.ERROR, EventSeverity.CRITICAL])
        severity_factor = min(1.0, high_severity / len(events) + 0.5)

        return (event_count_factor * 0.4 + time_factor * 0.3 + severity_factor * 0.3)

    def _analyze_correlation(
        self,
        events: List[Event],
        rule: CorrelationRule
    ) -> Dict[str, Any]:
        """Analyze correlated events"""
        analysis = {
            "event_count": len(events),
            "time_span_seconds": self._calculate_time_span(events),
            "event_types": list(set(e.event_type.value for e in events)),
            "sources": list(set(e.source for e in events)),
            "severities": list(set(e.severity.value for e in events)),
            "entities": list(set(f"{e.entity_type}:{e.entity_id}"
                               for e in events if e.entity_id))
        }

        # Determine root cause
        earliest = min(events, key=lambda e: e.timestamp)
        analysis["root_cause"] = f"{earliest.source}: {earliest.message}"

        # Assess impact
        critical_count = sum(1 for e in events if e.severity == EventSeverity.CRITICAL)
        error_count = sum(1 for e in events if e.severity == EventSeverity.ERROR)

        if critical_count > 0:
            analysis["impact"] = "Critical - Immediate attention required"
        elif error_count > 0:
            analysis["impact"] = "High - Investigation needed"
        else:
            analysis["impact"] = "Medium - Monitor closely"

        return analysis

    def _calculate_time_span(self, events: List[Event]) -> float:
        """Calculate time span of events in seconds"""
        if not events:
            return 0.0
        timestamps = [e.timestamp for e in events]
        return (max(timestamps) - min(timestamps)).total_seconds()

    def _execute_action(self, correlation: CorrelatedEvent, rule: CorrelationRule):
        """Execute the rule's action"""
        action = rule.action

        if action == "alert":
            logger.warning(f"Correlation alert: {rule.name} - {len(correlation.event_ids)} events")
        elif action == "immediate_alert":
            logger.critical(f"IMMEDIATE: {rule.name} - {correlation.root_cause}")
        elif action == "root_cause_analysis":
            logger.info(f"Root cause identified: {correlation.root_cause}")
        elif action == "predict_maintenance":
            logger.info(f"Maintenance prediction triggered: {correlation.analysis}")

    def _notify_correlation(self, correlation: CorrelatedEvent):
        """Notify callbacks of new correlation"""
        for callback in self._callbacks:
            try:
                callback(correlation)
            except Exception as e:
                logger.error(f"Correlation callback error: {e}")

    def _trim_old_events(self):
        """Remove old events to stay within limit"""
        while len(self._events) > self._max_events:
            oldest_id = self._by_time.pop(0)
            event = self._events.pop(oldest_id, None)

            if event:
                self._by_type[event.event_type].discard(oldest_id)
                if event.entity_id:
                    entity_key = f"{event.entity_type}:{event.entity_id}"
                    self._by_entity[entity_key].discard(oldest_id)

    def get_event(self, event_id: str) -> Optional[Event]:
        """Get event by ID"""
        return self._events.get(event_id)

    def get_correlation(self, correlation_id: str) -> Optional[CorrelatedEvent]:
        """Get correlation by ID"""
        return self._correlations.get(correlation_id)

    def get_events_for_entity(
        self,
        entity_type: str,
        entity_id: str,
        limit: int = 100
    ) -> List[Event]:
        """Get events for a specific entity"""
        entity_key = f"{entity_type}:{entity_id}"
        event_ids = self._by_entity.get(entity_key, set())

        events = [self._events[eid] for eid in event_ids if eid in self._events]
        events.sort(key=lambda e: e.timestamp, reverse=True)

        return events[:limit]

    def get_recent_correlations(self, limit: int = 50) -> List[CorrelatedEvent]:
        """Get recent correlations"""
        correlations = list(self._correlations.values())
        correlations.sort(key=lambda c: c.created_at, reverse=True)
        return correlations[:limit]

    def add_rule(self, rule: CorrelationRule):
        """Add a correlation rule"""
        self._rules[rule.id] = rule

    def remove_rule(self, rule_id: str):
        """Remove a correlation rule"""
        self._rules.pop(rule_id, None)

    def enable_rule(self, rule_id: str):
        """Enable a rule"""
        if rule_id in self._rules:
            self._rules[rule_id].enabled = True

    def disable_rule(self, rule_id: str):
        """Disable a rule"""
        if rule_id in self._rules:
            self._rules[rule_id].enabled = False

    def add_callback(self, callback: Callable[[CorrelatedEvent], None]):
        """Add callback for new correlations"""
        self._callbacks.append(callback)


# Singleton instance
_correlator: Optional[EventCorrelator] = None


def get_event_correlator() -> EventCorrelator:
    """Get or create the singleton event correlator instance"""
    global _correlator
    if _correlator is None:
        _correlator = EventCorrelator()
    return _correlator
