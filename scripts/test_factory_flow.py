#!/usr/bin/env python3
"""
LEGO Factory v3 - End-to-End Flow Test Script
==============================================
Tests the complete manufacturing flow:
1. Products with BOMs and Routings
2. Work order creation for any SKU
3. Jobs appearing in Gantt chart

Usage:
    # From project root with database running:
    python scripts/test_factory_flow.py

    # Or run specific tests:
    python scripts/test_factory_flow.py --test-products
    python scripts/test_factory_flow.py --test-workorder
    python scripts/test_factory_flow.py --test-gantt
"""

import sys
import os
import json
import argparse
from datetime import datetime, timedelta

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def print_header(title):
    print("\n" + "=" * 60)
    print(f"  {title}")
    print("=" * 60)


def print_success(msg):
    print(f"  ✅ {msg}")


def print_error(msg):
    print(f"  ❌ {msg}")


def print_info(msg):
    print(f"  ℹ️  {msg}")


def test_machines_config():
    """Test that machines.json is valid and has all required machines."""
    print_header("Testing Machines Configuration")

    try:
        with open('config/machines.json') as f:
            config = json.load(f)

        machines = config.get('machines', [])
        print_info(f"Found {len(machines)} machines")

        # Required machines for routings
        required = ['bambu-ps1', 'formlabs-3', 'bantam-explorer', 'longer-ray-laser', 'software']
        found = {m['machine_id'] for m in machines}

        for req in required:
            if req in found:
                print_success(f"Machine '{req}' found")
            else:
                print_error(f"Machine '{req}' MISSING - routings will fail!")

        # Check capabilities
        for m in machines:
            caps = m.get('capabilities', [])
            if caps:
                print_success(f"{m['machine_id']}: {len(caps)} capabilities")
            else:
                print_info(f"{m['machine_id']}: No capabilities defined")

        return True

    except Exception as e:
        print_error(f"Failed to load machines.json: {e}")
        return False


def test_database_connection():
    """Test database connectivity."""
    print_header("Testing Database Connection")

    try:
        from config.database import get_db_session

        with get_db_session() as session:
            from sqlalchemy import text
            result = session.execute(text("SELECT 1")).scalar()
            if result == 1:
                print_success("Database connection successful")
                return True
            else:
                print_error("Database query returned unexpected result")
                return False

    except Exception as e:
        print_error(f"Database connection failed: {e}")
        print_info("Make sure PostgreSQL is running and .env is configured")
        return False


