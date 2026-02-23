"""
Unit Tests for Supply Chain Excellence Services.

Tests Risk Assessment, Inventory Optimizer, Logistics Tracker, S&OP Planner, and Supplier Quality.
"""

import pytest
from datetime import datetime, timedelta
from decimal import Decimal
import asyncio

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from dashboard.services.supply_chain.risk_assessment import (
    SupplyChainRiskService, RiskCategory, RiskLevel, RiskMitigation,
    create_risk_service
)
from dashboard.services.supply_chain.inventory_optimizer import (
    InventoryOptimizerService, ABCClass, XYZClass, ReplenishmentStrategy,
    create_inventory_optimizer
)
from dashboard.services.supply_chain.logistics_tracker import (
    LogisticsTrackerService, ShipmentStatus, TransportMode, CarrierType,
    create_logistics_tracker
)
from dashboard.services.supply_chain.sop_planner import (
    SOPPlannerService, PlanningHorizon, DemandType, ConstraintType,
    create_sop_planner
)
from dashboard.services.supply_chain.supplier_quality import (
    SupplierQualityService, SupplierTier, AuditType, AuditResult,
    create_supplier_quality_service
)


class TestSupplyChainRiskService:
    """Tests for Supply Chain Risk Assessment."""

    @pytest.fixture
    def risk_service(self):
        """Create risk service instance."""
        return create_risk_service()

    @pytest.mark.asyncio
    async def test_register_supplier(self, risk_service):
        """Test registering a supplier for risk monitoring."""
        supplier = await risk_service.register_supplier(
            supplier_id="SUP-001",
            supplier_name="Acme Materials",
            country="China",
            region="Guangdong",
            tier=1,
            critical_materials=["ABS plastic", "Steel pins"]
        )

        assert supplier.supplier_id == "SUP-001"
        assert supplier.country == "China"
        assert supplier.tier == 1

    @pytest.mark.asyncio
    async def test_assess_geopolitical_risk(self, risk_service):
        """Test geopolitical risk assessment."""
        await risk_service.register_supplier(
            supplier_id="SUP-001",
            supplier_name="Test Supplier",
            country="Taiwan",
            region="Taipei",
            tier=1
        )

        risk = await risk_service.assess_risk(
            supplier_id="SUP-001",
            category=RiskCategory.GEOPOLITICAL
        )

        assert risk is not None
        assert risk.category == RiskCategory.GEOPOLITICAL
        assert risk.level in [RiskLevel.LOW, RiskLevel.MEDIUM, RiskLevel.HIGH, RiskLevel.CRITICAL]
        assert risk.score >= 0 and risk.score <= 100

    @pytest.mark.asyncio
    async def test_assess_financial_risk(self, risk_service):
        """Test financial risk assessment."""
        await risk_service.register_supplier(
            supplier_id="SUP-002",
            supplier_name="Stable Corp",
            country="Germany",
            region="Bavaria",
            tier=1,
            financial_rating="A+"
        )

        risk = await risk_service.assess_risk(
            supplier_id="SUP-002",
            category=RiskCategory.FINANCIAL
        )

        assert risk is not None
        assert risk.category == RiskCategory.FINANCIAL

    @pytest.mark.asyncio
    async def test_create_mitigation_plan(self, risk_service):
        """Test creating risk mitigation plan."""
        await risk_service.register_supplier(
            supplier_id="SUP-003",
            supplier_name="Risk Corp",
            country="Ukraine",
            region="Kyiv",
            tier=2
        )

        risk = await risk_service.assess_risk(
            supplier_id="SUP-003",
            category=RiskCategory.GEOPOLITICAL
        )

        mitigation = await risk_service.create_mitigation_plan(
            risk_id=risk.risk_id,
            strategy=RiskMitigation.DUAL_SOURCE,
            actions=[
                "Identify alternative supplier in Poland",
                "Build 60-day safety stock",
                "Establish VMI agreement"
            ],
            owner="procurement_manager"
        )

        assert mitigation is not None
        assert mitigation.strategy == RiskMitigation.DUAL_SOURCE

    @pytest.mark.asyncio
    async def test_aggregate_supply_chain_risk(self, risk_service):
        """Test aggregating risks across supply chain."""
        # Register multiple suppliers
        for i in range(3):
            await risk_service.register_supplier(
                supplier_id=f"SUP-{i:03d}",
                supplier_name=f"Supplier {i}",
                country="USA",
                region="California",
                tier=1
            )

        aggregate = await risk_service.get_aggregate_risk()

        assert "overall_score" in aggregate
        assert "risk_by_category" in aggregate
        assert "high_risk_suppliers" in aggregate


