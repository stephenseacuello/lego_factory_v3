"""
Integration Tests for Manufacturing Workflows.

End-to-end tests for complete manufacturing scenarios including:
- Order-to-Delivery workflow
- Quality Event Management
- Predictive Maintenance
- Supply Chain Integration
"""

import pytest
from datetime import datetime, timedelta
import asyncio

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

# ERP Services
from dashboard.services.erp.order_service import create_order_service
from dashboard.services.erp.gl_integration import create_gl_service
from dashboard.services.erp.ar_ap_service import create_ar_service, create_ap_service

# Manufacturing Services
from dashboard.services.manufacturing.work_order_service import create_work_order_service
from dashboard.services.manufacturing.oee_calculator import create_oee_calculator
from dashboard.services.manufacturing.routing_service import create_routing_service

# Quality Services
from dashboard.services.quality.spc_engine import create_spc_engine
from dashboard.services.compliance.qms.capa_service import create_capa_service
from dashboard.services.compliance.qms.deviation_service import create_deviation_service
from dashboard.services.compliance.qms.batch_record import create_batch_record_service

# Supply Chain Services
from dashboard.services.supply_chain.inventory_optimizer import create_inventory_optimizer
from dashboard.services.supply_chain.logistics_tracker import create_logistics_tracker
from dashboard.services.supply_chain.supplier_quality import create_supplier_quality_service

# Advanced Technology
from dashboard.services.blockchain.traceability_ledger import create_traceability_service
from dashboard.services.cloud.edge_sync import create_cloud_edge_service


