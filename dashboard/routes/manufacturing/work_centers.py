"""
Work Center Management API - Machine configuration and control.

Provides:
- Work center CRUD
- Status monitoring
- Equipment connection management
- Capacity and scheduling info
"""

from flask import Blueprint, jsonify, request, render_template
from datetime import datetime
import asyncio

from models import get_db_session, WorkCenter
from models.manufacturing import WorkCenterStatus
from services.manufacturing import OEEService
from services.equipment import (
    PrinterController, PrinterProtocol,
    MillController, LaserController,
    EquipmentStatus
)

work_centers_bp = Blueprint('work_centers', __name__, url_prefix='/work-centers')


# Dashboard Page Route
@work_centers_bp.route('/page', methods=['GET'])
def work_centers_page():
    """Render work centers dashboard page."""
    return render_template('pages/manufacturing/work_centers.html')

# Cache of active equipment controllers
_equipment_controllers = {}


def get_controller(work_center_id: str, connection_info: dict, wc_type: str):
    """Get or create equipment controller for work center."""
    if work_center_id in _equipment_controllers:
        return _equipment_controllers[work_center_id]

    # Create appropriate controller based on type
    if wc_type == '3d_printer':
        controller = PrinterController(
            work_center_id=work_center_id,
            name=f"Printer-{work_center_id[:8]}",
            connection_info=connection_info
        )
    elif wc_type == 'cnc_mill':
        controller = MillController(
            work_center_id=work_center_id,
            name=f"Mill-{work_center_id[:8]}",
            connection_info=connection_info
        )
    elif wc_type == 'laser_engraver':
        controller = LaserController(
            work_center_id=work_center_id,
            name=f"Laser-{work_center_id[:8]}",
            connection_info=connection_info
        )
    else:
        return None

    _equipment_controllers[work_center_id] = controller
    return controller


@work_centers_bp.route('', methods=['GET'])
def list_work_centers():
    """List all work centers."""
    with get_db_session() as session:
        work_centers = session.query(WorkCenter).order_by(WorkCenter.code).all()

        return jsonify({
            'work_centers': [{
                'id': str(wc.id),
                'code': wc.code,
                'name': wc.name,
                'type': wc.type,
                'status': wc.status,
                'capacity_per_hour': wc.capacity_per_hour,
                'hourly_rate': float(wc.hourly_rate) if wc.hourly_rate else 0,
                'efficiency_percent': wc.efficiency_percent,
                'connection_info': wc.connection_info,
                'total_runtime_hours': float(wc.total_runtime_hours) if wc.total_runtime_hours else 0,
                'last_maintenance': wc.last_maintenance.isoformat() if wc.last_maintenance else None
            } for wc in work_centers],
            'total': len(work_centers)
        })


@work_centers_bp.route('', methods=['POST'])
def create_work_center():
    """
    Create a new work center.

    Request body:
    {
        "code": "PRINTER-02",
        "name": "Prusa MK4",
        "type": "3d_printer",
        "capacity_per_hour": 2,
        "hourly_rate": 5.00,
        "connection_info": {
            "protocol": "prusa_connect",
            "host": "192.168.1.101",
            "api_key": "xxx"
        }
    }
    """
    data = request.get_json()

    code = data.get('code')
    name = data.get('name')
    wc_type = data.get('type')

    if not all([code, name, wc_type]):
        return jsonify({'error': 'code, name, and type are required'}), 400

    with get_db_session() as session:
        # Check for duplicate code
        existing = session.query(WorkCenter).filter(WorkCenter.code == code).first()
        if existing:
            return jsonify({'error': f'Work center {code} already exists'}), 400

        work_center = WorkCenter(
            code=code,
            name=name,
            type=wc_type,
            status=WorkCenterStatus.OFFLINE.value,
            capacity_per_hour=data.get('capacity_per_hour', 1),
            hourly_rate=data.get('hourly_rate', 0),
            efficiency_percent=data.get('efficiency_percent', 85),
            connection_info=data.get('connection_info', {})
        )

        session.add(work_center)
        session.commit()

        return jsonify({
            'id': str(work_center.id),
            'code': work_center.code,
            'message': 'Work center created successfully'
        }), 201


@work_centers_bp.route('/<work_center_id>', methods=['GET'])
def get_work_center(work_center_id: str):
    """Get work center details."""
    with get_db_session() as session:
        wc = session.query(WorkCenter).filter(WorkCenter.id == work_center_id).first()

        if not wc:
            return jsonify({'error': 'Work center not found'}), 404

        oee_service = OEEService(session)
        status = oee_service.get_work_center_status(work_center_id)

        return jsonify({
            'id': str(wc.id),
            'code': wc.code,
            'name': wc.name,
            'type': wc.type,
            'status': wc.status,
            'capacity_per_hour': wc.capacity_per_hour,
            'hourly_rate': float(wc.hourly_rate) if wc.hourly_rate else 0,
            'efficiency_percent': wc.efficiency_percent,
            'connection_info': wc.connection_info,
            'total_runtime_hours': float(wc.total_runtime_hours) if wc.total_runtime_hours else 0,
            'last_maintenance': wc.last_maintenance.isoformat() if wc.last_maintenance else None,
            'next_maintenance': wc.next_maintenance.isoformat() if wc.next_maintenance else None,
            'oee': status.get('current_shift_oee', {}),
            'created_at': wc.created_at.isoformat() if wc.created_at else None
        })