class TestInventoryOptimizerService:
    """Tests for Inventory Optimization."""

    @pytest.fixture
    def inventory_service(self):
        """Create inventory optimizer instance."""
        return create_inventory_optimizer()

    @pytest.mark.asyncio
    async def test_register_sku(self, inventory_service):
        """Test registering an SKU."""
        sku = await inventory_service.register_sku(
            sku_id="BRICK-2X4-RED",
            description="2x4 LEGO Brick - Red",
            unit_cost=0.10,
            lead_time_days=14,
            min_order_quantity=1000,
            storage_location="WAREHOUSE-A"
        )

        assert sku.sku_id == "BRICK-2X4-RED"
        assert sku.unit_cost == 0.10
        assert sku.lead_time_days == 14

    @pytest.mark.asyncio
    async def test_abc_xyz_classification(self, inventory_service):
        """Test ABC/XYZ classification."""
        # Register SKUs with different usage patterns
        await inventory_service.register_sku(
            sku_id="HIGH-VALUE",
            description="High value item",
            unit_cost=100.0,
            annual_usage=10000
        )
        await inventory_service.register_sku(
            sku_id="LOW-VALUE",
            description="Low value item",
            unit_cost=0.05,
            annual_usage=100
        )

        classification = await inventory_service.classify_abc_xyz("HIGH-VALUE")

        assert classification is not None
        assert classification.abc_class in [ABCClass.A, ABCClass.B, ABCClass.C]
        assert classification.xyz_class in [XYZClass.X, XYZClass.Y, XYZClass.Z]

    @pytest.mark.asyncio
    async def test_calculate_safety_stock(self, inventory_service):
        """Test safety stock calculation."""
        await inventory_service.register_sku(
            sku_id="BRICK-001",
            description="Test Brick",
            unit_cost=0.15,
            lead_time_days=7,
            demand_variability=0.2,
            lead_time_variability=0.1
        )

        safety_stock = await inventory_service.calculate_safety_stock(
            sku_id="BRICK-001",
            service_level=0.95
        )

        assert safety_stock > 0

    @pytest.mark.asyncio
    async def test_calculate_reorder_point(self, inventory_service):
        """Test reorder point calculation."""
        await inventory_service.register_sku(
            sku_id="BRICK-002",
            description="Test Brick 2",
            unit_cost=0.20,
            lead_time_days=10,
            average_daily_demand=500
        )

        reorder_point = await inventory_service.calculate_reorder_point(
            sku_id="BRICK-002",
            service_level=0.95
        )

        # ROP should be at least lead_time * avg_demand
        assert reorder_point >= 5000  # 10 days * 500/day

    @pytest.mark.asyncio
    async def test_generate_replenishment_plan(self, inventory_service):
        """Test generating replenishment plan."""
        await inventory_service.register_sku(
            sku_id="BRICK-003",
            description="Test Brick 3",
            unit_cost=0.25,
            lead_time_days=5,
            current_stock=100,
            reorder_point=500
        )

        plan = await inventory_service.generate_replenishment_plan(
            sku_ids=["BRICK-003"],
            planning_horizon_days=30
        )

        assert plan is not None
        assert "recommendations" in plan


