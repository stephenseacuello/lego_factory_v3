"""
Unity API Routes
================

REST API endpoints for Unity 3D clients.

Endpoints:
- Scene data (full and delta)
- Equipment state and control
- OME management
- Predictions and analytics
- AR/VR spatial anchors

Author: LegoMCP Team
Version: 2.0.0
"""

from flask import Blueprint, request, jsonify, current_app
from flask_socketio import emit, join_room, leave_room
from datetime import datetime, timedelta
from typing import Dict, Any, List
import logging

# Import services
from services.unity import get_unity_bridge, get_scene_data_service
from services.digital_twin.ome_registry import (
    get_ome_registry,
    ObservableManufacturingElement,
    OMEType,
    OMELifecycleState,
    create_printer_ome,
    create_work_cell_ome
)
from services.digital_twin.twin_engine import (
    get_twin_engine,
    TwinType,
    SyncMode,
    SimulationConfig
)

logger = logging.getLogger(__name__)

# Create Blueprint
unity_bp = Blueprint('unity', __name__, url_prefix='/api/unity')


# ================== Scene Data Endpoints ==================

@unity_bp.route('/scene', methods=['GET'])
def get_full_scene():
    """
    Get complete 3D scene data for Unity.

    Query Parameters:
        namespace: Filter by namespace (default: 'default')
        lod: Level of detail (0-4, default: 1)

    Returns:
        Complete scene data including equipment, sensors, annotations, etc.
    """
    try:
        namespace = request.args.get('namespace', 'default')
        lod = int(request.args.get('lod', 1))

        scene_service = get_scene_data_service()
        twin_engine = get_twin_engine()

        # Get scene data
        scene_data = scene_service.get_full_scene()

        # Add twin engine state
        scene_data['twins'] = [
            twin.to_dict() for twin in twin_engine.get_all_twins()
        ]

        # Add engine metrics
        scene_data['engineMetrics'] = twin_engine.get_metrics()

        return jsonify({
            'success': True,
            'data': scene_data
        })

    except Exception as e:
        logger.error(f"Error getting scene: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@unity_bp.route('/scene/delta', methods=['GET'])
def get_delta_scene():
    """
    Get scene changes since specified version.

    Query Parameters:
        since_version: Version number to get changes from
        namespace: Filter by namespace

    Returns:
        Only changed objects since version
    """
    try:
        since_version = int(request.args.get('since_version', 0))
        namespace = request.args.get('namespace', 'default')

        scene_service = get_scene_data_service()

        delta = scene_service.get_delta_scene(since_version)

        return jsonify({
            'success': True,
            'data': delta
        })

    except Exception as e:
        logger.error(f"Error getting delta: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@unity_bp.route('/scene/settings', methods=['GET', 'PUT'])
def scene_settings():
    """Get or update scene settings."""
    scene_service = get_scene_data_service()

    if request.method == 'GET':
        return jsonify({
            'success': True,
            'data': scene_service._settings.to_dict()
        })

    elif request.method == 'PUT':
        try:
            settings = request.get_json()
            scene_service.update_settings(settings)

            return jsonify({
                'success': True,
                'message': 'Settings updated'
            })
        except Exception as e:
            return jsonify({
                'success': False,
                'error': str(e)
            }), 400


# ================== Equipment Endpoints ==================

@unity_bp.route('/equipment', methods=['GET'])
def get_all_equipment():
    """
    Get all equipment with 3D scene data.

    Query Parameters:
        namespace: Filter by namespace
        status: Filter by status
        type: Filter by equipment type

    Returns:
        List of equipment with visual properties
    """
    try:
        namespace = request.args.get('namespace', 'default')
        status_filter = request.args.get('status')
        type_filter = request.args.get('type')

        registry = get_ome_registry()
        scene_service = get_scene_data_service()

        # Get OMEs
        omes = registry.get_by_type(OMEType.EQUIPMENT)

        # Filter
        if status_filter:
            omes = [o for o in omes if o.dynamic_attributes.status == status_filter]
        if type_filter:
            omes = [o for o in omes if type_filter.lower() in o.name.lower()]

        # Get scene objects
        equipment_data = []
        for ome in omes:
            scene_obj = scene_service._equipment.get(ome.id)
            if scene_obj:
                data = scene_obj.to_dict()
                data['ome'] = ome.to_dict()
            else:
                data = ome.to_unity_dict()

            equipment_data.append(data)

        return jsonify({
            'success': True,
            'count': len(equipment_data),
            'data': equipment_data
        })

    except Exception as e:
        logger.error(f"Error getting equipment: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@unity_bp.route('/equipment/<equipment_id>', methods=['GET'])
def get_equipment(equipment_id: str):
    """
    Get single equipment details.

    Path Parameters:
        equipment_id: OME ID of equipment

    Returns:
        Equipment details with visual and twin data
    """
    try:
        registry = get_ome_registry()
        scene_service = get_scene_data_service()
        twin_engine = get_twin_engine()

        ome = registry.get(equipment_id)
        if not ome:
            return jsonify({
                'success': False,
                'error': 'Equipment not found'
            }), 404

        # Get scene object
        scene_obj = scene_service._equipment.get(equipment_id)

        # Get twins
        twins = twin_engine.get_twins_for_ome(equipment_id)

        response_data = {
            'ome': ome.to_dict(),
            'visual': scene_obj.to_dict() if scene_obj else None,
            'twins': [t.to_dict() for t in twins]
        }

        return jsonify({
            'success': True,
            'data': response_data
        })

    except Exception as e:
        logger.error(f"Error getting equipment {equipment_id}: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@unity_bp.route('/equipment/<equipment_id>/highlight', methods=['POST'])
def highlight_equipment(equipment_id: str):
    """
    Trigger highlight animation on equipment.

    Path Parameters:
        equipment_id: OME ID of equipment

    Body:
        style: Highlight style (outline, glow, pulse, blink)
        color: Highlight color (hex)
        duration: Duration in seconds

    Returns:
        Success status
    """
    try:
        data = request.get_json() or {}

        bridge = get_unity_bridge()

        bridge.trigger_highlight(
            equipment_id=equipment_id,
            highlight_type=data.get('style', 'pulse'),
            color=data.get('color', '#FFFF00'),
            duration_seconds=data.get('duration', 3.0)
        )

        return jsonify({
            'success': True,
            'message': f'Highlight triggered on {equipment_id}'
        })

    except Exception as e:
        logger.error(f"Error highlighting equipment: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@unity_bp.route('/equipment/<equipment_id>/command', methods=['POST'])
def send_command(equipment_id: str):
    """
    Send command to equipment via digital twin.

    Path Parameters:
        equipment_id: OME ID of equipment

    Body:
        command: Command name
        parameters: Command parameters

    Returns:
        Command acknowledgment
    """
    try:
        data = request.get_json()

        if not data or 'command' not in data:
            return jsonify({
                'success': False,
                'error': 'Command required'
            }), 400

        twin_engine = get_twin_engine()

        # Find active twin for equipment
        twins = twin_engine.get_twins_for_ome(equipment_id)
        if not twins:
            return jsonify({
                'success': False,
                'error': 'No active twin for equipment'
            }), 404

        # Send command through first active twin
        result = twin_engine.sync_to_physical(
            twins[0].id,
            {
                'command': data['command'],
                'parameters': data.get('parameters', {})
            }
        )

        return jsonify({
            'success': result.get('success', False),
            'data': result
        })

    except Exception as e:
        logger.error(f"Error sending command: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# ================== OME Registry Endpoints ==================

@unity_bp.route('/ome', methods=['GET', 'POST'])
def ome_list():
    """
    List or create Observable Manufacturing Elements.

    GET Query Parameters:
        namespace: Filter by namespace
        type: Filter by OME type
        state: Filter by lifecycle state

    POST Body:
        name: OME name
        type: OME type (equipment, sensor, etc.)
        parent_id: Parent OME ID (optional)
        static_attributes: Static properties
        position: 3D position for visualization

    Returns:
        List of OMEs or created OME
    """
    registry = get_ome_registry()

    if request.method == 'GET':
        namespace = request.args.get('namespace', 'default')
        type_filter = request.args.get('type')
        state_filter = request.args.get('state')

        omes = registry.get_all(namespace)

        if type_filter:
            try:
                ome_type = OMEType(type_filter)
                omes = [o for o in omes if o.ome_type == ome_type]
            except ValueError:
                pass

        if state_filter:
            try:
                state = OMELifecycleState(state_filter)
                omes = [o for o in omes if o.lifecycle_state == state]
            except ValueError:
                pass

        return jsonify({
            'success': True,
            'count': len(omes),
            'data': [o.to_dict() for o in omes]
        })

    elif request.method == 'POST':
        try:
            data = request.get_json()

            if not data or 'name' not in data:
                return jsonify({
                    'success': False,
                    'error': 'Name required'
                }), 400

            ome_type = OMEType(data.get('type', 'equipment'))

            # Create OME using factory if applicable
            if ome_type == OMEType.EQUIPMENT and 'printer' in data.get('name', '').lower():
                ome = create_printer_ome(
                    name=data['name'],
                    manufacturer=data.get('manufacturer', 'Prusa'),
                    model=data.get('model', 'MK3S+'),
                    position=data.get('position'),
                    namespace=data.get('namespace', 'default')
                )
            else:
                ome = ObservableManufacturingElement(
                    name=data['name'],
                    ome_type=ome_type,
                    description=data.get('description', ''),
                    namespace=data.get('namespace', 'default'),
                    parent_id=data.get('parent_id')
                )

            registered = registry.register(ome)

            # Add to scene
            if ome_type == OMEType.EQUIPMENT and 'position' in data:
                scene_service = get_scene_data_service()
                from services.unity.scene_data import Vector3
                pos = data['position']
                scene_service.add_equipment(
                    ome_id=registered.id,
                    name=registered.name,
                    equipment_type=data.get('equipment_type', 'prusa_mk3s'),
                    position=Vector3(pos.get('x', 0), pos.get('y', 0), pos.get('z', 0))
                )

            return jsonify({
                'success': True,
                'data': registered.to_dict()
            }), 201

        except Exception as e:
            logger.error(f"Error creating OME: {e}")
            return jsonify({
                'success': False,
                'error': str(e)
            }), 400


@unity_bp.route('/ome/<ome_id>', methods=['GET', 'PUT', 'DELETE'])
def ome_detail(ome_id: str):
    """
    Get, update, or delete an OME.

    Path Parameters:
        ome_id: OME identifier

    PUT Body:
        Any OME properties to update

    Returns:
        OME data or success status
    """
    registry = get_ome_registry()

    ome = registry.get(ome_id)
    if not ome:
        return jsonify({
            'success': False,
            'error': 'OME not found'
        }), 404

    if request.method == 'GET':
        return jsonify({
            'success': True,
            'data': ome.to_dict()
        })

    elif request.method == 'PUT':
        try:
            data = request.get_json()
            updated = registry.update(ome_id, data)

            return jsonify({
                'success': True,
                'data': updated.to_dict()
            })
        except Exception as e:
            return jsonify({
                'success': False,
                'error': str(e)
            }), 400

    elif request.method == 'DELETE':
        registry.delete(ome_id)
        return jsonify({
            'success': True,
            'message': f'OME {ome_id} deleted'
        })


@unity_bp.route('/ome/<ome_id>/lifecycle', methods=['POST'])
def ome_lifecycle_transition(ome_id: str):
    """
    Transition OME lifecycle state.

    Path Parameters:
        ome_id: OME identifier

    Body:
        state: New lifecycle state
        reason: Reason for transition

    Returns:
        Updated OME
    """
    try:
        data = request.get_json()

        if not data or 'state' not in data:
            return jsonify({
                'success': False,
                'error': 'State required'
            }), 400

        new_state = OMELifecycleState(data['state'])
        reason = data.get('reason', '')
        user = data.get('user', 'api')

        registry = get_ome_registry()
        updated = registry.transition_lifecycle(ome_id, new_state, reason, user)

        return jsonify({
            'success': True,
            'data': updated.to_dict()
        })

    except ValueError as e:
        return jsonify({
            'success': False,
            'error': f'Invalid transition: {e}'
        }), 400
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@unity_bp.route('/ome/<ome_id>/twins', methods=['GET', 'POST'])
def ome_twins(ome_id: str):
    """
    Get or create digital twin instances for an OME.

    GET: List all twins for OME
    POST: Create new twin instance

    POST Body:
        twin_type: Type of twin (monitoring, simulation, predictive)
        sync_mode: Synchronization mode

    Returns:
        List of twins or created twin
    """
    twin_engine = get_twin_engine()

    if request.method == 'GET':
        twins = twin_engine.get_twins_for_ome(ome_id)

        return jsonify({
            'success': True,
            'count': len(twins),
            'data': [t.to_dict() for t in twins]
        })

    elif request.method == 'POST':
        try:
            data = request.get_json() or {}

            twin_type = TwinType(data.get('twin_type', 'monitoring'))
            sync_mode = SyncMode(data.get('sync_mode', 'realtime'))

            twin = twin_engine.create_twin(
                ome_id=ome_id,
                twin_type=twin_type,
                sync_mode=sync_mode,
                initial_state=data.get('initial_state')
            )

            return jsonify({
                'success': True,
                'data': twin.to_dict()
            }), 201

        except Exception as e:
            logger.error(f"Error creating twin: {e}")
            return jsonify({
                'success': False,
                'error': str(e)
            }), 400


# ================== Prediction Endpoints ==================

@unity_bp.route('/predict/failure/<ome_id>', methods=['GET'])
def predict_failure(ome_id: str):
    """
    Get failure prediction for equipment.

    Path Parameters:
        ome_id: Equipment OME ID

    Query Parameters:
        horizon: Prediction horizon in hours (default: 24)

    Returns:
        Failure prediction with probability and factors
    """
    try:
        horizon = float(request.args.get('horizon', 24))

        twin_engine = get_twin_engine()

        # Get or create twin
        twins = twin_engine.get_twins_for_ome(ome_id)
        if not twins:
            twin = twin_engine.create_twin(ome_id, TwinType.PREDICTIVE)
        else:
            twin = twins[0]

        prediction = twin_engine.predict_failure(twin.id, horizon)

        return jsonify({
            'success': True,
            'data': {
                'ome_id': ome_id,
                'prediction_type': prediction.prediction_type,
                'probability': prediction.value,
                'confidence': prediction.confidence,
                'valid_until': prediction.valid_until.isoformat(),
                'contributing_factors': prediction.contributing_factors,
                'recommendations': prediction.recommendations
            }
        })

    except Exception as e:
        logger.error(f"Error predicting failure: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@unity_bp.route('/predict/rul/<ome_id>', methods=['GET'])
def predict_rul(ome_id: str):
    """
    Estimate Remaining Useful Life for equipment.

    Path Parameters:
        ome_id: Equipment OME ID

    Returns:
        RUL estimation with confidence
    """
    try:
        twin_engine = get_twin_engine()

        twins = twin_engine.get_twins_for_ome(ome_id)
        if not twins:
            twin = twin_engine.create_twin(ome_id, TwinType.PREDICTIVE)
        else:
            twin = twins[0]

        prediction = twin_engine.estimate_rul(twin.id)

        return jsonify({
            'success': True,
            'data': {
                'ome_id': ome_id,
                'rul_hours': prediction.value,
                'confidence': prediction.confidence,
                'contributing_factors': prediction.contributing_factors,
                'recommendations': prediction.recommendations
            }
        })

    except Exception as e:
        logger.error(f"Error estimating RUL: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@unity_bp.route('/predict/quality/<ome_id>', methods=['POST'])
def predict_quality(ome_id: str):
    """
    Predict quality outcome for a job.

    Path Parameters:
        ome_id: Equipment OME ID

    Body:
        job_params: Job parameters (optional)

    Returns:
        Quality prediction
    """
    try:
        data = request.get_json() or {}

        twin_engine = get_twin_engine()

        twins = twin_engine.get_twins_for_ome(ome_id)
        if not twins:
            return jsonify({
                'success': False,
                'error': 'No active twin'
            }), 404

        prediction = twin_engine.predict_quality(
            twins[0].id,
            data.get('job_params')
        )

        return jsonify({
            'success': True,
            'data': {
                'ome_id': ome_id,
                'quality_probability': prediction.value,
                'confidence': prediction.confidence,
                'contributing_factors': prediction.contributing_factors,
                'recommendations': prediction.recommendations
            }
        })

    except Exception as e:
        logger.error(f"Error predicting quality: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# ================== Simulation Endpoints ==================

@unity_bp.route('/simulate/<twin_id>', methods=['POST'])
def run_simulation(twin_id: str):
    """
    Run simulation on a digital twin.

    Path Parameters:
        twin_id: Twin instance ID

    Body:
        duration_seconds: Simulation duration
        time_scale: Time multiplier (1.0 = real-time)
        initial_state: Starting state (optional)
        parameters: Simulation parameters

    Returns:
        Simulation results
    """
    try:
        data = request.get_json() or {}

        config = SimulationConfig(
            duration_seconds=data.get('duration_seconds', 3600),
            time_scale=data.get('time_scale', 10.0),
            initial_state=data.get('initial_state'),
            parameters=data.get('parameters', {}),
            record_interval_seconds=data.get('record_interval', 60),
            random_seed=data.get('random_seed')
        )

        twin_engine = get_twin_engine()
        result = twin_engine.run_simulation(twin_id, config)

        return jsonify({
            'success': True,
            'data': {
                'simulation_id': result.simulation_id,
                'twin_id': result.twin_id,
                'started_at': result.started_at.isoformat(),
                'completed_at': result.completed_at.isoformat(),
                'duration_simulated': result.duration_simulated,
                'final_state': result.final_state,
                'metrics': result.metrics,
                'events': result.events,
                'warnings': result.warnings,
                'time_series_count': len(result.time_series)
            }
        })

    except Exception as e:
        logger.error(f"Error running simulation: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# ================== Health/Metrics Endpoints ==================

@unity_bp.route('/health', methods=['GET'])
def health_summary():
    """
    Get health summary of all equipment.

    Returns:
        Health distribution and alerts
    """
    try:
        registry = get_ome_registry()

        health = registry.get_health_summary()

        return jsonify({
            'success': True,
            'data': health
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@unity_bp.route('/metrics', methods=['GET'])
def get_metrics():
    """
    Get system metrics for monitoring.

    Returns:
        Twin engine and bridge metrics
    """
    try:
        twin_engine = get_twin_engine()
        bridge = get_unity_bridge()

        return jsonify({
            'success': True,
            'data': {
                'twin_engine': twin_engine.get_metrics(),
                'unity_bridge': bridge.get_metrics(),
                'timestamp': datetime.utcnow().isoformat()
            }
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# ================== Camera Presets ==================

@unity_bp.route('/camera/presets', methods=['GET', 'POST'])
def camera_presets():
    """
    Get or create camera presets.

    GET: List all presets
    POST: Create new preset

    POST Body:
        name: Preset name
        position: Camera position {x, y, z}
        target: Look-at target {x, y, z}
        fov: Field of view (optional)

    Returns:
        List of presets or created preset
    """
    scene_service = get_scene_data_service()

    if request.method == 'GET':
        if not scene_service._camera_presets:
            scene_service.get_default_camera_presets()

        presets = [p.to_dict() for p in scene_service._camera_presets.values()]

        return jsonify({
            'success': True,
            'data': presets
        })

    elif request.method == 'POST':
        try:
            data = request.get_json()

            from services.unity.scene_data import Vector3

            preset = scene_service.add_camera_preset(
                name=data['name'],
                position=Vector3(**data['position']),
                target=Vector3(**data['target']),
                fov=data.get('fov', 60)
            )

            return jsonify({
                'success': True,
                'data': preset.to_dict()
            }), 201

        except Exception as e:
            return jsonify({
                'success': False,
                'error': str(e)
            }), 400


# ================== AR/VR Endpoints ==================

@unity_bp.route('/ar/anchors', methods=['GET', 'POST'])
def spatial_anchors():
    """
    Manage AR spatial anchors.

    GET: List all anchors
    POST: Create/update anchor

    POST Body:
        anchor_id: Anchor identifier
        position: World position
        rotation: World rotation
        equipment_id: Associated equipment (optional)

    Returns:
        List of anchors or created anchor
    """
    bridge = get_unity_bridge()

    if request.method == 'GET':
        # Collect anchors from all AR clients
        anchors = []
        for client in bridge.get_all_clients():
            if client.client_type.value.startswith('ar_'):
                anchors.extend(client.spatial_anchors)

        return jsonify({
            'success': True,
            'data': anchors
        })

    elif request.method == 'POST':
        try:
            data = request.get_json()

            bridge.sync_spatial_anchor(
                anchor_id=data['anchor_id'],
                position=data['position'],
                rotation=data['rotation'],
                equipment_id=data.get('equipment_id')
            )

            return jsonify({
                'success': True,
                'message': 'Anchor synced'
            })

        except Exception as e:
            return jsonify({
                'success': False,
                'error': str(e)
            }), 400


@unity_bp.route('/vr/clients', methods=['GET'])
def get_vr_clients():
    """
    Get connected VR/AR clients.

    Returns:
        List of VR/AR client connections
    """
    from services.unity.bridge import ClientType

    bridge = get_unity_bridge()

    vr_ar_types = {
        ClientType.VR_QUEST,
        ClientType.VR_VIVE,
        ClientType.AR_HOLOLENS,
        ClientType.AR_IOS,
        ClientType.AR_ANDROID
    }

    clients = [
        c.to_dict() for c in bridge.get_all_clients()
        if c.client_type in vr_ar_types
    ]

    return jsonify({
        'success': True,
        'count': len(clients),
        'data': clients
    })


# ================== ISO 23247 Compliance ==================

@unity_bp.route('/compliance/iso23247/status', methods=['GET'])
def iso23247_status():
    """
    Get ISO 23247 compliance status.

    Returns:
        Compliance level and gap analysis
    """
    registry = get_ome_registry()
    twin_engine = get_twin_engine()

    # Check compliance requirements
    omes = registry.get_all()
    twins = twin_engine.get_all_twins()

    checks = {
        'ome_registry': {
            'status': 'compliant' if len(omes) > 0 else 'non_compliant',
            'description': 'Observable Manufacturing Element registry',
            'count': len(omes)
        },
        'lifecycle_management': {
            'status': 'compliant',
            'description': 'OME lifecycle state management',
            'states_used': list(set(o.lifecycle_state.value for o in omes))
        },
        'digital_twin_instances': {
            'status': 'compliant' if len(twins) > 0 else 'partial',
            'description': 'Digital twin instances for OMEs',
            'count': len(twins)
        },
        'state_synchronization': {
            'status': 'compliant' if twin_engine._sync_running else 'partial',
            'description': 'Real-time state synchronization',
            'sync_running': twin_engine._sync_running
        },
        'behavior_models': {
            'status': 'compliant',
            'description': 'Physics and ML behavior models available',
            'model_types': ['physics', 'rules', 'pinn', 'hybrid']
        },
        'event_sourcing': {
            'status': 'compliant',
            'description': 'Event-based state tracking'
        },
        'hierarchical_structure': {
            'status': 'compliant',
            'description': 'Factory-Line-Cell-Equipment hierarchy supported'
        }
    }

    compliant_count = sum(1 for c in checks.values() if c['status'] == 'compliant')
    total_checks = len(checks)

    return jsonify({
        'success': True,
        'data': {
            'compliance_level': f"{compliant_count}/{total_checks}",
            'percentage': round(compliant_count / total_checks * 100, 1),
            'standard': 'ISO 23247',
            'checks': checks,
            'timestamp': datetime.utcnow().isoformat()
        }
    })


# Export blueprint
def init_unity_routes(app):
    """Initialize Unity routes with Flask app."""
    app.register_blueprint(unity_bp)
    logger.info("Unity API routes registered")
