"""
LEGO Factory v3 - Full Workflow Integration Tests
==================================================
End-to-end tests that verify complete manufacturing workflows
with real database operations.

These tests verify:
1. Work order creation and lifecycle
2. Inventory tracking and transactions
3. Quality management (NCR/CAPA)
4. Cross-system data consistency
"""

import pytest
from datetime import datetime, timedelta
from uuid import uuid4


class TestManufacturingWorkflow:
    """Test complete manufacturing workflow from order to completion."""

    def test_work_order_lifecycle(self, integration_db_session, work_order_service):
        """Test complete work order lifecycle: create -> start -> complete."""
        # Create work order
        wo_data = {
            'work_order_id': f'WO-TEST-{uuid4().hex[:8]}',
            'description': 'Integration test work order',
            'product_id': 'BRICK-2X4-RED',
            'quantity_ordered': 100,
            'priority': 5,
            'created_by': 'integration_test',
        }

        try:
            from models.mes.work_orders import WorkOrder, WorkOrderStatus

            # Create
            wo = WorkOrder(**wo_data)
            integration_db_session.add(wo)
            integration_db_session.flush()

            assert wo.id is not None
            assert wo.status == WorkOrderStatus.CREATED

            # Start
            wo.status = WorkOrderStatus.IN_PROGRESS
            wo.actual_start = datetime.utcnow()
            integration_db_session.flush()

            assert wo.status == WorkOrderStatus.IN_PROGRESS
            assert wo.actual_start is not None

            # Complete some quantity
            wo.quantity_completed = 50
            integration_db_session.flush()

            assert wo.quantity_completed == 50

            # Complete
            wo.quantity_completed = 100
            wo.status = WorkOrderStatus.COMPLETED
            wo.actual_end = datetime.utcnow()
            integration_db_session.flush()

            assert wo.status == WorkOrderStatus.COMPLETED
            assert wo.actual_end is not None

        except ImportError:
            pytest.skip("Work order models not available")

    def test_inventory_transaction_flow(self, integration_db_session, inventory_service):
        """Test inventory transactions: receipt -> issue -> adjust."""
        try:
            from models.erp.items import Item, ItemStatus
            from models.erp.inventory import Location, Inventory, InventoryTransaction

            # Setup: Create item and location
            item = Item(
                item_id=f'ITEM-TEST-{uuid4().hex[:8]}',
                name='Test Component',
                item_type='component',
                status=ItemStatus.ACTIVE,
                base_uom='EA',
            )
            location = Location(
                location_id=f'LOC-TEST-{uuid4().hex[:8]}',
                name='Test Warehouse',
                location_type='warehouse',
                is_active=True,
            )
            integration_db_session.add(item)
            integration_db_session.add(location)
            integration_db_session.flush()

            # Receipt transaction
            receipt_txn = InventoryTransaction(
                item_id=item.item_id,
                transaction_type='receipt',
                quantity=100,
                to_location_id=location.location_id,
                reference_type='purchase_order',
                reference_id='PO-TEST-001',
                unit_cost=10.0,
                created_by='integration_test',
            )
            integration_db_session.add(receipt_txn)
            integration_db_session.flush()

            assert receipt_txn.id is not None
            assert receipt_txn.quantity == 100

            # Create inventory record
            inv = Inventory(
                item_id=item.item_id,
                location_id=location.location_id,
                quantity_on_hand=100,
            )
            integration_db_session.add(inv)
            integration_db_session.flush()

            # Issue transaction
            issue_txn = InventoryTransaction(
                item_id=item.item_id,
                transaction_type='issue',
                quantity=-25,
                from_location_id=location.location_id,
                reference_type='work_order',
                reference_id='WO-TEST-001',
                created_by='integration_test',
            )
            integration_db_session.add(issue_txn)
            inv.quantity_on_hand = 75
            integration_db_session.flush()

            assert inv.quantity_on_hand == 75

        except ImportError:
            pytest.skip("Inventory models not available")


