"""
Unity Digital Twin API Routes
===============================
ISO 23247 compliant REST API for Unity digital twin visualization.

Provides endpoints for:
- Machine geometry (STEP AP242 → glTF conversion)
- Real-time render state (ISO 23247-3 digital representation)
- Toolpath data (STEP-NC)
- AAS integration
- Kinematics configuration

Standards:
- ISO 23247 Digital Twin Framework for Manufacturing
- ISO 10303 AP242 (STEP) for geometry
- ISO 14649 (STEP-NC) for toolpaths
- IEC 63278 (Asset Administration Shell)

Author: Flask CNC SCADA System
"""

import os
import time
import logging
from typing import Dict, Any, Optional, List
from flask import Blueprint, request, jsonify, Response, current_app, send_file
from dataclasses import asdict

logger = logging.getLogger(__name__)

bp = Blueprint('unity', __name__, url_prefix='/api/unity')


# =============================================================================
# Service Accessors (Lazy Imports)
# =============================================================================

def _get_aas_service():
    """Get AAS service (lazy import)."""
    from services.aas_service import get_aas_service
    return get_aas_service()


def _get_step_parser_service():
    """Get STEP parser service (lazy import)."""
    try:
        from services.step_parser_service import get_step_parser_service
        return get_step_parser_service()
    except ImportError:
        logger.warning("STEP parser service not available")
        return None


def _get_step_nc_service():
    """Get STEP-NC service (lazy import)."""
    try:
        from services.step_nc_service import get_step_nc_service
        return get_step_nc_service()
    except ImportError:
        logger.warning("STEP-NC service not available")
        return None


def _get_digital_twin_service():
    """Get digital twin service (lazy import)."""
    try:
        from services.digital_twin import DigitalTwinService
        return DigitalTwinService()
    except ImportError:
        logger.warning("Digital twin service not available")
        return None


def _get_unity_state_service():
    """Get Unity state service (lazy import)."""
    try:
        from services.unity_state_service import get_unity_state_service
        return get_unity_state_service()
    except ImportError:
        logger.warning("Unity state service not available")
        return None


# =============================================================================
# Configuration & Discovery Endpoints
# =============================================================================

@bp.route('/config/<machine_id>', methods=['GET'])
def get_unity_config(machine_id: str):
    """
    Get Unity digital twin configuration for a machine.

    Returns all endpoints, kinematics, and visualization settings
    from the AAS DigitalTwinVisualization submodel.

    Response:
        {
            "machine_id": "mill-01",
            "aas_id": "urn:scada:aas:mill-01",
            "endpoints": {
                "GeometryURI": "/api/unity/geometry/mill-01",
                "RenderStateURI": "/api/unity/state/mill-01",
                "ToolpathURI": "/api/unity/toolpath/mill-01",
                "WebSocketURI": "/socket.io/?room=unity:mill-01"
            },
            "kinematics": {...},
            "visualization": {...},
            "sensor_overlay": {...}
        }
    """
    aas_service = _get_aas_service()
    config = aas_service.get_unity_config(machine_id)

    if not config:
        # Check if AAS exists but doesn't have Unity submodel
        aas_id = f"urn:scada:aas:{machine_id}"
        shell = aas_service.get_shell(aas_id)

        if shell:
            return jsonify({
                "error": "Unity submodel not configured",
                "message": f"AAS exists but DigitalTwinVisualization submodel not found. "
                          f"Use POST /api/unity/config/{machine_id} to add it.",
                "aas_id": aas_id
            }), 404
        else:
            return jsonify({
                "error": "Not Found",
                "message": f"No AAS found for machine: {machine_id}"
            }), 404

    return jsonify(config)


@bp.route('/config/<machine_id>', methods=['POST'])
def add_unity_config(machine_id: str):
    """
    Add Unity Digital Twin submodel to existing AAS.

    Request body (all optional):
        {
            "geometry_format": "glTF",
            "update_rate_hz": 30,
            "step_file_path": "/path/to/machine.step",
            "step_nc_file_path": "/path/to/program.stepnc",
            "axes": ["X", "Y", "Z", "A"]
        }

    Response:
        {
            "message": "Unity submodel added",
            "submodel_id": "urn:scada:submodel:mill-01:unity_visualization"
        }
    """
    data = request.get_json() or {}

    aas_service = _get_aas_service()

    submodel = aas_service.add_unity_submodel(
        machine_id=machine_id,
        geometry_format=data.get('geometry_format', 'glTF'),
        update_rate_hz=data.get('update_rate_hz', 30),
        step_file_path=data.get('step_file_path'),
        step_nc_file_path=data.get('step_nc_file_path'),
        axes=data.get('axes')
    )

    if not submodel:
        return jsonify({
            "error": "Not Found",
            "message": f"No AAS found for machine: {machine_id}. "
                      f"Create AAS first with POST /api/aas/shells"
        }), 404

    return jsonify({
        "message": "Unity submodel added",
        "submodel_id": submodel.id
    }), 201


