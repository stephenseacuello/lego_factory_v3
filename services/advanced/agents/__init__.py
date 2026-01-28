"""
Agent Orchestration Framework - LEGO MCP v6.0

Multi-agent coordination system for manufacturing intelligence.
Provides unified communication bus, consensus protocols, and HTN planning.
"""

from .message_bus import MessageBus, Message, MessageType
from .agent_registry import AgentRegistry, AgentInfo, AgentStatus
from .orchestrator import AgentOrchestrator
from .collaboration_protocol import CollaborationProtocol

__all__ = [
    'MessageBus',
    'Message',
    'MessageType',
    'AgentRegistry',
    'AgentInfo',
    'AgentStatus',
    'AgentOrchestrator',
    'CollaborationProtocol',
]