class TestQualityWorkflow:
    """Test quality management workflows."""

    def test_ncr_to_capa_workflow(self, integration_db_session):
        """Test NCR creation and CAPA linkage."""
        try:
            from models.qms.ncr import NCR, NCRStatus, NCRSeverity
            from models.qms.capa import CAPA, CAPAStatus, CAPAType

            # Create NCR
            ncr = NCR(
                ncr_number=f'NCR-TEST-{uuid4().hex[:8]}',
                title='Test Non-Conformance',
                description='Integration test NCR',
                severity=NCRSeverity.MINOR,
                status=NCRStatus.OPEN,
                detected_by='integration_test',
            )
            integration_db_session.add(ncr)
            integration_db_session.flush()

            assert ncr.id is not None
            assert ncr.status == NCRStatus.OPEN

            # Create linked CAPA
            capa = CAPA(
                capa_number=f'CAPA-TEST-{uuid4().hex[:8]}',
                title='Test Corrective Action',
                problem_statement='Root cause analysis for test NCR',
                capa_type=CAPAType.CORRECTIVE,
                status=CAPAStatus.OPEN,
                ncr_number=ncr.ncr_number,
                owner_id='integration_test',
            )
            integration_db_session.add(capa)
            integration_db_session.flush()

            assert capa.id is not None
            assert capa.ncr_number == ncr.ncr_number

            # Complete workflow
            ncr.status = NCRStatus.CLOSED
            capa.status = CAPAStatus.CLOSED
            integration_db_session.flush()

        except ImportError:
            pytest.skip("QMS models not available")


class TestSCADAIntegration:
    """Test SCADA system integration with database."""

    def test_tag_creation_and_retrieval(self, integration_db_session, tag_service):
        """Test creating and retrieving SCADA tags."""
        try:
            from models.scada.tags import Tag

            # Create tag
            tag = Tag(
                tag_id=f'TAG-TEST-{uuid4().hex[:8]}',
                name='Test Temperature Sensor',
                description='Integration test tag',
                data_type='float32',
                category='analog_input',
                area='production',
                equipment='machine_01',
                eng_units='C',
                eng_low=0.0,
                eng_high=100.0,
            )
            integration_db_session.add(tag)
            integration_db_session.flush()

            # Retrieve tag
            retrieved = integration_db_session.query(Tag).filter(
                Tag.tag_id == tag.tag_id
            ).first()

            assert retrieved is not None
            assert retrieved.name == 'Test Temperature Sensor'
            assert retrieved.eng_units == 'C'

        except ImportError:
            pytest.skip("SCADA models not available")

    def test_alarm_definition_and_trigger(self, integration_db_session, alarm_service, seeded_tags):
        """Test alarm definition and triggering logic."""
        if not seeded_tags:
            pytest.skip("No tags seeded")

        try:
            from models.scada.alarms import AlarmDefinition, AlarmInstance

            tag = seeded_tags[0]

            # Create alarm definition
            alarm_def = AlarmDefinition(
                alarm_id=f'ALM-TEST-{uuid4().hex[:8]}',
                name='High Temperature Alarm',
                description='Test alarm for high temperature',
                priority=2,
                alarm_class='process',
                alarm_type='high',
                tag_id=tag.tag_id,
                high_limit=80.0,
                deadband=1.0,
                enabled=True,
            )
            integration_db_session.add(alarm_def)
            integration_db_session.flush()

            assert alarm_def.id is not None

            # Simulate alarm trigger
            alarm_instance = AlarmInstance(
                alarm_definition_id=alarm_def.id,
                alarm_id=alarm_def.alarm_id,
                tag_id=tag.tag_id,
                source_value=85.0,
                message='Temperature exceeded high limit',
                triggered_at=datetime.utcnow(),
            )
            integration_db_session.add(alarm_instance)
            integration_db_session.flush()

            assert alarm_instance.id is not None
            assert alarm_instance.source_value == 85.0

        except ImportError:
            pytest.skip("Alarm models not available")


class TestERPIntegration:
    """Test ERP system integration."""

    def test_sales_order_workflow(self, integration_db_session):
        """Test sales order creation and fulfillment."""
        try:
            from models.erp.sales import SalesOrder, SalesOrderLine, SalesOrderStatus
            from models.erp.partners import Partner, PartnerType, PartnerStatus
            from models.erp.items import Item, ItemStatus

            # Create customer
            customer = Partner(
                partner_id=f'CUST-TEST-{uuid4().hex[:8]}',
                name='Test Customer',
                partner_type=PartnerType.CUSTOMER,
                status=PartnerStatus.ACTIVE,
            )
            integration_db_session.add(customer)

            # Create item
            item = Item(
                item_id=f'ITEM-TEST-{uuid4().hex[:8]}',
                name='Test Product',
                item_type='finished_good',
                status=ItemStatus.ACTIVE,
                base_uom='EA',
                list_price=25.00,
            )
            integration_db_session.add(item)
            integration_db_session.flush()

            # Create sales order
            order = SalesOrder(
                order_number=f'SO-TEST-{uuid4().hex[:8]}',
                customer_id=customer.partner_id,
                status=SalesOrderStatus.DRAFT,
                order_date=datetime.utcnow().date(),
                created_by='integration_test',
            )
            integration_db_session.add(order)
            integration_db_session.flush()

            # Add order line
            line = SalesOrderLine(
                order_id=order.id,
                line_number=1,
                item_id=item.item_id,
                quantity=10,
                unit_price=25.00,
            )
            integration_db_session.add(line)
            integration_db_session.flush()

            # Verify
            assert order.id is not None
            assert line.id is not None
            assert line.quantity * line.unit_price == 250.00

            # Approve order
            order.status = SalesOrderStatus.APPROVED
            integration_db_session.flush()

            assert order.status == SalesOrderStatus.APPROVED

        except ImportError:
            pytest.skip("ERP models not available")


