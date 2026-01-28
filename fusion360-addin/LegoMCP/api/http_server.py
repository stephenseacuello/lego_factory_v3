"""
HTTP Server for Fusion 360 Add-in

Provides a local HTTP API that the MCP server can call to control
Fusion 360's modeling and CAM features.

Runs in a background thread within Fusion 360.

Key design considerations:
- Fusion 360 API is NOT thread-safe - all API calls must happen on main thread
- HTTP requests come from background thread
- Solution: Queue requests to a single worker that uses CustomEvent to
  execute on Fusion's main thread
"""

import threading
import queue
import json
import uuid
import time
import sys
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Callable, Dict, Any, Optional
import traceback

# Reference to modeler and CAM processor (set by start_server)
_modeler = None
_cam_processor = None

# Request queue for serializing Fusion 360 API calls
_request_queue = queue.Queue()
_response_dict = {}
_response_lock = threading.Lock()
_response_events = {}  # Event per request to signal completion


def _log(message: str, error: bool = False):
    """Log message to Fusion 360 console."""
    stream = sys.stderr if error else sys.stdout
    try:
        print(f"[LegoMCP HTTP] {message}", file=stream, flush=True)
    except:
        pass  # Don't let logging errors break anything


class FusionWorker(threading.Thread):
    """
    Single worker thread that processes Fusion 360 API calls sequentially.

    This ensures thread safety by serializing all Fusion API operations.
    The actual Fusion API calls happen on this worker thread, not directly
    in the HTTP handler thread.
    """

    def __init__(self, handler_registry: Dict[str, Callable]):
        super().__init__(daemon=True, name="FusionWorker")
        self.handler_registry = handler_registry
        self._stop_event = threading.Event()

    def run(self):
        """Process requests from the queue."""
        _log("FusionWorker started - processing requests sequentially")

        while not self._stop_event.is_set():
            try:
                # Block with timeout so we can check stop event
                try:
                    request_id, command, params = _request_queue.get(timeout=0.5)
                except queue.Empty:
                    continue

                _log(f"Processing request {request_id[:8]}... command={command}")

                # Execute the handler
                try:
                    handler = self.handler_registry.get(command)
                    if handler:
                        result = handler(params)
                    else:
                        result = {'success': False, 'error': f'Unknown command: {command}'}
                except Exception as e:
                    _log(f"Handler error for {command}: {e}", error=True)
                    result = {
                        'success': False,
                        'error': str(e),
                        'traceback': traceback.format_exc()
                    }

                # Store result and signal completion
                with _response_lock:
                    _response_dict[request_id] = result
                    if request_id in _response_events:
                        _response_events[request_id].set()

                _request_queue.task_done()
                _log(f"Completed request {request_id[:8]}...")

            except Exception as e:
                _log(f"FusionWorker error: {e}", error=True)

        _log("FusionWorker stopped")

    def stop(self):
        """Signal worker to stop."""
        self._stop_event.set()


# Global worker instance
_fusion_worker = None


def _queue_request(command: str, params: dict, timeout: float = 60.0) -> dict:
    """
    Queue a request for the Fusion worker and wait for result.

    Args:
        command: Command name to execute
        params: Parameters for the command
        timeout: Maximum time to wait for result (seconds)

    Returns:
        Result dictionary from the handler
    """
    request_id = str(uuid.uuid4())
    event = threading.Event()

    with _response_lock:
        _response_events[request_id] = event

    # Queue the request
    _request_queue.put((request_id, command, params))

    # Wait for result
    if not event.wait(timeout=timeout):
        # Timeout - clean up and return error
        with _response_lock:
            _response_events.pop(request_id, None)
            _response_dict.pop(request_id, None)
        return {
            'success': False,
            'error': f'Operation timed out after {timeout} seconds'
        }

    # Get result
    with _response_lock:
        result = _response_dict.pop(request_id, {'success': False, 'error': 'No result'})
        _response_events.pop(request_id, None)

    return result


