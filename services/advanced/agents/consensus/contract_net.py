"""
Contract Net Protocol - Task allocation through negotiation.

LEGO MCP v6.0 World-Class Manufacturing Research Platform
Phase 1: Multi-Agent Orchestration Framework

Implementation of the Contract Net Protocol (CNP) for distributed
task allocation among manufacturing agents.
"""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Optional, Set
from enum import Enum
import uuid
import logging

logger = logging.getLogger(__name__)


class TaskStatus(Enum):
    """Task execution status."""
    ANNOUNCED = "announced"
    BIDDING = "bidding"
    AWARDED = "awarded"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ProposalStatus(Enum):
    """Proposal status."""
    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    EXPIRED = "expired"


@dataclass
class Task:
    """
    Task to be allocated via Contract Net.

    Attributes:
        task_id: Unique task identifier
        task_type: Type of task (e.g., quality_inspection, schedule_optimization)
        requirements: Required capabilities and resources
        priority: Task priority (1 = highest)
        deadline: Task deadline
        payload: Task-specific data
        constraints: Execution constraints
    """
    task_type: str
    requirements: Dict[str, Any]
    priority: int = 5
    deadline: Optional[datetime] = None
    payload: Dict[str, Any] = field(default_factory=dict)
    constraints: Dict[str, Any] = field(default_factory=dict)
    task_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: datetime = field(default_factory=datetime.utcnow)
    status: TaskStatus = TaskStatus.ANNOUNCED

    def is_expired(self) -> bool:
        """Check if task has passed deadline."""
        if self.deadline is None:
            return False
        return datetime.utcnow() > self.deadline


@dataclass
class Proposal:
    """
    Agent proposal for task execution.

    Attributes:
        agent_id: Proposing agent ID
        task_id: Task being bid on
        cost: Estimated cost/effort
        time_estimate: Estimated completion time
        confidence: Confidence in estimate (0-1)
        capabilities: Relevant capabilities offered
        constraints: Execution constraints/conditions
    """
    agent_id: str
    task_id: str
    cost: float
    time_estimate: timedelta
    confidence: float = 0.8
    capabilities: Set[str] = field(default_factory=set)
    constraints: Dict[str, Any] = field(default_factory=dict)
    proposal_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: datetime = field(default_factory=datetime.utcnow)
    status: ProposalStatus = ProposalStatus.PENDING

    def score(self) -> float:
        """Calculate proposal score (lower is better)."""
        time_hours = self.time_estimate.total_seconds() / 3600
        return self.cost * 0.4 + time_hours * 0.3 + (1 - self.confidence) * 0.3


@dataclass
class Contract:
    """Contract between manager and contractor."""
    contract_id: str
    task: Task
    contractor_id: str
    proposal: Proposal
    created_at: datetime = field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    result: Optional[Dict[str, Any]] = None
    success: bool = False


