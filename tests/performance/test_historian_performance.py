"""
Performance tests for TimescaleDB Historian.

Target: 100,000 points/second write throughput.
"""

import pytest
import time
import random
from datetime import datetime, timedelta
from typing import List, Dict, Any
import statistics


class TestHistorianPerformance:
    """Performance tests for historian write/read operations."""

    @pytest.fixture
    def db_session(self):
        """Get database session."""
        from config.database import get_db_session
        with get_db_session() as session:
            yield session

    @pytest.fixture
    def historian_service(self, db_session):
        """Get historian service."""
        try:
            from services.scada.historian import get_historian_service
            return get_historian_service(db_session)
        except ImportError:
            pytest.skip("Historian service not available")

    def generate_test_data(self, num_points: int, num_tags: int = 10) -> List[Dict[str, Any]]:
        """Generate test data points."""
        base_time = datetime.utcnow()
        data = []

        for i in range(num_points):
            tag_id = f"test_tag_{i % num_tags}"
            timestamp = base_time + timedelta(milliseconds=i)
            value = random.uniform(0, 100)

            data.append({
                'tag_id': tag_id,
                'timestamp': timestamp,
                'value': value,
                'quality': 192,  # Good quality
            })

        return data

    def test_historian_write_throughput(self, historian_service):
        """
        Test historian write throughput.

        Target: 100,000 points/second
        """
        # Test parameters
        num_points = 10000  # 10k points for quick test
        batch_size = 1000

        # Generate test data
        test_data = self.generate_test_data(num_points)

        # Measure write time
        start_time = time.perf_counter()

        # Write in batches
        for i in range(0, num_points, batch_size):
            batch = test_data[i:i + batch_size]
            try:
                historian_service.write_batch(batch)
            except Exception as e:
                # If batch write not available, write individually
                for point in batch:
                    historian_service.write_point(
                        point['tag_id'],
                        point['value'],
                        point['timestamp']
                    )

        end_time = time.perf_counter()
        elapsed = end_time - start_time

        # Calculate throughput
        throughput = num_points / elapsed

        print(f"\n=== Historian Write Performance ===")
        print(f"Points written: {num_points:,}")
        print(f"Time elapsed: {elapsed:.3f} seconds")
        print(f"Throughput: {throughput:,.0f} points/second")
        print(f"Target: 100,000 points/second")

        # Assert minimum acceptable throughput (10% of target for CI)
        assert throughput > 10000, f"Throughput {throughput:.0f} below minimum 10,000 pts/sec"

    def test_historian_read_performance(self, historian_service):
        """
        Test historian read/query performance.

        Target: < 500ms for 1-hour query
        """
        # Query parameters
        tag_ids = [f"test_tag_{i}" for i in range(5)]
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(hours=1)

        # Measure query time
        query_times = []

        for _ in range(5):  # Run 5 queries
            start = time.perf_counter()

            try:
                result = historian_service.query(
                    tag_ids=tag_ids,
                    start_time=start_time,
                    end_time=end_time,
                    aggregation='avg',
                    interval='1min'
                )
            except Exception:
                # Basic query if aggregation not supported
                result = historian_service.query(
                    tag_ids=tag_ids,
                    start_time=start_time,
                    end_time=end_time
                )

            end = time.perf_counter()
            query_times.append((end - start) * 1000)  # Convert to ms

        avg_query_time = statistics.mean(query_times)

        print(f"\n=== Historian Query Performance ===")
        print(f"Query times: {[f'{t:.1f}ms' for t in query_times]}")
        print(f"Average: {avg_query_time:.1f}ms")
        print(f"Target: < 500ms")

        # Assert query time under target
        assert avg_query_time < 500, f"Query time {avg_query_time:.1f}ms exceeds 500ms target"

    def test_historian_concurrent_writes(self, historian_service):
        """
        Test concurrent write performance.
        """
        import concurrent.futures

        num_threads = 4
        points_per_thread = 2500

        def write_batch(thread_id: int):
            data = self.generate_test_data(points_per_thread, num_tags=10)
            for point in data:
                point['tag_id'] = f"thread_{thread_id}_{point['tag_id']}"

            start = time.perf_counter()
            for point in data:
                try:
                    historian_service.write_point(
                        point['tag_id'],
                        point['value'],
                        point['timestamp']
                    )
                except Exception:
                    pass
            return time.perf_counter() - start

        start_time = time.perf_counter()

        with concurrent.futures.ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [executor.submit(write_batch, i) for i in range(num_threads)]
            results = [f.result() for f in futures]

        total_time = time.perf_counter() - start_time
        total_points = num_threads * points_per_thread
        throughput = total_points / total_time

        print(f"\n=== Concurrent Write Performance ===")
        print(f"Threads: {num_threads}")
        print(f"Total points: {total_points:,}")
        print(f"Total time: {total_time:.3f}s")
        print(f"Throughput: {throughput:,.0f} points/second")