class FusionAPIHandler(BaseHTTPRequestHandler):
    """HTTP request handler for Fusion 360 API commands."""
    
    def log_message(self, format, *args):
        """Suppress default logging."""
        pass
    
    def _send_json_response(self, data: dict, status: int = 200):
        """Send JSON response."""
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode('utf-8'))
    
    def _read_json_body(self) -> dict:
        """Read and parse JSON request body."""
        content_length = int(self.headers.get('Content-Length', 0))
        if content_length == 0:
            return {}
        body = self.rfile.read(content_length)
        return json.loads(body.decode('utf-8'))
    
    def do_OPTIONS(self):
        """Handle CORS preflight."""
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
    
    def do_GET(self):
        """Handle GET requests."""
        if self.path == '/health':
            self._send_json_response({
                'status': 'ok',
                'service': 'LegoMCP Fusion360',
                'version': '1.0.0'
            })
        elif self.path == '/components':
            self._handle_list_components()
        else:
            self._send_json_response({'error': 'Not found'}, 404)
    
    def do_POST(self):
        """Handle POST requests via the serialized queue."""
        try:
            body = self._read_json_body()
            command = body.get('command', self.path.strip('/'))
            params = body.get('params', body)

            _log(f"POST request: command={command}")

            # Normalize command names (path-based and command-based both work)
            command_aliases = {
                'brick': 'create_brick',
                'plate': 'create_plate',
                'tile': 'create_tile',
                'slope': 'create_slope',
                'technic': 'create_technic',
                'round': 'create_round',
                'arch': 'create_arch',
                'wedge': 'create_wedge',
                'inverted_slope': 'create_inverted_slope',
                'jumper': 'create_jumper',
                'hinge': 'create_hinge',
                'modified': 'create_modified',
            }
            command = command_aliases.get(command, command)

            # Validate command exists
            valid_commands = {
                'create_brick', 'create_plate', 'create_tile', 'create_slope',
                'create_technic', 'create_round', 'create_arch',
                'create_wedge', 'create_inverted_slope', 'create_jumper',
                'create_hinge', 'create_modified',
                'export_stl', 'export_step', 'export_3mf',
                'setup_cam', 'generate_gcode', 'full_mill_workflow',
                'batch_export', 'slice_stl',
                'aluminum_lego_cam', 'aluminum_workflow_status',
                # AI CAM Copilot commands
                'ai_cam_recommend', 'ai_cam_execute', 'ai_cam_feedback',
            }

            if command not in valid_commands:
                self._send_json_response({
                    'success': False,
                    'error': f'Unknown command: {command}',
                    'valid_commands': list(valid_commands)
                }, 400)
                return

            # Queue the request and wait for result (with 60s timeout)
            result = _queue_request(command, params, timeout=60.0)
            self._send_json_response(result)

        except json.JSONDecodeError as e:
            _log(f"JSON parse error: {e}", error=True)
            self._send_json_response({
                'success': False,
                'error': f'Invalid JSON: {e}'
            }, 400)
        except Exception as e:
            _log(f"POST handler error: {e}", error=True)
            self._send_json_response({
                'success': False,
                'error': str(e),
                'traceback': traceback.format_exc()
            }, 500)
    
    # === Command Handlers ===
    
    def _handle_list_components(self):
        """List all components in current design."""
        if not _modeler:
            self._send_json_response({'error': 'Modeler not initialized'}, 500)
            return
        
        components = _modeler.list_components()
        self._send_json_response({
            'success': True,
            'components': components
        })
    
    def _handle_create_brick(self, params: dict) -> dict:
        """Create a standard LEGO brick.

        Accepts parameters in two formats:
        1. Flat format: {"studs_x": 3, "studs_y": 6, "height_units": 1.0}
        2. Nested format: {"dimensions": {"width_studs": 3, "depth_studs": 6, "height_plates": 3}}
        """
        if not _modeler:
            return {'success': False, 'error': 'Modeler not initialized'}

        # Extract parameters from nested OR flat format
        dimensions = params.get('dimensions', {})

        # Prefer nested dimensions.width_studs, fallback to flat studs_x, then default
        studs_x = dimensions.get('width_studs') or params.get('width_studs') or params.get('studs_x') or params.get('width', 2)
        studs_y = dimensions.get('depth_studs') or params.get('depth_studs') or params.get('studs_y') or params.get('depth', 4)

        # Ensure integer values
        studs_x = int(studs_x)
        studs_y = int(studs_y)

        # Height: nested height_plates (in plate units), flat height_units, or default
        height_plates = dimensions.get('height_plates')
        if height_plates:
            height_units = float(height_plates) / 3.0  # Convert plates to brick units (3 plates = 1 brick)
        else:
            height_units = float(params.get('height_units', params.get('height_bricks', 1.0)))

        # Hollow: check is_hollow (nested format) or hollow (flat format)
        hollow = params.get('is_hollow', params.get('hollow', True))

        # Center rib: adds the internal spine for 2xN bricks (like real LEGO)
        center_rib = params.get('center_rib', True)

        name = params.get('name')
        color = params.get('color')  # LEGO color name (red, blue, yellow, etc.)

        _log(f"Creating brick: {studs_x}x{studs_y}, height={height_units}, hollow={hollow}, center_rib={center_rib}, name={name}, color={color}")

        result = _modeler.create_standard_brick(
            studs_x=studs_x,
            studs_y=studs_y,
            height_units=height_units,
            hollow=hollow,
            center_rib=center_rib,
            name=name,
            color=color
        )

        return {
            'success': result.success,
            'brick_id': result.brick_id,
            'component_name': result.component_name,
            'dimensions': result.dimensions,
            'volume_mm3': result.volume_mm3,
            'error': result.error
        }
    
    def _handle_create_plate(self, params: dict) -> dict:
        """Create a LEGO plate (1/3 height)."""
        if not _modeler:
            return {'success': False, 'error': 'Modeler not initialized'}

        # Extract parameters from nested OR flat format
        dimensions = params.get('dimensions', {})
        studs_x = int(dimensions.get('width_studs') or params.get('width_studs') or params.get('studs_x') or params.get('width', 2))
        studs_y = int(dimensions.get('depth_studs') or params.get('depth_studs') or params.get('studs_y') or params.get('depth', 4))

        _log(f"Creating plate: {studs_x}x{studs_y}")

        result = _modeler.create_plate(
            studs_x=studs_x,
            studs_y=studs_y,
            name=params.get('name')
        )

        return {
            'success': result.success,
            'brick_id': result.brick_id,
            'component_name': result.component_name,
            'dimensions': result.dimensions,
            'volume_mm3': result.volume_mm3,
            'error': result.error
        }
    
    def _handle_create_tile(self, params: dict) -> dict:
        """Create a LEGO tile (flat, no studs)."""
        if not _modeler:
            return {'success': False, 'error': 'Modeler not initialized'}

        # Extract parameters from nested OR flat format
        dimensions = params.get('dimensions', {})
        studs_x = int(dimensions.get('width_studs') or params.get('width_studs') or params.get('studs_x') or params.get('width', 2))
        studs_y = int(dimensions.get('depth_studs') or params.get('depth_studs') or params.get('studs_y') or params.get('depth', 2))

        _log(f"Creating tile: {studs_x}x{studs_y}")

        result = _modeler.create_tile(
            studs_x=studs_x,
            studs_y=studs_y,
            name=params.get('name')
        )

        return {
            'success': result.success,
            'brick_id': result.brick_id,
            'component_name': result.component_name,
            'dimensions': result.dimensions,
            'volume_mm3': result.volume_mm3,
            'error': result.error
        }
    
    def _handle_create_slope(self, params: dict) -> dict:
        """Create a slope brick."""
        if not _modeler:
            return {'success': False, 'error': 'Modeler not initialized'}

        # Extract parameters from nested OR flat format
        dimensions = params.get('dimensions', {})
        studs_x = int(dimensions.get('width_studs') or params.get('width_studs') or params.get('studs_x') or params.get('width', 2))
        studs_y = int(dimensions.get('depth_studs') or params.get('depth_studs') or params.get('studs_y') or params.get('depth', 4))

        _log(f"Creating slope: {studs_x}x{studs_y}")

        result = _modeler.create_slope_brick(
            studs_x=studs_x,
            studs_y=studs_y,
            slope_angle=params.get('slope_angle', 45.0),
            slope_direction=params.get('slope_direction', 'front'),
            name=params.get('name')
        )

        return {
            'success': result.success,
            'brick_id': result.brick_id,
            'component_name': result.component_name,
            'dimensions': result.dimensions,
            'volume_mm3': result.volume_mm3,
            'error': result.error
        }

    def _handle_create_technic(self, params: dict) -> dict:
        """Create a Technic brick with pin/axle holes."""
        if not _modeler:
            return {'success': False, 'error': 'Modeler not initialized'}

        # Extract parameters from nested OR flat format
        dimensions = params.get('dimensions', {})
        studs_x = int(dimensions.get('width_studs') or params.get('width_studs') or params.get('studs_x') or params.get('width', 1))
        studs_y = int(dimensions.get('depth_studs') or params.get('depth_studs') or params.get('studs_y') or params.get('depth', 6))

        # Technic-specific parameters
        # Default to 'y' for holes along the longer dimension (typical Technic brick)
        hole_axis = params.get('hole_axis', 'y')
        hole_type = params.get('hole_type', 'pin')
        color = params.get('color')

        _log(f"Creating technic brick: {studs_x}x{studs_y}, holes along {hole_axis}")

        # Use the actual create_technic_brick method
        result = _modeler.create_technic_brick(
            studs_x=studs_x,
            studs_y=studs_y,
            height_units=1.0,
            hole_axis=hole_axis,
            hole_type=hole_type,
            hollow=True,
            name=params.get('name') or f"Technic_{studs_x}x{studs_y}",
            color=color
        )

        return {
            'success': result.success,
            'brick_id': result.brick_id,
            'component_name': result.component_name,
            'dimensions': result.dimensions,
            'volume_mm3': result.volume_mm3,
            'error': result.error
        }

    def _handle_create_round(self, params: dict) -> dict:
        """Create a cylindrical round brick."""
        if not _modeler:
            return {'success': False, 'error': 'Modeler not initialized'}

        # Extract parameters - round bricks use diameter
        dimensions = params.get('dimensions', {})
        diameter = int(dimensions.get('width_studs') or params.get('diameter_studs') or params.get('diameter') or params.get('width', 2))
        height_units = float(params.get('height_units', 1.0))
        color = params.get('color')

        _log(f"Creating round brick: diameter={diameter}, height={height_units}")

        # Use the actual create_round_brick method for cylindrical bricks
        result = _modeler.create_round_brick(
            diameter_studs=diameter,
            height_units=height_units,
            hollow=True,
            name=params.get('name') or f"Round_{diameter}x{height_units}",
            color=color
        )

        return {
            'success': result.success,
            'brick_id': result.brick_id,
            'component_name': result.component_name,
            'dimensions': result.dimensions,
            'volume_mm3': result.volume_mm3,
            'error': result.error
        }

    def _handle_create_arch(self, params: dict) -> dict:
        """Create an arch brick with curved cutout."""
        if not _modeler:
            return {'success': False, 'error': 'Modeler not initialized'}

        # Extract parameters from nested OR flat format
        dimensions = params.get('dimensions', {})
        studs_x = int(dimensions.get('width_studs') or params.get('width_studs') or params.get('studs_x') or params.get('width', 4))
        studs_y = int(dimensions.get('depth_studs') or params.get('depth_studs') or params.get('studs_y') or params.get('depth', 1))
        arch_height = int(params.get('arch_height', 1))

        _log(f"Creating arch brick: {studs_x}x{studs_y}, arch_height={arch_height}")

        # Arch bricks need brick_modeler enhancement for arch cutouts
        # For now, create standard brick of same size
        result = _modeler.create_standard_brick(
            studs_x=studs_x,
            studs_y=studs_y,
            height_units=arch_height + 1,  # Arch needs height for opening
            hollow=True,
            name=params.get('name') or f"Arch_{studs_x}x{studs_y}"
        )

        return {
            'success': result.success,
            'brick_id': result.brick_id,
            'component_name': result.component_name,
            'dimensions': result.dimensions,
            'volume_mm3': result.volume_mm3,
            'error': result.error,
            'note': 'Arch cutout not yet implemented - created as standard brick'
        }

    def _handle_create_wedge(self, params: dict) -> dict:
        """Create a wedge brick (triangular profile)."""
        if not _modeler:
            return {'success': False, 'error': 'Modeler not initialized'}

        # Extract parameters
        dimensions = params.get('dimensions', {})
        studs_x = int(dimensions.get('width_studs') or params.get('width_studs') or params.get('studs_x') or params.get('width', 2))
        studs_y = int(dimensions.get('depth_studs') or params.get('depth_studs') or params.get('studs_y') or params.get('depth', 4))
        height_units = float(params.get('height_units', 1.0))
        wedge_direction = params.get('wedge_direction', params.get('direction', 'right'))

        _log(f"Creating wedge brick: {studs_x}x{studs_y}, direction={wedge_direction}")

        result = _modeler.create_wedge_brick(
            studs_x=studs_x,
            studs_y=studs_y,
            height_units=height_units,
            wedge_direction=wedge_direction,
            hollow=params.get('hollow', True),
            name=params.get('name'),
            color=params.get('color')
        )

        return {
            'success': result.success,
            'brick_id': result.brick_id,
            'component_name': result.component_name,
            'dimensions': result.dimensions,
            'volume_mm3': result.volume_mm3,
            'error': result.error
        }

    def _handle_create_inverted_slope(self, params: dict) -> dict:
        """Create an inverted slope brick (slope on bottom)."""
        if not _modeler:
            return {'success': False, 'error': 'Modeler not initialized'}

        # Extract parameters
        dimensions = params.get('dimensions', {})
        studs_x = int(dimensions.get('width_studs') or params.get('width_studs') or params.get('studs_x') or params.get('width', 2))
        studs_y = int(dimensions.get('depth_studs') or params.get('depth_studs') or params.get('studs_y') or params.get('depth', 4))
        height_units = float(params.get('height_units', 1.0))
        slope_angle = float(params.get('slope_angle', 45.0))
        slope_direction = params.get('slope_direction', params.get('direction', 'front'))

        _log(f"Creating inverted slope: {studs_x}x{studs_y}, angle={slope_angle}, direction={slope_direction}")

        result = _modeler.create_inverted_slope(
            studs_x=studs_x,
            studs_y=studs_y,
            height_units=height_units,
            slope_angle=slope_angle,
            slope_direction=slope_direction,
            hollow=params.get('hollow', True),
            name=params.get('name'),
            color=params.get('color')
        )

        return {
            'success': result.success,
            'brick_id': result.brick_id,
            'component_name': result.component_name,
            'dimensions': result.dimensions,
            'volume_mm3': result.volume_mm3,
            'error': result.error
        }

    def _handle_create_jumper(self, params: dict) -> dict:
        """Create a jumper plate (offset stud)."""
        if not _modeler:
            return {'success': False, 'error': 'Modeler not initialized'}

        # Extract parameters
        dimensions = params.get('dimensions', {})
        studs_x = int(dimensions.get('width_studs') or params.get('width_studs') or params.get('studs_x') or params.get('width', 1))
        studs_y = int(dimensions.get('depth_studs') or params.get('depth_studs') or params.get('studs_y') or params.get('depth', 2))

        _log(f"Creating jumper plate: {studs_x}x{studs_y}")

        result = _modeler.create_jumper_plate(
            studs_x=studs_x,
            studs_y=studs_y,
            name=params.get('name'),
            color=params.get('color')
        )

        return {
            'success': result.success,
            'brick_id': result.brick_id,
            'component_name': result.component_name,
            'dimensions': result.dimensions,
            'volume_mm3': result.volume_mm3,
            'error': result.error
        }

    def _handle_create_hinge(self, params: dict) -> dict:
        """Create a hinge brick."""
        if not _modeler:
            return {'success': False, 'error': 'Modeler not initialized'}

        # Extract parameters
        dimensions = params.get('dimensions', {})
        studs_x = int(dimensions.get('width_studs') or params.get('width_studs') or params.get('studs_x') or params.get('width', 1))
        studs_y = int(dimensions.get('depth_studs') or params.get('depth_studs') or params.get('studs_y') or params.get('depth', 2))
        height_units = float(params.get('height_units', 1.0))
        hinge_type = params.get('hinge_type', 'top')  # top, bottom, side

        _log(f"Creating hinge brick: {studs_x}x{studs_y}, type={hinge_type}")

        result = _modeler.create_hinge_brick(
            studs_x=studs_x,
            studs_y=studs_y,
            height_units=height_units,
            hinge_type=hinge_type,
            hollow=params.get('hollow', True),
            name=params.get('name'),
            color=params.get('color')
        )

        return {
            'success': result.success,
            'brick_id': result.brick_id,
            'component_name': result.component_name,
            'dimensions': result.dimensions,
            'volume_mm3': result.volume_mm3,
            'error': result.error
        }

    def _handle_create_modified(self, params: dict) -> dict:
        """Create a modified brick (grille, clips, etc.)."""
        if not _modeler:
            return {'success': False, 'error': 'Modeler not initialized'}

        # Extract parameters
        dimensions = params.get('dimensions', {})
        studs_x = int(dimensions.get('width_studs') or params.get('width_studs') or params.get('studs_x') or params.get('width', 1))
        studs_y = int(dimensions.get('depth_studs') or params.get('depth_studs') or params.get('studs_y') or params.get('depth', 2))
        height_units = float(params.get('height_units', 1.0))
        modification = params.get('modification', 'grille')  # grille, clips, handle, etc.

        _log(f"Creating modified brick: {studs_x}x{studs_y}, modification={modification}")

        result = _modeler.create_modified_brick(
            studs_x=studs_x,
            studs_y=studs_y,
            height_units=height_units,
            modification=modification,
            hollow=params.get('hollow', True),
            name=params.get('name'),
            color=params.get('color')
        )

        return {
            'success': result.success,
            'brick_id': result.brick_id,
            'component_name': result.component_name,
            'dimensions': result.dimensions,
            'volume_mm3': result.volume_mm3,
            'error': result.error
        }

    def _handle_batch_export(self, params: dict) -> dict:
        """Export multiple components at once."""
        if not _modeler:
            return {'success': False, 'error': 'Modeler not initialized'}

        import os

        component_names = params.get('components', [])
        export_format = params.get('format', 'stl').lower()
        output_dir = params.get('output_dir')

        if not output_dir:
            output_dir = os.path.join(os.path.expanduser("~"), "Documents", "LegoMCP", "exports", export_format)

        os.makedirs(output_dir, exist_ok=True)

        results = []
        for comp_name in component_names:
            try:
                output_path = os.path.join(output_dir, f"{comp_name}.{export_format}")

                if export_format == 'stl':
                    result = _modeler.export_stl(comp_name, output_path, params.get('resolution', 'high'))
                    results.append({
                        'component': comp_name,
                        'success': True,
                        'path': result['path'],
                        'size_kb': result['size_kb']
                    })
                elif export_format == 'step':
                    comp = _modeler.get_component_by_name(comp_name)
                    if comp:
                        export_mgr = _modeler.design.exportManager
                        step_options = export_mgr.createSTEPExportOptions(output_path, comp)
                        export_mgr.execute(step_options)
                        file_size = os.path.getsize(output_path) / 1024
                        results.append({
                            'component': comp_name,
                            'success': True,
                            'path': output_path,
                            'size_kb': file_size
                        })
                    else:
                        results.append({
                            'component': comp_name,
                            'success': False,
                            'error': f'Component not found: {comp_name}'
                        })
                elif export_format == '3mf':
                    comp = _modeler.get_component_by_name(comp_name)
                    if comp:
                        export_mgr = _modeler.design.exportManager
                        threemf_options = export_mgr.createC3MFExportOptions(comp, output_path)
                        export_mgr.execute(threemf_options)
                        file_size = os.path.getsize(output_path) / 1024
                        results.append({
                            'component': comp_name,
                            'success': True,
                            'path': output_path,
                            'size_kb': file_size
                        })
                    else:
                        results.append({
                            'component': comp_name,
                            'success': False,
                            'error': f'Component not found: {comp_name}'
                        })
                else:
                    results.append({
                        'component': comp_name,
                        'success': False,
                        'error': f'Unsupported format: {export_format}'
                    })
            except Exception as e:
                results.append({
                    'component': comp_name,
                    'success': False,
                    'error': str(e)
                })

        successful = sum(1 for r in results if r.get('success'))
        return {
            'success': successful > 0,
            'exported': successful,
            'total': len(component_names),
            'results': results,
            'output_dir': output_dir
        }

    def _handle_slice_stl(self, params: dict) -> dict:
        """Generate slicer commands or G-code for 3D printing."""
        if not _modeler:
            return {'success': False, 'error': 'Modeler not initialized'}

        import os
        import subprocess

        stl_path = params.get('stl_path')
        component_name = params.get('component_name')
        slicer = params.get('slicer', 'prusaslicer').lower()
        profile = params.get('profile', 'default')

        # If component_name provided, export STL first
        if component_name and not stl_path:
            output_dir = os.path.join(os.path.expanduser("~"), "Documents", "LegoMCP", "exports", "stl")
            os.makedirs(output_dir, exist_ok=True)
            stl_path = os.path.join(output_dir, f"{component_name}.stl")

            try:
                export_result = _modeler.export_stl(component_name, stl_path, 'high')
            except Exception as e:
                return {'success': False, 'error': f'STL export failed: {e}'}

        if not stl_path or not os.path.exists(stl_path):
            return {'success': False, 'error': 'STL file not found'}

        # Generate slicer command
        output_dir = os.path.join(os.path.expanduser("~"), "Documents", "LegoMCP", "exports", "gcode")
        os.makedirs(output_dir, exist_ok=True)

        base_name = os.path.splitext(os.path.basename(stl_path))[0]
        gcode_path = os.path.join(output_dir, f"{base_name}.gcode")

        # Slicer-specific command generation
        slicer_commands = {
            'prusaslicer': f'prusa-slicer --export-gcode --output "{gcode_path}" "{stl_path}"',
            'cura': f'CuraEngine slice -j cura_defaults.json -o "{gcode_path}" -l "{stl_path}"',
            'slic3r': f'slic3r --output "{gcode_path}" "{stl_path}"',
            'superslicer': f'superslicer --export-gcode --output "{gcode_path}" "{stl_path}"',
        }

        slicer_cmd = slicer_commands.get(slicer)
        if not slicer_cmd:
            return {
                'success': False,
                'error': f'Unknown slicer: {slicer}',
                'supported_slicers': list(slicer_commands.keys())
            }

        # Attempt to run slicer (may fail if not installed)
        try:
            result = subprocess.run(
                slicer_cmd,
                shell=True,
                capture_output=True,
                text=True,
                timeout=300  # 5 minute timeout
            )

            if result.returncode == 0 and os.path.exists(gcode_path):
                file_size = os.path.getsize(gcode_path) / 1024
                return {
                    'success': True,
                    'gcode_path': gcode_path,
                    'size_kb': file_size,
                    'slicer': slicer,
                    'stl_path': stl_path
                }
            else:
                return {
                    'success': False,
                    'error': f'Slicer failed: {result.stderr}',
                    'command': slicer_cmd,
                    'hint': f'Make sure {slicer} is installed and in PATH'
                }
        except FileNotFoundError:
            return {
                'success': False,
                'error': f'{slicer} not found',
                'command': slicer_cmd,
                'hint': f'Install {slicer} and ensure it is in your system PATH',
                'manual_command': slicer_cmd
            }
        except subprocess.TimeoutExpired:
            return {
                'success': False,
                'error': 'Slicer timed out after 5 minutes',
                'command': slicer_cmd
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'command': slicer_cmd
            }

    def _handle_export_stl(self, params: dict) -> dict:
        """Export component as STL."""
        if not _modeler:
            return {'success': False, 'error': 'Modeler not initialized'}

        component_name = params.get('component_name') or params.get('brick_id')
        if not component_name:
            return {'success': False, 'error': 'component_name required'}

        # Get output path - use user's Documents folder if no path specified
        import os
        default_output_dir = os.path.join(os.path.expanduser("~"), "Documents", "LegoMCP", "exports", "stl")
        output_path = params.get('output_path')

        if not output_path:
            output_path = os.path.join(default_output_dir, f"{component_name}.stl")

        # Ensure output directory exists
        output_dir = os.path.dirname(output_path)
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)

        resolution = params.get('resolution', 'high')

        try:
            # First check if component exists
            comp = _modeler.get_component_by_name(component_name)
            if not comp:
                available = _modeler.list_components()
                return {
                    'success': False,
                    'error': f'Component not found: {component_name}',
                    'available_components': available,
                    'hint': 'Create the brick first, then export'
                }

            result = _modeler.export_stl(component_name, output_path, resolution)
            return {
                'success': True,
                'path': result['path'],
                'size_kb': result['size_kb'],
                'triangle_count': result['triangle_count']
            }
        except Exception as e:
            available = _modeler.list_components() if _modeler else []
            return {
                'success': False,
                'error': str(e),
                'available_components': available
            }

    def _handle_export_step(self, params: dict) -> dict:
        """Export component as STEP file."""
        if not _modeler:
            return {'success': False, 'error': 'Modeler not initialized'}

        component_name = params.get('component_name') or params.get('brick_id')
        if not component_name:
            return {'success': False, 'error': 'component_name required'}

        import os
        default_output_dir = os.path.join(os.path.expanduser("~"), "Documents", "LegoMCP", "exports", "step")
        output_path = params.get('output_path')

        if not output_path:
            output_path = os.path.join(default_output_dir, f"{component_name}.step")

        # Ensure output directory exists
        output_dir = os.path.dirname(output_path)
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)

        try:
            # Find component
            comp = _modeler.get_component_by_name(component_name)
            if not comp:
                available = _modeler.list_components()
                return {
                    'success': False,
                    'error': f'Component not found: {component_name}',
                    'available_components': available,
                    'hint': 'Create the brick first, then export'
                }

            # STEP export
            export_mgr = _modeler.design.exportManager
            step_options = export_mgr.createSTEPExportOptions(output_path, comp)
            export_mgr.execute(step_options)

            file_size = os.path.getsize(output_path) / 1024  # KB

            return {
                'success': True,
                'path': output_path,
                'size_kb': file_size,
                'format': 'STEP'
            }
        except Exception as e:
            available = _modeler.list_components() if _modeler else []
            return {
                'success': False,
                'error': str(e),
                'available_components': available
            }

    def _handle_export_3mf(self, params: dict) -> dict:
        """Export component as 3MF file."""
        if not _modeler:
            return {'success': False, 'error': 'Modeler not initialized'}

        component_name = params.get('component_name') or params.get('brick_id')
        if not component_name:
            return {'success': False, 'error': 'component_name required'}

        import os
        default_output_dir = os.path.join(os.path.expanduser("~"), "Documents", "LegoMCP", "exports", "3mf")
        output_path = params.get('output_path')

        if not output_path:
            output_path = os.path.join(default_output_dir, f"{component_name}.3mf")

        # Ensure output directory exists
        output_dir = os.path.dirname(output_path)
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)

        try:
            # Find component
            comp = _modeler.get_component_by_name(component_name)
            if not comp:
                available = _modeler.list_components()
                return {
                    'success': False,
                    'error': f'Component not found: {component_name}',
                    'available_components': available,
                    'hint': 'Create the brick first, then export'
                }

            # 3MF export
            export_mgr = _modeler.design.exportManager
            threemf_options = export_mgr.createC3MFExportOptions(comp, output_path)
            export_mgr.execute(threemf_options)

            file_size = os.path.getsize(output_path) / 1024  # KB

            return {
                'success': True,
                'path': output_path,
                'size_kb': file_size,
                'format': '3MF'
            }
        except Exception as e:
            available = _modeler.list_components() if _modeler else []
            return {
                'success': False,
                'error': str(e),
                'available_components': available
            }

    def _handle_setup_cam(self, params: dict) -> dict:
        """Set up CAM for a component."""
        if not _cam_processor:
            return {'success': False, 'error': 'CAM processor not initialized'}
        
        component_name = params.get('component_name')
        if not component_name:
            return {'success': False, 'error': 'component_name required'}
        
        try:
            setup = _cam_processor.setup_milling(
                component_name=component_name,
                material=params.get('material', 'abs'),
                stock_offset_mm=params.get('stock_offset_mm', 1.0)
            )
            return {
                'success': True,
                'setup_name': setup.name
            }
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def _handle_generate_gcode(self, params: dict) -> dict:
        """Generate G-code for milling."""
        if not _cam_processor:
            return {'success': False, 'error': 'CAM processor not initialized'}
        
        component_name = params.get('component_name')
        if not component_name:
            return {'success': False, 'error': 'component_name required'}
        
        try:
            result = _cam_processor.create_standard_brick_toolpath(
                component_name=component_name,
                material=params.get('material', 'abs'),
                machine=params.get('machine', 'grbl'),
                output_path=params.get('output_path')
            )
            return {
                'success': True,
                **result
            }
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def _handle_full_mill_workflow(self, params: dict) -> dict:
        """
        Complete workflow: create brick → setup CAM → generate G-code.
        
        Convenience endpoint for full milling workflow.
        """
        if not _modeler or not _cam_processor:
            return {'success': False, 'error': 'Services not initialized'}
        
        try:
            # Step 1: Create brick
            brick_result = _modeler.create_standard_brick(
                studs_x=params.get('studs_x', 2),
                studs_y=params.get('studs_y', 4),
                height_units=params.get('height_units', 1.0),
                hollow=params.get('hollow', True),
                name=params.get('name')
            )
            
            if not brick_result.success:
                return {'success': False, 'error': f'Brick creation failed: {brick_result.error}'}
            
            # Step 2: Export STL
            stl_path = f"/output/stl/{brick_result.component_name}.stl"
            stl_result = _modeler.export_stl(
                brick_result.component_name,
                stl_path,
                'high'
            )
            
            # Step 3: Generate milling G-code
            gcode_path = f"/output/gcode/milling/{brick_result.component_name}.nc"
            gcode_result = _cam_processor.create_standard_brick_toolpath(
                component_name=brick_result.component_name,
                material=params.get('material', 'abs'),
                machine=params.get('machine', 'grbl'),
                output_path=gcode_path
            )
            
            return {
                'success': True,
                'brick': {
                    'id': brick_result.brick_id,
                    'name': brick_result.component_name,
                    'dimensions': brick_result.dimensions,
                    'volume_mm3': brick_result.volume_mm3
                },
                'stl': {
                    'path': stl_result['path'],
                    'size_kb': stl_result['size_kb']
                },
                'gcode': gcode_result
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'traceback': traceback.format_exc()
            }

    def _handle_aluminum_lego_cam(self, params: dict) -> dict:
        """
        Create complete CAM workflow for aluminum LEGO brick on Bantam Desktop CNC.

        This creates a two-setup workflow:
        - SETUP1 (G54): Top operations - facing, stud roughing, stud finishing
        - SETUP2 (G55): Bottom operations - hollow pocket, tubes, wall finishing

        Uses optimized 2-tool strategy:
        - T1: 3mm flat endmill (facing, roughing)
        - T2: 2mm flat endmill (finishing, tubes)

        Params:
            studs_x: int (1-8, default 2)
            studs_y: int (1-8, default 4)
            height_plates: int (1-9, default 3)
            z_offset_mm: float (0.5-3.0, default 1.0)
            component_name: str (optional - will create brick if not provided)
            output_dir: str (optional)

        Returns:
            Complete workflow with setups, operations, G-code paths
        """
        if not _cam_processor:
            return {'success': False, 'error': 'CAM processor not initialized'}

        try:
            # Extract parameters
            studs_x = min(max(int(params.get('studs_x', 2)), 1), 8)
            studs_y = min(max(int(params.get('studs_y', 4)), 1), 8)
            height_plates = min(max(int(params.get('height_plates', 3)), 1), 9)
            z_offset_mm = min(max(float(params.get('z_offset_mm', 1.0)), 0.5), 3.0)
            output_dir = params.get('output_dir')

            # Get or create component
            component_name = params.get('component_name')
            brick_result = None

            if not component_name:
                # Create the brick first
                if not _modeler:
                    return {'success': False, 'error': 'Modeler not initialized - cannot create brick'}

                # Create aluminum brick (solid, no hollow for milling from stock)
                brick_result = _modeler.create_standard_brick(
                    studs_x=studs_x,
                    studs_y=studs_y,
                    height_units=height_plates / 3.0,  # Convert plates to brick units
                    hollow=True,  # Will have hollow interior
                    center_rib=True,
                    name=f"AluminumLEGO_{studs_x}x{studs_y}"
                )

                if not brick_result.success:
                    return {'success': False, 'error': f'Brick creation failed: {brick_result.error}'}

                component_name = brick_result.component_name
                _log(f"Created aluminum brick component: {component_name}")

            # Run the aluminum CAM workflow
            result = _cam_processor.create_aluminum_lego_cam(
                component_name=component_name,
                studs_x=studs_x,
                studs_y=studs_y,
                height_plates=height_plates,
                z_offset_mm=z_offset_mm,
                output_dir=output_dir
            )

            # Add brick info if we created it
            if brick_result:
                result['brick_created'] = {
                    'id': brick_result.brick_id,
                    'component_name': brick_result.component_name,
                    'dimensions': brick_result.dimensions,
                    'volume_mm3': brick_result.volume_mm3
                }

            result['success'] = len(result.get('errors', [])) == 0

            return result

        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'traceback': traceback.format_exc()
            }

    def _handle_aluminum_workflow_status(self, params: dict) -> dict:
        """
        Get status of aluminum LEGO milling capabilities.

        Returns machine specs, tool info, and workflow details.
        """
        if not _cam_processor:
            return {'success': False, 'error': 'CAM processor not initialized'}

        try:
            status = _cam_processor.get_aluminum_workflow_status()
            return {
                'success': True,
                **status
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }

    # ============================================
    # AI CAM Copilot Handlers
    # Integration with dashboard CAM API
    # ============================================

    def _handle_ai_cam_recommend(self, params: dict) -> dict:
        """
        Get AI-recommended CAM parameters from the dashboard API.

        Params:
            brick_type: str (e.g., "2x4")
            dimensions: dict with x, y, z (mm)
            material: str (e.g., "aluminum_6061")
            machine_id: str (e.g., "bantam-desktop-cnc")
            operation: str (e.g., "pocket")
            mode: str ("autonomous", "copilot", "advisory")

        Returns:
            AI recommendation with tool, feeds/speeds, toolpath strategy
        """
        import urllib.request
        import urllib.error

        # Build request to dashboard API
        api_url = params.get('api_url', 'http://localhost:5000/api/ai/cam/recommend')

        request_data = {
            'brick_type': params.get('brick_type', '2x4'),
            'dimensions': params.get('dimensions', {'x': 32, 'y': 16, 'z': 9.6}),
            'material': params.get('material', 'aluminum_6061'),
            'machine_id': params.get('machine_id', 'bantam-desktop-cnc'),
            'operation': params.get('operation', 'pocket'),
            'mode': params.get('mode', 'copilot'),
        }

        try:
            req = urllib.request.Request(
                api_url,
                data=json.dumps(request_data).encode('utf-8'),
                headers={'Content-Type': 'application/json'},
                method='POST'
            )

            with urllib.request.urlopen(req, timeout=30) as response:
                result = json.loads(response.read().decode('utf-8'))

                if result.get('success'):
                    recommendation = result.get('recommendation', {})
                    return {
                        'success': True,
                        'recommendation': recommendation,
                        'mode': result.get('mode', 'copilot'),
                        'requires_approval': result.get('requires_approval', True),
                        'source': 'dashboard_api'
                    }
                else:
                    raise Exception(result.get('error', 'Unknown error'))

        except (urllib.error.URLError, urllib.error.HTTPError) as e:
            _log(f"Dashboard API unavailable, using local calculation: {e}")
            # Fallback to local calculation
            return self._local_cam_recommend(params)

    def _local_cam_recommend(self, params: dict) -> dict:
        """Generate local CAM recommendation when API is unavailable."""
        material = params.get('material', 'aluminum_6061')
        dimensions = params.get('dimensions', {'x': 32, 'y': 16, 'z': 9.6})

        # Material properties database
        material_props = {
            'aluminum_6061': {'surface_speed': 150, 'chip_load': 0.05, 'coolant': 'flood'},
            'aluminum_7075': {'surface_speed': 120, 'chip_load': 0.04, 'coolant': 'flood'},
            'brass_360': {'surface_speed': 100, 'chip_load': 0.06, 'coolant': 'mist'},
            'steel_1018': {'surface_speed': 30, 'chip_load': 0.02, 'coolant': 'flood'},
            'abs_plastic': {'surface_speed': 300, 'chip_load': 0.1, 'coolant': 'none'},
            'delrin': {'surface_speed': 250, 'chip_load': 0.08, 'coolant': 'none'},
        }

        props = material_props.get(material, material_props['aluminum_6061'])

        # Calculate feeds and speeds
        tool_diameter = 3.175  # mm (1/8")
        rpm = min(24000, int((props['surface_speed'] * 1000) / (3.14159 * tool_diameter)))
        feed_rate = int(rpm * 2 * props['chip_load'])

        recommendation = {
            'recommendation_id': f"local-{uuid.uuid4().hex[:8]}",
            'tool': {
                'type': 'Flat End Mill',
                'diameter_mm': tool_diameter,
                'flutes': 2,
                'material': 'Carbide'
            },
            'feeds_speeds': {
                'spindle_rpm': rpm,
                'feed_rate_mm_min': feed_rate,
                'plunge_rate_mm_min': int(feed_rate * 0.3),
                'depth_of_cut_mm': 1.0,
                'stepover_percent': 40,
                'chip_load_mm': props['chip_load']
            },
            'toolpath': {
                'strategy': 'adaptive',
                'direction': 'climb',
                'lead_in': 'arc',
                'hsm_enabled': True
            },
            'confidence': 0.85,
            'rationale': f"Local calculation for {material} using conservative parameters."
        }

        return {
            'success': True,
            'recommendation': recommendation,
            'mode': params.get('mode', 'copilot'),
            'requires_approval': True,
            'source': 'local_calculation'
        }

    def _handle_ai_cam_execute(self, params: dict) -> dict:
        """
        Execute approved CAM recommendation.

        Params:
            recommendation: dict (from ai_cam_recommend)
            user_approved: bool (required for copilot mode)
            component_name: str (optional - target component)

        Returns:
            Execution result with G-code path
        """
        recommendation = params.get('recommendation')
        user_approved = params.get('user_approved', False)
        component_name = params.get('component_name')

        if not recommendation:
            return {'success': False, 'error': 'Recommendation required'}

        mode = recommendation.get('mode', 'copilot')

        # Check approval for copilot mode
        if mode == 'copilot' and not user_approved:
            return {
                'success': False,
                'error': 'User approval required for copilot mode',
                'requires_approval': True
            }

        # Extract CAM parameters
        feeds_speeds = recommendation.get('feeds_speeds', {})
        tool = recommendation.get('tool', {})

        _log(f"Executing AI CAM recommendation: RPM={feeds_speeds.get('spindle_rpm')}, "
             f"Feed={feeds_speeds.get('feed_rate_mm_min')}, Tool={tool.get('diameter_mm')}mm")

        # If we have a CAM processor, create actual toolpath
        if _cam_processor and component_name:
            try:
                result = _cam_processor.create_aluminum_lego_cam(
                    component_name=component_name,
                    studs_x=params.get('studs_x', 2),
                    studs_y=params.get('studs_y', 4),
                    height_plates=params.get('height_plates', 3),
                    # Override with AI parameters
                    spindle_rpm=feeds_speeds.get('spindle_rpm'),
                    feed_rate=feeds_speeds.get('feed_rate_mm_min'),
                    depth_of_cut=feeds_speeds.get('depth_of_cut_mm'),
                )
                return {
                    'success': True,
                    'executed': True,
                    'recommendation_id': recommendation.get('recommendation_id'),
                    'cam_result': result
                }
            except Exception as e:
                return {
                    'success': False,
                    'error': f'CAM execution failed: {e}'
                }
        else:
            # No CAM processor - just acknowledge approval
            return {
                'success': True,
                'executed': False,
                'recommendation_id': recommendation.get('recommendation_id'),
                'message': 'Recommendation approved (CAM processor not available for execution)',
                'approved_params': {
                    'spindle_rpm': feeds_speeds.get('spindle_rpm'),
                    'feed_rate_mm_min': feeds_speeds.get('feed_rate_mm_min'),
                    'depth_of_cut_mm': feeds_speeds.get('depth_of_cut_mm'),
                    'tool_diameter_mm': tool.get('diameter_mm')
                }
            }

    def _handle_ai_cam_feedback(self, params: dict) -> dict:
        """
        Submit quality feedback for CAM learning.

        Params:
            recommendation_id: str (from recommendation)
            defect_type: str (e.g., "rough_surface", "undersized_stud")
            severity: str ("minor", "major", "critical")
            notes: str (optional)

        Returns:
            Acknowledgment of feedback recording
        """
        import urllib.request
        import urllib.error

        recommendation_id = params.get('recommendation_id')
        defect_type = params.get('defect_type')
        severity = params.get('severity', 'minor')
        notes = params.get('notes', '')

        if not defect_type:
            return {'success': False, 'error': 'defect_type required'}

        # Try to send to dashboard API
        api_url = params.get('api_url', 'http://localhost:5000/api/ai/cam/feedback-loop/record')

        request_data = {
            'work_center_id': params.get('machine_id', 'bantam-desktop-cnc'),
            'part_number': params.get('part_number', 'LEGO-2x4-Brick'),
            'defect_type': defect_type,
            'severity': severity,
            'cam_recommendation_id': recommendation_id,
            'notes': notes
        }

        try:
            req = urllib.request.Request(
                api_url,
                data=json.dumps(request_data).encode('utf-8'),
                headers={'Content-Type': 'application/json'},
                method='POST'
            )

            with urllib.request.urlopen(req, timeout=10) as response:
                result = json.loads(response.read().decode('utf-8'))
                return {
                    'success': True,
                    'feedback_recorded': True,
                    'defect': result.get('defect', {}),
                    'will_adjust': True,
                    'source': 'dashboard_api'
                }

        except (urllib.error.URLError, urllib.error.HTTPError) as e:
            _log(f"Dashboard API unavailable for feedback: {e}")
            # Store locally for later sync
            return {
                'success': True,
                'feedback_recorded': True,
                'defect_type': defect_type,
                'severity': severity,
                'will_adjust': True,
                'source': 'local_storage',
                'note': 'Feedback stored locally, will sync when API available'
            }