@work_centers_bp.route('/<work_center_id>', methods=['PUT'])
def update_work_center(work_center_id: str):
    """Update work center configuration."""
    data = request.get_json()

    with get_db_session() as session:
        wc = session.query(WorkCenter).filter(WorkCenter.id == work_center_id).first()

        if not wc:
            return jsonify({'error': 'Work center not found'}), 404

        # Update allowed fields
        if 'name' in data:
            wc.name = data['name']
        if 'capacity_per_hour' in data:
            wc.capacity_per_hour = data['capacity_per_hour']
        if 'hourly_rate' in data:
            wc.hourly_rate = data['hourly_rate']
        if 'efficiency_percent' in data:
            wc.efficiency_percent = data['efficiency_percent']
        if 'connection_info' in data:
            wc.connection_info = data['connection_info']

        session.commit()

        return jsonify({
            'id': str(wc.id),
            'code': wc.code,
            'message': 'Work center updated'
        })


@work_centers_bp.route('/<work_center_id>/status', methods=['GET'])
def get_work_center_status(work_center_id: str):
    """Get real-time status from equipment."""
    with get_db_session() as session:
        wc = session.query(WorkCenter).filter(WorkCenter.id == work_center_id).first()

        if not wc:
            return jsonify({'error': 'Work center not found'}), 404

        # Get OEE status
        oee_service = OEEService(session)
        oee_status = oee_service.get_work_center_status(work_center_id)

        # Try to get live equipment status
        equipment_state = None
        if wc.connection_info:
            controller = get_controller(work_center_id, wc.connection_info, wc.type)
            if controller:
                try:
                    # Run async in sync context
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    state = loop.run_until_complete(controller.get_state())
                    loop.close()

                    equipment_state = {
                        'status': state.status.value,
                        'current_job_id': state.current_job_id,
                        'job_progress_percent': state.job_progress_percent,
                        'temperatures': state.temperatures,
                        'positions': state.positions,
                        'speeds': state.speeds,
                        'extra_data': state.extra_data
                    }
                except Exception as e:
                    equipment_state = {'error': str(e)}

        return jsonify({
            'work_center': oee_status.get('work_center', {}),
            'current_shift_oee': oee_status.get('current_shift_oee', {}),
            'equipment_state': equipment_state
        })


@work_centers_bp.route('/<work_center_id>/connect', methods=['POST'])
def connect_work_center(work_center_id: str):
    """Establish connection to equipment."""
    with get_db_session() as session:
        wc = session.query(WorkCenter).filter(WorkCenter.id == work_center_id).first()

        if not wc:
            return jsonify({'error': 'Work center not found'}), 404

        if not wc.connection_info:
            return jsonify({'error': 'No connection info configured'}), 400

        controller = get_controller(work_center_id, wc.connection_info, wc.type)
        if not controller:
            return jsonify({'error': f'Unsupported equipment type: {wc.type}'}), 400

        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            connected = loop.run_until_complete(controller.connect())
            loop.close()

            if connected:
                wc.status = WorkCenterStatus.IDLE.value
                session.commit()
                return jsonify({'message': 'Connected successfully', 'status': 'idle'})
            else:
                return jsonify({'error': 'Connection failed'}), 500

        except Exception as e:
            return jsonify({'error': str(e)}), 500


@work_centers_bp.route('/<work_center_id>/disconnect', methods=['POST'])
def disconnect_work_center(work_center_id: str):
    """Disconnect from equipment."""
    if work_center_id in _equipment_controllers:
        controller = _equipment_controllers[work_center_id]
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(controller.disconnect())
            loop.close()
        except Exception:
            pass

        del _equipment_controllers[work_center_id]

    with get_db_session() as session:
        wc = session.query(WorkCenter).filter(WorkCenter.id == work_center_id).first()
        if wc:
            wc.status = WorkCenterStatus.OFFLINE.value
            session.commit()

    return jsonify({'message': 'Disconnected', 'status': 'offline'})


@work_centers_bp.route('/<work_center_id>/home', methods=['POST'])
def home_work_center(work_center_id: str):
    """Home equipment axes."""
    with get_db_session() as session:
        wc = session.query(WorkCenter).filter(WorkCenter.id == work_center_id).first()

        if not wc:
            return jsonify({'error': 'Work center not found'}), 404

    controller = _equipment_controllers.get(work_center_id)
    if not controller or not controller.is_connected:
        return jsonify({'error': 'Equipment not connected'}), 400

    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        success = loop.run_until_complete(controller.home())
        loop.close()

        if success:
            return jsonify({'message': 'Homing started'})
        else:
            return jsonify({'error': 'Homing failed'}), 500

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@work_centers_bp.route('/<work_center_id>/emergency-stop', methods=['POST'])
def emergency_stop(work_center_id: str):
    """Emergency stop equipment."""
    controller = _equipment_controllers.get(work_center_id)

    if controller:
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(controller.emergency_stop())
            loop.close()
        except Exception:
            pass

    with get_db_session() as session:
        wc = session.query(WorkCenter).filter(WorkCenter.id == work_center_id).first()
        if wc:
            wc.status = WorkCenterStatus.DOWN.value
            session.commit()

    return jsonify({'message': 'Emergency stop triggered', 'status': 'down'})


@work_centers_bp.route('/<work_center_id>/capabilities', methods=['GET'])
def get_capabilities(work_center_id: str):
    """Get equipment capabilities."""
    with get_db_session() as session:
        wc = session.query(WorkCenter).filter(WorkCenter.id == work_center_id).first()

        if not wc:
            return jsonify({'error': 'Work center not found'}), 404

    controller = _equipment_controllers.get(work_center_id)
    if not controller or not controller.is_connected:
        return jsonify({
            'work_center_type': wc.type,
            'message': 'Connect to equipment for detailed capabilities'
        })

    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        capabilities = loop.run_until_complete(controller.get_capabilities())
        loop.close()

        return jsonify({
            'work_center_type': wc.type,
            'capabilities': capabilities
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500
