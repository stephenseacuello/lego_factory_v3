"""
LEGO Factory v3 - MES API Documentation
========================================
Flask-RESTX namespace for Manufacturing Execution System endpoints.
"""

from flask import request
from flask_restx import Namespace, Resource, fields
import logging

logger = logging.getLogger(__name__)

# Create namespace
mes_ns = Namespace(
    'mes',
    description='MES - Manufacturing Execution System (Level 3)',
    path='/mes',
)

# =============================================================================
# API MODELS - Work Orders
# =============================================================================

work_order_model = mes_ns.model('WorkOrder', {
    'id': fields.String(description='Internal ID'),
    'work_order_id': fields.String(description='Work order number', example='WO-20240115-001'),
    'description': fields.String(description='Work order description', example='Produce 500x 2x4 Red Bricks'),
    'product_id': fields.String(description='Product to manufacture', example='brick_2x4_red'),
    'recipe_id': fields.String(description='Recipe to use', example='RCP-BRICK-2X4'),
    'quantity_ordered': fields.Integer(description='Quantity to produce', example=500),
    'quantity_completed': fields.Integer(description='Quantity completed', example=335),
    'quantity_scrapped': fields.Integer(description='Quantity scrapped', example=12),
    'status': fields.String(
        description='Work order status',
        enum=['draft', 'planned', 'released', 'in_progress', 'on_hold', 'completed', 'cancelled'],
        example='in_progress'
    ),
    'priority': fields.Integer(description='Priority (1=highest, 10=lowest)', example=3),
    'planned_start': fields.DateTime(description='Planned start date'),
    'planned_end': fields.DateTime(description='Planned end date'),
    'actual_start': fields.DateTime(description='Actual start date'),
    'actual_end': fields.DateTime(description='Actual end date'),
    'due_date': fields.DateTime(description='Due date'),
    'customer_id': fields.String(description='Customer ID', example='CUST001'),
    'sales_order_id': fields.String(description='Sales order reference', example='SO-20240110-001'),
    'notes': fields.String(description='Notes'),
    'created_at': fields.DateTime(description='Creation timestamp'),
    'created_by': fields.String(description='Creator user ID'),
    'updated_at': fields.DateTime(description='Last update timestamp'),
})

work_order_create = mes_ns.model('WorkOrderCreate', {
    'product_id': fields.String(required=True, description='Product to manufacture', example='brick_2x4_red'),
    'quantity_ordered': fields.Integer(description='Quantity to produce', default=1, example=500),
    'description': fields.String(description='Work order description'),
    'recipe_id': fields.String(description='Recipe to use'),
    'priority': fields.Integer(description='Priority (1-10)', default=5, example=5),
    'due_date': fields.DateTime(description='Due date'),
    'planned_start': fields.DateTime(description='Planned start'),
    'planned_end': fields.DateTime(description='Planned end'),
    'customer_id': fields.String(description='Customer ID'),
    'sales_order_id': fields.String(description='Sales order reference'),
    'notes': fields.String(description='Notes'),
})

work_order_update = mes_ns.model('WorkOrderUpdate', {
    'description': fields.String(description='Work order description'),
    'quantity_ordered': fields.Integer(description='Quantity to produce'),
    'priority': fields.Integer(description='Priority (1-10)'),
    'due_date': fields.DateTime(description='Due date'),
    'planned_start': fields.DateTime(description='Planned start'),
    'planned_end': fields.DateTime(description='Planned end'),
    'notes': fields.String(description='Notes'),
})

work_order_list_response = mes_ns.model('WorkOrderListResponse', {
    'work_orders': fields.List(fields.Nested(work_order_model)),
    'count': fields.Integer(description='Total count', example=25),
})


# =============================================================================
# API MODELS - Operations
# =============================================================================

