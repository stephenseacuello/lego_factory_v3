"""
V8 Health Check Aggregator Routes
==================================

Unified health monitoring endpoints for:
- Service health checks
- Infrastructure monitoring
- Dependency status
- Kubernetes/Docker health probes
- Performance metrics summary

Endpoints:
- /health - Basic health check (for load balancers)
- /health/ready - Readiness probe (Kubernetes)
- /health/live - Liveness probe (Kubernetes)
- /health/detailed - Full system health report
- /health/services - Individual service status
- /health/metrics - Health metrics summary

Author: LEGO MCP Engineering Team
Version: 8.0.0
"""

from flask import Blueprint, jsonify, request
from datetime import datetime, timedelta
import asyncio
import logging
import os
import psutil
import threading
import time
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)

health_bp = Blueprint('health', __name__, url_prefix='/health')


# ============================================
# Health Status Enums
# ============================================

class HealthStatus(Enum):
    """Health status levels."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


class CheckType(Enum):
    """Health check types."""
    LIVENESS = "liveness"
    READINESS = "readiness"
    STARTUP = "startup"


# ============================================
# Data Classes
# ============================================

@dataclass
class HealthCheck:
    """Individual health check result."""
    name: str
    status: HealthStatus
    message: str = ""
    duration_ms: float = 0.0
    last_check: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "status": self.status.value,
            "message": self.message,
            "duration_ms": round(self.duration_ms, 2),
            "last_check": self.last_check.isoformat(),
            "metadata": self.metadata
        }


@dataclass
class SystemMetrics:
    """System resource metrics."""
    cpu_percent: float
    memory_percent: float
    disk_percent: float
    open_files: int
    thread_count: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "cpu_percent": round(self.cpu_percent, 1),
            "memory_percent": round(self.memory_percent, 1),
            "disk_percent": round(self.disk_percent, 1),
            "open_files": self.open_files,
            "thread_count": self.thread_count
        }


@dataclass
class HealthReport:
    """Aggregated health report."""
    status: HealthStatus
    checks: List[HealthCheck]
    system_metrics: Optional[SystemMetrics]
    timestamp: datetime = field(default_factory=datetime.now)
    version: str = "8.0.0"
    uptime_seconds: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status.value,
            "checks": [c.to_dict() for c in self.checks],
            "system_metrics": self.system_metrics.to_dict() if self.system_metrics else None,
            "timestamp": self.timestamp.isoformat(),
            "version": self.version,
            "uptime_seconds": round(self.uptime_seconds, 1)
        }


# ============================================
# Health Check Registry
# ============================================

_start_time = datetime.now()
_health_checks: Dict[str, callable] = {}
_check_results: Dict[str, HealthCheck] = {}
_check_lock = threading.Lock()


def register_health_check(name: str, check_func: callable):
    """Register a health check function."""
    _health_checks[name] = check_func
    logger.info(f"Registered health check: {name}")


def unregister_health_check(name: str):
    """Unregister a health check."""
    if name in _health_checks:
        del _health_checks[name]


# ============================================
# Built-in Health Checks
# ============================================

def check_database() -> HealthCheck:
    """Check database connectivity."""
    start = time.time()
    try:
        # Try to import and check database
        from models import db
        db.session.execute("SELECT 1")
        duration = (time.time() - start) * 1000

        return HealthCheck(
            name="database",
            status=HealthStatus.HEALTHY,
            message="Database connection OK",
            duration_ms=duration
        )
    except Exception as e:
        duration = (time.time() - start) * 1000
        return HealthCheck(
            name="database",
            status=HealthStatus.UNHEALTHY,
            message=f"Database error: {str(e)}",
            duration_ms=duration
        )


def check_redis() -> HealthCheck:
    """Check Redis connectivity."""
    start = time.time()
    try:
        import redis
        redis_url = os.environ.get("REDIS_URL", "redis://redis:6379/0")
        r = redis.from_url(redis_url)
        r.ping()
        duration = (time.time() - start) * 1000

        return HealthCheck(
            name="redis",
            status=HealthStatus.HEALTHY,
            message="Redis connection OK",
            duration_ms=duration
        )
    except Exception as e:
        duration = (time.time() - start) * 1000
        return HealthCheck(
            name="redis",
            status=HealthStatus.DEGRADED,
            message=f"Redis unavailable: {str(e)}",
            duration_ms=duration
        )


def check_celery() -> HealthCheck:
    """Check Celery worker status."""
    start = time.time()
    try:
        from worker import celery_app
        inspect = celery_app.control.inspect()
        stats = inspect.stats()
        duration = (time.time() - start) * 1000

        if stats:
            worker_count = len(stats)
            return HealthCheck(
                name="celery",
                status=HealthStatus.HEALTHY,
                message=f"{worker_count} worker(s) active",
                duration_ms=duration,
                metadata={"worker_count": worker_count}
            )
        else:
            return HealthCheck(
                name="celery",
                status=HealthStatus.DEGRADED,
                message="No active workers",
                duration_ms=duration
            )
    except Exception as e:
        duration = (time.time() - start) * 1000
        return HealthCheck(
            name="celery",
            status=HealthStatus.DEGRADED,
            message=f"Celery check failed: {str(e)}",
            duration_ms=duration
        )


def check_mcp_server() -> HealthCheck:
    """Check MCP server connectivity."""
    start = time.time()
    try:
        from services.mcp_bridge import get_mcp_status
        status = get_mcp_status()
        duration = (time.time() - start) * 1000

        if status.get("connected"):
            return HealthCheck(
                name="mcp_server",
                status=HealthStatus.HEALTHY,
                message="MCP server connected",
                duration_ms=duration
            )
        else:
            return HealthCheck(
                name="mcp_server",
                status=HealthStatus.DEGRADED,
                message="MCP server disconnected",
                duration_ms=duration
            )
    except Exception as e:
        duration = (time.time() - start) * 1000
        return HealthCheck(
            name="mcp_server",
            status=HealthStatus.DEGRADED,
            message=f"MCP check failed: {str(e)}",
            duration_ms=duration
        )


def check_ros2() -> HealthCheck:
    """Check ROS2 connectivity."""
    start = time.time()
    try:
        from services.command_center import get_ros2_command_center
        ros2 = get_ros2_command_center()
        data = ros2.get_dashboard_data()
        duration = (time.time() - start) * 1000

        if data.get("connected"):
            return HealthCheck(
                name="ros2",
                status=HealthStatus.HEALTHY,
                message="ROS2 bridge connected",
                duration_ms=duration,
                metadata={"equipment_count": data.get("equipment_count", 0)}
            )
        else:
            return HealthCheck(
                name="ros2",
                status=HealthStatus.DEGRADED,
                message="ROS2 bridge disconnected",
                duration_ms=duration
            )
    except Exception as e:
        duration = (time.time() - start) * 1000
        return HealthCheck(
            name="ros2",
            status=HealthStatus.DEGRADED,
            message=f"ROS2 check failed: {str(e)}",
            duration_ms=duration
        )


def check_fusion360() -> HealthCheck:
    """Check Fusion 360 add-in connectivity."""
    start = time.time()
    try:
        from services.mcp_bridge import check_fusion360_status
        connected = check_fusion360_status()
        duration = (time.time() - start) * 1000

        if connected:
            return HealthCheck(
                name="fusion360",
                status=HealthStatus.HEALTHY,
                message="Fusion 360 add-in connected",
                duration_ms=duration
            )
        else:
            return HealthCheck(
                name="fusion360",
                status=HealthStatus.DEGRADED,
                message="Fusion 360 add-in disconnected",
                duration_ms=duration
            )
    except Exception as e:
        duration = (time.time() - start) * 1000
        return HealthCheck(
            name="fusion360",
            status=HealthStatus.DEGRADED,
            message=f"Fusion 360 check failed: {str(e)}",
            duration_ms=duration
        )


def get_system_metrics() -> SystemMetrics:
    """Get system resource metrics."""
    try:
        process = psutil.Process()

        return SystemMetrics(
            cpu_percent=psutil.cpu_percent(interval=0.1),
            memory_percent=psutil.virtual_memory().percent,
            disk_percent=psutil.disk_usage('/').percent,
            open_files=len(process.open_files()),
            thread_count=threading.active_count()
        )
    except Exception as e:
        logger.warning(f"Failed to get system metrics: {e}")
        return SystemMetrics(
            cpu_percent=0,
            memory_percent=0,
            disk_percent=0,
            open_files=0,
            thread_count=0
        )


# Register built-in checks
register_health_check("database", check_database)
register_health_check("redis", check_redis)
register_health_check("celery", check_celery)
register_health_check("mcp_server", check_mcp_server)
register_health_check("ros2", check_ros2)
register_health_check("fusion360", check_fusion360)


# ============================================
# Health Aggregation
# ============================================

def run_all_checks(timeout_seconds: float = 10.0) -> List[HealthCheck]:
    """Run all registered health checks."""
    results = []

    for name, check_func in _health_checks.items():
        try:
            result = check_func()
            results.append(result)

            # Cache result
            with _check_lock:
                _check_results[name] = result

        except Exception as e:
            logger.error(f"Health check '{name}' failed: {e}")
            results.append(HealthCheck(
                name=name,
                status=HealthStatus.UNKNOWN,
                message=f"Check failed: {str(e)}"
            ))

    return results


def get_cached_check(name: str) -> Optional[HealthCheck]:
    """Get cached health check result."""
    with _check_lock:
        return _check_results.get(name)


def aggregate_status(checks: List[HealthCheck]) -> HealthStatus:
    """Determine overall status from individual checks."""
    if not checks:
        return HealthStatus.UNKNOWN

    statuses = [c.status for c in checks]

    if HealthStatus.UNHEALTHY in statuses:
        return HealthStatus.UNHEALTHY
    elif HealthStatus.DEGRADED in statuses:
        return HealthStatus.DEGRADED
    elif HealthStatus.UNKNOWN in statuses:
        return HealthStatus.DEGRADED
    else:
        return HealthStatus.HEALTHY


def generate_health_report(include_metrics: bool = True) -> HealthReport:
    """Generate comprehensive health report."""
    checks = run_all_checks()
    status = aggregate_status(checks)

    uptime = (datetime.now() - _start_time).total_seconds()

    return HealthReport(
        status=status,
        checks=checks,
        system_metrics=get_system_metrics() if include_metrics else None,
        uptime_seconds=uptime
    )


# ============================================
# Flask Routes
# ============================================

@health_bp.route('')
@health_bp.route('/')
def basic_health():
    """Basic health check for load balancers."""
    return jsonify({
        "status": "ok",
        "timestamp": datetime.now().isoformat()
    })


@health_bp.route('/live')
def liveness_probe():
    """Kubernetes liveness probe.

    Returns 200 if the application is running.
    Used to restart unhealthy pods.
    """
    return jsonify({
        "status": "ok",
        "check_type": "liveness",
        "timestamp": datetime.now().isoformat()
    })


@health_bp.route('/ready')
def readiness_probe():
    """Kubernetes readiness probe.

    Returns 200 if the application is ready to receive traffic.
    Checks critical dependencies.
    """
    # Only check critical dependencies for readiness
    critical_checks = ["database"]
    all_ready = True
    check_results = []

    for check_name in critical_checks:
        if check_name in _health_checks:
            result = _health_checks[check_name]()
            check_results.append(result.to_dict())
            if result.status == HealthStatus.UNHEALTHY:
                all_ready = False

    if all_ready:
        return jsonify({
            "status": "ready",
            "check_type": "readiness",
            "checks": check_results,
            "timestamp": datetime.now().isoformat()
        })
    else:
        return jsonify({
            "status": "not_ready",
            "check_type": "readiness",
            "checks": check_results,
            "timestamp": datetime.now().isoformat()
        }), 503


@health_bp.route('/detailed')
def detailed_health():
    """Full system health report."""
    include_metrics = request.args.get('metrics', 'true').lower() == 'true'
    report = generate_health_report(include_metrics=include_metrics)

    status_code = 200 if report.status == HealthStatus.HEALTHY else 503
    if report.status == HealthStatus.DEGRADED:
        status_code = 200  # Degraded is still operational

    return jsonify(report.to_dict()), status_code


@health_bp.route('/services')
def services_health():
    """Individual service status."""
    service = request.args.get('service')

    if service:
        # Check specific service
        if service in _health_checks:
            result = _health_checks[service]()
            return jsonify({
                "service": service,
                "check": result.to_dict()
            })
        else:
            return jsonify({
                "error": f"Unknown service: {service}",
                "available_services": list(_health_checks.keys())
            }), 404
    else:
        # List all services with cached status
        services = {}
        for name in _health_checks.keys():
            cached = get_cached_check(name)
            if cached:
                services[name] = cached.to_dict()
            else:
                services[name] = {"status": "unchecked"}

        return jsonify({
            "services": services,
            "count": len(services)
        })


@health_bp.route('/metrics')
def health_metrics():
    """Health metrics summary for monitoring."""
    metrics = get_system_metrics()
    uptime = (datetime.now() - _start_time).total_seconds()

    # Get check status counts
    checks = run_all_checks()
    status_counts = {
        "healthy": 0,
        "degraded": 0,
        "unhealthy": 0,
        "unknown": 0
    }
    for check in checks:
        status_counts[check.status.value] += 1

    return jsonify({
        "system": metrics.to_dict(),
        "checks": status_counts,
        "uptime_seconds": round(uptime, 1),
        "timestamp": datetime.now().isoformat()
    })


@health_bp.route('/startup')
def startup_probe():
    """Kubernetes startup probe.

    Returns 200 once the application has fully started.
    """
    uptime = (datetime.now() - _start_time).total_seconds()

    # Consider started after 5 seconds
    if uptime >= 5:
        return jsonify({
            "status": "started",
            "check_type": "startup",
            "uptime_seconds": round(uptime, 1),
            "timestamp": datetime.now().isoformat()
        })
    else:
        return jsonify({
            "status": "starting",
            "check_type": "startup",
            "uptime_seconds": round(uptime, 1),
            "timestamp": datetime.now().isoformat()
        }), 503


# ============================================
# Command Center Integration
# ============================================

@health_bp.route('/command-center')
def command_center_health():
    """Health status for command center dashboard."""
    try:
        from services.command_center import SystemHealthService

        service = SystemHealthService()

        # Run async health check
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            summary = loop.run_until_complete(service.check_all())
        finally:
            loop.close()

        return jsonify({
            "success": True,
            "data": summary.to_dict()
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


__all__ = [
    'health_bp',
    'HealthStatus',
    'HealthCheck',
    'HealthReport',
    'SystemMetrics',
    'register_health_check',
    'unregister_health_check',
    'generate_health_report',
    'run_all_checks',
    'get_system_metrics',
]
