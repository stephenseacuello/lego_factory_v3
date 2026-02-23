"""
CNC Milling Routes - Aluminum LEGO Manufacturing API

Endpoints for CNC machining operations:
- Aluminum brick workflow generation
- G-code generation for Bantam CNC
- Setup sheet creation
- Feeds/speeds calculation
"""

from flask import Blueprint, request, jsonify, Response
import sys
import os
from pathlib import Path
from datetime import datetime

# Add mcp-server tools to path
MCP_TOOLS = Path(__file__).parent.parent.parent.parent.parent / "mcp-server" / "src" / "tools"
sys.path.insert(0, str(MCP_TOOLS))

# Organized output directory - use /output mount for Docker, fallback to home for local dev
OUTPUT_BASE = Path("/output/cnc/aluminum") if Path("/output").exists() else Path.home() / "Documents" / "LegoMCP" / "exports" / "cnc" / "aluminum"

cnc_bp = Blueprint('cnc', __name__, url_prefix='/cnc')


@cnc_bp.route('/page', methods=['GET'])
def cnc_page():
    """CNC milling dashboard page."""
    from flask import render_template
    return render_template('pages/manufacturing/cnc_milling.html')


@cnc_bp.route('/aluminum-lego', methods=['POST'])
def create_aluminum_lego():
    """
    Generate complete aluminum LEGO brick milling workflow.

    Request Body:
        width_studs: int (1-8, default 2)
        depth_studs: int (1-8, default 4)
        height_plates: int (1-9, default 3)
        z_offset: float (0.5-3.0, default 1.0)

    Returns:
        Complete workflow with G-code, setup sheets, and parameters
    """
    try:
        from aluminum_lego_mill import create_aluminum_lego, get_bantam_specs

        data = request.get_json() or {}

        width_studs = min(max(int(data.get('width_studs', 2)), 1), 8)
        depth_studs = min(max(int(data.get('depth_studs', 4)), 1), 8)
        height_plates = min(max(int(data.get('height_plates', 3)), 1), 9)
        z_offset = min(max(float(data.get('z_offset', 1.0)), 0.5), 3.0)

        # Check if brick fits Bantam work envelope
        specs = get_bantam_specs()
        brick_width = width_studs * 8.0
        brick_depth = depth_studs * 8.0
        brick_height = height_plates * 3.2 + z_offset

        if brick_width > specs["work_envelope"]["x"]:
            return jsonify({
                "success": False,
                "error": f"Brick too wide ({brick_width}mm) for Bantam ({specs['work_envelope']['x']}mm)"
            }), 400

        if brick_depth > specs["work_envelope"]["y"]:
            return jsonify({
                "success": False,
                "error": f"Brick too deep ({brick_depth}mm) for Bantam ({specs['work_envelope']['y']}mm)"
            }), 400

        if brick_height > specs["work_envelope"]["z"]:
            return jsonify({
                "success": False,
                "error": f"Brick too tall ({brick_height}mm) for Bantam Z travel ({specs['work_envelope']['z']}mm)"
            }), 400

        # Generate workflow
        result = create_aluminum_lego(
            width_studs=width_studs,
            depth_studs=depth_studs,
            height_plates=height_plates,
            z_offset=z_offset
        )

        # Create organized output directory
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        brick_name = f"LEGO_{width_studs}x{depth_studs}"
        job_dir = OUTPUT_BASE / f"{brick_name}_{timestamp}"
        job_dir.mkdir(parents=True, exist_ok=True)

        # Save ALL G-code files (SETUP1 and SETUP2)
        saved_files = []
        for filename, gcode_content in result["gcode_files"].items():
            file_path = job_dir / filename
            with open(file_path, 'w') as f:
                f.write(gcode_content)
            saved_files.append({
                "filename": filename,
                "path": str(file_path),
                "size_bytes": len(gcode_content)
            })

        # Save setup sheet
        setup_sheet_path = job_dir / f"{brick_name}_setup_sheet.txt"
        with open(setup_sheet_path, 'w') as f:
            f.write(result["setup_sheet"])
        saved_files.append({
            "filename": f"{brick_name}_setup_sheet.txt",
            "path": str(setup_sheet_path),
            "size_bytes": len(result["setup_sheet"])
        })

        return jsonify({
            "success": True,
            "data": {
                "brick": result["brick"],
                "stock": result["stock"],
                "setups": result["setups"],
                "summary": result["summary"],
                "gcode_files": list(result["gcode_files"].keys()),
                "saved_files": saved_files,
                "output_dir": str(job_dir),
            }
        })

    except ImportError as e:
        return jsonify({
            "success": False,
            "error": f"Milling module not available: {e}"
        }), 500
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@cnc_bp.route('/aluminum-lego/gcode/<filename>', methods=['GET'])
def get_gcode_file(filename: str):
    """
    Get generated G-code file content.

    Path Parameters:
        filename: G-code filename (e.g., LEGO_2x4_SETUP1.nc)

    Query Parameters:
        width_studs, depth_studs, height_plates, z_offset (to regenerate)

    Returns:
        G-code file as text/plain
    """
    try:
        from aluminum_lego_mill import create_aluminum_lego

        width_studs = int(request.args.get('width_studs', 2))
        depth_studs = int(request.args.get('depth_studs', 4))
        height_plates = int(request.args.get('height_plates', 3))
        z_offset = float(request.args.get('z_offset', 1.0))

        result = create_aluminum_lego(
            width_studs=width_studs,
            depth_studs=depth_studs,
            height_plates=height_plates,
            z_offset=z_offset
        )

        gcode_files = result["gcode_files"]

        if filename not in gcode_files:
            return jsonify({
                "success": False,
                "error": f"File not found. Available: {list(gcode_files.keys())}"
            }), 404

        return Response(
            gcode_files[filename],
            mimetype='text/plain',
            headers={
                'Content-Disposition': f'attachment; filename={filename}'
            }
        )

    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@cnc_bp.route('/aluminum-lego/setup-sheet', methods=['GET'])
