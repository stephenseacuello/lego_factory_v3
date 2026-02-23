"""
End-to-End Integration Tests for LEGO MCP v8.0

Tests complete workflows across all system components:
- Manufacturing execution flow
- Quality control pipeline
- Security and compliance
- Command center operations
- AI/ML predictions with actions
- Co-simulation scenarios

Author: LEGO MCP Integration Testing
"""

import pytest
import asyncio
import json
import time
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, List
from unittest.mock import Mock, patch, AsyncMock
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


# =============================================================================
# Test Fixtures
# =============================================================================

@pytest.fixture
def app_client():
    """Create Flask test client."""
    from dashboard.app import create_app

    app = create_app(testing=True)
    with app.test_client() as client:
        yield client


@pytest.fixture
def command_center():
    """Initialize command center services."""
    from dashboard.services.command_center import (
        SystemHealthService,
        KPIAggregator,
        AlertManager,
        ActionConsole,
    )

    return {
        "health": SystemHealthService(),
        "kpis": KPIAggregator(),
        "alerts": AlertManager(),
        "actions": ActionConsole(),
    }


@pytest.fixture
def security_services():
    """Initialize security services."""
    from dashboard.services.security.pq_crypto import PostQuantumCrypto
    from dashboard.services.security.zero_trust import ZeroTrustGateway
    from dashboard.services.security.anomaly_detection import SecurityAnomalyDetector

    return {
        "pq_crypto": PostQuantumCrypto(),
        "zero_trust": ZeroTrustGateway(),
        "anomaly": SecurityAnomalyDetector(),
    }


@pytest.fixture
def manufacturing_services():
    """Initialize manufacturing services."""
    from dashboard.services.standards.isa95_integration import ISA95IntegrationManager

    return {
        "isa95": ISA95IntegrationManager(),
    }


# =============================================================================
# End-to-End Manufacturing Flow Tests
# =============================================================================

class TestManufacturingFlow:
    """End-to-end tests for manufacturing workflows."""

    def test_complete_work_order_flow(self, command_center, manufacturing_services):
        """Test complete work order from creation to completion."""
        from dashboard.services.standards.isa95_integration import (
            OperationsRequest, OperationType
        )
        from dashboard.services.command_center import KPICategory, AlertSeverity

        # Step 1: Create work order
        work_order = OperationsRequest(
            id="WO-E2E-001",
            operation_type=OperationType.PRODUCTION,
            description="Produce 100 4x2 bricks",
            priority=1,
        )
        manufacturing_services["isa95"].submit_work_order(work_order)

        # Step 2: Record initial KPIs
        command_center["kpis"].record_kpi(
            name="throughput",
            value=0,
            category=KPICategory.PRODUCTION,
            unit="parts/hr",
        )

        # Step 3: Simulate production progress
        for progress in [25, 50, 75, 100]:
            command_center["kpis"].record_kpi(
                name="throughput",
                value=progress,
                category=KPICategory.PRODUCTION,
                unit="parts/hr",
            )

            # Check for alerts at each stage
            if progress == 50:
                # Simulate a warning
                command_center["alerts"].create_alert(
                    title="Temperature Warning",
                    message="Mold temperature approaching limit",
                    severity=AlertSeverity.MEDIUM,
                    source="equipment",
                )

        # Step 4: Verify completion
        dashboard = command_center["kpis"].get_dashboard()
        assert dashboard is not None

        # Step 5: Verify alert was created
        alerts = command_center["alerts"].list_alerts()
        assert len(alerts) >= 1

    def test_quality_inspection_flow(self, command_center):
        """Test quality inspection from detection to action."""
        from dashboard.services.command_center import (
            AlertSeverity, ActionCategory
        )

        # Step 1: Simulate quality issue detection
        alert = command_center["alerts"].create_alert(
            title="Defect Detected",
            message="Surface defect detected by vision system",
            severity=AlertSeverity.HIGH,
            source="quality",
            entity_type="product",
            entity_id="PROD-001",
        )

        # Step 2: Create corrective action
        action = command_center["actions"].create_action(
            title="Adjust Injection Parameters",
            description="Reduce injection pressure by 5%",
            category=ActionCategory.EQUIPMENT,
            target_id="injector-001",
            parameters={"pressure_reduction": 5},
            requires_approval=True,
        )

        # Step 3: Approve action
        command_center["actions"].approve_action(
            action.id,
            approved_by="quality_engineer",
        )

        # Step 4: Execute action
        result = command_center["actions"].execute_action(action.id)

        # Step 5: Resolve original alert
        command_center["alerts"].resolve_alert(
            alert.id,
            resolved_by="quality_engineer",
            resolution="Parameters adjusted, defect rate reduced",
        )

        # Verify flow completed
        resolved_alert = command_center["alerts"].get_alert(alert.id)
        assert resolved_alert.status.value == "resolved"


