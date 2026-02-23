"""
CAM Copilot Routes - AI-Assisted CAM Parameter API

LEGO MCP World-Class Manufacturing System v6.0
Phase 18: AI CAM Copilot REST API

Provides REST endpoints for:
- CAM parameter recommendations
- Execution with approval workflow
- Quality feedback submission
- Mode management
"""

import logging
from datetime import datetime
from flask import Blueprint, request, jsonify, current_app
from typing import Optional
import asyncio

from services.ai.cam_assistant import (
    CAMAssistant,
    CAMAssistantConfig,
    CAMMode,
    MaterialType,
    OperationType,
    create_cam_assistant,
)

logger = logging.getLogger(__name__)

cam_copilot_bp = Blueprint('cam_copilot', __name__, url_prefix='/cam')

# Global assistant instance (lazy initialization)
_cam_assistant: Optional[CAMAssistant] = None


def get_cam_assistant() -> CAMAssistant:
    """Get or create the CAM assistant instance."""
    global _cam_assistant
    if _cam_assistant is None:
        _cam_assistant = create_cam_assistant(mode=CAMMode.COPILOT)
    return _cam_assistant


def run_async(coro):
    """Run async coroutine in sync context."""
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop.run_until_complete(coro)


@cam_copilot_bp.route('/recommend', methods=['POST'])
def recommend_cam_params():
    """
    Get AI-recommended CAM parameters.

    Request body:
    {
        "brick_type": "2x4",
        "dimensions": {"x": 32, "y": 16, "z": 9.6},
        "material": "aluminum_6061",
        "machine_id": "bantam-desktop-cnc",
        "operation": "pocket",
        "mode": "copilot",
        "quality_history": [...]  // Optional
    }

    Returns:
        Complete CAM recommendation with parameters, rationale, and alternatives.
    """
    try:
        data = request.get_json()

        if not data:
            return jsonify({
                'success': False,
                'error': 'Request body required'
            }), 400

        # Extract parameters
        brick_type = data.get('brick_type', '2x4')
        dimensions = data.get('dimensions', {'x': 32, 'y': 16, 'z': 9.6})
        material_str = data.get('material', 'aluminum_6061')
        machine_id = data.get('machine_id', 'bantam-desktop-cnc')
        operation_str = data.get('operation', 'pocket')
        mode_str = data.get('mode', 'copilot')
        quality_history = data.get('quality_history', [])
        custom_constraints = data.get('constraints')

        # Parse enums
        try:
            material = MaterialType(material_str)
        except ValueError:
            return jsonify({
                'success': False,
                'error': f'Invalid material: {material_str}',
                'valid_materials': [m.value for m in MaterialType]
            }), 400

        try:
            operation = OperationType(operation_str)
        except ValueError:
            return jsonify({
                'success': False,
                'error': f'Invalid operation: {operation_str}',
                'valid_operations': [o.value for o in OperationType]
            }), 400

        try:
            mode = CAMMode(mode_str)
        except ValueError:
            mode = CAMMode.COPILOT

        # Get recommendation
        assistant = get_cam_assistant()
        recommendation = run_async(
            assistant.recommend_cam_parameters(
                brick_type=brick_type,
                dimensions=dimensions,
                material=material,
                machine_id=machine_id,
                operation_type=operation,
                mode=mode,
                quality_history=quality_history,
                custom_constraints=custom_constraints,
            )
        )

        return jsonify({
            'success': True,
            'recommendation': recommendation.to_dict(),
            'mode': mode.value,
            'requires_approval': mode == CAMMode.COPILOT,
        })

    except Exception as e:
        logger.exception("Error generating CAM recommendation")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@cam_copilot_bp.route('/execute', methods=['POST'])
