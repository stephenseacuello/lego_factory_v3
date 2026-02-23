"""
VR Training API Routes
======================

REST API endpoints for Virtual Reality training system.

Endpoints:
- Training scenarios management
- Training sessions lifecycle
- Scoring and leaderboards
- VR device integration

Author: LegoMCP Team
Version: 2.0.0
"""

from flask import Blueprint, request, jsonify
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
import logging

logger = logging.getLogger(__name__)

# Create Blueprint
vr_training_bp = Blueprint('vr_training', __name__, url_prefix='/vr/training')


# ================== Training Scenarios ==================

@vr_training_bp.route('/scenarios', methods=['GET'])
def list_scenarios():
    """
    List available training scenarios.

    Query Parameters:
        category: Filter by category (equipment_operation, safety_procedures, etc.)
        difficulty: Filter by difficulty level
        equipment: Filter by required equipment

    Returns:
        List of training scenarios
    """
    try:
        from services.hmi import get_vr_training_service, TrainingCategory, DifficultyLevel

        service = get_vr_training_service()

        # Get filters
        category_filter = request.args.get('category')
        difficulty_filter = request.args.get('difficulty')
        equipment_filter = request.args.get('equipment')

        scenarios = service.get_all_scenarios()

        # Apply filters
        if category_filter:
            try:
                category = TrainingCategory(category_filter)
                scenarios = [s for s in scenarios if s.category == category]
            except ValueError:
                pass

        if difficulty_filter:
            try:
                difficulty = DifficultyLevel(difficulty_filter)
                scenarios = [s for s in scenarios if s.difficulty == difficulty]
            except ValueError:
                pass

        if equipment_filter:
            scenarios = [s for s in scenarios if equipment_filter in s.equipment_ids]

        return jsonify({
            'success': True,
            'count': len(scenarios),
            'data': [s.to_dict() for s in scenarios]
        })

    except Exception as e:
        logger.error(f"Error listing scenarios: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@vr_training_bp.route('/scenarios', methods=['POST'])
def create_scenario():
    """
    Create a new training scenario.

    Body:
        name: Scenario name
        description: Scenario description
        category: Training category
        difficulty: Difficulty level
        steps: List of training steps
        equipment_ids: Required equipment OME IDs
        max_score: Maximum achievable score
        passing_score: Minimum passing score

    Returns:
        Created scenario
    """
    try:
        from services.hmi import (
            get_vr_training_service,
            TrainingScenario,
            TrainingCategory,
            DifficultyLevel,
            TrainingStep
        )

        data = request.get_json()

        if not data or 'name' not in data:
            return jsonify({
                'success': False,
                'error': 'Name required'
            }), 400

        # Parse steps
        steps = []
        for step_data in data.get('steps', []):
            step = TrainingStep(
                step_id=step_data.get('step_id', f"step-{len(steps)+1}"),
                title=step_data.get('title', f"Step {len(steps)+1}"),
                instructions=step_data.get('instructions', ''),
                success_criteria=step_data.get('success_criteria', {}),
                hints=step_data.get('hints', []),
                points=step_data.get('points', 10),
                time_limit_seconds=step_data.get('time_limit_seconds'),
                required_interactions=step_data.get('required_interactions', [])
            )
            steps.append(step)

        scenario = TrainingScenario(
            scenario_id=data.get('scenario_id'),
            name=data['name'],
            description=data.get('description', ''),
            category=TrainingCategory(data.get('category', 'equipment_operation')),
            difficulty=DifficultyLevel(data.get('difficulty', 'intermediate')),
            steps=steps,
            equipment_ids=data.get('equipment_ids', []),
            estimated_duration_minutes=data.get('estimated_duration_minutes', 30),
            max_score=data.get('max_score', 100),
            passing_score=data.get('passing_score', 70),
            certification_valid_days=data.get('certification_valid_days')
        )

        service = get_vr_training_service()
        created = service.create_scenario(scenario)

        return jsonify({
            'success': True,
            'data': created.to_dict()
        }), 201

    except Exception as e:
        logger.error(f"Error creating scenario: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 400


@vr_training_bp.route('/scenarios/<scenario_id>', methods=['GET'])
def get_scenario(scenario_id: str):
    """
    Get scenario details.

    Path Parameters:
        scenario_id: Scenario identifier

    Returns:
        Scenario details with steps
    """
    try:
        from services.hmi import get_vr_training_service

        service = get_vr_training_service()
        scenario = service.get_scenario(scenario_id)

        if not scenario:
            return jsonify({
                'success': False,
                'error': 'Scenario not found'
            }), 404

        return jsonify({
            'success': True,
            'data': scenario.to_dict()
        })

    except Exception as e:
        logger.error(f"Error getting scenario: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@vr_training_bp.route('/scenarios/<scenario_id>', methods=['PUT'])
def update_scenario(scenario_id: str):
    """
    Update an existing scenario.

    Path Parameters:
        scenario_id: Scenario identifier

    Body:
        Any scenario properties to update

    Returns:
        Updated scenario
    """
    try:
        from services.hmi import get_vr_training_service

        data = request.get_json()

        service = get_vr_training_service()
        updated = service.update_scenario(scenario_id, data)

        if not updated:
            return jsonify({
                'success': False,
                'error': 'Scenario not found'
            }), 404

        return jsonify({
            'success': True,
            'data': updated.to_dict()
        })

    except Exception as e:
        logger.error(f"Error updating scenario: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 400


@vr_training_bp.route('/scenarios/<scenario_id>', methods=['DELETE'])
def delete_scenario(scenario_id: str):
    """
    Delete a scenario.

    Path Parameters:
        scenario_id: Scenario identifier

    Returns:
        Success status
    """
    try:
        from services.hmi import get_vr_training_service

        service = get_vr_training_service()
        service.delete_scenario(scenario_id)

        return jsonify({
            'success': True,
            'message': f'Scenario {scenario_id} deleted'
        })

    except Exception as e:
        logger.error(f"Error deleting scenario: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# ================== Training Sessions ==================

@vr_training_bp.route('/sessions', methods=['POST'])
def start_session():
    """
    Start a new training session.

    Body:
        scenario_id: Scenario to run
        trainee_id: Trainee identifier
        device_type: VR device type (quest, vive, hololens, desktop)

    Returns:
        Session details with connection info
    """
    try:
        from services.hmi import get_vr_training_service

        data = request.get_json()

        if not data or 'scenario_id' not in data or 'trainee_id' not in data:
            return jsonify({
                'success': False,
                'error': 'scenario_id and trainee_id required'
            }), 400

        service = get_vr_training_service()
        session = service.start_session(
            scenario_id=data['scenario_id'],
            trainee_id=data['trainee_id'],
            device_type=data.get('device_type', 'desktop')
        )

        return jsonify({
            'success': True,
            'data': session.to_dict()
        }), 201

    except Exception as e:
        logger.error(f"Error starting session: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 400


@vr_training_bp.route('/sessions/<session_id>', methods=['GET'])
def get_session(session_id: str):
    """
    Get session status and progress.

    Path Parameters:
        session_id: Session identifier

    Returns:
        Session details with current progress
    """
    try:
        from services.hmi import get_vr_training_service

        service = get_vr_training_service()
        session = service.get_session(session_id)

        if not session:
            return jsonify({
                'success': False,
                'error': 'Session not found'
            }), 404

        return jsonify({
            'success': True,
            'data': session.to_dict()
        })

    except Exception as e:
        logger.error(f"Error getting session: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@vr_training_bp.route('/sessions/<session_id>/step', methods=['POST'])
def complete_step(session_id: str):
    """
    Complete a training step.

    Path Parameters:
        session_id: Session identifier

    Body:
        step_id: Step that was completed
        score: Score achieved (optional)
        time_seconds: Time taken (optional)
        interactions: List of interactions performed

    Returns:
        Updated session with next step
    """
    try:
        from services.hmi import get_vr_training_service

        data = request.get_json()

        if not data or 'step_id' not in data:
            return jsonify({
                'success': False,
                'error': 'step_id required'
            }), 400

        service = get_vr_training_service()
        session = service.complete_step(
            session_id=session_id,
            step_id=data['step_id'],
            score=data.get('score'),
            time_seconds=data.get('time_seconds'),
            interactions=data.get('interactions', [])
        )

        return jsonify({
            'success': True,
            'data': session.to_dict()
        })

    except Exception as e:
        logger.error(f"Error completing step: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 400


@vr_training_bp.route('/sessions/<session_id>/interaction', methods=['POST'])
def record_interaction(session_id: str):
    """
    Record a user interaction during training.

    Path Parameters:
        session_id: Session identifier

    Body:
        interaction_type: Type of interaction
        target_object: Object interacted with
        position: Interaction position (optional)
        data: Additional interaction data

    Returns:
        Success status
    """
    try:
        from services.hmi import get_vr_training_service

        data = request.get_json()

        service = get_vr_training_service()
        service.record_interaction(
            session_id=session_id,
            interaction_type=data.get('interaction_type', 'generic'),
            target_object=data.get('target_object'),
            position=data.get('position'),
            data=data.get('data', {})
        )

        return jsonify({
            'success': True,
            'message': 'Interaction recorded'
        })

    except Exception as e:
        logger.error(f"Error recording interaction: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 400


@vr_training_bp.route('/sessions/<session_id>/complete', methods=['POST'])
def complete_session(session_id: str):
    """
    Complete a training session.

    Path Parameters:
        session_id: Session identifier

    Body:
        feedback: User feedback (optional)

    Returns:
        Training result with score and certificate
    """
    try:
        from services.hmi import get_vr_training_service

        data = request.get_json() or {}

        service = get_vr_training_service()
        result = service.complete_session(
            session_id=session_id,
            feedback=data.get('feedback')
        )

        return jsonify({
            'success': True,
            'data': result.to_dict()
        })

    except Exception as e:
        logger.error(f"Error completing session: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 400


@vr_training_bp.route('/sessions/<session_id>/pause', methods=['POST'])
def pause_session(session_id: str):
    """
    Pause a training session.

    Path Parameters:
        session_id: Session identifier

    Returns:
        Updated session
    """
    try:
        from services.hmi import get_vr_training_service

        service = get_vr_training_service()
        session = service.pause_session(session_id)

        return jsonify({
            'success': True,
            'data': session.to_dict()
        })

    except Exception as e:
        logger.error(f"Error pausing session: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@vr_training_bp.route('/sessions/<session_id>/resume', methods=['POST'])
def resume_session(session_id: str):
    """
    Resume a paused training session.

    Path Parameters:
        session_id: Session identifier

    Returns:
        Updated session
    """
    try:
        from services.hmi import get_vr_training_service

        service = get_vr_training_service()
        session = service.resume_session(session_id)

        return jsonify({
            'success': True,
            'data': session.to_dict()
        })

    except Exception as e:
        logger.error(f"Error resuming session: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@vr_training_bp.route('/sessions/<session_id>/abandon', methods=['POST'])
def abandon_session(session_id: str):
    """
    Abandon a training session.

    Path Parameters:
        session_id: Session identifier

    Body:
        reason: Reason for abandonment (optional)

    Returns:
        Success status
    """
    try:
        from services.hmi import get_vr_training_service

        data = request.get_json() or {}

        service = get_vr_training_service()
        service.abandon_session(
            session_id=session_id,
            reason=data.get('reason')
        )

        return jsonify({
            'success': True,
            'message': 'Session abandoned'
        })

    except Exception as e:
        logger.error(f"Error abandoning session: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# ================== Results & Leaderboard ==================

@vr_training_bp.route('/results', methods=['GET'])
def get_results():
    """
    Get training results.

    Query Parameters:
        trainee_id: Filter by trainee
        scenario_id: Filter by scenario
        passed: Filter by pass/fail status
        since: Filter by date (ISO format)

    Returns:
        List of training results
    """
    try:
        from services.hmi import get_vr_training_service

        service = get_vr_training_service()

        trainee_id = request.args.get('trainee_id')
        scenario_id = request.args.get('scenario_id')
        passed_filter = request.args.get('passed')
        since = request.args.get('since')

        results = service.get_results(
            trainee_id=trainee_id,
            scenario_id=scenario_id
        )

        # Apply additional filters
        if passed_filter is not None:
            passed = passed_filter.lower() == 'true'
            results = [r for r in results if r.passed == passed]

        if since:
            since_dt = datetime.fromisoformat(since.replace('Z', '+00:00'))
            results = [r for r in results if r.completed_at >= since_dt]

        return jsonify({
            'success': True,
            'count': len(results),
            'data': [r.to_dict() for r in results]
        })

    except Exception as e:
        logger.error(f"Error getting results: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@vr_training_bp.route('/results/<result_id>', methods=['GET'])
def get_result(result_id: str):
    """
    Get detailed training result.

    Path Parameters:
        result_id: Result identifier

    Returns:
        Result with detailed step breakdown
    """
    try:
        from services.hmi import get_vr_training_service

        service = get_vr_training_service()
        result = service.get_result(result_id)

        if not result:
            return jsonify({
                'success': False,
                'error': 'Result not found'
            }), 404

        return jsonify({
            'success': True,
            'data': result.to_dict()
        })

    except Exception as e:
        logger.error(f"Error getting result: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@vr_training_bp.route('/leaderboard', methods=['GET'])
def get_leaderboard():
    """
    Get training leaderboard.

    Query Parameters:
        scenario_id: Filter by scenario
        period: Time period (7d, 30d, 90d, all)
        limit: Number of entries (default: 10)

    Returns:
        Leaderboard with top performers
    """
    try:
        from services.hmi import get_vr_training_service

        service = get_vr_training_service()

        scenario_id = request.args.get('scenario_id')
        period = request.args.get('period', '30d')
        limit = int(request.args.get('limit', 10))

        # Calculate date range
        if period == '7d':
            since = datetime.utcnow() - timedelta(days=7)
        elif period == '30d':
            since = datetime.utcnow() - timedelta(days=30)
        elif period == '90d':
            since = datetime.utcnow() - timedelta(days=90)
        else:
            since = None

        leaderboard = service.get_leaderboard(
            scenario_id=scenario_id,
            since=since,
            limit=limit
        )

        return jsonify({
            'success': True,
            'data': {
                'period': period,
                'scenario_id': scenario_id,
                'entries': leaderboard,
                'generated_at': datetime.utcnow().isoformat()
            }
        })

    except Exception as e:
        logger.error(f"Error getting leaderboard: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# ================== Trainee Management ==================

@vr_training_bp.route('/trainees/<trainee_id>/progress', methods=['GET'])
def get_trainee_progress(trainee_id: str):
    """
    Get trainee's overall progress.

    Path Parameters:
        trainee_id: Trainee identifier

    Returns:
        Progress summary across all scenarios
    """
    try:
        from services.hmi import get_vr_training_service

        service = get_vr_training_service()
        progress = service.get_trainee_progress(trainee_id)

        return jsonify({
            'success': True,
            'data': progress
        })

    except Exception as e:
        logger.error(f"Error getting trainee progress: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@vr_training_bp.route('/trainees/<trainee_id>/certifications', methods=['GET'])
def get_trainee_certifications(trainee_id: str):
    """
    Get trainee's certifications.

    Path Parameters:
        trainee_id: Trainee identifier

    Returns:
        List of active and expired certifications
    """
    try:
        from services.hmi import get_vr_training_service

        service = get_vr_training_service()
        certifications = service.get_trainee_certifications(trainee_id)

        return jsonify({
            'success': True,
            'data': certifications
        })

    except Exception as e:
        logger.error(f"Error getting certifications: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# ================== Analytics ==================

@vr_training_bp.route('/analytics/overview', methods=['GET'])
def get_analytics_overview():
    """
    Get training analytics overview.

    Query Parameters:
        period: Time period (7d, 30d, 90d)

    Returns:
        Training statistics and trends
    """
    try:
        from services.hmi import get_vr_training_service

        service = get_vr_training_service()

        period = request.args.get('period', '30d')

        # Calculate date range
        if period == '7d':
            since = datetime.utcnow() - timedelta(days=7)
        elif period == '30d':
            since = datetime.utcnow() - timedelta(days=30)
        else:
            since = datetime.utcnow() - timedelta(days=90)

        analytics = service.get_analytics(since=since)

        return jsonify({
            'success': True,
            'data': {
                'period': period,
                **analytics
            }
        })

    except Exception as e:
        logger.error(f"Error getting analytics: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@vr_training_bp.route('/analytics/scenario/<scenario_id>', methods=['GET'])
def get_scenario_analytics(scenario_id: str):
    """
    Get analytics for a specific scenario.

    Path Parameters:
        scenario_id: Scenario identifier

    Returns:
        Scenario-specific analytics
    """
    try:
        from services.hmi import get_vr_training_service

        service = get_vr_training_service()
        analytics = service.get_scenario_analytics(scenario_id)

        return jsonify({
            'success': True,
            'data': analytics
        })

    except Exception as e:
        logger.error(f"Error getting scenario analytics: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# ================== Device Management ==================

@vr_training_bp.route('/devices', methods=['GET'])
def list_devices():
    """
    List connected VR devices.

    Returns:
        List of registered VR devices
    """
    try:
        from services.hmi import get_vr_training_service

        service = get_vr_training_service()
        devices = service.get_connected_devices()

        return jsonify({
            'success': True,
            'count': len(devices),
            'data': devices
        })

    except Exception as e:
        logger.error(f"Error listing devices: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@vr_training_bp.route('/devices/<device_id>/calibrate', methods=['POST'])
def calibrate_device(device_id: str):
    """
    Trigger device calibration.

    Path Parameters:
        device_id: Device identifier

    Returns:
        Calibration status
    """
    try:
        from services.hmi import get_vr_training_service

        service = get_vr_training_service()
        result = service.calibrate_device(device_id)

        return jsonify({
            'success': True,
            'data': result
        })

    except Exception as e:
        logger.error(f"Error calibrating device: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
