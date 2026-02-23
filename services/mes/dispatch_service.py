"""
LEGO Factory v3 - Dispatch Service
===================================
Real-time job dispatching for MESA-11 Dispatching Production Units function.
Handles job assignment, preemption, and auto-dispatch on machine idle.
"""

import logging
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Tuple
from dataclasses import dataclass

from sqlalchemy.orm import Session
from sqlalchemy import and_, or_

logger = logging.getLogger(__name__)


def _emit_dispatch_event(event_type: str, data: Dict[str, Any]):
    """Emit dispatch event to WebSocket clients."""
    try:
        from services.websocket.socket_service import emit_to_namespace
        emit_to_namespace(event_type, data, namespace='/dashboard')
    except ImportError:
        pass
    except Exception as e:
        logger.warning(f"Failed to emit dispatch event: {e}")


@dataclass
class DispatchResult:
    """Result of a dispatch operation."""
    success: bool
    job_id: Optional[str]
    machine_id: Optional[str]
    message: str
    previous_status: Optional[str] = None
    new_status: Optional[str] = None


class DispatchRuleConfig:
    """Configuration for machine/work center dispatch rules."""

    # Default rules by machine type or work center
    DEFAULT_RULES = {
        '_default': 'wspt',
        'fdm': 'setup_min',       # FDM printers: minimize material changes
        'cnc': 'spt',             # CNC: shortest processing time
        'assembly': 'edd',        # Assembly: earliest due date
        'quality': 'fifo',        # QC: first in first out
        'packaging': 'fifo',      # Packaging: FIFO
    }

    # Composite rule weights for advanced scheduling
    COMPOSITE_CONFIGS = {
        'balanced': {'spt': 0.3, 'edd': 0.4, 'wspt': 0.3},
        'urgent_first': {'edd': 0.6, 'cr': 0.3, 'wspt': 0.1},
        'efficient': {'spt': 0.4, 'setup_min': 0.4, 'wspt': 0.2},
    }


