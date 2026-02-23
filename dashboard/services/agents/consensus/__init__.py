"""
Consensus Protocols - Multi-agent decision making.

LEGO MCP v6.0 World-Class Manufacturing Research Platform
Phase 1: Multi-Agent Orchestration Framework
"""

from .voting import WeightedVoting, VoteResult
from .auction import ResourceAuction, Bid, AuctionResult
from .contract_net import ContractNetProtocol, Task, Proposal

__all__ = [
    'WeightedVoting',
    'VoteResult',
    'ResourceAuction',
    'Bid',
    'AuctionResult',
    'ContractNetProtocol',
    'Task',
    'Proposal',
]