@bp.route('/machines', methods=['GET'])
def list_unity_machines():
    """
    List all machines with Unity digital twin capability.

    Response:
        {
            "machines": [
                {
                    "machine_id": "mill-01",
                    "has_unity": true,
                    "has_geometry": true,
                    "has_toolpath": false,
                    "config_url": "/api/unity/config/mill-01"
                }
            ],
            "count": 1
        }
    """
    aas_service = _get_aas_service()
    shells = aas_service.get_all_shells()

    machines = []
    for shell in shells:
        machine_id = shell.id_short
        unity_sm = shell.get_submodel("DigitalTwinVisualization")

        machine_info = {
            "machine_id": machine_id,
            "aas_id": shell.id,
            "has_unity": unity_sm is not None,
            "has_geometry": False,
            "has_toolpath": False,
            "config_url": f"/api/unity/config/{machine_id}"
        }

        if unity_sm:
            for elem in unity_sm.submodel_elements:
                if hasattr(elem, 'id_short'):
                    if elem.id_short == "STEPFilePath" and elem.value:
                        machine_info["has_geometry"] = os.path.exists(elem.value)
                    elif elem.id_short == "STEPNCFilePath" and elem.value:
                        machine_info["has_toolpath"] = os.path.exists(elem.value)

        machines.append(machine_info)

    return jsonify({
        "machines": machines,
        "count": len(machines)
    })


# =============================================================================
# Geometry Endpoints (ISO 10303 AP242 / STEP)
# =============================================================================

@bp.route('/geometry/<machine_id>', methods=['GET'])
def get_geometry(machine_id: str):
    """
    Get machine geometry in Unity-compatible format.

    Query params:
        - format: Output format (gltf, json). Default: json
        - include_pmi: Include PMI annotations. Default: true
        - include_kinematics: Include kinematic chain. Default: true

    Response (JSON format):
        {
            "machine_id": "mill-01",
            "format": "json",
            "geometry": {
                "vertices": [...],
                "faces": [...],
                "normals": [...]
            },
            "pmi_annotations": [...],
            "kinematic_chain": [...],
            "bounding_box": {...}
        }
    """
    output_format = request.args.get('format', 'json')
    include_pmi = request.args.get('include_pmi', 'true').lower() == 'true'
    include_kinematics = request.args.get('include_kinematics', 'true').lower() == 'true'

    # Get STEP file path from AAS
    aas_service = _get_aas_service()
    config = aas_service.get_unity_config(machine_id)

    step_file_path = None
    if config:
        for key, value in config.get('endpoints', {}).items():
            pass  # endpoints don't contain file path

    # Try to find STEP file
    step_parser = _get_step_parser_service()

    if step_parser:
        # Check if there's a configured STEP file
        aas_id = f"urn:scada:aas:{machine_id}"
        shell = aas_service.get_shell(aas_id)

        if shell:
            unity_sm = shell.get_submodel("DigitalTwinVisualization")
            if unity_sm:
                for elem in unity_sm.submodel_elements:
                    if hasattr(elem, 'id_short') and elem.id_short == "STEPFilePath":
                        step_file_path = elem.value

        if step_file_path and os.path.exists(step_file_path):
            # Parse actual STEP file
            model = step_parser.parse_step_file(step_file_path)

            response = {
                "machine_id": machine_id,
                "format": output_format,
                "source": "step_file",
                "step_file": step_file_path,
                "model_info": asdict(model) if hasattr(model, '__dataclass_fields__') else model
            }

            if include_pmi:
                pmi = step_parser.extract_pmi(model)
                response["pmi_annotations"] = [asdict(p) for p in pmi]

            if include_kinematics:
                kinematics = step_parser.get_kinematic_chain(model)
                response["kinematic_chain"] = kinematics

            if output_format == 'gltf':
                unity_geom = step_parser.export_to_unity_format(model, 'gltf')
                response["gltf_data"] = asdict(unity_geom) if hasattr(unity_geom, '__dataclass_fields__') else unity_geom

            return jsonify(response)

    # Return mock geometry for development
    return jsonify({
        "machine_id": machine_id,
        "format": output_format,
        "source": "mock",
        "note": "No STEP file configured. Returning mock geometry.",
        "geometry": {
            "type": "CNCMill",
            "bounds": {
                "min": {"x": -500, "y": -500, "z": 0},
                "max": {"x": 500, "y": 500, "z": 400}
            },
            "components": [
                {"name": "base", "type": "box", "dimensions": [1000, 1000, 100]},
                {"name": "column", "type": "box", "dimensions": [200, 200, 600]},
                {"name": "spindle_head", "type": "cylinder", "radius": 50, "height": 150},
                {"name": "table", "type": "box", "dimensions": [600, 400, 50]}
            ]
        },
        "kinematic_chain": [
            {"name": "X_Axis", "type": "prismatic", "axis": [1, 0, 0], "limits": [-500, 500]},
            {"name": "Y_Axis", "type": "prismatic", "axis": [0, 1, 0], "limits": [-500, 500]},
            {"name": "Z_Axis", "type": "prismatic", "axis": [0, 0, 1], "limits": [0, 400]}
        ],
        "pmi_annotations": [] if not include_pmi else [
            {"id": "pmi_1", "type": "dimension", "value": "500mm", "position": [250, 0, 50]}
        ]
    })


