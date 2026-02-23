"""
Health Check and Diagnostics

Implements comprehensive health checks following
Kubernetes health probe patterns.

Reference: Kubernetes Probe API, Health Check RFC
"""

import logging
import time
import asyncio
import threading
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Union, Awaitable
from datetime import datetime, timedelta
from enum import Enum
import json
import socket
import os

logger = logging.getLogger(__name__)


class HealthStatus(Enum):
    """Health check status values."""
    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"
    DEGRADED = "degraded"
    UNKNOWN = "unknown"


class CheckType(Enum):
    """Types of health checks."""
    LIVENESS = "liveness"      # Is the process alive?
    READINESS = "readiness"    # Is the service ready to accept traffic?
    STARTUP = "startup"        # Has the service started successfully?


@dataclass
class CheckResult:
    """Result of a health check."""
    name: str
    status: HealthStatus
    message: Optional[str] = None
    duration_ms: float = 0.0
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "status": self.status.value,
            "message": self.message,
            "duration_ms": round(self.duration_ms, 2),
            "timestamp": self.timestamp,
            "details": self.details
        }


@dataclass
class HealthReport:
    """Aggregate health report."""
    status: HealthStatus
    checks: List[CheckResult]
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")
    version: str = "2.0.0"
    uptime_seconds: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "status": self.status.value,
            "timestamp": self.timestamp,
            "version": self.version,
            "uptime_seconds": round(self.uptime_seconds, 2),
            "checks": [c.to_dict() for c in self.checks]
        }

    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict(), indent=2)


class HealthCheck:
    """
    Base class for health checks.

    Subclass to implement custom checks.
    """

    def __init__(
        self,
        name: str,
        check_type: CheckType = CheckType.READINESS,
        timeout: float = 5.0,
        critical: bool = True
    ):
        """
        Initialize health check.

        Args:
            name: Check name
            check_type: Type of check
            timeout: Timeout in seconds
            critical: Whether failure makes system unhealthy
        """
        self.name = name
        self.check_type = check_type
        self.timeout = timeout
        self.critical = critical
        self._last_result: Optional[CheckResult] = None
        self._consecutive_failures = 0
        self._consecutive_successes = 0

    async def check(self) -> CheckResult:
        """
        Execute the health check.

        Override in subclasses.
        """
        raise NotImplementedError

    async def run(self) -> CheckResult:
        """Run the check with timeout and error handling."""
        start = time.time()
        try:
            if asyncio.iscoroutinefunction(self.check):
                result = await asyncio.wait_for(
                    self.check(),
                    timeout=self.timeout
                )
            else:
                # Run sync check in executor
                loop = asyncio.get_event_loop()
                result = await asyncio.wait_for(
                    loop.run_in_executor(None, self.check),
                    timeout=self.timeout
                )

            duration = (time.time() - start) * 1000
            result.duration_ms = duration

            # Update consecutive counters
            if result.status == HealthStatus.HEALTHY:
                self._consecutive_failures = 0
                self._consecutive_successes += 1
            else:
                self._consecutive_failures += 1
                self._consecutive_successes = 0

            self._last_result = result
            return result

        except asyncio.TimeoutError:
            duration = (time.time() - start) * 1000
            self._consecutive_failures += 1
            self._consecutive_successes = 0

            result = CheckResult(
                name=self.name,
                status=HealthStatus.UNHEALTHY,
                message=f"Check timed out after {self.timeout}s",
                duration_ms=duration
            )
            self._last_result = result
            return result

        except Exception as e:
            duration = (time.time() - start) * 1000
            self._consecutive_failures += 1
            self._consecutive_successes = 0

            result = CheckResult(
                name=self.name,
                status=HealthStatus.UNHEALTHY,
                message=f"Check failed: {str(e)}",
                duration_ms=duration
            )
            self._last_result = result
            return result