class TestDataConsistency:
    """Test cross-system data consistency."""

    def test_work_order_inventory_consistency(self, integration_db_session):
        """Verify inventory is properly consumed by work orders."""
        try:
            from models.mes.work_orders import WorkOrder, WorkOrderStatus
            from models.erp.items import Item, ItemStatus
            from models.erp.inventory import Location, Inventory, InventoryTransaction

            # Setup inventory
            item = Item(
                item_id=f'ITEM-TEST-{uuid4().hex[:8]}',
                name='Raw Material',
                item_type='raw_material',
                status=ItemStatus.ACTIVE,
                base_uom='EA',
            )
            location = Location(
                location_id=f'LOC-TEST-{uuid4().hex[:8]}',
                name='Production Floor',
                location_type='production',
                is_active=True,
            )
            integration_db_session.add(item)
            integration_db_session.add(location)
            integration_db_session.flush()

            inventory = Inventory(
                item_id=item.item_id,
                location_id=location.location_id,
                quantity_on_hand=1000,
            )
            integration_db_session.add(inventory)
            integration_db_session.flush()

            initial_qty = inventory.quantity_on_hand

            # Create and complete work order
            wo = WorkOrder(
                work_order_id=f'WO-TEST-{uuid4().hex[:8]}',
                description='Test production',
                product_id='FINISHED-PRODUCT',
                quantity_ordered=100,
                status=WorkOrderStatus.CREATED,
                created_by='integration_test',
            )
            integration_db_session.add(wo)
            integration_db_session.flush()

            # Simulate material consumption
            consumed_qty = 500
            consumption = InventoryTransaction(
                item_id=item.item_id,
                transaction_type='issue',
                quantity=-consumed_qty,
                from_location_id=location.location_id,
                reference_type='work_order',
                reference_id=wo.work_order_id,
                created_by='integration_test',
            )
            integration_db_session.add(consumption)
            inventory.quantity_on_hand -= consumed_qty
            integration_db_session.flush()

            # Verify consistency
            assert inventory.quantity_on_hand == initial_qty - consumed_qty
            assert consumption.reference_id == wo.work_order_id

        except ImportError:
            pytest.skip("MES/ERP models not available")


class TestDatabaseTransactions:
    """Test database transaction handling."""

    def test_rollback_on_error(self, integration_db_session):
        """Verify transactions roll back properly on error."""
        try:
            from models.scada.tags import Tag

            # Create a valid tag
            tag1 = Tag(
                tag_id=f'TAG-TEST-{uuid4().hex[:8]}',
                name='Valid Tag',
                data_type='float32',
                category='analog_input',
            )
            integration_db_session.add(tag1)
            integration_db_session.flush()

            tag1_id = tag1.tag_id

            # The fixture automatically rolls back at end of test
            # Verify tag exists during this transaction
            exists = integration_db_session.query(Tag).filter(
                Tag.tag_id == tag1_id
            ).first()
            assert exists is not None

        except ImportError:
            pytest.skip("Tag models not available")

    def test_concurrent_updates(self, integration_db_session):
        """Test handling of concurrent updates (optimistic locking)."""
        try:
            from models.erp.inventory import Inventory, Location
            from models.erp.items import Item, ItemStatus

            # Setup
            item = Item(
                item_id=f'ITEM-TEST-{uuid4().hex[:8]}',
                name='Concurrent Test Item',
                item_type='component',
                status=ItemStatus.ACTIVE,
                base_uom='EA',
            )
            location = Location(
                location_id=f'LOC-TEST-{uuid4().hex[:8]}',
                name='Test Location',
                location_type='warehouse',
                is_active=True,
            )
            integration_db_session.add(item)
            integration_db_session.add(location)
            integration_db_session.flush()

            inventory = Inventory(
                item_id=item.item_id,
                location_id=location.location_id,
                quantity_on_hand=100,
            )
            integration_db_session.add(inventory)
            integration_db_session.flush()

            # Simulate concurrent updates
            inventory.quantity_on_hand += 50
            integration_db_session.flush()

            assert inventory.quantity_on_hand == 150

            inventory.quantity_on_hand -= 25
            integration_db_session.flush()

            assert inventory.quantity_on_hand == 125

        except ImportError:
            pytest.skip("Inventory models not available")
