"""
LEGO Factory v3 - MCP Tools
===========================
Tool definitions for Model Context Protocol server.

Tools are organized by category:
- SCADA: Machine control, alarms, historian
- MES: Work orders, scheduling, OEE
- ERP: Sales, purchasing, inventory, MRP
- QMS: Documents, NCR/CAPA
- CMMS: Assets, maintenance
- LEGO: Brick design, catalog, slicing
- ML: Fingerprinting, anomaly detection
- Robotics: Robot control, cell orchestration
- Unity: Digital Twin
"""

from services.mcp.server import ToolCategory, ToolDefinition

__all__ = [
    'ToolCategory',
    'ToolDefinition',
]
