"""
Real-Time KPI Aggregation Service
=================================

Provides hierarchical KPI aggregation from machine to enterprise level:
- Operational KPIs (OEE, throughput, cycle time)
- Quality KPIs (FPY, defect rate, Cpk)
- Financial KPIs (cost per unit, margin)
- Sustainability KPIs (energy, carbon, waste)
- Safety KPIs (incidents, near-misses)

Author: LEGO MCP Engineering Team
Version: 8.0.0
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple
import threading
import statistics

logger = logging.getLogger(__name__)


class KPICategory(Enum):
    """KPI category classifications"""
    OPERATIONAL = "operational"
    QUALITY = "quality"
    FINANCIAL = "financial"
    SUSTAINABILITY = "sustainability"
    SAFETY = "safety"
    DELIVERY = "delivery"
    INVENTORY = "inventory"


class AggregationLevel(Enum):
    """Hierarchy levels for aggregation"""
    MACHINE = "machine"
    CELL = "cell"
    LINE = "line"
    PLANT = "plant"
    ENTERPRISE = "enterprise"


class AggregationPeriod(Enum):
    """Time periods for aggregation"""
    REALTIME = "realtime"
    HOURLY = "hourly"
    SHIFT = "shift"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"


@dataclass
class KPIMetric:
    """Individual KPI metric"""
    name: str
    category: KPICategory
    value: float
    unit: str
    timestamp: datetime
    level: AggregationLevel
    period: AggregationPeriod
    target: Optional[float] = None
    lower_limit: Optional[float] = None
    upper_limit: Optional[float] = None
    trend: str = "stable"  # up, down, stable
    trend_percent: float = 0.0
    source: str = ""
    details: Dict[str, Any] = field(default_factory=dict)

    @property
    def status(self) -> str:
        """Calculate status based on value vs target/limits"""
        if self.target is not None:
            variance = abs(self.value - self.target) / self.target if self.target != 0 else 0
            if variance <= 0.05:
                return "on_target"
            elif self.value > self.target:
                return "above_target"
            else:
                return "below_target"

        if self.lower_limit is not None and self.value < self.lower_limit:
            return "critical_low"
        if self.upper_limit is not None and self.value > self.upper_limit:
            return "critical_high"

        return "normal"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "category": self.category.value,
            "value": self.value,
            "unit": self.unit,
            "timestamp": self.timestamp.isoformat(),
            "level": self.level.value,
            "period": self.period.value,
            "target": self.target,
            "lower_limit": self.lower_limit,
            "upper_limit": self.upper_limit,
            "status": self.status,
            "trend": self.trend,
            "trend_percent": self.trend_percent,
            "source": self.source,
            "details": self.details
        }


@dataclass
class KPIDashboard:
    """Aggregated KPI dashboard"""
    timestamp: datetime
    level: AggregationLevel
    period: AggregationPeriod
    overall_score: float  # 0-100 composite score
    categories: Dict[str, float]  # Category scores
    metrics: List[KPIMetric]
    alerts: List[Dict[str, Any]]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp.isoformat(),
            "level": self.level.value,
            "period": self.period.value,
            "overall_score": self.overall_score,
            "categories": self.categories,
            "metrics": [m.to_dict() for m in self.metrics],
            "alerts": self.alerts
        }


class KPIAggregator:
    """
    Real-time KPI aggregation and calculation engine.

    Collects metrics from various sources and aggregates them
    hierarchically and temporally.
    """

    # Standard KPI definitions
    KPI_DEFINITIONS = {
        # Operational KPIs
        "oee": {
            "name": "Overall Equipment Effectiveness",
            "category": KPICategory.OPERATIONAL,
            "unit": "%",
            "target": 85.0,
            "lower_limit": 60.0
        },
        "availability": {
            "name": "Availability",
            "category": KPICategory.OPERATIONAL,
            "unit": "%",
            "target": 95.0,
            "lower_limit": 80.0
        },
        "performance": {
            "name": "Performance Efficiency",
            "category": KPICategory.OPERATIONAL,
            "unit": "%",
            "target": 95.0,
            "lower_limit": 80.0
        },
        "throughput": {
            "name": "Throughput",
            "category": KPICategory.OPERATIONAL,
            "unit": "units/hr",
            "target": None  # Dynamic
        },
        "cycle_time": {
            "name": "Cycle Time",
            "category": KPICategory.OPERATIONAL,
            "unit": "seconds",
            "target": None  # Dynamic
        },
        "mtbf": {
            "name": "Mean Time Between Failures",
            "category": KPICategory.OPERATIONAL,
            "unit": "hours",
            "target": 500.0,
            "lower_limit": 100.0
        },
        "mttr": {
            "name": "Mean Time To Repair",
            "category": KPICategory.OPERATIONAL,
            "unit": "hours",
            "target": 2.0,
            "upper_limit": 8.0
        },

        # Quality KPIs
        "fpy": {
            "name": "First Pass Yield",
            "category": KPICategory.QUALITY,
            "unit": "%",
            "target": 99.0,
            "lower_limit": 95.0
        },
        "defect_rate": {
            "name": "Defect Rate",
            "category": KPICategory.QUALITY,
            "unit": "ppm",
            "target": 100.0,
            "upper_limit": 1000.0
        },
        "cpk": {
            "name": "Process Capability (Cpk)",
            "category": KPICategory.QUALITY,
            "unit": "",
            "target": 1.67,
            "lower_limit": 1.33
        },
        "scrap_rate": {
            "name": "Scrap Rate",
            "category": KPICategory.QUALITY,
            "unit": "%",
            "target": 1.0,
            "upper_limit": 5.0
        },
        "rework_rate": {
            "name": "Rework Rate",
            "category": KPICategory.QUALITY,
            "unit": "%",
            "target": 2.0,
            "upper_limit": 5.0
        },

        # Financial KPIs
        "cost_per_unit": {
            "name": "Cost Per Unit",
            "category": KPICategory.FINANCIAL,
            "unit": "$",
            "target": None
        },
        "labor_productivity": {
            "name": "Labor Productivity",
            "category": KPICategory.FINANCIAL,
            "unit": "units/hr",
            "target": None
        },
        "inventory_turns": {
            "name": "Inventory Turns",
            "category": KPICategory.FINANCIAL,
            "unit": "turns/year",
            "target": 12.0,
            "lower_limit": 6.0
        },

        # Delivery KPIs
        "on_time_delivery": {
            "name": "On-Time Delivery",
            "category": KPICategory.DELIVERY,
            "unit": "%",
            "target": 98.0,
            "lower_limit": 90.0
        },
        "order_fulfillment_rate": {
            "name": "Order Fulfillment Rate",
            "category": KPICategory.DELIVERY,
            "unit": "%",
            "target": 99.0,
            "lower_limit": 95.0
        },
        "lead_time": {
            "name": "Lead Time",
            "category": KPICategory.DELIVERY,
            "unit": "days",
            "target": 3.0,
            "upper_limit": 7.0
        },

        # Sustainability KPIs
        "energy_per_unit": {
            "name": "Energy Per Unit",
            "category": KPICategory.SUSTAINABILITY,
            "unit": "kWh",
            "target": None
        },
        "carbon_per_unit": {
            "name": "Carbon Per Unit",
            "category": KPICategory.SUSTAINABILITY,
            "unit": "kgCO2e",
            "target": None
        },
        "water_usage": {
            "name": "Water Usage",
            "category": KPICategory.SUSTAINABILITY,
            "unit": "L/unit",
            "target": None
        },
        "waste_rate": {
            "name": "Waste Rate",
            "category": KPICategory.SUSTAINABILITY,
            "unit": "%",
            "target": 2.0,
            "upper_limit": 5.0
        },

        # Safety KPIs
        "incident_rate": {
            "name": "Incident Rate",
            "category": KPICategory.SAFETY,
            "unit": "per 200k hrs",
            "target": 0.0,
            "upper_limit": 2.0
        },
        "near_miss_rate": {
            "name": "Near Miss Rate",
            "category": KPICategory.SAFETY,
            "unit": "per month",
            "target": None
        },
        "safety_training_compliance": {
            "name": "Safety Training Compliance",
            "category": KPICategory.SAFETY,
            "unit": "%",
            "target": 100.0,
            "lower_limit": 95.0
        }
    }

    def __init__(self, aggregation_interval: float = 5.0):
        """
        Initialize KPI aggregator.

        Args:
            aggregation_interval: Seconds between aggregation cycles
        """
        self._metrics: Dict[str, List[KPIMetric]] = {}  # Historical metrics
        self._current: Dict[str, KPIMetric] = {}  # Latest values
        self._collectors: Dict[str, Callable] = {}
        self._aggregation_interval = aggregation_interval
        self._running = False
        self._lock = threading.RLock()
        self._callbacks: List[Callable[[KPIDashboard], None]] = []
        self._history_limit = 1000  # Max metrics to keep per KPI

        # Register default collectors
        self._register_default_collectors()

    def _register_default_collectors(self):
        """Register default metric collectors"""
        self.register_collector("oee", self._collect_oee)
        self.register_collector("fpy", self._collect_fpy)
        self.register_collector("throughput", self._collect_throughput)
        self.register_collector("on_time_delivery", self._collect_otd)
        self.register_collector("energy_per_unit", self._collect_energy)

    def register_collector(self, kpi_name: str, collector: Callable[[], Optional[float]]):
        """
        Register a KPI collector function.

        Args:
            kpi_name: Name of the KPI
            collector: Function that returns the current KPI value
        """
        with self._lock:
            self._collectors[kpi_name] = collector

    def add_metric(self, metric: KPIMetric):
        """Add a metric reading"""
        with self._lock:
            if metric.name not in self._metrics:
                self._metrics[metric.name] = []

            self._metrics[metric.name].append(metric)
            self._current[metric.name] = metric

            # Trim history
            if len(self._metrics[metric.name]) > self._history_limit:
                self._metrics[metric.name] = self._metrics[metric.name][-self._history_limit:]

    def record_kpi(
        self,
        name: str,
        value: float,
        level: AggregationLevel = AggregationLevel.MACHINE,
        period: AggregationPeriod = AggregationPeriod.REALTIME,
        source: str = "",
        details: Dict[str, Any] = None
    ):
        """
        Record a KPI value.

        Args:
            name: KPI name (must be in KPI_DEFINITIONS)
            value: Metric value
            level: Aggregation hierarchy level
            period: Time period for aggregation
            source: Source of the metric
            details: Additional details
        """
        definition = self.KPI_DEFINITIONS.get(name)
        if not definition:
            logger.warning(f"Unknown KPI: {name}")
            return

        # Calculate trend
        trend, trend_percent = self._calculate_trend(name, value)

        metric = KPIMetric(
            name=name,
            category=definition["category"],
            value=value,
            unit=definition["unit"],
            timestamp=datetime.now(),
            level=level,
            period=period,
            target=definition.get("target"),
            lower_limit=definition.get("lower_limit"),
            upper_limit=definition.get("upper_limit"),
            trend=trend,
            trend_percent=trend_percent,
            source=source,
            details=details or {}
        )

        self.add_metric(metric)

    def _calculate_trend(self, name: str, current_value: float) -> Tuple[str, float]:
        """Calculate trend based on historical values"""
        with self._lock:
            history = self._metrics.get(name, [])
            if len(history) < 5:
                return "stable", 0.0

            recent = [m.value for m in history[-10:]]
            avg = statistics.mean(recent)

            if avg == 0:
                return "stable", 0.0

            change_percent = ((current_value - avg) / avg) * 100

            if change_percent > 5:
                return "up", change_percent
            elif change_percent < -5:
                return "down", change_percent
            else:
                return "stable", change_percent

    async def collect_all(self) -> List[KPIMetric]:
        """
        Run all collectors and return metrics.

        Returns:
            List of collected KPI metrics
        """
        metrics = []

        for name, collector in self._collectors.items():
            try:
                value = await self._run_collector(collector)
                if value is not None:
                    self.record_kpi(name, value)
                    metrics.append(self._current.get(name))
            except Exception as e:
                logger.error(f"Collector failed for {name}: {e}")

        return [m for m in metrics if m is not None]

    async def _run_collector(self, collector: Callable) -> Optional[float]:
        """Run a single collector"""
        if asyncio.iscoroutinefunction(collector):
            return await collector()
        else:
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(None, collector)

    def get_dashboard(
        self,
        level: AggregationLevel = AggregationLevel.PLANT,
        period: AggregationPeriod = AggregationPeriod.REALTIME
    ) -> KPIDashboard:
        """
        Get aggregated KPI dashboard.

        Args:
            level: Hierarchy level to aggregate
            period: Time period for aggregation

        Returns:
            KPIDashboard with aggregated metrics
        """
        with self._lock:
            metrics = list(self._current.values())

            # Calculate category scores
            categories = {}
            for category in KPICategory:
                cat_metrics = [m for m in metrics if m.category == category]
                if cat_metrics:
                    scores = []
                    for m in cat_metrics:
                        if m.target:
                            score = min(100, (m.value / m.target) * 100)
                        else:
                            score = 100 if m.status == "normal" else 50
                        scores.append(score)
                    categories[category.value] = statistics.mean(scores)

            # Calculate overall score
            if categories:
                overall_score = statistics.mean(categories.values())
            else:
                overall_score = 0.0

            # Generate alerts
            alerts = []
            for m in metrics:
                if m.status in ["critical_low", "critical_high", "below_target"]:
                    alerts.append({
                        "kpi": m.name,
                        "status": m.status,
                        "value": m.value,
                        "target": m.target,
                        "message": f"{m.name} is {m.status}: {m.value} {m.unit}"
                    })

            return KPIDashboard(
                timestamp=datetime.now(),
                level=level,
                period=period,
                overall_score=overall_score,
                categories=categories,
                metrics=metrics,
                alerts=alerts
            )

    def get_metric(self, name: str) -> Optional[KPIMetric]:
        """Get latest metric for a KPI"""
        with self._lock:
            return self._current.get(name)

    def get_metric_history(
        self,
        name: str,
        since: datetime = None,
        limit: int = 100
    ) -> List[KPIMetric]:
        """Get historical metrics for a KPI"""
        with self._lock:
            history = self._metrics.get(name, [])

            if since:
                history = [m for m in history if m.timestamp >= since]

            return history[-limit:]

    def add_dashboard_callback(self, callback: Callable[[KPIDashboard], None]):
        """Register callback for dashboard updates"""
        self._callbacks.append(callback)

    # Default collectors (integrate with actual services)

    def _collect_oee(self) -> float:
        """Collect OEE from manufacturing service"""
        try:
            from services.manufacturing.oee_service import OEEService
            oee_service = OEEService()
            return oee_service.get_current_oee()
        except Exception:
            return 85.0  # Default value

    def _collect_fpy(self) -> float:
        """Collect First Pass Yield from quality service"""
        try:
            from services.quality.inspection_service import InspectionService
            inspection_service = InspectionService()
            return inspection_service.get_first_pass_yield()
        except Exception:
            return 98.5  # Default value

    def _collect_throughput(self) -> float:
        """Collect throughput from manufacturing service"""
        try:
            from services.manufacturing.oee_service import OEEService
            oee_service = OEEService()
            return oee_service.get_current_throughput()
        except Exception:
            return 120.0  # Default value

    def _collect_otd(self) -> float:
        """Collect on-time delivery from ERP service"""
        try:
            from services.erp.order_service import OrderService
            order_service = OrderService()
            return order_service.get_on_time_delivery_rate()
        except Exception:
            return 97.5  # Default value

    def _collect_energy(self) -> float:
        """Collect energy per unit from sustainability service"""
        try:
            from services.sustainability.energy_optimizer import EnergyOptimizer
            optimizer = EnergyOptimizer()
            return optimizer.get_energy_per_unit()
        except Exception:
            return 0.5  # Default value

    async def start_collection(self):
        """Start background KPI collection"""
        self._running = True
        while self._running:
            try:
                await self.collect_all()
                dashboard = self.get_dashboard()

                # Notify callbacks
                for callback in self._callbacks:
                    try:
                        callback(dashboard)
                    except Exception as e:
                        logger.error(f"Dashboard callback error: {e}")

            except Exception as e:
                logger.error(f"KPI collection error: {e}")

            await asyncio.sleep(self._aggregation_interval)

    def stop_collection(self):
        """Stop background KPI collection"""
        self._running = False


# Singleton instance
_kpi_aggregator: Optional[KPIAggregator] = None


def get_kpi_aggregator() -> KPIAggregator:
    """Get or create the singleton KPI aggregator instance"""
    global _kpi_aggregator
    if _kpi_aggregator is None:
        _kpi_aggregator = KPIAggregator()
    return _kpi_aggregator
