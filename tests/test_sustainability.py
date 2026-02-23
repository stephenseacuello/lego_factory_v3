"""
Sustainability Module Tests.

Tests for Phase 4 Sustainable Manufacturing components:
- Life Cycle Assessment (LCA)
- Carbon-Neutral Production Planning
- Circular Economy Metrics
"""

import unittest
import sys
import os
from datetime import datetime, timedelta
from typing import Dict, Any, List

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestLCAEngine(unittest.TestCase):
    """Tests for Life Cycle Assessment engine."""

    def setUp(self):
        """Set up test fixtures."""
        from dashboard.services.sustainability.lca.lca_engine import (
            LCAPhase, InventoryItem, ImpactResult, LCAEngine, ManufacturingLCA
        )
        self.LCAPhase = LCAPhase
        self.InventoryItem = InventoryItem
        self.ImpactResult = ImpactResult
        self.LCAEngine = LCAEngine
        self.ManufacturingLCA = ManufacturingLCA

    def test_lca_phases(self):
        """Test LCA phase enumeration."""
        phases = list(self.LCAPhase)

        self.assertIn(self.LCAPhase.RAW_MATERIAL, phases)
        self.assertIn(self.LCAPhase.MANUFACTURING, phases)
        self.assertIn(self.LCAPhase.USE, phases)
        self.assertIn(self.LCAPhase.END_OF_LIFE, phases)

    def test_inventory_item_creation(self):
        """Test inventory item creation."""
        item = self.InventoryItem(
            name="PLA Filament",
            category="Material",
            amount=1.0,
            unit="kg",
            phase=self.LCAPhase.RAW_MATERIAL
        )

        self.assertEqual(item.name, "PLA Filament")
        self.assertEqual(item.amount, 1.0)

    def test_lca_engine_creation(self):
        """Test LCA engine creation."""
        engine = self.LCAEngine()

        self.assertIsNotNone(engine)
        self.assertIsNotNone(engine.impact_database)

    def test_lca_inventory_analysis(self):
        """Test life cycle inventory analysis."""
        engine = self.LCAEngine()

        inventory = [
            self.InventoryItem("PLA", "Material", 0.5, "kg", self.LCAPhase.RAW_MATERIAL),
            self.InventoryItem("Electricity", "Energy", 2.0, "kWh", self.LCAPhase.MANUFACTURING),
        ]

        result = engine.analyze_inventory(inventory)

        self.assertIn("total_inputs", result)
        self.assertIn("total_outputs", result)
        self.assertIn("by_phase", result)

    def test_lca_impact_assessment(self):
        """Test life cycle impact assessment."""
        engine = self.LCAEngine()

        inventory = [
            self.InventoryItem("PLA", "Material", 0.5, "kg", self.LCAPhase.RAW_MATERIAL),
            self.InventoryItem("Electricity", "Energy", 2.0, "kWh", self.LCAPhase.MANUFACTURING),
        ]

        impacts = engine.assess_impacts(inventory)

        self.assertIn("climate_change", impacts)
        self.assertIn("acidification", impacts)
        self.assertIsInstance(impacts["climate_change"], float)

    def test_manufacturing_lca_product(self):
        """Test manufacturing LCA for product."""
        lca = self.ManufacturingLCA()

        result = lca.assess_product(
            material="PLA",
            mass_kg=0.1,
            print_time_hours=2.0,
            energy_consumption_kwh=0.5
        )

        self.assertIn("total_gwp", result)
        self.assertIn("by_phase", result)
        self.assertIn("hotspots", result)

    def test_lca_comparison(self):
        """Test LCA comparison between scenarios."""
        lca = self.ManufacturingLCA()

        scenario_a = lca.assess_product("PLA", 0.1, 2.0, 0.5)
        scenario_b = lca.assess_product("ABS", 0.1, 2.0, 0.6)

        comparison = lca.compare_scenarios(scenario_a, scenario_b)

        self.assertIn("gwp_difference", comparison)
        self.assertIn("better_scenario", comparison)


