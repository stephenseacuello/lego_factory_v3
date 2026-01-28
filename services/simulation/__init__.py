"""
LEGO Factory v3 - Simulation Package
=====================================
Discrete-event simulation engine for production schedule validation
and algorithm comparison.
"""

from services.simulation.des_engine import (
    DiscreteEventSimulator,
    SimulationClock,
    EventQueue,
    SimEvent,
    EventType,
    SimConfig,
    SimResult,
)
from services.simulation.stochastic_models import (
    BreakdownModel,
    QualityModel,
    MaterialShortageModel,
    SetupVariabilityModel,
    ProcessTimeModel,
)
from services.simulation.sim_reporter import SimReporter
from services.simulation.scenario_runner import run_scenario, compare_algorithms
from services.simulation.live_simulator import (
    LiveSimulator,
    LiveSimConfig,
    get_active_simulator,
    start_live_simulation,
    stop_live_simulation,
)
from services.simulation.sim_state import (
    SimulationState,
    get_simulation_state,
    is_simulation_running,
)

__all__ = [
    # DES Engine
    'DiscreteEventSimulator',
    'SimulationClock',
    'EventQueue',
    'SimEvent',
    'EventType',
    'SimConfig',
    'SimResult',
    # Stochastic Models
    'BreakdownModel',
    'QualityModel',
    'MaterialShortageModel',
    'SetupVariabilityModel',
    'ProcessTimeModel',
    # Reporter
    'SimReporter',
    # Scenario Runner
    'run_scenario',
    'compare_algorithms',
    # Live Simulation
    'LiveSimulator',
    'LiveSimConfig',
    'get_active_simulator',
    'start_live_simulation',
    'stop_live_simulation',
    # State Management
    'SimulationState',
    'get_simulation_state',
    'is_simulation_running',
]
