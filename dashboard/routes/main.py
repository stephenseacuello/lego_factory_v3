"""
Main Routes

Dashboard home and general routes.
"""

from flask import Blueprint, render_template, jsonify
from services.catalog_service import CatalogService
from services.status_service import StatusService
from services.file_service import FileService

main_bp = Blueprint("main", __name__)


@main_bp.route("/")
def index():
    """Dashboard home page."""
    # Get quick stats
    catalog_stats = CatalogService.get_stats()
    status = StatusService.get_all_status()
    file_stats = FileService.get_storage_stats()

    # Get performance stats
    perf_stats = StatusService.get_performance_stats()

    # Get recent operations
    try:
        from services.mcp_bridge import MCPBridge

        history_result = MCPBridge.execute_tool("get_history", {"limit": 10})
        recent_ops = history_result.get("result", []) if history_result.get("success") else []
    except Exception:
        recent_ops = []

    # Get popular/common bricks
    popular_bricks = CatalogService.get_all_bricks(limit=8)["bricks"]

    return render_template(
        "pages/index.html",
        catalog_stats=catalog_stats,
        status=status,
        file_stats=file_stats,
        perf_stats=perf_stats,
        recent_ops=recent_ops,
        popular_bricks=popular_bricks,
    )


@main_bp.route("/about")
def about():
    """About page."""
    return render_template("pages/about.html")


@main_bp.route("/help")
def help_page():
    """Help page."""
    return render_template("pages/help.html")
