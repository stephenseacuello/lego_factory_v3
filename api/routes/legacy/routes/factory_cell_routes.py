"""
Factory Cell Orchestration Routes

API endpoints for managing the manufacturing cell:
- Job queue management
- Production control (start/stop/pause)
- Pallet management
- Cell status and monitoring
- Pick-and-place workflow coordination
"""

from flask import Blueprint, jsonify, request, current_app
from typing import Dict, Any
import asyncio

factory_cell_bp = Blueprint(
    'factory_cell',
    __name__,
    url_prefix='/api/factory'
)


def get_factory_orchestrator():
    """Get factory cell orchestrator"""
    from services.factory_cell_orchestrator import get_factory_orchestrator
    return get_factory_orchestrator()


def run_async(coro):
    """Run async function in sync context"""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


# =============================================================================
# Cell Status & Control
# =============================================================================

@factory_cell_bp.route('/status', methods=['GET'])
def get_cell_status():
    """
    Get current factory cell status

    Returns comprehensive status including:
    - Cell state (idle, running, paused, error)
    - Active job and part information
    - Robot and CNC states
    - Pallet occupancy
    - Performance metrics

    Returns:
        200: Cell status
    """
    try:
        orchestrator = get_factory_orchestrator()
        status = orchestrator.get_cell_status()

        return jsonify({
            "state": status.state.value,
            "active_job": status.active_job,
            "current_part": status.current_part,
            "current_stage": (
                status.current_stage.value if status.current_stage else None
            ),
            "robots": {
                "ned2": {
                    "state": status.ned2_state,
                    "zone": status.ned2_zone.value if status.ned2_zone else None
                },
                "xarm": {
                    "state": status.xarm_state,
                    "zone": status.xarm_zone.value if status.xarm_zone else None
                }
            },
            "cnc": {
                "state": status.cnc_state,
                "position": status.cnc_position,
                "spindle_rpm": status.cnc_spindle_rpm,
                "program_progress": status.cnc_program_progress
            },
            "pallets": {
                "input": {
                    "occupied_slots": status.input_slots_occupied,
                    "available_slots": 6 - len(status.input_slots_occupied)
                },
                "output": {
                    "occupied_slots": status.output_slots_occupied,
                    "available_slots": 6 - len(status.output_slots_occupied)
                },
                "reject": {
                    "occupied_slots": status.reject_slots_occupied,
                    "available_slots": 3 - len(status.reject_slots_occupied)
                }
            },
            "metrics": {
                "parts_completed": status.parts_completed,
                "parts_rejected": status.parts_rejected,
                "uptime_seconds": status.uptime_seconds,
                "oee_percentage": status.oee_percentage
            },
            "sensors": status.sensor_readings,
            "timestamp": status.timestamp.isoformat()
        }), 200

    except Exception as e:
        current_app.logger.error(f"Get status error: {e}")
        return jsonify({"error": str(e)}), 500


@factory_cell_bp.route('/start', methods=['POST'])
def start_production():
    """
    Start production from job queue

    Begins processing queued jobs automatically.

    Returns:
        200: Production started
        409: Already running
    """
    try:
        orchestrator = get_factory_orchestrator()

        from services.factory_cell_orchestrator import CellState
        if orchestrator.state == CellState.RUNNING:
            return jsonify({
                "error": "Cell is already running",
                "state": orchestrator.state.value
            }), 409

        # Start in background task
        asyncio.ensure_future(orchestrator.start_production())

        return jsonify({
            "status": "started",
            "jobs_queued": len(orchestrator.job_queue)
        }), 200

    except Exception as e:
        current_app.logger.error(f"Start production error: {e}")
        return jsonify({"error": str(e)}), 500


@factory_cell_bp.route('/stop', methods=['POST'])
def stop_production():
    """
    Stop production

    Stops after current part completes. Does not abort mid-cycle.

    Returns:
        200: Production stopping
    """
    try:
        orchestrator = get_factory_orchestrator()

        from services.factory_cell_orchestrator import CellState
        orchestrator.state = CellState.IDLE

        return jsonify({
            "status": "stopping",
            "message": "Will stop after current cycle completes"
        }), 200

    except Exception as e:
        current_app.logger.error(f"Stop production error: {e}")
        return jsonify({"error": str(e)}), 500