operation_model = mes_ns.model('Operation', {
    'id': fields.String(description='Internal ID'),
    'operation_id': fields.String(description='Operation ID', example='OP-001'),
    'work_order_id': fields.String(description='Parent work order'),
    'sequence': fields.Integer(description='Operation sequence number', example=10),
    'operation_type': fields.String(
        description='Operation type',
        enum=['design', 'printing_fdm', 'printing_sla', 'cnc_milling', 'assembly', 'inspection', 'packaging', 'custom'],
        example='printing_fdm'
    ),
    'name': fields.String(description='Operation name', example='3D Print'),
    'description': fields.String(description='Operation description'),
    'work_center_id': fields.String(description='Work center'),
    'machine_id': fields.String(description='Assigned machine'),
    'status': fields.String(
        description='Operation status',
        enum=['pending', 'ready', 'running', 'paused', 'completed', 'failed'],
        example='running'
    ),
    'setup_time': fields.Integer(description='Setup time (minutes)', example=5),
    'run_time': fields.Integer(description='Run time (minutes)', example=45),
    'teardown_time': fields.Integer(description='Teardown time (minutes)', example=2),
    'actual_start': fields.DateTime(description='Actual start time'),
    'actual_end': fields.DateTime(description='Actual end time'),
    'parameters': fields.Raw(description='Operation parameters'),
})

operation_create = mes_ns.model('OperationCreate', {
    'name': fields.String(required=True, description='Operation name', example='3D Print'),
    'operation_type': fields.String(description='Operation type', default='custom'),
    'sequence': fields.Integer(description='Sequence number', default=10),
    'description': fields.String(description='Description'),
    'work_center_id': fields.String(description='Work center'),
    'machine_id': fields.String(description='Machine'),
    'setup_time': fields.Integer(description='Setup time (minutes)', default=0),
    'run_time': fields.Integer(description='Run time (minutes)', default=0),
    'teardown_time': fields.Integer(description='Teardown time (minutes)', default=0),
    'parameters': fields.Raw(description='Operation parameters'),
})


# =============================================================================
# API MODELS - Jobs
# =============================================================================

job_model = mes_ns.model('Job', {
    'id': fields.String(description='Internal ID'),
    'job_id': fields.String(description='Job ID', example='JOB-20240115-001'),
    'work_order_id': fields.String(description='Parent work order'),
    'machine_id': fields.String(description='Assigned machine', example='prusa_mk4_1'),
    'status': fields.String(
        description='Job status',
        enum=['pending', 'queued', 'running', 'paused', 'completed', 'failed', 'cancelled'],
        example='running'
    ),
    'quantity_planned': fields.Integer(description='Planned quantity', example=100),
    'quantity_completed': fields.Integer(description='Completed quantity', example=85),
    'quantity_scrapped': fields.Integer(description='Scrapped quantity', example=3),
    'scheduled_start': fields.DateTime(description='Scheduled start'),
    'scheduled_end': fields.DateTime(description='Scheduled end'),
    'actual_start': fields.DateTime(description='Actual start'),
    'actual_end': fields.DateTime(description='Actual end'),
    'priority_score': fields.Float(description='Priority score for scheduling', example=85.5),
    'assigned_worker_id': fields.String(description='Assigned worker'),
    'gcode_file': fields.String(description='G-code file path'),
    'gcode_hash': fields.String(description='G-code file hash for integrity'),
    'created_by': fields.String(description='Creator'),
    'created_at': fields.DateTime(description='Creation time'),
})

job_create = mes_ns.model('JobCreate', {
    'work_order_id': fields.String(required=True, description='Work order ID'),
    'machine_id': fields.String(description='Target machine'),
    'scheduled_start': fields.DateTime(description='Scheduled start'),
    'scheduled_end': fields.DateTime(description='Scheduled end'),
    'quantity_planned': fields.Integer(description='Quantity to produce', default=1),
    'priority_score': fields.Float(description='Priority score'),
    'assigned_worker_id': fields.String(description='Assigned worker'),
    'gcode_file': fields.String(description='G-code file'),
})

job_status_update = mes_ns.model('JobStatusUpdate', {
    'status': fields.String(
        required=True,
        description='New status',
        enum=['pending', 'queued', 'running', 'paused', 'completed', 'failed', 'cancelled']
    ),
    'user_id': fields.String(description='User making change'),
})

job_list_response = mes_ns.model('JobListResponse', {
    'jobs': fields.List(fields.Nested(job_model)),
    'count': fields.Integer(description='Total count'),
})


# =============================================================================
# API MODELS - Scheduling
# =============================================================================

schedule_job_input = mes_ns.model('ScheduleJobInput', {
    'job_id': fields.String(required=True, description='Job ID'),
    'work_order_id': fields.String(description='Work order reference'),
    'duration_minutes': fields.Integer(required=True, description='Job duration in minutes', example=60),
    'machine_id': fields.String(description='Preferred machine'),
    'eligible_machines': fields.List(fields.String, description='List of eligible machines'),
    'priority': fields.Integer(description='Priority (1-10)', default=5),
    'due_date': fields.DateTime(description='Due date'),
    'dependencies': fields.List(fields.String, description='Dependent job IDs'),
    'setup_time': fields.Integer(description='Setup time (minutes)', default=0),
})

