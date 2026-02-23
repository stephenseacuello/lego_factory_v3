"""
MES Machine Feedback Service
============================
Real-time machine event processing for automatic job status transitions.

Subscribes to SCADA machine events and automatically updates job statuses:
- Job completion signals → Mark job COMPLETED
- Partial completion → Update quantity_completed
- Machine faults → Mark job FAILED or ON_HOLD
- Scrap counts → Update quantity_defective
"""

import logging
from datetime import datetime
from typing import Dict, Any, Optional, List
from enum import Enum

from sqlalchemy.orm import Session
from sqlalchemy import and_

from config.database import get_db_session

logger = logging.getLogger(__name__)


class MachineEventType(str, Enum):
    """Types of machine events that trigger job updates."""
    JOB_COMPLETE = 'job_complete'
    JOB_STARTED = 'job_started'
    PARTIAL_COMPLETE = 'partial_complete'
    SCRAP_REPORTED = 'scrap_reported'
    MACHINE_FAULT = 'machine_fault'
    MACHINE_RECOVERED = 'machine_recovered'
    QUALITY_HOLD = 'quality_hold'
    SETUP_COMPLETE = 'setup_complete'


class MachineFeedbackService:
    """
    Processes machine events and updates MES job statuses automatically.

    This service bridges SCADA (Level 2) and MES (Level 3) by:
    1. Listening for machine completion events
    2. Validating event data
    3. Updating job records
    4. Emitting WebSocket notifications
    5. Triggering downstream workflows (genealogy, quality, etc.)
    """

    def __init__(self, session: Session):
        self.session = session

    def process_machine_event(self, event_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process incoming machine event and update relevant jobs.

        Args:
            event_data: {
                'machine_id': str,
                'event_type': MachineEventType,
                'job_id': str (optional - auto-detect from machine if not provided),
                'quantity_completed': int (for partial/complete),
                'quantity_defective': int (for scrap),
                'timestamp': datetime,
                'parameters': dict (optional - machine parameters at event time)
            }

        Returns:
            Processing result with updated job info
        """
        from models.mes.work_orders import Job, JobStatus
        from models.scada.machines import Machine

        event_type = event_data.get('event_type')
        machine_id = event_data.get('machine_id')
        job_id = event_data.get('job_id')
        timestamp = event_data.get('timestamp', datetime.utcnow())

        if not machine_id:
            return {'success': False, 'error': 'machine_id is required'}

        # Get machine
        machine = self.session.query(Machine).filter(
            Machine.machine_id == machine_id
        ).first()

        if not machine:
            return {'success': False, 'error': f'Machine {machine_id} not found'}

        # If no job_id provided, find the running job on this machine
        if not job_id:
            job = self.session.query(Job).filter(
                and_(
                    Job.machine_id == machine_id,
                    Job.status == JobStatus.RUNNING
                )
            ).first()
            if job:
                job_id = str(job.id)
        else:
            job = self.session.query(Job).filter(Job.id == job_id).first()

        if not job and event_type in [
            MachineEventType.JOB_COMPLETE,
            MachineEventType.PARTIAL_COMPLETE,
            MachineEventType.SCRAP_REPORTED
        ]:
            return {'success': False, 'error': f'No running job found for machine {machine_id}'}

        # Process based on event type
        handler = getattr(self, f'_handle_{event_type}', None)
        if handler:
            return handler(job, machine, event_data, timestamp)
        else:
            logger.warning(f"Unknown event type: {event_type}")
            return {'success': False, 'error': f'Unknown event type: {event_type}'}

    def _handle_job_complete(
        self, job, machine, event_data: Dict, timestamp: datetime
    ) -> Dict[str, Any]:
        """Handle job completion event."""
        from models.mes.work_orders import Job, JobStatus, WorkOrder, WorkOrderStatus

        if not job:
            return {'success': False, 'error': 'No job to complete'}

        quantity_completed = event_data.get('quantity_completed', job.quantity_required)
        quantity_defective = event_data.get('quantity_defective', 0)

        # Update job
        job.status = JobStatus.COMPLETED
        job.actual_end = timestamp
        job.quantity_completed = quantity_completed
        job.quantity_defective = quantity_defective

        # Calculate actual duration
        if job.actual_start:
            duration_seconds = (timestamp - job.actual_start).total_seconds()
            job.actual_duration = duration_seconds / 60  # Convert to minutes

        self.session.flush()

        # Check if all jobs for work order are complete
        work_order = self.session.query(WorkOrder).filter(
            WorkOrder.id == job.work_order_id
        ).first()

        if work_order:
            all_jobs_complete = all(
                j.status == JobStatus.COMPLETED
                for j in work_order.jobs
            )
            if all_jobs_complete:
                work_order.status = WorkOrderStatus.COMPLETED
                work_order.actual_end = timestamp
                self._emit_event('work_order_completed', {
                    'work_order_id': str(work_order.id),
                    'work_order_number': work_order.work_order_number
                })

        # Emit job completion event
        self._emit_event('job_completed', {
            'job_id': str(job.id),
            'machine_id': machine.machine_id,
            'quantity_completed': quantity_completed,
            'quantity_defective': quantity_defective,
            'duration_minutes': job.actual_duration
        })

        # Update machine status to IDLE
        self._update_machine_status(machine, 'IDLE', None)

        # Track cycle time variance and trigger re-optimization if needed
        variance_info = self._track_cycle_time_variance(job)
        if variance_info.get('needs_reoptimization'):
            self._trigger_schedule_reoptimization(job, variance_info)

        return {
            'success': True,
            'job_id': str(job.id),
            'new_status': 'COMPLETED',
            'quantity_completed': quantity_completed,
            'quantity_defective': quantity_defective,
            'cycle_time_variance': variance_info
        }

    def _handle_job_started(
        self, job, machine, event_data: Dict, timestamp: datetime
    ) -> Dict[str, Any]:
        """Handle job started event from machine."""
        from models.mes.work_orders import Job, JobStatus

        job_id = event_data.get('job_id')
        if not job_id:
            return {'success': False, 'error': 'job_id required for job_started event'}

        job = self.session.query(Job).filter(Job.id == job_id).first()
        if not job:
            return {'success': False, 'error': f'Job {job_id} not found'}

        job.status = JobStatus.RUNNING
        job.actual_start = timestamp
        job.machine_id = machine.machine_id

        self.session.flush()

        # Update machine status
        self._update_machine_status(machine, 'RUNNING', job)

        self._emit_event('job_started', {
            'job_id': str(job.id),
            'machine_id': machine.machine_id,
            'work_order_id': str(job.work_order_id)
        })

        return {
            'success': True,
            'job_id': str(job.id),
            'new_status': 'RUNNING'
        }

    def _handle_partial_complete(
        self, job, machine, event_data: Dict, timestamp: datetime
    ) -> Dict[str, Any]:
        """Handle partial completion (incremental count update)."""
        if not job:
            return {'success': False, 'error': 'No job for partial completion'}

        quantity_completed = event_data.get('quantity_completed', 0)

        # Increment completed count
        job.quantity_completed = (job.quantity_completed or 0) + quantity_completed

        self.session.flush()

        self._emit_event('job_progress', {
            'job_id': str(job.id),
            'machine_id': machine.machine_id,
            'quantity_completed': job.quantity_completed,
            'quantity_required': job.quantity_required,
            'progress_pct': round(job.quantity_completed / job.quantity_required * 100, 1) if job.quantity_required else 0
        })

        return {
            'success': True,
            'job_id': str(job.id),
            'total_completed': job.quantity_completed
        }

    def _handle_scrap_reported(
        self, job, machine, event_data: Dict, timestamp: datetime
    ) -> Dict[str, Any]:
        """Handle scrap/defective count report."""
        if not job:
            return {'success': False, 'error': 'No job for scrap report'}

        quantity_defective = event_data.get('quantity_defective', 0)
        scrap_reason = event_data.get('scrap_reason', 'unspecified')

        # Increment defective count
        job.quantity_defective = (job.quantity_defective or 0) + quantity_defective

        self.session.flush()

        self._emit_event('scrap_reported', {
            'job_id': str(job.id),
            'machine_id': machine.machine_id,
            'quantity_defective': quantity_defective,
            'total_defective': job.quantity_defective,
            'reason': scrap_reason
        })

        return {
            'success': True,
            'job_id': str(job.id),
            'total_defective': job.quantity_defective
        }

    def _handle_machine_fault(
        self, job, machine, event_data: Dict, timestamp: datetime
    ) -> Dict[str, Any]:
        """Handle machine fault - put job on hold."""
        from models.mes.work_orders import JobStatus

        fault_code = event_data.get('fault_code', 'UNKNOWN')
        fault_message = event_data.get('fault_message', '')

        result = {
            'success': True,
            'machine_id': machine.machine_id,
            'fault_code': fault_code
        }

        if job:
            job.status = JobStatus.ON_HOLD
            job.runtime_data = job.runtime_data or {}
            job.runtime_data['fault_info'] = {
                'code': fault_code,
                'message': fault_message,
                'timestamp': timestamp.isoformat()
            }
            self.session.flush()
            result['job_id'] = str(job.id)
            result['job_status'] = 'ON_HOLD'

        self._update_machine_status(machine, 'DOWN', None)

        self._emit_event('machine_fault', {
            'machine_id': machine.machine_id,
            'job_id': str(job.id) if job else None,
            'fault_code': fault_code,
            'fault_message': fault_message
        })

        return result

    def _handle_machine_recovered(
        self, job, machine, event_data: Dict, timestamp: datetime
    ) -> Dict[str, Any]:
        """Handle machine recovery after fault."""
        from models.mes.work_orders import JobStatus

        result = {
            'success': True,
            'machine_id': machine.machine_id
        }

        # Find any jobs that were on hold due to this machine
        if job and job.status == JobStatus.ON_HOLD:
            # Check if fault_info exists (was held due to machine fault)
            if job.runtime_data and job.runtime_data.get('fault_info'):
                job.status = JobStatus.RUNNING
                job.runtime_data.pop('fault_info', None)
                self.session.flush()
                result['job_id'] = str(job.id)
                result['job_status'] = 'RUNNING'

        self._update_machine_status(machine, 'IDLE' if not job else 'RUNNING', job)

        self._emit_event('machine_recovered', {
            'machine_id': machine.machine_id,
            'job_id': str(job.id) if job else None
        })

        return result

    def _handle_quality_hold(
        self, job, machine, event_data: Dict, timestamp: datetime
    ) -> Dict[str, Any]:
        """Handle quality hold request."""
        from models.mes.work_orders import JobStatus

        if not job:
            return {'success': False, 'error': 'No job for quality hold'}

        hold_reason = event_data.get('hold_reason', 'quality inspection required')

        job.status = JobStatus.ON_HOLD
        job.runtime_data = job.runtime_data or {}
        job.runtime_data['quality_hold'] = {
            'reason': hold_reason,
            'timestamp': timestamp.isoformat()
        }

        self.session.flush()

        self._emit_event('quality_hold', {
            'job_id': str(job.id),
            'machine_id': machine.machine_id,
            'reason': hold_reason
        })

        return {
            'success': True,
            'job_id': str(job.id),
            'new_status': 'ON_HOLD'
        }

    def _handle_setup_complete(
        self, job, machine, event_data: Dict, timestamp: datetime
    ) -> Dict[str, Any]:
        """Handle setup completion event."""
        setup_duration = event_data.get('setup_duration_minutes', 0)

        self._update_machine_status(machine, 'IDLE', None)

        self._emit_event('setup_complete', {
            'machine_id': machine.machine_id,
            'duration_minutes': setup_duration
        })

        return {
            'success': True,
            'machine_id': machine.machine_id,
            'setup_duration_minutes': setup_duration
        }

    def _update_machine_status(self, machine, status: str, job: Optional[Any]):
        """Update machine status in resource tracking."""
        try:
            from services.mes.resource_service import ResourceService
            with get_db_session() as session:
                resource_service = ResourceService(session)
                resource_service.update_machine_status(
                    machine_id=machine.machine_id,
                    status=status,
                    current_job_id=str(job.id) if job else None,
                    current_work_order_id=str(job.work_order_id) if job else None
                )
        except Exception as e:
            logger.warning(f"Failed to update machine status: {e}")

    def _emit_event(self, event_type: str, data: Dict[str, Any]):
        """Emit WebSocket event for real-time UI updates."""
        try:
            from app import socketio
            socketio.emit(event_type, data, namespace='/dashboard')
        except Exception as e:
            logger.debug(f"WebSocket emit failed (may not be initialized): {e}")

    def _track_cycle_time_variance(self, job) -> Dict[str, Any]:
        """
        Track variance between planned and actual cycle times.

        Returns:
            Dict with variance info and whether re-optimization is needed
        """
        # Thresholds for variance alerts
        MINOR_VARIANCE_PCT = 15  # 15% variance
        MAJOR_VARIANCE_PCT = 30  # 30% variance
        REOPT_THRESHOLD_PCT = 25  # Trigger re-optimization at 25%

        result = {
            'planned_duration_minutes': None,
            'actual_duration_minutes': None,
            'variance_minutes': None,
            'variance_percent': None,
            'severity': 'on_time',
            'needs_reoptimization': False
        }

        # Get planned duration from scheduled times
        if job.scheduled_start and job.scheduled_end:
            planned_duration = (job.scheduled_end - job.scheduled_start).total_seconds() / 60
            result['planned_duration_minutes'] = round(planned_duration, 1)

        # Get actual duration
        if job.actual_start and job.actual_end:
            actual_duration = (job.actual_end - job.actual_start).total_seconds() / 60
            result['actual_duration_minutes'] = round(actual_duration, 1)

        # Calculate variance
        if result['planned_duration_minutes'] and result['actual_duration_minutes']:
            variance = result['actual_duration_minutes'] - result['planned_duration_minutes']
            result['variance_minutes'] = round(variance, 1)

            if result['planned_duration_minutes'] > 0:
                variance_pct = (variance / result['planned_duration_minutes']) * 100
                result['variance_percent'] = round(variance_pct, 1)

                # Determine severity
                if abs(variance_pct) >= MAJOR_VARIANCE_PCT:
                    result['severity'] = 'major'
                elif abs(variance_pct) >= MINOR_VARIANCE_PCT:
                    result['severity'] = 'minor'

                # Check if re-optimization is needed
                if abs(variance_pct) >= REOPT_THRESHOLD_PCT:
                    result['needs_reoptimization'] = True

        # Update time estimates for future scheduling
        try:
            from services.mes.scheduling_service import SchedulingService
            sched_service = SchedulingService(self.session)
            sched_service.update_time_estimates_from_actuals(job.job_id)
        except Exception as e:
            logger.warning(f"Failed to update time estimates: {e}")

        # Emit variance event for monitoring
        if result['severity'] != 'on_time':
            self._emit_event('cycle_time_variance', {
                'job_id': str(job.id),
                'machine_id': job.machine_id,
                'variance_minutes': result['variance_minutes'],
                'variance_percent': result['variance_percent'],
                'severity': result['severity']
            })

        return result

    def _trigger_schedule_reoptimization(self, completed_job, variance_info: Dict[str, Any]):
        """
        Trigger schedule re-optimization when significant variance detected.

        This adjusts downstream job schedules when a job completes
        significantly early or late.
        """
        from models.mes.work_orders import Job, JobStatus

        try:
            # Find downstream jobs that might be affected
            affected_jobs = self.session.query(Job).filter(
                Job.status.in_([JobStatus.PENDING, JobStatus.QUEUED]),
                Job.machine_id == completed_job.machine_id,
                Job.scheduled_start != None
            ).order_by(Job.scheduled_start).all()

            if not affected_jobs:
                return

            # Calculate time shift
            shift_minutes = variance_info.get('variance_minutes', 0)

            # Shift downstream job schedules
            from datetime import timedelta
            shift_delta = timedelta(minutes=abs(shift_minutes))

            updated_count = 0
            for job in affected_jobs:
                if shift_minutes > 0:
                    # Job ran late - shift downstream jobs later
                    job.scheduled_start = job.scheduled_start + shift_delta
                    if job.scheduled_end:
                        job.scheduled_end = job.scheduled_end + shift_delta
                else:
                    # Job ran early - shift downstream jobs earlier
                    job.scheduled_start = job.scheduled_start - shift_delta
                    if job.scheduled_end:
                        job.scheduled_end = job.scheduled_end - shift_delta
                updated_count += 1

            self.session.flush()

            logger.info(
                f"Re-optimized schedule: shifted {updated_count} jobs by "
                f"{shift_minutes} minutes due to variance on job {completed_job.job_id}"
            )

            # Emit schedule update event
            self._emit_event('schedule_reoptimized', {
                'trigger_job_id': str(completed_job.id),
                'machine_id': completed_job.machine_id,
                'shift_minutes': shift_minutes,
                'jobs_affected': updated_count,
                'reason': f"Cycle time variance: {variance_info.get('variance_percent', 0):.1f}%"
            })

        except Exception as e:
            logger.error(f"Schedule re-optimization failed: {e}")

    def get_cycle_time_statistics(
        self,
        machine_id: str = None,
        operation_type: str = None,
        days: int = 7
    ) -> Dict[str, Any]:
        """
        Get cycle time statistics for analysis.

        Args:
            machine_id: Filter by machine
            operation_type: Filter by operation type
            days: Number of days to analyze

        Returns:
            Statistics including average, std dev, min, max variance
        """
        from models.mes.work_orders import Job, JobStatus
        from datetime import timedelta

        cutoff = datetime.utcnow() - timedelta(days=days)

        query = self.session.query(Job).filter(
            Job.status == JobStatus.COMPLETED,
            Job.actual_start != None,
            Job.actual_end != None,
            Job.scheduled_start != None,
            Job.scheduled_end != None,
            Job.actual_end >= cutoff
        )

        if machine_id:
            query = query.filter(Job.machine_id == machine_id)
        if operation_type:
            query = query.filter(Job.operation_name == operation_type)

        jobs = query.all()

        if not jobs:
            return {
                'job_count': 0,
                'average_variance_minutes': 0,
                'average_variance_percent': 0,
                'min_variance_minutes': 0,
                'max_variance_minutes': 0,
                'on_time_percent': 100
            }

        variances = []
        variance_percents = []
        on_time_count = 0

        for job in jobs:
            planned = (job.scheduled_end - job.scheduled_start).total_seconds() / 60
            actual = (job.actual_end - job.actual_start).total_seconds() / 60
            variance = actual - planned

            variances.append(variance)
            if planned > 0:
                variance_percents.append((variance / planned) * 100)

            if abs(variance) < 15:  # Within 15 minutes
                on_time_count += 1

        import statistics

        return {
            'job_count': len(jobs),
            'average_variance_minutes': round(statistics.mean(variances), 1) if variances else 0,
            'average_variance_percent': round(statistics.mean(variance_percents), 1) if variance_percents else 0,
            'std_dev_minutes': round(statistics.stdev(variances), 1) if len(variances) > 1 else 0,
            'min_variance_minutes': round(min(variances), 1) if variances else 0,
            'max_variance_minutes': round(max(variances), 1) if variances else 0,
            'on_time_percent': round((on_time_count / len(jobs)) * 100, 1)
        }

    def get_pending_completions(self, machine_id: str = None) -> List[Dict[str, Any]]:
        """Get jobs that may need manual completion confirmation."""
        from models.mes.work_orders import Job, JobStatus

        query = self.session.query(Job).filter(
            Job.status == JobStatus.RUNNING
        )

        if machine_id:
            query = query.filter(Job.machine_id == machine_id)

        jobs = query.all()

        return [{
            'job_id': str(j.id),
            'machine_id': j.machine_id,
            'work_order_id': str(j.work_order_id),
            'operation_name': j.operation_name,
            'quantity_required': j.quantity_required,
            'quantity_completed': j.quantity_completed or 0,
            'actual_start': j.actual_start.isoformat() if j.actual_start else None,
            'scheduled_end': j.scheduled_end.isoformat() if j.scheduled_end else None
        } for j in jobs]


# Convenience functions for API usage
def process_machine_event(event_data: Dict[str, Any]) -> Dict[str, Any]:
    """Process a machine event (standalone function)."""
    with get_db_session() as session:
        service = MachineFeedbackService(session)
        return service.process_machine_event(event_data)


def get_pending_completions(machine_id: str = None) -> List[Dict[str, Any]]:
    """Get pending job completions."""
    with get_db_session() as session:
        service = MachineFeedbackService(session)
        return service.get_pending_completions(machine_id)