def get_setup_sheet():
    """
    Get human-readable setup sheet.

    Query Parameters:
        width_studs, depth_studs, height_plates, z_offset

    Returns:
        Setup sheet as text/plain
    """
    try:
        from aluminum_lego_mill import create_aluminum_lego

        width_studs = int(request.args.get('width_studs', 2))
        depth_studs = int(request.args.get('depth_studs', 4))
        height_plates = int(request.args.get('height_plates', 3))
        z_offset = float(request.args.get('z_offset', 1.0))

        result = create_aluminum_lego(
            width_studs=width_studs,
            depth_studs=depth_studs,
            height_plates=height_plates,
            z_offset=z_offset
        )

        return Response(
            result["setup_sheet"],
            mimetype='text/plain',
            headers={
                'Content-Disposition': f'attachment; filename=LEGO_{width_studs}x{depth_studs}_setup_sheet.txt'
            }
        )

    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@cnc_bp.route('/feeds-speeds', methods=['POST'])
def calculate_feeds_speeds():
    """
    Calculate feeds and speeds for aluminum on Bantam.

    Request Body:
        tool_diameter: float (mm)
        flutes: int (default 2)
        material: str (default "aluminum")

    Returns:
        RPM, feed rate, plunge rate
    """
    try:
        from aluminum_lego_mill import AluminumLegoMill

        data = request.get_json() or {}

        tool_diameter = float(data.get('tool_diameter', 3.0))
        flutes = int(data.get('flutes', 2))

        mill = AluminumLegoMill()
        result = mill.calculate_feeds_speeds(tool_diameter, flutes)

        return jsonify({
            "success": True,
            "data": {
                "tool_diameter": tool_diameter,
                "flutes": flutes,
                "material": "6061-T6 Aluminum",
                "rpm": result["rpm"],
                "feed_rate_mm_min": result["feed_rate"],
                "feed_rate_ipm": round(result["feed_rate"] / 25.4, 2),
                "plunge_rate_mm_min": result["plunge_rate"],
                "chip_load_mm": result["chip_load"],
            }
        })

    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@cnc_bp.route('/bantam/specs', methods=['GET'])
def get_bantam_specifications():
    """Get Bantam Desktop CNC specifications."""
    try:
        from aluminum_lego_mill import get_bantam_specs, get_aluminum_params

        return jsonify({
            "success": True,
            "data": {
                "machine": get_bantam_specs(),
                "aluminum_params": get_aluminum_params(),
            }
        })

    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@cnc_bp.route('/bantam/max-brick-size', methods=['GET'])
def get_max_brick_size():
    """Get maximum brick size that fits Bantam work envelope."""
    try:
        from aluminum_lego_mill import get_bantam_specs, LEGO_DIMS

        specs = get_bantam_specs()
        envelope = specs["work_envelope"]

        max_width_studs = int(envelope["x"] / LEGO_DIMS["pitch"])
        max_depth_studs = int(envelope["y"] / LEGO_DIMS["pitch"])
        max_height_plates = int((envelope["z"] - 5) / LEGO_DIMS["plate_height"])

        return jsonify({
            "success": True,
            "data": {
                "max_width_studs": max_width_studs,
                "max_depth_studs": max_depth_studs,
                "max_height_plates": max_height_plates,
                "work_envelope_mm": envelope,
                "notes": [
                    f"Maximum brick: {max_width_studs}x{max_depth_studs} studs",
                    f"Maximum height: {max_height_plates} plates ({max_height_plates * 3.2}mm)",
                    "Allow 5mm clearance for tools and workholding",
                ]
            }
        })

    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500