@factory_cell_bp.route('/pause', methods=['POST'])
def pause_production():
    """
    Pause production

    Pauses after current operation. Can be resumed.

    Returns:
        200: Production paused
    """
    try:
        orchestrator = get_factory_orchestrator()

        from services.factory_cell_orchestrator import CellState
        orchestrator.state = CellState.PAUSED

        return jsonify({
            "status": "paused",
            "active_part": (
                orchestrator.active_part.part_id
                if orchestrator.active_part else None
            )
        }), 200

    except Exception as e:
        current_app.logger.error(f"Pause production error: {e}")
        return jsonify({"error": str(e)}), 500


@factory_cell_bp.route('/resume', methods=['POST'])
def resume_production():
    """
    Resume paused production

    Returns:
        200: Production resumed
        400: Not paused
    """
    try:
        orchestrator = get_factory_orchestrator()

        from services.factory_cell_orchestrator import CellState
        if orchestrator.state != CellState.PAUSED:
            return jsonify({
                "error": "Cell is not paused",
                "state": orchestrator.state.value
            }), 400

        orchestrator.state = CellState.RUNNING

        return jsonify({"status": "resumed"}), 200

    except Exception as e:
        current_app.logger.error(f"Resume production error: {e}")
        return jsonify({"error": str(e)}), 500


@factory_cell_bp.route('/emergency-stop', methods=['POST'])
def emergency_stop():
    """
    Emergency stop all cell equipment

    Immediately stops all robots and CNC machine.

    Returns:
        200: Emergency stop activated
    """
    try:
        orchestrator = get_factory_orchestrator()

        from services.factory_cell_orchestrator import CellState
        orchestrator.state = CellState.EMERGENCY_STOP

        # Stop all robots
        if orchestrator.robot_service:
            run_async(
                orchestrator.robot_service.stop_robot(
                    orchestrator.config.load_robot_id
                )
            )
            run_async(
                orchestrator.robot_service.stop_robot(
                    orchestrator.config.unload_robot_id
                )
            )

        # Stop CNC
        if orchestrator.cnc_controller:
            run_async(orchestrator.cnc_controller.feed_hold())

        return jsonify({
            "status": "emergency_stop",
            "message": "All equipment stopped"
        }), 200

    except Exception as e:
        current_app.logger.error(f"Emergency stop error: {e}")
        return jsonify({"error": str(e)}), 500


# =============================================================================
# Job Queue Management
# =============================================================================

@factory_cell_bp.route('/jobs', methods=['GET'])
def list_jobs():
    """
    List all jobs in queue

    Returns:
        200: List of queued jobs
    """
    try:
        orchestrator = get_factory_orchestrator()

        jobs = []
        for job in orchestrator.job_queue:
            jobs.append({
                "job_id": job.job_id,
                "nc_program": job.nc_program,
                "quantity": job.quantity,
                "material": job.material,
                "stock_dimensions": job.stock_dimensions,
                "created_at": job.created_at.isoformat(),
                "status": "queued"
            })

        # Add active job
        if orchestrator.active_job:
            jobs.insert(0, {
                "job_id": orchestrator.active_job.job_id,
                "nc_program": orchestrator.active_job.nc_program,
                "quantity": orchestrator.active_job.quantity,
                "material": orchestrator.active_job.material,
                "stock_dimensions": orchestrator.active_job.stock_dimensions,
                "created_at": orchestrator.active_job.created_at.isoformat(),
                "started_at": (
                    orchestrator.active_job.started_at.isoformat()
                    if orchestrator.active_job.started_at else None
                ),
                "completed_count": orchestrator.active_job.completed_count,
                "rejected_count": orchestrator.active_job.rejected_count,
                "status": "running"
            })

        return jsonify({"jobs": jobs}), 200

    except Exception as e:
        current_app.logger.error(f"List jobs error: {e}")
        return jsonify({"error": str(e)}), 500


@factory_cell_bp.route('/jobs', methods=['POST'])
def queue_job():
    """
    Queue a new manufacturing job

    Request Body:
        job_id: str - Unique job identifier
        nc_program: str - Path to NC program file
        quantity: int - Number of parts to produce
        material: str - Material type (default: aluminum_6061)
        stock_dimensions: dict - Raw stock size {x, y, z} in mm

    Returns:
        201: Job queued successfully
        400: Invalid request
    """
    data = request.get_json()
    if not data:
        return jsonify({"error": "Request body required"}), 400

    job_id = data.get('job_id')
    nc_program = data.get('nc_program')
    quantity = data.get('quantity', 1)

    if not job_id or not nc_program:
        return jsonify({
            "error": "job_id and nc_program are required"
        }), 400

    try:
        orchestrator = get_factory_orchestrator()

        job = orchestrator.queue_job(
            job_id=job_id,
            nc_program=nc_program,
            quantity=quantity,
            material=data.get('material', 'aluminum_6061'),
            stock_dimensions=data.get('stock_dimensions')
        )

        return jsonify({
            "status": "queued",
            "job_id": job.job_id,
            "quantity": job.quantity,
            "parts": [p.part_id for p in job.parts],
            "queue_position": len(orchestrator.job_queue)
        }), 201

    except Exception as e:
        current_app.logger.error(f"Queue job error: {e}")
        return jsonify({"error": str(e)}), 500