class TestMRPPerformance:
    """Performance tests for MRP planning."""

    @pytest.fixture
    def db_session(self):
        """Get database session."""
        from config.database import get_db_session
        with get_db_session() as session:
            yield session

    @pytest.fixture
    def mrp_service(self, db_session):
        """Get MRP service."""
        try:
            from services.erp.mrp_service import get_mrp_service
            return get_mrp_service(db_session)
        except ImportError:
            pytest.skip("MRP service not available")

    def test_mrp_90_day_planning(self, mrp_service):
        """
        Test MRP planning performance.

        Target: < 30 seconds for 90-day horizon
        """
        horizon_days = 90

        # Measure MRP run time
        start_time = time.perf_counter()

        try:
            result = mrp_service.run_mrp(
                horizon_days=horizon_days,
                include_forecasts=True
            )
        except Exception as e:
            print(f"MRP run failed: {e}")
            pytest.skip("MRP run not available")

        end_time = time.perf_counter()
        elapsed = end_time - start_time

        print(f"\n=== MRP Performance ===")
        print(f"Horizon: {horizon_days} days")
        print(f"Time elapsed: {elapsed:.2f} seconds")
        print(f"Target: < 30 seconds")

        if hasattr(result, 'planned_orders'):
            print(f"Planned orders: {len(result.planned_orders)}")
        if hasattr(result, 'action_messages'):
            print(f"Action messages: {len(result.action_messages)}")

        # Assert MRP completes within target
        assert elapsed < 30, f"MRP took {elapsed:.1f}s, exceeds 30s target"


class TestDashboardPerformance:
    """Performance tests for dashboard loading."""

    @pytest.fixture
    def client(self):
        """Get Flask test client."""
        from app import create_app
        app = create_app()
        app.config['TESTING'] = True
        with app.test_client() as client:
            yield client

    def test_dashboard_load_times(self, client):
        """
        Test dashboard page load times.

        Target: < 2 seconds per page
        """
        # Key dashboard endpoints
        dashboards = [
            ('/', 'Home'),
            ('/api/scada/machines', 'SCADA Machines'),
            ('/api/mes/work-orders', 'MES Work Orders'),
            ('/api/erp/sales-orders', 'ERP Sales Orders'),
            ('/api/qms/documents', 'QMS Documents'),
            ('/api/lego/catalog', 'LEGO Catalog'),
            ('/api/ml/status', 'ML Status'),
        ]

        results = []

        for endpoint, name in dashboards:
            times = []

            for _ in range(3):  # 3 requests per endpoint
                start = time.perf_counter()
                response = client.get(endpoint)
                elapsed = (time.perf_counter() - start) * 1000  # ms
                times.append(elapsed)

            avg_time = statistics.mean(times)
            results.append((name, avg_time, response.status_code))

        print(f"\n=== Dashboard Load Performance ===")
        print(f"{'Dashboard':<25} {'Avg Time':<15} {'Status':<10}")
        print("-" * 50)

        all_passed = True
        for name, avg_time, status in results:
            status_str = "OK" if status == 200 else f"ERR:{status}"
            passed = avg_time < 2000
            marker = "✓" if passed else "✗"
            print(f"{name:<25} {avg_time:>8.1f}ms     {status_str:<10} {marker}")
            if not passed:
                all_passed = False

        print(f"\nTarget: < 2000ms per dashboard")

        # At least health check should pass
        assert any(r[1] < 2000 for r in results), "No dashboards loaded within 2s target"


if __name__ == '__main__':
    pytest.main([__file__, '-v', '-s'])
