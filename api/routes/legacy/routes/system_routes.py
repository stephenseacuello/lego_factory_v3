"""
System Routes Module
====================
General system routes including main page, port discovery, and utilities.

Authentication:
- Public: /, /api, /health
- Optional auth: /ports, /status, /list_gcode
- Required auth: /config, /download, /list_files

Author: Flask CNC SCADA System
"""

import os
from pathlib import Path
from flask import Blueprint, jsonify, render_template, send_file, send_from_directory, request
from serial.tools import list_ports

from config import get_config
from services.auth_service import (
    require_auth,
    require_role,
    require_permission,
    optional_auth,
    get_current_user
)

# Load configuration
config = get_config()

# Create blueprint
bp = Blueprint('system', __name__)


@bp.route('/')
def index():
    """Main application page."""
    return render_template('index.html')


@bp.route('/scheduling')
def scheduling():
    """Multi-machine scheduling dashboard with Gantt chart."""
    return render_template('scheduling.html')


@bp.route('/mcp')
def mcp_dashboard():
    """MCP Fusion 360 integration dashboard for text engraving and patterns."""
    return render_template('mcp_dashboard.html')


@bp.route('/sensors')
def sensors():
    """Sensor monitoring dashboard with real-time data visualization."""
    return render_template('sensors.html')


@bp.route('/digital-twin')
def digital_twin():
    """3D Digital Twin visualization dashboard (Three.js WebGL)."""
    return render_template('digital_twin.html')


# Legacy route redirect for bookmarks
@bp.route('/unity')
def unity_redirect():
    """Redirect legacy /unity URL to /digital-twin."""
    from flask import redirect
    return redirect('/digital-twin', code=301)


@bp.route('/3d-models/<path:filepath>')
def serve_3d_model(filepath):
    """
    Serve 3D model files for Digital Twin visualization.

    Supports: STL, GLB, GLTF, STEP files
    Path: /3d-models/robots/ned2/base_link.stl
    """
    # Base directory for 3D models (legacy 'unity' folder for backwards compat)
    models_dir = Path(__file__).parent.parent.parent / 'unity' / 'models'

    # Validate file extension
    allowed_extensions = {'.stl', '.glb', '.gltf', '.step', '.obj'}
    file_ext = Path(filepath).suffix.lower()
    if file_ext not in allowed_extensions:
        return jsonify({"error": "File type not allowed"}), 403

    # Resolve the full path
    full_path = (models_dir / filepath).resolve()

    # Security check: ensure path stays within models directory
    if not str(full_path).startswith(str(models_dir.resolve())):
        return jsonify({"error": "Invalid file path"}), 403

    # Check if file exists
    if not full_path.exists() or not full_path.is_file():
        return jsonify({"error": "File not found"}), 404

    # Determine content type
    content_types = {
        '.stl': 'model/stl',
        '.glb': 'model/gltf-binary',
        '.gltf': 'model/gltf+json',
        '.step': 'model/step',
        '.obj': 'text/plain'
    }
    content_type = content_types.get(file_ext, 'application/octet-stream')

    return send_file(str(full_path), mimetype=content_type)


# Legacy route for backwards compatibility
@bp.route('/unity/models/<path:filepath>')
def serve_unity_model_legacy(filepath):
    """Legacy route - redirects to /3d-models/."""
    return serve_3d_model(filepath)