class TestLogisticsTrackerService:
    """Tests for Logistics Tracking."""

    @pytest.fixture
    def logistics_service(self):
        """Create logistics tracker instance."""
        return create_logistics_tracker()

    @pytest.mark.asyncio
    async def test_register_carrier(self, logistics_service):
        """Test registering a carrier."""
        carrier = await logistics_service.register_carrier(
            carrier_id="FEDEX",
            carrier_name="FedEx Express",
            carrier_type=CarrierType.PARCEL,
            api_credentials={"api_key": "test_key"}
        )

        assert carrier.carrier_id == "FEDEX"
        assert carrier.carrier_type == CarrierType.PARCEL

    @pytest.mark.asyncio
    async def test_create_shipment(self, logistics_service):
        """Test creating a shipment."""
        await logistics_service.register_carrier(
            carrier_id="UPS",
            carrier_name="UPS",
            carrier_type=CarrierType.PARCEL
        )

        shipment = await logistics_service.create_shipment(
            shipment_id="SHIP-001",
            carrier_id="UPS",
            origin={"city": "Los Angeles", "country": "USA"},
            destination={"city": "New York", "country": "USA"},
            transport_mode=TransportMode.GROUND,
            items=[
                {"sku": "BRICK-001", "quantity": 10000, "weight_kg": 50}
            ],
            estimated_delivery=datetime.now() + timedelta(days=5)
        )

        assert shipment.shipment_id == "SHIP-001"
        assert shipment.status == ShipmentStatus.CREATED

    @pytest.mark.asyncio
    async def test_update_shipment_status(self, logistics_service):
        """Test updating shipment status."""
        await logistics_service.register_carrier("DHL", "DHL Express", CarrierType.PARCEL)
        await logistics_service.create_shipment(
            shipment_id="SHIP-002",
            carrier_id="DHL",
            origin={"city": "Shanghai", "country": "China"},
            destination={"city": "Hamburg", "country": "Germany"},
            transport_mode=TransportMode.SEA,
            items=[{"sku": "BRICK-BULK", "quantity": 1000000, "weight_kg": 5000}]
        )

        updated = await logistics_service.update_status(
            shipment_id="SHIP-002",
            status=ShipmentStatus.IN_TRANSIT,
            location={"city": "Singapore", "country": "Singapore"},
            notes="Transshipment at Singapore port"
        )

        assert updated.status == ShipmentStatus.IN_TRANSIT

    @pytest.mark.asyncio
    async def test_track_shipment(self, logistics_service):
        """Test tracking shipment."""
        await logistics_service.register_carrier("MAERSK", "Maersk Line", CarrierType.OCEAN)
        await logistics_service.create_shipment(
            shipment_id="SHIP-003",
            carrier_id="MAERSK",
            origin={"city": "Shenzhen", "country": "China"},
            destination={"city": "Rotterdam", "country": "Netherlands"},
            transport_mode=TransportMode.SEA,
            items=[]
        )

        tracking = await logistics_service.track_shipment("SHIP-003")

        assert tracking is not None
        assert "status" in tracking
        assert "history" in tracking

    @pytest.mark.asyncio
    async def test_calculate_shipping_cost(self, logistics_service):
        """Test shipping cost calculation."""
        await logistics_service.register_carrier(
            "FEDEX",
            "FedEx",
            CarrierType.PARCEL,
            rate_card={"base_rate": 10.0, "per_kg": 2.5}
        )

        cost = await logistics_service.calculate_cost(
            carrier_id="FEDEX",
            weight_kg=25,
            dimensions={"length": 50, "width": 40, "height": 30},
            origin="USA",
            destination="Canada"
        )

        assert cost > 0


class TestSOPPlannerService:
    """Tests for Sales & Operations Planning."""

    @pytest.fixture
    def sop_service(self):
        """Create S&OP planner instance."""
        return create_sop_planner()

    @pytest.mark.asyncio
    async def test_create_demand_forecast(self, sop_service):
        """Test creating demand forecast."""
        forecast = await sop_service.create_demand_forecast(
            product_family="LEGO-Classic",
            forecast_data=[
                {"month": "2024-01", "quantity": 100000},
                {"month": "2024-02", "quantity": 120000},
                {"month": "2024-03", "quantity": 150000}
            ],
            demand_type=DemandType.BASE,
            confidence=0.85
        )

        assert forecast is not None
        assert forecast.product_family == "LEGO-Classic"
        assert len(forecast.periods) == 3

    @pytest.mark.asyncio
    async def test_create_supply_plan(self, sop_service):
        """Test creating supply plan."""
        # First create demand forecast
        await sop_service.create_demand_forecast(
            product_family="LEGO-Technic",
            forecast_data=[
                {"month": "2024-01", "quantity": 50000}
            ],
            demand_type=DemandType.BASE
        )

        supply_plan = await sop_service.create_supply_plan(
            product_family="LEGO-Technic",
            planning_horizon=PlanningHorizon.TACTICAL,
            capacity_constraints=[
                {"resource": "Assembly Line 1", "capacity_units": 40000}
            ]
        )

        assert supply_plan is not None
        assert "production_schedule" in supply_plan

    @pytest.mark.asyncio
    async def test_run_consensus_meeting(self, sop_service):
        """Test running S&OP consensus meeting."""
        # Setup forecasts
        await sop_service.create_demand_forecast(
            product_family="ALL",
            forecast_data=[
                {"month": "2024-01", "quantity": 500000}
            ],
            demand_type=DemandType.BASE
        )

        consensus = await sop_service.run_consensus(
            meeting_date=datetime.now(),
            participants=["sales_vp", "operations_vp", "finance_vp"],
            agenda_items=["Q1 Demand Review", "Capacity Constraints", "New Product Launch"]
        )

        assert consensus is not None
        assert "decisions" in consensus
        assert "action_items" in consensus

    @pytest.mark.asyncio
    async def test_scenario_planning(self, sop_service):
        """Test scenario planning."""
        scenarios = await sop_service.create_scenarios(
            product_family="LEGO-Star-Wars",
            base_demand=200000,
            scenarios=[
                {"name": "Optimistic", "growth_rate": 0.20},
                {"name": "Base", "growth_rate": 0.05},
                {"name": "Pessimistic", "growth_rate": -0.10}
            ]
        )

        assert len(scenarios) == 3
        assert scenarios[0].name == "Optimistic"


