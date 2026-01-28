"""
Workflow Coordinator for Flask CNC SCADA
========================================
Central orchestration connecting MES, GCode, Scheduler, Traceability, and TinyG.

This is the main integration point that:
- Creates work orders with operations and jobs
- Schedules work orders using selected algorithms
- Manages job execution lifecycle
- Links jobs to traceability records
- Records feedback for continuous improvement

Usage:
    from services.integration.workflow_coordinator import get_workflow_coordinator

    coordinator = get_workflow_coordinator()

    # Create work order with jobs
    wo = coordinator.create_work_order_with_jobs(wo_data, operations)

    # Schedule work orders
    schedule = coordinator.schedule_work_orders(wo_ids, algorithm='EDD')

    # Execute next job
    result = coordinator.execute_next_job(machine_id='tinyg-1')
"""

import logging
import time
import uuid
import threading
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List, Tuple
from dataclasses import dataclass, field

from config import get_config
from services.integration.event_dispatcher import (
    get_event_dispatcher,
    EventType,
    Event,
)
from services.integration.job_context import (
    JobContext,
    ExecutionState,
    create_job_context,
)
from services.integration.service_bus import get_service_bus, Message, MessageResponse

logger = logging.getLogger(__name__)
config = get_config()


@dataclass
class WorkOrderInput:
    """Input data for creating a work order."""
    wo_number: str
    part_number: str
    quantity: int
    due_date: datetime
    priority: int = 5
    part_revision: str = "A"
    customer: Optional[str] = None
    project: Optional[str] = None
    custom_fields: Dict[str, Any] = field(default_factory=dict)
    # Engraving options
    engraving_text: Optional[str] = None
    serial_prefix: Optional[str] = None
    generate_qr: bool = False


@dataclass
class OperationInput:
    """Input data for creating an operation."""
    sequence: int
    name: str
    machine_id: str
    gcode_file: Optional[str] = None
    setup_time_min: float = 0.0
    run_time_min: float = 0.0
    op_code: str = "MILL"
    instructions: str = ""
    tools_required: List[Dict] = field(default_factory=list)


@dataclass
class CompletionResult:
    """Result of job completion."""
    success: bool
    job_id: str
    actual_time_sec: float
    estimated_time_sec: Optional[float]
    error_percent: Optional[float]
    trace_record_id: Optional[str] = None
    error_message: Optional[str] = None