schedule_machine_input = mes_ns.model('ScheduleMachineInput', {
    'machine_id': fields.String(required=True, description='Machine ID'),
    'name': fields.String(description='Machine name'),
    'capabilities': fields.List(fields.String, description='Machine capabilities'),
    'efficiency': fields.Float(description='Efficiency factor (0-1)', default=1.0),
})

schedule_request = mes_ns.model('ScheduleRequest', {
    'jobs': fields.List(fields.Nested(schedule_job_input), required=True, description='Jobs to schedule'),
    'machines': fields.List(fields.Nested(schedule_machine_input), required=True, description='Available machines'),
    'horizon_hours': fields.Integer(description='Planning horizon in hours', default=24),
    'objective': fields.String(
        description='Optimization objective',
        enum=['makespan', 'due_date', 'setup_time'],
        default='makespan'
    ),
})

scheduled_job_output = mes_ns.model('ScheduledJobOutput', {
    'job_id': fields.String(description='Job ID'),
    'machine_id': fields.String(description='Assigned machine'),
    'start_time': fields.DateTime(description='Scheduled start'),
    'end_time': fields.DateTime(description='Scheduled end'),
    'setup_time': fields.Integer(description='Setup time used'),
})

schedule_response = mes_ns.model('ScheduleResponse', {
    'scheduled_jobs': fields.List(fields.Nested(scheduled_job_output)),
    'makespan_minutes': fields.Integer(description='Total makespan'),
    'total_setup_time': fields.Integer(description='Total setup time'),
    'utilization': fields.Raw(description='Machine utilization'),
    'unscheduled_jobs': fields.List(fields.String, description='Jobs that could not be scheduled'),
    'solver_status': fields.String(description='Solver status'),
})

dispatch_queue_item = mes_ns.model('DispatchQueueItem', {
    'job_id': fields.String(description='Job ID'),
    'work_order_id': fields.String(description='Work order ID'),
    'priority_score': fields.Float(description='Priority score'),
    'quantity': fields.Integer(description='Quantity'),
})


# =============================================================================
# API MODELS - OEE
# =============================================================================

oee_model = mes_ns.model('OEE', {
    'machine_id': fields.String(description='Machine ID'),
    'period': fields.Raw(description='Time period', example={'start': '2024-01-08T00:00:00Z', 'end': '2024-01-15T23:59:59Z'}),
    'oee': fields.Float(description='Overall Equipment Effectiveness', example=0.852),
    'availability': fields.Float(description='Availability component', example=0.92),
    'performance': fields.Float(description='Performance component', example=0.95),
    'quality': fields.Float(description='Quality component', example=0.975),
    'planned_production_time': fields.Float(description='Planned production time (hours)', example=168),
    'actual_production_time': fields.Float(description='Actual production time (hours)', example=154.56),
    'total_count': fields.Integer(description='Total units produced', example=4500),
    'good_count': fields.Integer(description='Good units', example=4387),
})

oee_summary_model = mes_ns.model('OEESummary', {
    'period': fields.Raw(description='Time period'),
    'overall_oee': fields.Float(description='Overall OEE across all machines', example=0.847),
    'machines': fields.List(fields.Nested(mes_ns.model('MachineOEE', {
        'machine_id': fields.String(),
        'name': fields.String(),
        'oee': fields.Float(),
        'availability': fields.Float(),
        'performance': fields.Float(),
        'quality': fields.Float(),
    }))),
})


# =============================================================================
# API MODELS - Recipes (ISA-88)
# =============================================================================

recipe_operation_model = mes_ns.model('RecipeOperation', {
    'sequence': fields.Integer(description='Operation sequence', example=10),
    'name': fields.String(description='Operation name', example='Slice Model'),
    'type': fields.String(description='Operation type', example='design'),
    'duration_min': fields.Integer(description='Duration in minutes', example=5),
    'parameters': fields.Raw(description='Operation parameters'),
})

