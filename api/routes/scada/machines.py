"""
LEGO Factory v3 - Machine API Routes
====================================
REST API for machine control and monitoring with Pydantic validation.
"""

from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required
from datetime import datetime
import asyncio
import logging

from services.scada.machine_control.machine_service import (
    machine_manager,
    get_machine_service,
    MachineController,
    ControllerType
)
from config.database import get_db_session

# Import Pydantic schemas and validation utilities
from api.schemas import (
    MachineCreate,
    MachineUpdate,
    MachineJogRequest,
    MachineHomeRequest,
    GCodeExecuteRequest,
)
from api.utils.validation import validate_request, validate_path_param

logger = logging.getLogger(__name__)

machines_bp = Blueprint('machines', __name__, url_prefix='/machines')


def run_async(coro):
    """Helper to run async functions in sync context"""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@machines_bp.route('', methods=['GET'])
@jwt_required()
def list_machines():
    """
    Get all registered machines.

    Query parameters:
        - area: Filter by factory area
        - type: Filter by machine type
        - limit: Max results (default: 100)
        - offset: Pagination offset (default: 0)

    Returns:
        200: List of machines with count
        500: Server error
    """
    try:
        with get_db_session() as session:
            service = get_machine_service(session)
            machines = service.get_machines()
            return jsonify({'machines': machines, 'count': len(machines)})
    except Exception as e:
        logger.error(f"Error listing machines: {e}")
        return jsonify({'error': str(e)}), 500


@machines_bp.route('/<machine_id>', methods=['GET'])
@validate_path_param('machine_id', pattern=r'^[a-zA-Z][a-zA-Z0-9_-]*$', max_length=50)
def get_machine(machine_id: str):
    """
    Get machine by ID.

    Path parameters:
        - machine_id: Machine identifier (alphanumeric)

    Returns:
        200: Machine details
        404: Machine not found
        500: Server error
    """
    try:
        with get_db_session() as session:
            service = get_machine_service(session)
            machine = service.get_machine(machine_id)
            if not machine:
                return jsonify({'error': 'Machine not found'}), 404
            return jsonify(machine)
    except Exception as e:
        logger.error(f"Error getting machine {machine_id}: {e}")
        return jsonify({'error': str(e)}), 500


@machines_bp.route('', methods=['POST'])
@validate_request(MachineCreate)
def create_machine(validated_data: MachineCreate):
    """
    Create a new machine.

    Request body (validated by Pydantic):
        {
            "machine_id": "string (required, alphanumeric)",
            "name": "string (required, 1-200 chars)",
            "controller_type": "grbl|marlin|bambu|...",
            "machine_type": "fdm_printer|cnc_mill|... (optional)",
            "ip_address": "string (optional, valid IP)",
            "port": "integer (optional, 1-65535)",
            "serial_port": "string (optional)",
            "area": "string (optional)",
            "description": "string (optional)"
        }

    Returns:
        201: Created machine
        400: Validation error with field details
        500: Server error
    """
    try:
        with get_db_session() as session:
            service = get_machine_service(session)
            machine = service.create_machine(validated_data.model_dump(exclude_none=True))
            session.commit()
            return jsonify(machine), 201
    except Exception as e:
        logger.error(f"Error creating machine: {e}")
        return jsonify({'error': str(e)}), 500


@machines_bp.route('/<machine_id>', methods=['PUT'])
@validate_path_param('machine_id', pattern=r'^[a-zA-Z][a-zA-Z0-9_-]*$', max_length=50)
@validate_request(MachineUpdate)
def update_machine(validated_data: MachineUpdate, machine_id: str):
    """
    Update machine configuration.

    Path parameters:
        - machine_id: Machine identifier

    Request body (validated by Pydantic):
        {
            "name": "string (optional)",
            "controller_type": "string (optional)",
            "ip_address": "string (optional)",
            ...
        }

    Returns:
        200: Updated machine
        400: Validation error
        404: Machine not found
        500: Server error
    """
    try:
        # Only include non-None values for update
        update_data = validated_data.model_dump(exclude_none=True)
        if not update_data:
            return jsonify({'error': 'No data provided'}), 400

        with get_db_session() as session:
            service = get_machine_service(session)
            machine = service.update_machine(machine_id, update_data)
            if not machine:
                return jsonify({'error': 'Machine not found'}), 404
            session.commit()
            return jsonify(machine)
    except Exception as e:
        logger.error(f"Error updating machine {machine_id}: {e}")
        return jsonify({'error': str(e)}), 500


@machines_bp.route('/<machine_id>', methods=['DELETE'])
@validate_path_param('machine_id', pattern=r'^[a-zA-Z][a-zA-Z0-9_-]*$', max_length=50)
def delete_machine(machine_id: str):
    """
    Delete a machine (soft delete).

    Path parameters:
        - machine_id: Machine identifier

    Returns:
        200: Success message
        404: Machine not found
        500: Server error
    """
    try:
        with get_db_session() as session:
            service = get_machine_service(session)
            success = service.delete_machine(machine_id)
            if not success:
                return jsonify({'error': 'Machine not found'}), 404
            session.commit()
            return jsonify({'message': 'Machine deleted'})
    except Exception as e:
        logger.error(f"Error deleting machine {machine_id}: {e}")
        return jsonify({'error': str(e)}), 500