class WorkflowCoordinator:
    """
    Central workflow orchestration for the CNC system.

    Connects all services and manages the complete manufacturing workflow:
    Work Order -> Operations -> Jobs -> Scheduling -> Execution -> Feedback
    """

    def __init__(self):
        """Initialize workflow coordinator with service dependencies."""
        self._lock = threading.RLock()

        # Service references (lazy loaded)
        self._mes_service = None
        self._gcode_service = None
        self._scheduler_service = None
        self._traceability_service = None
        self._mqtt_service = None

        # Active execution contexts
        self._active_contexts: Dict[str, JobContext] = {}

        # Event dispatcher
        self._event_dispatcher = get_event_dispatcher()

        # Subscribe to relevant events
        self._setup_event_handlers()

        logger.info("WorkflowCoordinator initialized")

    def _setup_event_handlers(self):
        """Set up event subscriptions."""
        self._event_dispatcher.subscribe(
            EventType.JOB_COMPLETED,
            self._on_job_completed,
        )
        self._event_dispatcher.subscribe(
            EventType.JOB_FAILED,
            self._on_job_failed,
        )

    # =========================================================================
    # Service Access (Lazy Loading)
    # =========================================================================

    @property
    def mes_service(self):
        """Get MES service instance."""
        if self._mes_service is None:
            from services.mes_service import get_mes_service
            self._mes_service = get_mes_service()
        return self._mes_service

    @property
    def gcode_service(self):
        """Get G-code service instance."""
        if self._gcode_service is None:
            from services.gcode_service import get_gcode_service
            self._gcode_service = get_gcode_service()
        return self._gcode_service

    @property
    def scheduler_service(self):
        """Get scheduler service instance."""
        if self._scheduler_service is None:
            from services.scheduler_service import get_scheduler_service
            self._scheduler_service = get_scheduler_service()
        return self._scheduler_service

    @property
    def traceability_service(self):
        """Get traceability service instance."""
        if self._traceability_service is None:
            from services.traceability_service import get_traceability_service
            self._traceability_service = get_traceability_service()
        return self._traceability_service

    @property
    def mqtt_service(self):
        """Get MQTT service instance."""
        if self._mqtt_service is None:
            from services.mqtt_service import get_mqtt_service
            self._mqtt_service = get_mqtt_service()
        return self._mqtt_service

    # =========================================================================
    # Work Order Management
    # =========================================================================

    def create_work_order_with_jobs(
        self,
        wo_input: WorkOrderInput,
        operations: List[OperationInput],
    ) -> Tuple[Optional[Dict], str]:
        """
        Create a complete work order with operations and queued jobs.

        Args:
            wo_input: Work order data
            operations: List of operations with G-code files

        Returns:
            Tuple of (work_order_dict or None, error_message)
        """
        try:
            # Create work order in MES
            wo, error = self.mes_service.create_work_order(
                wo_number=wo_input.wo_number,
                part_number=wo_input.part_number,
                quantity=wo_input.quantity,
                part_name=wo_input.part_number,  # Use part number as name
                due_date=wo_input.due_date.isoformat() if wo_input.due_date else None,
                priority=wo_input.priority,
            )

            if not wo:
                return None, error

            # Add operations
            created_ops = []
            for op_input in operations:
                op, error = self.mes_service.add_operation(
                    wo_id=wo.id,
                    sequence=op_input.sequence,
                    name=op_input.name,
                    operation_type=op_input.op_code,
                    machine_id=op_input.machine_id,
                    setup_time=op_input.setup_time_min,
                    run_time_per_piece=op_input.run_time_min,
                    instructions=op_input.instructions,
                    gcode_file=op_input.gcode_file,
                )

                if not op:
                    logger.warning(f"Failed to create operation {op_input.name}: {error}")
                    continue

                created_ops.append(op)

                # Queue job for this operation if G-code file provided
                if op_input.gcode_file:
                    self._queue_job_for_operation(op, wo_input.priority)

            # Store custom fields (engraving, etc.)
            # This would be stored in PostgreSQL in the full implementation
            wo_data = wo.to_dict()
            wo_data['custom_fields'] = wo_input.custom_fields
            wo_data['engraving_text'] = wo_input.engraving_text
            wo_data['serial_prefix'] = wo_input.serial_prefix
            wo_data['generate_qr'] = wo_input.generate_qr

            # Publish event
            self._event_dispatcher.publish(
                EventType.WORK_ORDER_CREATED,
                {
                    "wo_id": wo.id,
                    "wo_number": wo.wo_number,
                    "part_number": wo.part_number,
                    "quantity": wo.quantity_ordered,
                    "operation_count": len(created_ops),
                },
                source="workflow_coordinator",
            )

            logger.info(f"Created work order {wo.wo_number} with {len(created_ops)} operations")
            return wo_data, ""

        except Exception as e:
            logger.error(f"Error creating work order: {e}")
            return None, str(e)

    def _queue_job_for_operation(self, operation, priority: int):
        """Queue a job in the G-code service for an operation."""
        try:
            # Read G-code file content
            with open(operation.gcode_file, 'rb') as f:
                content = f.read()

            from services.gcode_service import JobPriority

            # Map priority 1-10 to JobPriority enum
            if priority <= 2:
                job_priority = JobPriority.URGENT
            elif priority <= 4:
                job_priority = JobPriority.HIGH
            elif priority <= 7:
                job_priority = JobPriority.NORMAL
            else:
                job_priority = JobPriority.LOW

            job, error = self.gcode_service.upload_file(
                file_content=content,
                filename=operation.gcode_file,
                priority=job_priority,
            )

            if job:
                logger.info(f"Queued job {job.id} for operation {operation.operation_name}")
            else:
                logger.warning(f"Failed to queue job: {error}")

        except Exception as e:
            logger.error(f"Error queuing job for operation: {e}")

    def release_work_order(self, wo_id: str) -> Tuple[bool, str]:
        """
        Release a work order for production.

        Args:
            wo_id: Work order ID

        Returns:
            Tuple of (success, error_message)
        """
        try:
            success = self.mes_service.release_work_order(wo_id)
            if success:
                wo = self.mes_service.get_work_order(wo_id)
                self._event_dispatcher.publish(
                    EventType.WORK_ORDER_RELEASED,
                    {
                        "wo_id": wo_id,
                        "wo_number": wo.wo_number if wo else "",
                    },
                    source="workflow_coordinator",
                )
                return True, ""
            return False, "Failed to release work order"
        except Exception as e:
            return False, str(e)

    # =========================================================================
    # Scheduling
    # =========================================================================

    def schedule_work_orders(
        self,
        wo_ids: List[str],
        algorithm: str = "EDD",
        machines: Optional[List[str]] = None,
    ) -> Tuple[Optional[Dict], str]:
        """
        Schedule work orders using the specified algorithm.

        Args:
            wo_ids: List of work order IDs to schedule
            algorithm: Scheduling algorithm (FIFO, EDD, SPT, CR, WSPT, Genetic, SA, OR-Tools)
            machines: List of machine IDs (optional)

        Returns:
            Tuple of (schedule_result_dict or None, error_message)
        """
        try:
            from services.scheduler_service import (
                Job as SchedulerJob,
                Operation as SchedulerOperation,
                Machine,
                DispatchingRule,
            )

            # Convert work orders to scheduler format
            scheduler_jobs = []
            for wo_id in wo_ids:
                wo = self.mes_service.get_work_order(wo_id)
                if not wo:
                    continue

                # Convert due date to minutes from now
                due_minutes = None
                if wo.due_date:
                    due_dt = datetime.fromisoformat(wo.due_date)
                    due_minutes = int((due_dt - datetime.now()).total_seconds() / 60)

                # Convert operations
                ops = []
                for op in wo.operations:
                    ops.append(SchedulerOperation(
                        id=op.id,
                        name=op.operation_name,
                        machine_id=op.machine_id or "default",
                        processing_time=int(op.run_time_per_piece_min * wo.quantity_ordered),
                        setup_time=int(op.setup_time_min),
                    ))

                if ops:
                    scheduler_jobs.append(SchedulerJob(
                        id=wo.id,
                        name=wo.wo_number,
                        operations=ops,
                        priority=wo.priority,
                        due_date=due_minutes,
                    ))

            if not scheduler_jobs:
                return None, "No valid jobs to schedule"

            # Get or create machines
            if machines is None:
                # Get unique machine IDs from operations
                machine_ids = set()
                for job in scheduler_jobs:
                    for op in job.operations:
                        machine_ids.add(op.machine_id)
                machines = [Machine(id=m, name=m) for m in machine_ids]
            else:
                machines = [Machine(id=m, name=m) for m in machines]

            # Map algorithm string to dispatching rule
            algorithm_map = {
                "FIFO": DispatchingRule.FIFO,
                "EDD": DispatchingRule.EDD,
                "SPT": DispatchingRule.SPT,
                "CR": DispatchingRule.CR,
                "PRIORITY": DispatchingRule.PRIORITY,
            }

            # Run scheduling
            if algorithm.upper() in ("GENETIC", "SA", "ORTOOLS", "OR-TOOLS"):
                # Use advanced scheduler for metaheuristics
                result = self.scheduler_service.optimize_schedule(
                    scheduler_jobs,
                    machines,
                )
            else:
                # Use heuristic scheduling
                rule = algorithm_map.get(algorithm.upper(), DispatchingRule.EDD)
                result = self.scheduler_service.schedule_with_rule(
                    scheduler_jobs,
                    machines,
                    rule,
                )

            if result.success:
                # Publish event
                self._event_dispatcher.publish(
                    EventType.SCHEDULE_CREATED,
                    {
                        "algorithm": algorithm,
                        "jobs_scheduled": len(scheduler_jobs),
                        "machines_used": len(machines),
                        "makespan_hours": result.makespan / 60,
                    },
                    source="workflow_coordinator",
                )

                return result.to_dict(), ""
            else:
                return None, result.status

        except Exception as e:
            logger.error(f"Error scheduling work orders: {e}")
            return None, str(e)

    def get_next_scheduled_job(self, machine_id: str) -> Optional[Dict]:
        """
        Get the next scheduled job for a machine.

        Args:
            machine_id: Machine ID

        Returns:
            Job dict or None
        """
        try:
            job = self.gcode_service.get_next_job()
            if job:
                return job.to_dict()
            return None
        except Exception as e:
            logger.error(f"Error getting next job: {e}")
            return None

    # =========================================================================
    # Job Execution
    # =========================================================================

    def start_job_execution(
        self,
        job_id: str,
        machine_id: str,
        operator_id: Optional[str] = None,
    ) -> Tuple[Optional[JobContext], str]:
        """
        Start executing a job.

        Args:
            job_id: Job ID to execute
            machine_id: Machine to run on
            operator_id: Operator ID

        Returns:
            Tuple of (JobContext or None, error_message)
        """
        try:
            # Get job from G-code service
            job = self.gcode_service.get_job(job_id)
            if not job:
                return None, f"Job not found: {job_id}"

            # Create execution context
            ctx = JobContext(
                job_id=job_id,
                machine_id=machine_id,
                gcode_file=job.filepath,
                estimated_time_sec=job.metadata.estimated_time_sec,
                operator_id=operator_id,
            )

            # Store active context
            with self._lock:
                self._active_contexts[job_id] = ctx

            # Update job status
            from services.gcode_service import JobStatus
            self.gcode_service.update_job_status(job_id, JobStatus.RUNNING)

            # Start the context
            ctx.start_loading()
            ctx.start_setup()
            ctx.start_execution()

            logger.info(f"Started execution of job {job_id} on {machine_id}")
            return ctx, ""

        except Exception as e:
            logger.error(f"Error starting job execution: {e}")
            return None, str(e)

    def get_active_context(self, job_id: str) -> Optional[JobContext]:
        """Get active execution context for a job."""
        with self._lock:
            return self._active_contexts.get(job_id)

    def complete_job_with_feedback(
        self,
        job_id: str,
        actual_time_sec: float,
    ) -> CompletionResult:
        """
        Complete a job and record feedback.

        Args:
            job_id: Job ID
            actual_time_sec: Actual execution time

        Returns:
            CompletionResult with accuracy metrics
        """
        try:
            # Get job
            job = self.gcode_service.get_job(job_id)
            if not job:
                return CompletionResult(
                    success=False,
                    job_id=job_id,
                    actual_time_sec=actual_time_sec,
                    estimated_time_sec=None,
                    error_percent=None,
                    error_message="Job not found",
                )

            # Complete the job
            from services.gcode_service import JobStatus
            self.gcode_service.update_job_status(job_id, JobStatus.COMPLETED)

            # Get execution context
            ctx = self._active_contexts.get(job_id)
            if ctx:
                ctx.complete()
                # Clean up
                del self._active_contexts[job_id]

            # Calculate accuracy
            estimated = job.metadata.estimated_time_sec
            error_percent = None
            if estimated and estimated > 0:
                error_percent = ((actual_time_sec - estimated) / estimated) * 100

            # Record time accuracy (for feedback loop)
            accuracy_data = self.gcode_service.get_time_accuracy(job_id)

            # Publish feedback event
            self._event_dispatcher.publish(
                EventType.TIME_ACCURACY_RECORDED,
                {
                    "job_id": job_id,
                    "estimated_sec": estimated,
                    "actual_sec": actual_time_sec,
                    "error_percent": error_percent,
                },
                source="workflow_coordinator",
            )

            logger.info(
                f"Job {job_id} completed. Estimated: {estimated}s, "
                f"Actual: {actual_time_sec}s, Error: {error_percent:.1f}%"
                if error_percent else f"Job {job_id} completed."
            )

            return CompletionResult(
                success=True,
                job_id=job_id,
                actual_time_sec=actual_time_sec,
                estimated_time_sec=estimated,
                error_percent=error_percent,
            )

        except Exception as e:
            logger.error(f"Error completing job: {e}")
            return CompletionResult(
                success=False,
                job_id=job_id,
                actual_time_sec=actual_time_sec,
                estimated_time_sec=None,
                error_percent=None,
                error_message=str(e),
            )

    # =========================================================================
    # Traceability
    # =========================================================================

    def link_job_to_traceability(
        self,
        job_id: str,
        serial_number: str,
        part_number: str,
        material_lots: Optional[List[str]] = None,
    ) -> Tuple[Optional[str], str]:
        """
        Create a traceability record linked to a job.

        Args:
            job_id: Job ID
            serial_number: Part serial number
            part_number: Part number
            material_lots: List of material lot IDs

        Returns:
            Tuple of (trace_record_id or None, error_message)
        """
        try:
            # Get execution context for sensor data
            ctx = self._active_contexts.get(job_id)
            sensor_data = []
            if ctx:
                sensor_data = [s.to_dict() for s in ctx.sensor_snapshots]

            # Create trace record
            trace_id = str(uuid.uuid4())

            # Publish event
            self._event_dispatcher.publish(
                EventType.TRACE_RECORD_CREATED,
                {
                    "trace_id": trace_id,
                    "job_id": job_id,
                    "serial_number": serial_number,
                    "part_number": part_number,
                    "material_lots": material_lots or [],
                    "sensor_snapshot_count": len(sensor_data),
                },
                source="workflow_coordinator",
            )

            logger.info(f"Created trace record {trace_id} for serial {serial_number}")
            return trace_id, ""

        except Exception as e:
            logger.error(f"Error creating trace record: {e}")
            return None, str(e)

    # =========================================================================
    # Event Handlers
    # =========================================================================

    def _on_job_completed(self, event: Event):
        """Handle job completed event."""
        job_id = event.data.get("job_id")
        if job_id:
            # Clean up active context
            with self._lock:
                if job_id in self._active_contexts:
                    del self._active_contexts[job_id]

    def _on_job_failed(self, event: Event):
        """Handle job failed event."""
        job_id = event.data.get("job_id")
        if job_id:
            # Clean up active context
            with self._lock:
                if job_id in self._active_contexts:
                    del self._active_contexts[job_id]

    # =========================================================================
    # Status and Metrics
    # =========================================================================

    def get_workflow_status(self) -> Dict[str, Any]:
        """Get current workflow status."""
        with self._lock:
            active_jobs = len(self._active_contexts)

        return {
            "active_jobs": active_jobs,
            "active_contexts": [
                ctx.to_dict() for ctx in self._active_contexts.values()
            ],
            "queue_status": self.gcode_service.get_queue_status(),
        }

    def get_production_metrics(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """Get production metrics for a date range."""
        return self.mes_service.get_production_summary(
            start_date=start_date.isoformat() if start_date else None,
            end_date=end_date.isoformat() if end_date else None,
        )


# Global coordinator instance
_workflow_coordinator: Optional[WorkflowCoordinator] = None


def get_workflow_coordinator() -> WorkflowCoordinator:
    """Get global workflow coordinator instance."""
    global _workflow_coordinator
    if _workflow_coordinator is None:
        _workflow_coordinator = WorkflowCoordinator()
    return _workflow_coordinator


def initialize_workflow_coordinator() -> WorkflowCoordinator:
    """Initialize and return global workflow coordinator."""
    global _workflow_coordinator
    _workflow_coordinator = WorkflowCoordinator()
    return _workflow_coordinator