recipe_model = mes_ns.model('Recipe', {
    'recipe_id': fields.String(description='Recipe ID', example='RCP-001'),
    'name': fields.String(description='Recipe name', example='2x4 Brick Standard'),
    'version': fields.String(description='Version', example='1.0'),
    'product_id': fields.String(description='Product ID', example='brick_2x4'),
    'status': fields.String(
        description='Recipe status',
        enum=['draft', 'pending_approval', 'approved', 'obsolete'],
        example='approved'
    ),
    'operations': fields.List(fields.Nested(recipe_operation_model)),
    'parameters': fields.Raw(description='Recipe parameters', example={'infill': 20, 'layer_height': 0.2}),
    'created_at': fields.DateTime(description='Creation time'),
    'created_by': fields.String(description='Creator'),
    'approved_at': fields.DateTime(description='Approval time'),
    'approved_by': fields.String(description='Approver'),
})

recipe_create = mes_ns.model('RecipeCreate', {
    'name': fields.String(required=True, description='Recipe name'),
    'product_id': fields.String(required=True, description='Product ID'),
    'version': fields.String(description='Version', default='1.0'),
    'operations': fields.List(fields.Nested(recipe_operation_model)),
    'parameters': fields.Raw(description='Recipe parameters'),
})


# =============================================================================
# API MODELS - Labor
# =============================================================================

worker_model = mes_ns.model('Worker', {
    'id': fields.String(description='Worker ID', example='W001'),
    'name': fields.String(description='Worker name', example='John Smith'),
    'role': fields.String(description='Role', example='Operator'),
    'skills': fields.List(fields.String, description='Skills', example=['3d_printing', 'assembly']),
    'status': fields.String(
        description='Current status',
        enum=['active', 'break', 'offline'],
        example='active'
    ),
})

time_entry_model = mes_ns.model('TimeEntry', {
    'id': fields.String(description='Entry ID'),
    'worker_id': fields.String(description='Worker ID'),
    'job_id': fields.String(description='Job ID'),
    'start': fields.DateTime(description='Start time'),
    'end': fields.DateTime(description='End time'),
    'hours': fields.Float(description='Hours worked'),
})

time_entry_create = mes_ns.model('TimeEntryCreate', {
    'worker_id': fields.String(required=True, description='Worker ID'),
    'job_id': fields.String(description='Job ID'),
    'start': fields.DateTime(required=True, description='Start time'),
    'end': fields.DateTime(description='End time'),
})


# =============================================================================
# API MODELS - Gantt
# =============================================================================

gantt_job = mes_ns.model('GanttJob', {
    'job_id': fields.String(description='Job ID'),
    'machine_id': fields.String(description='Machine ID'),
    'work_order_id': fields.String(description='Work order ID'),
    'start': fields.DateTime(description='Start time'),
    'end': fields.DateTime(description='End time'),
    'status': fields.String(description='Job status'),
    'product': fields.String(description='Product name'),
    'color': fields.String(description='Display color'),
})

gantt_response = mes_ns.model('GanttResponse', {
    'machines': fields.List(fields.Raw(description='Machine list')),
    'jobs': fields.List(fields.Nested(gantt_job)),
    'time_range': fields.Raw(description='Time range'),
})


# =============================================================================
# RESOURCES - Work Orders
# =============================================================================

@mes_ns.route('/work-orders')
class WorkOrderList(Resource):
    """Work order listing and creation."""

    @mes_ns.doc(
        'list_work_orders',
        params={
            'status': {'description': 'Filter by status', 'enum': ['draft', 'planned', 'released', 'in_progress', 'on_hold', 'completed', 'cancelled']},
            'product_id': {'description': 'Filter by product'},
            'customer_id': {'description': 'Filter by customer'},
            'due_before': {'description': 'Filter by due date (ISO format)'},
            'limit': {'description': 'Max results', 'default': 100},
            'offset': {'description': 'Pagination offset', 'default': 0},
        },
        responses={
            200: ('List of work orders', work_order_list_response),
        }
    )
    @mes_ns.marshal_with(work_order_list_response)
    def get(self):
        """
        List work orders with optional filtering.

        Returns work orders sorted by priority and due date.
        Use query parameters to filter results.

        **Status Workflow:**
        1. `draft` - Initial creation, not yet released
        2. `planned` - Planning complete, awaiting release
        3. `released` - Released for production
        4. `in_progress` - Currently being worked
        5. `on_hold` - Temporarily paused
        6. `completed` - Successfully finished
        7. `cancelled` - Cancelled before completion
        """
        from api.routes.mes_api import list_work_orders
        return list_work_orders()

    @mes_ns.doc(
        'create_work_order',
        responses={
            201: ('Work order created', work_order_model),
            400: 'Validation error',
        }
    )
    @mes_ns.expect(work_order_create, validate=True)
    @mes_ns.marshal_with(work_order_model, code=201)
    def post(self):
        """
        Create a new work order.

        Creates a work order in 'draft' status. The work order must be
        released before production can begin.

        **Required Fields:**
        - `product_id`: The product to manufacture

        **Optional Fields:**
        - `quantity_ordered`: Defaults to 1
        - `recipe_id`: Manufacturing recipe (auto-selected if not provided)
        - `priority`: 1 (highest) to 10 (lowest), default 5
        - `due_date`: Required delivery date
        """
        from api.routes.mes_api import create_work_order
        return create_work_order()