@bp.route('/geometry/<machine_id>/gltf', methods=['GET'])
def get_geometry_gltf(machine_id: str):
    """
    Get machine geometry as glTF file (for Unity import).

    Response: Binary glTF (.glb) or JSON glTF (.gltf)
    """
    step_parser = _get_step_parser_service()

    if not step_parser:
        return jsonify({
            "error": "Service Unavailable",
            "message": "STEP parser service not available"
        }), 503

    # Get STEP file path from AAS
    aas_service = _get_aas_service()
    aas_id = f"urn:scada:aas:{machine_id}"
    shell = aas_service.get_shell(aas_id)

    if not shell:
        return jsonify({
            "error": "Not Found",
            "message": f"No AAS found for machine: {machine_id}"
        }), 404

    unity_sm = shell.get_submodel("DigitalTwinVisualization")
    step_file_path = None

    if unity_sm:
        for elem in unity_sm.submodel_elements:
            if hasattr(elem, 'id_short') and elem.id_short == "STEPFilePath":
                step_file_path = elem.value

    if not step_file_path or not os.path.exists(step_file_path):
        return jsonify({
            "error": "Not Found",
            "message": "No STEP file configured for this machine"
        }), 404

    # Parse and convert
    model = step_parser.parse_step_file(step_file_path)
    unity_geom = step_parser.export_to_unity_format(model, 'gltf')

    # Return as JSON glTF
    return jsonify(asdict(unity_geom) if hasattr(unity_geom, '__dataclass_fields__') else unity_geom)


# =============================================================================
# Real-time State Endpoints (ISO 23247-3 Digital Representation)
# =============================================================================

