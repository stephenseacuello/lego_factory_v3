"""
Status Routes

System status, health monitoring, and error viewing.
"""

from flask import Blueprint, render_template, request, jsonify
from services.status_service import StatusService

status_bp = Blueprint("status", __name__)


@status_bp.route("/")
def status_page():
    """System status page."""
    # Get all status info
    status = StatusService.get_all_status(use_cache=False)
    circuits = StatusService.get_circuit_breakers()
    errors = StatusService.get_error_log(limit=20)
    error_stats = StatusService.get_error_stats()
    perf_stats = StatusService.get_performance_stats()
    mcp_info = StatusService.get_mcp_info()

    return render_template(
        "pages/status.html",
        status=status,
        circuits=circuits,
        errors=errors,
        error_stats=error_stats,
        perf_stats=perf_stats,
        mcp_info=mcp_info,
    )


@status_bp.route("/check")
def check_status():
    """Check all services status."""
    status = StatusService.get_all_status(use_cache=False)
    return jsonify(status)


@status_bp.route("/check/<service>")
def check_service(service):
    """Check a specific service."""
    result = StatusService.get_service_status(service)
    return jsonify({"service": service, **result})


@status_bp.route("/circuits")
def get_circuits():
    """Get circuit breaker states."""
    circuits = StatusService.get_circuit_breakers()
    return jsonify(circuits)


@status_bp.route("/circuits/<service>/reset", methods=["POST"])
def reset_circuit(service):
    """Reset a circuit breaker."""
    result = StatusService.reset_circuit_breaker(service)
    return jsonify(result)


@status_bp.route("/errors")
def get_errors():
    """Get error log."""
    limit = int(request.args.get("limit", 50))
    errors = StatusService.get_error_log(limit=limit)
    stats = StatusService.get_error_stats()

    return jsonify({"errors": errors, "stats": stats})


@status_bp.route("/performance")
def get_performance():
    """Get performance statistics."""
    stats = StatusService.get_performance_stats()
    return jsonify(stats)


@status_bp.route("/mcp")
def get_mcp_info():
    """Get MCP server information."""
    info = StatusService.get_mcp_info()
    return jsonify(info)
