"""
Security Performance Benchmarks for LEGO MCP v8.0

Measures performance of security-critical operations:
- Post-Quantum Cryptography (ML-KEM, ML-DSA, SLH-DSA)
- Zero-Trust Authentication
- Anomaly Detection
- HSM Operations
- Audit Chain Operations

Author: LEGO MCP Performance Engineering
Reference: IEC 62443, NIST 800-171
"""

import pytest
import time
import statistics
import sys
import os
from typing import List, Dict, Any
from datetime import datetime, timezone
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


class BenchmarkResult:
    """Container for benchmark results."""

    def __init__(self, name: str, iterations: int):
        self.name = name
        self.iterations = iterations
        self.times: List[float] = []
        self.start_time = None
        self.end_time = None

    def record(self, elapsed: float):
        self.times.append(elapsed)

    @property
    def mean(self) -> float:
        return statistics.mean(self.times) if self.times else 0

    @property
    def median(self) -> float:
        return statistics.median(self.times) if self.times else 0

    @property
    def stdev(self) -> float:
        return statistics.stdev(self.times) if len(self.times) > 1 else 0

    @property
    def min_time(self) -> float:
        return min(self.times) if self.times else 0

    @property
    def max_time(self) -> float:
        return max(self.times) if self.times else 0

    @property
    def ops_per_second(self) -> float:
        return 1.0 / self.mean if self.mean > 0 else 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "iterations": self.iterations,
            "mean_ms": self.mean * 1000,
            "median_ms": self.median * 1000,
            "stdev_ms": self.stdev * 1000,
            "min_ms": self.min_time * 1000,
            "max_ms": self.max_time * 1000,
            "ops_per_second": self.ops_per_second,
        }

    def print_summary(self):
        print(f"\n{'='*60}")
        print(f"Benchmark: {self.name}")
        print(f"{'='*60}")
        print(f"  Iterations:    {self.iterations}")
        print(f"  Mean:          {self.mean*1000:.3f} ms")
        print(f"  Median:        {self.median*1000:.3f} ms")
        print(f"  Std Dev:       {self.stdev*1000:.3f} ms")
        print(f"  Min:           {self.min_time*1000:.3f} ms")
        print(f"  Max:           {self.max_time*1000:.3f} ms")
        print(f"  Ops/Second:    {self.ops_per_second:.1f}")


# =============================================================================
# Post-Quantum Cryptography Benchmarks
# =============================================================================

