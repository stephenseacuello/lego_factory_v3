"""
LEGO MCP Supervisor - OTP-style supervision patterns for ROS2 nodes.

This package provides fault-tolerant node supervision with restart strategies
inspired by Erlang/OTP supervisors:

Restart Strategies:
- ONE_FOR_ONE: Only restart the failed child
- ONE_FOR_ALL: Restart all children if one fails
- REST_FOR_ONE: Restart the failed child and all children started after it

Components:
- SupervisorNode: Main supervisor node implementing OTP-style supervision
- HeartbeatMixin: Mixin class providing heartbeat functionality for monitored nodes

Usage:
    from lego_mcp_supervisor import SupervisorNode, HeartbeatMixin
    from lego_mcp_supervisor import RestartStrategy, ChildSpec
"""

from lego_mcp_supervisor.supervisor_node import (
    SupervisorNode,
    RestartStrategy,
    ChildSpec,
    ChildState,
    RestartType,
)
from lego_mcp_supervisor.heartbeat import HeartbeatMixin, HeartbeatMonitor
from lego_mcp_supervisor.checkpoint_manager import (
    CheckpointManager,
    CheckpointMixin,
    PeriodicCheckpointer,
    Checkpoint,
    CheckpointMetadata,
    CheckpointType,
)

__all__ = [
    # Supervisor
    "SupervisorNode",
    "RestartStrategy",
    "ChildSpec",
    "ChildState",
    "RestartType",
    # Heartbeat
    "HeartbeatMixin",
    "HeartbeatMonitor",
    # Checkpoint
    "CheckpointManager",
    "CheckpointMixin",
    "PeriodicCheckpointer",
    "Checkpoint",
    "CheckpointMetadata",
    "CheckpointType",
]

__version__ = "1.0.0"