@bp.route('/state/<machine_id>', methods=['GET'])
def get_render_state(machine_id: str):
    """
    Get current render state for Unity visualization.

    This is the ISO 23247-3 compliant digital representation
    optimized for real-time Unity rendering.

    Response:
        {
            "ome_id": "mill-01",
            "ome_type": "equipment",
            "timestamp": 1703789456.789,
            "operational_state": {
                "execution": "ACTIVE",
                "mode": "AUTOMATIC",
                "program": "part001.nc",
                "line_number": 42,
                "feed_override": 100.0,
                "spindle_override": 100.0
            },
            "position": {
                "x": 125.5,
                "y": 80.2,
                "z": -15.0
            },
            "kinematics": {
                "axes": {...},
                "tool": {...},
                "spindle": {...}
            },
            "quality_score": 0.98
        }
    """
    unity_state_service = _get_unity_state_service()

    if unity_state_service:
        state = unity_state_service.get_render_state(machine_id)
        if state:
            return jsonify(asdict(state) if hasattr(state, '__dataclass_fields__') else state)

    # Fallback to AAS operational data
    aas_service = _get_aas_service()
    aas_id = f"urn:scada:aas:{machine_id}"
    shell = aas_service.get_shell(aas_id)

    if not shell:
        return jsonify({
            "error": "Not Found",
            "message": f"No AAS found for machine: {machine_id}"
        }), 404

    # Build state from AAS operational data
    op_data = shell.get_submodel("OperationalData")

    state = {
        "ome_id": machine_id,
        "ome_type": "equipment",
        "timestamp": time.time(),
        "operational_state": {
            "execution": "UNKNOWN",
            "mode": "UNKNOWN",
            "program": None,
            "line_number": 0,
            "feed_override": 100.0,
            "spindle_override": 100.0
        },
        "position": {"x": 0.0, "y": 0.0, "z": 0.0},
        "kinematics": {
            "axes": {},
            "tool": {"number": 1, "length": 50.0, "diameter": 6.0},
            "spindle": {"speed": 0.0, "direction": "CW", "load": 0.0}
        },
        "quality_score": 1.0
    }

    if op_data:
        for elem in op_data.submodel_elements:
            if hasattr(elem, 'id_short'):
                if elem.id_short == "MachineState":
                    state["operational_state"]["execution"] = elem.value
                elif elem.id_short == "FeedRate":
                    state["kinematics"]["axes"]["feed_rate"] = float(elem.value or 0)
                elif elem.id_short == "SpindleSpeed":
                    state["kinematics"]["spindle"]["speed"] = float(elem.value or 0)
                elif elem.id_short == "CurrentLine":
                    state["operational_state"]["line_number"] = int(elem.value or 0)
                elif hasattr(elem, 'elements'):  # SubmodelElementCollection
                    if elem.id_short == "Position":
                        for prop in elem.elements:
                            if prop.id_short in ["X", "Y", "Z"]:
                                state["position"][prop.id_short.lower()] = float(prop.value or 0)

    return jsonify(state)


@bp.route('/iso23247/<machine_id>', methods=['GET'])
def get_iso23247_representation(machine_id: str):
    """
    Get full ISO 23247-3 compliant digital representation.

    This includes complete metadata, lineage, and AAS references.
    Use /state for lightweight real-time updates.

    Response:
        {
            "ome_id": "mill-01",
            "ome_type": "equipment",
            "timestamp": 1703789456.789,
            "geometry_ref": "/api/unity/geometry/mill-01",
            "operational_state": {...},
            "position": {...},
            "kinematics": {...},
            "identification": {...},
            "technical_data": {...},
            "lineage": {...},
            "quality_score": 0.98
        }
    """
    aas_service = _get_aas_service()
    aas_id = f"urn:scada:aas:{machine_id}"
    shell = aas_service.get_shell(aas_id)

    if not shell:
        return jsonify({
            "error": "Not Found",
            "message": f"No AAS found for machine: {machine_id}"
        }), 404

    # Build complete ISO 23247 representation
    representation = {
        "ome_id": machine_id,
        "ome_type": "equipment",
        "timestamp": time.time(),
        "geometry_ref": f"/api/unity/geometry/{machine_id}",
        "operational_state": {},
        "position": {"x": 0.0, "y": 0.0, "z": 0.0},
        "kinematics": {},
        "identification": {},
        "technical_data": {},
        "lineage": {
            "source": "aas",
            "aas_id": aas_id,
            "created_at": time.time()
        },
        "quality_score": 1.0
    }

    # Extract data from submodels
    for submodel in shell.submodels:
        if submodel.id_short == "Identification":
            for elem in submodel.submodel_elements:
                if hasattr(elem, 'id_short') and hasattr(elem, 'value'):
                    representation["identification"][elem.id_short] = elem.value

        elif submodel.id_short == "TechnicalData":
            for elem in submodel.submodel_elements:
                if hasattr(elem, 'id_short') and hasattr(elem, 'value'):
                    representation["technical_data"][elem.id_short] = elem.value

        elif submodel.id_short == "OperationalData":
            for elem in submodel.submodel_elements:
                if hasattr(elem, 'id_short'):
                    if hasattr(elem, 'value'):
                        representation["operational_state"][elem.id_short] = elem.value
                    elif hasattr(elem, 'elements'):
                        if elem.id_short == "Position":
                            for prop in elem.elements:
                                representation["position"][prop.id_short.lower()] = float(prop.value or 0)

        elif submodel.id_short == "DigitalTwinVisualization":
            kinematics_data = {}
            for elem in submodel.submodel_elements:
                if hasattr(elem, 'id_short') and elem.id_short == "Kinematics":
                    if hasattr(elem, 'elements'):
                        for sub_elem in elem.elements:
                            if hasattr(sub_elem, 'id_short'):
                                kinematics_data[sub_elem.id_short] = {}
                                if hasattr(sub_elem, 'elements'):
                                    for prop in sub_elem.elements:
                                        kinematics_data[sub_elem.id_short][prop.id_short] = prop.value
            representation["kinematics"] = kinematics_data

    return jsonify(representation)