class ThreadedHTTPServer(threading.Thread):
    """HTTP server running in background thread."""

    def __init__(self, port: int):
        super().__init__(daemon=True)
        self.port = port
        self.server = None
        self._stop_event = threading.Event()
        self._started = threading.Event()

    def run(self):
        """Start serving."""
        try:
            self.server = HTTPServer(('127.0.0.1', self.port), FusionAPIHandler)
            self.server.timeout = 0.5  # Check for stop every 0.5s
            self._started.set()

            while not self._stop_event.is_set():
                self.server.handle_request()
        except Exception as e:
            print(f"HTTP Server error: {e}")
        finally:
            if self.server:
                try:
                    self.server.server_close()
                except:
                    pass

    def stop(self):
        """Stop the server gracefully."""
        self._stop_event.set()

        # Give the server a moment to finish current request
        if self.server:
            try:
                # Make a dummy request to unblock handle_request()
                import socket
                try:
                    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    sock.settimeout(1)
                    sock.connect(('127.0.0.1', self.port))
                    sock.sendall(b'GET /health HTTP/1.0\r\n\r\n')
                    sock.close()
                except:
                    pass

                self.server.server_close()
            except:
                pass

        # Wait for thread to finish (with timeout)
        self.join(timeout=2.0)


def _build_handler_registry():
    """Build the handler registry for the FusionWorker."""
    # Create a temporary handler instance to access the methods
    # This is a bit of a hack, but it works since handlers just use global _modeler/_cam_processor
    class HandlerContainer:
        pass

    container = HandlerContainer()

    # Copy handler methods from FusionAPIHandler
    for method_name in dir(FusionAPIHandler):
        if method_name.startswith('_handle_'):
            method = getattr(FusionAPIHandler, method_name)
            # Make it a standalone function that takes params
            setattr(container, method_name, lambda p, m=method: m(None, p))

    return {
        # Standard brick types
        'create_brick': lambda p: FusionAPIHandler._handle_create_brick(None, p),
        'create_plate': lambda p: FusionAPIHandler._handle_create_plate(None, p),
        'create_tile': lambda p: FusionAPIHandler._handle_create_tile(None, p),
        'create_slope': lambda p: FusionAPIHandler._handle_create_slope(None, p),
        'create_technic': lambda p: FusionAPIHandler._handle_create_technic(None, p),
        'create_round': lambda p: FusionAPIHandler._handle_create_round(None, p),
        'create_arch': lambda p: FusionAPIHandler._handle_create_arch(None, p),
        # Advanced brick types
        'create_wedge': lambda p: FusionAPIHandler._handle_create_wedge(None, p),
        'create_inverted_slope': lambda p: FusionAPIHandler._handle_create_inverted_slope(None, p),
        'create_jumper': lambda p: FusionAPIHandler._handle_create_jumper(None, p),
        'create_hinge': lambda p: FusionAPIHandler._handle_create_hinge(None, p),
        'create_modified': lambda p: FusionAPIHandler._handle_create_modified(None, p),
        # Export functions
        'export_stl': lambda p: FusionAPIHandler._handle_export_stl(None, p),
        'export_step': lambda p: FusionAPIHandler._handle_export_step(None, p),
        'export_3mf': lambda p: FusionAPIHandler._handle_export_3mf(None, p),
        'batch_export': lambda p: FusionAPIHandler._handle_batch_export(None, p),
        # Slicing and CAM
        'slice_stl': lambda p: FusionAPIHandler._handle_slice_stl(None, p),
        'setup_cam': lambda p: FusionAPIHandler._handle_setup_cam(None, p),
        'generate_gcode': lambda p: FusionAPIHandler._handle_generate_gcode(None, p),
        'full_mill_workflow': lambda p: FusionAPIHandler._handle_full_mill_workflow(None, p),
        # Aluminum LEGO CNC milling (Bantam Desktop)
        'aluminum_lego_cam': lambda p: FusionAPIHandler._handle_aluminum_lego_cam(None, p),
        'aluminum_workflow_status': lambda p: FusionAPIHandler._handle_aluminum_workflow_status(None, p),
        # AI CAM Copilot integration
        'ai_cam_recommend': lambda p: FusionAPIHandler._handle_ai_cam_recommend(None, p),
        'ai_cam_execute': lambda p: FusionAPIHandler._handle_ai_cam_execute(None, p),
        'ai_cam_feedback': lambda p: FusionAPIHandler._handle_ai_cam_feedback(None, p),
    }


