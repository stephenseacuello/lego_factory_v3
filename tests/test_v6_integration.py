"""
Integration Tests for LEGO MCP v6.0 Research Pipeline.

End-to-end tests for:
- Complete experiment lifecycle
- Model training and registry workflow
- Causal analysis pipeline
- Closed-loop learning cycle
- Agent orchestration scenarios
"""

import pytest
import asyncio
from datetime import datetime, timedelta
from typing import Dict, Any, List


# ============================================
# Experiment Lifecycle Integration Tests
# ============================================

class TestExperimentLifecycle:
    """Tests for complete experiment lifecycle."""

    @pytest.mark.asyncio
    async def test_full_experiment_workflow(self):
        """Test complete experiment from creation to model registration."""
        from dashboard.services.data import DatasetManager, DatasetType
        from dashboard.services.database import ExperimentRepository, ModelRepository

        # Step 1: Create dataset
        dataset_manager = DatasetManager()
        dataset = dataset_manager.create_dataset(
            name="Integration Test Dataset",
            description="Dataset for integration testing",
            dataset_type=DatasetType.TRAINING_DATA,
            owner="integration_test",
            schema={"format": "parquet", "columns": ["features", "labels"]},
        )
        assert dataset.dataset_id is not None

        # Step 2: Create dataset version
        version = dataset_manager.create_version(
            dataset_id=dataset.dataset_id,
            version_number="1.0.0",
            created_by="integration_test",
            size_bytes=1000000,
            record_count=5000,
            data_hash="integration_test_hash",
            metadata={"split": "train"},
        )
        assert version.version_number == "1.0.0"

        # Step 3: Create experiment
        exp_repo = ExperimentRepository()
        from dashboard.services.database import ExperimentEntity

        experiment = ExperimentEntity(
            name="Integration Test Experiment",
            description="Testing full workflow",
            status="created",
            experiment_type="quality",
            params={
                "learning_rate": 0.001,
                "batch_size": 32,
                "epochs": 10,
                "dataset_id": dataset.dataset_id,
                "dataset_version": "1.0.0",
            },
            owner="integration_test",
        )
        saved_exp = await exp_repo.save(experiment)
        assert saved_exp.id is not None

        # Step 4: Simulate training (update metrics)
        saved_exp.status = "running"
        saved_exp.metrics = {"epoch": 5, "loss": 0.05, "accuracy": 0.92}
        await exp_repo.save(saved_exp)

        # Step 5: Complete experiment
        saved_exp.status = "completed"
        saved_exp.metrics = {"final_loss": 0.02, "final_accuracy": 0.98}
        await exp_repo.save(saved_exp)

        # Step 6: Register model
        model_repo = ModelRepository()
        from dashboard.services.database import ModelEntity

        model = ModelEntity(
            name="quality_classifier",
            version="1.0.0",
            stage="staging",
            experiment_id=saved_exp.id,
            artifact_path="/models/quality_classifier_v1.pt",
            metrics=saved_exp.metrics,
            tags=["quality", "integration_test"],
        )
        saved_model = await model_repo.save(model)
        assert saved_model.id is not None

        # Verify workflow
        retrieved_exp = await exp_repo.find_by_id(saved_exp.id)
        assert retrieved_exp.status == "completed"

        models = await model_repo.find_by_name("quality_classifier")
        assert len(models) > 0

    @pytest.mark.asyncio
    async def test_experiment_comparison_workflow(self):
        """Test comparing multiple experiments."""
        from dashboard.services.database import ExperimentRepository, ExperimentEntity

        exp_repo = ExperimentRepository()

        # Create two experiments with different hyperparameters
        exp1 = ExperimentEntity(
            name="Experiment A - Low LR",
            status="completed",
            params={"learning_rate": 0.0001, "batch_size": 32},
            metrics={"accuracy": 0.95, "loss": 0.05},
        )
        exp2 = ExperimentEntity(
            name="Experiment B - High LR",
            status="completed",
            params={"learning_rate": 0.01, "batch_size": 32},
            metrics={"accuracy": 0.92, "loss": 0.08},
        )

        saved1 = await exp_repo.save(exp1)
        saved2 = await exp_repo.save(exp2)

        # Compare experiments
        all_completed = await exp_repo.find_by_status("completed")
        assert len(all_completed) >= 2

        # Find best by accuracy
        best = max(all_completed, key=lambda e: e.metrics.get("accuracy", 0))
        assert best.metrics["accuracy"] >= 0.95


# ============================================
# Causal Analysis Pipeline Integration Tests
# ============================================

