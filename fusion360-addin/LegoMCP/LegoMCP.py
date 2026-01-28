"""
LegoMCP - Fusion 360 Add-in
Main entry point for the LEGO MCP Fusion 360 integration.

This add-in:
1. Starts a local HTTP server to receive commands from the MCP server
2. Provides parametric LEGO brick modeling
3. Handles CAM setup and G-code generation for milling
4. Exports STL files for 3D printing
"""

import adsk.core
import adsk.fusion
import adsk.cam
import traceback
import threading

# Version string - increment this when making code changes to verify reload
VERSION = "1.10.1-technic-symmetric-cut"

# HTTP server port - changed from 8765 to avoid Docker conflicts
HTTP_PORT = 8767

# Global references to keep objects alive
_app = None
_ui = None
_handlers = []
_http_server = None

# Add the add-in directory to path for imports
import os
import sys
ADDIN_DIR = os.path.dirname(os.path.realpath(__file__))
if ADDIN_DIR not in sys.path:
    sys.path.insert(0, ADDIN_DIR)

from api.http_server import start_server, stop_server
from core.brick_modeler import BrickModeler
from core.cam_processor import CAMProcessor


def run(context):
    """Entry point when add-in is started."""
    global _app, _ui, _http_server
    
    try:
        _app = adsk.core.Application.get()
        _ui = _app.userInterface
        
        # Initialize modeler
        modeler = BrickModeler(_app)
        
        # Initialize CAM processor with tool library
        tool_library_path = os.path.join(ADDIN_DIR, 'resources', 'tool_library.json')
        cam_processor = CAMProcessor(_app, tool_library_path)
        
        # Start HTTP server in background thread
        _http_server = start_server(
            modeler=modeler,
            cam_processor=cam_processor,
            port=HTTP_PORT
        )

        _ui.messageBox(
            f'LegoMCP Add-in Started! (v{VERSION})\n\n'
            f'HTTP API running on http://localhost:{HTTP_PORT}\n\n'
            'Ready to receive commands from MCP server.\n\n'
            'TIP: If you make code changes and they don\'t take effect,\n'
            'delete __pycache__ folders and restart Fusion 360.',
            'LegoMCP'
        )
        
    except:
        if _ui:
            _ui.messageBox(f'Failed to start LegoMCP:\n{traceback.format_exc()}')


def stop(context):
    """Entry point when add-in is stopped."""
    global _http_server, _ui, _app

    try:
        # Stop HTTP server first - this is the critical part
        if _http_server:
            try:
                stop_server(_http_server)
            except:
                pass  # Don't let server stop failure block shutdown
            _http_server = None

        # Clean up global references
        _app = None

        # Don't show message box on stop - it can cause UI freezes
        # Just silently stop

    except:
        # Never show message box on error during stop
        # It can cause Fusion to hang
        pass
