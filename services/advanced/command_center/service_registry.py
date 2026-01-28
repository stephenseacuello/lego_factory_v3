"""
Service Registry for Manufacturing System

Central registry for all services with health monitoring,
dependency management, and service discovery.

Reference: ISA-95, IEC 62264, Microservices Patterns
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set
import threading

logger = logging.getLogger(__name__)


class ServiceStatus(Enum):
    """Service health status."""
    UNKNOWN = "unknown"
    STARTING = "starting"
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    STOPPED = "stopped"


class ServiceCategory(Enum):
    """Service categories per ISA-95 levels."""
    LEVEL_0 = "process_control"       # Physical processes
    LEVEL_1 = "sensing_manipulation"  # Sensors/actuators
    LEVEL_2 = "monitoring_control"    # SCADA/HMI
    LEVEL_3 = "manufacturing_ops"     # MES/MOM
    LEVEL_4 = "business_planning"     # ERP
    INFRASTRUCTURE = "infrastructure" # Supporting services


@dataclass
class ServiceHealth:
    """Service health information."""
    status: ServiceStatus = ServiceStatus.UNKNOWN
    last_check: Optional[datetime] = None
    message: str = ""
    latency_ms: float = 0.0
    error_count: int = 0
    uptime_seconds: float = 0.0


@dataclass
class ServiceDescriptor:
    """Service descriptor with metadata."""
    name: str
    category: ServiceCategory
    version: str
    description: str = ""
    dependencies: List[str] = field(default_factory=list)
    endpoints: Dict[str, str] = field(default_factory=dict)
    health: ServiceHealth = field(default_factory=ServiceHealth)
    tags: Set[str] = field(default_factory=set)
    config: Dict[str, Any] = field(default_factory=dict)
    registered_at: datetime = field(default_factory=datetime.now)
    instance_id: str = ""
    priority: int = 0  # Higher = more important


class ServiceRegistry:
    """
    Central Service Registry.

    Manages service registration, discovery, and health monitoring.
    """

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._init()
        return cls._instance

    def _init(self):
        self._services: Dict[str, ServiceDescriptor] = {}
        self._health_checks: Dict[str, Callable[[], ServiceHealth]] = {}
        self._listeners: List[Callable[[str, ServiceStatus], None]] = []
        self._started = False
        self._check_interval = 30  # seconds

        # Pre-register core services
        self._register_core_services()

    def _register_core_services(self):
        """Register core manufacturing services."""
        core_services = [
            # Level 4 - Business Planning
            ServiceDescriptor(
                name="erp",
                category=ServiceCategory.LEVEL_4,
                version="1.0.0",
                description="Enterprise Resource Planning",
                tags={"core", "planning", "sap-compatible"}
            ),
            ServiceDescriptor(
                name="mrp",
                category=ServiceCategory.LEVEL_4,
                version="1.0.0",
                description="Material Requirements Planning",
                dependencies=["erp", "inventory"],
                tags={"core", "planning"}
            ),

            # Level 3 - Manufacturing Operations
            ServiceDescriptor(
                name="mes",
                category=ServiceCategory.LEVEL_3,
                version="1.0.0",
                description="Manufacturing Execution System",
                dependencies=["scheduling", "quality"],
                tags={"core", "execution"}
            ),
            ServiceDescriptor(
                name="scheduling",
                category=ServiceCategory.LEVEL_3,
                version="1.0.0",
                description="Production Scheduling",
                tags={"core", "planning"}
            ),
            ServiceDescriptor(
                name="quality",
                category=ServiceCategory.LEVEL_3,
                version="1.0.0",
                description="Quality Management System",
                tags={"core", "quality", "iso9001"}
            ),
            ServiceDescriptor(
                name="inventory",
                category=ServiceCategory.LEVEL_3,
                version="1.0.0",
                description="Inventory Management",
                tags={"core", "materials"}
            ),

            # Level 2 - Monitoring & Control
            ServiceDescriptor(
                name="scada",
                category=ServiceCategory.LEVEL_2,
                version="1.0.0",
                description="Supervisory Control and Data Acquisition",
                tags={"core", "control"}
            ),
            ServiceDescriptor(
                name="hmi",
                category=ServiceCategory.LEVEL_2,
                version="1.0.0",
                description="Human-Machine Interface",
                dependencies=["scada"],
                tags={"core", "ui"}
            ),
            ServiceDescriptor(
                name="vision",
                category=ServiceCategory.LEVEL_2,
                version="1.0.0",
                description="Machine Vision System",
                tags={"core", "inspection"}
            ),

            # Level 1 - Sensing & Manipulation
            ServiceDescriptor(
                name="robotics",
                category=ServiceCategory.LEVEL_1,
                version="1.0.0",
                description="Robotic Control System",
                tags={"core", "automation"}
            ),
            ServiceDescriptor(
                name="cnc",
                category=ServiceCategory.LEVEL_1,
                version="1.0.0",
                description="CNC Machine Control",
                tags={"core", "machining"}
            ),

            # Infrastructure
            ServiceDescriptor(
                name="analytics",
                category=ServiceCategory.INFRASTRUCTURE,
                version="1.0.0",
                description="Manufacturing Analytics Engine",
                tags={"analytics", "ml"}
            ),
            ServiceDescriptor(
                name="digital_twin",
                category=ServiceCategory.INFRASTRUCTURE,
                version="1.0.0",
                description="Digital Twin Framework",
                dependencies=["scada", "analytics"],
                tags={"simulation", "iso23247"}
            ),
            ServiceDescriptor(
                name="compliance",
                category=ServiceCategory.INFRASTRUCTURE,
                version="1.0.0",
                description="Regulatory Compliance Engine",
                tags={"compliance", "audit"}
            ),
            ServiceDescriptor(
                name="security",
                category=ServiceCategory.INFRASTRUCTURE,
                version="1.0.0",
                description="Industrial Security Services",
                tags={"security", "iec62443"}
            ),
        ]

        for svc in core_services:
            self._services[svc.name] = svc

    def register(
        self,
        descriptor: ServiceDescriptor,
        health_check: Optional[Callable[[], ServiceHealth]] = None
    ) -> bool:
        """
        Register a service.

        Args:
            descriptor: Service descriptor
            health_check: Optional health check function

        Returns:
            True if registered successfully
        """
        with self._lock:
            if descriptor.name in self._services:
                existing = self._services[descriptor.name]
                # Update existing registration
                descriptor.registered_at = existing.registered_at
                logger.info(f"Updating service registration: {descriptor.name}")
            else:
                logger.info(f"Registering new service: {descriptor.name}")

            self._services[descriptor.name] = descriptor

            if health_check:
                self._health_checks[descriptor.name] = health_check

            self._notify_listeners(descriptor.name, descriptor.health.status)

        return True

    def deregister(self, name: str) -> bool:
        """Deregister a service."""
        with self._lock:
            if name in self._services:
                del self._services[name]
                if name in self._health_checks:
                    del self._health_checks[name]
                self._notify_listeners(name, ServiceStatus.STOPPED)
                logger.info(f"Deregistered service: {name}")
                return True
        return False

    def get_service(self, name: str) -> Optional[ServiceDescriptor]:
        """Get service by name."""
        return self._services.get(name)

    def get_services_by_category(self, category: ServiceCategory) -> List[ServiceDescriptor]:
        """Get all services in a category."""
        return [s for s in self._services.values() if s.category == category]

    def get_services_by_tag(self, tag: str) -> List[ServiceDescriptor]:
        """Get all services with a specific tag."""
        return [s for s in self._services.values() if tag in s.tags]

    def get_healthy_services(self) -> List[ServiceDescriptor]:
        """Get all healthy services."""
        return [
            s for s in self._services.values()
            if s.health.status == ServiceStatus.HEALTHY
        ]

    def get_all_services(self) -> Dict[str, ServiceDescriptor]:
        """Get all registered services."""
        return dict(self._services)

    def check_dependencies(self, name: str) -> Dict[str, bool]:
        """
        Check if all dependencies of a service are healthy.

        Returns dict of {dependency_name: is_healthy}
        """
        service = self._services.get(name)
        if not service:
            return {}

        result = {}
        for dep_name in service.dependencies:
            dep = self._services.get(dep_name)
            if dep:
                result[dep_name] = dep.health.status == ServiceStatus.HEALTHY
            else:
                result[dep_name] = False

        return result

    def get_dependency_graph(self) -> Dict[str, List[str]]:
        """Get full dependency graph."""
        return {
            name: svc.dependencies
            for name, svc in self._services.items()
        }

    def update_health(self, name: str, health: ServiceHealth) -> None:
        """Update service health status."""
        if name in self._services:
            old_status = self._services[name].health.status
            self._services[name].health = health

            if old_status != health.status:
                logger.info(f"Service {name} status changed: {old_status} -> {health.status}")
                self._notify_listeners(name, health.status)

    def add_status_listener(self, callback: Callable[[str, ServiceStatus], None]) -> None:
        """Add listener for status changes."""
        self._listeners.append(callback)

    def _notify_listeners(self, service_name: str, status: ServiceStatus) -> None:
        """Notify all listeners of status change."""
        for listener in self._listeners:
            try:
                listener(service_name, status)
            except Exception as e:
                logger.error(f"Listener error: {e}")

    async def run_health_checks(self) -> Dict[str, ServiceHealth]:
        """Run all registered health checks."""
        results = {}

        for name, check_func in self._health_checks.items():
            try:
                health = check_func()
                self.update_health(name, health)
                results[name] = health
            except Exception as e:
                logger.error(f"Health check failed for {name}: {e}")
                results[name] = ServiceHealth(
                    status=ServiceStatus.UNHEALTHY,
                    message=str(e),
                    last_check=datetime.now()
                )
                self.update_health(name, results[name])

        return results

    def get_system_status(self) -> Dict[str, Any]:
        """Get overall system status."""
        services = list(self._services.values())

        healthy = sum(1 for s in services if s.health.status == ServiceStatus.HEALTHY)
        degraded = sum(1 for s in services if s.health.status == ServiceStatus.DEGRADED)
        unhealthy = sum(1 for s in services if s.health.status == ServiceStatus.UNHEALTHY)

        # Determine overall status
        if unhealthy > 0:
            overall = ServiceStatus.UNHEALTHY
        elif degraded > 0:
            overall = ServiceStatus.DEGRADED
        elif healthy == len(services):
            overall = ServiceStatus.HEALTHY
        else:
            overall = ServiceStatus.UNKNOWN

        return {
            "overall_status": overall.value,
            "total_services": len(services),
            "healthy": healthy,
            "degraded": degraded,
            "unhealthy": unhealthy,
            "services_by_category": {
                cat.value: len(self.get_services_by_category(cat))
                for cat in ServiceCategory
            },
            "timestamp": datetime.now().isoformat()
        }


def get_registry() -> ServiceRegistry:
    """Get global service registry instance."""
    return ServiceRegistry()