# =============================================================================
# Toolpath Endpoints (ISO 14649 / STEP-NC)
# =============================================================================

@bp.route('/toolpath/<machine_id>', methods=['GET'])
def get_toolpath(machine_id: str):
    """
    Get toolpath data for Unity visualization.

    Query params:
        - format: Output format (unity, stepnc). Default: unity
        - program: Specific program name. Default: active program

    Response:
        {
            "machine_id": "mill-01",
            "program": "part001.nc",
            "format": "unity",
            "segments": [
                {
                    "type": "rapid",
                    "start": {"x": 0, "y": 0, "z": 50},
                    "end": {"x": 100, "y": 100, "z": 50},
                    "color": "#FF0000"
                },
                {
                    "type": "linear",
                    "start": {"x": 100, "y": 100, "z": 50},
                    "end": {"x": 100, "y": 100, "z": 0},
                    "feed_rate": 500,
                    "color": "#00FF00"
                }
            ],
            "bounds": {...},
            "total_length": 1234.5,
            "estimated_time": 180.0
        }
    """
    output_format = request.args.get('format', 'unity')
    program_name = request.args.get('program')

    step_nc_service = _get_step_nc_service()

    if step_nc_service:
        # Get STEP-NC file from AAS
        aas_service = _get_aas_service()
        aas_id = f"urn:scada:aas:{machine_id}"
        shell = aas_service.get_shell(aas_id)

        if shell:
            unity_sm = shell.get_submodel("DigitalTwinVisualization")
            step_nc_path = None

            if unity_sm:
                for elem in unity_sm.submodel_elements:
                    if hasattr(elem, 'id_short') and elem.id_short == "STEPNCFilePath":
                        step_nc_path = elem.value

            if step_nc_path and os.path.exists(step_nc_path):
                program = step_nc_service.parse_step_nc(step_nc_path)
                toolpath = step_nc_service.get_unity_toolpath(machine_id)

                return jsonify({
                    "machine_id": machine_id,
                    "program": program_name or step_nc_path,
                    "format": output_format,
                    "source": "step_nc",
                    "toolpath": asdict(toolpath) if hasattr(toolpath, '__dataclass_fields__') else toolpath
                })

    # Return mock toolpath for development
    return jsonify({
        "machine_id": machine_id,
        "program": program_name or "demo.nc",
        "format": output_format,
        "source": "mock",
        "note": "No STEP-NC file configured. Returning mock toolpath.",
        "segments": [
            {"type": "rapid", "start": {"x": 0, "y": 0, "z": 50}, "end": {"x": 50, "y": 50, "z": 50}, "color": "#FF0000"},
            {"type": "linear", "start": {"x": 50, "y": 50, "z": 50}, "end": {"x": 50, "y": 50, "z": 0}, "color": "#00FF00", "feed_rate": 500},
            {"type": "linear", "start": {"x": 50, "y": 50, "z": 0}, "end": {"x": 100, "y": 50, "z": 0}, "color": "#00FF00", "feed_rate": 1000},
            {"type": "arc", "start": {"x": 100, "y": 50, "z": 0}, "end": {"x": 100, "y": 100, "z": 0}, "center": {"x": 100, "y": 75, "z": 0}, "color": "#0000FF", "feed_rate": 800},
            {"type": "rapid", "start": {"x": 100, "y": 100, "z": 0}, "end": {"x": 0, "y": 0, "z": 50}, "color": "#FF0000"}
        ],
        "bounds": {
            "min": {"x": 0, "y": 0, "z": 0},
            "max": {"x": 100, "y": 100, "z": 50}
        },
        "total_length": 350.5,
        "estimated_time": 45.0
    })