class TCPHealthCheck(HealthCheck):
    """TCP connectivity health check."""

    def __init__(
        self,
        name: str,
        host: str,
        port: int,
        **kwargs
    ):
        super().__init__(name, **kwargs)
        self.host = host
        self.port = port

    async def check(self) -> CheckResult:
        """Check TCP connectivity."""
        try:
            loop = asyncio.get_event_loop()

            def _connect():
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(self.timeout)
                try:
                    sock.connect((self.host, self.port))
                    return True
                finally:
                    sock.close()

            await loop.run_in_executor(None, _connect)

            return CheckResult(
                name=self.name,
                status=HealthStatus.HEALTHY,
                message=f"TCP connection to {self.host}:{self.port} successful",
                details={"host": self.host, "port": self.port}
            )
        except Exception as e:
            return CheckResult(
                name=self.name,
                status=HealthStatus.UNHEALTHY,
                message=f"TCP connection failed: {str(e)}",
                details={"host": self.host, "port": self.port}
            )


class HTTPHealthCheck(HealthCheck):
    """HTTP endpoint health check."""

    def __init__(
        self,
        name: str,
        url: str,
        expected_status: int = 200,
        **kwargs
    ):
        super().__init__(name, **kwargs)
        self.url = url
        self.expected_status = expected_status

    async def check(self) -> CheckResult:
        """Check HTTP endpoint."""
        import urllib.request
        import urllib.error

        try:
            loop = asyncio.get_event_loop()

            def _request():
                req = urllib.request.Request(self.url, method='GET')
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    return resp.status

            status = await loop.run_in_executor(None, _request)

            if status == self.expected_status:
                return CheckResult(
                    name=self.name,
                    status=HealthStatus.HEALTHY,
                    message=f"HTTP {status} OK",
                    details={"url": self.url, "status_code": status}
                )
            else:
                return CheckResult(
                    name=self.name,
                    status=HealthStatus.DEGRADED,
                    message=f"HTTP {status} (expected {self.expected_status})",
                    details={"url": self.url, "status_code": status}
                )

        except Exception as e:
            return CheckResult(
                name=self.name,
                status=HealthStatus.UNHEALTHY,
                message=f"HTTP check failed: {str(e)}",
                details={"url": self.url}
            )


class DatabaseHealthCheck(HealthCheck):
    """Database connectivity health check."""

    def __init__(
        self,
        name: str,
        connection_func: Callable[[], bool],
        **kwargs
    ):
        super().__init__(name, **kwargs)
        self.connection_func = connection_func

    async def check(self) -> CheckResult:
        """Check database connectivity."""
        try:
            loop = asyncio.get_event_loop()
            is_connected = await loop.run_in_executor(
                None, self.connection_func
            )

            if is_connected:
                return CheckResult(
                    name=self.name,
                    status=HealthStatus.HEALTHY,
                    message="Database connection successful"
                )
            else:
                return CheckResult(
                    name=self.name,
                    status=HealthStatus.UNHEALTHY,
                    message="Database connection failed"
                )
        except Exception as e:
            return CheckResult(
                name=self.name,
                status=HealthStatus.UNHEALTHY,
                message=f"Database check error: {str(e)}"
            )