def execute_cam():
    """
    Execute approved CAM recommendation.

    Request body:
    {
        "recommendation_id": "cam-abc123",
        "user_approved": true,  // Required for COPILOT mode
        "recommendation": {...}  // Full recommendation object
    }

    Returns:
        Execution result with G-code file path.
    """
    try:
        data = request.get_json()

        if not data:
            return jsonify({
                'success': False,
                'error': 'Request body required'
            }), 400

        recommendation_data = data.get('recommendation')
        user_approved = data.get('user_approved', False)

        if not recommendation_data:
            return jsonify({
                'success': False,
                'error': 'Recommendation data required'
            }), 400

        # Reconstruct recommendation object
        from services.ai.cam_assistant import (
            CAMRecommendation,
            ToolRecommendation,
            FeedSpeedRecommendation,
            ToolpathStrategy,
        )

        # Build tool recommendation
        tool_data = recommendation_data.get('tool', {})
        tool = ToolRecommendation(
            tool_type=tool_data.get('type', 'Flat End Mill'),
            tool_diameter_mm=tool_data.get('diameter_mm', 3.175),
            flute_count=tool_data.get('flutes', 2),
            material=tool_data.get('material', 'Carbide'),
            coating=tool_data.get('coating'),
            rationale=tool_data.get('rationale', ''),
        )

        # Build feeds/speeds
        fs_data = recommendation_data.get('feeds_speeds', {})
        feeds_speeds = FeedSpeedRecommendation(
            spindle_rpm=fs_data.get('spindle_rpm', 15000),
            feed_rate_mm_min=fs_data.get('feed_rate_mm_min', 500),
            plunge_rate_mm_min=fs_data.get('plunge_rate_mm_min', 150),
            depth_of_cut_mm=fs_data.get('depth_of_cut_mm', 1.0),
            stepover_percent=fs_data.get('stepover_percent', 40),
            surface_speed_m_min=fs_data.get('surface_speed_m_min', 150),
            chip_load_mm=fs_data.get('chip_load_mm', 0.017),
            mrr_cm3_min=fs_data.get('mrr_cm3_min', 0.5),
            rationale=fs_data.get('rationale', ''),
        )

        # Build toolpath strategy
        tp_data = recommendation_data.get('toolpath', {})
        toolpath = ToolpathStrategy(
            strategy_type=tp_data.get('strategy', 'adaptive'),
            direction=tp_data.get('direction', 'climb'),
            lead_in_type=tp_data.get('lead_in', 'arc'),
            lead_out_type=tp_data.get('lead_out', 'arc'),
            smoothing_tolerance_mm=0.01,
            high_speed_machining=tp_data.get('hsm_enabled', False),
        )

        # Build full recommendation
        component = recommendation_data.get('component', {})
        recommendation = CAMRecommendation(
            recommendation_id=recommendation_data.get('recommendation_id', 'unknown'),
            timestamp=datetime.utcnow(),
            mode=CAMMode(recommendation_data.get('mode', 'copilot')),
            component_name=component.get('name', 'LEGO-2x4-Brick'),
            brick_type=component.get('brick_type', '2x4'),
            dimensions=component.get('dimensions', {'x': 32, 'y': 16, 'z': 9.6}),
            material=MaterialType(component.get('material', 'aluminum_6061')),
            machine_id=recommendation_data.get('machine_id', 'bantam-desktop-cnc'),
            tool=tool,
            feeds_speeds=feeds_speeds,
            toolpath=toolpath,
            operations=recommendation_data.get('operations', []),
            confidence=recommendation_data.get('confidence', 0.85),
            rationale=recommendation_data.get('rationale', ''),
            warnings=recommendation_data.get('warnings', []),
        )

        # Execute based on mode
        assistant = get_cam_assistant()

        if recommendation.mode == CAMMode.AUTONOMOUS:
            result = run_async(assistant.execute_autonomous(recommendation))
        else:
            result = run_async(
                assistant.execute_with_approval(recommendation, user_approved)
            )

        return jsonify({
            'success': result.success,
            'result': result.to_dict(),
        })

    except Exception as e:
        logger.exception("Error executing CAM")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@cam_copilot_bp.route('/feedback', methods=['POST'])
def cam_feedback():
    """
    Submit quality feedback for CAM learning.

    Request body:
    {
        "recommendation_id": "cam-abc123",
        "defect_type": "rough_surface",
        "severity": "minor",
        "notes": "Surface finish slightly below spec"
    }

    Returns:
        Acknowledgment of feedback recording.
    """
    try:
        data = request.get_json()

        if not data:
            return jsonify({
                'success': False,
                'error': 'Request body required'
            }), 400

        recommendation_id = data.get('recommendation_id')
        defect_type = data.get('defect_type')
        severity = data.get('severity', 'minor')
        notes = data.get('notes')

        if not recommendation_id or not defect_type:
            return jsonify({
                'success': False,
                'error': 'recommendation_id and defect_type required'
            }), 400

        # Record feedback
        assistant = get_cam_assistant()
        assistant.record_quality_feedback(
            recommendation_id=recommendation_id,
            defect_type=defect_type,
            severity=severity,
            notes=notes,
        )

        return jsonify({
            'success': True,
            'message': 'Feedback recorded for learning',
            'defect_type': defect_type,
            'will_adjust': True,
        })

    except Exception as e:
        logger.exception("Error recording CAM feedback")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@cam_copilot_bp.route('/modes', methods=['GET'])