@factory_cell_bp.route('/jobs/<job_id>', methods=['GET'])
def get_job(job_id: str):
    """
    Get job details

    Path Parameters:
        job_id: Job identifier

    Returns:
        200: Job details
        404: Job not found
    """
    try:
        orchestrator = get_factory_orchestrator()

        # Check active job
        if orchestrator.active_job and orchestrator.active_job.job_id == job_id:
            job = orchestrator.active_job
        else:
            # Check queue
            job = None
            for queued in orchestrator.job_queue:
                if queued.job_id == job_id:
                    job = queued
                    break

        if not job:
            return jsonify({"error": f"Job '{job_id}' not found"}), 404

        return jsonify({
            "job_id": job.job_id,
            "nc_program": job.nc_program,
            "quantity": job.quantity,
            "material": job.material,
            "stock_dimensions": job.stock_dimensions,
            "created_at": job.created_at.isoformat(),
            "started_at": (
                job.started_at.isoformat() if job.started_at else None
            ),
            "completed_at": (
                job.completed_at.isoformat() if job.completed_at else None
            ),
            "completed_count": job.completed_count,
            "rejected_count": job.rejected_count,
            "parts": [
                {
                    "part_id": p.part_id,
                    "stage": p.current_stage.value,
                    "cycle_time": p.cycle_time,
                    "inspection_result": p.inspection_result
                }
                for p in job.parts
            ]
        }), 200

    except Exception as e:
        current_app.logger.error(f"Get job error: {e}")
        return jsonify({"error": str(e)}), 500


@factory_cell_bp.route('/jobs/<job_id>', methods=['DELETE'])
def cancel_job(job_id: str):
    """
    Cancel a queued job

    Cannot cancel running job. Use /stop instead.

    Path Parameters:
        job_id: Job identifier

    Returns:
        200: Job cancelled
        400: Cannot cancel active job
        404: Job not found
    """
    try:
        orchestrator = get_factory_orchestrator()

        if orchestrator.active_job and orchestrator.active_job.job_id == job_id:
            return jsonify({
                "error": "Cannot cancel active job. Use /stop endpoint."
            }), 400

        # Find and remove from queue
        for i, job in enumerate(orchestrator.job_queue):
            if job.job_id == job_id:
                orchestrator.job_queue.remove(job)
                return jsonify({
                    "status": "cancelled",
                    "job_id": job_id
                }), 200

        return jsonify({"error": f"Job '{job_id}' not found"}), 404

    except Exception as e:
        current_app.logger.error(f"Cancel job error: {e}")
        return jsonify({"error": str(e)}), 500


# =============================================================================
# Pallet Management
# =============================================================================

@factory_cell_bp.route('/pallets', methods=['GET'])
def get_pallets():
    """
    Get pallet status

    Returns occupancy of input, output, and reject pallets.

    Returns:
        200: Pallet status
    """
    try:
        orchestrator = get_factory_orchestrator()

        def pallet_to_dict(pallet, pallet_type):
            return {
                "type": pallet_type,
                "slots": [
                    {
                        "slot_id": s.slot_id,
                        "is_occupied": s.is_occupied,
                        "part_id": s.part_id,
                        "material": s.material
                    }
                    for s in pallet
                ],
                "total_slots": len(pallet),
                "occupied_count": sum(1 for s in pallet if s.is_occupied)
            }

        return jsonify({
            "pallets": {
                "input": pallet_to_dict(orchestrator.input_pallet, "input"),
                "output": pallet_to_dict(orchestrator.output_pallet, "output"),
                "reject": pallet_to_dict(orchestrator.reject_pallet, "reject")
            }
        }), 200

    except Exception as e:
        current_app.logger.error(f"Get pallets error: {e}")
        return jsonify({"error": str(e)}), 500


