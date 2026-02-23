"""
Agent Registry - Agent discovery and health monitoring.

LEGO MCP v6.0 World-Class Manufacturing Research Platform
Phase 1: Multi-Agent Orchestration Framework
"""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set
import logging

logger = logging.getLogger(__name__)


class AgentStatus(Enum):
    """Agent operational status."""
    INITIALIZING = "initializing"
    READY = "ready"
    BUSY = "busy"
    SUSPENDED = "suspended"
    ERROR = "error"
    OFFLINE = "offline"


class AgentCapability(Enum):
    """Agent capabilities for task assignment."""
    QUALITY_INSPECTION = "quality_inspection"
    QUALITY_PREDICTION = "quality_prediction"
    SCHEDULE_OPTIMIZATION = "schedule_optimization"
    RESOURCE_ALLOCATION = "resource_allocation"
    MAINTENANCE_PREDICTION = "maintenance_prediction"
    MAINTENANCE_SCHEDULING = "maintenance_scheduling"
    PROCESS_CONTROL = "process_control"
    ANOMALY_DETECTION = "anomaly_detection"
    ROOT_CAUSE_ANALYSIS = "root_cause_analysis"
    DECISION_MAKING = "decision_making"
    GENERATIVE_DESIGN = "generative_design"


@dataclass
class AgentInfo:
    """
    Information about a registered agent.

    Attributes:
        agent_id: Unique agent identifier
        agent_type: Type of agent (quality, scheduling, maintenance, etc.)
        capabilities: Set of agent capabilities
        status: Current operational status
        load: Current workload (0.0 - 1.0)
        metadata: Additional agent information
        registered_at: Registration timestamp
        last_heartbeat: Last heartbeat timestamp
    """
    agent_id: str
    agent_type: str
    capabilities: Set[AgentCapability]
    status: AgentStatus = AgentStatus.INITIALIZING
    load: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    registered_at: datetime = field(default_factory=datetime.utcnow)
    last_heartbeat: datetime = field(default_factory=datetime.utcnow)
    version: str = "1.0.0"
    priority: int = 5  # 1 = highest, 10 = lowest

    def is_available(self) -> bool:
        """Check if agent is available for tasks."""
        return (
            self.status in (AgentStatus.READY, AgentStatus.BUSY) and
            self.load < 0.9 and
            self.is_healthy()
        )

    def is_healthy(self) -> bool:
        """Check if agent is healthy (received heartbeat recently)."""
        return (datetime.utcnow() - self.last_heartbeat) < timedelta(seconds=30)

    def has_capability(self, capability: AgentCapability) -> bool:
        """Check if agent has a specific capability."""
        return capability in self.capabilities