class TestImpactCategories(unittest.TestCase):
    """Tests for environmental impact categories."""

    def setUp(self):
        """Set up test fixtures."""
        from dashboard.services.sustainability.lca.impact_categories import (
            ClimateChange, Acidification, Eutrophication,
            ImpactCategoryManager, ManufacturingImpactAssessment
        )
        self.ClimateChange = ClimateChange
        self.Acidification = Acidification
        self.Eutrophication = Eutrophication
        self.ImpactCategoryManager = ImpactCategoryManager
        self.ManufacturingImpactAssessment = ManufacturingImpactAssessment

    def test_climate_change_gwp(self):
        """Test climate change GWP calculation."""
        cc = self.ClimateChange()

        # CO2 has GWP of 1
        co2_impact = cc.calculate_impact({"CO2": 1.0})
        self.assertAlmostEqual(co2_impact, 1.0, places=2)

        # CH4 has higher GWP
        ch4_impact = cc.calculate_impact({"CH4": 1.0})
        self.assertGreater(ch4_impact, 1.0)

    def test_acidification_calculation(self):
        """Test acidification potential calculation."""
        acid = self.Acidification()

        impact = acid.calculate_impact({"SO2": 1.0, "NOx": 0.5})

        self.assertGreater(impact, 0)

    def test_eutrophication_calculation(self):
        """Test eutrophication potential calculation."""
        eutr = self.Eutrophication()

        impact = eutr.calculate_impact({"NOx": 1.0, "PO4": 0.1})

        self.assertGreater(impact, 0)

    def test_impact_category_manager(self):
        """Test impact category manager."""
        manager = self.ImpactCategoryManager()

        # Get all registered categories
        categories = manager.get_categories()

        self.assertIn("climate_change", categories)
        self.assertIn("acidification", categories)

    def test_manufacturing_impact_assessment(self):
        """Test manufacturing-specific impact assessment."""
        assessment = self.ManufacturingImpactAssessment()

        emissions = {
            "CO2": 10.0,
            "CH4": 0.1,
            "SO2": 0.05,
            "NOx": 0.1,
        }

        result = assessment.assess_all_impacts(emissions)

        self.assertIn("climate_change", result)
        self.assertIn("acidification", result)
        self.assertIn("normalized_scores", result)


class TestCarbonOptimizer(unittest.TestCase):
    """Tests for carbon-aware production optimization."""

    def setUp(self):
        """Set up test fixtures."""
        from dashboard.services.sustainability.carbon.carbon_optimizer import (
            CarbonIntensity, ProductionJob, CarbonOptimizer,
            ManufacturingCarbonOptimizer
        )
        self.CarbonIntensity = CarbonIntensity
        self.ProductionJob = ProductionJob
        self.CarbonOptimizer = CarbonOptimizer
        self.ManufacturingCarbonOptimizer = ManufacturingCarbonOptimizer

    def test_carbon_intensity_creation(self):
        """Test carbon intensity data creation."""
        intensity = self.CarbonIntensity(
            timestamp=datetime.now(),
            value=400.0,
            unit="gCO2/kWh",
            source="grid"
        )

        self.assertEqual(intensity.value, 400.0)

    def test_production_job_creation(self):
        """Test production job creation."""
        job = self.ProductionJob(
            job_id="J001",
            energy_kwh=5.0,
            duration_hours=2.0,
            deadline=datetime.now() + timedelta(hours=24)
        )

        self.assertEqual(job.energy_kwh, 5.0)

    def test_carbon_optimizer_scheduling(self):
        """Test carbon-aware scheduling."""
        optimizer = self.CarbonOptimizer()

        jobs = [
            self.ProductionJob("J1", 5.0, 2.0, datetime.now() + timedelta(hours=24)),
            self.ProductionJob("J2", 3.0, 1.0, datetime.now() + timedelta(hours=12)),
        ]

        # Mock carbon intensity forecast
        forecast = [
            self.CarbonIntensity(datetime.now() + timedelta(hours=i), 400 - i * 10, "gCO2/kWh", "grid")
            for i in range(24)
        ]

        schedule = optimizer.optimize_schedule(jobs, forecast)

        self.assertIn("schedule", schedule)
        self.assertIn("total_emissions", schedule)

    def test_manufacturing_carbon_optimizer(self):
        """Test manufacturing-specific carbon optimization."""
        optimizer = self.ManufacturingCarbonOptimizer()

        result = optimizer.plan_production(
            jobs=[
                {"id": "J1", "energy": 10.0, "duration": 2.0},
                {"id": "J2", "energy": 5.0, "duration": 1.0},
            ],
            planning_horizon_hours=24
        )

        self.assertIn("scheduled_jobs", result)
        self.assertIn("emissions_saved", result)