@mes_ns.route('/work-orders/<string:work_order_id>')
@mes_ns.param('work_order_id', 'Work order ID')
class WorkOrderDetail(Resource):
    """Single work order operations."""

    @mes_ns.doc(
        'get_work_order',
        responses={
            200: ('Work order details', work_order_model),
            404: 'Work order not found',
        }
    )
    @mes_ns.marshal_with(work_order_model)
    def get(self, work_order_id):
        """
        Get work order details.

        Returns complete work order information including:
        - Basic work order data
        - Associated operations
        - Linked jobs
        - Progress statistics
        """
        from api.routes.mes_api import get_work_order
        return get_work_order(work_order_id)

    @mes_ns.doc(
        'update_work_order',
        responses={
            200: ('Work order updated', work_order_model),
            400: 'Validation error',
            404: 'Work order not found',
        }
    )
    @mes_ns.expect(work_order_update)
    @mes_ns.marshal_with(work_order_model)
    def put(self, work_order_id):
        """
        Update a work order.

        Updates allowed fields on a work order. Some fields may be
        restricted based on the current status.

        **Note:** Completed or cancelled work orders cannot be updated.
        """
        from api.routes.mes_api import update_work_order
        return update_work_order(work_order_id)


@mes_ns.route('/work-orders/<string:work_order_id>/release')
@mes_ns.param('work_order_id', 'Work order ID')
class WorkOrderRelease(Resource):
    """Work order release endpoint."""

    @mes_ns.doc(
        'release_work_order',
        responses={
            200: ('Work order released', work_order_model),
            404: 'Work order not found',
            400: 'Cannot release (invalid status)',
        }
    )
    def post(self, work_order_id):
        """
        Release a work order for production.

        Changes status from 'draft' or 'planned' to 'released'.
        Once released, the work order is available for job creation
        and production scheduling.

        **Prerequisites:**
        - Work order must be in 'draft' or 'planned' status
        - All required fields must be completed
        - Recipe must be approved (if specified)
        """
        from api.routes.mes_api import release_work_order
        return release_work_order(work_order_id)


@mes_ns.route('/work-orders/<string:work_order_id>/start')
@mes_ns.param('work_order_id', 'Work order ID')
class WorkOrderStart(Resource):
    """Work order start endpoint."""

    @mes_ns.doc(
        'start_work_order',
        responses={
            200: ('Work order started', work_order_model),
            404: 'Work order not found',
            400: 'Cannot start (invalid status)',
        }
    )
    def post(self, work_order_id):
        """
        Start a work order.

        Changes status to 'in_progress' and records the actual start time.
        This is typically called when the first job begins execution.
        """
        from api.routes.mes_api import start_work_order
        return start_work_order(work_order_id)


@mes_ns.route('/work-orders/<string:work_order_id>/complete')
@mes_ns.param('work_order_id', 'Work order ID')
class WorkOrderComplete(Resource):
    """Work order completion endpoint."""

    @mes_ns.doc(
        'complete_work_order',
        responses={
            200: ('Work order completed', work_order_model),
            404: 'Work order not found',
            400: 'Cannot complete (invalid status)',
        }
    )
    def post(self, work_order_id):
        """
        Complete a work order.

        Marks the work order as completed and records the actual end time.
        All associated jobs should be completed before calling this.
        """
        from api.routes.mes_api import complete_work_order
        return complete_work_order(work_order_id)