class AgentRegistry:
    """
    Central registry for agent discovery and health monitoring.

    Features:
    - Agent registration and deregistration
    - Capability-based agent discovery
    - Health monitoring via heartbeats
    - Load balancing support
    - Agent lifecycle management
    """

    def __init__(self, heartbeat_interval: float = 10.0, heartbeat_timeout: float = 30.0):
        self._agents: Dict[str, AgentInfo] = {}
        self._capability_index: Dict[AgentCapability, Set[str]] = {}
        self._type_index: Dict[str, Set[str]] = {}
        self._heartbeat_interval = heartbeat_interval
        self._heartbeat_timeout = heartbeat_timeout
        self._health_check_task: Optional[asyncio.Task] = None
        self._running = False
        self._listeners: List[Callable[[str, str], None]] = []
        self._lock = asyncio.Lock()

    async def start(self) -> None:
        """Start the registry health check loop."""
        if self._running:
            return
        self._running = True
        self._health_check_task = asyncio.create_task(self._health_check_loop())
        logger.info("Agent registry started")

    async def stop(self) -> None:
        """Stop the registry."""
        self._running = False
        if self._health_check_task:
            self._health_check_task.cancel()
            try:
                await self._health_check_task
            except asyncio.CancelledError:
                pass
        logger.info("Agent registry stopped")

    async def register(self, agent_info: AgentInfo) -> bool:
        """
        Register an agent with the registry.

        Args:
            agent_info: Agent information

        Returns:
            True if registration successful
        """
        async with self._lock:
            if agent_info.agent_id in self._agents:
                logger.warning(f"Agent {agent_info.agent_id} already registered")
                return False

            self._agents[agent_info.agent_id] = agent_info

            # Update capability index
            for capability in agent_info.capabilities:
                if capability not in self._capability_index:
                    self._capability_index[capability] = set()
                self._capability_index[capability].add(agent_info.agent_id)

            # Update type index
            if agent_info.agent_type not in self._type_index:
                self._type_index[agent_info.agent_type] = set()
            self._type_index[agent_info.agent_type].add(agent_info.agent_id)

            logger.info(f"Agent {agent_info.agent_id} registered with capabilities: {agent_info.capabilities}")
            await self._notify_listeners(agent_info.agent_id, "registered")
            return True

    async def deregister(self, agent_id: str) -> bool:
        """
        Deregister an agent from the registry.

        Args:
            agent_id: Agent identifier

        Returns:
            True if deregistration successful
        """
        async with self._lock:
            if agent_id not in self._agents:
                return False

            agent_info = self._agents.pop(agent_id)

            # Update capability index
            for capability in agent_info.capabilities:
                if capability in self._capability_index:
                    self._capability_index[capability].discard(agent_id)

            # Update type index
            if agent_info.agent_type in self._type_index:
                self._type_index[agent_info.agent_type].discard(agent_id)

            logger.info(f"Agent {agent_id} deregistered")
            await self._notify_listeners(agent_id, "deregistered")
            return True

    async def update_status(self, agent_id: str, status: AgentStatus, load: Optional[float] = None) -> None:
        """Update agent status and optionally load."""
        if agent_id in self._agents:
            agent = self._agents[agent_id]
            old_status = agent.status
            agent.status = status
            if load is not None:
                agent.load = max(0.0, min(1.0, load))

            if old_status != status:
                await self._notify_listeners(agent_id, f"status_changed:{status.value}")

    async def heartbeat(self, agent_id: str, load: Optional[float] = None) -> bool:
        """
        Record agent heartbeat.

        Args:
            agent_id: Agent identifier
            load: Optional current load

        Returns:
            True if agent is registered
        """
        if agent_id not in self._agents:
            return False

        agent = self._agents[agent_id]
        agent.last_heartbeat = datetime.utcnow()
        if load is not None:
            agent.load = max(0.0, min(1.0, load))

        if agent.status == AgentStatus.OFFLINE:
            agent.status = AgentStatus.READY
            await self._notify_listeners(agent_id, "online")

        return True

    def get_agent(self, agent_id: str) -> Optional[AgentInfo]:
        """Get agent information by ID."""
        return self._agents.get(agent_id)

    def get_all_agents(self) -> List[AgentInfo]:
        """Get all registered agents."""
        return list(self._agents.values())

    def find_by_capability(self,
                          capability: AgentCapability,
                          available_only: bool = True) -> List[AgentInfo]:
        """
        Find agents with a specific capability.

        Args:
            capability: Required capability
            available_only: Only return available agents

        Returns:
            List of matching agents sorted by load (ascending)
        """
        agent_ids = self._capability_index.get(capability, set())
        agents = [self._agents[aid] for aid in agent_ids if aid in self._agents]

        if available_only:
            agents = [a for a in agents if a.is_available()]

        # Sort by load and priority
        return sorted(agents, key=lambda a: (a.load, a.priority))

    def find_by_type(self, agent_type: str, available_only: bool = True) -> List[AgentInfo]:
        """Find agents by type."""
        agent_ids = self._type_index.get(agent_type, set())
        agents = [self._agents[aid] for aid in agent_ids if aid in self._agents]

        if available_only:
            agents = [a for a in agents if a.is_available()]

        return sorted(agents, key=lambda a: (a.load, a.priority))

    def find_best_agent(self,
                        capabilities: Set[AgentCapability],
                        prefer_type: Optional[str] = None) -> Optional[AgentInfo]:
        """
        Find the best available agent for a task requiring specific capabilities.

        Args:
            capabilities: Required capabilities
            prefer_type: Preferred agent type

        Returns:
            Best matching agent or None
        """
        candidates = []

        for agent in self._agents.values():
            if not agent.is_available():
                continue

            if not capabilities.issubset(agent.capabilities):
                continue

            # Score based on load, priority, and type preference
            score = agent.load * 10 + agent.priority
            if prefer_type and agent.agent_type == prefer_type:
                score -= 5

            candidates.append((score, agent))

        if not candidates:
            return None

        candidates.sort(key=lambda x: x[0])
        return candidates[0][1]

    def add_listener(self, listener: Callable[[str, str], None]) -> None:
        """Add a listener for agent events."""
        self._listeners.append(listener)

    def remove_listener(self, listener: Callable[[str, str], None]) -> None:
        """Remove an agent event listener."""
        if listener in self._listeners:
            self._listeners.remove(listener)

    async def _notify_listeners(self, agent_id: str, event: str) -> None:
        """Notify listeners of agent events."""
        for listener in self._listeners:
            try:
                if asyncio.iscoroutinefunction(listener):
                    await listener(agent_id, event)
                else:
                    listener(agent_id, event)
            except Exception as e:
                logger.error(f"Error notifying listener: {e}")

    async def _health_check_loop(self) -> None:
        """Periodic health check for all agents."""
        while self._running:
            try:
                await self._check_agent_health()
                await asyncio.sleep(self._heartbeat_interval)
            except Exception as e:
                logger.error(f"Health check error: {e}")

    async def _check_agent_health(self) -> None:
        """Check health of all registered agents."""
        now = datetime.utcnow()
        timeout = timedelta(seconds=self._heartbeat_timeout)

        for agent_id, agent in list(self._agents.items()):
            if now - agent.last_heartbeat > timeout:
                if agent.status != AgentStatus.OFFLINE:
                    agent.status = AgentStatus.OFFLINE
                    logger.warning(f"Agent {agent_id} marked offline (no heartbeat)")
                    await self._notify_listeners(agent_id, "offline")

    def get_stats(self) -> Dict[str, Any]:
        """Get registry statistics."""
        agents = list(self._agents.values())
        return {
            'total_agents': len(agents),
            'available_agents': len([a for a in agents if a.is_available()]),
            'healthy_agents': len([a for a in agents if a.is_healthy()]),
            'by_status': {
                status.value: len([a for a in agents if a.status == status])
                for status in AgentStatus
            },
            'by_type': {
                agent_type: len(agent_ids)
                for agent_type, agent_ids in self._type_index.items()
            },
            'average_load': sum(a.load for a in agents) / len(agents) if agents else 0
        }