class TestPQCryptoBenchmarks:
    """Benchmarks for Post-Quantum Cryptography operations."""

    @pytest.fixture
    def pq_crypto(self):
        from dashboard.services.security.pq_crypto import PostQuantumCrypto
        return PostQuantumCrypto()

    def test_ml_kem_768_keygen_benchmark(self, pq_crypto, benchmark):
        """Benchmark ML-KEM-768 key generation."""
        from dashboard.services.security.pq_crypto import PQAlgorithm

        def keygen():
            return pq_crypto.generate_kem_keypair(PQAlgorithm.ML_KEM_768)

        result = benchmark(keygen)
        # Target: < 10ms per operation
        assert benchmark.stats.stats.mean < 0.010

    def test_ml_kem_768_encapsulate_benchmark(self, pq_crypto, benchmark):
        """Benchmark ML-KEM-768 encapsulation."""
        from dashboard.services.security.pq_crypto import PQAlgorithm

        keypair = pq_crypto.generate_kem_keypair(PQAlgorithm.ML_KEM_768)

        def encapsulate():
            return pq_crypto.encapsulate(keypair.public_key)

        result = benchmark(encapsulate)
        # Target: < 5ms per operation
        assert benchmark.stats.stats.mean < 0.005

    def test_ml_kem_768_decapsulate_benchmark(self, pq_crypto, benchmark):
        """Benchmark ML-KEM-768 decapsulation."""
        from dashboard.services.security.pq_crypto import PQAlgorithm

        keypair = pq_crypto.generate_kem_keypair(PQAlgorithm.ML_KEM_768)
        ciphertext, _ = pq_crypto.encapsulate(keypair.public_key)

        def decapsulate():
            return pq_crypto.decapsulate(keypair, ciphertext)

        result = benchmark(decapsulate)
        # Target: < 5ms per operation
        assert benchmark.stats.stats.mean < 0.005

    def test_ml_dsa_65_keygen_benchmark(self, pq_crypto, benchmark):
        """Benchmark ML-DSA-65 key generation."""
        from dashboard.services.security.pq_crypto import PQAlgorithm

        def keygen():
            return pq_crypto.generate_signing_keypair(PQAlgorithm.ML_DSA_65)

        result = benchmark(keygen)
        # Target: < 20ms per operation
        assert benchmark.stats.stats.mean < 0.020

    def test_ml_dsa_65_sign_benchmark(self, pq_crypto, benchmark):
        """Benchmark ML-DSA-65 signing."""
        from dashboard.services.security.pq_crypto import PQAlgorithm

        keypair = pq_crypto.generate_signing_keypair(PQAlgorithm.ML_DSA_65)
        message = b"Benchmark message for signing" * 10  # ~300 bytes

        def sign():
            return pq_crypto.sign(keypair, message)

        result = benchmark(sign)
        # Target: < 10ms per operation
        assert benchmark.stats.stats.mean < 0.010

    def test_ml_dsa_65_verify_benchmark(self, pq_crypto, benchmark):
        """Benchmark ML-DSA-65 verification."""
        from dashboard.services.security.pq_crypto import PQAlgorithm

        keypair = pq_crypto.generate_signing_keypair(PQAlgorithm.ML_DSA_65)
        message = b"Benchmark message for signing" * 10
        signature = pq_crypto.sign(keypair, message)

        def verify():
            return pq_crypto.verify(keypair.public_key, message, signature)

        result = benchmark(verify)
        # Target: < 5ms per operation
        assert benchmark.stats.stats.mean < 0.005

    def test_hybrid_encryption_benchmark(self, pq_crypto, benchmark):
        """Benchmark hybrid PQ + classical encryption."""
        from dashboard.services.security.pq_crypto import EncryptionMode

        plaintext = b"Sensitive manufacturing data" * 100  # ~2.8KB

        def encrypt():
            return pq_crypto.encrypt_hybrid(plaintext, mode=EncryptionMode.HYBRID)

        result = benchmark(encrypt)
        # Target: < 50ms per operation
        assert benchmark.stats.stats.mean < 0.050


# =============================================================================
# Zero-Trust Authentication Benchmarks
# =============================================================================

class TestZeroTrustBenchmarks:
    """Benchmarks for Zero-Trust authentication operations."""

    @pytest.fixture
    def gateway(self):
        from dashboard.services.security.zero_trust import ZeroTrustGateway
        return ZeroTrustGateway()

    def test_token_validation_benchmark(self, gateway, benchmark):
        """Benchmark JWT token validation."""
        token = "test_token_for_benchmark"

        def validate():
            return gateway.validate_token(token)

        result = benchmark(validate)
        # Target: < 1ms per operation (must be fast for every request)
        assert benchmark.stats.stats.mean < 0.001

    def test_trust_score_calculation_benchmark(self, gateway, benchmark):
        """Benchmark trust score calculation."""
        from dashboard.services.security.zero_trust import TrustScoreCalculator

        calculator = TrustScoreCalculator()
        context = {
            "device_posture": {"os_patched": True, "antivirus": True},
            "user_behavior": {"failed_logins": 0},
            "network_context": {"vpn": True},
        }

        def calculate():
            return calculator.calculate(**context)

        result = benchmark(calculate)
        # Target: < 1ms per operation
        assert benchmark.stats.stats.mean < 0.001

    def test_policy_evaluation_benchmark(self, gateway, benchmark):
        """Benchmark OPA-style policy evaluation."""
        from dashboard.services.security.zero_trust import PolicyEnforcementPoint

        pep = PolicyEnforcementPoint()

        def evaluate():
            return pep.evaluate(
                subject="operator@plant-1",
                action="read",
                resource="equipment-status",
                environment={"time": "09:00"},
            )

        result = benchmark(evaluate)
        # Target: < 5ms per operation
        assert benchmark.stats.stats.mean < 0.005