@bp.route('/api')
def api_info():
    """API documentation endpoint."""
    return jsonify({
        "name": "Flask CNC SCADA System",
        "version": "2.0.0",
        "status": "running",
        "authentication": {
            "type": "JWT Bearer Token",
            "login": "POST /auth/login",
            "refresh": "POST /auth/refresh",
            "roles": ["operator", "maintenance", "management", "admin"]
        },
        "endpoints": {
            "auth": {
                "/auth/login": "Authenticate and get JWT tokens",
                "/auth/logout": "Logout (requires auth)",
                "/auth/refresh": "Refresh access token",
                "/auth/me": "Get current user info (requires auth)",
                "/auth/users": "User management (admin only)"
            },
            "system": {
                "/": "Web UI",
                "/api": "This page",
                "/scheduling": "Multi-machine scheduling dashboard",
                "/mcp": "MCP Fusion 360 engraving and pattern dashboard",
                "/ports": "Discover serial ports",
                "/status": "System status",
                "/config": "Configuration info (maintenance+)"
            },
            "tinyg": {
                "/tinyg/status": "TinyG controller status",
                "/tinyg/connect": "Connect to TinyG (maintenance+)",
                "/tinyg/disconnect": "Disconnect from TinyG (maintenance+)",
                "/tinyg/jog": "Jog machine (operator+)",
                "/tinyg/send": "Send G-code (operator+)"
            },
            "sensor": {
                "/sensor/status": "Sensor recorder status",
                "/sensor/start": "Start sensor recording (operator+)",
                "/sensor/stop": "Stop sensor recording (operator+)"
            },
            "mcc": {
                "/mcc/status": "MCC DAQ status",
                "/mcc/start": "Start MCC recording (operator+)",
                "/mcc/stop": "Stop MCC recording (operator+)"
            },
            "mtconnect": {
                "/mtconnect/probe": "Device metadata (MTConnect XML)",
                "/mtconnect/current": "Current data values (MTConnect XML)",
                "/mtconnect/sample": "Historical data stream (MTConnect XML)",
                "/mtconnect/probe/json": "Device metadata (JSON)",
                "/mtconnect/current/json": "Current data values (JSON)",
                "/mtconnect/sample/json": "Historical data stream (JSON)",
                "/mtconnect/status": "Agent status information",
                "/mtconnect/data-items": "List all data items",
                "/mtconnect/position": "Current machine position",
                "/mtconnect/execution": "Current execution state"
            }
        },
        "documentation": "See README_SCADA.md for full documentation"
    })


@bp.route('/ports')
def discover_ports():
    """
    Discover available serial ports.

    Returns:
        JSON with list of available serial ports
    """
    try:
        ports = []
        for p in list_ports.comports():
            name = (p.device or "").lower()
            desc = (p.description or "").lower()
            manu = (getattr(p, "manufacturer", "") or "").lower()

            # Determine device type
            # Heuristics:
            # - TinyG: often shows as CDC with manufacturer "Synthetos" and ttyUSB/cu.usbmodem paths
            # - Arduino sensors: common Nano/Arduino markers
            is_arduino = any(s in name for s in ("ttyacm", "tty.usbmodem", "usbserial", "cu.usbmodem")) \
                          or "arduino" in desc or "arduino" in manu or "nano" in desc
            is_tinyg = (
                "tinyg" in desc
                or "synthetos" in manu
                or "synthetos" in desc
                or "cdc device" in desc
                or "ttyusb" in name
            )

            ports.append({
                'device': p.device,
                'description': p.description or "Unknown",
                'is_arduino': is_arduino,
                'is_tinyg': is_tinyg,
                'manufacturer': getattr(p, 'manufacturer', 'Unknown')
            })

        return jsonify({
            "success": True,
            "ports": ports,
            "count": len(ports)
        })

    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@bp.route('/status')
