"""
Shift Awareness for CNC Copilot.

Provides:
- Shift schedule management
- Operator tracking
- Shift handoff summaries
- Time-aware notifications
"""

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta, time
from enum import Enum

logger = logging.getLogger(__name__)


class ShiftType(Enum):
    """Standard shift types."""
    DAY = "day"
    SWING = "swing"
    NIGHT = "night"
    WEEKEND = "weekend"


@dataclass
class Shift:
    """A work shift definition."""
    name: str
    shift_type: ShiftType
    start_time: time
    end_time: time
    days: List[int] = field(default_factory=lambda: [0, 1, 2, 3, 4])  # Mon-Fri

    def is_active(self, dt: Optional[datetime] = None) -> bool:
        """Check if this shift is currently active."""
        dt = dt or datetime.now()

        # Check day of week
        if dt.weekday() not in self.days:
            return False

        # Check time
        current_time = dt.time()

        if self.start_time <= self.end_time:
            # Normal shift (e.g., 6:00-14:00)
            return self.start_time <= current_time < self.end_time
        else:
            # Overnight shift (e.g., 22:00-06:00)
            return current_time >= self.start_time or current_time < self.end_time

    def get_start_datetime(self, date: Optional[datetime] = None) -> datetime:
        """Get the start datetime for this shift on a given date."""
        date = date or datetime.now()
        return datetime.combine(date.date(), self.start_time)

    def get_end_datetime(self, date: Optional[datetime] = None) -> datetime:
        """Get the end datetime for this shift on a given date."""
        date = date or datetime.now()
        end = datetime.combine(date.date(), self.end_time)

        # Handle overnight shifts
        if self.end_time < self.start_time:
            end += timedelta(days=1)

        return end

    def duration_hours(self) -> float:
        """Get shift duration in hours."""
        start_dt = datetime.combine(datetime.today(), self.start_time)
        end_dt = datetime.combine(datetime.today(), self.end_time)

        if end_dt < start_dt:
            end_dt += timedelta(days=1)

        return (end_dt - start_dt).total_seconds() / 3600


@dataclass
class Operator:
    """An operator definition."""
    id: str
    name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    skills: List[str] = field(default_factory=list)
    certifications: List[str] = field(default_factory=list)


@dataclass
class ShiftAssignment:
    """Assignment of an operator to a shift."""
    operator_id: str
    shift_name: str
    date: datetime
    machines: List[str] = field(default_factory=list)
    notes: Optional[str] = None


@dataclass
class ShiftMetrics:
    """Metrics collected during a shift."""
    shift_name: str
    date: datetime
    start_time: datetime
    end_time: Optional[datetime] = None

    # Production metrics
    jobs_completed: int = 0
    parts_produced: int = 0
    cycle_time_avg: float = 0.0

    # Quality metrics
    scrap_count: int = 0
    rework_count: int = 0
    first_pass_yield: float = 100.0

    # Machine metrics
    uptime_percent: float = 100.0
    alarm_count: int = 0
    setup_time_minutes: float = 0.0

    # Issues
    issues: List[Dict[str, Any]] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)