class DiskSpaceHealthCheck(HealthCheck):
    """Disk space availability check."""

    def __init__(
        self,
        name: str,
        path: str = "/",
        min_free_gb: float = 1.0,
        warning_free_gb: float = 5.0,
        **kwargs
    ):
        super().__init__(name, **kwargs)
        self.path = path
        self.min_free_gb = min_free_gb
        self.warning_free_gb = warning_free_gb

    async def check(self) -> CheckResult:
        """Check disk space."""
        try:
            stat = os.statvfs(self.path)
            free_bytes = stat.f_frsize * stat.f_bavail
            total_bytes = stat.f_frsize * stat.f_blocks
            free_gb = free_bytes / (1024 ** 3)
            total_gb = total_bytes / (1024 ** 3)
            usage_percent = ((total_bytes - free_bytes) / total_bytes) * 100

            details = {
                "path": self.path,
                "free_gb": round(free_gb, 2),
                "total_gb": round(total_gb, 2),
                "usage_percent": round(usage_percent, 2)
            }

            if free_gb < self.min_free_gb:
                return CheckResult(
                    name=self.name,
                    status=HealthStatus.UNHEALTHY,
                    message=f"Critical: Only {free_gb:.2f}GB free",
                    details=details
                )
            elif free_gb < self.warning_free_gb:
                return CheckResult(
                    name=self.name,
                    status=HealthStatus.DEGRADED,
                    message=f"Warning: Only {free_gb:.2f}GB free",
                    details=details
                )
            else:
                return CheckResult(
                    name=self.name,
                    status=HealthStatus.HEALTHY,
                    message=f"Disk space OK: {free_gb:.2f}GB free",
                    details=details
                )
        except Exception as e:
            return CheckResult(
                name=self.name,
                status=HealthStatus.UNHEALTHY,
                message=f"Disk check failed: {str(e)}"
            )


class MemoryHealthCheck(HealthCheck):
    """Memory availability check."""

    def __init__(
        self,
        name: str,
        max_usage_percent: float = 90.0,
        warning_percent: float = 80.0,
        **kwargs
    ):
        super().__init__(name, **kwargs)
        self.max_usage_percent = max_usage_percent
        self.warning_percent = warning_percent

    async def check(self) -> CheckResult:
        """Check memory usage."""
        try:
            with open('/proc/meminfo', 'r') as f:
                meminfo = {}
                for line in f:
                    parts = line.split(':')
                    if len(parts) == 2:
                        key = parts[0].strip()
                        value = int(parts[1].strip().split()[0])  # Value in KB
                        meminfo[key] = value

            total_kb = meminfo.get('MemTotal', 0)
            available_kb = meminfo.get('MemAvailable', 0)

            if total_kb == 0:
                raise ValueError("Could not read memory info")

            used_kb = total_kb - available_kb
            usage_percent = (used_kb / total_kb) * 100

            details = {
                "total_mb": round(total_kb / 1024, 2),
                "available_mb": round(available_kb / 1024, 2),
                "used_mb": round(used_kb / 1024, 2),
                "usage_percent": round(usage_percent, 2)
            }

            if usage_percent >= self.max_usage_percent:
                return CheckResult(
                    name=self.name,
                    status=HealthStatus.UNHEALTHY,
                    message=f"Critical: {usage_percent:.1f}% memory used",
                    details=details
                )
            elif usage_percent >= self.warning_percent:
                return CheckResult(
                    name=self.name,
                    status=HealthStatus.DEGRADED,
                    message=f"Warning: {usage_percent:.1f}% memory used",
                    details=details
                )
            else:
                return CheckResult(
                    name=self.name,
                    status=HealthStatus.HEALTHY,
                    message=f"Memory OK: {usage_percent:.1f}% used",
                    details=details
                )
        except FileNotFoundError:
            # Not on Linux, try different approach
            return CheckResult(
                name=self.name,
                status=HealthStatus.UNKNOWN,
                message="Memory check not available on this platform"
            )
        except Exception as e:
            return CheckResult(
                name=self.name,
                status=HealthStatus.UNHEALTHY,
                message=f"Memory check failed: {str(e)}"
            )


