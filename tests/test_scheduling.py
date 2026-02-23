"""
Scheduling Module Tests.

Tests for Phase 2 Advanced Scheduling components:
- Quantum-Inspired Optimization (QAOA, VQE)
- Deep Reinforcement Learning (PPO, SAC, TD3)
- Multi-objective Optimization (NSGA-II/III)
"""

import unittest
import sys
import os
from datetime import datetime, timedelta
from typing import Dict, Any, List

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestQAOAScheduler(unittest.TestCase):
    """Tests for Quantum Approximate Optimization Algorithm scheduler."""

    def setUp(self):
        """Set up test fixtures."""
        from dashboard.services.scheduling.quantum.qaoa_scheduler import (
            QAOAConfig, QAOAScheduler, ManufacturingQAOA
        )
        self.QAOAConfig = QAOAConfig
        self.QAOAScheduler = QAOAScheduler
        self.ManufacturingQAOA = ManufacturingQAOA

    def test_qaoa_config(self):
        """Test QAOA configuration."""
        config = self.QAOAConfig()

        self.assertGreater(config.num_layers, 0)
        self.assertGreater(config.max_iterations, 0)

    def test_qaoa_scheduler_creation(self):
        """Test QAOA scheduler creation."""
        scheduler = self.QAOAScheduler()

        self.assertIsNotNone(scheduler)

    def test_qaoa_cost_hamiltonian(self):
        """Test cost Hamiltonian construction."""
        scheduler = self.QAOAScheduler()

        # Simple 3-job problem
        jobs = [
            {"id": 1, "duration": 10, "deadline": 20},
            {"id": 2, "duration": 15, "deadline": 25},
            {"id": 3, "duration": 8, "deadline": 30},
        ]

        hamiltonian = scheduler.build_cost_hamiltonian(jobs)

        self.assertIsNotNone(hamiltonian)
        self.assertIn("terms", hamiltonian)

    def test_qaoa_optimization(self):
        """Test QAOA optimization run."""
        config = self.QAOAConfig(max_iterations=10)
        scheduler = self.QAOAScheduler(config)

        jobs = [
            {"id": 1, "duration": 10},
            {"id": 2, "duration": 15},
            {"id": 3, "duration": 8},
        ]

        result = scheduler.optimize(jobs, num_machines=2)

        self.assertIn("schedule", result)
        self.assertIn("cost", result)
        self.assertIn("iterations", result)

    def test_manufacturing_qaoa(self):
        """Test manufacturing-specific QAOA."""
        qaoa = self.ManufacturingQAOA()

        # Create manufacturing jobs
        jobs = [
            {"id": "J1", "part": "bracket", "duration": 30, "priority": 1},
            {"id": "J2", "part": "housing", "duration": 45, "priority": 2},
            {"id": "J3", "part": "cover", "duration": 20, "priority": 1},
        ]

        result = qaoa.schedule_production(
            jobs=jobs,
            machines=["M1", "M2"],
            objective="minimize_makespan"
        )

        self.assertIn("assignments", result)
        self.assertIn("makespan", result)


class TestVQEScheduler(unittest.TestCase):
    """Tests for Variational Quantum Eigensolver scheduler."""

    def setUp(self):
        """Set up test fixtures."""
        from dashboard.services.scheduling.quantum.qaoa_scheduler import (
            VQEScheduler, VQEConfig
        )
        self.VQEScheduler = VQEScheduler
        self.VQEConfig = VQEConfig

    def test_vqe_ansatz(self):
        """Test VQE ansatz construction."""
        scheduler = self.VQEScheduler()

        ansatz = scheduler.build_ansatz(num_qubits=4)

        self.assertIsNotNone(ansatz)
        self.assertIn("depth", ansatz)

    def test_vqe_optimization(self):
        """Test VQE optimization."""
        config = self.VQEConfig(max_iterations=10)
        scheduler = self.VQEScheduler(config)

        # Simple scheduling problem
        problem = {
            "num_jobs": 4,
            "num_machines": 2,
            "durations": [10, 15, 8, 12],
        }

        result = scheduler.solve(problem)

        self.assertIn("solution", result)
        self.assertIn("energy", result)


