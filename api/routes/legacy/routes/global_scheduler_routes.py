"""
Global Scheduler Routes
========================
REST API endpoints for enterprise cross-plant scheduling.

Provides:
- Job routing to optimal plants
- Global schedule state queries
- Plant management
- Cross-region synchronization

Author: Flask CNC SCADA System
"""

import asyncio
import logging
from datetime import datetime
from functools import wraps
from typing import Any, Dict, List, Optional

from flask import Blueprint, request, jsonify, g

logger = logging.getLogger(__name__)

# Blueprint for global scheduler routes
global_scheduler_bp = Blueprint(
    'global_scheduler',
    __name__,
    url_prefix='/api/global-scheduler'
)


# =============================================================================
# Lazy Service Imports
# =============================================================================

def get_scheduler():
    """Lazy import of global scheduler service."""
    from services.global_scheduler_service import get_global_scheduler
    return get_global_scheduler()


def run_async(coro):
    """Run async coroutine in sync context."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


# =============================================================================
# Plant Management
# =============================================================================

@global_scheduler_bp.route('/plants', methods=['GET'])
def list_plants():
    """
    List all registered plants.

    Query params:
    - region: Filter by region (e.g., us-east, eu-west)
    - status: Filter by status (online, offline, maintenance)

    Response:
    {
        "plants": [...],
        "total": 10,
        "online": 8
    }
    """
    scheduler = get_scheduler()
    region_filter = request.args.get('region')
    status_filter = request.args.get('status')

    plants = []
    for plant in scheduler.plants.values():
        if region_filter and plant.region.value != region_filter:
            continue
        if status_filter and plant.status.value != status_filter:
            continue

        plants.append({
            'plant_id': plant.plant_id,
            'name': plant.name,
            'region': plant.region.value,
            'status': plant.status.value,
            'machine_count': plant.machine_count,
            'available_machines': plant.available_machines,
            'utilization': plant.current_utilization,
            'avg_oee': plant.avg_oee,
            'avg_queue_time_hours': plant.avg_queue_time_hours,
            'capabilities': list(plant.capabilities),
            'data_zone': plant.data_zone.value,
            'hourly_rate': plant.hourly_rate
        })

    online_count = len([p for p in plants if p['status'] == 'online'])

    return jsonify({
        'plants': plants,
        'total': len(plants),
        'online': online_count
    })


@global_scheduler_bp.route('/plants/<plant_id>', methods=['GET'])
def get_plant(plant_id: str):
    """Get detailed plant information."""
    scheduler = get_scheduler()
    plant = scheduler.get_plant(plant_id)

    if not plant:
        return jsonify({'error': 'Plant not found'}), 404

    return jsonify({
        'plant_id': plant.plant_id,
        'name': plant.name,
        'region': plant.region.value,
        'timezone': plant.timezone,
        'status': plant.status.value,
        'machine_count': plant.machine_count,
        'available_machines': plant.available_machines,
        'current_utilization': plant.current_utilization,
        'avg_oee': plant.avg_oee,
        'avg_queue_time_hours': plant.avg_queue_time_hours,
        'capabilities': list(plant.capabilities),
        'max_part_size_mm': list(plant.max_part_size_mm),
        'hourly_rate': plant.hourly_rate,
        'energy_cost_kwh': plant.energy_cost_kwh,
        'data_zone': plant.data_zone.value,
        'latency_ms': plant.latency_ms,
        'last_heartbeat': plant.last_heartbeat
    })


@global_scheduler_bp.route('/plants', methods=['POST'])
def register_plant():
    """
    Register a new plant.

    Request body:
    {
        "plant_id": "plant-us-east-1",
        "name": "US East Manufacturing",
        "region": "us-east",
        "timezone": "America/New_York",
        "machine_count": 10,
        "capabilities": ["3axis", "5axis", "turning"],
        "max_part_size_mm": [500, 500, 500],
        "hourly_rate": 120.0,
        "data_zone": "ccpa"
    }
    """
    data = request.get_json() or {}

    required_fields = ['plant_id', 'name', 'region']
    for field in required_fields:
        if field not in data:
            return jsonify({'error': f'{field} is required'}), 400

    from services.global_scheduler_service import (
        PlantInfo, Region, PlantStatus, DataSovereigntyZone
    )

    try:
        plant = PlantInfo(
            plant_id=data['plant_id'],
            name=data['name'],
            region=Region(data['region']),
            timezone=data.get('timezone', 'UTC'),
            status=PlantStatus(data.get('status', 'online')),
            machine_count=data.get('machine_count', 0),
            available_machines=data.get('available_machines', data.get('machine_count', 0)),
            capabilities=set(data.get('capabilities', [])),
            max_part_size_mm=tuple(data.get('max_part_size_mm', [500, 500, 500])),
            hourly_rate=data.get('hourly_rate', 100.0),
            energy_cost_kwh=data.get('energy_cost_kwh', 0.12),
            data_zone=DataSovereigntyZone(data.get('data_zone', 'global'))
        )

        scheduler = get_scheduler()
        success = scheduler.register_plant(plant)

        if success:
            return jsonify({
                'status': 'registered',
                'plant_id': plant.plant_id
            }), 201
        else:
            return jsonify({'error': 'Registration failed'}), 500

    except ValueError as e:
        return jsonify({'error': str(e)}), 400


@global_scheduler_bp.route('/plants/<plant_id>/status', methods=['PUT'])
def update_plant_status(plant_id: str):
    """
    Update plant status and metrics.

    Request body:
    {
        "status": "online",
        "utilization": 0.75,
        "available_machines": 8,
        "oee": 0.87
    }
    """
    data = request.get_json() or {}
    scheduler = get_scheduler()

    from services.global_scheduler_service import PlantStatus

    success = scheduler.update_plant_status(
        plant_id=plant_id,
        status=PlantStatus(data['status']) if 'status' in data else None,
        utilization=data.get('utilization'),
        available_machines=data.get('available_machines'),
        oee=data.get('oee')
    )

    if success:
        return jsonify({'status': 'updated'})
    else:
        return jsonify({'error': 'Plant not found'}), 404


# =============================================================================
# Job Routing
# =============================================================================

@global_scheduler_bp.route('/route', methods=['POST'])
def route_job():
    """
    Route a job to the optimal plant.

    Request body:
    {
        "job_id": "job-123",
        "part_number": "PART-001",
        "quantity": 100,
        "priority": "high",
        "required_capabilities": ["3axis", "aluminum"],
        "due_date": "2024-01-15T00:00:00Z",
        "estimated_hours": 8.5,
        "allowed_regions": ["us-east", "us-west"],
        "data_zone": "ccpa",
        "preferences": {
            "strategy": "balanced",
            "weight_capacity": 0.3,
            "weight_cost": 0.2
        }
    }

    Response:
    {
        "allocation": {
            "job_id": "job-123",
            "plant_id": "plant-us-east-1",
            "region": "us-east",
            "estimated_start": "2024-01-10T08:00:00Z",
            "estimated_completion": "2024-01-10T16:30:00Z",
            "confidence": 0.92,
            "routing_score": 87.5,
            "reasoning": "capacity:85, capability:100, geography:100, cost:70"
        }
    }
    """
    data = request.get_json() or {}

    if 'job_id' not in data or 'part_number' not in data:
        return jsonify({'error': 'job_id and part_number are required'}), 400

    from services.global_scheduler_service import (
        GlobalJob, JobPriority, Region, DataSovereigntyZone, RoutingPreferences
    )

    # Parse due date
    due_date = None
    if 'due_date' in data:
        try:
            due_date = datetime.fromisoformat(data['due_date'].replace('Z', '+00:00'))
        except ValueError:
            return jsonify({'error': 'Invalid due_date format'}), 400

    # Parse allowed regions
    allowed_regions = set()
    if 'allowed_regions' in data:
        try:
            allowed_regions = {Region(r) for r in data['allowed_regions']}
        except ValueError as e:
            return jsonify({'error': f'Invalid region: {e}'}), 400

    # Create job
    job = GlobalJob(
        job_id=data['job_id'],
        part_number=data['part_number'],
        quantity=data.get('quantity', 1),
        priority=JobPriority(data.get('priority', 'normal')),
        required_capabilities=set(data.get('required_capabilities', [])),
        due_date=due_date,
        estimated_hours=data.get('estimated_hours', 1.0),
        allowed_regions=allowed_regions,
        preferred_plant=data.get('preferred_plant'),
        customer_id=data.get('customer_id'),
        data_zone=DataSovereigntyZone(data.get('data_zone', 'global')),
        contains_pii=data.get('contains_pii', False)
    )

    # Parse preferences
    prefs = None
    if 'preferences' in data:
        pref_data = data['preferences']
        from services.global_scheduler_service import RoutingStrategy
        prefs = RoutingPreferences(
            strategy=RoutingStrategy(pref_data.get('strategy', 'balanced')),
            weight_capacity=pref_data.get('weight_capacity', 0.25),
            weight_capability=pref_data.get('weight_capability', 0.25),
            weight_geography=pref_data.get('weight_geography', 0.20),
            weight_cost=pref_data.get('weight_cost', 0.15),
            weight_performance=pref_data.get('weight_performance', 0.15)
        )

    # Route the job
    scheduler = get_scheduler()
    allocation = run_async(scheduler.route_job(job, prefs))

    if allocation:
        return jsonify({
            'allocation': {
                'job_id': allocation.job_id,
                'plant_id': allocation.plant_id,
                'region': allocation.region.value,
                'estimated_start': allocation.estimated_start.isoformat(),
                'estimated_completion': allocation.estimated_completion.isoformat(),
                'confidence': allocation.confidence,
                'routing_score': allocation.routing_score,
                'reasoning': allocation.reasoning
            }
        })
    else:
        return jsonify({
            'error': 'No suitable plant found',
            'job_id': job.job_id
        }), 404


@global_scheduler_bp.route('/route/batch', methods=['POST'])
def route_jobs_batch():
    """
    Route multiple jobs optimally.

    Request body:
    {
        "jobs": [
            {"job_id": "job-1", "part_number": "PART-001", ...},
            {"job_id": "job-2", "part_number": "PART-002", ...}
        ],
        "preferences": {...}
    }

    Response:
    {
        "allocations": {
            "job-1": {...},
            "job-2": {...}
        },
        "success_count": 2,
        "failed_count": 0
    }
    """
    data = request.get_json() or {}
    jobs_data = data.get('jobs', [])

    if not jobs_data:
        return jsonify({'error': 'jobs array is required'}), 400

    from services.global_scheduler_service import (
        GlobalJob, JobPriority, Region, DataSovereigntyZone, RoutingPreferences,
        RoutingStrategy
    )

    jobs = []
    for jd in jobs_data:
        job = GlobalJob(
            job_id=jd['job_id'],
            part_number=jd['part_number'],
            quantity=jd.get('quantity', 1),
            priority=JobPriority(jd.get('priority', 'normal')),
            required_capabilities=set(jd.get('required_capabilities', [])),
            estimated_hours=jd.get('estimated_hours', 1.0)
        )
        jobs.append(job)

    # Parse preferences
    prefs = None
    if 'preferences' in data:
        pref_data = data['preferences']
        prefs = RoutingPreferences(
            strategy=RoutingStrategy(pref_data.get('strategy', 'balanced'))
        )

    scheduler = get_scheduler()
    allocations = run_async(scheduler.route_jobs_batch(jobs, prefs))

    result = {}
    for job_id, alloc in allocations.items():
        result[job_id] = {
            'plant_id': alloc.plant_id,
            'region': alloc.region.value,
            'estimated_start': alloc.estimated_start.isoformat(),
            'estimated_completion': alloc.estimated_completion.isoformat(),
            'routing_score': alloc.routing_score
        }

    return jsonify({
        'allocations': result,
        'success_count': len(result),
        'failed_count': len(jobs) - len(result)
    })


# =============================================================================
# Global State
# =============================================================================

@global_scheduler_bp.route('/state', methods=['GET'])
def get_global_state():
    """
    Get global schedule state.

    Response:
    {
        "timestamp": "2024-01-10T12:00:00Z",
        "total_jobs": 150,
        "pending_jobs": 25,
        "active_jobs": 45,
        "completed_jobs": 80,
        "jobs_by_region": {...},
        "utilization_by_region": {...}
    }
    """
    scheduler = get_scheduler()
    state = scheduler.get_global_state()

    return jsonify({
        'timestamp': state.timestamp.isoformat(),
        'total_jobs': state.total_jobs,
        'pending_jobs': state.pending_jobs,
        'active_jobs': state.active_jobs,
        'completed_jobs': state.completed_jobs,
        'jobs_by_region': state.jobs_by_region,
        'utilization_by_region': state.utilization_by_region,
        'avg_wait_time_hours': state.avg_wait_time_hours,
        'on_time_delivery_rate': state.on_time_delivery_rate
    })


@global_scheduler_bp.route('/metrics', methods=['GET'])
def get_metrics():
    """Get scheduler metrics."""
    scheduler = get_scheduler()
    return jsonify(scheduler.get_metrics())


# =============================================================================
# Health
# =============================================================================

@global_scheduler_bp.route('/health', methods=['GET'])
def health():
    """Health check for global scheduler."""
    scheduler = get_scheduler()
    online_plants = scheduler.get_online_plants()

    return jsonify({
        'status': 'healthy' if online_plants else 'degraded',
        'registered_plants': len(scheduler.plants),
        'online_plants': len(online_plants),
        'metrics': scheduler.get_metrics()
    })
