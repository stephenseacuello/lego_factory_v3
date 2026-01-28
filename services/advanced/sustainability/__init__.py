"""
Sustainability & Carbon Tracking Module
=======================================

LegoMCP PhD-Level Manufacturing Platform
Part of the Sustainable Manufacturing Research (Phase 4)

This module provides comprehensive sustainability capabilities aligned with:
- ISO 14040/14044 (Life Cycle Assessment)
- ISO 14067 (Carbon Footprint)
- GHG Protocol (Greenhouse Gas Accounting)
- Science Based Targets initiative (SBTi)

Why Sustainability in Manufacturing?
------------------------------------
Manufacturing accounts for ~20% of global CO2 emissions. Key drivers:
- **Energy Consumption**: Process energy, HVAC, lighting
- **Material Usage**: Raw materials, packaging, waste
- **Transportation**: Supply chain, product distribution
- **End of Life**: Product disposal, recycling potential

The module enables data-driven sustainability decisions by tracking:
- Real-time carbon emissions per operation/product
- Energy efficiency opportunities
- Material circularity metrics
- Scope 1, 2, and 3 emissions

Components:
-----------

1. **CarbonTracker**:
   - Real-time CO2 equivalent tracking
   - Per-operation and per-product footprint
   - Scope 1/2/3 emissions breakdown
   - Emission factors database (EPA, DEFRA, etc.)
   - Trend analysis and forecasting

2. **EnergyOptimizer**:
   - Production schedule optimization for carbon
   - Renewable energy alignment
   - Demand response integration
   - Peak shaving recommendations
   - Energy efficiency opportunities

3. **LCA Services** (lca/):
   - Life Cycle Assessment engine
   - Impact categories (GWP, AP, EP, etc.)
   - Cradle-to-gate analysis
   - Eco-design optimization
   - Environmental product declarations

4. **Circular Economy** (circular/):
   - Material flow analysis
   - Recycling optimization
   - Design for disassembly
   - Waste reduction strategies
   - Closed-loop supply chain

Emission Categories:
--------------------
- **Scope 1**: Direct emissions (on-site combustion)
- **Scope 2**: Indirect from purchased energy
- **Scope 3**: Value chain emissions
  - Upstream: Materials, transportation, waste
  - Downstream: Product use, end-of-life

Example Usage:
--------------
    from services.sustainability import (
        CarbonTracker,
        EnergyOptimizer,
    )

    # Carbon tracking
    tracker = CarbonTracker()

    # Track operation emissions
    emissions = tracker.track_operation(
        operation_id="OP-001",
        energy_kwh=150,
        material_kg=10,
        material_type="ABS_plastic",
    )
    print(f"CO2e: {emissions.total_co2e_kg:.2f} kg")

    # Get product carbon footprint
    footprint = tracker.get_product_footprint(product_id="BRICK-2x4")
    print(f"Product footprint: {footprint.total_kg_co2e:.2f} kg CO2e")

    # Energy optimization
    optimizer = EnergyOptimizer()

    # Optimize schedule for carbon
    schedule = optimizer.optimize_for_carbon(
        jobs=production_jobs,
        renewable_forecast=solar_forecast,
        carbon_price=50,  # $/ton CO2
    )

    # Get efficiency recommendations
    recommendations = optimizer.get_efficiency_recommendations(
        equipment_id="CNC-001",
        period_days=30,
    )

Integration with Standards:
---------------------------
- GHG Protocol compliant reporting
- SBTi target tracking
- EU Taxonomy alignment
- CBAM (Carbon Border Adjustment) ready
- EPD generation support

Research Contributions:
-----------------------
- Novel multi-objective carbon-aware scheduling
- AI-powered emission prediction
- Circular economy optimization algorithms
- Supply chain Scope 3 estimation

References:
-----------
- ISO 14040/14044 (LCA Standards)
- ISO 14067 (Carbon Footprint of Products)
- GHG Protocol Corporate Standard
- Allwood, J. et al. (2011). Material Efficiency: A White Paper

Author: LegoMCP Team
Version: 2.0.0
"""

# Carbon Tracking
from .carbon_tracker import CarbonTracker, get_carbon_tracker

# Energy Optimization
from .energy_optimizer import EnergyOptimizer, get_energy_optimizer

# LCA Services
from .lca import (
    LCAEngine,
    ImpactCategories,
    LCAOptimizer,
    LCAResult,
    ImpactCategory,
)

# Carbon Management
from .carbon import (
    CarbonOptimizer,
    RenewableScheduler,
    Scope3Tracker,
    EmissionFactor,
    CarbonBudget,
)

# Circular Economy
from .circular import (
    MaterialFlowAnalyzer,
    RecyclingOptimizer,
    DesignForDisassembly,
    CircularityMetrics,
    WasteReducer,
)

__all__ = [
    # Carbon Tracking
    "CarbonTracker",
    "get_carbon_tracker",

    # Energy
    "EnergyOptimizer",
    "get_energy_optimizer",

    # LCA
    "LCAEngine",
    "ImpactCategories",
    "LCAOptimizer",
    "LCAResult",
    "ImpactCategory",

    # Carbon
    "CarbonOptimizer",
    "RenewableScheduler",
    "Scope3Tracker",
    "EmissionFactor",
    "CarbonBudget",

    # Circular
    "MaterialFlowAnalyzer",
    "RecyclingOptimizer",
    "DesignForDisassembly",
    "CircularityMetrics",
    "WasteReducer",
]

__version__ = "2.0.0"
__author__ = "LegoMCP Team"