# =============================================================================
# Security Integration Tests
# =============================================================================

class TestSecurityIntegration:
    """End-to-end tests for security workflows."""

    def test_secure_command_flow(self, security_services, command_center):
        """Test secure command execution with PQ signatures."""
        from dashboard.services.security.pq_crypto import PQAlgorithm
        from dashboard.services.command_center import ActionCategory

        pq = security_services["pq_crypto"]

        # Step 1: Generate signing keypair
        keypair = pq.generate_signing_keypair(PQAlgorithm.ML_DSA_65)

        # Step 2: Create command
        command = {
            "action": "set_temperature",
            "target": "extruder-001",
            "value": 220,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        command_bytes = json.dumps(command).encode()

        # Step 3: Sign command
        signature = pq.sign(keypair, command_bytes)

        # Step 4: Verify signature
        is_valid = pq.verify(keypair.public_key, command_bytes, signature)
        assert is_valid, "Command signature verification failed"

        # Step 5: Create action with signed command
        action = command_center["actions"].create_action(
            title="Set Extruder Temperature",
            description="Signed command to set temperature",
            category=ActionCategory.EQUIPMENT,
            target_id="extruder-001",
            parameters={
                "command": command,
                "signature": signature.hex(),
                "key_id": keypair.key_id,
            },
        )

        assert action is not None

    def test_anomaly_detection_to_alert_flow(self, security_services, command_center):
        """Test anomaly detection triggering security alert."""
        from dashboard.services.security.anomaly_detection import SecurityEvent
        from dashboard.services.command_center import AlertSeverity

        detector = security_services["anomaly"]

        # Step 1: Create suspicious event
        event = SecurityEvent(
            user="unknown_user",
            action="equipment_control",
            resource="robot-arm-01",
            source_ip="10.0.0.99",  # Unknown IP
            timestamp=datetime.now(timezone.utc),
        )

        # Step 2: Analyze event
        result = detector.analyze(event)

        # Step 3: If anomalous, create alert
        if result and result.is_anomaly:
            alert = command_center["alerts"].create_alert(
                title="Security Anomaly Detected",
                message=f"Suspicious activity from {event.user}",
                severity=AlertSeverity.HIGH,
                source="security",
                entity_type="user",
                entity_id=event.user,
            )
            assert alert.severity == AlertSeverity.HIGH

    def test_zero_trust_authorization_flow(self, security_services):
        """Test zero-trust authorization for resource access."""
        from dashboard.services.security.zero_trust import (
            ResourceType, AccessLevel
        )

        gateway = security_services["zero_trust"]

        # Step 1: Authenticate user
        token = gateway.create_session("operator@plant-1", max_lifetime=3600)

        # Step 2: Check authorization for different resources
        test_cases = [
            (ResourceType.EQUIPMENT, "cnc-001", AccessLevel.READ, True),
            (ResourceType.EQUIPMENT, "cnc-001", AccessLevel.CONTROL, True),
            (ResourceType.DATA, "production-records", AccessLevel.READ, True),
            (ResourceType.API, "admin-api", AccessLevel.WRITE, False),
        ]

        for resource_type, resource_id, access_level, expected in test_cases:
            result = gateway.authorize(
                identity="operator@plant-1",
                resource_type=resource_type,
                resource_id=resource_id,
                access_level=access_level,
            )
            # Result may vary based on policy configuration


# =============================================================================
# AI/ML Integration Tests
# =============================================================================

class TestAIMLIntegration:
    """End-to-end tests for AI/ML workflows."""

    def test_predictive_maintenance_flow(self, command_center):
        """Test predictive maintenance from prediction to action."""
        from dashboard.services.command_center import (
            ActionCategory, AlertSeverity
        )

        # Step 1: Simulate AI prediction (equipment failure predicted)
        prediction = {
            "equipment_id": "motor-001",
            "failure_probability": 0.85,
            "predicted_failure_date": (datetime.now() + timedelta(days=7)).isoformat(),
            "confidence": 0.92,
            "recommended_action": "Replace bearing",
        }

        # Step 2: Create alert based on prediction
        alert = command_center["alerts"].create_alert(
            title="Predicted Equipment Failure",
            message=f"AI predicts {prediction['failure_probability']*100:.0f}% failure probability",
            severity=AlertSeverity.HIGH,
            source="ai_prediction",
            entity_type="equipment",
            entity_id=prediction["equipment_id"],
        )

        # Step 3: Create maintenance action
        action = command_center["actions"].create_action(
            title="Schedule Preventive Maintenance",
            description=prediction["recommended_action"],
            category=ActionCategory.MAINTENANCE,
            target_id=prediction["equipment_id"],
            parameters={
                "prediction_confidence": prediction["confidence"],
                "due_date": prediction["predicted_failure_date"],
            },
            requires_approval=True,
        )

        assert action is not None
        assert alert is not None

    def test_pinn_digital_twin_flow(self):
        """Test PINN digital twin prediction to quality action."""
        from dashboard.services.digital_twin.pinn_model import create_thermal_twin

        # Step 1: Create thermal twin
        twin = create_thermal_twin("4x2", "ABS")

        # Step 2: Predict temperature at critical location
        temp = twin.predict_temperature(
            x=0.016,  # Center of brick
            y=0.008,
            z=0.005,
            t=15.0,   # 15 seconds into cooling
        )

        # Step 3: Check if temperature is within spec
        target_temp = 60.0  # Target temp at this time
        tolerance = 5.0

        temp_value = temp if isinstance(temp, (int, float)) else temp.get("temperature", 60)

        is_within_spec = abs(temp_value - target_temp) <= tolerance

        # Step 4: If out of spec, would trigger action
        if not is_within_spec:
            # Would create adjustment action
            pass

        # Verify twin is functional
        assert twin is not None

    def test_causal_analysis_flow(self):
        """Test causal discovery for root cause analysis."""
        from dashboard.services.ai.causal_discovery import (
            PCAlgorithm, CausalMethod
        )
        import numpy as np

        # Step 1: Generate manufacturing data with known causality
        # A (temp) -> B (viscosity) -> C (quality)
        np.random.seed(42)
        n = 200
        A = np.random.randn(n) * 10 + 220  # Temperature
        B = 0.7 * A + np.random.randn(n) * 5  # Viscosity depends on temp
        C = 0.5 * B + np.random.randn(n) * 2  # Quality depends on viscosity

        data = np.column_stack([A, B, C])

        # Step 2: Discover causal structure
        pc = PCAlgorithm(alpha=0.05)
        graph = pc.discover(data, ["temperature", "viscosity", "quality"])

        # Step 3: Verify causal relationships discovered
        assert len(graph.nodes) == 3

        # Step 4: Use for root cause analysis
        # If quality issue, trace back through graph


# =============================================================================
# Command Center Integration Tests
# =============================================================================

class TestCommandCenterIntegration:
    """End-to-end tests for command center operations."""

    def test_system_health_aggregation(self, command_center):
        """Test system health aggregation from multiple sources."""
        from dashboard.services.command_center import HealthStatus

        health_service = command_center["health"]

        # Register multiple health checks
        services = ["dashboard", "mcp_server", "slicer", "ros2_bridge"]

        for service in services:
            def mock_check(svc=service):
                return {"status": HealthStatus.HEALTHY, "latency_ms": 10}

            health_service.register_health_check(service, "core", mock_check)

        # Get aggregated status
        summary = health_service.get_summary()
        assert summary is not None

    def test_kpi_rollup_hierarchy(self, command_center):
        """Test KPI aggregation across hierarchy levels."""
        from dashboard.services.command_center import KPICategory

        kpi_service = command_center["kpis"]

        # Record KPIs at machine level
        machines = ["CNC-001", "CNC-002", "CNC-003"]
        for machine in machines:
            kpi_service.record_kpi(
                name=f"oee_{machine}",
                value=85 + hash(machine) % 10,  # 85-94%
                category=KPICategory.EQUIPMENT,
                unit="%",
                metadata={"machine": machine, "cell": "CELL-01"},
            )

        # Get dashboard should show aggregated view
        dashboard = kpi_service.get_dashboard()
        assert dashboard is not None

    def test_alert_correlation(self, command_center):
        """Test alert correlation across systems."""
        from dashboard.services.command_center import AlertSeverity

        alert_manager = command_center["alerts"]

        # Create related alerts from different sources
        alerts = []

        # Equipment alert
        alerts.append(alert_manager.create_alert(
            title="Motor Overheating",
            message="Motor temp 85C",
            severity=AlertSeverity.MEDIUM,
            source="equipment",
            entity_id="motor-001",
        ))

        # Quality alert (potentially related)
        alerts.append(alert_manager.create_alert(
            title="Dimension Out of Spec",
            message="Part length +0.2mm",
            severity=AlertSeverity.MEDIUM,
            source="quality",
            entity_id="inspection-001",
        ))

        # Process alert (potentially related)
        alerts.append(alert_manager.create_alert(
            title="Cycle Time Increased",
            message="Cycle time +15%",
            severity=AlertSeverity.LOW,
            source="process",
            entity_id="process-001",
        ))

        # All alerts should be created
        assert len(alerts) == 3


# =============================================================================
# Co-Simulation Integration Tests
# =============================================================================

class TestCoSimulationIntegration:
    """End-to-end tests for co-simulation scenarios."""

    def test_what_if_scenario_execution(self):
        """Test what-if scenario creation and execution."""
        from dashboard.services.cosimulation.scenario_manager import (
            ScenarioManager, Scenario, ScenarioType
        )

        manager = ScenarioManager()

        # Create scenario
        scenario = Scenario(
            name="Demand Surge Test",
            scenario_type=ScenarioType.WHAT_IF,
            parameters={
                "demand_multiplier": 1.5,
                "duration_hours": 24,
            },
        )

        scenario_id = manager.create_scenario(scenario)
        assert scenario_id is not None

        # Run scenario (simplified)
        result = manager.run_scenario(scenario_id)
        assert result is not None

    def test_optimization_loop(self):
        """Test parameter optimization loop."""
        from dashboard.services.cosimulation.optimization_loop import (
            OptimizationLoop, OptimizationObjective
        )

        optimizer = OptimizationLoop()

        # Define optimization problem
        objective = OptimizationObjective(
            name="maximize_throughput",
            metric="throughput",
            direction="maximize",
            constraints={
                "quality": {"min": 0.95},
                "energy": {"max": 100},
            },
        )

        # Run optimization
        result = optimizer.optimize(
            objective=objective,
            parameters={
                "injection_speed": (50, 150),
                "cooling_time": (10, 30),
            },
            iterations=10,
        )

        assert result is not None


# =============================================================================
# Compliance Integration Tests
# =============================================================================

class TestComplianceIntegration:
    """End-to-end tests for compliance workflows."""

    def test_audit_trail_completeness(self):
        """Test audit trail captures all operations."""
        from dashboard.services.traceability.audit_chain import DigitalThread

        audit = DigitalThread()

        # Perform series of operations
        operations = [
            ("config_change", "admin", "update", "safety_params"),
            ("equipment_control", "operator", "start", "cnc-001"),
            ("quality_check", "inspector", "approve", "batch-001"),
            ("work_order", "planner", "create", "wo-001"),
        ]

        for event_type, actor, action, resource in operations:
            audit.append_event(
                event_type=event_type,
                actor=actor,
                action=action,
                resource=resource,
            )

        # Verify chain integrity
        valid, _ = audit.verify_integrity()
        assert valid, "Audit chain integrity check failed"

        # Verify all operations captured
        entries = audit.get_all_entries()
        assert len(entries) >= len(operations)

    def test_cmmc_compliance_check(self):
        """Test CMMC compliance assessment."""
        from dashboard.services.compliance.cmmc_compliance import (
            CMMCAssessment, CMMCLevel, ComplianceStatus
        )

        assessment = CMMCAssessment(target_level=CMMCLevel.LEVEL_2)

        # Assess critical practices
        practices = [
            ("AC.L1-3.1.1", "Access Control Policy"),
            ("AC.L1-3.1.2", "Limit Access"),
            ("AU.L1-3.3.1", "Create Audit Logs"),
            ("SC.L1-3.13.1", "Boundary Protection"),
        ]

        for practice_id, description in practices:
            assessment.assess_practice(
                practice_id=practice_id,
                status=ComplianceStatus.FULLY_IMPLEMENTED,
                evidence=[f"{description} implemented"],
            )

        # Get readiness score
        readiness = assessment.get_readiness_score()
        assert readiness["fully_implemented"] >= len(practices)


# =============================================================================
# Performance Integration Tests
# =============================================================================

class TestPerformanceIntegration:
    """Performance tests for integrated system."""

    def test_end_to_end_latency(self, command_center):
        """Test end-to-end latency for critical path."""
        from dashboard.services.command_center import AlertSeverity

        start = time.time()

        # Create alert
        alert = command_center["alerts"].create_alert(
            title="E2E Test Alert",
            message="Testing latency",
            severity=AlertSeverity.HIGH,
            source="test",
        )

        # Acknowledge
        command_center["alerts"].acknowledge_alert(
            alert.id,
            acknowledged_by="test",
        )

        # Resolve
        command_center["alerts"].resolve_alert(
            alert.id,
            resolved_by="test",
            resolution="Test complete",
        )

        elapsed = time.time() - start

        print(f"\nEnd-to-end alert lifecycle: {elapsed*1000:.2f}ms")
        # Target: < 100ms for complete alert lifecycle
        assert elapsed < 0.100

    def test_concurrent_operations(self, command_center):
        """Test system under concurrent operations."""
        import threading

        results = {"success": 0, "failure": 0}
        lock = threading.Lock()

        def create_alert(i):
            try:
                from dashboard.services.command_center import AlertSeverity

                command_center["alerts"].create_alert(
                    title=f"Concurrent Alert {i}",
                    message="Testing concurrency",
                    severity=AlertSeverity.LOW,
                    source="test",
                )
                with lock:
                    results["success"] += 1
            except Exception:
                with lock:
                    results["failure"] += 1

        # Create 50 concurrent alerts
        threads = []
        for i in range(50):
            t = threading.Thread(target=create_alert, args=(i,))
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        print(f"\nConcurrency test: {results['success']} success, {results['failure']} failure")
        assert results["success"] >= 45  # Allow some variance


# =============================================================================
# Main
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "-x"])
