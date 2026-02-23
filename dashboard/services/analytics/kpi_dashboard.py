"""
KPI Dashboard

Manufacturing KPI visualization and dashboard components.

Reference: ISO 22400 (Key Performance Indicators for Manufacturing)
"""

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from datetime import datetime
from enum import Enum

logger = logging.getLogger(__name__)


class WidgetType(Enum):
    """Dashboard widget types."""
    GAUGE = "gauge"
    LINE_CHART = "line_chart"
    BAR_CHART = "bar_chart"
    PIE_CHART = "pie_chart"
    TABLE = "table"
    METRIC_CARD = "metric_card"
    HEATMAP = "heatmap"
    SPARKLINE = "sparkline"


class KPICategory(Enum):
    """KPI categories per ISO 22400."""
    PRODUCTION = "production"
    QUALITY = "quality"
    MAINTENANCE = "maintenance"
    INVENTORY = "inventory"
    ENERGY = "energy"
    SAFETY = "safety"
    DELIVERY = "delivery"


class TrendIndicator(Enum):
    """KPI trend indicators."""
    UP = "up"
    DOWN = "down"
    STABLE = "stable"


@dataclass
class KPIMetric:
    """KPI metric definition."""
    id: str
    name: str
    category: KPICategory
    value: float
    unit: str
    target: Optional[float] = None
    min_threshold: Optional[float] = None
    max_threshold: Optional[float] = None
    trend: TrendIndicator = TrendIndicator.STABLE
    trend_value: float = 0.0
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")
    
    @property
    def status(self) -> str:
        """Get status based on thresholds."""
        if self.target:
            ratio = self.value / self.target
            if ratio >= 0.95:
                return "good"
            elif ratio >= 0.80:
                return "warning"
            else:
                return "critical"
        return "neutral"
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "category": self.category.value,
            "value": round(self.value, 4),
            "unit": self.unit,
            "target": self.target,
            "status": self.status,
            "trend": self.trend.value,
            "trend_value": round(self.trend_value, 4),
            "timestamp": self.timestamp
        }


@dataclass
class DashboardWidget:
    """Dashboard widget configuration."""
    id: str
    title: str
    widget_type: WidgetType
    metrics: List[str]  # KPI IDs
    position: Dict[str, int] = field(default_factory=lambda: {"x": 0, "y": 0})
    size: Dict[str, int] = field(default_factory=lambda: {"w": 4, "h": 2})
    config: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "type": self.widget_type.value,
            "metrics": self.metrics,
            "position": self.position,
            "size": self.size,
            "config": self.config
        }