class TestRenewableScheduler(unittest.TestCase):
    """Tests for renewable energy scheduling."""

    def setUp(self):
        """Set up test fixtures."""
        from dashboard.services.sustainability.carbon.renewable_scheduler import (
            SolarForecaster, WindForecaster, BatteryStorage, RenewableScheduler
        )
        self.SolarForecaster = SolarForecaster
        self.WindForecaster = WindForecaster
        self.BatteryStorage = BatteryStorage
        self.RenewableScheduler = RenewableScheduler

    def test_solar_forecaster(self):
        """Test solar power forecasting."""
        forecaster = self.SolarForecaster(
            capacity_kw=100.0,
            latitude=37.7749,
            longitude=-122.4194
        )

        forecast = forecaster.forecast(hours_ahead=24)

        self.assertEqual(len(forecast), 24)
        # Solar should be zero at night
        self.assertTrue(any(f["power_kw"] > 0 for f in forecast))

    def test_wind_forecaster(self):
        """Test wind power forecasting."""
        forecaster = self.WindForecaster(capacity_kw=50.0)

        forecast = forecaster.forecast(hours_ahead=24)

        self.assertEqual(len(forecast), 24)
        self.assertTrue(all("power_kw" in f for f in forecast))

    def test_battery_storage(self):
        """Test battery storage simulation."""
        battery = self.BatteryStorage(
            capacity_kwh=100.0,
            max_charge_kw=25.0,
            max_discharge_kw=25.0,
            initial_soc=0.5
        )

        # Test charging
        result = battery.charge(10.0, duration_hours=1.0)
        self.assertGreater(battery.state_of_charge, 0.5)

        # Test discharging
        result = battery.discharge(5.0, duration_hours=1.0)
        self.assertIsNotNone(result)

    def test_renewable_scheduler(self):
        """Test renewable energy production scheduler."""
        scheduler = self.RenewableScheduler(
            solar_capacity_kw=100.0,
            wind_capacity_kw=50.0,
            battery_capacity_kwh=200.0
        )

        jobs = [
            {"id": "J1", "energy_kwh": 50.0, "duration_hours": 2.0},
            {"id": "J2", "energy_kwh": 30.0, "duration_hours": 1.0},
        ]

        result = scheduler.schedule_with_renewables(jobs, planning_horizon_hours=24)

        self.assertIn("schedule", result)
        self.assertIn("renewable_utilization", result)
        self.assertIn("grid_usage", result)