class TestOrderToDeliveryWorkflow:
    """End-to-end order-to-delivery workflow tests."""

    @pytest.mark.asyncio
    async def test_complete_order_lifecycle(self):
        """Test complete order from creation to delivery."""
        # Initialize services
        order_svc = create_order_service()
        work_order_svc = create_work_order_service()
        inventory_svc = create_inventory_optimizer()
        logistics_svc = create_logistics_tracker()
        ar_svc = create_ar_service()
        gl_svc = create_gl_service()

        # Initialize GL
        await gl_svc.initialize_manufacturing_coa()

        # Step 1: Create sales order
        order = await order_svc.create_order(
            customer_id="CUST-ACME",
            customer_name="ACME Corporation",
            items=[
                {"sku": "LEGO-42100", "quantity": 50, "unit_price": 399.99},
                {"sku": "LEGO-42125", "quantity": 25, "unit_price": 179.99}
            ],
            shipping_address={"city": "New York", "country": "USA"},
            requested_delivery_date=datetime.now() + timedelta(days=14)
        )

        assert order.order_id is not None
        assert order.status == "pending"

        # Step 2: Check inventory and create work orders if needed
        for item in order.items:
            sku_info = await inventory_svc.check_availability(
                sku_id=item["sku"],
                quantity=item["quantity"]
            )

            if not sku_info.get("available", False):
                # Create work order for production
                wo = await work_order_svc.create_work_order(
                    product_id=item["sku"],
                    quantity=item["quantity"],
                    priority="HIGH",
                    due_date=datetime.now() + timedelta(days=10),
                    sales_order_ref=order.order_id
                )
                assert wo.work_order_id is not None

        # Step 3: Release order for fulfillment
        released = await order_svc.release_order(
            order_id=order.order_id,
            released_by="order_management"
        )
        assert released.status == "released"

        # Step 4: Create shipment
        await logistics_svc.register_carrier("FEDEX", "FedEx", "PARCEL")
        shipment = await logistics_svc.create_shipment(
            shipment_id=f"SHIP-{order.order_id}",
            carrier_id="FEDEX",
            origin={"city": "Billund", "country": "Denmark"},
            destination=order.shipping_address,
            transport_mode="AIR",
            items=[
                {"sku": i["sku"], "quantity": i["quantity"]}
                for i in order.items
            ]
        )
        assert shipment is not None

        # Step 5: Create invoice
        total_amount = sum(i["quantity"] * i["unit_price"] for i in order.items)
        invoice = await ar_svc.create_invoice(
            customer_id=order.customer_id,
            customer_name=order.customer_name,
            amount=total_amount,
            payment_terms="NET_30",
            line_items=order.items,
            created_by="billing_system",
            sales_order_ref=order.order_id
        )
        await ar_svc.post_invoice(invoice.invoice_id, "ar_manager")

        assert invoice.invoice_id is not None

        # Step 6: Record revenue in GL
        entry = await gl_svc.record_sale(
            order_id=order.order_id,
            customer_id=order.customer_id,
            amount=total_amount,
            created_by="ar_system"
        )
        assert entry is not None

        # Step 7: Ship order
        shipped = await order_svc.ship_order(
            order_id=order.order_id,
            shipment_id=shipment.shipment_id,
            shipped_by="warehouse"
        )
        assert shipped.status == "shipped"

    @pytest.mark.asyncio
    async def test_order_with_quality_hold(self):
        """Test order workflow with quality hold."""
        order_svc = create_order_service()
        deviation_svc = create_deviation_service()
        batch_svc = create_batch_record_service()

        # Create order
        order = await order_svc.create_order(
            customer_id="CUST-QUAL",
            customer_name="Quality Customer",
            items=[{"sku": "LEGO-QUAL-001", "quantity": 100, "unit_price": 50.0}],
            shipping_address={"city": "Berlin", "country": "Germany"}
        )

        # Create batch for production
        await batch_svc.create_master_batch_record(
            "LEGO-QUAL-001", "Quality Test Product", "1.0", 100, "sets",
            steps=[{"step_number": 1, "description": "Final QC"}],
            created_by="engineer"
        )
        batch = await batch_svc.initiate_batch(
            "LEGO-QUAL-001", f"BATCH-{order.order_id}", 100, "production"
        )

        # Quality deviation found during production
        deviation = await deviation_svc.report_deviation(
            "Color variation detected",
            "PRODUCT",
            "MAJOR",
            "Color outside specification limits",
            "Molding",
            "qa_inspector",
            batch.batch_number
        )

        # Put order on hold
        held = await order_svc.hold_order(
            order_id=order.order_id,
            reason=f"Quality hold - deviation {deviation.deviation_number}",
            held_by="quality_manager"
        )
        assert held.status == "on_hold"

        # Resolve deviation
        await deviation_svc.assess_impact(
            deviation.deviation_id, "qa_eng",
            "Cosmetic only", "None", "None", 100, False
        )
        await deviation_svc.make_disposition(
            deviation.deviation_id, "USE_AS_IS",
            "Color within acceptable customer tolerance",
            "engineering_manager"
        )
        await deviation_svc.close_deviation(
            deviation.deviation_id, "qa_manager", "Resolved"
        )

        # Release order hold
        released = await order_svc.release_hold(
            order_id=order.order_id,
            released_by="quality_manager",
            notes="Deviation resolved"
        )
        assert released.status == "released"