@factory_cell_bp.route('/pallets/input/load', methods=['POST'])
def load_input_pallet():
    """
    Load raw stock into input pallet

    Request Body:
        slots: list[dict] - Slots to load with part info
            - slot_id: int
            - material: str
            - dimensions: dict {x, y, z}

    Returns:
        200: Slots loaded
    """
    data = request.get_json()
    if not data:
        return jsonify({"error": "Request body required"}), 400

    slots = data.get('slots', [])

    try:
        orchestrator = get_factory_orchestrator()

        for slot_data in slots:
            slot_id = slot_data.get('slot_id')
            if 0 <= slot_id < len(orchestrator.input_pallet):
                slot = orchestrator.input_pallet[slot_id]
                slot.is_occupied = True
                slot.material = slot_data.get('material', 'aluminum_6061')
                slot.dimensions = slot_data.get('dimensions', {
                    "x": 50, "y": 50, "z": 25
                })

        loaded = [s['slot_id'] for s in slots]

        return jsonify({
            "status": "loaded",
            "slots_loaded": loaded
        }), 200

    except Exception as e:
        current_app.logger.error(f"Load pallet error: {e}")
        return jsonify({"error": str(e)}), 500


@factory_cell_bp.route('/pallets/output/unload', methods=['POST'])
def unload_output_pallet():
    """
    Unload finished parts from output pallet

    Request Body:
        slots: list[int] - Slot IDs to unload (or empty for all)

    Returns:
        200: Slots unloaded with part IDs
    """
    data = request.get_json() or {}
    slots = data.get('slots', None)

    try:
        orchestrator = get_factory_orchestrator()

        unloaded = []
        for slot in orchestrator.output_pallet:
            if slot.is_occupied:
                if slots is None or slot.slot_id in slots:
                    unloaded.append({
                        "slot_id": slot.slot_id,
                        "part_id": slot.part_id
                    })
                    slot.is_occupied = False
                    slot.part_id = None

        return jsonify({
            "status": "unloaded",
            "parts": unloaded
        }), 200

    except Exception as e:
        current_app.logger.error(f"Unload pallet error: {e}")
        return jsonify({"error": str(e)}), 500


# =============================================================================
# Pick-and-Place Workflow
# =============================================================================

@factory_cell_bp.route('/workflow/pick-place', methods=['POST'])
def execute_pick_place():
    """
    Execute a pick-and-place operation

    Manual control for testing and calibration.

    Request Body:
        robot_id: str - Robot to use (ned2-001 or xarm-001)
        operation: str - "pick" or "place"
        location: str - Location identifier
        approach_height: float - Height above location (mm)

    Returns:
        200: Operation completed
    """
    data = request.get_json()
    if not data:
        return jsonify({"error": "Request body required"}), 400

    robot_id = data.get('robot_id')
    operation = data.get('operation')
    location = data.get('location')

    if not all([robot_id, operation, location]):
        return jsonify({
            "error": "robot_id, operation, and location required"
        }), 400

    try:
        orchestrator = get_factory_orchestrator()

        if not orchestrator.robot_service:
            return jsonify({
                "status": "simulated",
                "message": "Robot service not connected, simulation only"
            }), 200

        # Parse location to coordinates
        x, y, z = _parse_location(location)
        approach_height = data.get('approach_height', 50)

        if operation == "pick":
            # Approach
            run_async(orchestrator.robot_service.move_robot_to_pose(
                robot_id, x=x, y=y, z=z + approach_height,
                roll=0, pitch=3.14159, yaw=0
            ))
            # Descend
            run_async(orchestrator.robot_service.move_robot_to_pose(
                robot_id, x=x, y=y, z=z,
                roll=0, pitch=3.14159, yaw=0
            ))
            # Grasp
            run_async(orchestrator.robot_service.gripper_grasp(
                robot_id, force=50
            ))
            # Retract
            run_async(orchestrator.robot_service.move_robot_to_pose(
                robot_id, x=x, y=y, z=z + approach_height,
                roll=0, pitch=3.14159, yaw=0
            ))

        elif operation == "place":
            # Approach
            run_async(orchestrator.robot_service.move_robot_to_pose(
                robot_id, x=x, y=y, z=z + approach_height,
                roll=0, pitch=3.14159, yaw=0
            ))
            # Descend
            run_async(orchestrator.robot_service.move_robot_to_pose(
                robot_id, x=x, y=y, z=z,
                roll=0, pitch=3.14159, yaw=0
            ))
            # Release
            run_async(orchestrator.robot_service.gripper_release(robot_id))
            # Retract
            run_async(orchestrator.robot_service.move_robot_to_pose(
                robot_id, x=x, y=y, z=z + approach_height,
                roll=0, pitch=3.14159, yaw=0
            ))

        return jsonify({
            "status": "completed",
            "robot_id": robot_id,
            "operation": operation,
            "location": location
        }), 200

    except Exception as e:
        current_app.logger.error(f"Pick-place error: {e}")
        return jsonify({"error": str(e)}), 500