@mes_ns.route('/work-orders/<string:work_order_id>/operations')
@mes_ns.param('work_order_id', 'Work order ID')
class WorkOrderOperations(Resource):
    """Work order operations endpoint."""

    @mes_ns.doc(
        'add_operation',
        responses={
            201: ('Operation added', operation_model),
            404: 'Work order not found',
            400: 'Validation error',
        }
    )
    @mes_ns.expect(operation_create, validate=True)
    @mes_ns.marshal_with(operation_model, code=201)
    def post(self, work_order_id):
        """
        Add an operation to a work order.

        Operations define the manufacturing steps for the work order.
        They are executed in sequence order.

        **Operation Types:**
        - `design`: CAD/CAM preparation
        - `printing_fdm`: FDM 3D printing
        - `printing_sla`: SLA 3D printing
        - `cnc_milling`: CNC milling
        - `assembly`: Assembly operations
        - `inspection`: Quality inspection
        - `packaging`: Packaging operations
        - `custom`: Custom operations
        """
        from api.routes.mes_api import add_operation
        return add_operation(work_order_id)


# =============================================================================
# RESOURCES - Jobs
# =============================================================================

@mes_ns.route('/jobs')
class JobList(Resource):
    """Job listing and creation."""

    @mes_ns.doc(
        'list_jobs',
        params={
            'machine_id': {'description': 'Filter by machine'},
            'status': {'description': 'Filter by status'},
            'work_order_id': {'description': 'Filter by work order'},
            'limit': {'description': 'Max results', 'default': 100},
        },
        responses={
            200: ('List of jobs', job_list_response),
        }
    )
    @mes_ns.marshal_with(job_list_response)
    def get(self):
        """
        List jobs with optional filtering.

        Jobs represent individual production runs on specific machines.
        A single work order may have multiple jobs across different machines.
        """
        from api.routes.mes_api import list_jobs
        return list_jobs()

    @mes_ns.doc(
        'create_job',
        responses={
            201: ('Job created', job_model),
            400: 'Validation error',
            404: 'Work order not found',
        }
    )
    @mes_ns.expect(job_create, validate=True)
    @mes_ns.marshal_with(job_model, code=201)
    def post(self):
        """
        Create a job for a work order.

        Jobs are the schedulable units of work. They link a work order
        to a specific machine and time slot.

        **Note:** Work order must be in 'released' status to create jobs.
        """
        from api.routes.mes_api import create_job
        return create_job()


@mes_ns.route('/jobs/<string:job_id>/status')
@mes_ns.param('job_id', 'Job ID')
class JobStatus(Resource):
    """Job status update endpoint."""

    @mes_ns.doc(
        'update_job_status',
        responses={
            200: ('Job status updated', job_model),
            404: 'Job not found',
            400: 'Invalid status transition',
        }
    )
    @mes_ns.expect(job_status_update, validate=True)
    @mes_ns.marshal_with(job_model)
    def put(self, job_id):
        """
        Update job status.

        Updates the job status and records relevant timestamps.

        **Valid Transitions:**
        - `pending` -> `queued`
        - `queued` -> `running`
        - `running` -> `paused`, `completed`, `failed`
        - `paused` -> `running`, `cancelled`
        - Any -> `cancelled` (if not completed)
        """
        from api.routes.mes_api import update_job_status
        return update_job_status(job_id)


# =============================================================================
# RESOURCES - Scheduling
# =============================================================================

@mes_ns.route('/schedule')
class Schedule(Resource):
    """Job scheduling endpoint."""

    @mes_ns.doc(
        'schedule_jobs',
        responses={
            200: ('Schedule created', schedule_response),
            400: 'Invalid input',
        }
    )
    @mes_ns.expect(schedule_request, validate=True)
    @mes_ns.marshal_with(schedule_response)
    def post(self):
        """
        Schedule jobs using optimization solver.

        Uses CP-SAT (Constraint Programming) solver to create an
        optimal schedule for the given jobs and machines.

        **Optimization Objectives:**
        - `makespan`: Minimize total completion time
        - `due_date`: Minimize due date violations
        - `setup_time`: Minimize total setup time

        **Constraints:**
        - Machine capacity
        - Job dependencies
        - Job eligibility per machine
        - Setup times between jobs
        """
        from api.routes.mes_api import schedule_jobs
        return schedule_jobs()


@mes_ns.route('/dispatch/<string:machine_id>')
@mes_ns.param('machine_id', 'Machine ID')
class DispatchQueue(Resource):
    """Machine dispatch queue endpoint."""

    @mes_ns.doc(
        'get_dispatch_queue',
        responses={
            200: 'Dispatch queue for machine',
        }
    )
    def get(self, machine_id):
        """
        Get dispatch queue for a machine.

        Returns the prioritized queue of jobs waiting to be
        executed on the specified machine.

        Jobs are ordered by priority score which considers:
        - Job priority
        - Due date urgency
        - Setup optimization
        - Dependencies
        """
        from api.routes.mes_api import get_dispatch_queue
        return get_dispatch_queue(machine_id)


