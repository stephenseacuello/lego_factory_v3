"""
Dispatching API Routes.

Provides REST API endpoints for real-time job prioritization
using various dispatching rules (FIFO, SPT, EDD, Critical Ratio, etc.).
"""

from flask import Blueprint, request, jsonify
import logging

logger = logging.getLogger(__name__)

dispatching_bp = Blueprint('dispatching', __name__, url_prefix='/api/dispatching')

# Lazy service initialization
_dispatching_service = None


def get_dispatching_service():
    """Get or create the dispatching service instance."""
    global _dispatching_service
    if _dispatching_service is None:
        from services.dispatching_service import DispatchingService
        _dispatching_service = DispatchingService()
    return _dispatching_service


# =============================================================================
# Queue Management
# =============================================================================

@dispatching_bp.route('/queue', methods=['GET'])
def get_queue():
    """
    Get the current job queue.

    Query Parameters:
        work_center: Filter by work center
        status: Filter by status (waiting, dispatched)
    """
    try:
        service = get_dispatching_service()

        work_center = request.args.get('work_center')
        status = request.args.get('status')

        jobs = list(service.queue.values())

        if work_center:
            jobs = [j for j in jobs if j.work_center == work_center]

        if status:
            from services.dispatching_service import JobStatus
            try:
                status_enum = JobStatus(status)
                jobs = [j for j in jobs if j.status == status_enum]
            except ValueError:
                pass

        # Sort by arrival time
        jobs.sort(key=lambda x: x.arrival_time)

        return jsonify({
            'success': True,
            'queue': [j.to_dict() for j in jobs],
            'count': len(jobs)
        })

    except Exception as e:
        logger.error(f"Error getting queue: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@dispatching_bp.route('/queue', methods=['POST'])
def add_to_queue():
    """
    Add a job to the dispatch queue.

    Request Body:
        job_id: Unique job identifier (required)
        work_order_id: Associated work order (required)
        operation_id: Operation ID (required)
        work_center: Work center (required)
        processing_time_min: Estimated processing time (required)
        due_date: Job due date (optional, ISO format)
        priority: Priority weight 1-10 (default 5)
        setup_time_min: Setup time if different from previous job (optional)
    """
    try:
        data = request.get_json()

        if not data:
            return jsonify({
                'success': False,
                'error': 'Request body required'
            }), 400

        required = ['job_id', 'work_order_id', 'operation_id', 'work_center', 'processing_time_min']
        missing = [f for f in required if f not in data]
        if missing:
            return jsonify({
                'success': False,
                'error': f'Missing required fields: {missing}'
            }), 400

        service = get_dispatching_service()

        # Parse due date
        due_date = None
        if data.get('due_date'):
            from datetime import datetime
            due_date = datetime.fromisoformat(data['due_date'].replace('Z', '+00:00'))

        job = service.add_to_queue(
            job_id=data['job_id'],
            work_order_id=data['work_order_id'],
            operation_id=data['operation_id'],
            work_center=data['work_center'],
            processing_time_min=data['processing_time_min'],
            due_date=due_date,
            priority=data.get('priority', 5),
            setup_time_min=data.get('setup_time_min', 0)
        )

        return jsonify({
            'success': True,
            'job': job.to_dict()
        }), 201

    except Exception as e:
        logger.error(f"Error adding to queue: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@dispatching_bp.route('/queue/<job_id>', methods=['DELETE'])
def remove_from_queue(job_id: str):
    """Remove a job from the queue."""
    try:
        service = get_dispatching_service()

        if job_id in service.queue:
            del service.queue[job_id]
            return jsonify({
                'success': True,
                'message': f'Job {job_id} removed from queue'
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Job not found in queue'
            }), 404

    except Exception as e:
        logger.error(f"Error removing from queue: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


# =============================================================================
# Dispatching Operations
# =============================================================================

@dispatching_bp.route('/dispatch', methods=['POST'])
def dispatch_next():
    """
    Dispatch the next job for a work center/machine.

    Request Body:
        work_center: Work center ID (required)
        machine_id: Machine ID (required)
        rule: Dispatching rule (default FIFO)
            - FIFO: First In First Out
            - LIFO: Last In First Out
            - SPT: Shortest Processing Time
            - LPT: Longest Processing Time
            - EDD: Earliest Due Date
            - MST: Minimum Slack Time
            - CR: Critical Ratio
            - WSPT: Weighted Shortest Processing Time
            - ATC: Apparent Tardiness Cost
            - COVERT: Cost Over Time
    """
    try:
        data = request.get_json()

        if not data or not data.get('work_center') or not data.get('machine_id'):
            return jsonify({
                'success': False,
                'error': 'work_center and machine_id required'
            }), 400

        service = get_dispatching_service()

        # Parse rule
        rule = None
        if data.get('rule'):
            from services.dispatching_service import DispatchingRule
            try:
                rule = DispatchingRule(data['rule'].upper())
            except ValueError:
                return jsonify({
                    'success': False,
                    'error': f'Invalid rule: {data["rule"]}. Valid rules: FIFO, LIFO, SPT, LPT, EDD, MST, CR, WSPT, ATC, COVERT'
                }), 400

        decision = service.dispatch_next(
            work_center=data['work_center'],
            machine_id=data['machine_id'],
            rule=rule
        )

        if decision:
            return jsonify({
                'success': True,
                'decision': decision.to_dict()
            })
        else:
            return jsonify({
                'success': False,
                'error': 'No jobs available for dispatch'
            }), 404

    except Exception as e:
        logger.error(f"Error dispatching: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@dispatching_bp.route('/rank', methods=['GET'])
def rank_queue():
    """
    Rank jobs in queue by a dispatching rule.

    Query Parameters:
        work_center: Work center to rank (required)
        rule: Dispatching rule (default FIFO)
        top_n: Number of top jobs to return (default 10)
    """
    try:
        service = get_dispatching_service()

        work_center = request.args.get('work_center')
        if not work_center:
            return jsonify({
                'success': False,
                'error': 'work_center required'
            }), 400

        rule_str = request.args.get('rule', 'FIFO').upper()
        top_n = request.args.get('top_n', 10, type=int)

        from services.dispatching_service import DispatchingRule
        try:
            rule = DispatchingRule(rule_str)
        except ValueError:
            return jsonify({
                'success': False,
                'error': f'Invalid rule: {rule_str}'
            }), 400

        ranked = service.rank_queue(
            work_center=work_center,
            rule=rule,
            top_n=top_n
        )

        return jsonify({
            'success': True,
            'ranked_jobs': ranked,
            'rule': rule_str,
            'count': len(ranked)
        })

    except Exception as e:
        logger.error(f"Error ranking queue: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@dispatching_bp.route('/compare-rules', methods=['GET'])
def compare_rules():
    """
    Compare different dispatching rules for a work center.

    Query Parameters:
        work_center: Work center to compare (required)
    """
    try:
        service = get_dispatching_service()

        work_center = request.args.get('work_center')
        if not work_center:
            return jsonify({
                'success': False,
                'error': 'work_center required'
            }), 400

        comparison = service.compare_rules(work_center)

        return jsonify({
            'success': True,
            'comparison': comparison
        })

    except Exception as e:
        logger.error(f"Error comparing rules: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


# =============================================================================
# Rules Information
# =============================================================================

@dispatching_bp.route('/rules', methods=['GET'])
def list_rules():
    """List all available dispatching rules with descriptions."""
    try:
        rules = [
            {
                'name': 'FIFO',
                'description': 'First In First Out - Jobs processed in arrival order',
                'best_for': 'Fair scheduling, simple environments'
            },
            {
                'name': 'LIFO',
                'description': 'Last In First Out - Most recent jobs first',
                'best_for': 'Minimizing WIP in certain scenarios'
            },
            {
                'name': 'SPT',
                'description': 'Shortest Processing Time - Quick jobs first',
                'best_for': 'Minimizing average flow time and WIP'
            },
            {
                'name': 'LPT',
                'description': 'Longest Processing Time - Long jobs first',
                'best_for': 'Load balancing across machines'
            },
            {
                'name': 'EDD',
                'description': 'Earliest Due Date - Most urgent jobs first',
                'best_for': 'Minimizing maximum tardiness'
            },
            {
                'name': 'MST',
                'description': 'Minimum Slack Time - Least buffer time first',
                'best_for': 'Balancing urgency with processing needs'
            },
            {
                'name': 'CR',
                'description': 'Critical Ratio - Time remaining / work remaining',
                'best_for': 'Dynamic prioritization based on urgency'
            },
            {
                'name': 'WSPT',
                'description': 'Weighted Shortest Processing Time - Priority-weighted SPT',
                'best_for': 'Balancing speed with priority'
            },
            {
                'name': 'ATC',
                'description': 'Apparent Tardiness Cost - Sophisticated due-date rule',
                'best_for': 'Minimizing weighted tardiness'
            },
            {
                'name': 'COVERT',
                'description': 'Cost Over Time - Expected tardiness cost ratio',
                'best_for': 'Cost-sensitive tardiness minimization'
            }
        ]

        return jsonify({
            'success': True,
            'rules': rules
        })

    except Exception as e:
        logger.error(f"Error listing rules: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


# =============================================================================
# Analytics
# =============================================================================

@dispatching_bp.route('/analytics/work-center/<work_center>', methods=['GET'])
def get_work_center_analytics(work_center: str):
    """Get dispatching analytics for a work center."""
    try:
        service = get_dispatching_service()

        # Get jobs for this work center
        jobs = [j for j in service.queue.values() if j.work_center == work_center]

        from services.dispatching_service import JobStatus
        from datetime import datetime

        waiting = [j for j in jobs if j.status == JobStatus.WAITING]
        dispatched = [j for j in jobs if j.status == JobStatus.DISPATCHED]

        # Calculate metrics
        total_processing = sum(j.processing_time_min for j in waiting)
        total_setup = sum(j.setup_time_min for j in waiting)

        # Count jobs by priority
        by_priority = {}
        for j in waiting:
            p = j.priority
            by_priority[p] = by_priority.get(p, 0) + 1

        # Count overdue
        now = datetime.now()
        overdue = sum(1 for j in waiting if j.due_date and j.due_date < now)

        return jsonify({
            'success': True,
            'analytics': {
                'work_center': work_center,
                'jobs_waiting': len(waiting),
                'jobs_dispatched': len(dispatched),
                'total_processing_time_min': total_processing,
                'total_setup_time_min': total_setup,
                'estimated_queue_time_min': total_processing + total_setup,
                'by_priority': by_priority,
                'overdue_count': overdue
            }
        })

    except Exception as e:
        logger.error(f"Error getting work center analytics: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@dispatching_bp.route('/history', methods=['GET'])
def get_dispatch_history():
    """
    Get dispatch decision history.

    Query Parameters:
        work_center: Filter by work center
        machine_id: Filter by machine
        limit: Maximum results (default 50)
    """
    try:
        service = get_dispatching_service()

        work_center = request.args.get('work_center')
        machine_id = request.args.get('machine_id')
        limit = request.args.get('limit', 50, type=int)

        history = list(service.dispatch_history)

        if work_center:
            history = [h for h in history if h.work_center == work_center]

        if machine_id:
            history = [h for h in history if h.machine_id == machine_id]

        # Sort by dispatch time descending
        history.sort(key=lambda x: x.dispatch_time, reverse=True)

        # Apply limit
        history = history[:limit]

        return jsonify({
            'success': True,
            'history': [h.to_dict() for h in history],
            'count': len(history)
        })

    except Exception as e:
        logger.error(f"Error getting dispatch history: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500
