"""
Tests for LEGO MCP v6.0 API Routes.

Tests for:
- Causal AI routes (/api/v6/causal/*)
- Agent orchestration routes (/api/v6/agents/*)
- Closed-loop learning routes (/api/v6/closed-loop/*)
- Generative design routes (/api/v6/generative/*)
- Research routes (/api/v6/research/*)
- Action approval routes (/api/v6/actions/*)
"""

import pytest
import json
from flask import Flask


@pytest.fixture
def app():
    """Create test Flask application."""
    from dashboard.app import create_app
    app = create_app("testing")
    app.config["TESTING"] = True
    return app


@pytest.fixture
def client(app):
    """Create test client."""
    return app.test_client()


# ============================================
# Causal AI Route Tests
# ============================================

class TestCausalRoutes:
    """Tests for causal AI routes."""

    def test_get_causal_graph(self, client):
        """Test getting causal graph."""
        response = client.get("/api/v6/causal/graph")
        assert response.status_code == 200

        data = json.loads(response.data)
        assert data["success"] == True
        assert "graph" in data
        assert "nodes" in data["graph"]
        assert "edges" in data["graph"]

    def test_counterfactual_query(self, client):
        """Test counterfactual query."""
        response = client.post(
            "/api/v6/causal/counterfactual",
            json={
                "observation": {
                    "nozzle_temperature": 200,
                    "print_speed": 50,
                    "defect_rate": 0.05,
                },
                "intervention": {
                    "nozzle_temperature": 210,
                },
                "target": "defect_rate",
            },
        )
        assert response.status_code == 200

        data = json.loads(response.data)
        assert data["success"] == True
        assert "result" in data
        assert "counterfactual_value" in data["result"]

    def test_root_cause_analysis(self, client):
        """Test root cause analysis."""
        response = client.post(
            "/api/v6/causal/root-cause",
            json={
                "defect_type": "layer_separation",
                "context": {
                    "printer_id": "prusa-001",
                    "material": "PLA",
                },
            },
        )
        assert response.status_code == 200

        data = json.loads(response.data)
        assert data["success"] == True
        assert "root_causes" in data

    def test_get_explanation(self, client):
        """Test getting decision explanation."""
        response = client.get("/api/v6/causal/explain/decision-001")
        assert response.status_code == 200

        data = json.loads(response.data)
        assert data["success"] == True
        assert "explanation" in data


# ============================================
# Agent Orchestration Route Tests
# ============================================

class TestOrchestrationRoutes:
    """Tests for agent orchestration routes."""

    def test_get_agent_registry(self, client):
        """Test getting agent registry."""
        response = client.get("/api/v6/agents/registry")
        assert response.status_code == 200

        data = json.loads(response.data)
        assert data["success"] == True
        assert "agents" in data
        assert len(data["agents"]) > 0

    def test_get_messages(self, client):
        """Test getting message bus messages."""
        response = client.get("/api/v6/agents/messages")
        assert response.status_code == 200

        data = json.loads(response.data)
        assert data["success"] == True
        assert "messages" in data

    def test_post_message(self, client):
        """Test posting to message bus."""
        response = client.post(
            "/api/v6/agents/messages",
            json={
                "from_agent": "quality_agent",
                "to_agent": "scheduling_agent",
                "message_type": "quality_alert",
                "payload": {"defect_detected": True},
            },
        )
        assert response.status_code == 200

        data = json.loads(response.data)
        assert data["success"] == True
        assert "message_id" in data

    def test_initiate_consensus(self, client):
        """Test initiating consensus decision."""
        response = client.post(
            "/api/v6/agents/consensus/initiate",
            json={
                "decision_type": "parameter_change",
                "proposal": {
                    "change": "increase_temperature",
                    "value": 215,
                },
                "participating_agents": ["quality", "scheduling", "maintenance"],
            },
        )
        assert response.status_code == 200

        data = json.loads(response.data)
        assert data["success"] == True
        assert "consensus" in data

    def test_create_plan(self, client):
        """Test creating HTN plan."""
        response = client.post(
            "/api/v6/agents/plan",
            json={
                "goal": "optimize_production",
                "constraints": {
                    "max_time": 3600,
                    "quality_threshold": 0.95,
                },
            },
        )
        assert response.status_code == 200

        data = json.loads(response.data)
        assert data["success"] == True
        assert "plan" in data
        assert "tasks" in data["plan"]


# ============================================
# Closed-Loop Learning Route Tests
# ============================================

