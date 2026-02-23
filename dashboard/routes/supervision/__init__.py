"""
Supervision Routes

Dashboard routes for OTP-style supervision monitoring.
Industry 4.0/5.0 Architecture - ISA-95 Compliant Fault Tolerance

LEGO MCP Manufacturing System v7.0
"""

from flask import Blueprint, render_template, jsonify, request
from datetime import datetime
from typing import Dict, List, Any, Optional

supervision_bp = Blueprint(
    'supervision',
    __name__,
    url_prefix='/supervision',
    template_folder='../../templates/pages/supervision'
)


# Mock supervision data (in production, this would come from ROS2)
_mock_supervision_tree = {
    "root_supervisor": {
        "id": "root",
        "name": "RootSupervisor",
        "strategy": "one_for_all",
        "state": "running",
        "restarts": 0,
        "children": [
            {
                "id": "safety",
                "name": "SafetySupervisor",
                "strategy": "one_for_all",
                "state": "running",
                "restarts": 0,
                "children": [
                    {
                        "id": "safety_node",
                        "name": "safety_node",
                        "type": "lifecycle_node",
                        "state": "active",
                        "restarts": 0,
                        "last_heartbeat": datetime.now().isoformat(),
                        "health": {"cpu": 5.2, "memory_mb": 64, "errors": 0},
                    },
                    {
                        "id": "watchdog_node",
                        "name": "watchdog_node",
                        "type": "lifecycle_node",
                        "state": "active",
                        "restarts": 0,
                        "last_heartbeat": datetime.now().isoformat(),
                        "health": {"cpu": 2.1, "memory_mb": 32, "errors": 0},
                    },
                ],
            },
            {
                "id": "equipment",
                "name": "EquipmentSupervisor",
                "strategy": "one_for_one",
                "state": "running",
                "restarts": 0,
                "children": [
                    {
                        "id": "grbl_node",
                        "name": "grbl_node",
                        "type": "lifecycle_node",
                        "state": "active",
                        "restarts": 1,
                        "last_heartbeat": datetime.now().isoformat(),
                        "health": {"cpu": 15.3, "memory_mb": 128, "errors": 0},
                    },
                    {
                        "id": "formlabs_node",
                        "name": "formlabs_node",
                        "type": "lifecycle_node",
                        "state": "active",
                        "restarts": 0,
                        "last_heartbeat": datetime.now().isoformat(),
                        "health": {"cpu": 8.7, "memory_mb": 96, "errors": 0},
                    },
                    {
                        "id": "bambu_node",
                        "name": "bambu_node",
                        "type": "lifecycle_node",
                        "state": "inactive",
                        "restarts": 0,
                        "last_heartbeat": datetime.now().isoformat(),
                        "health": {"cpu": 0, "memory_mb": 0, "errors": 0},
                    },
                ],
            },
            {
                "id": "robotics",
                "name": "RoboticsSupervisor",
                "strategy": "rest_for_one",
                "state": "running",
                "restarts": 0,
                "children": [
                    {
                        "id": "moveit_node",
                        "name": "moveit_node",
                        "type": "node",
                        "state": "active",
                        "restarts": 0,
                        "last_heartbeat": datetime.now().isoformat(),
                        "health": {"cpu": 25.1, "memory_mb": 512, "errors": 0},
                    },
                    {
                        "id": "ned2_node",
                        "name": "ned2_node",
                        "type": "lifecycle_node",
                        "state": "active",
                        "restarts": 0,
                        "last_heartbeat": datetime.now().isoformat(),
                        "health": {"cpu": 12.4, "memory_mb": 256, "errors": 0},
                    },
                ],
            },
        ],
    }
}


@supervision_bp.route('/')
def supervision_dashboard():
    """Supervision dashboard main page."""
    return render_template(
        'supervision/dashboard.html',
        title='Supervision Tree',
        supervision_tree=_mock_supervision_tree,
    )


@supervision_bp.route('/api/tree')
def get_supervision_tree():
    """Get current supervision tree state."""
    return jsonify({
        "success": True,
        "tree": _mock_supervision_tree,
        "timestamp": datetime.now().isoformat(),
    })


@supervision_bp.route('/api/node/<node_id>')
def get_node_status(node_id: str):
    """Get status of a specific node."""
    def find_node(tree: Dict, target_id: str) -> Optional[Dict]:
        if tree.get('id') == target_id:
            return tree
        for child in tree.get('children', []):
            result = find_node(child, target_id)
            if result:
                return result
        return None

    node = find_node(_mock_supervision_tree['root_supervisor'], node_id)
    if node:
        return jsonify({"success": True, "node": node})
    return jsonify({"success": False, "error": "Node not found"}), 404