class KPIDashboard:
    """
    Manufacturing KPI Dashboard.
    
    Provides real-time KPI visualization per ISO 22400.
    
    Usage:
        >>> dashboard = KPIDashboard("Production Floor")
        >>> dashboard.add_metric(oee_metric)
        >>> dashboard.add_widget(oee_widget)
        >>> data = dashboard.get_dashboard_data()
    """
    
    # ISO 22400 Standard KPIs
    STANDARD_KPIS = {
        # Production KPIs
        "oee": ("Overall Equipment Effectiveness", KPICategory.PRODUCTION, "%"),
        "availability": ("Availability", KPICategory.PRODUCTION, "%"),
        "performance": ("Performance", KPICategory.PRODUCTION, "%"),
        "quality_rate": ("Quality Rate", KPICategory.PRODUCTION, "%"),
        "throughput": ("Throughput", KPICategory.PRODUCTION, "units/hr"),
        "cycle_time": ("Cycle Time", KPICategory.PRODUCTION, "sec"),
        "takt_time": ("Takt Time", KPICategory.PRODUCTION, "sec"),
        
        # Quality KPIs
        "first_pass_yield": ("First Pass Yield", KPICategory.QUALITY, "%"),
        "defect_rate": ("Defect Rate", KPICategory.QUALITY, "ppm"),
        "scrap_rate": ("Scrap Rate", KPICategory.QUALITY, "%"),
        "rework_rate": ("Rework Rate", KPICategory.QUALITY, "%"),
        
        # Maintenance KPIs
        "mtbf": ("Mean Time Between Failures", KPICategory.MAINTENANCE, "hours"),
        "mttr": ("Mean Time To Repair", KPICategory.MAINTENANCE, "hours"),
        "planned_maintenance": ("Planned Maintenance", KPICategory.MAINTENANCE, "%"),
        
        # Delivery KPIs
        "otd": ("On-Time Delivery", KPICategory.DELIVERY, "%"),
        "lead_time": ("Lead Time", KPICategory.DELIVERY, "days"),
        
        # Inventory KPIs
        "inventory_turns": ("Inventory Turns", KPICategory.INVENTORY, "turns"),
        "wip": ("Work in Progress", KPICategory.INVENTORY, "units"),
    }
    
    def __init__(self, name: str = "Manufacturing Dashboard"):
        self.name = name
        self.metrics: Dict[str, KPIMetric] = {}
        self.widgets: Dict[str, DashboardWidget] = {}
        self.layout: List[Dict[str, Any]] = []
        logger.info(f"KPIDashboard '{name}' initialized")
    
    def add_metric(self, metric: KPIMetric) -> None:
        """Add a KPI metric."""
        self.metrics[metric.id] = metric
        logger.debug(f"Added metric: {metric.id}")
    
    def update_metric(
        self,
        metric_id: str,
        value: float,
        calculate_trend: bool = True
    ) -> Optional[KPIMetric]:
        """Update metric value."""
        if metric_id not in self.metrics:
            return None
        
        metric = self.metrics[metric_id]
        old_value = metric.value
        metric.value = value
        metric.timestamp = datetime.utcnow().isoformat() + "Z"
        
        if calculate_trend and old_value != 0:
            change = (value - old_value) / old_value
            metric.trend_value = change
            
            if change > 0.02:
                metric.trend = TrendIndicator.UP
            elif change < -0.02:
                metric.trend = TrendIndicator.DOWN
            else:
                metric.trend = TrendIndicator.STABLE
        
        return metric
    
    def add_widget(self, widget: DashboardWidget) -> None:
        """Add a dashboard widget."""
        self.widgets[widget.id] = widget
        logger.debug(f"Added widget: {widget.id}")
    
    def create_standard_metric(
        self,
        kpi_id: str,
        value: float,
        target: Optional[float] = None
    ) -> KPIMetric:
        """Create a metric from ISO 22400 standards."""
        if kpi_id not in self.STANDARD_KPIS:
            raise ValueError(f"Unknown standard KPI: {kpi_id}")
        
        name, category, unit = self.STANDARD_KPIS[kpi_id]
        
        return KPIMetric(
            id=kpi_id,
            name=name,
            category=category,
            value=value,
            unit=unit,
            target=target
        )
    
    def create_oee_dashboard(self) -> None:
        """Create standard OEE dashboard widgets."""
        # OEE Gauge
        self.add_widget(DashboardWidget(
            id="oee_gauge",
            title="Overall Equipment Effectiveness",
            widget_type=WidgetType.GAUGE,
            metrics=["oee"],
            position={"x": 0, "y": 0},
            size={"w": 4, "h": 4},
            config={
                "min": 0, "max": 100,
                "thresholds": [60, 85, 95],
                "colors": ["red", "yellow", "green"]
            }
        ))
        
        # Component Metrics
        self.add_widget(DashboardWidget(
            id="oee_components",
            title="OEE Components",
            widget_type=WidgetType.BAR_CHART,
            metrics=["availability", "performance", "quality_rate"],
            position={"x": 4, "y": 0},
            size={"w": 8, "h": 4}
        ))
        
        # Trend Chart
        self.add_widget(DashboardWidget(
            id="oee_trend",
            title="OEE Trend",
            widget_type=WidgetType.LINE_CHART,
            metrics=["oee"],
            position={"x": 0, "y": 4},
            size={"w": 12, "h": 4},
            config={"timeRange": "7d"}
        ))
    
    def create_quality_dashboard(self) -> None:
        """Create quality-focused dashboard."""
        self.add_widget(DashboardWidget(
            id="fpy_metric",
            title="First Pass Yield",
            widget_type=WidgetType.METRIC_CARD,
            metrics=["first_pass_yield"],
            position={"x": 0, "y": 0},
            size={"w": 3, "h": 2}
        ))
        
        self.add_widget(DashboardWidget(
            id="defect_metric",
            title="Defect Rate (PPM)",
            widget_type=WidgetType.METRIC_CARD,
            metrics=["defect_rate"],
            position={"x": 3, "y": 0},
            size={"w": 3, "h": 2}
        ))
        
        self.add_widget(DashboardWidget(
            id="quality_trend",
            title="Quality Trends",
            widget_type=WidgetType.LINE_CHART,
            metrics=["first_pass_yield", "defect_rate"],
            position={"x": 0, "y": 2},
            size={"w": 12, "h": 4}
        ))
    
    def get_dashboard_data(self) -> Dict[str, Any]:
        """Get complete dashboard data."""
        return {
            "name": self.name,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "metrics": {
                id: m.to_dict() for id, m in self.metrics.items()
            },
            "widgets": [w.to_dict() for w in self.widgets.values()],
            "summary": self._get_summary()
        }
    
    def _get_summary(self) -> Dict[str, Any]:
        """Get metrics summary."""
        by_status = {"good": 0, "warning": 0, "critical": 0, "neutral": 0}
        by_category: Dict[str, List[str]] = {}
        
        for metric in self.metrics.values():
            by_status[metric.status] = by_status.get(metric.status, 0) + 1
            
            cat = metric.category.value
            if cat not in by_category:
                by_category[cat] = []
            by_category[cat].append(metric.id)
        
        return {
            "total_metrics": len(self.metrics),
            "by_status": by_status,
            "by_category": by_category
        }