class CustomHealthCheck(HealthCheck):
    """Custom health check from a callable."""

    def __init__(
        self,
        name: str,
        check_func: Union[Callable[[], bool], Callable[[], Awaitable[bool]]],
        **kwargs
    ):
        super().__init__(name, **kwargs)
        self.check_func = check_func

    async def check(self) -> CheckResult:
        """Run custom check function."""
        try:
            if asyncio.iscoroutinefunction(self.check_func):
                result = await self.check_func()
            else:
                loop = asyncio.get_event_loop()
                result = await loop.run_in_executor(None, self.check_func)

            if result:
                return CheckResult(
                    name=self.name,
                    status=HealthStatus.HEALTHY,
                    message="Check passed"
                )
            else:
                return CheckResult(
                    name=self.name,
                    status=HealthStatus.UNHEALTHY,
                    message="Check failed"
                )
        except Exception as e:
            return CheckResult(
                name=self.name,
                status=HealthStatus.UNHEALTHY,
                message=f"Check error: {str(e)}"
            )


class HealthChecker:
    """
    Central health check manager.

    Coordinates multiple health checks and provides
    aggregate health status.

    Usage:
        >>> checker = HealthChecker()
        >>> checker.add_check(TCPHealthCheck("db", "localhost", 5432))
        >>> report = await checker.check_all()
        >>> print(report.status)
    """

    def __init__(
        self,
        service_name: str = "lego-mcp",
        version: str = "2.0.0"
    ):
        """
        Initialize health checker.

        Args:
            service_name: Name of the service
            version: Service version
        """
        self.service_name = service_name
        self.version = version
        self._checks: Dict[CheckType, List[HealthCheck]] = {
            CheckType.LIVENESS: [],
            CheckType.READINESS: [],
            CheckType.STARTUP: []
        }
        self._start_time = time.time()
        self._startup_complete = False

        logger.info(f"HealthChecker initialized: service={service_name}")

    @property
    def uptime_seconds(self) -> float:
        """Get service uptime in seconds."""
        return time.time() - self._start_time

    def add_check(self, check: HealthCheck) -> None:
        """Add a health check."""
        self._checks[check.check_type].append(check)
        logger.debug(f"Added health check: {check.name} ({check.check_type.value})")

    def remove_check(self, name: str) -> bool:
        """Remove a health check by name."""
        for check_type in self._checks:
            for i, check in enumerate(self._checks[check_type]):
                if check.name == name:
                    del self._checks[check_type][i]
                    logger.debug(f"Removed health check: {name}")
                    return True
        return False

    def mark_startup_complete(self) -> None:
        """Mark startup as complete."""
        self._startup_complete = True
        logger.info("Startup marked as complete")

    async def check_liveness(self) -> HealthReport:
        """Run liveness checks (is the process alive?)."""
        return await self._run_checks(CheckType.LIVENESS)

    async def check_readiness(self) -> HealthReport:
        """Run readiness checks (is the service ready?)."""
        return await self._run_checks(CheckType.READINESS)

    async def check_startup(self) -> HealthReport:
        """Run startup checks (has the service started?)."""
        if self._startup_complete:
            return HealthReport(
                status=HealthStatus.HEALTHY,
                checks=[],
                version=self.version,
                uptime_seconds=self.uptime_seconds
            )
        return await self._run_checks(CheckType.STARTUP)

    async def check_all(self) -> HealthReport:
        """Run all health checks."""
        all_results = []
        overall_status = HealthStatus.HEALTHY

        for check_type in [CheckType.LIVENESS, CheckType.READINESS]:
            checks = self._checks[check_type]
            if not checks:
                continue

            results = await asyncio.gather(
                *[c.run() for c in checks],
                return_exceptions=True
            )

            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    result = CheckResult(
                        name=checks[i].name,
                        status=HealthStatus.UNHEALTHY,
                        message=f"Check exception: {str(result)}"
                    )

                all_results.append(result)

                # Update overall status
                if result.status == HealthStatus.UNHEALTHY:
                    if checks[i].critical:
                        overall_status = HealthStatus.UNHEALTHY
                    elif overall_status != HealthStatus.UNHEALTHY:
                        overall_status = HealthStatus.DEGRADED
                elif result.status == HealthStatus.DEGRADED:
                    if overall_status == HealthStatus.HEALTHY:
                        overall_status = HealthStatus.DEGRADED

        return HealthReport(
            status=overall_status,
            checks=all_results,
            version=self.version,
            uptime_seconds=self.uptime_seconds
        )

    async def _run_checks(self, check_type: CheckType) -> HealthReport:
        """Run checks of a specific type."""
        checks = self._checks[check_type]

        if not checks:
            return HealthReport(
                status=HealthStatus.HEALTHY,
                checks=[],
                version=self.version,
                uptime_seconds=self.uptime_seconds
            )

        results = await asyncio.gather(
            *[c.run() for c in checks],
            return_exceptions=True
        )

        processed_results = []
        overall_status = HealthStatus.HEALTHY

        for i, result in enumerate(results):
            if isinstance(result, Exception):
                result = CheckResult(
                    name=checks[i].name,
                    status=HealthStatus.UNHEALTHY,
                    message=f"Check exception: {str(result)}"
                )

            processed_results.append(result)

            # Determine overall status
            if result.status == HealthStatus.UNHEALTHY and checks[i].critical:
                overall_status = HealthStatus.UNHEALTHY
            elif result.status == HealthStatus.DEGRADED and overall_status == HealthStatus.HEALTHY:
                overall_status = HealthStatus.DEGRADED

        return HealthReport(
            status=overall_status,
            checks=processed_results,
            version=self.version,
            uptime_seconds=self.uptime_seconds
        )


