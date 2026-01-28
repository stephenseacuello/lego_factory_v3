"""
Agent Orchestrator - Central coordination for multi-agent system.

LEGO MCP v6.0 World-Class Manufacturing Research Platform
Phase 1: Multi-Agent Orchestration Framework

Coordinates Quality, Scheduling, and Maintenance agents using
hierarchical task decomposition and consensus protocols.
"""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Set, Callable
from enum import Enum
import uuid
import logging

from .message_bus import MessageBus, Message, MessageType, Priority
from .agent_registry import AgentRegistry, AgentInfo, AgentStatus, AgentCapability
from .consensus.contract_net import ContractNetProtocol, Task, Proposal, Contract
from .consensus.voting import WeightedVoting, VoteChoice, VoteResult

logger = logging.getLogger(__name__)


class DecisionType(Enum):
    """Types of coordinated decisions."""
    QUALITY_INTERVENTION = "quality_intervention"
    SCHEDULE_CHANGE = "schedule_change"
    MAINTENANCE_TRIGGER = "maintenance_trigger"
    PROCESS_ADJUSTMENT = "process_adjustment"
    RESOURCE_ALLOCATION = "resource_allocation"
    EMERGENCY_STOP = "emergency_stop"


@dataclass
class ManufacturingContext:
    """
    Current manufacturing context for decision-making.

    Aggregates state from all agents and sensors.
    """
    timestamp: datetime = field(default_factory=datetime.utcnow)
    active_jobs: List[Dict[str, Any]] = field(default_factory=list)
    equipment_status: Dict[str, Any] = field(default_factory=dict)
    quality_metrics: Dict[str, Any] = field(default_factory=dict)
    resource_availability: Dict[str, Any] = field(default_factory=dict)
    alerts: List[Dict[str, Any]] = field(default_factory=list)
    predictions: Dict[str, Any] = field(default_factory=dict)

    def has_critical_alerts(self) -> bool:
        """Check for critical alerts."""
        return any(a.get('severity') == 'critical' for a in self.alerts)


@dataclass
class CoordinatedDecision:
    """Result of multi-agent coordination."""
    decision_id: str
    decision_type: DecisionType
    action: str
    parameters: Dict[str, Any]
    contributing_agents: List[str]
    confidence: float
    consensus_result: Optional[VoteResult] = None
    contract: Optional[Contract] = None
    timestamp: datetime = field(default_factory=datetime.utcnow)
    executed: bool = False
    execution_result: Optional[Dict[str, Any]] = None