class ShiftSchedule:
    """
    Manages shift schedules and operator assignments.

    Provides:
    - Shift definitions
    - Operator tracking
    - Current shift detection
    - Shift handoff support
    """

    # Standard 8-hour shift definitions
    DEFAULT_SHIFTS = [
        Shift(
            name="Day Shift",
            shift_type=ShiftType.DAY,
            start_time=time(6, 0),
            end_time=time(14, 0),
            days=[0, 1, 2, 3, 4],  # Mon-Fri
        ),
        Shift(
            name="Swing Shift",
            shift_type=ShiftType.SWING,
            start_time=time(14, 0),
            end_time=time(22, 0),
            days=[0, 1, 2, 3, 4],
        ),
        Shift(
            name="Night Shift",
            shift_type=ShiftType.NIGHT,
            start_time=time(22, 0),
            end_time=time(6, 0),
            days=[0, 1, 2, 3, 4],
        ),
        Shift(
            name="Weekend Day",
            shift_type=ShiftType.WEEKEND,
            start_time=time(6, 0),
            end_time=time(18, 0),
            days=[5, 6],  # Sat-Sun
        ),
        Shift(
            name="Weekend Night",
            shift_type=ShiftType.WEEKEND,
            start_time=time(18, 0),
            end_time=time(6, 0),
            days=[5, 6],
        ),
    ]

    def __init__(
        self,
        shifts: Optional[List[Shift]] = None,
        operators: Optional[List[Operator]] = None,
    ):
        """Initialize shift schedule."""
        self._shifts = {s.name: s for s in (shifts or self.DEFAULT_SHIFTS)}
        self._operators: Dict[str, Operator] = {}
        self._assignments: List[ShiftAssignment] = []
        self._metrics: Dict[str, ShiftMetrics] = {}
        self._current_metrics: Optional[ShiftMetrics] = None

        if operators:
            for op in operators:
                self._operators[op.id] = op

    def add_shift(self, shift: Shift):
        """Add a shift definition."""
        self._shifts[shift.name] = shift

    def add_operator(self, operator: Operator):
        """Add an operator."""
        self._operators[operator.id] = operator

    def assign_operator(
        self,
        operator_id: str,
        shift_name: str,
        date: datetime,
        machines: Optional[List[str]] = None,
        notes: Optional[str] = None,
    ):
        """Assign an operator to a shift."""
        assignment = ShiftAssignment(
            operator_id=operator_id,
            shift_name=shift_name,
            date=date,
            machines=machines or [],
            notes=notes,
        )
        self._assignments.append(assignment)

    def get_current_shift(self) -> Optional[Shift]:
        """Get the currently active shift."""
        now = datetime.now()
        for shift in self._shifts.values():
            if shift.is_active(now):
                return shift
        return None

    def get_current_operators(self) -> List[Operator]:
        """Get operators assigned to the current shift."""
        current = self.get_current_shift()
        if not current:
            return []

        today = datetime.now().date()
        operator_ids = set()

        for assignment in self._assignments:
            if (
                assignment.shift_name == current.name and
                assignment.date.date() == today
            ):
                operator_ids.add(assignment.operator_id)

        return [
            self._operators[oid]
            for oid in operator_ids
            if oid in self._operators
        ]

    def get_next_shift(self) -> Optional[Shift]:
        """Get the next shift that will become active."""
        now = datetime.now()
        current = self.get_current_shift()

        # Sort shifts by start time
        sorted_shifts = sorted(
            self._shifts.values(),
            key=lambda s: (s.start_time.hour, s.start_time.minute),
        )

        # Find the next shift
        for shift in sorted_shifts:
            if current and shift.name == current.name:
                continue

            shift_start = shift.get_start_datetime(now)
            if shift_start > now:
                return shift

        # Wrap to tomorrow's first shift
        return sorted_shifts[0] if sorted_shifts else None

    def time_until_shift_end(self) -> Optional[timedelta]:
        """Get time remaining in the current shift."""
        current = self.get_current_shift()
        if not current:
            return None

        now = datetime.now()
        end = current.get_end_datetime(now)

        if end < now:
            end += timedelta(days=1)

        return end - now

    def start_shift_metrics(self) -> ShiftMetrics:
        """Start tracking metrics for the current shift."""
        current = self.get_current_shift()
        if not current:
            raise ValueError("No active shift")

        now = datetime.now()
        metrics = ShiftMetrics(
            shift_name=current.name,
            date=now,
            start_time=current.get_start_datetime(now),
        )

        self._current_metrics = metrics
        return metrics

    def end_shift_metrics(self) -> Optional[ShiftMetrics]:
        """End tracking for current shift and archive metrics."""
        if not self._current_metrics:
            return None

        self._current_metrics.end_time = datetime.now()

        # Archive
        key = f"{self._current_metrics.shift_name}_{self._current_metrics.date.date()}"
        self._metrics[key] = self._current_metrics

        metrics = self._current_metrics
        self._current_metrics = None

        return metrics

    def update_metrics(
        self,
        jobs_completed: int = 0,
        parts_produced: int = 0,
        scrap_count: int = 0,
        rework_count: int = 0,
        alarm_count: int = 0,
    ):
        """Update current shift metrics."""
        if not self._current_metrics:
            return

        self._current_metrics.jobs_completed += jobs_completed
        self._current_metrics.parts_produced += parts_produced
        self._current_metrics.scrap_count += scrap_count
        self._current_metrics.rework_count += rework_count
        self._current_metrics.alarm_count += alarm_count

        # Recalculate first pass yield
        total = self._current_metrics.parts_produced
        if total > 0:
            good = total - self._current_metrics.scrap_count - self._current_metrics.rework_count
            self._current_metrics.first_pass_yield = (good / total) * 100

    def add_shift_issue(self, issue: Dict[str, Any]):
        """Add an issue to current shift metrics."""
        if self._current_metrics:
            self._current_metrics.issues.append({
                "timestamp": datetime.now().isoformat(),
                **issue,
            })

    def add_shift_note(self, note: str):
        """Add a note to current shift metrics."""
        if self._current_metrics:
            self._current_metrics.notes.append(note)

    def get_shift_metrics(
        self,
        shift_name: Optional[str] = None,
        date: Optional[datetime] = None,
    ) -> Optional[ShiftMetrics]:
        """Get metrics for a specific shift."""
        if shift_name is None and date is None:
            return self._current_metrics

        d = (date or datetime.now()).date()
        key = f"{shift_name}_{d}"
        return self._metrics.get(key)

    def generate_handoff_report(self) -> Dict[str, Any]:
        """Generate a shift handoff report."""
        current = self.get_current_shift()
        metrics = self._current_metrics

        report = {
            "generated_at": datetime.now().isoformat(),
            "current_shift": current.name if current else "None",
            "operators_on_shift": [
                {"id": op.id, "name": op.name}
                for op in self.get_current_operators()
            ],
            "time_remaining": str(self.time_until_shift_end()),
        }

        if metrics:
            report["metrics"] = {
                "jobs_completed": metrics.jobs_completed,
                "parts_produced": metrics.parts_produced,
                "first_pass_yield": f"{metrics.first_pass_yield:.1f}%",
                "alarm_count": metrics.alarm_count,
                "issues_count": len(metrics.issues),
            }

            if metrics.issues:
                report["recent_issues"] = metrics.issues[-5:]

            if metrics.notes:
                report["notes"] = metrics.notes[-5:]

        # Add upcoming shift info
        next_shift = self.get_next_shift()
        if next_shift:
            report["next_shift"] = {
                "name": next_shift.name,
                "starts_at": next_shift.start_time.strftime("%H:%M"),
            }

            # Get operators for next shift
            tomorrow = datetime.now() + timedelta(days=1)
            next_operators = [
                self._operators.get(a.operator_id)
                for a in self._assignments
                if a.shift_name == next_shift.name and
                   a.date.date() in [datetime.now().date(), tomorrow.date()]
            ]
            report["next_shift"]["operators"] = [
                {"id": op.id, "name": op.name}
                for op in next_operators if op
            ]

        return report

    def get_schedule_for_week(
        self,
        start_date: Optional[datetime] = None,
    ) -> List[Dict[str, Any]]:
        """Get the schedule for a week starting from a date."""
        start = start_date or datetime.now()
        start = start.replace(hour=0, minute=0, second=0, microsecond=0)

        # Go to Monday of this week
        start -= timedelta(days=start.weekday())

        schedule = []
        for i in range(7):
            date = start + timedelta(days=i)
            day_schedule = {
                "date": date.strftime("%Y-%m-%d"),
                "day_name": date.strftime("%A"),
                "shifts": [],
            }

            for shift in self._shifts.values():
                if date.weekday() in shift.days:
                    # Get assignments for this shift
                    assignments = [
                        a for a in self._assignments
                        if a.shift_name == shift.name and
                           a.date.date() == date.date()
                    ]

                    operators = [
                        {
                            "id": a.operator_id,
                            "name": self._operators.get(a.operator_id, Operator(
                                id=a.operator_id,
                                name="Unknown"
                            )).name,
                            "machines": a.machines,
                        }
                        for a in assignments
                    ]

                    day_schedule["shifts"].append({
                        "name": shift.name,
                        "type": shift.shift_type.value,
                        "start": shift.start_time.strftime("%H:%M"),
                        "end": shift.end_time.strftime("%H:%M"),
                        "operators": operators,
                    })

            schedule.append(day_schedule)

        return schedule