class TestSimulatedQuantum(unittest.TestCase):
    """Tests for classical quantum simulation."""

    def setUp(self):
        """Set up test fixtures."""
        from dashboard.services.scheduling.quantum.simulated_quantum import (
            SimulatedQuantumAnnealing, QuantumInspiredOptimizer
        )
        self.SimulatedQuantumAnnealing = SimulatedQuantumAnnealing
        self.QuantumInspiredOptimizer = QuantumInspiredOptimizer

    def test_simulated_annealing(self):
        """Test simulated quantum annealing."""
        annealer = self.SimulatedQuantumAnnealing()

        # QUBO problem
        Q = {
            (0, 0): -1, (1, 1): -1, (2, 2): -1,
            (0, 1): 2, (1, 2): 2,
        }

        result = annealer.anneal(Q, num_reads=100)

        self.assertIn("best_solution", result)
        self.assertIn("best_energy", result)
        self.assertIn("samples", result)

    def test_quantum_inspired_optimizer(self):
        """Test quantum-inspired optimizer."""
        optimizer = self.QuantumInspiredOptimizer()

        # Objective function
        def objective(x):
            return sum(xi ** 2 for xi in x)

        result = optimizer.optimize(
            objective=objective,
            dimensions=5,
            bounds=(-10, 10)
        )

        self.assertIn("solution", result)
        self.assertIn("value", result)
        self.assertLess(result["value"], 1.0)  # Should find near-zero


class TestRLDispatcher(unittest.TestCase):
    """Tests for RL-based job dispatching."""

    def setUp(self):
        """Set up test fixtures."""
        from dashboard.services.scheduling.rl_dispatcher import (
            PPOAgent, SACAgent, TD3Agent, RLDispatcher
        )
        self.PPOAgent = PPOAgent
        self.SACAgent = SACAgent
        self.TD3Agent = TD3Agent
        self.RLDispatcher = RLDispatcher

    def test_ppo_agent_creation(self):
        """Test PPO agent creation."""
        agent = self.PPOAgent(
            state_dim=10,
            action_dim=4
        )

        self.assertIsNotNone(agent)

    def test_ppo_action_selection(self):
        """Test PPO action selection."""
        agent = self.PPOAgent(state_dim=10, action_dim=4)

        state = [0.1] * 10
        action = agent.select_action(state)

        self.assertIsInstance(action, int)
        self.assertGreaterEqual(action, 0)
        self.assertLess(action, 4)

    def test_sac_agent(self):
        """Test SAC (Soft Actor-Critic) agent."""
        agent = self.SACAgent(state_dim=10, action_dim=4)

        state = [0.1] * 10
        action = agent.select_action(state, deterministic=True)

        self.assertIsNotNone(action)

    def test_td3_agent(self):
        """Test TD3 (Twin Delayed DDPG) agent."""
        agent = self.TD3Agent(state_dim=10, action_dim=4)

        state = [0.1] * 10
        action = agent.select_action(state)

        self.assertIsNotNone(action)

    def test_rl_dispatcher_training(self):
        """Test RL dispatcher training step."""
        dispatcher = self.RLDispatcher(algorithm="PPO")

        # Create environment step
        state = [0.5] * 10
        action = dispatcher.dispatch(state)
        reward = 1.0
        next_state = [0.6] * 10
        done = False

        result = dispatcher.train_step(state, action, reward, next_state, done)

        self.assertIn("loss", result)

    def test_dispatcher_policy(self):
        """Test dispatcher policy evaluation."""
        dispatcher = self.RLDispatcher(algorithm="PPO")

        # Evaluate current policy
        state = {
            "queue_lengths": [5, 3, 8],
            "machine_states": ["idle", "busy", "idle"],
            "time": 100,
        }

        action = dispatcher.get_dispatch_decision(state)

        self.assertIn("selected_machine", action)
        self.assertIn("confidence", action)


