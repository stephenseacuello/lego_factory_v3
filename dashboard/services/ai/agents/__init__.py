"""
AI Agents - Autonomous Manufacturing Agents

LegoMCP World-Class Manufacturing System v5.0
Phase 17: AI Manufacturing Copilot

Provides autonomous agents for specific manufacturing domains:
- Quality Agent: Monitors quality and triggers interventions
- Scheduling Agent: Optimizes and adjusts schedules
- Maintenance Agent: Predicts and schedules maintenance
- Supervisor Agent: Coordinates other agents

Each agent can operate autonomously within defined boundaries
or escalate decisions requiring human approval.
"""

from .quality_agent import QualityAgent
from .scheduling_agent import SchedulingAgent
from .maintenance_agent import MaintenanceAgent

__all__ = [
    'QualityAgent',
    'SchedulingAgent',
    'MaintenanceAgent',
]