class ShiftAwareness:
    """
    Provides shift-aware features for the copilot.

    Integrates with the shift schedule to provide:
    - Context-aware notifications
    - Automatic handoff summaries
    - Time-sensitive alerts
    """

    def __init__(self, schedule: Optional[ShiftSchedule] = None):
        """Initialize shift awareness."""
        self.schedule = schedule or ShiftSchedule()
        self._handoff_callbacks: List[Any] = []

    def register_handoff_callback(self, callback):
        """Register a callback for shift handoff events."""
        self._handoff_callbacks.append(callback)

    def should_notify_now(
        self,
        priority: str,
        operator_id: Optional[str] = None,
    ) -> bool:
        """
        Determine if a notification should be sent now.

        Considers:
        - Current shift status
        - Priority level
        - Operator availability
        """
        current = self.schedule.get_current_shift()

        # Critical notifications always go through
        if priority == "critical":
            return True

        # If no active shift, only send high priority
        if not current:
            return priority in ["critical", "high"]

        # Check if near shift end (last 15 minutes)
        remaining = self.schedule.time_until_shift_end()
        if remaining and remaining < timedelta(minutes=15):
            # Queue non-critical notifications for next shift
            return priority in ["critical", "high"]

        return True

    def get_notification_context(self) -> Dict[str, Any]:
        """Get context for notifications."""
        current = self.schedule.get_current_shift()
        operators = self.schedule.get_current_operators()

        return {
            "shift_name": current.name if current else None,
            "shift_type": current.shift_type.value if current else None,
            "operators": [{"id": op.id, "name": op.name} for op in operators],
            "time_remaining": str(self.schedule.time_until_shift_end()),
        }

    async def trigger_handoff(self):
        """Trigger shift handoff process."""
        report = self.schedule.generate_handoff_report()

        for callback in self._handoff_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(report)
                else:
                    callback(report)
            except Exception as e:
                logger.error(f"Handoff callback error: {e}")

        return report

    def format_handoff_message(self, report: Dict[str, Any]) -> str:
        """Format a handoff report as a readable message."""
        lines = [
            f"=== Shift Handoff Report ===",
            f"Shift: {report.get('current_shift', 'Unknown')}",
            f"Time: {report.get('generated_at', '')}",
            "",
        ]

        # Metrics
        metrics = report.get("metrics", {})
        if metrics:
            lines.extend([
                "Production Summary:",
                f"  • Jobs Completed: {metrics.get('jobs_completed', 0)}",
                f"  • Parts Produced: {metrics.get('parts_produced', 0)}",
                f"  • First Pass Yield: {metrics.get('first_pass_yield', 'N/A')}",
                f"  • Alarms: {metrics.get('alarm_count', 0)}",
                "",
            ])

        # Issues
        issues = report.get("recent_issues", [])
        if issues:
            lines.append("Issues to Note:")
            for issue in issues[:3]:
                lines.append(f"  ⚠️ {issue.get('message', str(issue))}")
            lines.append("")

        # Notes
        notes = report.get("notes", [])
        if notes:
            lines.append("Operator Notes:")
            for note in notes[:3]:
                lines.append(f"  📝 {note}")
            lines.append("")

        # Next shift
        next_info = report.get("next_shift", {})
        if next_info:
            lines.extend([
                f"Incoming: {next_info.get('name', 'Unknown')} at {next_info.get('starts_at', '')}",
            ])
            ops = next_info.get("operators", [])
            if ops:
                lines.append(f"  Operators: {', '.join(op['name'] for op in ops)}")

        return "\n".join(lines)


# Import asyncio for type hints
import asyncio