def system_status():
    """
    Get overall system status including all controllers and services.

    Returns:
        JSON with comprehensive system status information
    """
    from datetime import datetime

    status = {
        "system": "operational",
        "timestamp": datetime.now().isoformat(),
        "controllers": {},
        "services": {},
        "infrastructure": {},
    }

    # Get TinyG controller status
    try:
        from core.controllers.tinyg_controller import get_tinyg_controller
        tinyg = get_tinyg_controller()
        if tinyg:
            status["controllers"]["tinyg"] = {
                "connected": tinyg.is_connected(),
                "port": tinyg.port if hasattr(tinyg, 'port') else None,
                "machine_id": tinyg.machine_id if hasattr(tinyg, 'machine_id') else None,
                "status": "running" if tinyg.is_connected() else "disconnected",
            }
        else:
            status["controllers"]["tinyg"] = {"status": "not_initialized"}
    except Exception as e:
        status["controllers"]["tinyg"] = {"status": "error", "error": str(e)}

    # Get Sensor controller status
    try:
        from core.controllers.sensor_controller import get_sensor_controller
        sensor = get_sensor_controller()
        if sensor:
            status["controllers"]["sensor"] = {
                "running": sensor.is_running() if hasattr(sensor, 'is_running') else False,
                "active_ports": len(sensor.active_ports) if hasattr(sensor, 'active_ports') else 0,
                "sensors_online": sensor.get_sensor_count() if hasattr(sensor, 'get_sensor_count') else 0,
                "status": "recording" if (hasattr(sensor, 'is_running') and sensor.is_running()) else "idle",
            }
        else:
            status["controllers"]["sensor"] = {"status": "not_initialized"}
    except Exception as e:
        status["controllers"]["sensor"] = {"status": "error", "error": str(e)}

    # Get MCC controller status
    try:
        from core.controllers.mcc_controller import get_mcc_controller
        mcc = get_mcc_controller()
        if mcc:
            status["controllers"]["mcc"] = {
                "running": mcc.is_running() if hasattr(mcc, 'is_running') else False,
                "channels": mcc.num_channels if hasattr(mcc, 'num_channels') else 0,
                "machine_id": mcc.machine_id if hasattr(mcc, 'machine_id') else None,
                "status": "recording" if (hasattr(mcc, 'is_running') and mcc.is_running()) else "idle",
            }
        else:
            status["controllers"]["mcc"] = {"status": "not_initialized"}
    except Exception as e:
        status["controllers"]["mcc"] = {"status": "error", "error": str(e)}

    # Get Machine Manager status
    try:
        from services.machine_manager import get_machine_manager
        manager = get_machine_manager()
        machines = manager.list_machines()
        status["services"]["machine_manager"] = {
            "status": "active",
            "registered_machines": len(machines),
            "machines": [
                {
                    "id": m.machine_id,
                    "name": m.name,
                    "status": m.status.value if hasattr(m.status, 'value') else str(m.status),
                }
                for m in machines
            ],
        }
    except Exception as e:
        status["services"]["machine_manager"] = {"status": "error", "error": str(e)}

    # Get Scheduler status
    try:
        from services.scheduling import get_unified_scheduler
        from api.routes.scheduler_routes import _list_schedule_runs
        scheduler = get_unified_scheduler()
        active_runs = _list_schedule_runs(limit=1, active_only=True)
        status["services"]["scheduler"] = {
            "status": "active",
            "algorithms_available": 9,
            "active_schedule": active_runs[0] if active_runs else None,
        }
    except Exception as e:
        status["services"]["scheduler"] = {"status": "error", "error": str(e)}

    # Get Scheduling Trigger Service status
    try:
        from services.scheduling_trigger_service import get_scheduling_trigger_service
        trigger_service = get_scheduling_trigger_service()
        rules = trigger_service.get_rules()
        enabled_count = sum(1 for r in rules.values() if r.get('enabled', False))
        status["services"]["scheduling_triggers"] = {
            "status": "active",
            "total_rules": len(rules),
            "enabled_rules": enabled_count,
            "recent_events": len(trigger_service.get_event_history(limit=10)),
        }
    except Exception as e:
        status["services"]["scheduling_triggers"] = {"status": "error", "error": str(e)}

    # Get InfluxDB status
    try:
        from services.influxdb_service import get_influxdb_service
        influx = get_influxdb_service()
        if influx and config.INFLUXDB_ENABLED:
            health = influx.health_check() if hasattr(influx, 'health_check') else None
            status["infrastructure"]["influxdb"] = {
                "enabled": True,
                "url": config.INFLUXDB_URL,
                "bucket": config.INFLUXDB_BUCKET,
                "status": "healthy" if health else "unknown",
            }
        else:
            status["infrastructure"]["influxdb"] = {"enabled": False}
    except Exception as e:
        status["infrastructure"]["influxdb"] = {"enabled": config.INFLUXDB_ENABLED, "status": "error", "error": str(e)}

    # Get MQTT status
    try:
        from services.mqtt_service import get_mqtt_client
        mqtt = get_mqtt_client()
        if mqtt:
            status["infrastructure"]["mqtt"] = {
                "enabled": True,
                "connected": mqtt.is_connected() if hasattr(mqtt, 'is_connected') else False,
                "broker": config.MQTT_BROKER if hasattr(config, 'MQTT_BROKER') else None,
            }
        else:
            status["infrastructure"]["mqtt"] = {"enabled": False}
    except Exception as e:
        status["infrastructure"]["mqtt"] = {"enabled": False, "status": "error", "error": str(e)}

    # Get PostgreSQL status
    try:
        from database import check_db_health
        db_health = check_db_health()
        status["infrastructure"]["postgresql"] = {
            "enabled": True,
            "status": db_health.get("status", "unknown"),
            "database": db_health.get("database"),
            "pool": db_health.get("pool", {}),
        }
    except Exception as e:
        status["infrastructure"]["postgresql"] = {"enabled": True, "status": "error", "error": str(e)}

    # Get MTConnect status
    try:
        from services.mtconnect import get_mtconnect_adapter, get_mtconnect_agent
        adapter = get_mtconnect_adapter()
        agent = get_mtconnect_agent()
        if adapter and config.MTCONNECT_ENABLED:
            status["infrastructure"]["mtconnect"] = {
                "enabled": True,
                "status": "active",
                "device_id": adapter.device_id,
                "device_name": adapter.device.name,
                "buffer_size": adapter.buffer_size,
                "data_items": len(adapter._data_items),
                "sequence": adapter.get_current_sequence(),
                "version": agent.version if agent else "unknown",
            }
        else:
            status["infrastructure"]["mtconnect"] = {"enabled": False}
    except Exception as e:
        status["infrastructure"]["mtconnect"] = {"enabled": config.MTCONNECT_ENABLED, "status": "error", "error": str(e)}

    # Add Grafana info
    status["infrastructure"]["grafana"] = {
        "url": config.GRAFANA_URL,
    }

    # Add directory info
    status["directories"] = {
        "logs": config.LOG_DIR,
        "gcode": config.GCODE_DIR,
    }

    # Determine overall system status
    controller_statuses = [c.get("status", "unknown") for c in status["controllers"].values()]
    service_statuses = [s.get("status", "unknown") for s in status["services"].values()]
    infra_statuses = [i.get("status", "unknown") for i in status["infrastructure"].values() if isinstance(i, dict)]

    if "error" in controller_statuses + service_statuses + infra_statuses:
        status["system"] = "degraded"
    elif all(s in ["active", "running", "recording", "healthy", "idle", "disconnected", "not_initialized"]
             for s in controller_statuses + service_statuses):
        status["system"] = "operational"
    else:
        status["system"] = "partial"

    return jsonify(status)