class TestQualityEventManagement:
    """Integration tests for quality event workflows."""

    @pytest.mark.asyncio
    async def test_spc_alarm_to_capa(self):
        """Test SPC alarm triggering CAPA."""
        spc_engine = create_spc_engine()
        deviation_svc = create_deviation_service()
        capa_svc = create_capa_service()

        # Initialize SPC chart
        await spc_engine.create_chart(
            chart_id="TEMP-CHART-001",
            parameter="Temperature",
            ucl=225.0,
            lcl=215.0,
            target=220.0
        )

        # Record out-of-control point
        alarm = await spc_engine.record_measurement(
            chart_id="TEMP-CHART-001",
            value=228.5,  # Above UCL
            timestamp=datetime.now()
        )

        assert alarm.is_out_of_control

        # Create deviation for out-of-control condition
        deviation = await deviation_svc.report_deviation(
            f"SPC Out of Control - {alarm.violation_rule}",
            "PROCESS",
            "MAJOR",
            f"Temperature exceeded UCL: {alarm.value} > {alarm.ucl}",
            "Injection Molding",
            "spc_system",
            "CURRENT_BATCH"
        )

        # If pattern indicates systemic issue, create CAPA
        if alarm.violation_rule in ["RULE_1_BEYOND_3SIGMA", "RULE_2_ZONE_A"]:
            capa = await capa_svc.initiate_capa(
                f"SPC Pattern - {alarm.violation_rule}",
                "CORRECTIVE",
                "HIGH",
                f"SPC Chart {alarm.chart_id}",
                "Systemic process variation detected",
                [],
                "quality_engineer"
            )

            await deviation_svc.link_to_capa(
                deviation.deviation_id, capa.capa_id, "qa_manager"
            )

            assert capa.capa_id is not None
            assert deviation.linked_capa == capa.capa_id

    @pytest.mark.asyncio
    async def test_supplier_quality_escalation(self):
        """Test supplier quality issue escalation."""
        sqm_svc = create_supplier_quality_service()
        deviation_svc = create_deviation_service()
        capa_svc = create_capa_service()
        inventory_svc = create_inventory_optimizer()

        # Register supplier
        await sqm_svc.register_supplier(
            "SUP-QUALITY-TEST",
            "Quality Issue Supplier",
            "PREFERRED",
            quality_certifications=["ISO 9001"]
        )

        # Record poor quality scorecard (3 consecutive quarters)
        for quarter in ["2024-Q1", "2024-Q2", "2024-Q3"]:
            await sqm_svc.create_scorecard(
                "SUP-QUALITY-TEST",
                quarter,
                metrics={
                    "quality_ppm": 750,  # High defect rate
                    "on_time_delivery": 0.80,
                    "cost_competitiveness": 0.95,
                    "responsiveness": 0.70
                }
            )

        # Create deviation for incoming quality issue
        deviation = await deviation_svc.report_deviation(
            "Incoming Material Quality Issue",
            "MATERIAL",
            "CRITICAL",
            "30% of incoming lot fails inspection",
            "Receiving",
            "incoming_inspector",
            "LOT-SUP-2024-100"
        )

        # Escalate to CAPA due to recurring issues
        capa = await capa_svc.initiate_capa(
            "Recurring Supplier Quality Issues",
            "CORRECTIVE",
            "CRITICAL",
            "Supplier Quality Management",
            "Multiple quality failures from supplier SUP-QUALITY-TEST",
            ["LOT-SUP-2024-100"],
            "supplier_quality_manager"
        )

        # Schedule supplier audit
        audit = await sqm_svc.schedule_audit(
            "SUP-QUALITY-TEST",
            "QUALITY_SYSTEM",
            datetime.now() + timedelta(days=7),
            ["Quality Management System", "Process Controls", "Inspection Methods"]
        )

        # Update inventory to increase safety stock
        await inventory_svc.register_sku(
            "MAT-FROM-SUP",
            "Material from Problem Supplier",
            unit_cost=10.0,
            lead_time_days=21,
            primary_supplier="SUP-QUALITY-TEST"
        )

        # Increase safety stock due to quality risk
        new_safety_stock = await inventory_svc.calculate_safety_stock(
            "MAT-FROM-SUP",
            service_level=0.99,
            risk_multiplier=2.0  # Double due to supplier issues
        )

        assert capa.capa_id is not None
        assert audit.audit_id is not None
        assert new_safety_stock > 0