class TestClosedLoopRoutes:
    """Tests for closed-loop learning routes."""

    def test_submit_feedback(self, client):
        """Test submitting production feedback."""
        response = client.post(
            "/api/v6/closed-loop/feedback",
            json={
                "model_id": "quality_predictor_v2",
                "prediction": {"quality_score": 0.92},
                "actual": {"quality_score": 0.88},
                "context": {
                    "printer_id": "prusa-001",
                    "material": "PLA",
                },
            },
        )
        assert response.status_code == 200

        data = json.loads(response.data)
        assert data["success"] == True
        assert "feedback_id" in data

    def test_get_drift_status(self, client):
        """Test getting drift detection status."""
        response = client.get("/api/v6/closed-loop/drift")
        assert response.status_code == 200

        data = json.loads(response.data)
        assert data["success"] == True
        assert "drift_status" in data

    def test_trigger_retrain(self, client):
        """Test triggering model retraining."""
        response = client.post(
            "/api/v6/closed-loop/retrain",
            json={
                "model_id": "quality_predictor_v2",
                "reason": "drift_detected",
            },
        )
        assert response.status_code == 200

        data = json.loads(response.data)
        assert data["success"] == True
        assert "job_id" in data

    def test_get_active_learning_queue(self, client):
        """Test getting active learning queue."""
        response = client.get("/api/v6/closed-loop/active-learning/queue")
        assert response.status_code == 200

        data = json.loads(response.data)
        assert data["success"] == True
        assert "samples" in data

    def test_get_healing_actions(self, client):
        """Test getting self-healing actions."""
        response = client.get("/api/v6/closed-loop/healing/actions")
        assert response.status_code == 200

        data = json.loads(response.data)
        assert data["success"] == True
        assert "actions" in data


# ============================================
# Generative Design Route Tests
# ============================================

class TestGenerativeRoutes:
    """Tests for generative design routes."""

    def test_create_design_space(self, client):
        """Test creating design space."""
        response = client.post(
            "/api/v6/generative/design-space",
            json={
                "name": "LEGO 2x4 Brick",
                "bounding_box": [[0, 0, 0], [31.8, 15.8, 9.6]],
                "preserve_regions": ["studs"],
                "symmetry_planes": ["XZ", "YZ"],
            },
        )
        assert response.status_code == 200

        data = json.loads(response.data)
        assert data["success"] == True
        assert "design_space" in data

    def test_start_optimization(self, client):
        """Test starting topology optimization."""
        response = client.post(
            "/api/v6/generative/optimize",
            json={
                "design_space_id": "ds-001",
                "optimization_type": "topology",
                "material": "PLA",
                "constraints": {
                    "max_stress": 40,
                    "min_safety_factor": 1.5,
                },
                "objectives": {
                    "minimize_mass": 0.7,
                    "maximize_strength": 0.3,
                },
            },
        )
        assert response.status_code == 200

        data = json.loads(response.data)
        assert data["success"] == True
        assert "job" in data

    def test_generate_lattice(self, client):
        """Test generating lattice structure."""
        response = client.post(
            "/api/v6/generative/lattice",
            json={
                "lattice_type": "gyroid",
                "density": 0.3,
                "cell_size": 5.0,
            },
        )
        assert response.status_code == 200

        data = json.loads(response.data)
        assert data["success"] == True
        assert "lattice" in data

    def test_get_lattice_types(self, client):
        """Test getting available lattice types."""
        response = client.get("/api/v6/generative/lattice/types")
        assert response.status_code == 200

        data = json.loads(response.data)
        assert data["success"] == True
        assert "types" in data
        assert len(data["types"]) > 0

    def test_optimize_lego_clutch(self, client):
        """Test LEGO clutch optimization."""
        response = client.post(
            "/api/v6/generative/lego/optimize-clutch",
            json={
                "target_clutch_force": 2.0,
                "tolerance": 0.1,
                "material": "PLA",
            },
        )
        assert response.status_code == 200

        data = json.loads(response.data)
        assert data["success"] == True
        assert "result" in data
        assert "optimized_parameters" in data["result"]

    def test_validate_lego_compatibility(self, client):
        """Test LEGO compatibility validation."""
        response = client.post(
            "/api/v6/generative/lego/validate",
            json={
                "design_id": "design-001",
                "official_specs": True,
            },
        )
        assert response.status_code == 200

        data = json.loads(response.data)
        assert data["success"] == True
        assert "validation" in data
        assert "compatible" in data["validation"]


# ============================================
# Research Route Tests
# ============================================