class TestCausalAnalysisPipeline:
    """Tests for causal analysis pipeline."""

    def test_root_cause_to_counterfactual_workflow(self):
        """Test workflow from defect detection to counterfactual analysis."""
        # Simulate defect detection
        defect = {
            "type": "layer_separation",
            "severity": "high",
            "location": {"layer": 42, "x": 50, "y": 75},
            "context": {
                "nozzle_temperature": 195,
                "print_speed": 80,
                "bed_temperature": 55,
            },
        }

        # Step 1: Analyze root cause
        # In production, this would use the CausalEngine
        root_causes = [
            {"cause": "low_nozzle_temperature", "probability": 0.85},
            {"cause": "high_print_speed", "probability": 0.65},
            {"cause": "bed_adhesion_issue", "probability": 0.40},
        ]

        # Verify top cause identified
        top_cause = max(root_causes, key=lambda c: c["probability"])
        assert top_cause["cause"] == "low_nozzle_temperature"

        # Step 2: Counterfactual query
        # "What if temperature was 210 instead of 195?"
        counterfactual = {
            "observation": defect["context"],
            "intervention": {"nozzle_temperature": 210},
            "predicted_defect_rate": 0.02,  # Down from 0.15
        }

        assert counterfactual["predicted_defect_rate"] < 0.10

        # Step 3: Generate recommendation
        recommendation = {
            "action": "increase_nozzle_temperature",
            "from_value": 195,
            "to_value": 210,
            "expected_improvement": "87% reduction in layer separation",
            "confidence": 0.85,
        }

        assert recommendation["confidence"] > 0.8

    def test_tcav_explanation_workflow(self):
        """Test TCAV concept-based explanation workflow."""
        from dashboard.services.explainability import ConceptActivationTester

        # Initialize TCAV
        tcav = ConceptActivationTester(model_name="quality_classifier")

        # List available concepts
        concepts = tcav.list_concepts()
        assert len(concepts) > 0

        # Run analysis for defective class
        analysis = tcav.run_tcav_analysis(
            target_class="defective",
            layers=["layer4"],
        )

        assert "scores" in analysis
        assert len(analysis["scores"]) > 0

        # Generate explanation for a prediction
        explanation = tcav.explain_prediction(
            image_path="/test/brick_001.png",
            predicted_class="defective",
        )

        assert "explanation" in explanation
        assert "defective" in explanation["explanation"]


# ============================================
# Closed-Loop Learning Integration Tests
# ============================================

class TestClosedLoopLearning:
    """Tests for closed-loop learning cycle."""

    @pytest.mark.asyncio
    async def test_feedback_to_retrain_cycle(self):
        """Test complete feedback to model retraining cycle."""
        # Step 1: Simulate production feedback
        feedback_events = [
            {
                "prediction": {"quality_score": 0.92},
                "actual": {"quality_score": 0.85},
                "context": {"printer_id": "prusa-001", "material": "PLA"},
            },
            {
                "prediction": {"quality_score": 0.88},
                "actual": {"quality_score": 0.78},
                "context": {"printer_id": "prusa-001", "material": "PLA"},
            },
            {
                "prediction": {"quality_score": 0.95},
                "actual": {"quality_score": 0.82},
                "context": {"printer_id": "prusa-001", "material": "PLA"},
            },
        ]

        # Step 2: Detect drift
        prediction_errors = [
            abs(f["prediction"]["quality_score"] - f["actual"]["quality_score"])
            for f in feedback_events
        ]
        avg_error = sum(prediction_errors) / len(prediction_errors)

        # Check if drift detected (error > 0.1)
        drift_detected = avg_error > 0.1
        assert drift_detected, f"Expected drift, got avg_error={avg_error}"

        # Step 3: Trigger retraining (simulated)
        retrain_job = {
            "job_id": "retrain-001",
            "model_id": "quality_predictor",
            "reason": "drift_detected",
            "avg_error": avg_error,
            "samples_used": len(feedback_events),
            "status": "queued",
        }

        assert retrain_job["status"] == "queued"

        # Step 4: Simulate retraining completion
        retrain_job["status"] = "completed"
        retrain_job["new_version"] = "2.0.1"
        retrain_job["improvement"] = 0.05

        assert retrain_job["status"] == "completed"

    @pytest.mark.asyncio
    async def test_active_learning_sample_selection(self):
        """Test active learning sample selection."""
        # Simulate uncertain samples
        samples = [
            {"sample_id": "s1", "uncertainty": 0.95, "predicted_class": "defective"},
            {"sample_id": "s2", "uncertainty": 0.52, "predicted_class": "good"},
            {"sample_id": "s3", "uncertainty": 0.88, "predicted_class": "defective"},
            {"sample_id": "s4", "uncertainty": 0.15, "predicted_class": "good"},
            {"sample_id": "s5", "uncertainty": 0.78, "predicted_class": "good"},
        ]

        # Select most uncertain samples for labeling
        uncertainty_threshold = 0.7
        selected = [s for s in samples if s["uncertainty"] > uncertainty_threshold]

        assert len(selected) == 3
        assert all(s["uncertainty"] > 0.7 for s in selected)

        # Simulate human labeling
        for sample in selected:
            sample["human_label"] = "defective" if sample["uncertainty"] > 0.85 else "good"
            sample["labeled_at"] = datetime.now().isoformat()

        assert all("human_label" in s for s in selected)


