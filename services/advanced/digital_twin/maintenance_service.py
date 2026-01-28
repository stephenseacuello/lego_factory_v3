"""
Predictive Maintenance Service - Equipment health monitoring and prediction.

Handles:
- Equipment health scoring
- Failure prediction
- Maintenance scheduling
- Anomaly detection
"""

from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from dataclasses import dataclass
from enum import Enum
import logging
import math

from sqlalchemy.orm import Session
from sqlalchemy import func

from models import WorkCenter
from models.analytics import DigitalTwinState, OEEEvent
from models.manufacturing import MaintenanceRecord

logger = logging.getLogger(__name__)


class HealthStatus(Enum):
    """Equipment health status."""
    EXCELLENT = "excellent"    # 90-100%
    GOOD = "good"              # 70-90%
    FAIR = "fair"              # 50-70%
    POOR = "poor"              # 30-50%
    CRITICAL = "critical"      # 0-30%


class MaintenanceType(Enum):
    """Types of maintenance."""
    PREVENTIVE = "preventive"
    PREDICTIVE = "predictive"
    CORRECTIVE = "corrective"
    EMERGENCY = "emergency"


@dataclass
class HealthScore:
    """Equipment health score."""
    overall: float
    status: HealthStatus
    components: Dict[str, float]
    recommendations: List[str]


@dataclass
class MaintenanceRecommendation:
    """Maintenance action recommendation."""
    work_center_id: str
    maintenance_type: MaintenanceType
    priority: str
    action: str
    reason: str
    estimated_hours: float
    due_date: datetime