class TestResearchRoutes:
    """Tests for research platform routes."""

    def test_list_experiments(self, client):
        """Test listing experiments."""
        response = client.get("/api/v6/research/experiments")
        assert response.status_code == 200

        data = json.loads(response.data)
        assert data["success"] == True
        assert "experiments" in data

    def test_create_experiment(self, client):
        """Test creating experiment."""
        response = client.post(
            "/api/v6/research/experiments",
            json={
                "name": "Quality Prediction Test",
                "type": "quality",
                "params": {
                    "learning_rate": 0.001,
                    "batch_size": 32,
                },
                "tags": ["quality", "test"],
            },
        )
        assert response.status_code == 200

        data = json.loads(response.data)
        assert data["success"] == True
        assert "experiment" in data
        assert "id" in data["experiment"]

    def test_get_experiment(self, client):
        """Test getting experiment details."""
        response = client.get("/api/v6/research/experiments/EXP-2024-0156")
        assert response.status_code == 200

        data = json.loads(response.data)
        assert data["success"] == True
        assert "experiment" in data

    def test_log_metrics(self, client):
        """Test logging experiment metrics."""
        response = client.post(
            "/api/v6/research/experiments/EXP-001/metrics",
            json={
                "step": 100,
                "metrics": {
                    "loss": 0.05,
                    "accuracy": 0.95,
                },
            },
        )
        assert response.status_code == 200

        data = json.loads(response.data)
        assert data["success"] == True

    def test_list_models(self, client):
        """Test listing registered models."""
        response = client.get("/api/v6/research/models")
        assert response.status_code == 200

        data = json.loads(response.data)
        assert data["success"] == True
        assert "models" in data

    def test_compare_experiments(self, client):
        """Test comparing experiments."""
        response = client.post(
            "/api/v6/research/compare",
            json={
                "experiment_ids": ["EXP-0155", "EXP-0152"],
            },
        )
        assert response.status_code == 200

        data = json.loads(response.data)
        assert data["success"] == True
        assert "comparison" in data

    def test_power_analysis(self, client):
        """Test statistical power analysis."""
        response = client.post(
            "/api/v6/research/statistics/power-analysis",
            json={
                "effect_size": 0.5,
                "alpha": 0.05,
                "power": 0.8,
            },
        )
        assert response.status_code == 200

        data = json.loads(response.data)
        assert data["success"] == True
        assert "result" in data
        assert "required_sample_size" in data["result"]


# ============================================
# Action Approval Route Tests
# ============================================

class TestActionRoutes:
    """Tests for action approval routes."""

    def test_list_pending_actions(self, client):
        """Test listing pending actions."""
        response = client.get("/api/v6/actions/pending")
        assert response.status_code == 200

        data = json.loads(response.data)
        assert data["success"] == True
        assert "actions" in data
        assert "summary" in data

    def test_approve_action(self, client):
        """Test approving an action."""
        response = client.post(
            "/api/v6/actions/act-001/approve",
            json={
                "user": "operator",
            },
        )
        assert response.status_code == 200

        data = json.loads(response.data)
        assert data["success"] == True
        assert "result" in data
        assert data["result"]["status"] == "approved"

    def test_reject_action(self, client):
        """Test rejecting an action."""
        response = client.post(
            "/api/v6/actions/act-002/reject",
            json={
                "user": "operator",
                "reason": "Risk too high",
            },
        )
        assert response.status_code == 200

        data = json.loads(response.data)
        assert data["success"] == True
        assert data["result"]["status"] == "rejected"

    def test_get_action_history(self, client):
        """Test getting action history."""
        response = client.get("/api/v6/actions/history")
        assert response.status_code == 200

        data = json.loads(response.data)
        assert data["success"] == True
        assert "history" in data

    def test_get_approval_rules(self, client):
        """Test getting approval rules."""
        response = client.get("/api/v6/actions/rules")
        assert response.status_code == 200

        data = json.loads(response.data)
        assert data["success"] == True
        assert "rules" in data

    def test_update_approval_rules(self, client):
        """Test updating approval rules."""
        response = client.put(
            "/api/v6/actions/rules",
            json={
                "auto_approve_low_risk": True,
                "confidence_threshold": 0.9,
            },
        )
        assert response.status_code == 200

        data = json.loads(response.data)
        assert data["success"] == True

    def test_execute_direct(self, client):
        """Test direct action execution."""
        response = client.post(
            "/api/v6/actions/execute",
            json={
                "printer_id": "prusa-001",
                "gcode": ["G28", "M104 S200"],
                "bypass_approval": False,
            },
        )
        assert response.status_code == 200

        data = json.loads(response.data)
        assert data["success"] == True

    def test_rollback_action(self, client):
        """Test rolling back an action."""
        response = client.post("/api/v6/actions/act-001/rollback")
        assert response.status_code == 200

        data = json.loads(response.data)
        assert data["success"] == True
        assert data["result"]["status"] == "rolled_back"


# ============================================
# Health Check Tests
# ============================================

class TestHealthChecks:
    """Tests for health check endpoints."""

    def test_v5_health(self, client):
        """Test v5 health endpoint."""
        response = client.get("/api/v5/health")
        assert response.status_code == 200

        data = json.loads(response.data)
        assert data["status"] == "healthy"
        assert data["version"] == "5.0.0"

    def test_v6_health(self, client):
        """Test v6 health endpoint."""
        response = client.get("/api/v6/health")
        assert response.status_code == 200

        data = json.loads(response.data)
        assert data["status"] == "healthy"
        assert data["version"] == "6.0.0"
        assert "modules" in data
        assert "capabilities" in data


# ============================================
# Run tests
# ============================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