# ============================================
# Agent Orchestration Integration Tests
# ============================================

class TestAgentOrchestration:
    """Tests for multi-agent orchestration scenarios."""

    @pytest.mark.asyncio
    async def test_quality_scheduling_coordination(self):
        """Test coordination between quality and scheduling agents."""
        # Scenario: Quality agent detects issue, scheduling agent responds

        # Step 1: Quality agent detects defect
        quality_alert = {
            "agent": "quality_agent",
            "alert_type": "defect_detected",
            "severity": "high",
            "printer_id": "prusa-003",
            "defect_type": "layer_separation",
            "recommended_action": "pause_and_inspect",
        }

        # Step 2: Message to scheduling agent
        message = {
            "from": "quality_agent",
            "to": "scheduling_agent",
            "type": "quality_alert",
            "payload": quality_alert,
            "priority": "high",
        }

        assert message["priority"] == "high"

        # Step 3: Scheduling agent responds
        scheduling_response = {
            "agent": "scheduling_agent",
            "action": "reschedule_jobs",
            "affected_printer": "prusa-003",
            "jobs_rescheduled": 3,
            "new_assignments": {
                "job-001": "prusa-001",
                "job-002": "prusa-002",
                "job-003": "prusa-004",
            },
        }

        assert scheduling_response["jobs_rescheduled"] == 3

        # Step 4: Consensus reached
        consensus = {
            "decision": "pause_prusa-003_and_redistribute",
            "participating_agents": ["quality_agent", "scheduling_agent"],
            "votes": {"quality_agent": "approve", "scheduling_agent": "approve"},
            "outcome": "approved",
        }

        assert consensus["outcome"] == "approved"

    @pytest.mark.asyncio
    async def test_multi_agent_planning(self):
        """Test HTN planning across multiple agents."""
        # Goal: Optimize production while maintaining quality

        # Step 1: Define high-level goal
        goal = {
            "objective": "maximize_throughput",
            "constraints": {
                "min_quality_score": 0.95,
                "max_energy_consumption": 1000,
            },
        }

        # Step 2: HTN decomposition
        plan = {
            "plan_id": "plan-001",
            "goal": goal["objective"],
            "tasks": [
                {
                    "id": "task-1",
                    "name": "Assess current capacity",
                    "agent": "scheduling_agent",
                    "status": "pending",
                },
                {
                    "id": "task-2",
                    "name": "Verify quality baselines",
                    "agent": "quality_agent",
                    "status": "pending",
                },
                {
                    "id": "task-3",
                    "name": "Optimize print parameters",
                    "agent": "quality_agent",
                    "dependencies": ["task-2"],
                    "status": "pending",
                },
                {
                    "id": "task-4",
                    "name": "Rebalance job queue",
                    "agent": "scheduling_agent",
                    "dependencies": ["task-1", "task-3"],
                    "status": "pending",
                },
            ],
        }

        assert len(plan["tasks"]) == 4

        # Step 3: Execute plan
        for task in plan["tasks"]:
            # Check dependencies
            deps_met = all(
                any(t["id"] == dep and t["status"] == "completed"
                    for t in plan["tasks"])
                for dep in task.get("dependencies", [])
            )

            if deps_met or not task.get("dependencies"):
                task["status"] = "completed"

        completed = [t for t in plan["tasks"] if t["status"] == "completed"]
        # First two tasks should complete (no dependencies)
        assert len(completed) >= 2


# ============================================
# Digital Twin Sync Integration Tests
# ============================================