@bp.route('/config')
@require_auth
@require_role('maintenance')
def get_config_info():
    """
    Get configuration information.

    Auth: Requires 'maintenance' role or higher

    Returns:
        JSON with configuration details
    """
    config_info = {
        "flask": {
            "host": config.FLASK_HOST,
            "port": config.FLASK_PORT,
            "debug": config.FLASK_DEBUG
        },
        "serial": {
            "default_baud": config.DEFAULT_BAUD,
            "tinyg_poll_interval": config.TINYG_POLL_INTERVAL
        },
        "paths": {
            "log_dir": config.LOG_DIR,
            "gcode_dir": config.GCODE_DIR
        },
        "influxdb": {
            "enabled": config.INFLUXDB_ENABLED,
            "url": config.INFLUXDB_URL if config.INFLUXDB_ENABLED else None,
            "org": config.INFLUXDB_ORG if config.INFLUXDB_ENABLED else None,
            "bucket": config.INFLUXDB_BUCKET if config.INFLUXDB_ENABLED else None
        },
        "mcc": {
            "zmq_url": config.MCC_ZMQ_URL,
            "sample_rate": config.MCC_SAMPLE_RATE
        }
    }

    return jsonify(config_info)


@bp.route('/download/<path:filename>')
@require_auth
@require_permission('view_logs')
def download_file(filename):
    """
    Download a file from the logs directory.

    Auth: Requires 'view_logs' permission (maintenance+)

    Args:
        filename: Name of file to download

    Returns:
        File download response
    """
    # Allowed extensions whitelist
    ALLOWED_EXTENSIONS = {'.csv', '.log', '.txt', '.json'}

    try:
        # Use pathlib for safer path handling
        log_dir = Path(config.LOG_DIR).resolve()
        # Only use the basename to prevent path traversal
        safe_filename = Path(filename).name
        filepath = log_dir / safe_filename

        # Resolve to get absolute path (handles symlinks)
        resolved_path = filepath.resolve()

        # Security check 1: Ensure file is in log directory
        if not str(resolved_path).startswith(str(log_dir)):
            return jsonify({"error": "Invalid file path"}), 403

        # Security check 2: Ensure not a symlink pointing outside
        if filepath.is_symlink():
            return jsonify({"error": "Symlinks not allowed"}), 403

        # Security check 3: Extension whitelist
        if filepath.suffix.lower() not in ALLOWED_EXTENSIONS:
            return jsonify({"error": f"File type not allowed. Allowed: {', '.join(ALLOWED_EXTENSIONS)}"}), 403

        # Security check 4: File exists
        if not resolved_path.exists() or not resolved_path.is_file():
            return jsonify({"error": "File not found"}), 404

        return send_file(str(resolved_path), as_attachment=True)

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.route('/list_files')
@require_auth
@require_permission('view_logs')
def list_files():
    """
    List available log files.

    Auth: Requires 'view_logs' permission (maintenance+)

    Returns:
        JSON with list of log files
    """
    try:
        files = []
        for filename in os.listdir(config.LOG_DIR):
            if filename.endswith('.csv') or filename.endswith('.log'):
                filepath = os.path.join(config.LOG_DIR, filename)
                files.append({
                    'name': filename,
                    'size': os.path.getsize(filepath),
                    'modified': os.path.getmtime(filepath)
                })

        # Sort by modification time (newest first)
        files.sort(key=lambda x: x['modified'], reverse=True)

        return jsonify({
            "success": True,
            "files": files,
            "count": len(files)
        })

    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@bp.route('/list_gcode')
def list_gcode_files():
    """
    List available G-code files.

    Returns:
        JSON with list of G-code files
    """
    try:
        files = []
        valid_extensions = ('.gcode', '.nc', '.tap', '.ngc')
        for filename in os.listdir(config.GCODE_DIR):
            if filename.lower().endswith(valid_extensions):
                filepath = os.path.join(config.GCODE_DIR, filename)
                files.append({
                    'name': filename,
                    'size': os.path.getsize(filepath),
                    'modified': os.path.getmtime(filepath)
                })

        # Sort alphabetically
        files.sort(key=lambda x: x['name'])

        return jsonify({
            "success": True,
            "files": files,
            "count": len(files)
        })

    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@bp.route('/health')
def health_check():
    """
    Health check endpoint for monitoring.

    Returns:
        JSON with health status
    """
    return jsonify({
        "status": "healthy",
        "service": "Flask CNC SCADA"
    })


# Alias for container health check path used in Dockerfile
@bp.route('/api/health')
def health_check_alias():
    return health_check()
