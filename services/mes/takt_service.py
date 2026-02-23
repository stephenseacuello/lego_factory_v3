"""
Takt Time & Line Balancing Service
===================================
Calculates takt time and analyzes production line balance.
Enhanced with real-time monitoring, alerts, and bottleneck analysis.
"""
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict
import statistics

from sqlalchemy import distinct

from models.mes.operations import CycleTimeRecord


class TaktAlertLevel(str, Enum):
    """Alert severity levels for takt time deviations."""
    NORMAL = 'normal'
    WARNING = 'warning'
    CRITICAL = 'critical'


class BottleneckSeverity(str, Enum):
    """Severity of production bottleneck."""
    NONE = 'none'
    MINOR = 'minor'
    MODERATE = 'moderate'
    SEVERE = 'severe'


@dataclass
class TaktStatus:
    """Real-time takt time status for a work center."""
    work_center_id: str
    takt_time_seconds: float
    actual_cycle_seconds: float
    deviation_seconds: float
    deviation_pct: float
    alert_level: TaktAlertLevel
    units_behind: int
    time_behind_seconds: float
    trend: str  # 'improving', 'stable', 'degrading'
    timestamp: datetime = field(default_factory=datetime.utcnow)

    @property
    def is_on_takt(self) -> bool:
        return self.deviation_pct <= 5.0


@dataclass
class LineBalanceRecommendation:
    """Recommendation for improving line balance."""
    priority: int
    action: str
    description: str
    affected_stations: List[str]
    estimated_improvement_pct: float
    effort_level: str  # 'low', 'medium', 'high'


@dataclass
class BottleneckAnalysis:
    """Detailed bottleneck analysis for a production line."""
    bottleneck_station: str
    bottleneck_cycle_seconds: float
    line_capacity_units_per_hour: float
    stations_starved: List[str]
    stations_blocked: List[str]
    severity: BottleneckSeverity
    cost_impact_per_hour: float


@dataclass
class TaktPerformanceTrend:
    """Historical takt performance data point."""
    period: str
    takt_target_seconds: float
    actual_avg_seconds: float
    deviation_pct: float
    on_takt_pct: float  # % of cycles within takt
    sample_count: int