class TestSupplierQualityService:
    """Tests for Supplier Quality Management."""

    @pytest.fixture
    def sqm_service(self):
        """Create supplier quality service instance."""
        return create_supplier_quality_service()

    @pytest.mark.asyncio
    async def test_register_supplier(self, sqm_service):
        """Test registering supplier for quality management."""
        supplier = await sqm_service.register_supplier(
            supplier_id="QUAL-SUP-001",
            supplier_name="Quality Materials Inc",
            tier=SupplierTier.STRATEGIC,
            quality_certifications=["ISO 9001", "IATF 16949"],
            products_supplied=["ABS Pellets", "Colorants"]
        )

        assert supplier.supplier_id == "QUAL-SUP-001"
        assert supplier.tier == SupplierTier.STRATEGIC
        assert "ISO 9001" in supplier.quality_certifications

    @pytest.mark.asyncio
    async def test_create_supplier_scorecard(self, sqm_service):
        """Test creating supplier scorecard."""
        await sqm_service.register_supplier(
            supplier_id="QUAL-SUP-002",
            supplier_name="Test Supplier",
            tier=SupplierTier.PREFERRED
        )

        scorecard = await sqm_service.create_scorecard(
            supplier_id="QUAL-SUP-002",
            period="2024-Q1",
            metrics={
                "quality_ppm": 50,
                "on_time_delivery": 0.98,
                "cost_competitiveness": 0.85,
                "responsiveness": 0.90
            }
        )

        assert scorecard is not None
        assert scorecard.overall_score > 0

    @pytest.mark.asyncio
    async def test_schedule_audit(self, sqm_service):
        """Test scheduling supplier audit."""
        await sqm_service.register_supplier(
            supplier_id="QUAL-SUP-003",
            supplier_name="Audit Target Supplier",
            tier=SupplierTier.APPROVED
        )

        audit = await sqm_service.schedule_audit(
            supplier_id="QUAL-SUP-003",
            audit_type=AuditType.PROCESS,
            scheduled_date=datetime.now() + timedelta(days=30),
            scope=["Quality Management System", "Production Process", "Incoming Inspection"],
            auditors=["lead_auditor", "quality_engineer"]
        )

        assert audit is not None
        assert audit.audit_type == AuditType.PROCESS

    @pytest.mark.asyncio
    async def test_record_audit_results(self, sqm_service):
        """Test recording audit results."""
        await sqm_service.register_supplier("QUAL-SUP-004", "Test", SupplierTier.APPROVED)
        audit = await sqm_service.schedule_audit(
            supplier_id="QUAL-SUP-004",
            audit_type=AuditType.QUALITY_SYSTEM,
            scheduled_date=datetime.now(),
            scope=["QMS Review"]
        )

        results = await sqm_service.record_audit_results(
            audit_id=audit.audit_id,
            result=AuditResult.PASS_WITH_OBSERVATIONS,
            findings=[
                {"category": "Minor", "description": "Calibration records incomplete"},
                {"category": "Observation", "description": "Training matrix needs update"}
            ],
            score=85,
            auditor_notes="Overall good quality system with minor improvements needed"
        )

        assert results.result == AuditResult.PASS_WITH_OBSERVATIONS
        assert results.score == 85

    @pytest.mark.asyncio
    async def test_supplier_development_plan(self, sqm_service):
        """Test creating supplier development plan."""
        await sqm_service.register_supplier(
            supplier_id="QUAL-SUP-005",
            supplier_name="Development Target",
            tier=SupplierTier.CONDITIONAL
        )

        plan = await sqm_service.create_development_plan(
            supplier_id="QUAL-SUP-005",
            objectives=[
                "Achieve ISO 9001 certification within 12 months",
                "Reduce quality PPM from 500 to 100",
                "Implement SPC for critical processes"
            ],
            milestones=[
                {"description": "Complete ISO gap analysis", "target_date": datetime.now() + timedelta(days=30)},
                {"description": "SPC training completed", "target_date": datetime.now() + timedelta(days=60)}
            ],
            resources_committed=["Quality engineer support", "Training materials"]
        )

        assert plan is not None
        assert len(plan.objectives) == 3