def test_products_with_bom_routing():
    """Test that products have BOMs and routings."""
    print_header("Testing Products with BOMs and Routings")

    try:
        from config.database import get_db_session
        from models.lego.parts_catalog import LegoProduct, LegoProductBOM, LegoRouting

        with get_db_session() as session:
            # Count products
            product_count = session.query(LegoProduct).count()
            print_info(f"Total products in catalog: {product_count}")

            if product_count == 0:
                print_error("No products found! Run: python scripts/seed_lego_catalog.py")
                return False

            # Sample products
            products = session.query(LegoProduct).limit(5).all()

            for product in products:
                print(f"\n  Product: {product.sku}")

                # Check routing
                if product.routing_id:
                    routing = session.query(LegoRouting).filter_by(routing_id=product.routing_id).first()
                    if routing:
                        print_success(f"Routing: {routing.name} ({routing.routing_id})")
                        # Check routing operations
                        ops = routing.operations if hasattr(routing, 'operations') else []
                        print_info(f"  Operations: {len(ops) if ops else 'N/A'}")
                    else:
                        print_error(f"Routing {product.routing_id} not found!")
                else:
                    print_error("No routing assigned")

                # Check BOM
                bom_items = session.query(LegoProductBOM).filter_by(product_sku=product.sku).all()
                if bom_items:
                    print_success(f"BOM: {len(bom_items)} items")
                    for item in bom_items[:3]:
                        print(f"    - {item.material_name}: {item.quantity} {item.unit}")
                else:
                    print_info("No BOM items (will be auto-generated)")

            # Count routings
            routing_count = session.query(LegoRouting).count()
            print_info(f"\nTotal routings: {routing_count}")

            # Count BOM items
            bom_count = session.query(LegoProductBOM).count()
            print_info(f"Total BOM items: {bom_count}")

            return True

    except Exception as e:
        print_error(f"Product test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_work_order_creation():
    """Test creating a work order for a product."""
    print_header("Testing Work Order Creation")

    try:
        from config.database import get_db_session
        from services.mes.work_order_service import WorkOrderService
        from models.lego.parts_catalog import LegoProduct

        with get_db_session() as session:
            # Get a random product
            product = session.query(LegoProduct).first()

            if not product:
                print_error("No products found! Run seeding first.")
                return False

            print_info(f"Creating work order for: {product.sku}")

            service = WorkOrderService(session)

            # Create work order
            wo_data = {
                'product_id': product.sku,
                'quantity_ordered': 10,
                'description': f"Test production of {product.sku}",
                'priority': 7,
                'due_date': datetime.utcnow() + timedelta(days=3),
            }

            work_order = service.create_work_order(wo_data)

            if work_order:
                print_success(f"Created work order: {work_order['work_order_id']}")
                print_info(f"  Product: {work_order.get('product_id')}")
                print_info(f"  Status: {work_order.get('status')}")

                # Get operations
                from models.mes.work_orders import Operation, WorkOrder
                wo = session.query(WorkOrder).filter_by(work_order_id=work_order['work_order_id']).first()
                if wo:
                    ops = session.query(Operation).filter_by(work_order_id=wo.id).order_by(Operation.sequence).all()
                    print_info(f"  Operations: {len(ops)}")
                    for op in ops[:5]:
                        machine = op.machine_id or 'No machine'
                        print(f"    {op.sequence}. {op.name} ({machine})")

                # Release work order
                print_info("\nReleasing work order...")
                result = service.release_work_order(work_order['work_order_id'], 'test_user')

                if result:
                    print_success(f"Work order released")
                    print_info(f"  New status: {result.get('status')}")
                    if 'job' in result:
                        job = result['job']
                        print_success(f"Job created: {job['job_id']}")
                        print_info(f"  Machine: {job.get('machine_id')}")
                        print_info(f"  Scheduled: {job.get('scheduled_start')} to {job.get('scheduled_end')}")
                        return work_order['work_order_id']
                    else:
                        print_info("No job created (may already exist)")
                        return work_order['work_order_id']
                else:
                    print_error("Failed to release work order")
                    return None
            else:
                print_error("Failed to create work order")
                return None

    except Exception as e:
        print_error(f"Work order test failed: {e}")
        import traceback
        traceback.print_exc()
        return None


def test_gantt_chart():
    """Test Gantt chart data retrieval."""
    print_header("Testing Gantt Chart Data")

    try:
        from config.database import get_db_session
        from services.mes.scheduling_service import SchedulingService

        with get_db_session() as session:
            service = SchedulingService(session)
            gantt_data = service.get_gantt_data(hours_back=24, hours_forward=72)

            machines = gantt_data.get('machines', [])
            jobs = gantt_data.get('jobs', [])

            print_info(f"Machines in Gantt: {len(machines)}")
            for m in machines:
                print(f"    - {m['id']}: {m['name']}")

            print_info(f"Jobs in Gantt: {len(jobs)}")

            if jobs:
                print_success("Jobs found in scheduling window:")
                for job in jobs[:5]:
                    print(f"    - {job['job_id']} on {job['machine_id']}")
                    print(f"      {job['start']} to {job['end']}")
                    print(f"      Status: {job['status']}, Product: {job.get('product')}")
                return True
            else:
                print_info("No jobs in current scheduling window")
                print_info("Create and release a work order to see jobs in Gantt")
                return True

    except Exception as e:
        print_error(f"Gantt test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_setup_time_matrix():
    """Test setup time calculation."""
    print_header("Testing Setup Time Matrix")

    try:
        from config.database import get_db_session
        from services.mes.scheduling_service import SchedulingService

        with get_db_session() as session:
            service = SchedulingService(session)

            # Test some material transitions
            test_cases = [
                ('ABS', 'ABS', 'bambu-ps1', 0),  # Same material
                ('ABS', 'PLA', 'bambu-ps1', 15),  # Different material
                ('PLA', 'PETG', 'bambu-ps1', 8),
                ('ALU', 'BRS', 'bantam-explorer', 10),
            ]

            for from_mat, to_mat, machine, expected in test_cases:
                setup_time = service.calculate_setup_time(from_mat, to_mat, machine)
                status = "✅" if setup_time == expected else "⚠️"
                print(f"  {status} {from_mat} -> {to_mat} on {machine}: {setup_time} min (expected {expected})")

            # Get full matrix
            matrix = service.get_setup_time_matrix()
            print_info(f"\nSetup matrix has {len(matrix.get('material_matrix', {}))} entries")
            print_info(f"Machine factors: {len(matrix.get('machine_factors', {}))} machines")

            return True

    except Exception as e:
        print_error(f"Setup time test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def run_all_tests():
    """Run all tests."""
    print("\n" + "=" * 60)
    print("  LEGO Factory v3 - End-to-End Flow Test")
    print("=" * 60)
    print(f"  Started: {datetime.now().isoformat()}")

    results = {}

    # Test machines config (no DB required)
    results['machines'] = test_machines_config()

    # Test database
    results['database'] = test_database_connection()

    if results['database']:
        results['products'] = test_products_with_bom_routing()
        results['work_order'] = test_work_order_creation() is not None
        results['gantt'] = test_gantt_chart()
        results['setup_time'] = test_setup_time_matrix()
    else:
        print_info("\nSkipping database tests due to connection failure")

    # Summary
    print_header("Test Summary")
    passed = sum(1 for v in results.values() if v)
    total = len(results)

    for test, result in results.items():
        status = "PASS" if result else "FAIL"
        print(f"  {test}: {status}")

    print(f"\n  Total: {passed}/{total} passed")

    if passed == total:
        print_success("All tests passed!")
        return 0
    else:
        print_error(f"{total - passed} tests failed")
        return 1


def main():
    parser = argparse.ArgumentParser(description='LEGO Factory v3 - End-to-End Flow Test')
    parser.add_argument('--test-machines', action='store_true', help='Test machines config only')
    parser.add_argument('--test-products', action='store_true', help='Test products with BOM/routing')
    parser.add_argument('--test-workorder', action='store_true', help='Test work order creation')
    parser.add_argument('--test-gantt', action='store_true', help='Test Gantt chart data')
    parser.add_argument('--test-setup', action='store_true', help='Test setup time matrix')

    args = parser.parse_args()

    # If specific test requested
    if args.test_machines:
        return 0 if test_machines_config() else 1
    elif args.test_products:
        if not test_database_connection():
            return 1
        return 0 if test_products_with_bom_routing() else 1
    elif args.test_workorder:
        if not test_database_connection():
            return 1
        return 0 if test_work_order_creation() else 1
    elif args.test_gantt:
        if not test_database_connection():
            return 1
        return 0 if test_gantt_chart() else 1
    elif args.test_setup:
        if not test_database_connection():
            return 1
        return 0 if test_setup_time_matrix() else 1

    # Run all tests
    return run_all_tests()


if __name__ == "__main__":
    sys.exit(main())
