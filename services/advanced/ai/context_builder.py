"""
Context Builder - Production Context for AI

LegoMCP World-Class Manufacturing System v5.0
Phase 17: AI Manufacturing Copilot

Builds comprehensive context from production data for AI analysis.
Aggregates information from multiple sources into structured context.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class ContextType(str, Enum):
    """Types of context information."""
    MACHINE_STATUS = "machine_status"
    PRODUCTION_STATE = "production_state"
    QUALITY_METRICS = "quality_metrics"
    SCHEDULE_STATE = "schedule_state"
    INVENTORY_LEVELS = "inventory_levels"
    MAINTENANCE_STATUS = "maintenance_status"
    ALERTS = "alerts"
    HISTORICAL = "historical"
    FMEA = "fmea"
    SPC = "spc"


@dataclass
class MachineContext:
    """Context about a specific machine."""
    machine_id: str
    machine_name: str
    machine_type: str
    status: str  # running, idle, down, maintenance
    current_job: Optional[str] = None
    current_operation: Optional[str] = None
    progress_percent: float = 0.0
    temperature: Optional[float] = None
    speed_percent: float = 100.0
    health_score: float = 100.0
    runtime_hours: float = 0.0
    last_maintenance: Optional[datetime] = None
    pending_alerts: List[str] = field(default_factory=list)


@dataclass
class QualityContext:
    """Context about quality state."""
    fpy_percent: float = 100.0  # First Pass Yield
    defect_rate: float = 0.0
    active_ncrs: int = 0  # Non-conformance reports
    spc_signals: List[Dict[str, Any]] = field(default_factory=list)
    recent_defects: List[Dict[str, Any]] = field(default_factory=list)
    cpk_values: Dict[str, float] = field(default_factory=dict)
    top_failure_modes: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class ScheduleContext:
    """Context about schedule state."""
    orders_in_progress: int = 0
    orders_on_time: int = 0
    orders_late: int = 0
    orders_at_risk: int = 0
    schedule_adherence_percent: float = 100.0
    current_oee: float = 0.0
    bottleneck_machine: Optional[str] = None
    urgent_orders: List[Dict[str, Any]] = field(default_factory=list)
    upcoming_due_dates: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class InventoryContext:
    """Context about inventory levels."""
    low_stock_items: List[Dict[str, Any]] = field(default_factory=list)
    stockouts: List[str] = field(default_factory=list)
    pending_receipts: List[Dict[str, Any]] = field(default_factory=list)
    wip_value: float = 0.0


@dataclass
class ProductionContext:
    """
    Complete production context for AI analysis.

    Aggregates all relevant information about current production state.
    """
    timestamp: datetime = field(default_factory=datetime.utcnow)

    # Machine states
    machines: List[MachineContext] = field(default_factory=list)
    machines_running: int = 0
    machines_idle: int = 0
    machines_down: int = 0

    # Quality state
    quality: Optional[QualityContext] = None

    # Schedule state
    schedule: Optional[ScheduleContext] = None

    # Inventory state
    inventory: Optional[InventoryContext] = None

    # Alerts and events
    active_alerts: List[Dict[str, Any]] = field(default_factory=list)
    recent_events: List[Dict[str, Any]] = field(default_factory=list)

    # Historical context
    shift_start: Optional[datetime] = None
    shift_output: int = 0
    shift_target: int = 0

    # Metadata
    context_types_included: List[ContextType] = field(default_factory=list)

    def to_prompt_text(self) -> str:
        """Convert context to text suitable for AI prompt."""
        lines = []
        lines.append(f"## Current Production State ({self.timestamp.strftime('%Y-%m-%d %H:%M')})")
        lines.append("")

        # Machine summary
        lines.append("### Machines")
        lines.append(f"- Running: {self.machines_running}")
        lines.append(f"- Idle: {self.machines_idle}")
        lines.append(f"- Down: {self.machines_down}")

        for machine in self.machines:
            status_icon = "🟢" if machine.status == "running" else "🟡" if machine.status == "idle" else "🔴"
            lines.append(f"- {status_icon} {machine.machine_name} ({machine.machine_type}): {machine.status}")
            if machine.current_job:
                lines.append(f"  - Current job: {machine.current_job} ({machine.progress_percent:.0f}%)")
            if machine.pending_alerts:
                lines.append(f"  - Alerts: {', '.join(machine.pending_alerts)}")

        # Quality summary
        if self.quality:
            lines.append("")
            lines.append("### Quality")
            lines.append(f"- First Pass Yield: {self.quality.fpy_percent:.1f}%")
            lines.append(f"- Defect Rate: {self.quality.defect_rate:.2f}%")
            lines.append(f"- Active NCRs: {self.quality.active_ncrs}")

            if self.quality.spc_signals:
                lines.append(f"- SPC Signals: {len(self.quality.spc_signals)} active")
                for signal in self.quality.spc_signals[:3]:
                    lines.append(f"  - {signal.get('metric')}: {signal.get('type')}")

            if self.quality.top_failure_modes:
                lines.append("- Top Failure Modes:")
                for fm in self.quality.top_failure_modes[:3]:
                    lines.append(f"  - {fm.get('name')} (RPN: {fm.get('rpn', 0)})")

        # Schedule summary
        if self.schedule:
            lines.append("")
            lines.append("### Schedule")
            lines.append(f"- Orders in Progress: {self.schedule.orders_in_progress}")
            lines.append(f"- On Time: {self.schedule.orders_on_time}")
            lines.append(f"- Late: {self.schedule.orders_late}")
            lines.append(f"- At Risk: {self.schedule.orders_at_risk}")
            lines.append(f"- Schedule Adherence: {self.schedule.schedule_adherence_percent:.1f}%")
            lines.append(f"- Current OEE: {self.schedule.current_oee:.1f}%")

            if self.schedule.bottleneck_machine:
                lines.append(f"- Bottleneck: {self.schedule.bottleneck_machine}")

            if self.schedule.urgent_orders:
                lines.append("- Urgent Orders:")
                for order in self.schedule.urgent_orders[:3]:
                    lines.append(f"  - {order.get('order_id')}: due {order.get('due_date')}")

        # Inventory summary
        if self.inventory:
            lines.append("")
            lines.append("### Inventory")
            if self.inventory.stockouts:
                lines.append(f"- STOCKOUTS: {', '.join(self.inventory.stockouts)}")
            if self.inventory.low_stock_items:
                lines.append(f"- Low Stock: {len(self.inventory.low_stock_items)} items")
            lines.append(f"- WIP Value: ${self.inventory.wip_value:,.2f}")

        # Active alerts
        if self.active_alerts:
            lines.append("")
            lines.append("### Active Alerts")
            for alert in self.active_alerts[:5]:
                severity = alert.get('severity', 'INFO')
                icon = "🔴" if severity == "CRITICAL" else "🟠" if severity == "WARNING" else "🔵"
                lines.append(f"- {icon} [{severity}] {alert.get('message')}")

        # Shift progress
        if self.shift_start:
            lines.append("")
            lines.append("### Shift Progress")
            lines.append(f"- Output: {self.shift_output} / {self.shift_target} ({self.shift_output / max(1, self.shift_target) * 100:.0f}%)")

        return "\n".join(lines)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'timestamp': self.timestamp.isoformat(),
            'machines_running': self.machines_running,
            'machines_idle': self.machines_idle,
            'machines_down': self.machines_down,
            'quality': {
                'fpy_percent': self.quality.fpy_percent if self.quality else None,
                'defect_rate': self.quality.defect_rate if self.quality else None,
                'active_ncrs': self.quality.active_ncrs if self.quality else None,
            } if self.quality else None,
            'schedule': {
                'orders_in_progress': self.schedule.orders_in_progress if self.schedule else None,
                'on_time': self.schedule.orders_on_time if self.schedule else None,
                'late': self.schedule.orders_late if self.schedule else None,
                'oee': self.schedule.current_oee if self.schedule else None,
            } if self.schedule else None,
            'active_alerts': len(self.active_alerts),
        }


class ContextBuilder:
    """
    Builds production context from various data sources.

    Aggregates information from databases, events, and real-time feeds.
    """

    def __init__(
        self,
        db_session: Optional[Any] = None,
        event_bus: Optional[Any] = None,
        redis_client: Optional[Any] = None,
    ):
        self.db = db_session
        self.event_bus = event_bus
        self.redis = redis_client

    async def build_context(
        self,
        context_types: Optional[List[ContextType]] = None,
        machine_ids: Optional[List[str]] = None,
        time_window: Optional[timedelta] = None,
    ) -> ProductionContext:
        """
        Build production context.

        Args:
            context_types: Types of context to include (all if None)
            machine_ids: Specific machines to include (all if None)
            time_window: How far back to look for events

        Returns:
            Complete production context
        """
        context = ProductionContext()
        types_to_build = context_types or list(ContextType)
        time_window = time_window or timedelta(hours=8)

        if ContextType.MACHINE_STATUS in types_to_build:
            await self._build_machine_context(context, machine_ids)

        if ContextType.QUALITY_METRICS in types_to_build:
            await self._build_quality_context(context, time_window)

        if ContextType.SCHEDULE_STATE in types_to_build:
            await self._build_schedule_context(context)

        if ContextType.INVENTORY_LEVELS in types_to_build:
            await self._build_inventory_context(context)

        if ContextType.ALERTS in types_to_build:
            await self._build_alerts_context(context, time_window)

        context.context_types_included = types_to_build
        return context

    async def _build_machine_context(
        self,
        context: ProductionContext,
        machine_ids: Optional[List[str]] = None
    ) -> None:
        """Build machine status context."""
        # In production, this would query the database and digital twin
        # For now, create sample data structure

        sample_machines = [
            MachineContext(
                machine_id="printer-001",
                machine_name="Prusa MK3S #1",
                machine_type="3D Printer",
                status="running",
                current_job="WO-2024-001",
                current_operation="Print 2x4 Brick",
                progress_percent=67.5,
                temperature=210.0,
                health_score=92.0,
            ),
            MachineContext(
                machine_id="printer-002",
                machine_name="Bambu X1C #1",
                machine_type="3D Printer",
                status="idle",
                health_score=98.0,
            ),
            MachineContext(
                machine_id="cnc-001",
                machine_name="CNC Mill #1",
                machine_type="CNC Mill",
                status="running",
                current_job="WO-2024-003",
                progress_percent=45.0,
                health_score=85.0,
                pending_alerts=["Tool wear warning"],
            ),
        ]

        if machine_ids:
            context.machines = [m for m in sample_machines if m.machine_id in machine_ids]
        else:
            context.machines = sample_machines

        context.machines_running = sum(1 for m in context.machines if m.status == "running")
        context.machines_idle = sum(1 for m in context.machines if m.status == "idle")
        context.machines_down = sum(1 for m in context.machines if m.status in ("down", "maintenance"))

    async def _build_quality_context(
        self,
        context: ProductionContext,
        time_window: timedelta
    ) -> None:
        """Build quality metrics context."""
        context.quality = QualityContext(
            fpy_percent=97.5,
            defect_rate=0.8,
            active_ncrs=2,
            spc_signals=[
                {"metric": "stud_diameter", "type": "ZONE_C", "machine": "printer-001"},
            ],
            recent_defects=[
                {"type": "under_extrusion", "count": 3, "severity": "minor"},
                {"type": "warping", "count": 1, "severity": "major"},
            ],
            cpk_values={
                "stud_diameter": 1.45,
                "stud_height": 1.62,
                "wall_thickness": 1.33,
            },
            top_failure_modes=[
                {"name": "Layer adhesion failure", "rpn": 180, "occurrence": 4},
                {"name": "Dimensional drift", "rpn": 144, "occurrence": 3},
            ]
        )

    async def _build_schedule_context(self, context: ProductionContext) -> None:
        """Build schedule state context."""
        context.schedule = ScheduleContext(
            orders_in_progress=12,
            orders_on_time=10,
            orders_late=1,
            orders_at_risk=3,
            schedule_adherence_percent=94.5,
            current_oee=78.3,
            bottleneck_machine="printer-001",
            urgent_orders=[
                {"order_id": "ORD-2024-045", "due_date": "2024-01-15", "priority": "high"},
                {"order_id": "ORD-2024-048", "due_date": "2024-01-16", "priority": "medium"},
            ],
        )

    async def _build_inventory_context(self, context: ProductionContext) -> None:
        """Build inventory levels context."""
        context.inventory = InventoryContext(
            low_stock_items=[
                {"part": "PLA Red Filament", "qty": 2, "reorder_point": 5},
            ],
            stockouts=[],
            wip_value=15420.50,
        )

    async def _build_alerts_context(
        self,
        context: ProductionContext,
        time_window: timedelta
    ) -> None:
        """Build active alerts context."""
        context.active_alerts = [
            {
                "severity": "WARNING",
                "message": "CNC Mill #1: Tool wear approaching limit",
                "timestamp": datetime.utcnow().isoformat(),
            },
            {
                "severity": "INFO",
                "message": "Shift change in 30 minutes",
                "timestamp": datetime.utcnow().isoformat(),
            },
        ]

    async def build_for_question(
        self,
        question: str,
        include_historical: bool = False
    ) -> ProductionContext:
        """
        Build context optimized for answering a specific question.

        Analyzes the question to determine which context types are needed.
        """
        question_lower = question.lower()

        context_types = []

        # Determine relevant context types based on question
        if any(word in question_lower for word in ['machine', 'printer', 'cnc', 'equipment', 'status']):
            context_types.append(ContextType.MACHINE_STATUS)

        if any(word in question_lower for word in ['quality', 'defect', 'spc', 'cpk', 'yield', 'fmea']):
            context_types.append(ContextType.QUALITY_METRICS)
            context_types.append(ContextType.FMEA)
            context_types.append(ContextType.SPC)

        if any(word in question_lower for word in ['schedule', 'order', 'late', 'due', 'oee', 'on time']):
            context_types.append(ContextType.SCHEDULE_STATE)

        if any(word in question_lower for word in ['inventory', 'stock', 'material', 'wip']):
            context_types.append(ContextType.INVENTORY_LEVELS)

        if any(word in question_lower for word in ['alert', 'alarm', 'warning', 'problem']):
            context_types.append(ContextType.ALERTS)

        if any(word in question_lower for word in ['maintenance', 'health', 'preventive']):
            context_types.append(ContextType.MAINTENANCE_STATUS)

        # Default to comprehensive context if no specific types identified
        if not context_types:
            context_types = [
                ContextType.MACHINE_STATUS,
                ContextType.SCHEDULE_STATE,
                ContextType.QUALITY_METRICS,
            ]

        if include_historical:
            context_types.append(ContextType.HISTORICAL)

        return await self.build_context(context_types=context_types)
