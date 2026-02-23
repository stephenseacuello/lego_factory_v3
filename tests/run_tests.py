#!/usr/bin/env python3
"""
LegoMCP Test Runner.

Run comprehensive tests for all PhD-level manufacturing components.

Usage:
    python tests/run_tests.py                    # Run all tests
    python tests/run_tests.py --unit             # Run unit tests only
    python tests/run_tests.py --integration      # Run integration tests
    python tests/run_tests.py --benchmark        # Run benchmark tests
    python tests/run_tests.py --compliance       # Run compliance tests
    python tests/run_tests.py --coverage         # Run with coverage report
"""

import unittest
import sys
import os
import argparse
from datetime import datetime
from typing import List, Dict, Any

# Add project root to path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)


def discover_tests(test_dir: str, pattern: str = "test_*.py") -> unittest.TestSuite:
    """Discover and load tests from directory."""
    loader = unittest.TestLoader()
    return loader.discover(test_dir, pattern=pattern)


def run_unit_tests() -> unittest.TestResult:
    """Run all unit tests."""
    print("\n" + "=" * 60)
    print("RUNNING UNIT TESTS")
    print("=" * 60 + "\n")

    test_dir = os.path.dirname(os.path.abspath(__file__))
    suite = discover_tests(test_dir)

    runner = unittest.TextTestRunner(verbosity=2)
    return runner.run(suite)


def run_integration_tests() -> unittest.TestResult:
    """Run integration tests."""
    print("\n" + "=" * 60)
    print("RUNNING INTEGRATION TESTS")
    print("=" * 60 + "\n")

    suite = unittest.TestSuite()

    # Add integration test classes
    from tests.test_digital_twin import TestStateEventSourcing
    from tests.test_scheduling import TestSchedulingIntegration
    from tests.test_sustainability import TestLCAOptimizer

    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(TestStateEventSourcing))
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(TestSchedulingIntegration))
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(TestLCAOptimizer))

    runner = unittest.TextTestRunner(verbosity=2)
    return runner.run(suite)


def run_benchmark_tests() -> Dict[str, Any]:
    """Run performance benchmark tests."""
    print("\n" + "=" * 60)
    print("RUNNING BENCHMARK TESTS")
    print("=" * 60 + "\n")

    import time
    results = {}

    # Benchmark 1: Scheduling Performance
    print("Benchmark 1: Scheduling Algorithm Comparison")
    try:
        from dashboard.services.scheduling.quantum.qaoa_scheduler import ManufacturingQAOA
        from dashboard.services.scheduling.nsga2_scheduler import NSGA2Scheduler

        jobs = [{"id": f"J{i}", "duration": 10 + i, "priority": i % 3} for i in range(10)]

        # QAOA
        start = time.time()
        qaoa = ManufacturingQAOA()
        qaoa_result = qaoa.schedule_production(jobs, ["M1", "M2"], "minimize_makespan")
        qaoa_time = time.time() - start

        # NSGA-II
        start = time.time()
        nsga = NSGA2Scheduler(population_size=50, num_generations=20)
        nsga_result = nsga.optimize(jobs, ["minimize_makespan"])
        nsga_time = time.time() - start

        results["scheduling"] = {
            "qaoa_time": qaoa_time,
            "nsga2_time": nsga_time,
            "status": "PASS"
        }
        print(f"  QAOA: {qaoa_time:.3f}s, NSGA-II: {nsga_time:.3f}s ✓")
    except Exception as e:
        results["scheduling"] = {"status": "FAIL", "error": str(e)}
        print(f"  Failed: {e}")

    # Benchmark 2: LCA Calculation
    print("\nBenchmark 2: LCA Calculation Performance")
    try:
        from dashboard.services.sustainability.lca.lca_engine import ManufacturingLCA

        start = time.time()
        lca = ManufacturingLCA()
        for _ in range(100):
            lca.assess_product("PLA", 0.1, 2.0, 0.5)
        lca_time = time.time() - start

        results["lca"] = {
            "time_for_100": lca_time,
            "avg_per_assessment": lca_time / 100,
            "status": "PASS"
        }
        print(f"  100 assessments: {lca_time:.3f}s ({lca_time*10:.1f}ms avg) ✓")
    except Exception as e:
        results["lca"] = {"status": "FAIL", "error": str(e)}
        print(f"  Failed: {e}")

    # Benchmark 3: Quality Prediction
    print("\nBenchmark 3: Quality Prediction Performance")
    try:
        from dashboard.services.quality.multimodal.sensor_fusion import ManufacturingSensorFusion

        start = time.time()
        fusion = ManufacturingSensorFusion()
        for _ in range(50):
            fusion.predict_quality(
                temperature=[200.0, 205.0, 210.0],
                vibration=[0.1, 0.15, 0.12],
                layer_image=[[0.5] * 64 for _ in range(64)]
            )
        quality_time = time.time() - start

        results["quality"] = {
            "time_for_50": quality_time,
            "avg_per_prediction": quality_time / 50,
            "status": "PASS"
        }
        print(f"  50 predictions: {quality_time:.3f}s ({quality_time*20:.1f}ms avg) ✓")
    except Exception as e:
        results["quality"] = {"status": "FAIL", "error": str(e)}
        print(f"  Failed: {e}")

    return results