class AgentOrchestrator:
    """
    Central orchestrator for multi-agent manufacturing intelligence.

    Coordinates:
    - Quality Agent: Monitors and predicts quality issues
    - Scheduling Agent: Optimizes production schedules
    - Maintenance Agent: Predicts and plans maintenance

    Features:
    - Hierarchical task decomposition
    - Multi-agent consensus for critical decisions
    - Conflict resolution between agents
    - Priority-based action coordination
    """

    def __init__(self):
        self.message_bus = MessageBus()
        self.registry = AgentRegistry()
        self.contract_net = ContractNetProtocol()
        self.voting = WeightedVoting()

        self._running = False
        self._context = ManufacturingContext()
        self._pending_decisions: Dict[str, CoordinatedDecision] = {}
        self._decision_history: List[CoordinatedDecision] = []
        self._decision_handlers: Dict[DecisionType, Callable] = {}

        # Agent type to weight mapping for voting
        self._agent_weights = {
            'quality': 1.2,      # Quality gets slight priority
            'scheduling': 1.0,
            'maintenance': 1.0,
            'safety': 1.5,       # Safety gets highest priority
        }

    async def start(self) -> None:
        """Start the orchestrator."""
        if self._running:
            return

        await self.message_bus.start()
        await self.registry.start()

        # Subscribe to agent messages
        self.message_bus.subscribe(
            'orchestrator',
            {'agent.*', 'decision.*', 'alert.*'},
            self._handle_message
        )

        self._running = True
        logger.info("Agent orchestrator started")

    async def stop(self) -> None:
        """Stop the orchestrator."""
        self._running = False
        await self.message_bus.stop()
        await self.registry.stop()
        logger.info("Agent orchestrator stopped")

    def register_decision_handler(self,
                                  decision_type: DecisionType,
                                  handler: Callable[[CoordinatedDecision], Any]) -> None:
        """Register a handler for decision execution."""
        self._decision_handlers[decision_type] = handler

    async def update_context(self, context: ManufacturingContext) -> None:
        """Update manufacturing context."""
        self._context = context

        # Broadcast context update to all agents
        await self.message_bus.broadcast(
            sender='orchestrator',
            topic='context.update',
            msg_type=MessageType.EVENT,
            payload={'context': context.__dict__}
        )

        # Check for critical conditions
        if context.has_critical_alerts():
            await self._handle_critical_alerts(context.alerts)

    async def coordinate_decision(self,
                                 decision_type: DecisionType,
                                 context: Optional[ManufacturingContext] = None,
                                 require_consensus: bool = True) -> CoordinatedDecision:
        """
        Coordinate a multi-agent decision.

        Args:
            decision_type: Type of decision to make
            context: Manufacturing context (uses current if not provided)
            require_consensus: Whether to require voting consensus

        Returns:
            CoordinatedDecision with action and parameters
        """
        context = context or self._context
        decision_id = str(uuid.uuid4())

        # 1. Gather proposals from relevant agents
        proposals = await self._gather_proposals(decision_type, context)

        if not proposals:
            logger.warning(f"No proposals for {decision_type}")
            return CoordinatedDecision(
                decision_id=decision_id,
                decision_type=decision_type,
                action="no_action",
                parameters={},
                contributing_agents=[],
                confidence=0.0
            )

        # 2. If consensus required, run voting
        consensus_result = None
        if require_consensus and len(proposals) > 1:
            consensus_result = await self._run_consensus(decision_id, proposals)

            if not consensus_result.approved:
                logger.info(f"Decision {decision_id} not approved by consensus")
                return CoordinatedDecision(
                    decision_id=decision_id,
                    decision_type=decision_type,
                    action="no_action",
                    parameters={'reason': 'consensus_not_reached'},
                    contributing_agents=[p['agent_id'] for p in proposals],
                    confidence=0.0,
                    consensus_result=consensus_result
                )

        # 3. Select best proposal
        best_proposal = self._select_best_proposal(proposals, decision_type)

        # 4. Create coordinated decision
        decision = CoordinatedDecision(
            decision_id=decision_id,
            decision_type=decision_type,
            action=best_proposal['action'],
            parameters=best_proposal['parameters'],
            contributing_agents=[p['agent_id'] for p in proposals],
            confidence=best_proposal.get('confidence', 0.8),
            consensus_result=consensus_result
        )

        self._pending_decisions[decision_id] = decision
        logger.info(f"Coordinated decision {decision_id}: {decision.action}")

        return decision

    async def execute_decision(self, decision_id: str) -> Dict[str, Any]:
        """
        Execute a coordinated decision.

        Args:
            decision_id: Decision identifier

        Returns:
            Execution result
        """
        if decision_id not in self._pending_decisions:
            return {'success': False, 'error': 'Decision not found'}

        decision = self._pending_decisions[decision_id]

        # Get handler for decision type
        handler = self._decision_handlers.get(decision.decision_type)
        if not handler:
            return {'success': False, 'error': 'No handler registered'}

        try:
            if asyncio.iscoroutinefunction(handler):
                result = await handler(decision)
            else:
                result = handler(decision)

            decision.executed = True
            decision.execution_result = result
            self._decision_history.append(decision)
            del self._pending_decisions[decision_id]

            # Notify agents of execution
            await self.message_bus.broadcast(
                sender='orchestrator',
                topic='decision.executed',
                msg_type=MessageType.EVENT,
                payload={
                    'decision_id': decision_id,
                    'action': decision.action,
                    'result': result
                }
            )

            return result

        except Exception as e:
            logger.error(f"Decision execution failed: {e}")
            return {'success': False, 'error': str(e)}

    async def delegate_task(self,
                           task: Task,
                           preferred_agent_type: Optional[str] = None) -> Optional[Contract]:
        """
        Delegate a task to the best available agent.

        Uses Contract Net Protocol for task allocation.
        """
        # Find eligible agents
        if preferred_agent_type:
            agents = self.registry.find_by_type(preferred_agent_type)
        else:
            # Find agents with required capabilities
            required = set(task.requirements.get('capabilities', []))
            agents = []
            for cap in required:
                if hasattr(AgentCapability, cap.upper()):
                    agents.extend(self.registry.find_by_capability(
                        AgentCapability[cap.upper()]
                    ))

        if not agents:
            logger.warning(f"No eligible agents for task {task.task_id}")
            return None

        # Announce task and collect proposals
        async def announce(t: Task, agent_id: str):
            await self.message_bus.send(
                sender='orchestrator',
                recipient=agent_id,
                msg_type=MessageType.TASK_ASSIGN,
                payload={'task': t.__dict__}
            )

        await self.contract_net.announce_task(
            task,
            [a.agent_id for a in agents],
            announce
        )

        # Wait for proposals
        await asyncio.sleep(self.contract_net.bid_timeout)

        # Evaluate and award
        contract = await self.contract_net.evaluate_proposals(task.task_id)
        return contract

    async def _gather_proposals(self,
                               decision_type: DecisionType,
                               context: ManufacturingContext) -> List[Dict[str, Any]]:
        """Gather proposals from relevant agents."""
        proposals = []

        # Determine which agents to query based on decision type
        agent_types = self._get_relevant_agent_types(decision_type)

        for agent_type in agent_types:
            agents = self.registry.find_by_type(agent_type)
            for agent in agents:
                if not agent.is_available():
                    continue

                # Request proposal from agent
                response = await self.message_bus.request_response(
                    Message(
                        type=MessageType.REQUEST,
                        sender='orchestrator',
                        recipient=agent.agent_id,
                        topic=f'decision.{decision_type.value}',
                        payload={
                            'decision_type': decision_type.value,
                            'context': context.__dict__
                        },
                        priority=Priority.HIGH
                    ),
                    timeout=10.0
                )

                if response and response.payload.get('proposal'):
                    proposals.append({
                        'agent_id': agent.agent_id,
                        'agent_type': agent.agent_type,
                        **response.payload['proposal']
                    })

        return proposals

    def _get_relevant_agent_types(self, decision_type: DecisionType) -> List[str]:
        """Get agent types relevant to a decision."""
        mapping = {
            DecisionType.QUALITY_INTERVENTION: ['quality', 'maintenance'],
            DecisionType.SCHEDULE_CHANGE: ['scheduling', 'quality'],
            DecisionType.MAINTENANCE_TRIGGER: ['maintenance', 'scheduling'],
            DecisionType.PROCESS_ADJUSTMENT: ['quality', 'scheduling', 'maintenance'],
            DecisionType.RESOURCE_ALLOCATION: ['scheduling'],
            DecisionType.EMERGENCY_STOP: ['quality', 'maintenance', 'safety'],
        }
        return mapping.get(decision_type, ['quality', 'scheduling', 'maintenance'])

    async def _run_consensus(self,
                            decision_id: str,
                            proposals: List[Dict[str, Any]]) -> VoteResult:
        """Run voting consensus on proposals."""
        # Set agent weights
        for proposal in proposals:
            agent_type = proposal.get('agent_type', 'default')
            weight = self._agent_weights.get(agent_type, 1.0)
            self.voting.set_agent_weight(proposal['agent_id'], weight)

        # Start vote
        eligible = [p['agent_id'] for p in proposals]
        self.voting.start_vote(decision_id, eligible)

        # Collect votes (agents vote on their own proposals)
        for proposal in proposals:
            self.voting.cast_vote(
                decision_id,
                proposal['agent_id'],
                VoteChoice.APPROVE if proposal.get('recommend', True) else VoteChoice.ABSTAIN,
                confidence=proposal.get('confidence', 0.8),
                reasoning=proposal.get('reasoning')
            )

        # Calculate total eligible weight
        total_weight = sum(
            self.voting.get_agent_weight(p['agent_id'])
            for p in proposals
        )

        return self.voting.tally_votes(decision_id, total_weight)

    def _select_best_proposal(self,
                             proposals: List[Dict[str, Any]],
                             decision_type: DecisionType) -> Dict[str, Any]:
        """Select the best proposal based on scoring."""
        if not proposals:
            return {'action': 'no_action', 'parameters': {}}

        # Score each proposal
        scored = []
        for p in proposals:
            score = self._score_proposal(p, decision_type)
            scored.append((score, p))

        scored.sort(key=lambda x: -x[0])  # Higher score is better
        return scored[0][1]

    def _score_proposal(self, proposal: Dict[str, Any], decision_type: DecisionType) -> float:
        """Score a proposal."""
        base_score = proposal.get('confidence', 0.5)

        # Weight by agent type
        agent_type = proposal.get('agent_type', 'default')
        type_weight = self._agent_weights.get(agent_type, 1.0)

        # Penalize for risk
        risk_penalty = proposal.get('risk', 0.0) * 0.3

        # Bonus for urgency alignment
        urgency_bonus = 0.0
        if proposal.get('urgent') and decision_type in (
            DecisionType.EMERGENCY_STOP,
            DecisionType.QUALITY_INTERVENTION
        ):
            urgency_bonus = 0.2

        return (base_score * type_weight) - risk_penalty + urgency_bonus

    async def _handle_critical_alerts(self, alerts: List[Dict[str, Any]]) -> None:
        """Handle critical alerts requiring immediate action."""
        critical = [a for a in alerts if a.get('severity') == 'critical']

        for alert in critical:
            logger.warning(f"Critical alert: {alert}")

            # Coordinate emergency response
            decision = await self.coordinate_decision(
                DecisionType.EMERGENCY_STOP,
                require_consensus=False  # No consensus needed for emergencies
            )

            if decision.action != 'no_action':
                await self.execute_decision(decision.decision_id)

    async def _handle_message(self, message: Message) -> None:
        """Handle incoming messages from agents."""
        if message.type == MessageType.STATUS:
            # Update agent status
            agent_id = message.sender
            status = message.payload.get('status')
            load = message.payload.get('load')
            if status:
                await self.registry.update_status(
                    agent_id,
                    AgentStatus(status),
                    load
                )

        elif message.type == MessageType.ALERT:
            # Add to context alerts
            self._context.alerts.append({
                'source': message.sender,
                'severity': message.payload.get('severity', 'info'),
                'message': message.payload.get('message'),
                'timestamp': datetime.utcnow().isoformat()
            })

        elif message.type == MessageType.HEARTBEAT:
            await self.registry.heartbeat(message.sender, message.payload.get('load'))

    def get_decision_history(self, limit: int = 100) -> List[CoordinatedDecision]:
        """Get recent decision history."""
        return self._decision_history[-limit:]

    def get_statistics(self) -> Dict[str, Any]:
        """Get orchestrator statistics."""
        return {
            'message_bus': self.message_bus.get_stats(),
            'registry': self.registry.get_stats(),
            'contract_net': self.contract_net.get_statistics(),
            'pending_decisions': len(self._pending_decisions),
            'total_decisions': len(self._decision_history),
            'successful_decisions': len([
                d for d in self._decision_history
                if d.execution_result and d.execution_result.get('success')
            ])
        }