class ContractNetProtocol:
    """
    Contract Net Protocol implementation.

    Phases:
    1. Task Announcement: Manager announces task to potential contractors
    2. Bidding: Contractors submit proposals
    3. Award: Manager selects best proposal and awards contract
    4. Execution: Contractor executes task
    5. Completion: Contractor reports completion

    Features:
    - Configurable proposal evaluation
    - Timeout handling
    - Multi-task coordination
    - Subcontracting support
    """

    def __init__(self,
                 bid_timeout: float = 30.0,
                 execution_timeout: float = 300.0):
        self.bid_timeout = bid_timeout
        self.execution_timeout = execution_timeout
        self._active_tasks: Dict[str, Task] = {}
        self._proposals: Dict[str, List[Proposal]] = {}
        self._contracts: Dict[str, Contract] = {}
        self._agent_tasks: Dict[str, Set[str]] = {}
        self._evaluator: Optional[Callable[[List[Proposal]], Proposal]] = None

    def set_proposal_evaluator(self, evaluator: Callable[[List[Proposal]], Proposal]) -> None:
        """Set custom proposal evaluation function."""
        self._evaluator = evaluator

    async def announce_task(self,
                           task: Task,
                           eligible_agents: List[str],
                           announcement_callback: Callable[[Task, str], None]) -> str:
        """
        Announce a task to eligible agents.

        Args:
            task: Task to announce
            eligible_agents: List of agent IDs to notify
            announcement_callback: Callback to send announcement

        Returns:
            Task ID
        """
        self._active_tasks[task.task_id] = task
        self._proposals[task.task_id] = []
        task.status = TaskStatus.ANNOUNCED

        for agent_id in eligible_agents:
            try:
                await self._send_announcement(task, agent_id, announcement_callback)
            except Exception as e:
                logger.error(f"Failed to announce to {agent_id}: {e}")

        logger.info(f"Task {task.task_id} announced to {len(eligible_agents)} agents")
        return task.task_id

    async def _send_announcement(self,
                                 task: Task,
                                 agent_id: str,
                                 callback: Callable) -> None:
        """Send task announcement to an agent."""
        if asyncio.iscoroutinefunction(callback):
            await callback(task, agent_id)
        else:
            callback(task, agent_id)

    def submit_proposal(self, proposal: Proposal) -> bool:
        """
        Submit a proposal for a task.

        Args:
            proposal: Agent's proposal

        Returns:
            True if proposal accepted
        """
        if proposal.task_id not in self._active_tasks:
            logger.warning(f"Task {proposal.task_id} not found")
            return False

        task = self._active_tasks[proposal.task_id]
        if task.status not in (TaskStatus.ANNOUNCED, TaskStatus.BIDDING):
            logger.warning(f"Task {proposal.task_id} not accepting proposals")
            return False

        task.status = TaskStatus.BIDDING
        self._proposals[proposal.task_id].append(proposal)

        logger.debug(f"Proposal from {proposal.agent_id} for task {proposal.task_id}")
        return True

    async def evaluate_proposals(self, task_id: str) -> Optional[Contract]:
        """
        Evaluate proposals and award contract.

        Args:
            task_id: Task identifier

        Returns:
            Contract if awarded, None otherwise
        """
        if task_id not in self._active_tasks:
            return None

        task = self._active_tasks[task_id]
        proposals = self._proposals.get(task_id, [])

        if not proposals:
            logger.warning(f"No proposals for task {task_id}")
            task.status = TaskStatus.CANCELLED
            return None

        # Select best proposal
        if self._evaluator:
            best = self._evaluator(proposals)
        else:
            best = self._default_evaluate(proposals)

        if not best:
            task.status = TaskStatus.CANCELLED
            return None

        # Create contract
        contract = Contract(
            contract_id=str(uuid.uuid4()),
            task=task,
            contractor_id=best.agent_id,
            proposal=best
        )

        # Update statuses
        task.status = TaskStatus.AWARDED
        best.status = ProposalStatus.ACCEPTED

        for p in proposals:
            if p.proposal_id != best.proposal_id:
                p.status = ProposalStatus.REJECTED

        self._contracts[contract.contract_id] = contract

        # Track agent's tasks
        if best.agent_id not in self._agent_tasks:
            self._agent_tasks[best.agent_id] = set()
        self._agent_tasks[best.agent_id].add(task_id)

        logger.info(f"Contract {contract.contract_id} awarded to {best.agent_id}")
        return contract

    def _default_evaluate(self, proposals: List[Proposal]) -> Optional[Proposal]:
        """Default proposal evaluation - lowest score wins."""
        if not proposals:
            return None

        valid = [p for p in proposals if p.status == ProposalStatus.PENDING]
        if not valid:
            return None

        return min(valid, key=lambda p: p.score())

    def start_execution(self, contract_id: str) -> bool:
        """Mark contract execution as started."""
        if contract_id not in self._contracts:
            return False

        contract = self._contracts[contract_id]
        contract.task.status = TaskStatus.EXECUTING
        logger.info(f"Contract {contract_id} execution started")
        return True

    def complete_task(self,
                     contract_id: str,
                     result: Dict[str, Any],
                     success: bool = True) -> bool:
        """
        Report task completion.

        Args:
            contract_id: Contract identifier
            result: Task execution result
            success: Whether task completed successfully

        Returns:
            True if completion recorded
        """
        if contract_id not in self._contracts:
            return False

        contract = self._contracts[contract_id]
        contract.completed_at = datetime.utcnow()
        contract.result = result
        contract.success = success
        contract.task.status = TaskStatus.COMPLETED if success else TaskStatus.FAILED

        # Remove from active tasks
        if contract.task.task_id in self._active_tasks:
            del self._active_tasks[contract.task.task_id]

        # Remove from agent's active tasks
        agent_id = contract.contractor_id
        if agent_id in self._agent_tasks:
            self._agent_tasks[agent_id].discard(contract.task.task_id)

        logger.info(f"Contract {contract_id} completed: success={success}")
        return True

    def get_contract(self, contract_id: str) -> Optional[Contract]:
        """Get contract by ID."""
        return self._contracts.get(contract_id)

    def get_agent_contracts(self, agent_id: str) -> List[Contract]:
        """Get all contracts for an agent."""
        return [
            c for c in self._contracts.values()
            if c.contractor_id == agent_id
        ]

    def get_pending_tasks(self) -> List[Task]:
        """Get tasks awaiting proposals."""
        return [
            t for t in self._active_tasks.values()
            if t.status in (TaskStatus.ANNOUNCED, TaskStatus.BIDDING)
        ]

    def cancel_task(self, task_id: str, reason: str = "") -> bool:
        """Cancel a task."""
        if task_id not in self._active_tasks:
            return False

        task = self._active_tasks[task_id]
        task.status = TaskStatus.CANCELLED

        # Reject all proposals
        for proposal in self._proposals.get(task_id, []):
            proposal.status = ProposalStatus.REJECTED

        logger.info(f"Task {task_id} cancelled: {reason}")
        return True

    def get_statistics(self) -> Dict[str, Any]:
        """Get protocol statistics."""
        contracts = list(self._contracts.values())
        return {
            'active_tasks': len(self._active_tasks),
            'total_contracts': len(contracts),
            'successful_contracts': len([c for c in contracts if c.success]),
            'failed_contracts': len([c for c in contracts if c.completed_at and not c.success]),
            'pending_contracts': len([c for c in contracts if not c.completed_at]),
            'avg_proposals_per_task': (
                sum(len(p) for p in self._proposals.values()) / len(self._proposals)
                if self._proposals else 0
            )
        }
