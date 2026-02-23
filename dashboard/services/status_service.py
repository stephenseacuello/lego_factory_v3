"""
Status Service

Monitors system health, circuit breakers, and service connections.
"""

import time
from typing import Dict, Any, List, Optional
from datetime import datetime
import threading

# Optional async support
try:
    import asyncio
    import aiohttp

    ASYNC_AVAILABLE = True
except ImportError:
    ASYNC_AVAILABLE = False


class StatusService:
    """Service for monitoring system health and status."""

    # Service endpoints
    SERVICES = {
        "fusion360": {
            "name": "Fusion 360",
            "url": "http://127.0.0.1:8767",  # Use 127.0.0.1 to avoid IPv6 conflicts
            "health_endpoint": "/health",
            "description": "CAD modeling engine",
        },
        "slicer": {
            "name": "Slicer Service",
            "url": "http://localhost:8766",
            "health_endpoint": "/health",
            "description": "G-code generation",
        },
    }

    # Cache for status
    _status_cache: Dict[str, Any] = {}
    _cache_time: float = 0
    _cache_ttl: float = 5.0  # seconds

    # Error history
    _error_log: List[Dict[str, Any]] = []
    _max_errors: int = 100

    @classmethod
    def get_service_status(cls, service_id: str, timeout: float = 5.0) -> Dict[str, Any]:
        """Get status of a specific service."""
        if service_id not in cls.SERVICES:
            return {"status": "unknown", "error": "Unknown service"}

        service = cls.SERVICES[service_id]
        url = f"{service['url']}{service['health_endpoint']}"

        start_time = time.time()

        try:
            import requests

            response = requests.get(url, timeout=timeout)
            latency = (time.time() - start_time) * 1000

            if response.status_code == 200:
                data = response.json() if response.content else {}
                return {
                    "status": "connected",
                    "latency_ms": round(latency, 1),
                    "data": data,
                    "checked_at": datetime.now().isoformat(),
                }
            else:
                return {
                    "status": "error",
                    "error": f"HTTP {response.status_code}",
                    "latency_ms": round(latency, 1),
                    "checked_at": datetime.now().isoformat(),
                }

        except requests.exceptions.ConnectionError:
            return {
                "status": "disconnected",
                "error": "Connection refused",
                "checked_at": datetime.now().isoformat(),
            }
        except requests.exceptions.Timeout:
            return {
                "status": "timeout",
                "error": f"Timeout after {timeout}s",
                "checked_at": datetime.now().isoformat(),
            }
        except Exception as e:
            return {"status": "error", "error": str(e), "checked_at": datetime.now().isoformat()}

    @classmethod
    def get_all_status(cls, use_cache: bool = True) -> Dict[str, Any]:
        """Get status of all services."""
        # Check cache
        if use_cache and time.time() - cls._cache_time < cls._cache_ttl:
            return cls._status_cache

        status = {"services": {}, "overall": "healthy", "checked_at": datetime.now().isoformat()}

        unhealthy_count = 0

        for service_id, service_info in cls.SERVICES.items():
            service_status = cls.get_service_status(service_id)
            status["services"][service_id] = {
                "name": service_info["name"],
                "description": service_info["description"],
                "url": service_info["url"],
                **service_status,
            }

            if service_status["status"] != "connected":
                unhealthy_count += 1

        # Determine overall status
        if unhealthy_count == 0:
            status["overall"] = "healthy"
        elif unhealthy_count < len(cls.SERVICES):
            status["overall"] = "degraded"
        else:
            status["overall"] = "unhealthy"

        # Update cache
        cls._status_cache = status
        cls._cache_time = time.time()

        return status

    @classmethod
    def get_circuit_breakers(cls) -> Dict[str, Any]:
        """Get circuit breaker states."""
        try:
            from error_recovery import fusion_circuit, slicer_circuit

            return {"fusion360": fusion_circuit.get_status(), "slicer": slicer_circuit.get_status()}
        except ImportError:
            return {
                "fusion360": {"state": "unknown", "error": "Module not available"},
                "slicer": {"state": "unknown", "error": "Module not available"},
            }

    @classmethod
    def reset_circuit_breaker(cls, service: str) -> Dict[str, Any]:
        """Reset a circuit breaker."""
        try:
            from error_recovery import fusion_circuit, slicer_circuit

            if service == "fusion360":
                fusion_circuit.reset()
                return {"success": True, "service": "fusion360", "state": "closed"}
            elif service == "slicer":
                slicer_circuit.reset()
                return {"success": True, "service": "slicer", "state": "closed"}
            else:
                return {"success": False, "error": f"Unknown service: {service}"}
        except ImportError:
            return {"success": False, "error": "Error recovery module not available"}

    @classmethod
    def get_error_log(cls, limit: int = 50) -> List[Dict[str, Any]]:
        """Get recent errors."""
        try:
            from error_recovery import error_handler

            return error_handler.get_recent_errors(limit)
        except ImportError:
            return cls._error_log[-limit:]

    @classmethod
    def get_error_stats(cls) -> Dict[str, Any]:
        """Get error statistics."""
        try:
            from error_recovery import error_handler

            return error_handler.get_error_stats()
        except ImportError:
            return {"total": len(cls._error_log)}

    @classmethod
    def log_error(cls, error_type: str, message: str, code: str = None, context: Dict = None):
        """Log an error."""
        error = {
            "timestamp": time.time(),
            "datetime": datetime.now().isoformat(),
            "error_type": error_type,
            "message": message,
            "code": code,
            "context": context,
        }

        cls._error_log.append(error)

        # Trim log
        if len(cls._error_log) > cls._max_errors:
            cls._error_log = cls._error_log[-cls._max_errors :]

    @classmethod
    def get_performance_stats(cls) -> Dict[str, Any]:
        """Get performance statistics."""
        try:
            from history_manager import get_history_manager

            manager = get_history_manager()
            return manager.get_statistics()
        except ImportError:
            return {"total_operations": 0, "average_time_ms": 0, "success_rate": 1.0}

    @classmethod
    def get_mcp_info(cls) -> Dict[str, Any]:
        """Get MCP server information."""
        try:
            from tools import ALL_TOOLS

            tool_categories = {}
            for name, tool in ALL_TOOLS.items():
                # Categorize by prefix
                prefix = name.split("_")[0]
                if prefix not in tool_categories:
                    tool_categories[prefix] = []
                tool_categories[prefix].append(name)

            return {
                "total_tools": len(ALL_TOOLS),
                "categories": tool_categories,
                "tool_list": list(ALL_TOOLS.keys()),
            }
        except ImportError:
            return {"total_tools": 0, "error": "Tools not available"}


def get_quick_status() -> Dict[str, str]:
    """Get quick status indicators for template context."""
    try:
        status = StatusService.get_all_status(use_cache=True)
        return {service_id: svc["status"] for service_id, svc in status["services"].items()}
    except Exception:
        return {"fusion360": "unknown", "slicer": "unknown"}


# Singleton
status_service = StatusService()