@machines_bp.route('/<machine_id>/connect', methods=['POST'])
@validate_path_param('machine_id', pattern=r'^[a-zA-Z][a-zA-Z0-9_-]*$', max_length=50)
def connect_machine(machine_id: str):
    """
    Connect to a machine.

    Path parameters:
        - machine_id: Machine identifier

    Returns:
        200: Connected successfully
        404: Machine controller not found
        500: Connection failed
    """
    try:
        controller = machine_manager.get_controller(machine_id)
        if not controller:
            return jsonify({'error': 'Machine controller not found'}), 404

        success = run_async(controller.connect())
        if success:
            return jsonify({'message': 'Connected', 'machine_id': machine_id})
        return jsonify({'error': 'Connection failed'}), 500
    except Exception as e:
        logger.error(f"Error connecting to machine {machine_id}: {e}")
        return jsonify({'error': str(e)}), 500


@machines_bp.route('/<machine_id>/disconnect', methods=['POST'])
@validate_path_param('machine_id', pattern=r'^[a-zA-Z][a-zA-Z0-9_-]*$', max_length=50)
def disconnect_machine(machine_id: str):
    """
    Disconnect from a machine.

    Path parameters:
        - machine_id: Machine identifier

    Returns:
        200: Disconnected successfully
        404: Machine controller not found
        500: Server error
    """
    try:
        controller = machine_manager.get_controller(machine_id)
        if not controller:
            return jsonify({'error': 'Machine controller not found'}), 404

        run_async(controller.disconnect())
        return jsonify({'message': 'Disconnected', 'machine_id': machine_id})
    except Exception as e:
        logger.error(f"Error disconnecting from machine {machine_id}: {e}")
        return jsonify({'error': str(e)}), 500


@machines_bp.route('/<machine_id>/status', methods=['GET'])
@validate_path_param('machine_id', pattern=r'^[a-zA-Z][a-zA-Z0-9_-]*$', max_length=50)
def get_machine_status(machine_id: str):
    """
    Get machine status.

    Path parameters:
        - machine_id: Machine identifier

    Returns:
        200: Machine status object
        404: Machine controller not found
        500: Server error
    """
    try:
        controller = machine_manager.get_controller(machine_id)
        if not controller:
            return jsonify({'error': 'Machine controller not found'}), 404

        status = run_async(controller.get_status())
        return jsonify(status)
    except Exception as e:
        logger.error(f"Error getting status for machine {machine_id}: {e}")
        return jsonify({'error': str(e)}), 500


@machines_bp.route('/<machine_id>/home', methods=['POST'])
@validate_path_param('machine_id', pattern=r'^[a-zA-Z][a-zA-Z0-9_-]*$', max_length=50)
@validate_request(MachineHomeRequest)
def home_machine(validated_data: MachineHomeRequest, machine_id: str):
    """
    Home machine axes.

    Path parameters:
        - machine_id: Machine identifier

    Request body (validated by Pydantic):
        {
            "axes": "XYZ (default) | X | Y | Z | XY | XZ | YZ"
        }

    Returns:
        200: Homing complete
        400: Validation error
        404: Machine controller not found
        500: Homing failed
    """
    try:
        controller = machine_manager.get_controller(machine_id)
        if not controller:
            return jsonify({'error': 'Machine controller not found'}), 404

        success = run_async(controller.home(validated_data.axes))
        if success:
            return jsonify({'message': 'Homing complete', 'axes': validated_data.axes})
        return jsonify({'error': 'Homing failed'}), 500
    except Exception as e:
        logger.error(f"Error homing machine {machine_id}: {e}")
        return jsonify({'error': str(e)}), 500


@machines_bp.route('/<machine_id>/jog', methods=['POST'])
@validate_path_param('machine_id', pattern=r'^[a-zA-Z][a-zA-Z0-9_-]*$', max_length=50)
@validate_request(MachineJogRequest)
def jog_machine(validated_data: MachineJogRequest, machine_id: str):
    """
    Jog machine to position.

    Path parameters:
        - machine_id: Machine identifier

    Request body (validated by Pydantic):
        {
            "x": "float (optional, -10000 to 10000 mm)",
            "y": "float (optional, -10000 to 10000 mm)",
            "z": "float (optional, -1000 to 1000 mm)",
            "feed_rate": "integer (default: 1000, 1-100000 mm/min)"
        }

    Note: At least one axis position must be specified.

    Returns:
        200: Jog complete
        400: Validation error (missing axis or invalid values)
        404: Machine controller not found
        500: Jog failed
    """
    try:
        controller = machine_manager.get_controller(machine_id)
        if not controller:
            return jsonify({'error': 'Machine controller not found'}), 404

        success = run_async(controller.jog(
            x=validated_data.x,
            y=validated_data.y,
            z=validated_data.z,
            feed_rate=validated_data.feed_rate
        ))
        if success:
            return jsonify({'message': 'Jog complete'})
        return jsonify({'error': 'Jog failed'}), 500
    except Exception as e:
        logger.error(f"Error jogging machine {machine_id}: {e}")
        return jsonify({'error': str(e)}), 500