class TestSupplyChainIntegration:
    """Integration tests for supply chain scenarios."""

    @pytest.mark.asyncio
    async def test_supplier_risk_to_inventory_adjustment(self):
        """Test risk assessment triggering inventory adjustment."""
        risk_service = create_risk_service()
        inventory_service = create_inventory_optimizer()

        # Register high-risk supplier
        await risk_service.register_supplier(
            supplier_id="HIGH-RISK-SUP",
            supplier_name="High Risk Supplier",
            country="High-Risk-Region",
            tier=1,
            critical_materials=["Critical Component"]
        )

        # Assess risk
        risk = await risk_service.assess_risk(
            supplier_id="HIGH-RISK-SUP",
            category=RiskCategory.GEOPOLITICAL
        )

        # Register SKU from this supplier
        await inventory_service.register_sku(
            sku_id="CRITICAL-001",
            description="Critical Component",
            unit_cost=5.00,
            lead_time_days=30,
            primary_supplier="HIGH-RISK-SUP"
        )

        # If high risk, increase safety stock
        if risk.level in [RiskLevel.HIGH, RiskLevel.CRITICAL]:
            adjusted_safety_stock = await inventory_service.calculate_safety_stock(
                sku_id="CRITICAL-001",
                service_level=0.99,  # Higher service level for critical items
                risk_multiplier=1.5
            )
            assert adjusted_safety_stock > 0

    @pytest.mark.asyncio
    async def test_sop_to_logistics_planning(self):
        """Test S&OP driving logistics planning."""
        sop_service = create_sop_planner()
        logistics_service = create_logistics_tracker()

        # Create demand forecast
        await sop_service.create_demand_forecast(
            product_family="LEGO-City",
            forecast_data=[
                {"month": "2024-06", "quantity": 200000}
            ],
            demand_type=DemandType.PROMOTIONAL
        )

        # Create supply plan
        supply_plan = await sop_service.create_supply_plan(
            product_family="LEGO-City",
            planning_horizon=PlanningHorizon.TACTICAL
        )

        # Register carrier
        await logistics_service.register_carrier(
            "SEA-CARRIER",
            "Ocean Freight Co",
            CarrierType.OCEAN
        )

        # Plan shipments based on supply plan
        if supply_plan:
            shipment = await logistics_service.create_shipment(
                shipment_id="SOP-SHIP-001",
                carrier_id="SEA-CARRIER",
                origin={"city": "Shenzhen", "country": "China"},
                destination={"city": "Los Angeles", "country": "USA"},
                transport_mode=TransportMode.SEA,
                items=[{"sku": "LEGO-City-Kit", "quantity": 200000}]
            )
            assert shipment is not None

    @pytest.mark.asyncio
    async def test_quality_issue_triggers_supplier_action(self):
        """Test quality issue triggering supplier quality action."""
        sqm_service = create_supplier_quality_service()

        # Register supplier
        await sqm_service.register_supplier(
            supplier_id="QUALITY-ISSUE-SUP",
            supplier_name="Quality Issue Supplier",
            tier=SupplierTier.PREFERRED
        )

        # Record poor scorecard
        scorecard = await sqm_service.create_scorecard(
            supplier_id="QUALITY-ISSUE-SUP",
            period="2024-Q1",
            metrics={
                "quality_ppm": 500,  # High defect rate
                "on_time_delivery": 0.75,  # Poor delivery
                "cost_competitiveness": 0.90,
                "responsiveness": 0.60  # Slow response
            }
        )

        # If score is low, trigger audit
        if scorecard.overall_score < 70:
            audit = await sqm_service.schedule_audit(
                supplier_id="QUALITY-ISSUE-SUP",
                audit_type=AuditType.QUALITY_SYSTEM,
                scheduled_date=datetime.now() + timedelta(days=14),
                scope=["Root cause of quality issues", "Process capability review"]
            )
            assert audit is not None

            # Create improvement plan
            plan = await sqm_service.create_development_plan(
                supplier_id="QUALITY-ISSUE-SUP",
                objectives=["Reduce PPM to <100", "Improve OTD to >95%"]
            )
            assert plan is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
