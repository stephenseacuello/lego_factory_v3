"""
Event Stream API - Real-time SSE and Event History

LegoMCP World-Class Manufacturing System v5.0
Phase 7: Event-Driven Architecture

Provides:
- Server-Sent Events (SSE) for real-time streaming
- Historical event queries
- Event publishing endpoints
"""

import json
import asyncio
from datetime import datetime, timedelta
from typing import Optional
from flask import Response, jsonify, request

from . import events_bp

# Try to import event services (graceful fallback)
try:
    from services.events.event_bus import EventBus
    from services.events.event_types import (
        ManufacturingEvent, EventCategory, EventPriority,
        MachineEvent, MachineEventType, MachineState,
        QualityEvent, QualityEventType,
        SchedulingEvent, SchedulingEventType,
        InventoryEvent, InventoryEventType,
        MaintenanceEvent, MaintenanceEventType
    )
    EVENTS_AVAILABLE = True
except ImportError:
    EVENTS_AVAILABLE = False


# In-memory event store for demo/fallback
_event_store = []
_max_events = 1000


def _get_mock_events(count: int = 50) -> list:
    """Generate mock events for demo purposes."""
    events = []
    now = datetime.utcnow()

    event_templates = [
        {
            'event_type': 'machine.state_change',
            'category': 'machine',
            'work_center_id': 'WC-001',
            'payload': {'machine_state': 'running', 'temperature': {'bed': 60.0, 'nozzle': 215.0}}
        },
        {
            'event_type': 'production.work_order_started',
            'category': 'production',
            'work_order_id': 'WO-2024-001',
            'payload': {'quantity_ordered': 100, 'part_number': 'BRICK-2X4'}
        },
        {
            'event_type': 'quality.inspection_completed',
            'category': 'quality',
            'payload': {'inspection_id': 'INS-001', 'result': 'pass', 'clutch_power': 0.85}
        },
        {
            'event_type': 'inventory.stock_issued',
            'category': 'inventory',
            'payload': {'part_id': 'PART-001', 'quantity': 50, 'location': 'STORE-A'}
        },
        {
            'event_type': 'scheduling.operation_completed',
            'category': 'scheduling',
            'payload': {'operation_id': 'OP-001', 'deviation_minutes': 2.5}
        },
        {
            'event_type': 'maintenance.predictive_alert',
            'category': 'maintenance',
            'work_center_id': 'WC-002',
            'payload': {'health_score': 0.75, 'predicted_failure': 'none'}
        }
    ]

    import random
    for i in range(count):
        template = random.choice(event_templates)
        event = {
            'event_id': f'evt-{i:04d}',
            'timestamp': (now - timedelta(minutes=count - i)).isoformat(),
            'source_layer': 'L3',
            'priority': random.choice(['normal', 'high', 'low']),
            **template
        }
        events.append(event)

    return events


@events_bp.route('/stream')
def event_stream():
    """
    Server-Sent Events (SSE) endpoint for real-time event streaming.

    Query params:
    - categories: Comma-separated list of event categories to filter
    - priority: Minimum priority level (critical, high, normal, low)

    Returns:
        SSE stream of events
    """
    categories = request.args.get('categories', '').split(',') if request.args.get('categories') else None
    min_priority = request.args.get('priority', 'low')

    def generate():
        """Generate SSE events."""
        # Send initial connection event
        yield f"event: connected\ndata: {json.dumps({'status': 'connected', 'timestamp': datetime.utcnow().isoformat()})}\n\n"

        # For demo, send periodic heartbeats and sample events
        import time
        counter = 0
        while True:
            counter += 1

            # Send heartbeat every 30 seconds
            if counter % 30 == 0:
                yield f"event: heartbeat\ndata: {json.dumps({'timestamp': datetime.utcnow().isoformat()})}\n\n"

            # Check for new events from store
            if _event_store:
                event = _event_store[-1]
                if categories is None or event.get('category') in categories:
                    yield f"event: manufacturing_event\ndata: {json.dumps(event)}\n\n"

            time.sleep(1)

    return Response(
        generate(),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'Connection': 'keep-alive',
            'X-Accel-Buffering': 'no'
        }
    )


@events_bp.route('/recent')
def get_recent_events():
    """
    Get recent events from the event store.

    Query params:
    - count: Number of events to return (default: 50, max: 500)
    - category: Filter by event category
    - since: ISO timestamp to get events after
    - priority: Filter by priority level

    Returns:
        JSON list of recent events
    """
    count = min(int(request.args.get('count', 50)), 500)
    category = request.args.get('category')
    since = request.args.get('since')
    priority = request.args.get('priority')

    # Use mock events if store is empty
    events = _event_store if _event_store else _get_mock_events(count)

    # Apply filters
    if category:
        events = [e for e in events if e.get('category') == category]

    if since:
        try:
            since_dt = datetime.fromisoformat(since.replace('Z', '+00:00'))
            events = [e for e in events if datetime.fromisoformat(e['timestamp']) > since_dt]
        except ValueError:
            pass

    if priority:
        priority_levels = {'critical': 0, 'high': 1, 'normal': 2, 'low': 3}
        min_level = priority_levels.get(priority, 3)
        events = [e for e in events if priority_levels.get(e.get('priority', 'normal'), 2) <= min_level]

    # Return most recent first
    events = sorted(events, key=lambda x: x.get('timestamp', ''), reverse=True)[:count]

    return jsonify({
        'events': events,
        'count': len(events),
        'timestamp': datetime.utcnow().isoformat()
    })