@mes_ns.route('/scheduling/gantt')
class GanttData(Resource):
    """Gantt chart data endpoint."""

    @mes_ns.doc(
        'get_gantt_data',
        responses={
            200: ('Gantt chart data', gantt_response),
        }
    )
    @mes_ns.marshal_with(gantt_response)
    def get(self):
        """
        Get Gantt chart data.

        Returns data formatted for Gantt chart visualization,
        including machines, jobs, and their time allocations.
        """
        from api.routes.mes_api import get_gantt_data
        return get_gantt_data()


@mes_ns.route('/scheduling/capacity')
class CapacityReport(Resource):
    """Capacity utilization endpoint."""

    @mes_ns.doc(
        'get_capacity',
        responses={
            200: 'Capacity utilization report',
        }
    )
    def get(self):
        """
        Get machine capacity utilization.

        Returns capacity utilization metrics for each machine,
        useful for capacity planning and bottleneck identification.
        """
        from api.routes.mes_api import get_capacity
        return get_capacity()


# =============================================================================
# RESOURCES - OEE
# =============================================================================

@mes_ns.route('/oee')
class OEEResource(Resource):
    """OEE metrics endpoint."""

    @mes_ns.doc(
        'get_oee',
        params={
            'machine_id': {'description': 'Filter by machine'},
            'start_date': {'description': 'Period start (ISO format)'},
            'end_date': {'description': 'Period end (ISO format)'},
        },
        responses={
            200: ('OEE metrics', oee_model),
        }
    )
    @mes_ns.marshal_with(oee_model)
    def get(self):
        """
        Get OEE (Overall Equipment Effectiveness) metrics.

        OEE is calculated as: Availability x Performance x Quality

        **Components:**
        - **Availability**: Actual run time / Planned production time
        - **Performance**: Actual output / Theoretical output at run rate
        - **Quality**: Good units / Total units produced

        **World-Class OEE:**
        - Overall OEE: 85%+
        - Availability: 90%+
        - Performance: 95%+
        - Quality: 99%+
        """
        from api.routes.mes_api import get_oee
        return get_oee()


@mes_ns.route('/oee/summary')
class OEESummaryResource(Resource):
    """OEE summary endpoint."""

    @mes_ns.doc(
        'get_oee_summary',
        responses={
            200: ('OEE summary', oee_summary_model),
        }
    )
    @mes_ns.marshal_with(oee_summary_model)
    def get(self):
        """
        Get OEE summary for all machines.

        Returns aggregated OEE metrics across all machines,
        useful for management dashboards.
        """
        from api.routes.mes_api import get_oee_summary
        return get_oee_summary()


# =============================================================================
# RESOURCES - Recipes
# =============================================================================

@mes_ns.route('/recipes')
class RecipeList(Resource):
    """Recipe listing and creation."""

    @mes_ns.doc(
        'list_recipes',
        params={
            'status': {'description': 'Filter by status', 'enum': ['draft', 'pending_approval', 'approved', 'obsolete']},
            'product_id': {'description': 'Filter by product'},
        },
        responses={
            200: 'List of recipes',
        }
    )
    def get(self):
        """
        List recipes (master recipes).

        Recipes define the manufacturing process for products
        following ISA-88 batch control standards.
        """
        from api.routes.mes_api import list_recipes
        return list_recipes()

    @mes_ns.doc(
        'create_recipe',
        responses={
            201: ('Recipe created', recipe_model),
            400: 'Validation error',
        }
    )
    @mes_ns.expect(recipe_create, validate=True)
    @mes_ns.marshal_with(recipe_model, code=201)
    def post(self):
        """
        Create a new recipe.

        Creates a recipe in 'draft' status. It must go through
        the approval workflow before it can be used in production.

        **ISA-88 Recipe Types:**
        - General Recipe: Plant-independent
        - Site Recipe: Site-specific adaptation
        - Master Recipe: Equipment-specific (this API)
        - Control Recipe: Instance for specific batch
        """
        from api.routes.mes_api import create_recipe
        return create_recipe()