class TaktService:
    def __init__(self, session):
        self.session = session
        self._alert_thresholds = {
            'warning_pct': 10.0,
            'critical_pct': 20.0,
        }

    def _query_recent_records(self, work_center_id: str,
                              cutoff: datetime) -> List[Dict[str, Any]]:
        """Query CycleTimeRecord rows for a work center since cutoff, returned as dicts."""
        rows = (
            self.session.query(CycleTimeRecord)
            .filter(
                CycleTimeRecord.work_center_id == work_center_id,
                CycleTimeRecord.created_at >= cutoff,
            )
            .order_by(CycleTimeRecord.created_at.asc())
            .all()
        )
        return [r.to_dict() for r in rows]

    def calculate_takt_time(self, demand_qty: int, available_hours: float,
                            product_id: str = None) -> Dict[str, Any]:
        """Calculate takt time from demand and available time."""
        if demand_qty <= 0:
            return {'error': 'Demand must be positive'}
        available_seconds = available_hours * 3600
        takt = available_seconds / demand_qty
        result = {
            'takt_time_seconds': round(takt, 1),
            'takt_time_minutes': round(takt / 60, 2),
            'demand_qty': demand_qty,
            'available_hours': available_hours,
            'units_per_hour': round(demand_qty / available_hours, 1),
        }
        if product_id:
            result['product_id'] = product_id
        return result

    def record_cycle_time(self, work_center_id: str, cycle_seconds: float,
                          takt_target_seconds: float, job_id: str = None,
                          operator_id: str = None) -> Dict[str, Any]:
        """Record an actual cycle time for real-time monitoring."""
        deviation_seconds = cycle_seconds - takt_target_seconds
        on_takt = cycle_seconds <= takt_target_seconds * 1.05

        db_record = CycleTimeRecord(
            work_center_id=work_center_id,
            cycle_seconds=cycle_seconds,
            takt_target_seconds=takt_target_seconds,
            deviation_seconds=deviation_seconds,
            on_takt=on_takt,
            job_id=job_id,
            operator_id=operator_id,
        )
        self.session.add(db_record)
        self.session.flush()

        record = db_record.to_dict()

        alert = self._check_takt_alert(work_center_id, cycle_seconds, takt_target_seconds)

        return {
            'status': 'recorded',
            'record': record,
            'alert': alert,
        }

    def _check_takt_alert(self, work_center_id: str, cycle_seconds: float,
                          takt_seconds: float) -> Optional[Dict[str, Any]]:
        """Check if cycle time deviation triggers an alert."""
        if takt_seconds <= 0:
            return None

        deviation_pct = ((cycle_seconds - takt_seconds) / takt_seconds) * 100

        if deviation_pct >= self._alert_thresholds['critical_pct']:
            return {
                'level': TaktAlertLevel.CRITICAL.value,
                'message': f'Critical: {work_center_id} cycle time {deviation_pct:.1f}% over takt',
                'deviation_pct': round(deviation_pct, 1),
                'action_required': 'Immediate intervention required',
            }
        elif deviation_pct >= self._alert_thresholds['warning_pct']:
            return {
                'level': TaktAlertLevel.WARNING.value,
                'message': f'Warning: {work_center_id} cycle time {deviation_pct:.1f}% over takt',
                'deviation_pct': round(deviation_pct, 1),
                'action_required': 'Monitor closely, prepare contingency',
            }
        return None

    def get_realtime_takt_status(self, work_center_id: str,
                                  takt_target_seconds: float,
                                  window_minutes: int = 30) -> TaktStatus:
        """Get real-time takt status with trend analysis."""
        cutoff = datetime.utcnow() - timedelta(minutes=window_minutes)
        recent = self._query_recent_records(work_center_id, cutoff)

        if not recent:
            return TaktStatus(
                work_center_id=work_center_id,
                takt_time_seconds=takt_target_seconds,
                actual_cycle_seconds=0,
                deviation_seconds=0,
                deviation_pct=0,
                alert_level=TaktAlertLevel.NORMAL,
                units_behind=0,
                time_behind_seconds=0,
                trend='stable',
            )

        avg_cycle = statistics.mean(r['cycle_seconds'] for r in recent)
        deviation = avg_cycle - takt_target_seconds
        deviation_pct = (deviation / takt_target_seconds) * 100 if takt_target_seconds > 0 else 0

        if deviation_pct >= self._alert_thresholds['critical_pct']:
            alert_level = TaktAlertLevel.CRITICAL
        elif deviation_pct >= self._alert_thresholds['warning_pct']:
            alert_level = TaktAlertLevel.WARNING
        else:
            alert_level = TaktAlertLevel.NORMAL

        units_behind = 0
        time_behind = 0
        if deviation > 0:
            elapsed_seconds = window_minutes * 60
            expected_units = elapsed_seconds / takt_target_seconds
            actual_units = elapsed_seconds / avg_cycle
            units_behind = max(0, int(expected_units - actual_units))
            time_behind = units_behind * takt_target_seconds

        trend = self._calculate_trend(recent)

        return TaktStatus(
            work_center_id=work_center_id,
            takt_time_seconds=takt_target_seconds,
            actual_cycle_seconds=round(avg_cycle, 1),
            deviation_seconds=round(deviation, 1),
            deviation_pct=round(deviation_pct, 1),
            alert_level=alert_level,
            units_behind=units_behind,
            time_behind_seconds=round(time_behind, 1),
            trend=trend,
        )

    def _calculate_trend(self, records: List[Dict]) -> str:
        """Calculate trend from recent cycle times."""
        if len(records) < 5:
            return 'stable'

        first_half = records[:len(records) // 2]
        second_half = records[len(records) // 2:]

        first_avg = statistics.mean(r['cycle_seconds'] for r in first_half)
        second_avg = statistics.mean(r['cycle_seconds'] for r in second_half)

        change_pct = ((second_avg - first_avg) / first_avg) * 100 if first_avg > 0 else 0

        if change_pct < -5:
            return 'improving'
        elif change_pct > 5:
            return 'degrading'
        return 'stable'

    def get_takt_alerts(self, work_center_ids: List[str] = None,
                        takt_targets: Dict[str, float] = None) -> List[Dict[str, Any]]:
        """Get active takt alerts across work centers."""
        alerts = []

        if work_center_ids:
            work_centers = work_center_ids
        else:
            rows = (
                self.session.query(distinct(CycleTimeRecord.work_center_id))
                .all()
            )
            work_centers = [row[0] for row in rows]

        for wc_id in work_centers:
            takt = takt_targets.get(wc_id, 60) if takt_targets else 60
            status = self.get_realtime_takt_status(wc_id, takt)

            if status.alert_level != TaktAlertLevel.NORMAL:
                alerts.append({
                    'work_center_id': wc_id,
                    'alert_level': status.alert_level.value,
                    'deviation_pct': status.deviation_pct,
                    'units_behind': status.units_behind,
                    'trend': status.trend,
                    'timestamp': status.timestamp.isoformat(),
                })

        return sorted(alerts, key=lambda x: (
            0 if x['alert_level'] == 'critical' else 1,
            -x['deviation_pct']
        ))

    def line_balance_analysis(self, operation_cycle_times: List[Dict[str, Any]],
                               takt_seconds: float) -> Dict[str, Any]:
        """Analyze production line balance against takt time."""
        if not operation_cycle_times or takt_seconds <= 0:
            return {'error': 'Invalid inputs'}

        total_cycle = sum(op.get('cycle_seconds', 0) for op in operation_cycle_times)
        num_stations = len(operation_cycle_times)
        max_cycle = max(op.get('cycle_seconds', 0) for op in operation_cycle_times)

        balance_efficiency = round(
            total_cycle / (num_stations * max_cycle) * 100, 1
        ) if max_cycle > 0 else 0

        bottleneck = max(operation_cycle_times, key=lambda x: x.get('cycle_seconds', 0))

        operations = []
        for op in operation_cycle_times:
            ct = op.get('cycle_seconds', 0)
            utilization = (ct / max_cycle * 100) if max_cycle > 0 else 0
            operations.append({
                'name': op.get('name', 'Unknown'),
                'cycle_seconds': ct,
                'idle_seconds': round(max_cycle - ct, 1),
                'exceeds_takt': ct > takt_seconds,
                'utilization_pct': round(utilization, 1),
            })

        theoretical_min_stations = total_cycle / takt_seconds if takt_seconds > 0 else num_stations

        return {
            'takt_time_seconds': takt_seconds,
            'total_cycle_time': round(total_cycle, 1),
            'num_stations': num_stations,
            'theoretical_min_stations': round(theoretical_min_stations, 1),
            'bottleneck': bottleneck.get('name', 'Unknown'),
            'bottleneck_cycle': max_cycle,
            'balance_efficiency_pct': balance_efficiency,
            'operations': operations,
            'recommendation': 'Balanced' if balance_efficiency > 85 else 'Needs rebalancing',
        }

    def get_line_balance_recommendations(self, operation_cycle_times: List[Dict[str, Any]],
                                          takt_seconds: float) -> List[LineBalanceRecommendation]:
        """Generate specific recommendations to improve line balance."""
        if not operation_cycle_times or takt_seconds <= 0:
            return []

        recommendations = []
        max_cycle = max(op.get('cycle_seconds', 0) for op in operation_cycle_times)
        avg_cycle = sum(op.get('cycle_seconds', 0) for op in operation_cycle_times) / len(operation_cycle_times)

        exceeds_takt = [op for op in operation_cycle_times if op.get('cycle_seconds', 0) > takt_seconds]
        if exceeds_takt:
            recommendations.append(LineBalanceRecommendation(
                priority=1,
                action='reduce_bottleneck_cycle',
                description=f'Reduce cycle time at {len(exceeds_takt)} station(s) exceeding takt',
                affected_stations=[op.get('name', 'Unknown') for op in exceeds_takt],
                estimated_improvement_pct=round(
                    (max_cycle - takt_seconds) / max_cycle * 100, 1
                ) if max_cycle > takt_seconds else 0,
                effort_level='high',
            ))

        underutilized = [op for op in operation_cycle_times
                         if op.get('cycle_seconds', 0) < avg_cycle * 0.7]
        if underutilized and len(operation_cycle_times) > 2:
            recommendations.append(LineBalanceRecommendation(
                priority=2,
                action='combine_operations',
                description='Consider combining underutilized stations',
                affected_stations=[op.get('name', 'Unknown') for op in underutilized],
                estimated_improvement_pct=round(
                    (len(underutilized) / len(operation_cycle_times)) * 100 * 0.3, 1
                ),
                effort_level='medium',
            ))

        overloaded = [op for op in operation_cycle_times
                      if op.get('cycle_seconds', 0) > avg_cycle * 1.3]
        if overloaded:
            recommendations.append(LineBalanceRecommendation(
                priority=2,
                action='split_operation',
                description='Split overloaded operations across multiple stations',
                affected_stations=[op.get('name', 'Unknown') for op in overloaded],
                estimated_improvement_pct=round(
                    ((max_cycle - avg_cycle) / max_cycle) * 100, 1
                ),
                effort_level='high',
            ))

        has_adjacent_imbalance = False
        for i in range(len(operation_cycle_times) - 1):
            ct1 = operation_cycle_times[i].get('cycle_seconds', 0)
            ct2 = operation_cycle_times[i + 1].get('cycle_seconds', 0)
            if abs(ct1 - ct2) > avg_cycle * 0.3:
                has_adjacent_imbalance = True
                break

        if has_adjacent_imbalance:
            recommendations.append(LineBalanceRecommendation(
                priority=3,
                action='redistribute_work',
                description='Redistribute work elements between adjacent stations',
                affected_stations=[op.get('name', 'Unknown') for op in operation_cycle_times],
                estimated_improvement_pct=10.0,
                effort_level='low',
            ))

        return sorted(recommendations, key=lambda x: x.priority)

    def analyze_bottleneck(self, operation_cycle_times: List[Dict[str, Any]],
                            cost_per_hour: float = 100.0) -> BottleneckAnalysis:
        """Detailed bottleneck analysis with cost impact."""
        if not operation_cycle_times:
            return BottleneckAnalysis(
                bottleneck_station='Unknown',
                bottleneck_cycle_seconds=0,
                line_capacity_units_per_hour=0,
                stations_starved=[],
                stations_blocked=[],
                severity=BottleneckSeverity.NONE,
                cost_impact_per_hour=0,
            )

        cycles = [(op.get('name', f'Station {i}'), op.get('cycle_seconds', 0))
                  for i, op in enumerate(operation_cycle_times)]

        bottleneck_name, bottleneck_cycle = max(cycles, key=lambda x: x[1])
        avg_cycle = sum(c[1] for c in cycles) / len(cycles)

        idx = next(i for i, (name, _) in enumerate(cycles) if name == bottleneck_name)
        stations_starved = [name for name, _ in cycles[idx + 1:]]
        stations_blocked = [name for name, _ in cycles[:idx]]

        deviation_ratio = bottleneck_cycle / avg_cycle if avg_cycle > 0 else 1
        if deviation_ratio >= 1.5:
            severity = BottleneckSeverity.SEVERE
        elif deviation_ratio >= 1.25:
            severity = BottleneckSeverity.MODERATE
        elif deviation_ratio >= 1.1:
            severity = BottleneckSeverity.MINOR
        else:
            severity = BottleneckSeverity.NONE

        line_capacity = 3600 / bottleneck_cycle if bottleneck_cycle > 0 else 0
        theoretical_capacity = 3600 / avg_cycle if avg_cycle > 0 else 0
        lost_capacity = theoretical_capacity - line_capacity
        cost_impact = lost_capacity * cost_per_hour / theoretical_capacity if theoretical_capacity > 0 else 0

        return BottleneckAnalysis(
            bottleneck_station=bottleneck_name,
            bottleneck_cycle_seconds=round(bottleneck_cycle, 1),
            line_capacity_units_per_hour=round(line_capacity, 1),
            stations_starved=stations_starved,
            stations_blocked=stations_blocked,
            severity=severity,
            cost_impact_per_hour=round(cost_impact, 2),
        )

    def get_takt_performance_trend(self, work_center_id: str,
                                    takt_target_seconds: float,
                                    periods: int = 12,
                                    period_type: str = 'daily') -> List[TaktPerformanceTrend]:
        """Get historical takt performance trending."""
        if period_type == 'hourly':
            period_format = '%Y-%m-%d %H:00'
            delta = timedelta(hours=periods)
        elif period_type == 'weekly':
            period_format = '%Y-W%W'
            delta = timedelta(weeks=periods)
        else:
            period_format = '%Y-%m-%d'
            delta = timedelta(days=periods)

        cutoff = datetime.utcnow() - delta
        records = self._query_recent_records(work_center_id, cutoff)

        if not records:
            return []

        grouped: Dict[str, List[Dict]] = defaultdict(list)
        for record in records:
            ts = datetime.fromisoformat(record['timestamp'])
            period_key = ts.strftime(period_format)
            grouped[period_key].append(record)

        trends = []
        for period, period_records in sorted(grouped.items()):
            cycles = [r['cycle_seconds'] for r in period_records]
            avg_cycle = statistics.mean(cycles)
            on_takt_count = sum(1 for c in cycles if c <= takt_target_seconds * 1.05)

            trends.append(TaktPerformanceTrend(
                period=period,
                takt_target_seconds=takt_target_seconds,
                actual_avg_seconds=round(avg_cycle, 1),
                deviation_pct=round(((avg_cycle - takt_target_seconds) / takt_target_seconds) * 100, 1)
                if takt_target_seconds > 0 else 0,
                on_takt_pct=round(on_takt_count / len(period_records) * 100, 1),
                sample_count=len(period_records),
            ))

        return trends

    def get_multi_line_comparison(self, line_configs: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Compare takt performance across multiple production lines."""
        comparisons = []
        for config in line_configs:
            line_id = config.get('line_id', 'Unknown')
            work_centers = config.get('work_centers', [])
            takt_target = config.get('takt_target_seconds', 60)

            line_cycles = []
            for wc_id in work_centers:
                status = self.get_realtime_takt_status(wc_id, takt_target)
                if status.actual_cycle_seconds > 0:
                    line_cycles.append(status.actual_cycle_seconds)

            if line_cycles:
                avg_cycle = statistics.mean(line_cycles)
                max_cycle = max(line_cycles)
                comparisons.append({
                    'line_id': line_id,
                    'takt_target': takt_target,
                    'avg_cycle': round(avg_cycle, 1),
                    'max_cycle': round(max_cycle, 1),
                    'deviation_pct': round(((avg_cycle - takt_target) / takt_target) * 100, 1)
                    if takt_target > 0 else 0,
                    'on_takt': max_cycle <= takt_target * 1.05,
                    'work_center_count': len(work_centers),
                })

        return {
            'comparison_timestamp': datetime.utcnow().isoformat(),
            'lines': comparisons,
            'best_performing': min(comparisons, key=lambda x: x['deviation_pct'])['line_id']
            if comparisons else None,
            'needs_attention': [c['line_id'] for c in comparisons if c['deviation_pct'] > 10],
        }