class PredictiveMaintenanceService:
    """Predictive maintenance service."""

    # Thresholds for health scoring
    RUNTIME_THRESHOLD_HOURS = 1000  # Hours before recommended service
    DOWNTIME_THRESHOLD = 0.15  # 15% downtime triggers concern
    QUALITY_THRESHOLD = 0.95  # Quality below 95% triggers concern
    TEMP_VARIANCE_THRESHOLD = 10  # Temperature variance in C

    def __init__(self, session: Session):
        self.session = session

    def calculate_health_score(
        self,
        work_center_id: str
    ) -> HealthScore:
        """
        Calculate equipment health score.

        Uses multiple factors:
        - Runtime since last maintenance
        - Recent downtime frequency
        - Quality metrics
        - Temperature stability
        """
        work_center = self.session.query(WorkCenter).filter(
            WorkCenter.id == work_center_id
        ).first()

        if not work_center:
            raise ValueError(f"Work center {work_center_id} not found")

        scores = {}
        recommendations = []

        # 1. Runtime score
        total_runtime = float(work_center.total_runtime_hours or 0)
        last_maintenance = work_center.last_maintenance

        if last_maintenance:
            hours_since_maintenance = (datetime.utcnow() - last_maintenance).total_seconds() / 3600
        else:
            hours_since_maintenance = total_runtime

        runtime_score = max(0, 100 - (hours_since_maintenance / self.RUNTIME_THRESHOLD_HOURS * 100))
        scores['runtime'] = runtime_score

        if runtime_score < 30:
            recommendations.append("Schedule preventive maintenance - high runtime since last service")

        # 2. Downtime score
        week_ago = datetime.utcnow() - timedelta(weeks=1)
        downtime_events = self.session.query(OEEEvent).filter(
            OEEEvent.work_center_id == work_center_id,
            OEEEvent.event_type == 'downtime',
            OEEEvent.start_time >= week_ago
        ).all()

        total_downtime_hours = sum(
            (e.end_time - e.start_time).total_seconds() / 3600
            for e in downtime_events if e.end_time
        )

        # Assume 168 hours in a week * efficiency
        expected_uptime = 168 * (work_center.efficiency_percent or 85) / 100
        downtime_ratio = total_downtime_hours / expected_uptime if expected_uptime > 0 else 0
        downtime_score = max(0, 100 - (downtime_ratio / self.DOWNTIME_THRESHOLD * 100))
        scores['downtime'] = downtime_score

        if downtime_score < 50:
            recommendations.append("Investigate frequent downtime - check for recurring issues")

        # 3. Quality score
        production_events = self.session.query(OEEEvent).filter(
            OEEEvent.work_center_id == work_center_id,
            OEEEvent.event_type == 'production',
            OEEEvent.start_time >= week_ago
        ).all()

        total_produced = sum(e.parts_produced or 0 for e in production_events)
        total_defects = sum(e.parts_defective or 0 for e in production_events)

        if total_produced > 0:
            quality_rate = (total_produced - total_defects) / total_produced
            quality_score = quality_rate * 100
        else:
            quality_score = 100

        scores['quality'] = quality_score

        if quality_score < 95:
            recommendations.append("Quality degradation detected - check calibration and tooling")

        # 4. Temperature stability score
        temp_states = self.session.query(DigitalTwinState).filter(
            DigitalTwinState.work_center_id == work_center_id,
            DigitalTwinState.state_type == 'temperature',
            DigitalTwinState.timestamp >= week_ago
        ).all()

        if temp_states:
            temps = []
            for s in temp_states:
                if isinstance(s.state_data, dict):
                    temps.extend([v for v in s.state_data.values() if isinstance(v, (int, float))])

            if temps:
                avg_temp = sum(temps) / len(temps)
                variance = sum((t - avg_temp) ** 2 for t in temps) / len(temps)
                std_dev = math.sqrt(variance)

                temp_score = max(0, 100 - (std_dev / self.TEMP_VARIANCE_THRESHOLD * 100))
            else:
                temp_score = 100
        else:
            temp_score = 100  # No data = assume OK

        scores['temperature'] = temp_score

        if temp_score < 70:
            recommendations.append("Temperature instability - check heaters and thermal components")

        # Calculate overall score (weighted average)
        weights = {
            'runtime': 0.25,
            'downtime': 0.30,
            'quality': 0.30,
            'temperature': 0.15
        }

        overall = sum(scores[k] * weights[k] for k in weights)

        # Determine status
        if overall >= 90:
            status = HealthStatus.EXCELLENT
        elif overall >= 70:
            status = HealthStatus.GOOD
        elif overall >= 50:
            status = HealthStatus.FAIR
        elif overall >= 30:
            status = HealthStatus.POOR
        else:
            status = HealthStatus.CRITICAL

        return HealthScore(
            overall=round(overall, 1),
            status=status,
            components={k: round(v, 1) for k, v in scores.items()},
            recommendations=recommendations
        )

    def get_maintenance_schedule(
        self,
        work_center_id: Optional[str] = None,
        include_completed: bool = False
    ) -> List[Dict[str, Any]]:
        """Get maintenance schedule."""
        query = self.session.query(MaintenanceRecord)

        if work_center_id:
            query = query.filter(MaintenanceRecord.work_center_id == work_center_id)

        if not include_completed:
            query = query.filter(MaintenanceRecord.status != 'completed')

        records = query.order_by(MaintenanceRecord.scheduled_date).all()

        return [
            {
                'id': str(r.id),
                'work_center_id': str(r.work_center_id),
                'maintenance_type': r.maintenance_type,
                'description': r.description,
                'status': r.status,
                'scheduled_date': r.scheduled_date.isoformat() if r.scheduled_date else None,
                'completed_date': r.completed_date.isoformat() if r.completed_date else None,
                'estimated_hours': r.estimated_hours,
                'actual_hours': r.actual_hours,
                'cost': float(r.cost) if r.cost else 0
            }
            for r in records
        ]

    def generate_recommendations(
        self,
        work_center_id: Optional[str] = None
    ) -> List[MaintenanceRecommendation]:
        """Generate maintenance recommendations based on equipment health."""
        if work_center_id:
            work_centers = [self.session.query(WorkCenter).filter(
                WorkCenter.id == work_center_id
            ).first()]
        else:
            work_centers = self.session.query(WorkCenter).all()

        recommendations = []

        for wc in work_centers:
            if not wc:
                continue

            try:
                health = self.calculate_health_score(str(wc.id))
            except Exception as e:
                logger.warning(f"Could not calculate health for {wc.code}: {e}")
                continue

            # Generate recommendations based on health
            if health.status == HealthStatus.CRITICAL:
                recommendations.append(MaintenanceRecommendation(
                    work_center_id=str(wc.id),
                    maintenance_type=MaintenanceType.EMERGENCY,
                    priority='CRITICAL',
                    action=f"Immediate maintenance required for {wc.code}",
                    reason=f"Health score critical ({health.overall}%)",
                    estimated_hours=4.0,
                    due_date=datetime.utcnow()
                ))

            elif health.status == HealthStatus.POOR:
                recommendations.append(MaintenanceRecommendation(
                    work_center_id=str(wc.id),
                    maintenance_type=MaintenanceType.PREDICTIVE,
                    priority='HIGH',
                    action=f"Schedule maintenance for {wc.code}",
                    reason=f"Health score poor ({health.overall}%)",
                    estimated_hours=2.0,
                    due_date=datetime.utcnow() + timedelta(days=3)
                ))

            elif health.status == HealthStatus.FAIR:
                recommendations.append(MaintenanceRecommendation(
                    work_center_id=str(wc.id),
                    maintenance_type=MaintenanceType.PREVENTIVE,
                    priority='MEDIUM',
                    action=f"Plan maintenance for {wc.code}",
                    reason=f"Health score fair ({health.overall}%)",
                    estimated_hours=1.0,
                    due_date=datetime.utcnow() + timedelta(weeks=1)
                ))

            # Check for overdue maintenance
            if wc.next_maintenance and wc.next_maintenance < datetime.utcnow():
                recommendations.append(MaintenanceRecommendation(
                    work_center_id=str(wc.id),
                    maintenance_type=MaintenanceType.PREVENTIVE,
                    priority='HIGH',
                    action=f"Overdue maintenance for {wc.code}",
                    reason=f"Scheduled maintenance past due: {wc.next_maintenance.date()}",
                    estimated_hours=2.0,
                    due_date=datetime.utcnow()
                ))

        # Sort by priority
        priority_order = {'CRITICAL': 0, 'HIGH': 1, 'MEDIUM': 2, 'LOW': 3}
        recommendations.sort(key=lambda x: (priority_order.get(x.priority, 4), x.due_date))

        return recommendations

    def schedule_maintenance(
        self,
        work_center_id: str,
        maintenance_type: str,
        description: str,
        scheduled_date: datetime,
        estimated_hours: float = 2.0
    ) -> MaintenanceRecord:
        """Schedule a maintenance task."""
        record = MaintenanceRecord(
            work_center_id=work_center_id,
            maintenance_type=maintenance_type,
            description=description,
            status='scheduled',
            scheduled_date=scheduled_date,
            estimated_hours=estimated_hours
        )

        self.session.add(record)
        self.session.commit()

        # Update work center next maintenance date
        work_center = self.session.query(WorkCenter).filter(
            WorkCenter.id == work_center_id
        ).first()

        if work_center:
            work_center.next_maintenance = scheduled_date
            self.session.commit()

        return record

    def complete_maintenance(
        self,
        maintenance_id: str,
        actual_hours: float,
        cost: float = 0,
        notes: Optional[str] = None
    ) -> MaintenanceRecord:
        """Complete a maintenance task."""
        record = self.session.query(MaintenanceRecord).filter(
            MaintenanceRecord.id == maintenance_id
        ).first()

        if not record:
            raise ValueError(f"Maintenance record {maintenance_id} not found")

        record.status = 'completed'
        record.completed_date = datetime.utcnow()
        record.actual_hours = actual_hours
        record.cost = cost
        if notes:
            record.notes = notes

        # Update work center last maintenance date
        work_center = self.session.query(WorkCenter).filter(
            WorkCenter.id == record.work_center_id
        ).first()

        if work_center:
            work_center.last_maintenance = datetime.utcnow()
            # Schedule next maintenance
            work_center.next_maintenance = datetime.utcnow() + timedelta(
                hours=self.RUNTIME_THRESHOLD_HOURS
            )

        self.session.commit()
        return record

    def get_health_dashboard(self) -> Dict[str, Any]:
        """Get health dashboard for all equipment."""
        work_centers = self.session.query(WorkCenter).all()

        dashboard = []
        summary = {
            'excellent': 0,
            'good': 0,
            'fair': 0,
            'poor': 0,
            'critical': 0
        }

        for wc in work_centers:
            try:
                health = self.calculate_health_score(str(wc.id))
                dashboard.append({
                    'work_center_id': str(wc.id),
                    'work_center_code': wc.code,
                    'work_center_name': wc.name,
                    'health_score': health.overall,
                    'status': health.status.value,
                    'components': health.components,
                    'recommendations': health.recommendations
                })
                summary[health.status.value] += 1

            except Exception as e:
                dashboard.append({
                    'work_center_id': str(wc.id),
                    'work_center_code': wc.code,
                    'work_center_name': wc.name,
                    'error': str(e)
                })

        return {
            'generated_at': datetime.utcnow().isoformat(),
            'summary': summary,
            'equipment': dashboard
        }
