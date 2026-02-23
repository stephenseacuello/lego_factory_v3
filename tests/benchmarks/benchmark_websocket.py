"""
WebSocket Performance Benchmarks

LegoMCP v6.0 - World-Class Manufacturing Research Platform
Performance testing for WebSocket events throughput and latency.
"""

import time
import threading
import statistics
from concurrent.futures import ThreadPoolExecutor, as_completed
from unittest.mock import Mock, MagicMock


class WebSocketBenchmark:
    """Benchmark WebSocket event throughput and latency."""

    def __init__(self):
        self.results = []
        self.errors = []

    def benchmark_event_emission_throughput(self, num_events=1000):
        """Benchmark raw event emission throughput."""
        from dashboard.websocket import (
            emit_unity_equipment_state,
            emit_robot_status,
            emit_supply_chain_flow_update,
            emit_vr_step_progress,
        )

        # Mock socketio to measure pure emission speed
        mock_socketio = MagicMock()

        with MagicMock() as mock_app:
            mock_app.socketio = mock_socketio

            start_time = time.perf_counter()

            for i in range(num_events):
                # Cycle through different event types
                event_type = i % 4

                if event_type == 0:
                    emit_unity_equipment_state(
                        f"EQ-{i:04d}",
                        "printing",
                        position={"x": i, "y": 0, "z": 0}
                    )
                elif event_type == 1:
                    emit_robot_status(
                        f"ARM-{i:04d}",
                        "active",
                        position={"x": i, "y": 0, "z": 0}
                    )
                elif event_type == 2:
                    emit_supply_chain_flow_update(
                        f"E-{i:04d}",
                        "SUP-001",
                        "WH-001",
                        "ABS_RED",
                        5000 + i
                    )
                else:
                    emit_vr_step_progress(
                        f"VRS-{i:04d}",
                        step_number=i % 10,
                        total_steps=10,
                        step_name=f"Step {i % 10}",
                        status="completed"
                    )

            end_time = time.perf_counter()

        elapsed = end_time - start_time
        events_per_second = num_events / elapsed

        return {
            "num_events": num_events,
            "elapsed_seconds": round(elapsed, 4),
            "events_per_second": round(events_per_second, 2),
            "avg_latency_ms": round((elapsed / num_events) * 1000, 4)
        }

    def benchmark_concurrent_emissions(self, num_threads=10, events_per_thread=100):
        """Benchmark concurrent event emission from multiple threads."""
        from dashboard.websocket import emit_unity_scene_update

        mock_socketio = MagicMock()
        results = []
        errors = []

        def emit_events(thread_id):
            thread_results = []
            for i in range(events_per_thread):
                start = time.perf_counter()
                try:
                    emit_unity_scene_update(
                        scene_name="FactoryFloor",
                        equipment_updates=[
                            {"equipment_id": f"EQ-{thread_id}-{i}", "state": "active"}
                        ]
                    )
                    latency = (time.perf_counter() - start) * 1000
                    thread_results.append(latency)
                except Exception as e:
                    errors.append(str(e))
            return thread_results

        start_time = time.perf_counter()

        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [executor.submit(emit_events, t) for t in range(num_threads)]

            for future in as_completed(futures):
                results.extend(future.result())

        end_time = time.perf_counter()

        total_events = num_threads * events_per_thread
        elapsed = end_time - start_time

        return {
            "num_threads": num_threads,
            "events_per_thread": events_per_thread,
            "total_events": total_events,
            "elapsed_seconds": round(elapsed, 4),
            "events_per_second": round(total_events / elapsed, 2),
            "avg_latency_ms": round(statistics.mean(results), 4) if results else 0,
            "p95_latency_ms": round(sorted(results)[int(len(results) * 0.95)], 4) if results else 0,
            "p99_latency_ms": round(sorted(results)[int(len(results) * 0.99)], 4) if results else 0,
            "errors": len(errors)
        }

    def benchmark_scene_data_preparation(self, num_equipment=100):
        """Benchmark Unity scene data preparation."""
        from dashboard.services.unity.scene_data import SceneDataService

        service = SceneDataService()

        # Measure full scene generation
        start_time = time.perf_counter()

        for _ in range(10):
            scene = service.get_full_scene("FactoryFloor")

        elapsed = time.perf_counter() - start_time
        avg_time = elapsed / 10

        return {
            "iterations": 10,
            "avg_generation_ms": round(avg_time * 1000, 4),
            "scenes_per_second": round(1 / avg_time, 2)
        }

    def benchmark_delta_update_generation(self, num_updates=1000):
        """Benchmark incremental scene update generation."""
        from dashboard.services.unity.scene_data import SceneDataService

        service = SceneDataService()

        latencies = []

        for i in range(num_updates):
            # Update equipment state
            service.update_equipment_state(f"EQ-{i % 10:03d}", {
                "state": "printing" if i % 2 == 0 else "idle",
                "progress": (i % 100)
            })

            # Measure delta generation
            start = time.perf_counter()
            delta = service.get_scene_delta(time.time() - 1)
            latency = (time.perf_counter() - start) * 1000
            latencies.append(latency)

        return {
            "num_updates": num_updates,
            "avg_delta_ms": round(statistics.mean(latencies), 4),
            "p95_delta_ms": round(sorted(latencies)[int(len(latencies) * 0.95)], 4),
            "max_delta_ms": round(max(latencies), 4)
        }