@machines_bp.route('/<machine_id>/gcode', methods=['POST'])
@validate_path_param('machine_id', pattern=r'^[a-zA-Z][a-zA-Z0-9_-]*$', max_length=50)
@validate_request(GCodeExecuteRequest)
def run_gcode(validated_data: GCodeExecuteRequest, machine_id: str):
    """
    Execute G-code on machine.

    Path parameters:
        - machine_id: Machine identifier

    Request body (validated by Pydantic):
        {
            "gcode": "string (required, 1-100000 chars)",
            "wait_for_completion": "boolean (default: true)"
        }

    Returns:
        200: G-code execution complete
        400: Validation error
        404: Machine controller not found
        500: G-code execution failed
    """
    try:
        controller = machine_manager.get_controller(machine_id)
        if not controller:
            return jsonify({'error': 'Machine controller not found'}), 404

        success = run_async(controller.run_gcode(validated_data.gcode))
        if success:
            return jsonify({'message': 'G-code execution complete'})
        return jsonify({'error': 'G-code execution failed'}), 500
    except Exception as e:
        logger.error(f"Error running G-code on machine {machine_id}: {e}")
        return jsonify({'error': str(e)}), 500


@machines_bp.route('/<machine_id>/stop', methods=['POST'])
@validate_path_param('machine_id', pattern=r'^[a-zA-Z][a-zA-Z0-9_-]*$', max_length=50)
def stop_machine(machine_id: str):
    """
    Stop machine (feed hold).

    Path parameters:
        - machine_id: Machine identifier

    Returns:
        200: Machine stopped
        404: Machine controller not found
        500: Stop failed
    """
    try:
        controller = machine_manager.get_controller(machine_id)
        if not controller:
            return jsonify({'error': 'Machine controller not found'}), 404

        success = run_async(controller.stop())
        if success:
            return jsonify({'message': 'Machine stopped'})
        return jsonify({'error': 'Stop failed'}), 500
    except Exception as e:
        logger.error(f"Error stopping machine {machine_id}: {e}")
        return jsonify({'error': str(e)}), 500


@machines_bp.route('/<machine_id>/reset', methods=['POST'])
@validate_path_param('machine_id', pattern=r'^[a-zA-Z][a-zA-Z0-9_-]*$', max_length=50)
def reset_machine(machine_id: str):
    """
    Reset machine.

    Path parameters:
        - machine_id: Machine identifier

    Returns:
        200: Machine reset
        404: Machine controller not found
        500: Reset failed
    """
    try:
        controller = machine_manager.get_controller(machine_id)
        if not controller:
            return jsonify({'error': 'Machine controller not found'}), 404

        success = run_async(controller.reset())
        if success:
            return jsonify({'message': 'Machine reset'})
        return jsonify({'error': 'Reset failed'}), 500
    except Exception as e:
        logger.error(f"Error resetting machine {machine_id}: {e}")
        return jsonify({'error': str(e)}), 500


@machines_bp.route('/<machine_id>/events', methods=['GET'])
@validate_path_param('machine_id', pattern=r'^[a-zA-Z][a-zA-Z0-9_-]*$', max_length=50)
def get_machine_events(machine_id: str):
    """
    Get machine events history.

    Path parameters:
        - machine_id: Machine identifier

    Query parameters:
        - limit: Max events to return (default: 100, max: 1000)
        - type: Filter by event type

    Returns:
        200: List of events with count
        500: Server error
    """
    try:
        limit = request.args.get('limit', 100, type=int)
        # Enforce max limit
        limit = min(limit, 1000)
        event_type = request.args.get('type')

        with get_db_session() as session:
            service = get_machine_service(session)
            events = service.get_events(machine_id, limit=limit, event_type=event_type)
            return jsonify({'events': events, 'count': len(events)})
    except Exception as e:
        logger.error(f"Error getting events for machine {machine_id}: {e}")
        return jsonify({'error': str(e)}), 500


@machines_bp.route('/types', methods=['GET'])
@jwt_required()
def get_machine_types():
    """
    Get available machine and controller types.

    Returns:
        200: Dictionary of available types
    """
    from models.scada.machines import MachineType, ControllerType, MachineState

    return jsonify({
        'machine_types': [t.value for t in MachineType],
        'controller_types': [t.value for t in ControllerType],
        'machine_states': [s.value for s in MachineState]
    })


@machines_bp.route('/stats', methods=['GET'])
@jwt_required()
def get_machine_stats():
    """
    Get machine statistics.

    Returns:
        200: Machine statistics
        500: Server error
    """
    try:
        stats = machine_manager.get_stats()
        return jsonify(stats)
    except Exception as e:
        logger.error(f"Error getting machine stats: {e}")
        return jsonify({'error': str(e)}), 500