def get_cam_modes():
    """
    Get available CAM operating modes with descriptions.

    Returns:
        List of available modes with detailed descriptions.
    """
    try:
        assistant = get_cam_assistant()

        modes = []
        for mode in CAMMode:
            description = assistant.get_mode_description(mode)
            modes.append({
                'mode': mode.value,
                **description,
            })

        return jsonify({
            'success': True,
            'modes': modes,
            'current_mode': assistant.config.default_mode.value,
        })

    except Exception as e:
        logger.exception("Error getting CAM modes")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@cam_copilot_bp.route('/modes/<mode>', methods=['PUT'])
def set_cam_mode(mode: str):
    """
    Set the default CAM operating mode.

    Returns:
        Updated mode configuration.
    """
    try:
        try:
            new_mode = CAMMode(mode)
        except ValueError:
            return jsonify({
                'success': False,
                'error': f'Invalid mode: {mode}',
                'valid_modes': [m.value for m in CAMMode]
            }), 400

        assistant = get_cam_assistant()
        assistant.config.default_mode = new_mode

        return jsonify({
            'success': True,
            'mode': new_mode.value,
            'description': assistant.get_mode_description(new_mode),
        })

    except Exception as e:
        logger.exception("Error setting CAM mode")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@cam_copilot_bp.route('/materials', methods=['GET'])
def get_materials():
    """
    Get supported materials with cutting properties.

    Returns:
        List of materials with recommended speed/feed ranges.
    """
    try:
        from services.ai.cam_assistant import MaterialDatabase

        materials = []
        for material_type in MaterialType:
            props = MaterialDatabase.MATERIALS.get(material_type, {})
            if props:
                materials.append({
                    'id': material_type.value,
                    'name': props.get('name', material_type.value),
                    'surface_speed_range': props.get('surface_speed_range', [0, 0]),
                    'chip_load_range': props.get('chip_load_range', [0, 0]),
                    'coolant': props.get('coolant', 'none'),
                    'hardness_bhn': props.get('hardness_bhn', 0),
                })

        return jsonify({
            'success': True,
            'materials': materials,
        })

    except Exception as e:
        logger.exception("Error getting materials")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@cam_copilot_bp.route('/machines', methods=['GET'])
def get_machines():
    """
    Get supported machine profiles.

    Returns:
        List of machines with capabilities.
    """
    try:
        from services.ai.cam_assistant import MachineProfiles

        machines = []
        for machine_id, profile in MachineProfiles.PROFILES.items():
            machines.append({
                'id': machine_id,
                'name': profile.get('name', machine_id),
                'type': profile.get('type', 'unknown'),
                'max_rpm': profile.get('max_rpm', 0),
                'max_feed_rate': profile.get('max_feed_rate', 0),
                'work_envelope': profile.get('work_envelope', {}),
                'precision_mm': profile.get('precision_mm', 0.1),
            })

        return jsonify({
            'success': True,
            'machines': machines,
        })

    except Exception as e:
        logger.exception("Error getting machines")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@cam_copilot_bp.route('/defect-mappings', methods=['GET'])
def get_defect_mappings():
    """
    Get defect-to-CAM parameter mappings.

    Returns:
        Map of defect types to parameter adjustments.
    """
    try:
        from services.ai.cam_assistant import DefectCAMMapping

        mappings = []
        for defect_type, mapping in DefectCAMMapping.MAPPINGS.items():
            mappings.append({
                'defect_type': defect_type,
                'description': mapping.get('description', ''),
                'adjustments': mapping.get('adjustments', {}),
                'root_cause': mapping.get('root_cause', ''),
            })

        return jsonify({
            'success': True,
            'mappings': mappings,
        })

    except Exception as e:
        logger.exception("Error getting defect mappings")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@cam_copilot_bp.route('/health', methods=['GET'])
def health_check():
    """Health check for CAM copilot service."""
    try:
        assistant = get_cam_assistant()
        return jsonify({
            'status': 'healthy',
            'service': 'cam_copilot',
            'mode': assistant.config.default_mode.value,
            'anthropic_available': assistant.client is not None,
        })
    except Exception as e:
        return jsonify({
            'status': 'unhealthy',
            'error': str(e)
        }), 500


# ============================================
# CAM Feedback Loop Routes
# Connects defects back to CAM optimization
# ============================================