@mes_ns.route('/recipes/<string:recipe_id>')
@mes_ns.param('recipe_id', 'Recipe ID')
class RecipeDetail(Resource):
    """Single recipe operations."""

    @mes_ns.doc(
        'get_recipe',
        responses={
            200: ('Recipe details', recipe_model),
            404: 'Recipe not found',
        }
    )
    @mes_ns.marshal_with(recipe_model)
    def get(self, recipe_id):
        """Get recipe details."""
        from api.routes.mes_api import get_recipe
        return get_recipe(recipe_id)

    @mes_ns.doc(
        'update_recipe',
        responses={
            200: ('Recipe updated', recipe_model),
            201: ('New version created (if approved)', recipe_model),
            404: 'Recipe not found',
        }
    )
    @mes_ns.expect(recipe_create)
    @mes_ns.marshal_with(recipe_model)
    def put(self, recipe_id):
        """
        Update a recipe.

        If the recipe is approved, a new version is created instead
        of modifying the existing one (version control).
        """
        from api.routes.mes_api import update_recipe
        return update_recipe(recipe_id)


@mes_ns.route('/recipes/<string:recipe_id>/submit')
@mes_ns.param('recipe_id', 'Recipe ID')
class RecipeSubmit(Resource):
    """Recipe submission endpoint."""

    @mes_ns.doc(
        'submit_recipe',
        responses={
            200: ('Recipe submitted', recipe_model),
            400: 'Cannot submit (invalid status)',
            404: 'Recipe not found',
        }
    )
    def post(self, recipe_id):
        """
        Submit recipe for approval.

        Changes status from 'draft' to 'pending_approval'.
        The recipe will be reviewed before it can be used.
        """
        from api.routes.mes_api import submit_recipe_for_approval
        return submit_recipe_for_approval(recipe_id)


@mes_ns.route('/recipes/<string:recipe_id>/approve')
@mes_ns.param('recipe_id', 'Recipe ID')
class RecipeApprove(Resource):
    """Recipe approval endpoint."""

    @mes_ns.doc(
        'approve_recipe',
        responses={
            200: ('Recipe approved', recipe_model),
            400: 'Cannot approve (invalid status)',
            404: 'Recipe not found',
        }
    )
    def post(self, recipe_id):
        """
        Approve a recipe.

        Changes status to 'approved'. The recipe can now be used
        for production work orders.

        **Note:** Requires approval permissions.
        """
        from api.routes.mes_api import approve_recipe
        return approve_recipe(recipe_id)


@mes_ns.route('/recipes/<string:recipe_id>/download')
@mes_ns.param('recipe_id', 'Recipe ID')
class RecipeDownload(Resource):
    """Recipe download endpoint."""

    @mes_ns.doc(
        'download_recipe',
        params={
            'machine_id': {'description': 'Target machine'},
            'work_order_id': {'description': 'Work order reference'},
        },
        responses={
            200: 'Control recipe instance',
            400: 'Recipe not approved',
            404: 'Recipe not found',
        }
    )
    def get(self, recipe_id):
        """
        Download recipe to machine (create control recipe).

        Creates a control recipe instance for a specific production run.
        This is the recipe that actually controls the machine.
        """
        from api.routes.mes_api import download_recipe
        return download_recipe(recipe_id)


# =============================================================================
# RESOURCES - Labor
# =============================================================================

@mes_ns.route('/labor/workers')
class WorkerList(Resource):
    """Worker listing endpoint."""

    @mes_ns.doc(
        'list_workers',
        responses={
            200: 'List of workers',
        }
    )
    def get(self):
        """
        List workers.

        Returns all workers with their skills and current status.
        """
        from api.routes.mes_api import list_workers
        return list_workers()


@mes_ns.route('/labor/time-entries')
class TimeEntryList(Resource):
    """Time entry management endpoint."""

    @mes_ns.doc(
        'list_time_entries',
        responses={
            200: 'List of time entries',
        }
    )
    def get(self):
        """
        List labor time entries.

        Returns time tracking records for workers.
        """
        from api.routes.mes_api import list_time_entries
        return list_time_entries()

    @mes_ns.doc(
        'create_time_entry',
        responses={
            201: ('Time entry created', time_entry_model),
            400: 'Validation error',
        }
    )
    @mes_ns.expect(time_entry_create, validate=True)
    @mes_ns.marshal_with(time_entry_model, code=201)
    def post(self):
        """
        Create a labor time entry.

        Records time worked by a worker, optionally linked to a job.
        """
        from api.routes.mes_api import create_time_entry
        return create_time_entry()