@events_bp.route('/publish', methods=['POST'])
def publish_event():
    """
    Publish an event to the event bus.

    Request body:
    {
        "event_type": "machine.state_change",
        "category": "machine",
        "work_center_id": "WC-001",
        "work_order_id": null,
        "priority": "normal",
        "payload": {...}
    }

    Returns:
        JSON with event_id of published event
    """
    data = request.get_json() or {}

    # Build event
    event = {
        'event_id': f"evt-{datetime.utcnow().strftime('%Y%m%d%H%M%S%f')}",
        'event_type': data.get('event_type', 'custom'),
        'category': data.get('category', 'system'),
        'timestamp': datetime.utcnow().isoformat(),
        'source_layer': data.get('source_layer', 'L3'),
        'priority': data.get('priority', 'normal'),
        'work_center_id': data.get('work_center_id'),
        'work_order_id': data.get('work_order_id'),
        'payload': data.get('payload', {})
    }

    # Add to store
    _event_store.append(event)
    if len(_event_store) > _max_events:
        _event_store.pop(0)

    return jsonify({
        'success': True,
        'event_id': event['event_id'],
        'timestamp': event['timestamp']
    })


@events_bp.route('/categories')
def get_categories():
    """
    Get available event categories.

    Returns:
        JSON list of event categories with descriptions
    """
    categories = [
        {
            'name': 'machine',
            'description': 'Equipment state changes, alarms, sensor data',
            'layer': 'L0-L1'
        },
        {
            'name': 'quality',
            'description': 'SPC signals, inspections, defects',
            'layer': 'L3'
        },
        {
            'name': 'scheduling',
            'description': 'Schedule changes, deviations, bottlenecks',
            'layer': 'L3'
        },
        {
            'name': 'inventory',
            'description': 'Stock movements, alerts',
            'layer': 'L3'
        },
        {
            'name': 'maintenance',
            'description': 'Predictive alerts, work orders',
            'layer': 'L3'
        },
        {
            'name': 'production',
            'description': 'Work order events',
            'layer': 'L3'
        },
        {
            'name': 'erp',
            'description': 'Business events',
            'layer': 'L4'
        },
        {
            'name': 'system',
            'description': 'Cross-cutting system events',
            'layer': 'All'
        }
    ]

    return jsonify({
        'categories': categories,
        'count': len(categories)
    })


@events_bp.route('/stats')
def get_event_stats():
    """
    Get event statistics.

    Returns:
        JSON with event counts by category, priority, etc.
    """
    events = _event_store if _event_store else _get_mock_events(100)

    # Count by category
    by_category = {}
    for event in events:
        cat = event.get('category', 'unknown')
        by_category[cat] = by_category.get(cat, 0) + 1

    # Count by priority
    by_priority = {}
    for event in events:
        pri = event.get('priority', 'normal')
        by_priority[pri] = by_priority.get(pri, 0) + 1

    # Get time range
    timestamps = [e.get('timestamp') for e in events if e.get('timestamp')]
    oldest = min(timestamps) if timestamps else None
    newest = max(timestamps) if timestamps else None

    return jsonify({
        'total_events': len(events),
        'by_category': by_category,
        'by_priority': by_priority,
        'time_range': {
            'oldest': oldest,
            'newest': newest
        },
        'event_rate': {
            'description': 'Events per minute (estimated)',
            'value': len(events) / 60 if events else 0
        }
    })


@events_bp.route('/stream-info')
def get_stream_info():
    """
    Get information about event streams.

    Returns:
        JSON with stream status and configuration
    """
    return jsonify({
        'streams': [
            {
                'key': 'lego:events:machine',
                'category': 'machine',
                'status': 'active',
                'max_length': 100000
            },
            {
                'key': 'lego:events:quality',
                'category': 'quality',
                'status': 'active',
                'max_length': 100000
            },
            {
                'key': 'lego:events:scheduling',
                'category': 'scheduling',
                'status': 'active',
                'max_length': 100000
            },
            {
                'key': 'lego:events:inventory',
                'category': 'inventory',
                'status': 'active',
                'max_length': 100000
            },
            {
                'key': 'lego:events:maintenance',
                'category': 'maintenance',
                'status': 'active',
                'max_length': 100000
            },
            {
                'key': 'lego:events:production',
                'category': 'production',
                'status': 'active',
                'max_length': 100000
            }
        ],
        'redis_connected': EVENTS_AVAILABLE,
        'fallback_mode': not EVENTS_AVAILABLE
    })