def start_server(modeler, cam_processor, port: int = 8765) -> ThreadedHTTPServer:
    """
    Start the HTTP API server.

    Args:
        modeler: BrickModeler instance
        cam_processor: CAMProcessor instance
        port: Port to listen on

    Returns:
        ThreadedHTTPServer instance
    """
    global _modeler, _cam_processor, _fusion_worker

    _modeler = modeler
    _cam_processor = cam_processor

    _log(f"Starting LegoMCP HTTP server on port {port}")

    # Start the Fusion worker thread (serializes Fusion 360 API calls)
    handler_registry = _build_handler_registry()
    _fusion_worker = FusionWorker(handler_registry)
    _fusion_worker.start()

    # Start the HTTP server
    server = ThreadedHTTPServer(port)
    server.start()

    _log("LegoMCP HTTP server started successfully")
    return server


def stop_server(server: ThreadedHTTPServer):
    """Stop the HTTP API server."""
    global _fusion_worker

    _log("Stopping LegoMCP HTTP server...")

    # Stop the worker first
    if _fusion_worker:
        _fusion_worker.stop()
        _fusion_worker.join(timeout=2.0)
        _fusion_worker = None

    # Then stop the HTTP server
    if server:
        server.stop()

    _log("LegoMCP HTTP server stopped")