class OMERegistryBenchmark:
    """Benchmark OME Registry operations."""

    def benchmark_ome_registration(self, num_omes=1000):
        """Benchmark OME registration throughput."""
        from dashboard.services.digital_twin.ome_registry import OMERegistry

        registry = OMERegistry()

        start_time = time.perf_counter()

        for i in range(num_omes):
            registry.register_ome({
                "ome_type": "equipment",
                "name": f"Equipment {i}",
                "static_attributes": {
                    "model": f"Model-{i % 10}",
                    "serial": f"SN-{i:06d}"
                }
            })

        elapsed = time.perf_counter() - start_time

        return {
            "num_omes": num_omes,
            "elapsed_seconds": round(elapsed, 4),
            "registrations_per_second": round(num_omes / elapsed, 2),
            "avg_registration_ms": round((elapsed / num_omes) * 1000, 4)
        }

    def benchmark_ome_hierarchy_query(self, depth=4, children_per_node=5):
        """Benchmark hierarchical OME queries."""
        from dashboard.services.digital_twin.ome_registry import OMERegistry

        registry = OMERegistry()

        # Build hierarchy
        def create_hierarchy(parent_id, current_depth):
            if current_depth >= depth:
                return

            for i in range(children_per_node):
                child_id = registry.register_ome({
                    "ome_type": "equipment" if current_depth == depth - 1 else "cell",
                    "name": f"Node-D{current_depth}-{i}",
                    "parent_id": parent_id
                })
                create_hierarchy(child_id, current_depth + 1)

        root_id = registry.register_ome({
            "ome_type": "facility",
            "name": "Root Facility"
        })
        create_hierarchy(root_id, 0)

        # Benchmark hierarchy query
        latencies = []
        for _ in range(100):
            start = time.perf_counter()
            hierarchy = registry.get_hierarchy(root_id)
            latency = (time.perf_counter() - start) * 1000
            latencies.append(latency)

        total_nodes = sum(children_per_node ** d for d in range(depth + 1))

        return {
            "depth": depth,
            "children_per_node": children_per_node,
            "total_nodes": total_nodes,
            "avg_query_ms": round(statistics.mean(latencies), 4),
            "p95_query_ms": round(sorted(latencies)[int(len(latencies) * 0.95)], 4)
        }


class SupplyChainBenchmark:
    """Benchmark Supply Chain Twin operations."""

    def benchmark_disruption_simulation(self, network_size=50):
        """Benchmark disruption simulation performance."""
        from dashboard.services.digital_twin.supply_chain_twin import SupplyChainTwin

        twin = SupplyChainTwin()

        # Build network
        for i in range(network_size):
            twin.add_node({
                "node_id": f"NODE-{i:03d}",
                "type": ["supplier", "warehouse", "factory", "distribution"][i % 4],
                "name": f"Node {i}"
            })

        # Add edges (linear chain with some branches)
        for i in range(1, network_size):
            twin.add_edge({
                "source": f"NODE-{(i-1):03d}",
                "target": f"NODE-{i:03d}"
            })
            # Add some branching
            if i > 2 and i % 5 == 0:
                twin.add_edge({
                    "source": f"NODE-{(i-3):03d}",
                    "target": f"NODE-{i:03d}"
                })

        # Benchmark disruption simulation
        latencies = []
        for i in range(20):
            node_id = f"NODE-{(i * 2) % network_size:03d}"

            start = time.perf_counter()
            result = twin.simulate_disruption({
                "node_id": node_id,
                "disruption_type": "shutdown",
                "duration_days": 7
            })
            latency = (time.perf_counter() - start) * 1000
            latencies.append(latency)

        return {
            "network_size": network_size,
            "simulations": 20,
            "avg_simulation_ms": round(statistics.mean(latencies), 4),
            "p95_simulation_ms": round(sorted(latencies)[int(len(latencies) * 0.95)], 4),
            "max_simulation_ms": round(max(latencies), 4)
        }


def run_all_benchmarks():
    """Run all benchmarks and print results."""
    print("=" * 60)
    print("LegoMCP v6.0 Performance Benchmarks")
    print("=" * 60)
    print()

    # WebSocket benchmarks
    ws_bench = WebSocketBenchmark()

    print("WebSocket Event Emission Throughput:")
    print("-" * 40)
    result = ws_bench.benchmark_event_emission_throughput(1000)
    for key, value in result.items():
        print(f"  {key}: {value}")
    print()

    print("Concurrent Event Emission:")
    print("-" * 40)
    result = ws_bench.benchmark_concurrent_emissions(10, 100)
    for key, value in result.items():
        print(f"  {key}: {value}")
    print()

    # OME benchmarks
    ome_bench = OMERegistryBenchmark()

    print("OME Registration Throughput:")
    print("-" * 40)
    result = ome_bench.benchmark_ome_registration(500)
    for key, value in result.items():
        print(f"  {key}: {value}")
    print()

    # Supply Chain benchmarks
    sc_bench = SupplyChainBenchmark()

    print("Supply Chain Disruption Simulation:")
    print("-" * 40)
    result = sc_bench.benchmark_disruption_simulation(30)
    for key, value in result.items():
        print(f"  {key}: {value}")
    print()

    print("=" * 60)
    print("Benchmarks Complete")
    print("=" * 60)


if __name__ == "__main__":
    run_all_benchmarks()