@bp.route('/toolpath/<machine_id>/gcode', methods=['POST'])
def parse_gcode_to_toolpath(machine_id: str):
    """
    Parse G-code and return Unity-compatible toolpath.

    Request body:
        {
            "gcode": "G0 X0 Y0 Z50\\nG1 X100 Y100 F1000\\n..."
        }
        OR
        {
            "file_path": "/path/to/program.nc"
        }

    Response:
        {
            "machine_id": "mill-01",
            "segments": [...],
            "bounds": {...}
        }
    """
    data = request.get_json()
    if not data:
        return jsonify({"error": "Bad Request", "message": "JSON body required"}), 400

    step_nc_service = _get_step_nc_service()

    if not step_nc_service:
        return jsonify({
            "error": "Service Unavailable",
            "message": "STEP-NC service not available"
        }), 503

    gcode = data.get('gcode')
    file_path = data.get('file_path')

    if file_path and os.path.exists(file_path):
        with open(file_path, 'r') as f:
            gcode = f.read()

    if not gcode:
        return jsonify({"error": "Bad Request", "message": "gcode or file_path required"}), 400

    toolpath = step_nc_service.parse_gcode_to_toolpath(gcode)

    return jsonify({
        "machine_id": machine_id,
        "source": "gcode",
        "toolpath": asdict(toolpath) if hasattr(toolpath, '__dataclass_fields__') else toolpath
    })


# =============================================================================
# Sensor Overlay Endpoints
# =============================================================================

@bp.route('/sensors/<machine_id>', methods=['GET'])
def get_sensor_overlay(machine_id: str):
    """
    Get sensor data for Unity overlay visualization.

    Response:
        {
            "machine_id": "mill-01",
            "timestamp": 1703789456.789,
            "sensors": {
                "temperature": {
                    "spindle": 45.2,
                    "table": 32.1,
                    "ambient": 22.5
                },
                "vibration": {
                    "x": 0.02,
                    "y": 0.015,
                    "z": 0.03
                },
                "current": {
                    "spindle": 2.5,
                    "x_axis": 0.8,
                    "y_axis": 0.7,
                    "z_axis": 1.2
                }
            },
            "alerts": []
        }
    """
    unity_state_service = _get_unity_state_service()

    if unity_state_service:
        sensors = unity_state_service.get_sensor_overlay(machine_id)
        if sensors:
            return jsonify(sensors)

    # Return mock sensor data
    return jsonify({
        "machine_id": machine_id,
        "timestamp": time.time(),
        "source": "mock",
        "sensors": {
            "temperature": {
                "spindle": 42.5,
                "table": 28.3,
                "ambient": 23.1
            },
            "vibration": {
                "x": 0.018,
                "y": 0.012,
                "z": 0.025
            },
            "current": {
                "spindle": 2.1,
                "x_axis": 0.65,
                "y_axis": 0.58,
                "z_axis": 0.92
            }
        },
        "alerts": []
    })


# =============================================================================
# WebSocket Room Management
# =============================================================================

@bp.route('/subscribe/<machine_id>', methods=['POST'])
def subscribe_to_updates(machine_id: str):
    """
    Get WebSocket subscription info for real-time updates.

    Response:
        {
            "websocket_url": "/socket.io",
            "room": "unity:mill-01",
            "events": [
                "iso23247:state",
                "unity:position",
                "unity:toolpath_progress",
                "sensor:update"
            ]
        }
    """
    return jsonify({
        "websocket_url": "/socket.io",
        "room": f"unity:{machine_id}",
        "events": [
            "iso23247:state",
            "unity:position",
            "unity:kinematics",
            "unity:toolpath_progress",
            "unity:tool_change",
            "sensor:update",
            "sensor:alert",
            "machine:state_change"
        ],
        "subscribe_message": {
            "event": "join",
            "data": {"room": f"unity:{machine_id}"}
        }
    })


# =============================================================================
# Health & Debug
# =============================================================================

@bp.route('/health', methods=['GET'])
def health():
    """Health check for Unity API."""
    services = {
        "aas_service": _get_aas_service() is not None,
        "step_parser": _get_step_parser_service() is not None,
        "step_nc": _get_step_nc_service() is not None,
        "unity_state": _get_unity_state_service() is not None
    }

    all_healthy = all(services.values())

    return jsonify({
        "status": "healthy" if all_healthy else "degraded",
        "services": services,
        "timestamp": time.time()
    }), 200 if all_healthy else 503


# Alias for compatibility with app.py registration
unity_bp = bp