class TestPredictiveMaintenanceWorkflow:
    """Integration tests for predictive maintenance workflows."""

    @pytest.mark.asyncio
    async def test_equipment_failure_prediction_to_work_order(self):
        """Test equipment failure prediction triggering maintenance."""
        work_order_svc = create_work_order_service()
        oee_calc = create_oee_calculator()

        # Simulate equipment health degradation detected by ML model
        equipment_id = "MOLD-MACHINE-001"
        failure_probability = 0.85
        predicted_failure_date = datetime.now() + timedelta(days=3)
        failure_mode = "Heater element degradation"

        # Record OEE decline as supporting evidence
        await oee_calc.record_shift(
            equipment_id=equipment_id,
            shift_date=datetime.now() - timedelta(days=1),
            planned_time_minutes=480,
            actual_running_time=400,
            ideal_cycle_time=0.5,
            total_pieces=700,
            good_pieces=680
        )

        oee = await oee_calc.calculate_oee(equipment_id)

        # If failure probability high and OEE declining, create maintenance WO
        if failure_probability > 0.75:
            wo = await work_order_svc.create_maintenance_order(
                equipment_id=equipment_id,
                maintenance_type="PREDICTIVE",
                priority="URGENT",
                description=f"Predicted failure: {failure_mode}",
                scheduled_date=datetime.now() + timedelta(days=1),
                estimated_duration_hours=4,
                created_by="predictive_maintenance_system",
                failure_probability=failure_probability
            )

            assert wo.work_order_id is not None
            assert wo.maintenance_type == "PREDICTIVE"


class TestSupplyChainIntegration:
    """Integration tests for supply chain workflows."""

    @pytest.mark.asyncio
    async def test_material_shortage_response(self):
        """Test response to material shortage scenario."""
        inventory_svc = create_inventory_optimizer()
        logistics_svc = create_logistics_tracker()
        work_order_svc = create_work_order_service()

        # Register critical SKU
        await inventory_svc.register_sku(
            "CRIT-COMPONENT-001",
            "Critical Component",
            unit_cost=25.0,
            lead_time_days=30,
            current_stock=500,
            reorder_point=1000,
            average_daily_demand=100
        )

        # Check for shortage condition
        replenishment = await inventory_svc.generate_replenishment_plan(
            sku_ids=["CRIT-COMPONENT-001"],
            planning_horizon_days=60
        )

        # Shortage detected
        if replenishment["shortage_alerts"]:
            # Create expedited shipment request
            await logistics_svc.register_carrier(
                "EXPRESS-FREIGHT", "Express Freight Co", "AIR_FREIGHT"
            )

            expedited_shipment = await logistics_svc.create_shipment(
                shipment_id="EXPEDITE-CRIT-001",
                carrier_id="EXPRESS-FREIGHT",
                origin={"city": "Shanghai", "country": "China"},
                destination={"city": "Los Angeles", "country": "USA"},
                transport_mode="AIR",
                items=[{"sku": "CRIT-COMPONENT-001", "quantity": 2000}],
                expedited=True
            )

            # Adjust production schedule if necessary
            affected_wos = await work_order_svc.find_affected_work_orders(
                component_id="CRIT-COMPONENT-001"
            )

            for wo in affected_wos:
                if wo.priority != "CRITICAL":
                    await work_order_svc.reschedule_work_order(
                        wo.work_order_id,
                        new_start_date=datetime.now() + timedelta(days=7),
                        reason="Material shortage - expedited order in transit"
                    )

            assert expedited_shipment is not None

    @pytest.mark.asyncio
    async def test_blockchain_traceability_workflow(self):
        """Test full blockchain traceability workflow."""
        blockchain_svc = create_traceability_service()
        batch_svc = create_batch_record_service()
        logistics_svc = create_logistics_tracker()

        # Register product
        await blockchain_svc.register_product(
            "LEGO-TRACE-001",
            "LEGO Traceable Set",
            "LEGO Group",
            "5702016123456"
        )

        # Commission serial numbers
        serials = await blockchain_svc.commission_serial_numbers(
            "LEGO-TRACE-001",
            "BATCH-TRACE-2024-001",
            10
        )

        # Record manufacturing events
        await blockchain_svc.record_event(
            "COMMISSIONING",
            serials,
            {"name": "Factory Billund", "gln": "1234567890123"},
            "commissioning",
            "active"
        )

        # Create and complete batch
        await batch_svc.create_master_batch_record(
            "LEGO-TRACE-001", "Traceable Set", "1.0", 10, "sets",
            steps=[{"step_number": 1, "description": "Assembly"}],
            created_by="engineer"
        )
        batch = await batch_svc.initiate_batch(
            "LEGO-TRACE-001", "BATCH-TRACE-2024-001", 10, "production"
        )
        await batch_svc.complete_step(batch.batch_id, 1, "operator", "qa")
        await batch_svc.calculate_yield(batch.batch_id, 10, 0, 0)
        await batch_svc.release_batch(batch.batch_id, "RELEASE", "qa_manager")

        # Record packing event
        await blockchain_svc.record_event(
            "PACKING",
            serials,
            {"name": "Packing Station", "gln": "1234567890124"},
            "packing",
            "packed"
        )

        # Create shipment
        await logistics_svc.register_carrier("DHL", "DHL Express", "PARCEL")
        shipment = await logistics_svc.create_shipment(
            "SHIP-TRACE-001",
            "DHL",
            {"city": "Billund", "country": "Denmark"},
            {"city": "New York", "country": "USA"},
            "AIR",
            [{"sku": "LEGO-TRACE-001", "quantity": 10}]
        )

        # Record shipping event
        await blockchain_svc.record_event(
            "SHIPPING",
            serials,
            {"name": "Billund DC", "gln": "1234567890125"},
            "shipping",
            "in_transit",
            metadata={"tracking": shipment.shipment_id}
        )

        # Mine blocks to finalize
        await blockchain_svc.mine_block()

        # Verify chain and trace history
        is_valid = await blockchain_svc.verify_chain()
        history = await blockchain_svc.trace_product_history(serials[0])

        assert is_valid is True
        assert len(history) >= 3


