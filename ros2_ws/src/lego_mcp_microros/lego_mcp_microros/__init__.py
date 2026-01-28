"""
LEGO MCP Micro-ROS Package

Micro-ROS agent configuration and ESP32 firmware templates
for Alvik AGVs.

LEGO MCP Manufacturing System v7.0
"""

__version__ = "7.0.0"

from .microros_agent_launcher import MicroROSAgentLauncher

__all__ = ['MicroROSAgentLauncher']
