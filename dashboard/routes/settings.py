"""
Settings Routes

Application settings and preferences.
"""

from flask import Blueprint, render_template, request, jsonify, session
from services.mcp_bridge import MCPBridge

settings_bp = Blueprint("settings", __name__)

# Default settings
DEFAULT_SETTINGS = {
    "theme": "auto",
    "sidebar_collapsed": False,
    "catalog_view": "grid",
    "items_per_page": 48,
    "fusion_url": "http://127.0.0.1:8767",
    "slicer_url": "http://localhost:8766",
    "connection_timeout": 30,
    "default_printer": "prusa_mk3s",
    "default_material": "pla_generic",
    "default_quality": "lego",
    "stl_refinement": "high",
    "auto_export": False,
    "output_directory": "/output",
}


@settings_bp.route("/")
def settings_page():
    """Settings page."""
    # Get current settings from session or defaults
    settings = {**DEFAULT_SETTINGS}
    for key in DEFAULT_SETTINGS:
        if key in session:
            settings[key] = session[key]

    # Get available options
    printers_result = MCPBridge.execute_tool("list_printers", {})
    printers = (
        printers_result.get("result", {}).get("printers", [])
        if printers_result.get("success")
        else []
    )

    materials_result = MCPBridge.execute_tool("list_materials", {})
    materials = (
        materials_result.get("result", {}).get("materials", [])
        if materials_result.get("success")
        else []
    )

    return render_template(
        "pages/settings.html",
        settings=settings,
        printers=printers,
        materials=materials,
        themes=["auto", "light", "dark"],
        stl_qualities=["low", "medium", "high", "ultra"],
        quality_presets=["draft", "normal", "quality", "ultra", "lego"],
    )


@settings_bp.route("/save", methods=["POST"])
def save_settings():
    """Save settings."""
    data = request.get_json()

    # Update session with new settings
    for key, value in data.items():
        if key in DEFAULT_SETTINGS:
            session[key] = value

    session.modified = True

    return jsonify({"success": True, "message": "Settings saved"})


@settings_bp.route("/get")
def get_settings():
    """Get current settings."""
    settings = {**DEFAULT_SETTINGS}
    for key in DEFAULT_SETTINGS:
        if key in session:
            settings[key] = session[key]

    return jsonify(settings)


@settings_bp.route("/reset", methods=["POST"])
def reset_settings():
    """Reset settings to defaults."""
    for key in DEFAULT_SETTINGS:
        if key in session:
            del session[key]

    session.modified = True

    return jsonify(
        {"success": True, "message": "Settings reset to defaults", "settings": DEFAULT_SETTINGS}
    )


@settings_bp.route("/theme", methods=["POST"])
def set_theme():
    """Set theme quickly."""
    data = request.get_json()
    theme = data.get("theme", "auto")

    if theme in ["auto", "light", "dark"]:
        session["theme"] = theme
        session.modified = True
        return jsonify({"success": True, "theme": theme})

    return jsonify({"success": False, "error": "Invalid theme"})