class ManufacturingHealthChecker(HealthChecker):
    """
    Manufacturing-specific health checker.

    Includes checks for equipment, PLCs, and manufacturing systems.
    """

    def __init__(
        self,
        service_name: str = "lego-mcp",
        version: str = "2.0.0"
    ):
        super().__init__(service_name, version)
        self._equipment_status: Dict[str, HealthStatus] = {}

    def add_equipment_check(
        self,
        equipment_id: str,
        check_func: Callable[[], bool],
        critical: bool = False
    ) -> None:
        """Add health check for equipment."""
        check = CustomHealthCheck(
            name=f"equipment_{equipment_id}",
            check_func=check_func,
            check_type=CheckType.READINESS,
            critical=critical
        )
        self.add_check(check)

    def update_equipment_status(
        self,
        equipment_id: str,
        status: HealthStatus
    ) -> None:
        """Update cached equipment status."""
        self._equipment_status[equipment_id] = status

    def get_equipment_status(self, equipment_id: str) -> HealthStatus:
        """Get cached equipment status."""
        return self._equipment_status.get(equipment_id, HealthStatus.UNKNOWN)

    async def check_manufacturing_readiness(self) -> HealthReport:
        """
        Check if manufacturing system is ready for production.

        Includes equipment, material, and quality system checks.
        """
        report = await self.check_all()

        # Add equipment status summary
        equipment_summary = {
            "total": len(self._equipment_status),
            "healthy": sum(
                1 for s in self._equipment_status.values()
                if s == HealthStatus.HEALTHY
            ),
            "degraded": sum(
                1 for s in self._equipment_status.values()
                if s == HealthStatus.DEGRADED
            ),
            "unhealthy": sum(
                1 for s in self._equipment_status.values()
                if s == HealthStatus.UNHEALTHY
            )
        }

        # Add summary check result
        report.checks.append(CheckResult(
            name="equipment_summary",
            status=report.status,
            message=f"{equipment_summary['healthy']}/{equipment_summary['total']} equipment healthy",
            details=equipment_summary
        ))

        return report


# Global health checker instance
_global_checker: Optional[HealthChecker] = None


def get_health_checker() -> HealthChecker:
    """Get the global health checker instance."""
    global _global_checker
    if _global_checker is None:
        _global_checker = HealthChecker()
    return _global_checker


def set_health_checker(checker: HealthChecker) -> None:
    """Set the global health checker instance."""
    global _global_checker
    _global_checker = checker
