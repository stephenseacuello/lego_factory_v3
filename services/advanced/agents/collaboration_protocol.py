"""
Collaboration Protocol - Agent cooperation patterns.

LEGO MCP v6.0 World-Class Manufacturing Research Platform
Phase 1: Multi-Agent Orchestration Framework

Defines protocols for agent collaboration on complex tasks.
"""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Set
from enum import Enum
import uuid
import logging

logger = logging.getLogger(__name__)


class CollaborationType(Enum):
    """Types of agent collaboration."""
    SEQUENTIAL = "sequential"      # Agents work in sequence
    PARALLEL = "parallel"          # Agents work simultaneously
    HIERARCHICAL = "hierarchical"  # Manager delegates to workers
    PEER = "peer"                  # Equal collaboration
    BLACKBOARD = "blackboard"      # Shared workspace model


@dataclass
class CollaborationSession:
    """Active collaboration session between agents."""
    session_id: str
    collaboration_type: CollaborationType
    initiator: str
    participants: Set[str]
    goal: str
    shared_state: Dict[str, Any] = field(default_factory=dict)
    contributions: List[Dict[str, Any]] = field(default_factory=list)
    status: str = "active"
    created_at: datetime = field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None


class CollaborationProtocol:
    """
    Manages multi-agent collaboration patterns.

    Supports various collaboration models:
    - Sequential: Pipeline processing
    - Parallel: Concurrent work with aggregation
    - Hierarchical: Manager-worker delegation
    - Peer: Equal collaboration with negotiation
    - Blackboard: Shared workspace with opportunistic contributions
    """

    def __init__(self):
        self._sessions: Dict[str, CollaborationSession] = {}
        self._blackboards: Dict[str, Dict[str, Any]] = {}

    async def create_session(self,
                            collaboration_type: CollaborationType,
                            initiator: str,
                            participants: Set[str],
                            goal: str,
                            initial_state: Optional[Dict[str, Any]] = None) -> str:
        """
        Create a new collaboration session.

        Args:
            collaboration_type: Type of collaboration
            initiator: Agent initiating collaboration
            participants: Set of participating agent IDs
            goal: Collaboration goal description
            initial_state: Optional initial shared state

        Returns:
            Session ID
        """
        session_id = str(uuid.uuid4())

        session = CollaborationSession(
            session_id=session_id,
            collaboration_type=collaboration_type,
            initiator=initiator,
            participants=participants,
            goal=goal,
            shared_state=initial_state or {}
        )

        self._sessions[session_id] = session

        if collaboration_type == CollaborationType.BLACKBOARD:
            self._blackboards[session_id] = {}

        logger.info(f"Collaboration session {session_id} created: {collaboration_type.value}")
        return session_id

    async def contribute(self,
                        session_id: str,
                        agent_id: str,
                        contribution: Dict[str, Any]) -> bool:
        """
        Add a contribution to a collaboration session.

        Args:
            session_id: Session identifier
            agent_id: Contributing agent
            contribution: Agent's contribution

        Returns:
            True if contribution accepted
        """
        if session_id not in self._sessions:
            return False

        session = self._sessions[session_id]
        if agent_id not in session.participants:
            logger.warning(f"Agent {agent_id} not in session {session_id}")
            return False

        if session.status != "active":
            return False

        session.contributions.append({
            'agent_id': agent_id,
            'timestamp': datetime.utcnow().isoformat(),
            'content': contribution
        })

        # Update shared state if provided
        if 'state_update' in contribution:
            session.shared_state.update(contribution['state_update'])

        logger.debug(f"Agent {agent_id} contributed to session {session_id}")
        return True

    async def execute_sequential(self,
                                session_id: str,
                                agent_order: List[str],
                                task_executor: Callable) -> Dict[str, Any]:
        """
        Execute sequential collaboration (pipeline).

        Each agent processes the output of the previous agent.
        """
        if session_id not in self._sessions:
            return {'error': 'Session not found'}

        session = self._sessions[session_id]
        current_state = session.shared_state.copy()

        for agent_id in agent_order:
            if agent_id not in session.participants:
                continue

            try:
                result = await task_executor(agent_id, current_state)
                current_state.update(result.get('output', {}))

                await self.contribute(session_id, agent_id, {
                    'stage_result': result,
                    'state_update': result.get('output', {})
                })
            except Exception as e:
                logger.error(f"Sequential execution failed at {agent_id}: {e}")
                return {'error': str(e), 'failed_at': agent_id}

        session.shared_state = current_state
        return {'success': True, 'final_state': current_state}

    async def execute_parallel(self,
                              session_id: str,
                              task_executor: Callable,
                              aggregator: Callable) -> Dict[str, Any]:
        """
        Execute parallel collaboration.

        All agents work simultaneously, results are aggregated.
        """
        if session_id not in self._sessions:
            return {'error': 'Session not found'}

        session = self._sessions[session_id]

        # Execute all agents in parallel
        tasks = []
        for agent_id in session.participants:
            task = asyncio.create_task(
                task_executor(agent_id, session.shared_state)
            )
            tasks.append((agent_id, task))

        # Gather results
        results = {}
        for agent_id, task in tasks:
            try:
                result = await task
                results[agent_id] = result

                await self.contribute(session_id, agent_id, {
                    'parallel_result': result
                })
            except Exception as e:
                logger.error(f"Parallel execution failed for {agent_id}: {e}")
                results[agent_id] = {'error': str(e)}

        # Aggregate results
        aggregated = await aggregator(results)
        session.shared_state.update(aggregated)

        return {'success': True, 'results': results, 'aggregated': aggregated}

    async def blackboard_post(self,
                             session_id: str,
                             agent_id: str,
                             knowledge_type: str,
                             content: Any) -> bool:
        """
        Post to blackboard shared workspace.

        Args:
            session_id: Session identifier
            agent_id: Posting agent
            knowledge_type: Type of knowledge being posted
            content: Knowledge content
        """
        if session_id not in self._blackboards:
            return False

        session = self._sessions.get(session_id)
        if not session or agent_id not in session.participants:
            return False

        self._blackboards[session_id][knowledge_type] = {
            'content': content,
            'posted_by': agent_id,
            'timestamp': datetime.utcnow().isoformat()
        }

        await self.contribute(session_id, agent_id, {
            'blackboard_post': {
                'type': knowledge_type,
                'content': content
            }
        })

        return True

    def blackboard_read(self,
                        session_id: str,
                        knowledge_type: Optional[str] = None) -> Dict[str, Any]:
        """Read from blackboard."""
        if session_id not in self._blackboards:
            return {}

        if knowledge_type:
            return self._blackboards[session_id].get(knowledge_type, {})
        return self._blackboards[session_id]

    async def complete_session(self,
                              session_id: str,
                              final_result: Optional[Dict[str, Any]] = None) -> bool:
        """Complete a collaboration session."""
        if session_id not in self._sessions:
            return False

        session = self._sessions[session_id]
        session.status = "completed"
        session.completed_at = datetime.utcnow()

        if final_result:
            session.shared_state['final_result'] = final_result

        logger.info(f"Collaboration session {session_id} completed")
        return True

    def get_session(self, session_id: str) -> Optional[CollaborationSession]:
        """Get session details."""
        return self._sessions.get(session_id)

    def get_agent_sessions(self, agent_id: str) -> List[CollaborationSession]:
        """Get all sessions an agent is participating in."""
        return [
            s for s in self._sessions.values()
            if agent_id in s.participants and s.status == "active"
        ]