# =============================================================================
# Anomaly Detection Benchmarks
# =============================================================================

class TestAnomalyDetectionBenchmarks:
    """Benchmarks for anomaly detection operations."""

    @pytest.fixture
    def detector(self):
        from dashboard.services.security.anomaly_detection import SecurityAnomalyDetector
        return SecurityAnomalyDetector()

    def test_event_analysis_benchmark(self, detector, benchmark):
        """Benchmark single event analysis."""
        from dashboard.services.security.anomaly_detection import SecurityEvent

        event = SecurityEvent(
            user="operator1",
            action="equipment_control",
            resource="robot-arm-01",
            source_ip="192.168.1.100",
            timestamp=datetime.now(timezone.utc),
        )

        def analyze():
            return detector.analyze(event)

        result = benchmark(analyze)
        # Target: < 5ms per event (must handle 1000+ events/sec)
        assert benchmark.stats.stats.mean < 0.005

    def test_quick_check_benchmark(self, detector, benchmark):
        """Benchmark quick anomaly check (hot path)."""

        def check():
            return detector.quick_check(
                user="operator1",
                action="api_call",
                resource="endpoint",
            )

        result = benchmark(check)
        # Target: < 0.5ms per check (very hot path)
        assert benchmark.stats.stats.mean < 0.0005

    def test_batch_analysis_benchmark(self, detector, benchmark):
        """Benchmark batch event analysis."""
        from dashboard.services.security.anomaly_detection import SecurityEvent

        events = [
            SecurityEvent(
                user=f"user_{i % 10}",
                action="api_call",
                resource=f"resource_{i % 5}",
                source_ip=f"192.168.1.{i % 256}",
                timestamp=datetime.now(timezone.utc),
            )
            for i in range(100)
        ]

        def analyze_batch():
            return [detector.analyze(e) for e in events]

        result = benchmark(analyze_batch)
        # Target: < 200ms for 100 events
        assert benchmark.stats.stats.mean < 0.200


# =============================================================================
# Audit Chain Benchmarks
# =============================================================================

class TestAuditChainBenchmarks:
    """Benchmarks for audit chain operations."""

    @pytest.fixture
    def audit_chain(self):
        from dashboard.services.traceability.audit_chain import DigitalThread
        return DigitalThread()

    def test_append_entry_benchmark(self, audit_chain, benchmark):
        """Benchmark appending audit entry."""

        def append():
            return audit_chain.append_event(
                event_type="api_call",
                actor="benchmark_user",
                action="test_action",
                resource="test_resource",
                details={"key": "value"},
            )

        result = benchmark(append)
        # Target: < 1ms per append
        assert benchmark.stats.stats.mean < 0.001

    def test_verify_chain_benchmark(self, audit_chain, benchmark):
        """Benchmark chain verification (100 entries)."""
        # Pre-populate chain
        for i in range(100):
            audit_chain.append_event(
                event_type="test",
                actor="benchmark",
                action=f"action_{i}",
                resource="resource",
            )

        def verify():
            return audit_chain.verify_integrity()

        result = benchmark(verify)
        # Target: < 50ms for 100 entries
        assert benchmark.stats.stats.mean < 0.050

    def test_query_by_actor_benchmark(self, audit_chain, benchmark):
        """Benchmark querying entries by actor."""
        # Pre-populate
        for i in range(1000):
            audit_chain.append_event(
                event_type="test",
                actor=f"user_{i % 10}",
                action="action",
                resource="resource",
            )

        def query():
            return audit_chain.get_entries_by_actor("user_5")

        result = benchmark(query)
        # Target: < 20ms for query
        assert benchmark.stats.stats.mean < 0.020