def run_compliance_tests() -> unittest.TestResult:
    """Run ISO compliance validation tests."""
    print("\n" + "=" * 60)
    print("RUNNING COMPLIANCE TESTS")
    print("=" * 60 + "\n")

    suite = unittest.TestSuite()

    from tests.test_compliance import (
        TestDocumentControl,
        TestCAPAService,
        TestInternalAudit,
        TestManagementReview
    )

    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(TestDocumentControl))
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(TestCAPAService))
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(TestInternalAudit))
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(TestManagementReview))

    runner = unittest.TextTestRunner(verbosity=2)
    return runner.run(suite)


def run_with_coverage() -> None:
    """Run tests with coverage reporting."""
    try:
        import coverage
    except ImportError:
        print("Coverage not installed. Install with: pip install coverage")
        sys.exit(1)

    cov = coverage.Coverage(
        source=["dashboard/services"],
        omit=["*/__pycache__/*", "*/tests/*"]
    )

    cov.start()
    result = run_unit_tests()
    cov.stop()
    cov.save()

    print("\n" + "=" * 60)
    print("COVERAGE REPORT")
    print("=" * 60 + "\n")

    cov.report(show_missing=False)

    # Generate HTML report
    html_dir = os.path.join(PROJECT_ROOT, "htmlcov")
    cov.html_report(directory=html_dir)
    print(f"\nHTML report: {html_dir}/index.html")


def generate_test_report(results: Dict[str, Any]) -> str:
    """Generate test report summary."""
    report_lines = [
        "=" * 60,
        "LEGOMCP TEST REPORT",
        f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "=" * 60,
        "",
    ]

    for category, data in results.items():
        report_lines.append(f"\n{category.upper()}:")
        if isinstance(data, unittest.TestResult):
            tests_run = data.testsRun
            failures = len(data.failures)
            errors = len(data.errors)
            success = tests_run - failures - errors

            report_lines.append(f"  Tests Run: {tests_run}")
            report_lines.append(f"  Passed: {success}")
            report_lines.append(f"  Failed: {failures}")
            report_lines.append(f"  Errors: {errors}")
            report_lines.append(f"  Success Rate: {success/tests_run*100:.1f}%")
        elif isinstance(data, dict):
            for key, value in data.items():
                report_lines.append(f"  {key}: {value}")

    report_lines.extend([
        "",
        "=" * 60,
    ])

    return "\n".join(report_lines)


def main():
    """Main test runner entry point."""
    parser = argparse.ArgumentParser(description="LegoMCP Test Runner")
    parser.add_argument("--unit", action="store_true", help="Run unit tests only")
    parser.add_argument("--integration", action="store_true", help="Run integration tests")
    parser.add_argument("--benchmark", action="store_true", help="Run benchmark tests")
    parser.add_argument("--compliance", action="store_true", help="Run compliance tests")
    parser.add_argument("--coverage", action="store_true", help="Run with coverage")
    parser.add_argument("--all", action="store_true", help="Run all tests")

    args = parser.parse_args()

    # Default to all tests if no specific option
    if not any([args.unit, args.integration, args.benchmark, args.compliance, args.all]):
        args.all = True

    results = {}

    print("\n" + "=" * 60)
    print("LEGOMCP v5.0 TEST SUITE")
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    try:
        if args.coverage:
            run_with_coverage()
            return

        if args.unit or args.all:
            results["unit"] = run_unit_tests()

        if args.integration or args.all:
            results["integration"] = run_integration_tests()

        if args.benchmark or args.all:
            results["benchmark"] = run_benchmark_tests()

        if args.compliance or args.all:
            results["compliance"] = run_compliance_tests()

        # Print summary
        report = generate_test_report(results)
        print("\n" + report)

        # Save report
        report_path = os.path.join(PROJECT_ROOT, "test_report.txt")
        with open(report_path, "w") as f:
            f.write(report)
        print(f"\nReport saved to: {report_path}")

        # Exit with error if any tests failed
        for result in results.values():
            if isinstance(result, unittest.TestResult):
                if result.failures or result.errors:
                    sys.exit(1)

    except KeyboardInterrupt:
        print("\n\nTest run interrupted by user.")
        sys.exit(1)
    except Exception as e:
        print(f"\n\nTest run failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