@supervision_bp.route('/api/node/<node_id>/restart', methods=['POST'])
def restart_node(node_id: str):
    """Request node restart."""
    # In production, this would call the supervisor service
    return jsonify({
        "success": True,
        "message": f"Restart requested for {node_id}",
        "timestamp": datetime.now().isoformat(),
    })


@supervision_bp.route('/api/node/<node_id>/lifecycle/<action>', methods=['POST'])
def lifecycle_action(node_id: str, action: str):
    """Perform lifecycle action on a node."""
    valid_actions = ['configure', 'activate', 'deactivate', 'cleanup', 'shutdown']
    if action not in valid_actions:
        return jsonify({
            "success": False,
            "error": f"Invalid action. Valid: {valid_actions}"
        }), 400

    return jsonify({
        "success": True,
        "message": f"Lifecycle {action} requested for {node_id}",
        "timestamp": datetime.now().isoformat(),
    })


@supervision_bp.route('/api/heartbeats')
def get_heartbeats():
    """Get recent heartbeat data."""
    heartbeats = []

    def collect_heartbeats(node: Dict):
        if 'last_heartbeat' in node:
            heartbeats.append({
                "node_id": node['id'],
                "name": node['name'],
                "state": node.get('state', 'unknown'),
                "last_heartbeat": node['last_heartbeat'],
                "health": node.get('health', {}),
            })
        for child in node.get('children', []):
            collect_heartbeats(child)

    collect_heartbeats(_mock_supervision_tree['root_supervisor'])

    return jsonify({
        "success": True,
        "heartbeats": heartbeats,
        "timestamp": datetime.now().isoformat(),
    })


@supervision_bp.route('/api/metrics')
def get_supervision_metrics():
    """Get supervision system metrics."""
    metrics = {
        "total_nodes": 0,
        "active_nodes": 0,
        "inactive_nodes": 0,
        "total_restarts": 0,
        "supervisors": 0,
        "lifecycle_nodes": 0,
    }

    def count_nodes(node: Dict):
        if 'strategy' in node:
            metrics['supervisors'] += 1
        else:
            metrics['total_nodes'] += 1
            if node.get('type') == 'lifecycle_node':
                metrics['lifecycle_nodes'] += 1
            if node.get('state') == 'active':
                metrics['active_nodes'] += 1
            else:
                metrics['inactive_nodes'] += 1
            metrics['total_restarts'] += node.get('restarts', 0)

        for child in node.get('children', []):
            count_nodes(child)

    count_nodes(_mock_supervision_tree['root_supervisor'])

    return jsonify({
        "success": True,
        "metrics": metrics,
        "timestamp": datetime.now().isoformat(),
    })


@supervision_bp.route('/api/checkpoints')
def get_checkpoints():
    """Get available checkpoints."""
    # Mock checkpoint data
    checkpoints = [
        {
            "id": "job_123_20240115_103000",
            "name": "job_123",
            "type": "periodic",
            "timestamp": "2024-01-15T10:30:00Z",
            "node_id": "orchestrator",
            "size_bytes": 1024,
        },
        {
            "id": "grbl_20240115_102500",
            "name": "grbl_state",
            "type": "manual",
            "timestamp": "2024-01-15T10:25:00Z",
            "node_id": "grbl_node",
            "size_bytes": 512,
        },
    ]

    return jsonify({
        "success": True,
        "checkpoints": checkpoints,
        "timestamp": datetime.now().isoformat(),
    })


@supervision_bp.route('/api/checkpoints/<checkpoint_id>/restore', methods=['POST'])
def restore_checkpoint(checkpoint_id: str):
    """Restore from a checkpoint."""
    return jsonify({
        "success": True,
        "message": f"Checkpoint {checkpoint_id} restored",
        "timestamp": datetime.now().isoformat(),
    })


# Strategy information endpoint
@supervision_bp.route('/api/strategies')
def get_strategies():
    """Get information about supervision strategies."""
    strategies = {
        "one_for_one": {
            "name": "One for One",
            "description": "Restart only the failed child node",
            "use_case": "Independent nodes (equipment)",
            "color": "#4CAF50",
        },
        "one_for_all": {
            "name": "One for All",
            "description": "Restart ALL children when ANY fails",
            "use_case": "Tightly coupled systems (safety)",
            "color": "#F44336",
        },
        "rest_for_one": {
            "name": "Rest for One",
            "description": "Restart failed child and all started after it",
            "use_case": "Ordered dependencies (robotics)",
            "color": "#FF9800",
        },
    }

    return jsonify({
        "success": True,
        "strategies": strategies,
    })


__all__ = ['supervision_bp']
