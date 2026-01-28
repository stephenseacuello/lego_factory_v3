"""
LEGO Factory v3 - Unity Digital Twin View Routes
=================================================
Digital Twin 3D visualization dashboards.
"""

from flask import Blueprint, render_template, jsonify, request
import logging

logger = logging.getLogger(__name__)

unity_bp = Blueprint('unity', __name__, url_prefix='/unity')


@unity_bp.route('/viewer')
def viewer():
    """Main 3D factory viewer."""
    try:
        from services.unity.unity_state_service import get_unity_service
        service = get_unity_service()
        scene = service.get_scene_state()
    except Exception as e:
        logger.warning(f'Exception in unity_views.py: {e}')
        scene = {}

    return render_template('unity/viewer.html', scene=scene)


@unity_bp.route('/playback')
def playback():
    """Historical playback viewer."""
    return render_template('unity/playback.html')


@unity_bp.route('/api/state')
def get_state():
    """Get current scene state (JSON)."""
    try:
        from services.unity.unity_state_service import get_unity_service
        service = get_unity_service()
        return jsonify(service.get_scene_state())
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@unity_bp.route('/api/entity/<entity_id>', methods=['GET', 'PATCH'])
def entity(entity_id):
    """Get or update entity state."""
    try:
        from services.unity.unity_state_service import get_unity_service
        service = get_unity_service()

        if request.method == 'GET':
            entity = service.get_entity(entity_id)
            if entity:
                return jsonify(entity)
            return jsonify({'error': 'Entity not found'}), 404

        elif request.method == 'PATCH':
            data = request.json
            success = service.update_entity(
                entity_id,
                state=data.get('state'),
                transform=data.get('transform')
            )
            if success:
                return jsonify({'success': True})
            return jsonify({'error': 'Update failed'}), 400

    except Exception as e:
        return jsonify({'error': str(e)}), 500