@cam_copilot_bp.route('/feedback-loop/record', methods=['POST'])
def record_defect():
    """
    Record a defect for feedback loop analysis.

    Request body:
    {
        "work_center_id": "bantam-desktop-cnc",
        "part_number": "LEGO-2x4-Brick",
        "defect_type": "rough_surface",
        "severity": "minor",
        "measured_value": 0.85,
        "target_value": 0.80,
        "cam_recommendation_id": "cam-abc123",
        "notes": "Slightly rough on top surface"
    }

    Returns:
        Recorded defect details.
    """
    try:
        from services.ai.cam_feedback_loop import get_feedback_loop

        data = request.get_json()

        if not data:
            return jsonify({
                'success': False,
                'error': 'Request body required'
            }), 400

        work_center_id = data.get('work_center_id')
        part_number = data.get('part_number')
        defect_type = data.get('defect_type')

        if not all([work_center_id, part_number, defect_type]):
            return jsonify({
                'success': False,
                'error': 'work_center_id, part_number, and defect_type are required'
            }), 400

        feedback_loop = get_feedback_loop()
        defect = feedback_loop.record_defect(
            work_center_id=work_center_id,
            part_number=part_number,
            defect_type=defect_type,
            severity=data.get('severity', 'minor'),
            measured_value=data.get('measured_value'),
            target_value=data.get('target_value'),
            cam_recommendation_id=data.get('cam_recommendation_id'),
            notes=data.get('notes', ''),
        )

        return jsonify({
            'success': True,
            'defect': defect.to_dict(),
        })

    except Exception as e:
        logger.exception("Error recording defect")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@cam_copilot_bp.route('/feedback-loop/analyze', methods=['POST'])
def analyze_for_cam():
    """
    Analyze recent defects and recommend CAM parameter adjustments.

    Request body:
    {
        "work_center_id": "bantam-desktop-cnc",  // Optional
        "period_hours": 24,
        "current_params": {
            "spindle_rpm": 15000,
            "feed_rate_mm_min": 500,
            ...
        }
    }

    Returns:
        Analysis with recommended CAM corrections.
    """
    try:
        from services.ai.cam_feedback_loop import get_feedback_loop

        data = request.get_json() or {}

        work_center_id = data.get('work_center_id')
        period_hours = data.get('period_hours', 24)
        current_params = data.get('current_params')

        feedback_loop = get_feedback_loop()
        analysis = feedback_loop.analyze_defects_for_cam(
            work_center_id=work_center_id,
            period_hours=period_hours,
            current_params=current_params,
        )

        return jsonify({
            'success': True,
            'analysis': analysis.to_dict(),
        })

    except Exception as e:
        logger.exception("Error analyzing defects for CAM")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@cam_copilot_bp.route('/feedback-loop/statistics', methods=['GET'])
def get_defect_statistics():
    """
    Get defect statistics for a period.

    Query params:
        work_center_id: Filter by work center (optional)
        period_hours: Lookback period in hours (default: 168 = 1 week)

    Returns:
        Statistics on defects by type, category, severity, work center.
    """
    try:
        from services.ai.cam_feedback_loop import get_feedback_loop

        work_center_id = request.args.get('work_center_id')
        period_hours = int(request.args.get('period_hours', 168))

        feedback_loop = get_feedback_loop()
        stats = feedback_loop.get_defect_statistics(
            work_center_id=work_center_id,
            period_hours=period_hours,
        )

        return jsonify({
            'success': True,
            'statistics': stats,
        })

    except Exception as e:
        logger.exception("Error getting defect statistics")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@cam_copilot_bp.route('/feedback-loop/defect-types', methods=['GET'])
def get_defect_types():
    """
    Get all supported defect types with their categories.

    Returns:
        Defect types grouped by category with descriptions.
    """
    try:
        from services.ai.cam_feedback_loop import DefectCAMMapping

        defect_types = []
        for defect_type, mapping in DefectCAMMapping.MAPPINGS.items():
            defect_types.append({
                'type': defect_type,
                'description': mapping.get('description', ''),
                'category': mapping.get('category').value if mapping.get('category') else 'unknown',
                'root_cause': mapping.get('root_cause', ''),
                'adjustable_params': list(mapping.get('adjustments', {}).keys()),
            })

        categories = DefectCAMMapping.get_defect_categories()

        return jsonify({
            'success': True,
            'defect_types': defect_types,
            'by_category': categories,
        })

    except Exception as e:
        logger.exception("Error getting defect types")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