class DispatchService:
    """
    Service for dispatching jobs to machines.

    Responsibilities:
    - Validate machine eligibility and availability
    - Transition job status (QUEUED -> RUNNING)
    - Update resource status
    - Reserve materials
    - Handle preemption
    - Auto-dispatch on machine idle
    - Configurable dispatch rules per machine/work center
    """

    def __init__(self, session: Session):
        self.session = session
        self._rule_cache: Dict[str, str] = {}  # machine_id -> rule_name

    def dispatch_job(
        self,
        job_id: str,
        machine_id: str,
        operator_id: Optional[str] = None,
        force: bool = False
    ) -> DispatchResult:
        """
        Dispatch a job to a specific machine.

        Args:
            job_id: Job to dispatch
            machine_id: Target machine
            operator_id: Operator performing dispatch
            force: Force dispatch even if machine is busy (for preemption)

        Returns:
            DispatchResult with success/failure and details
        """
        from models.mes.work_orders import Job, JobStatus

        # Get job
        job = self.session.query(Job).filter(Job.job_id == job_id).first()
        if not job:
            return DispatchResult(False, job_id, machine_id, "Job not found")

        # Validate job status
        if job.status not in (JobStatus.PENDING, JobStatus.QUEUED, JobStatus.PAUSED):
            return DispatchResult(
                False, job_id, machine_id,
                f"Cannot dispatch job with status '{job.status.value}'"
            )

        # Check machine eligibility
        eligible_machines = []
        if job.runtime_data:
            eligible_machines = job.runtime_data.get('eligible_machines', [])

        if eligible_machines and machine_id not in eligible_machines:
            return DispatchResult(
                False, job_id, machine_id,
                f"Machine '{machine_id}' not eligible for this job"
            )

        # Check machine availability
        if not force:
            machine_available = self._check_machine_available(machine_id)
            if not machine_available:
                return DispatchResult(
                    False, job_id, machine_id,
                    f"Machine '{machine_id}' is not available"
                )

        # Check WIP limit (MESA-1: Resource Allocation)
        if not force:
            try:
                from services.mes.wip_service import WIPService
                wip_svc = WIPService(self.session)
                wip_status = wip_svc.check_wip_limit(machine_id)
                if not wip_status.get('can_accept', True):
                    return DispatchResult(
                        False, job_id, machine_id,
                        f"WIP limit reached for {machine_id} ({wip_status.get('wip_limit', '?')} max, {wip_status.get('available_slots', 0)} available)"
                    )
            except Exception as e:
                logger.debug(f"WIP check skipped: {e}")

        # Check material availability
        material_type = None
        if job.runtime_data:
            material_type = job.runtime_data.get('material_type')

        if material_type:
            material_ok, material_msg = self._check_material_available(material_type, job_id)
            if not material_ok:
                return DispatchResult(False, job_id, machine_id, material_msg)

        # Check quality holds on machine (MESA-7: Quality Management)
        if not force:
            try:
                from models.qms.ncr_capa import NonConformanceReport, NCRStatus
                from models.mes.work_orders import Job as JobModel
                # Find active NCRs linked to jobs on this machine
                active_ncrs = self.session.query(NonConformanceReport).filter(
                    NonConformanceReport.status.in_([NCRStatus.DRAFT, NCRStatus.SUBMITTED, NCRStatus.UNDER_INVESTIGATION]),
                    NonConformanceReport.work_order_id.in_(
                        self.session.query(JobModel.work_order_id).filter(
                            JobModel.machine_id == machine_id,
                            JobModel.status.in_(['running', 'paused'])
                        )
                    )
                ).count()
                if active_ncrs > 0:
                    return DispatchResult(
                        False, job_id, machine_id,
                        f"Machine {machine_id} has {active_ncrs} active quality hold(s). Resolve NCRs before dispatching."
                    )
            except Exception as e:
                logger.debug(f"Quality hold check skipped: {e}")

        # Lock recipe for production (MESA-8: Process Management)
        try:
            from services.mes.recipe_tracking_service import RecipeTrackingService
            recipe_id = None
            if job.runtime_data:
                recipe_id = job.runtime_data.get('recipe_id')
            if recipe_id:
                recipe_svc = RecipeTrackingService(self.session)
                recipe_svc.lock_for_production(recipe_id, str(job.job_id))
                logger.debug(f"Recipe {recipe_id} locked for job {job_id}")
        except Exception as e:
            logger.debug(f"Recipe lock skipped: {e}")

        # Update job
        previous_status = job.status.value
        job.status = JobStatus.RUNNING
        job.machine_id = machine_id
        job.actual_start = datetime.utcnow()

        if job.runtime_data is None:
            job.runtime_data = {}
        job.runtime_data['dispatched_at'] = datetime.utcnow().isoformat()
        job.runtime_data['dispatched_by'] = operator_id

        # Update resource status
        self._update_resource_status(machine_id, job)

        # Record dispatch event
        self._record_dispatch_event(job, machine_id, operator_id)

        self.session.flush()

        # Emit WebSocket event
        _emit_dispatch_event('job_dispatched', {
            'job_id': job_id,
            'machine_id': machine_id,
            'operator_id': operator_id,
            'work_order_id': str(job.work_order_id),
            'timestamp': datetime.utcnow().isoformat(),
        })

        logger.info(f"Dispatched job {job_id} to machine {machine_id}")

        return DispatchResult(
            True, job_id, machine_id,
            f"Job dispatched successfully",
            previous_status=previous_status,
            new_status='running'
        )

    def auto_dispatch(
        self,
        machine_id: str,
        rule_name: str = None
    ) -> DispatchResult:
        """
        Automatically dispatch next job to an idle machine.

        Uses configured dispatching rule to select best candidate.

        Args:
            machine_id: Machine to dispatch to
            rule_name: Dispatching rule to use (None = use configured rule)

        Returns:
            DispatchResult
        """
        from services.mes.dispatching_rules import dispatch_next_job

        # Check machine is available
        if not self._check_machine_available(machine_id):
            return DispatchResult(
                False, None, machine_id,
                "Machine is not available for dispatch"
            )

        # Get candidate jobs
        candidates = self._get_dispatch_candidates(machine_id)
        if not candidates:
            return DispatchResult(
                False, None, machine_id,
                "No jobs available for dispatch"
            )

        # Get current material on machine
        current_material = self._get_machine_material(machine_id)

        # Get dispatch rule for this machine (use configured or default)
        effective_rule = rule_name or self.get_machine_dispatch_rule(machine_id)

        # Check if it's a composite rule
        composite_weights = None
        if effective_rule in DispatchRuleConfig.COMPOSITE_CONFIGS:
            composite_weights = DispatchRuleConfig.COMPOSITE_CONFIGS[effective_rule]
            effective_rule = 'composite'

        # Select best job using dispatching rule
        kwargs = {}
        if composite_weights:
            kwargs['rules_weights'] = composite_weights

        selected = dispatch_next_job(
            machine_id,
            candidates,
            rule_name=effective_rule,
            current_material=current_material,
            **kwargs
        )

        if not selected:
            return DispatchResult(
                False, None, machine_id,
                "No suitable job found"
            )

        # Dispatch selected job
        return self.dispatch_job(selected['job_id'], machine_id)

    def get_machine_dispatch_rule(self, machine_id: str) -> str:
        """
        Get the configured dispatch rule for a machine.

        Args:
            machine_id: Machine ID

        Returns:
            Rule name (e.g., 'spt', 'edd', 'wspt', 'fifo', etc.)
        """
        # Check cache first
        if machine_id in self._rule_cache:
            return self._rule_cache[machine_id]

        # Try to get from database
        if self.session:
            try:
                from models.mes.scheduling import MachineDispatchConfig

                config = self.session.query(MachineDispatchConfig).filter(
                    MachineDispatchConfig.machine_id == machine_id,
                    MachineDispatchConfig.is_active == True
                ).first()

                if config:
                    self._rule_cache[machine_id] = config.dispatch_rule
                    return config.dispatch_rule
            except ImportError:
                pass

        # Fall back to defaults by machine type
        machine_type = self._get_machine_type(machine_id)
        rule = DispatchRuleConfig.DEFAULT_RULES.get(
            machine_type,
            DispatchRuleConfig.DEFAULT_RULES['_default']
        )
        self._rule_cache[machine_id] = rule
        return rule

    def set_machine_dispatch_rule(
        self,
        machine_id: str,
        rule_name: str,
        priority_override: Dict[str, int] = None
    ) -> Dict[str, Any]:
        """
        Set the dispatch rule for a machine.

        Args:
            machine_id: Machine ID
            rule_name: Rule name ('spt', 'edd', 'wspt', 'fifo', 'setup_min',
                      'cr', 'slack', 'balanced', 'urgent_first', 'efficient')
            priority_override: Optional priority overrides by job attribute

        Returns:
            Configuration result
        """
        # Validate rule name
        valid_rules = list(DispatchRuleConfig.DEFAULT_RULES.values())
        valid_rules.extend(DispatchRuleConfig.COMPOSITE_CONFIGS.keys())
        valid_rules.extend(['spt', 'lpt', 'edd', 'cr', 'wspt', 'slack', 'fifo', 'setup_min', 'composite'])

        if rule_name not in valid_rules:
            return {
                'success': False,
                'error': f"Invalid rule '{rule_name}'. Valid: {valid_rules}"
            }

        # Update cache
        self._rule_cache[machine_id] = rule_name

        # Persist to database if available
        if self.session:
            try:
                from models.mes.scheduling import MachineDispatchConfig

                config = self.session.query(MachineDispatchConfig).filter(
                    MachineDispatchConfig.machine_id == machine_id
                ).first()

                if config:
                    config.dispatch_rule = rule_name
                    config.priority_override = priority_override
                    config.updated_at = datetime.utcnow()
                else:
                    config = MachineDispatchConfig(
                        machine_id=machine_id,
                        dispatch_rule=rule_name,
                        priority_override=priority_override,
                        is_active=True,
                        created_at=datetime.utcnow()
                    )
                    self.session.add(config)

                self.session.flush()

                logger.info(f"Set dispatch rule for {machine_id}: {rule_name}")
            except ImportError:
                pass

        _emit_dispatch_event('dispatch_rule_changed', {
            'machine_id': machine_id,
            'rule_name': rule_name,
            'timestamp': datetime.utcnow().isoformat(),
        })

        return {
            'success': True,
            'machine_id': machine_id,
            'rule_name': rule_name,
            'priority_override': priority_override
        }

    def get_all_dispatch_rules(self) -> Dict[str, Any]:
        """
        Get all configured dispatch rules.

        Returns:
            Dict with rules by machine and available rules
        """
        from services.mes.dispatching_rules import get_rule_descriptions

        machine_rules = {}

        if self.session:
            try:
                from models.mes.scheduling import MachineDispatchConfig

                configs = self.session.query(MachineDispatchConfig).filter(
                    MachineDispatchConfig.is_active == True
                ).all()

                for config in configs:
                    machine_rules[config.machine_id] = {
                        'rule': config.dispatch_rule,
                        'priority_override': config.priority_override
                    }
            except ImportError:
                pass

        return {
            'machine_rules': machine_rules,
            'available_rules': get_rule_descriptions(),
            'composite_rules': {
                name: {'weights': weights}
                for name, weights in DispatchRuleConfig.COMPOSITE_CONFIGS.items()
            },
            'default_rules': DispatchRuleConfig.DEFAULT_RULES
        }

    def _get_machine_type(self, machine_id: str) -> str:
        """Get machine type for default rule lookup."""
        # Extract type from machine_id pattern
        machine_lower = machine_id.lower()
        if 'bambu' in machine_lower or 'creality' in machine_lower or 'fdm' in machine_lower:
            return 'fdm'
        elif 'bantam' in machine_lower or 'cnc' in machine_lower:
            return 'cnc'
        elif 'assembly' in machine_lower:
            return 'assembly'
        elif 'qc' in machine_lower or 'quality' in machine_lower:
            return 'quality'
        elif 'pack' in machine_lower:
            return 'packaging'
        return '_default'

    def preempt_job(
        self,
        job_id: str,
        reason: str,
        operator_id: Optional[str] = None
    ) -> DispatchResult:
        """
        Preempt (pause) a running job.

        Args:
            job_id: Job to preempt
            reason: Reason for preemption
            operator_id: Operator performing preemption

        Returns:
            DispatchResult
        """
        from models.mes.work_orders import Job, JobStatus

        job = self.session.query(Job).filter(Job.job_id == job_id).first()
        if not job:
            return DispatchResult(False, job_id, None, "Job not found")

        if job.status != JobStatus.RUNNING:
            return DispatchResult(
                False, job_id, job.machine_id,
                f"Cannot preempt job with status '{job.status.value}'"
            )

        previous_status = job.status.value
        machine_id = job.machine_id

        # Pause job
        job.status = JobStatus.PAUSED

        if job.runtime_data is None:
            job.runtime_data = {}
        job.runtime_data['preempted_at'] = datetime.utcnow().isoformat()
        job.runtime_data['preempt_reason'] = reason
        job.runtime_data['preempted_by'] = operator_id

        # Free up machine
        self._free_machine(machine_id)

        # Record event
        self._record_machine_event(
            machine_id, 'job_preempted',
            f"Job {job_id} preempted: {reason}",
            job_id=job_id
        )

        self.session.flush()

        # Emit event
        _emit_dispatch_event('job_preempted', {
            'job_id': job_id,
            'machine_id': machine_id,
            'reason': reason,
            'timestamp': datetime.utcnow().isoformat(),
        })

        logger.info(f"Preempted job {job_id} on machine {machine_id}: {reason}")

        return DispatchResult(
            True, job_id, machine_id,
            f"Job preempted: {reason}",
            previous_status=previous_status,
            new_status='paused'
        )

    def get_dispatch_queue(
        self,
        machine_id: str,
        rule_name: str = None
    ) -> List[Dict[str, Any]]:
        """
        Get ordered dispatch queue for a machine.

        Args:
            machine_id: Machine to get queue for
            rule_name: Rule to use for ordering (None = use configured)

        Returns:
            Ordered list of candidate jobs
        """
        from services.mes.dispatching_rules import rank_jobs_by_rule

        candidates = self._get_dispatch_candidates(machine_id)
        if not candidates:
            return []

        # Use configured rule if not specified
        effective_rule = rule_name or self.get_machine_dispatch_rule(machine_id)

        # Handle composite rules
        kwargs = {}
        if effective_rule in DispatchRuleConfig.COMPOSITE_CONFIGS:
            kwargs['rules_weights'] = DispatchRuleConfig.COMPOSITE_CONFIGS[effective_rule]
            effective_rule = 'composite'

        return rank_jobs_by_rule(candidates, effective_rule, **kwargs)

    def get_machine_status(self, machine_id: str) -> Dict[str, Any]:
        """Get current dispatch status for a machine."""
        from models.mes.work_orders import Job, JobStatus

        # Get running job
        running_job = self.session.query(Job).filter(
            and_(
                Job.machine_id == machine_id,
                Job.status == JobStatus.RUNNING
            )
        ).first()

        # Get queue depth
        queue_count = len(self._get_dispatch_candidates(machine_id))

        return {
            'machine_id': machine_id,
            'is_available': self._check_machine_available(machine_id),
            'current_job': running_job.to_dict() if running_job else None,
            'queue_depth': queue_count,
        }

    # =========================================================================
    # Private Methods
    # =========================================================================

    def _check_machine_available(self, machine_id: str) -> bool:
        """Check if machine is available for new jobs."""
        from models.mes.work_orders import Job, JobStatus

        # Check for running jobs
        running = self.session.query(Job).filter(
            and_(
                Job.machine_id == machine_id,
                Job.status == JobStatus.RUNNING
            )
        ).first()

        if running:
            return False

        # Check resource status
        try:
            from models.mes.resources import ResourceStatus, MachineStatus
            status = self.session.query(ResourceStatus).filter(
                ResourceStatus.machine_id == machine_id
            ).first()

            if status:
                return status.status in (MachineStatus.IDLE, MachineStatus.RUNNING)
        except ImportError:
            pass

        return True

    def _get_dispatch_candidates(self, machine_id: str) -> List[Dict[str, Any]]:
        """Get jobs eligible for dispatch to this machine."""
        from models.mes.work_orders import Job, JobStatus

        jobs = self.session.query(Job).filter(
            Job.status.in_([JobStatus.PENDING, JobStatus.QUEUED, JobStatus.PAUSED])
        ).all()

        candidates = []
        for job in jobs:
            # Check eligibility
            eligible_machines = []
            if job.runtime_data:
                eligible_machines = job.runtime_data.get('eligible_machines', [])

            if eligible_machines and machine_id not in eligible_machines:
                continue

            candidates.append({
                'job_id': job.job_id,
                'work_order_id': str(job.work_order_id),
                'processing_time_mins': job.runtime_data.get('estimated_duration_mins', 30) if job.runtime_data else 30,
                'setup_time_mins': job.runtime_data.get('setup_time_mins', 5) if job.runtime_data else 5,
                'due_date': job.work_order.due_date if job.work_order else None,
                'priority': job.priority_score or 5,
                'remaining_operations': 1,
                'total_remaining_time': job.runtime_data.get('estimated_duration_mins', 30) if job.runtime_data else 30,
                'material_type': job.runtime_data.get('material_type') if job.runtime_data else None,
                'eligible_machines': eligible_machines,
            })

        return candidates

    def _get_machine_material(self, machine_id: str) -> Optional[str]:
        """Get currently loaded material on machine."""
        try:
            from models.mes.resources import ResourceStatus
            status = self.session.query(ResourceStatus).filter(
                ResourceStatus.machine_id == machine_id
            ).first()
            return status.current_material_type if status else None
        except ImportError:
            return None

    def _check_material_available(
        self,
        material_type: str,
        job_id: str
    ) -> Tuple[bool, str]:
        """Check if material is available for the job."""
        try:
            from services.mes.resource_service import ResourceService
            service = ResourceService(self.session)
            available, lots = service.check_material_availability(material_type, 1)
            if not available:
                return False, f"Material '{material_type}' not available"
            return True, "Material available"
        except ImportError:
            return True, "Material check skipped"

    def _update_resource_status(self, machine_id: str, job):
        """Update resource status when job is dispatched."""
        try:
            from models.mes.resources import ResourceStatus, MachineStatus

            status = self.session.query(ResourceStatus).filter(
                ResourceStatus.machine_id == machine_id
            ).first()

            if status:
                status.previous_status = status.status
                status.status = MachineStatus.RUNNING
                status.status_changed_at = datetime.utcnow()
                status.current_job_id = job.job_id
                status.current_work_order_id = str(job.work_order_id)

                if job.runtime_data:
                    status.current_operation_name = job.runtime_data.get('operation_name')
                    status.current_material_type = job.runtime_data.get('material_type')

        except ImportError:
            pass

    def _free_machine(self, machine_id: str):
        """Free machine when job is preempted or completed."""
        try:
            from models.mes.resources import ResourceStatus, MachineStatus

            status = self.session.query(ResourceStatus).filter(
                ResourceStatus.machine_id == machine_id
            ).first()

            if status:
                status.previous_status = status.status
                status.status = MachineStatus.IDLE
                status.status_changed_at = datetime.utcnow()
                status.current_job_id = None
                status.current_work_order_id = None
                status.current_operation_name = None

        except ImportError:
            pass

    def _record_dispatch_event(self, job, machine_id: str, operator_id: Optional[str]):
        """Record dispatch in data collection events."""
        try:
            from services.mes.data_collector import DataCollectorService
            service = DataCollectorService(self.session)
            service.record_machine_event(
                machine_id=machine_id,
                event_type='job_started',
                description=f"Job {job.job_id} dispatched",
                job_id=job.job_id,
                work_order_id=str(job.work_order_id),
                operator_id=operator_id,
                severity='info',
                source='dispatch_service'
            )
        except ImportError:
            pass

    def _record_machine_event(
        self,
        machine_id: str,
        event_type: str,
        description: str,
        job_id: Optional[str] = None
    ):
        """Record machine event."""
        try:
            from services.mes.data_collector import DataCollectorService
            service = DataCollectorService(self.session)
            service.record_machine_event(
                machine_id=machine_id,
                event_type=event_type,
                description=description,
                job_id=job_id,
                severity='info',
                source='dispatch_service'
            )
        except ImportError:
            pass


# =============================================================================
# Module-level convenience functions
# =============================================================================

def dispatch_job(session: Session, job_id: str, machine_id: str, **kwargs) -> DispatchResult:
    """Dispatch a job to a machine."""
    service = DispatchService(session)
    return service.dispatch_job(job_id, machine_id, **kwargs)


def auto_dispatch(session: Session, machine_id: str, **kwargs) -> DispatchResult:
    """Auto-dispatch next job to a machine."""
    service = DispatchService(session)
    return service.auto_dispatch(machine_id, **kwargs)


def get_dispatch_queue(session: Session, machine_id: str, **kwargs) -> List[Dict[str, Any]]:
    """Get dispatch queue for a machine."""
    service = DispatchService(session)
    return service.get_dispatch_queue(machine_id, **kwargs)


def set_dispatch_rule(session: Session, machine_id: str, rule_name: str, **kwargs) -> Dict[str, Any]:
    """Set dispatch rule for a machine."""
    service = DispatchService(session)
    return service.set_machine_dispatch_rule(machine_id, rule_name, **kwargs)


def get_dispatch_rules(session: Session) -> Dict[str, Any]:
    """Get all configured dispatch rules."""
    service = DispatchService(session)
    return service.get_all_dispatch_rules()