class TestNSGAScheduler(unittest.TestCase):
    """Tests for NSGA-II/III multi-objective optimization."""

    def setUp(self):
        """Set up test fixtures."""
        from dashboard.services.scheduling.nsga2_scheduler import (
            NSGA2Scheduler, NSGA3Scheduler, MOEADScheduler
        )
        self.NSGA2Scheduler = NSGA2Scheduler
        self.NSGA3Scheduler = NSGA3Scheduler
        self.MOEADScheduler = MOEADScheduler

    def test_nsga2_creation(self):
        """Test NSGA-II scheduler creation."""
        scheduler = self.NSGA2Scheduler(
            population_size=50,
            num_generations=10
        )

        self.assertIsNotNone(scheduler)

    def test_nsga2_optimization(self):
        """Test NSGA-II multi-objective optimization."""
        scheduler = self.NSGA2Scheduler(
            population_size=20,
            num_generations=5
        )

        jobs = [
            {"id": 1, "duration": 10, "energy": 5},
            {"id": 2, "duration": 15, "energy": 8},
            {"id": 3, "duration": 8, "energy": 3},
        ]

        result = scheduler.optimize(
            jobs=jobs,
            objectives=["minimize_makespan", "minimize_energy"]
        )

        self.assertIn("pareto_front", result)
        self.assertIn("solutions", result)
        self.assertGreater(len(result["pareto_front"]), 0)

    def test_nsga2_crowding_distance(self):
        """Test crowding distance calculation."""
        scheduler = self.NSGA2Scheduler()

        solutions = [
            {"makespan": 100, "energy": 50},
            {"makespan": 80, "energy": 70},
            {"makespan": 120, "energy": 30},
        ]

        distances = scheduler.calculate_crowding_distance(solutions)

        self.assertEqual(len(distances), 3)

    def test_nsga3_reference_points(self):
        """Test NSGA-III reference point generation."""
        scheduler = self.NSGA3Scheduler(num_objectives=3)

        ref_points = scheduler.generate_reference_points(divisions=4)

        self.assertGreater(len(ref_points), 0)

    def test_moead_decomposition(self):
        """Test MOEA/D decomposition approach."""
        scheduler = self.MOEADScheduler(
            num_objectives=2,
            neighborhood_size=5
        )

        # Test weight vector generation
        weights = scheduler.generate_weight_vectors(num_vectors=20)

        self.assertEqual(len(weights), 20)


class TestSchedulingIntegration(unittest.TestCase):
    """Integration tests for scheduling module."""

    def test_quantum_vs_classical_comparison(self):
        """Compare quantum-inspired vs classical scheduling."""
        from dashboard.services.scheduling.quantum.qaoa_scheduler import ManufacturingQAOA
        from dashboard.services.scheduling.nsga2_scheduler import NSGA2Scheduler

        jobs = [
            {"id": f"J{i}", "duration": 10 + i * 5, "priority": i % 3}
            for i in range(5)
        ]

        # Quantum-inspired
        qaoa = ManufacturingQAOA()
        qaoa_result = qaoa.schedule_production(
            jobs=jobs,
            machines=["M1", "M2"],
            objective="minimize_makespan"
        )

        # Classical NSGA-II
        nsga = NSGA2Scheduler(population_size=20, num_generations=10)
        nsga_result = nsga.optimize(
            jobs=jobs,
            objectives=["minimize_makespan"]
        )

        # Both should produce valid schedules
        self.assertIn("makespan", qaoa_result)
        self.assertIn("solutions", nsga_result)

    def test_rl_curriculum_learning(self):
        """Test curriculum learning for RL dispatcher."""
        from dashboard.services.scheduling.rl_dispatcher import RLDispatcher

        dispatcher = RLDispatcher(algorithm="PPO")

        # Start with simple problems
        simple_state = [0.1] * 10
        dispatcher.dispatch(simple_state)

        # Progress to complex problems
        complex_state = [0.5] * 10
        action = dispatcher.dispatch(complex_state)

        self.assertIsNotNone(action)


if __name__ == "__main__":
    unittest.main()