# =============================================================================
# HSM Operations Benchmarks
# =============================================================================

class TestHSMBenchmarks:
    """Benchmarks for HSM operations (simulated)."""

    @pytest.fixture
    def key_manager(self):
        from dashboard.services.security.hsm.key_manager import KeyManager
        return KeyManager()

    def test_hsm_sign_benchmark(self, key_manager, benchmark):
        """Benchmark HSM signing operation."""
        key_id = key_manager.generate_key(algorithm="ECDSA-P384", purpose="signing")
        message = b"Data to sign" * 100

        def sign():
            return key_manager.sign(key_id, message)

        result = benchmark(sign)
        # Target: < 50ms per operation (HSM has latency)
        assert benchmark.stats.stats.mean < 0.050

    def test_hsm_verify_benchmark(self, key_manager, benchmark):
        """Benchmark HSM verification operation."""
        key_id = key_manager.generate_key(algorithm="ECDSA-P384", purpose="signing")
        message = b"Data to sign" * 100
        signature = key_manager.sign(key_id, message)

        def verify():
            return key_manager.verify(key_id, message, signature)

        result = benchmark(verify)
        # Target: < 10ms per operation
        assert benchmark.stats.stats.mean < 0.010


# =============================================================================
# Throughput Tests
# =============================================================================

class TestSecurityThroughput:
    """High-throughput tests for security operations."""

    def test_authentication_throughput(self):
        """Test authentication throughput target: 1000/sec."""
        from dashboard.services.security.zero_trust import ZeroTrustGateway

        gateway = ZeroTrustGateway()
        target_ops = 1000
        start = time.time()

        for i in range(target_ops):
            gateway.validate_token(f"token_{i}")

        elapsed = time.time() - start
        ops_per_sec = target_ops / elapsed

        print(f"\nAuthentication throughput: {ops_per_sec:.0f} ops/sec")
        assert ops_per_sec >= 1000, f"Below target: {ops_per_sec:.0f} ops/sec"

    def test_anomaly_detection_throughput(self):
        """Test anomaly detection throughput target: 1000 events/sec."""
        from dashboard.services.security.anomaly_detection import SecurityAnomalyDetector

        detector = SecurityAnomalyDetector()
        target_ops = 1000
        start = time.time()

        for i in range(target_ops):
            detector.quick_check(
                user=f"user_{i % 100}",
                action="api_call",
                resource="endpoint",
            )

        elapsed = time.time() - start
        ops_per_sec = target_ops / elapsed

        print(f"\nAnomaly detection throughput: {ops_per_sec:.0f} events/sec")
        assert ops_per_sec >= 1000, f"Below target: {ops_per_sec:.0f} events/sec"

    def test_audit_append_throughput(self):
        """Test audit append throughput target: 5000/sec."""
        from dashboard.services.traceability.audit_chain import DigitalThread

        audit = DigitalThread()
        target_ops = 5000
        start = time.time()

        for i in range(target_ops):
            audit.append_event(
                event_type="test",
                actor="benchmark",
                action=f"action_{i}",
                resource="resource",
            )

        elapsed = time.time() - start
        ops_per_sec = target_ops / elapsed

        print(f"\nAudit append throughput: {ops_per_sec:.0f} ops/sec")
        assert ops_per_sec >= 5000, f"Below target: {ops_per_sec:.0f} ops/sec"


# =============================================================================
# Main
# =============================================================================

if __name__ == "__main__":
    # Run with: pytest benchmark_security.py --benchmark-only -v
    pytest.main([__file__, "-v", "--benchmark-only"])
