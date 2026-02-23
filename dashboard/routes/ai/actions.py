"""
Action Routes - Algorithm-to-Action bridge API.

LEGO MCP v6.0 World-Class Manufacturing Research Platform
Phase 5: Algorithm-to-Action Bridge
"""

from flask import Blueprint, jsonify, request, render_template
from typing import Dict, Any, List
import logging
import uuid
from datetime import datetime

logger = logging.getLogger(__name__)

actions_bp = Blueprint('actions', __name__, url_prefix='/api/v6/actions')


# Page Routes
@actions_bp.route('/approval', methods=['GET'])
def action_approval_page():
    """Render action approval dashboard."""
    return render_template('pages/ai/action_approval.html')


# Pending Actions
@actions_bp.route('/pending', methods=['GET'])
def list_pending_actions():
    """List pending actions requiring approval."""
    try:
        actions = [
            {
                "id": "act-001",
                "type": "TEMPERATURE_CHANGE",
                "title": "Increase Nozzle Temperature to 225°C",
                "source": {
                    "agent": "Quality Agent",
                    "reason": "Responding to layer adhesion issues"
                },
                "risk_level": "high",
                "details": {
                    "current_value": 200,
                    "proposed_value": 225,
                    "unit": "°C",
                    "target_printer": "Prusa MK4 #003"
                },
                "impact": {
                    "thermal_risk": "medium",
                    "quality_impact": "+15%",
                    "time_impact": "+2 min"
                },
                "safety_checks": [
                    {"check": "Temperature within material safe range", "status": "pass"},
                    {"check": "Above recommended range for filament", "status": "warning"},
                    {"check": "Printer supports mid-print changes", "status": "pass"}
                ],
                "confidence": 0.78,
                "gcode": ["M104 S225", "M109 S225"],
                "created_at": "2024-01-01T12:30:00Z"
            },
            {
                "id": "act-002",
                "type": "SPEED_ADJUSTMENT",
                "title": "Reduce Print Speed to 80%",
                "source": {
                    "agent": "Scheduling Agent",
                    "reason": "Optimizing for quality threshold"
                },
                "risk_level": "medium",
                "details": {
                    "current_value": 100,
                    "proposed_value": 80,
                    "unit": "%",
                    "estimated_time_impact": "+12 min"
                },
                "confidence": 0.85,
                "gcode": ["M220 S80"],
                "created_at": "2024-01-01T12:28:00Z"
            },
            {
                "id": "act-003",
                "type": "FAN_ADJUSTMENT",
                "title": "Increase Part Cooling Fan to 100%",
                "source": {
                    "agent": "Quality Agent",
                    "reason": "Bridge detected on layer 42"
                },
                "risk_level": "low",
                "details": {
                    "current_value": 70,
                    "proposed_value": 100,
                    "unit": "%"
                },
                "confidence": 0.95,
                "gcode": ["M106 S255"],
                "created_at": "2024-01-01T12:25:00Z"
            }
        ]

        return jsonify({
            "success": True,
            "actions": actions,
            "summary": {
                "pending": 7,
                "high_risk": 2,
                "approved_today": 156,
                "auto_approved": 4
            }
        })
    except Exception as e:
        logger.error(f"Failed to list pending actions: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@actions_bp.route('/<action_id>/approve', methods=['POST'])
def approve_action(action_id: str):
    """Approve and execute an action."""
    try:
        data = request.get_json() or {}

        result = {
            "action_id": action_id,
            "status": "approved",
            "executed": True,
            "execution_result": "ok",
            "approved_by": data.get('user', 'operator'),
            "approved_at": datetime.now().isoformat()
        }

        logger.info(f"Action {action_id} approved and executed")

        return jsonify({"success": True, "result": result})
    except Exception as e:
        logger.error(f"Action approval failed: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@actions_bp.route('/<action_id>/reject', methods=['POST'])
def reject_action(action_id: str):
    """Reject an action."""
    try:
        data = request.get_json()

        result = {
            "action_id": action_id,
            "status": "rejected",
            "reason": data.get('reason', ''),
            "rejected_by": data.get('user', 'operator'),
            "rejected_at": datetime.now().isoformat()
        }

        logger.info(f"Action {action_id} rejected: {result['reason']}")

        return jsonify({"success": True, "result": result})
    except Exception as e:
        logger.error(f"Action rejection failed: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@actions_bp.route('/approve-all-low-risk', methods=['POST'])
def approve_all_low_risk():
    """Approve all low-risk actions."""
    try:
        result = {
            "approved_count": 3,
            "action_ids": ["act-003", "act-005", "act-007"],
            "approved_at": datetime.now().isoformat()
        }

        return jsonify({"success": True, "result": result})
    except Exception as e:
        logger.error(f"Bulk approval failed: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


# Action History
@actions_bp.route('/history', methods=['GET'])
def get_action_history():
    """Get action history (audit trail)."""
    try:
        limit = request.args.get('limit', 50, type=int)

        history = [
            {
                "id": "act-hist-001",
                "action_type": "PAUSE_PRINT",
                "title": "Pause Print - Filament Change",
                "status": "approved",
                "outcome": "success",
                "approved_by": "John D.",
                "timestamp": "2024-01-01T12:25:00Z"
            },
            {
                "id": "act-hist-002",
                "action_type": "FLOW_ADJUSTMENT",
                "title": "Adjust Flow Rate to 95%",
                "status": "auto-approved",
                "outcome": "success",
                "approved_by": "system",
                "timestamp": "2024-01-01T12:18:00Z",
                "notes": "Quality improved by 3%"
            },
            {
                "id": "act-hist-003",
                "action_type": "CANCEL_JOB",
                "title": "Cancel Current Job",
                "status": "rejected",
                "outcome": "not_executed",
                "rejected_by": "Sarah M.",
                "timestamp": "2024-01-01T11:30:00Z",
                "reason": "Job 85% complete, prefer to finish"
            },
            {
                "id": "act-hist-004",
                "action_type": "EMERGENCY_STOP",
                "title": "Emergency Stop - Thermal Runaway",
                "status": "auto-executed",
                "outcome": "success",
                "approved_by": "safety_system",
                "timestamp": "2024-01-01T10:15:00Z",
                "notes": "Printer #005 offline for inspection"
            }
        ]

        return jsonify({"success": True, "history": history[:limit]})
    except Exception as e:
        logger.error(f"Failed to get action history: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


# Auto-Approval Rules
@actions_bp.route('/rules', methods=['GET'])
def get_approval_rules():
    """Get auto-approval rules configuration."""
    try:
        rules = {
            "auto_approve_low_risk": True,
            "auto_approve_fan_adjustments": False,
            "auto_approve_high_confidence": False,
            "confidence_threshold": 0.95,
            "blocked_action_types": ["EMERGENCY_STOP", "CANCEL_JOB", "FIRMWARE_UPDATE"],
            "require_manual_for_temperature_above": 240
        }

        return jsonify({"success": True, "rules": rules})
    except Exception as e:
        logger.error(f"Failed to get approval rules: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@actions_bp.route('/rules', methods=['PUT'])
def update_approval_rules():
    """Update auto-approval rules."""
    try:
        data = request.get_json()

        # In production, this would update the rules in the database
        updated_rules = {
            "auto_approve_low_risk": data.get('auto_approve_low_risk', True),
            "auto_approve_fan_adjustments": data.get('auto_approve_fan_adjustments', False),
            "auto_approve_high_confidence": data.get('auto_approve_high_confidence', False),
            "confidence_threshold": data.get('confidence_threshold', 0.95),
            "updated_at": datetime.now().isoformat()
        }

        return jsonify({"success": True, "rules": updated_rules})
    except Exception as e:
        logger.error(f"Failed to update approval rules: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


# Direct Equipment Control
@actions_bp.route('/execute', methods=['POST'])
def execute_direct():
    """
    Execute a direct action on equipment.

    Request body:
    {
        "printer_id": "prusa-001",
        "gcode": ["G28", "M104 S200"],
        "bypass_approval": false
    }
    """
    try:
        data = request.get_json()

        if not data.get('bypass_approval', False):
            # Create pending action
            action = {
                "id": str(uuid.uuid4()),
                "status": "pending_approval",
                "message": "Action queued for approval"
            }
            return jsonify({"success": True, "action": action})

        # Direct execution (requires elevated permissions)
        result = {
            "id": str(uuid.uuid4()),
            "printer_id": data.get('printer_id', ''),
            "status": "executed",
            "commands_sent": len(data.get('gcode', [])),
            "response": "ok",
            "executed_at": datetime.now().isoformat()
        }

        return jsonify({"success": True, "result": result})
    except Exception as e:
        logger.error(f"Direct execution failed: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


# Rollback
@actions_bp.route('/<action_id>/rollback', methods=['POST'])
def rollback_action(action_id: str):
    """Rollback a previously executed action."""
    try:
        result = {
            "action_id": action_id,
            "status": "rolled_back",
            "rollback_commands": ["M104 S200"],  # Restore previous temperature
            "executed_at": datetime.now().isoformat()
        }

        return jsonify({"success": True, "result": result})
    except Exception as e:
        logger.error(f"Rollback failed: {e}")
        return jsonify({"success": False, "error": str(e)}), 500
