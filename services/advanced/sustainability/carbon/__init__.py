"""
Carbon-Neutral Production Planning Module.

This module implements carbon-aware manufacturing scheduling:
- Real-time carbon intensity tracking
- Renewable energy-aligned scheduling
- Scope 1/2/3 emissions tracking
- Carbon offset integration

Research Value:
- Novel carbon-aware scheduling algorithms
- Integration of real-time grid carbon intensity
- Multi-objective optimization with carbon constraints

References:
- GHG Protocol Corporate Standard
- Science Based Targets initiative (SBTi)
- ISO 14064 - Greenhouse gases
"""

from .carbon_optimizer import (
    CarbonOptimizer,
    CarbonConfig,
    EmissionScope,
    CarbonIntensity,
    ProductionSchedule,
    CarbonResult,
)
from .renewable_scheduler import (
    RenewableScheduler,
    RenewableConfig,
    EnergySource,
    GridForecast,
    RenewableWindow,
)
from .scope3_tracker import (
    Scope3Tracker,
    Scope3Category,
    SupplyChainEmission,
    TransportEmission,
    EmissionInventory,
)

__all__ = [
    # Carbon Optimizer
    'CarbonOptimizer',
    'CarbonConfig',
    'EmissionScope',
    'CarbonIntensity',
    'ProductionSchedule',
    'CarbonResult',
    # Renewable Scheduler
    'RenewableScheduler',
    'RenewableConfig',
    'EnergySource',
    'GridForecast',
    'RenewableWindow',
    # Scope 3 Tracker
    'Scope3Tracker',
    'Scope3Category',
    'SupplyChainEmission',
    'TransportEmission',
    'EmissionInventory',
]