@factory_cell_bp.route('/workflow/cycle/single', methods=['POST'])
def run_single_cycle():
    """
    Run a single part manufacturing cycle

    Useful for testing and demonstration.

    Request Body:
        nc_program: str - NC program to run
        input_slot: int - Input pallet slot (0-5)

    Returns:
        200: Cycle completed
        400: Invalid request
    """
    data = request.get_json()
    if not data:
        return jsonify({"error": "Request body required"}), 400

    nc_program = data.get('nc_program', 'test_program.nc')
    input_slot = data.get('input_slot', 0)

    try:
        orchestrator = get_factory_orchestrator()

        # Queue single-part job
        job = orchestrator.queue_job(
            job_id=f"single_cycle_{int(asyncio.get_event_loop().time())}",
            nc_program=nc_program,
            quantity=1
        )

        # Set input slot
        job.parts[0].raw_stock_slot = input_slot

        # Execute
        run_async(orchestrator._execute_part_cycle(job.parts[0]))

        return jsonify({
            "status": "completed",
            "part_id": job.parts[0].part_id,
            "stage": job.parts[0].current_stage.value,
            "cycle_time": job.parts[0].cycle_time,
            "inspection_result": job.parts[0].inspection_result
        }), 200

    except Exception as e:
        current_app.logger.error(f"Single cycle error: {e}")
        return jsonify({"error": str(e)}), 500


# =============================================================================
# Collision Zone Management
# =============================================================================

@factory_cell_bp.route('/zones', methods=['GET'])
def get_zone_status():
    """
    Get collision zone status

    Returns:
        200: Zone occupancy status
    """
    try:
        orchestrator = get_factory_orchestrator()
        zones = orchestrator.zone_manager.get_zone_status()

        return jsonify({"zones": zones}), 200

    except Exception as e:
        current_app.logger.error(f"Get zones error: {e}")
        return jsonify({"error": str(e)}), 500


# =============================================================================
# Configuration
# =============================================================================

@factory_cell_bp.route('/config', methods=['GET'])
def get_cell_config():
    """
    Get factory cell configuration

    Returns:
        200: Cell configuration
    """
    try:
        orchestrator = get_factory_orchestrator()
        config = orchestrator.config

        return jsonify({
            "cnc": {
                "id": config.cnc_id,
                "type": config.cnc_type
            },
            "robots": {
                "load": {
                    "id": config.load_robot_id,
                    "type": config.load_robot_type,
                    "position": config.load_robot_position
                },
                "unload": {
                    "id": config.unload_robot_id,
                    "type": config.unload_robot_type,
                    "position": config.unload_robot_position
                }
            },
            "pallets": {
                "input_slots": config.input_pallet_slots,
                "output_slots": config.output_pallet_slots,
                "reject_slots": config.reject_pallet_slots
            },
            "timing": {
                "pick_time": config.pick_time,
                "place_time": config.place_time,
                "fixture_time": config.fixture_time,
                "inspection_time": config.inspection_time
            },
            "shared_zone_bounds": config.shared_zone_bounds
        }), 200

    except Exception as e:
        current_app.logger.error(f"Get config error: {e}")
        return jsonify({"error": str(e)}), 500


# =============================================================================
# Helper Functions
# =============================================================================

def _parse_location(location: str) -> tuple:
    """Parse location string to (x, y, z) coordinates"""
    # Predefined locations
    locations = {
        "input_pallet:slot_0": (-600, 0, 100),
        "input_pallet:slot_1": (-540, 0, 100),
        "input_pallet:slot_2": (-480, 0, 100),
        "input_pallet:slot_3": (-600, 60, 100),
        "input_pallet:slot_4": (-540, 60, 100),
        "input_pallet:slot_5": (-480, 60, 100),
        "cnc_fixture": (0, 0, 80),
        "inspection_station": (400, -300, 50),
        "output_pallet:slot_0": (600, 0, 100),
        "output_pallet:slot_1": (660, 0, 100),
        "output_pallet:slot_2": (720, 0, 100),
        "output_pallet:slot_3": (600, 60, 100),
        "output_pallet:slot_4": (660, 60, 100),
        "output_pallet:slot_5": (720, 60, 100),
        "reject_pallet:slot_0": (600, -200, 100),
        "reject_pallet:slot_1": (660, -200, 100),
        "reject_pallet:slot_2": (720, -200, 100),
    }

    if location in locations:
        return locations[location]

    # Default to origin
    return (0, 0, 100)