class TestScope3Tracker(unittest.TestCase):
    """Tests for Scope 3 emissions tracking."""

    def setUp(self):
        """Set up test fixtures."""
        from dashboard.services.sustainability.carbon.scope3_tracker import (
            Scope3Category, EmissionFactorDatabase, Scope3Tracker
        )
        self.Scope3Category = Scope3Category
        self.EmissionFactorDatabase = EmissionFactorDatabase
        self.Scope3Tracker = Scope3Tracker

    def test_scope3_categories(self):
        """Test Scope 3 category enumeration."""
        categories = list(self.Scope3Category)

        # GHG Protocol defines 15 categories
        self.assertEqual(len(categories), 15)

        self.assertIn(self.Scope3Category.PURCHASED_GOODS, categories)
        self.assertIn(self.Scope3Category.TRANSPORTATION, categories)
        self.assertIn(self.Scope3Category.USE_OF_SOLD_PRODUCTS, categories)

    def test_emission_factor_database(self):
        """Test emission factor database."""
        db = self.EmissionFactorDatabase()

        # Get factor for material
        factor = db.get_factor("PLA", "material")

        self.assertIsNotNone(factor)
        self.assertGreater(factor, 0)

    def test_scope3_tracker_creation(self):
        """Test Scope 3 tracker creation."""
        tracker = self.Scope3Tracker()

        self.assertIsNotNone(tracker)

    def test_scope3_purchased_goods(self):
        """Test tracking purchased goods emissions."""
        tracker = self.Scope3Tracker()

        result = tracker.track_purchased_goods(
            items=[
                {"name": "PLA Filament", "quantity_kg": 10.0},
                {"name": "Steel Parts", "quantity_kg": 5.0},
            ]
        )

        self.assertIn("total_emissions", result)
        self.assertIn("by_item", result)

    def test_scope3_transportation(self):
        """Test tracking transportation emissions."""
        tracker = self.Scope3Tracker()

        result = tracker.track_transportation(
            shipments=[
                {"weight_kg": 100.0, "distance_km": 500.0, "mode": "truck"},
                {"weight_kg": 50.0, "distance_km": 2000.0, "mode": "air"},
            ]
        )

        self.assertIn("total_emissions", result)
        # Air freight should have higher emissions
        self.assertGreater(result["by_shipment"][1]["emissions"],
                          result["by_shipment"][0]["emissions"])

    def test_scope3_full_report(self):
        """Test full Scope 3 emissions report."""
        tracker = self.Scope3Tracker()

        # Add various emissions
        tracker.track_purchased_goods([{"name": "Material", "quantity_kg": 100.0}])
        tracker.track_transportation([{"weight_kg": 100.0, "distance_km": 500.0, "mode": "truck"}])

        report = tracker.generate_report()

        self.assertIn("total_scope3", report)
        self.assertIn("by_category", report)
        self.assertIn("reduction_opportunities", report)


class TestLCAOptimizer(unittest.TestCase):
    """Tests for LCA optimization."""

    def setUp(self):
        """Set up test fixtures."""
        from dashboard.services.sustainability.lca.lca_optimizer import (
            DesignVariable, OptimizationConstraint, LCAOptimizer
        )
        self.DesignVariable = DesignVariable
        self.OptimizationConstraint = OptimizationConstraint
        self.LCAOptimizer = LCAOptimizer

    def test_design_variable(self):
        """Test design variable definition."""
        var = self.DesignVariable(
            name="wall_thickness",
            min_value=0.5,
            max_value=3.0,
            current_value=1.0
        )

        self.assertEqual(var.name, "wall_thickness")
        self.assertTrue(var.is_valid(1.5))
        self.assertFalse(var.is_valid(5.0))

    def test_optimization_constraint(self):
        """Test optimization constraint."""
        constraint = self.OptimizationConstraint(
            name="min_strength",
            type=">=",
            value=100.0
        )

        self.assertTrue(constraint.is_satisfied(150.0))
        self.assertFalse(constraint.is_satisfied(50.0))

    def test_lca_optimizer(self):
        """Test LCA multi-objective optimization."""
        optimizer = self.LCAOptimizer()

        variables = [
            self.DesignVariable("material_mass", 0.05, 0.5, 0.1),
            self.DesignVariable("infill_percent", 10, 100, 20),
        ]

        constraints = [
            self.OptimizationConstraint("min_strength", ">=", 50.0),
        ]

        result = optimizer.optimize(
            variables=variables,
            constraints=constraints,
            objectives=["minimize_gwp", "minimize_cost"]
        )

        self.assertIn("pareto_solutions", result)
        self.assertIn("recommended", result)


if __name__ == "__main__":
    unittest.main()
