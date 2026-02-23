"""
LEGO MCP V8 Co-Simulation Services
===================================

Unified simulation coordination combining:
- Discrete Event Simulation (DES)
- Physics-Informed Neural Network (PINN) Digital Twin
- Monte Carlo Analysis
- What-If Scenario Planning
- Individual Simulation Engines

Author: LEGO MCP Engineering Team
Version: 8.0.0
"""

from .coordinator import CoSimulationCoordinator, SimulationMode, SimulationResult
from .scenario_manager import ScenarioManager, Scenario, ScenarioComparison
from .simulation_engines import (
    EngineState,
    EngineResult,
    SimulationEngineBase,
    DESEngine,
    MonteCarloEngine,
    PINNEngine,
    DiscreteEvent,
    Entity,
    MonteCarloSample,
    get_engine,
    list_engines,
    register_engine,
)

__all__ = [
    # Coordinator
    'CoSimulationCoordinator',
    'SimulationMode',
    'SimulationResult',
    # Scenario Manager
    'ScenarioManager',
    'Scenario',
    'ScenarioComparison',
    # Simulation Engines
    'EngineState',
    'EngineResult',
    'SimulationEngineBase',
    'DESEngine',
    'MonteCarloEngine',
    'PINNEngine',
    'DiscreteEvent',
    'Entity',
    'MonteCarloSample',
    'get_engine',
    'list_engines',
    'register_engine',
]

__version__ = '8.0.0'