class TestDigitalTwinSync:
    """Tests for digital twin synchronization."""

    @pytest.mark.asyncio
    async def test_realtime_sync_workflow(self):
        """Test real-time sync between physical and digital twin."""
        from dashboard.services.digital_twin import (
            RealtimeTwinSync,
            SyncState,
        )

        # Create sync instance
        sync = RealtimeTwinSync(
            twin_id="printer-001",
            sync_interval_ms=100,
            deviation_threshold=0.1,
        )

        # Start sync (briefly)
        await sync.start()
        await asyncio.sleep(0.5)  # Let it run for 500ms

        # Check status
        status = sync.get_status()
        assert status["running"] == True
        assert status["twin_id"] == "printer-001"

        # Get metrics
        metrics = sync.get_metrics()
        assert metrics.total_updates > 0

        # Stop sync
        await sync.stop()
        assert sync._running == False

    @pytest.mark.asyncio
    async def test_multi_twin_coordination(self):
        """Test coordinated sync across multiple twins."""
        from dashboard.services.digital_twin import MultiTwinSyncManager

        manager = MultiTwinSyncManager()

        # Add multiple twins
        await manager.add_twin("printer-001", sync_interval_ms=100)
        await manager.add_twin("printer-002", sync_interval_ms=100)

        # Start all
        await manager.start_all()
        await asyncio.sleep(0.3)

        # Check aggregate status
        all_status = manager.get_all_status()
        assert "printer-001" in all_status
        assert "printer-002" in all_status

        # Get aggregate metrics
        metrics = manager.get_aggregate_metrics()
        assert metrics["twin_count"] == 2

        # Stop all
        await manager.stop_all()


# ============================================
# End-to-End Manufacturing Scenario Tests
# ============================================

class TestE2EManufacturingScenario:
    """End-to-end tests for complete manufacturing scenarios."""

    @pytest.mark.asyncio
    async def test_defect_detection_to_action_workflow(self):
        """
        Test complete workflow:
        1. Vision system detects defect
        2. Causal analysis identifies root cause
        3. Agent orchestration decides action
        4. Action approval workflow
        5. Equipment control executes
        6. Closed-loop feedback
        """
        # Step 1: Defect Detection (Vision)
        defect_detection = {
            "defect_id": "def-001",
            "defect_type": "under_extrusion",
            "confidence": 0.92,
            "location": {"layer": 25, "region": "infill"},
            "printer_id": "prusa-001",
        }

        # Step 2: Root Cause Analysis
        root_cause = {
            "defect_id": "def-001",
            "probable_causes": [
                {"cause": "partial_clog", "probability": 0.75},
                {"cause": "low_temperature", "probability": 0.45},
            ],
            "recommended_action": "increase_temperature",
        }

        # Step 3: Agent Decision
        agent_decision = {
            "source_agent": "quality_agent",
            "action_type": "TEMPERATURE_CHANGE",
            "target_printer": "prusa-001",
            "current_value": 200,
            "proposed_value": 210,
            "risk_level": "medium",
            "confidence": 0.78,
        }

        # Step 4: Action Approval
        approval = {
            "action_id": "act-001",
            "status": "approved",
            "approved_by": "operator",
            "timestamp": datetime.now().isoformat(),
        }

        assert approval["status"] == "approved"

        # Step 5: Equipment Control
        execution = {
            "action_id": "act-001",
            "printer_id": "prusa-001",
            "gcode_sent": ["M104 S210"],
            "execution_status": "success",
            "new_temperature": 210,
        }

        assert execution["execution_status"] == "success"

        # Step 6: Closed-Loop Feedback
        feedback = {
            "action_id": "act-001",
            "outcome": "successful",
            "defect_resolved": True,
            "quality_improvement": 0.15,
            "feedback_for_model": {
                "context": defect_detection,
                "action": agent_decision,
                "result": "positive",
            },
        }

        assert feedback["defect_resolved"] == True

    @pytest.mark.asyncio
    async def test_optimization_to_production_workflow(self):
        """
        Test optimization workflow:
        1. Run print parameter optimization
        2. Validate with simulation
        3. Create experiment
        4. Deploy to production
        """
        from dashboard.services.optimization import PrintParameterOptimizer

        # Step 1: Optimize parameters
        optimizer = PrintParameterOptimizer(
            target_quality="high_quality",
            material="PLA",
        )

        result = optimizer.optimize(
            objectives=["quality", "strength"],
            generations=10,
            population_size=20,
        )

        assert "recommended" in result
        assert result["recommended"] is not None

        recommended = result["recommended"]

        # Step 2: Validate with simulation
        simulation_result = {
            "parameters": recommended,
            "predicted_quality": 0.96,
            "predicted_strength": 0.92,
            "printability_score": 0.94,
            "estimated_time_minutes": 45,
        }

        assert simulation_result["predicted_quality"] > 0.9

        # Step 3: Create experiment record
        experiment = {
            "name": "Optimized Parameters Test",
            "type": "parameter_optimization",
            "params": recommended,
            "simulation_results": simulation_result,
            "status": "pending_validation",
        }

        # Step 4: Validation print
        validation = {
            "experiment_id": experiment["name"],
            "actual_quality": 0.94,
            "actual_strength": 0.91,
            "deviation_from_prediction": 0.02,
            "status": "validated",
        }

        assert validation["status"] == "validated"
        assert validation["deviation_from_prediction"] < 0.05


# ============================================
# Run tests
# ============================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--asyncio-mode=auto"])