class TestCloudEdgeManufacturing:
    """Integration tests for cloud-edge manufacturing scenarios."""

    @pytest.mark.asyncio
    async def test_edge_production_with_cloud_sync(self):
        """Test edge-based production with cloud synchronization."""
        sync_svc = create_cloud_edge_service()
        work_order_svc = create_work_order_service()
        oee_calc = create_oee_calculator()

        # Register edge nodes
        factory_edge = await sync_svc.register_edge_node(
            "EDGE-FACTORY-1",
            "Factory 1 Edge Gateway",
            "Billund Factory",
            ["inference", "data_collection", "local_control"]
        )

        # Create sync topics
        await sync_svc.create_topic(
            "production-events",
            "Production Events",
            "CRITICAL",
            "LAST_WRITE_WINS"
        )
        await sync_svc.create_topic(
            "quality-metrics",
            "Quality Metrics",
            "HIGH",
            "MERGE"
        )

        # Simulate local production at edge
        work_order = await work_order_svc.create_work_order(
            product_id="LEGO-EDGE-001",
            quantity=1000,
            priority="NORMAL",
            due_date=datetime.now() + timedelta(days=7)
        )

        # Edge publishes production data locally
        await sync_svc.publish_from_edge(
            "EDGE-FACTORY-1",
            "production-events",
            {
                "work_order": work_order.work_order_id,
                "event": "started",
                "timestamp": datetime.now().isoformat(),
                "quantity_planned": 1000
            }
        )

        # Record production metrics
        for i in range(5):  # 5 production cycles
            await sync_svc.publish_from_edge(
                "EDGE-FACTORY-1",
                "quality-metrics",
                {
                    "work_order": work_order.work_order_id,
                    "cycle": i + 1,
                    "good_parts": 190 + (i % 10),
                    "defective_parts": 10 - (i % 5),
                    "cycle_time": 60 + (i * 2)
                }
            )

        # Sync to cloud
        sync_result = await sync_svc.sync_edge_to_cloud("EDGE-FACTORY-1")

        assert sync_result["status"] == "success"
        assert sync_result["synced_count"] >= 6  # 1 start event + 5 quality events

        # Complete work order
        await sync_svc.publish_from_edge(
            "EDGE-FACTORY-1",
            "production-events",
            {
                "work_order": work_order.work_order_id,
                "event": "completed",
                "timestamp": datetime.now().isoformat(),
                "quantity_produced": 995,
                "quantity_good": 950
            }
        )

        # Final sync
        final_sync = await sync_svc.sync_edge_to_cloud("EDGE-FACTORY-1")
        assert final_sync["status"] == "success"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
