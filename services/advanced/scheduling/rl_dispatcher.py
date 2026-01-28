"""
RL Dispatcher - Reinforcement Learning for Real-Time Dispatching

LegoMCP World-Class Manufacturing System v5.0
Phase 12: Advanced Scheduling Algorithms

Uses Deep Q-Network (DQN) or PPO for real-time dispatching decisions.

State: Machine status, queue lengths, slack times, current time
Actions: Dispatching rules (SPT, EDD, SLACK, FIFO, CR, etc.)
Reward: Tardiness reduction, utilization, quality events
"""

import logging
import pickle
import random
from abc import ABC, abstractmethod
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from uuid import uuid4

import numpy as np

try:
    import torch
    import torch.nn as nn
    import torch.optim as optim
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False
    torch = nn = optim = None

from .scheduler_factory import (
    BaseScheduler, Schedule, ScheduledOperation, ScheduleStatus,
    SchedulingProblem, SchedulerType, SchedulerFactory,
    Job, Operation, Machine
)
from .objectives import ObjectiveCalculator

logger = logging.getLogger(__name__)


class DispatchRule(str, Enum):
    """Available dispatching rules."""
    SPT = "spt"      # Shortest Processing Time
    LPT = "lpt"      # Longest Processing Time
    EDD = "edd"      # Earliest Due Date
    SLACK = "slack"  # Minimum Slack Time
    FIFO = "fifo"    # First In First Out
    CR = "cr"        # Critical Ratio
    RANDOM = "random"
    WEIGHTED = "weighted"  # Weighted combination


@dataclass
class DispatchState:
    """
    State representation for RL dispatcher.

    Captures the current state of the shop floor for decision-making.
    """
    current_time: float
    machine_states: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    queue_lengths: Dict[str, int] = field(default_factory=dict)
    pending_operations: List[Dict[str, Any]] = field(default_factory=list)

    # Derived features
    num_pending_jobs: int = 0
    avg_slack: float = 0.0
    min_slack: float = float('inf')
    max_urgency: float = 0.0
    avg_utilization: float = 0.0

    def to_vector(self, num_machines: int = 10) -> np.ndarray:
        """Convert state to fixed-size feature vector."""
        features = []

        # Time features
        features.append(self.current_time / 480.0)  # Normalized to 8-hour shift

        # Machine features (pad to num_machines)
        for i in range(num_machines):
            machine_id = list(self.machine_states.keys())[i] if i < len(self.machine_states) else None
            if machine_id:
                state = self.machine_states[machine_id]
                features.append(1.0 if state.get('available', True) else 0.0)
                features.append(state.get('remaining_time', 0) / 60.0)  # Normalized
            else:
                features.append(1.0)  # Available
                features.append(0.0)  # No remaining time

        # Queue features
        for i in range(num_machines):
            machine_id = list(self.queue_lengths.keys())[i] if i < len(self.queue_lengths) else None
            if machine_id:
                features.append(min(self.queue_lengths[machine_id] / 10.0, 1.0))
            else:
                features.append(0.0)

        # Aggregate features
        features.append(self.num_pending_jobs / 50.0)  # Normalized
        features.append(max(0, min(1, self.avg_slack / 100.0)))
        features.append(max(0, min(1, self.min_slack / 100.0)) if self.min_slack != float('inf') else 1.0)
        features.append(self.max_urgency)
        features.append(self.avg_utilization)

        return np.array(features, dtype=np.float32)

    @classmethod
    def from_problem(cls, problem: SchedulingProblem, schedule: Schedule, current_time: float) -> 'DispatchState':
        """Create state from current problem and partial schedule."""
        state = cls(current_time=current_time)

        # Build machine states
        for machine in problem.machines:
            current_op = None
            remaining = 0.0

            for op in schedule.get_operations_for_machine(machine.machine_id):
                if op.start_time <= current_time < op.end_time:
                    current_op = op
                    remaining = op.end_time - current_time
                    break

            state.machine_states[machine.machine_id] = {
                'available': current_op is None,
                'remaining_time': remaining,
                'current_op': current_op.operation_id if current_op else None,
            }

        # Count queue lengths (pending operations per machine)
        scheduled_ops = {op.operation_id for op in schedule.operations}
        all_ops = problem.get_all_operations()

        for machine in problem.machines:
            count = 0
            for op in all_ops:
                if op.operation_id not in scheduled_ops:
                    if machine.machine_id in op.eligible_machines:
                        count += 1
            state.queue_lengths[machine.machine_id] = count

        # Pending operations
        for job in problem.jobs:
            for op in job.operations:
                if op.operation_id not in scheduled_ops:
                    state.pending_operations.append({
                        'operation_id': op.operation_id,
                        'job_id': job.job_id,
                        'due_date': job.due_date,
                        'priority': job.priority,
                        'processing_times': op.processing_times,
                    })

        # Aggregate features
        state.num_pending_jobs = len(set(op['job_id'] for op in state.pending_operations))

        if state.pending_operations and any(op['due_date'] for op in state.pending_operations):
            slacks = []
            for op in state.pending_operations:
                if op['due_date']:
                    remaining_time = min(op['processing_times'].values()) if op['processing_times'] else 0
                    slack = op['due_date'] - current_time - remaining_time
                    slacks.append(slack)

            if slacks:
                state.avg_slack = sum(slacks) / len(slacks)
                state.min_slack = min(slacks)
                state.max_urgency = 1.0 / (1.0 + max(0, state.min_slack))

        # Utilization
        if problem.machines:
            busy = sum(1 for m_id, s in state.machine_states.items() if not s['available'])
            state.avg_utilization = busy / len(problem.machines)

        return state


if TORCH_AVAILABLE:
    class DQNNetwork(nn.Module):
        """Deep Q-Network for dispatching decisions."""

        def __init__(self, state_dim: int, action_dim: int, hidden_dim: int = 128):
            super().__init__()
            self.fc1 = nn.Linear(state_dim, hidden_dim)
            self.fc2 = nn.Linear(hidden_dim, hidden_dim)
            self.fc3 = nn.Linear(hidden_dim, action_dim)

        def forward(self, x):
            x = torch.relu(self.fc1(x))
            x = torch.relu(self.fc2(x))
            return self.fc3(x)
else:
    class DQNNetwork:
        """Placeholder when PyTorch not available."""
        def __init__(self, *args, **kwargs):
            pass


@dataclass
class Experience:
    """Experience tuple for replay buffer."""
    state: np.ndarray
    action: int
    reward: float
    next_state: np.ndarray
    done: bool


class ReplayBuffer:
    """Experience replay buffer for DQN training."""

    def __init__(self, capacity: int = 10000):
        self.buffer = deque(maxlen=capacity)

    def push(self, experience: Experience) -> None:
        """Add experience to buffer."""
        self.buffer.append(experience)

    def sample(self, batch_size: int) -> List[Experience]:
        """Sample random batch."""
        return random.sample(self.buffer, min(batch_size, len(self.buffer)))

    def __len__(self) -> int:
        return len(self.buffer)


@dataclass
class RLConfig:
    """Configuration for RL dispatcher."""
    state_dim: int = 35  # Depends on num_machines
    action_dim: int = 7  # Number of dispatch rules
    hidden_dim: int = 128
    learning_rate: float = 0.001
    gamma: float = 0.99  # Discount factor
    epsilon_start: float = 1.0
    epsilon_end: float = 0.01
    epsilon_decay: float = 0.995
    batch_size: int = 64
    target_update: int = 10  # Update target network every N episodes
    replay_capacity: int = 10000
    model_path: Optional[str] = None


class RLDispatcher:
    """
    Reinforcement Learning dispatcher for real-time decisions.

    Uses DQN to learn optimal dispatching rule selection based on shop state.
    """

    # Map action indices to dispatch rules
    ACTIONS = [
        DispatchRule.SPT,
        DispatchRule.LPT,
        DispatchRule.EDD,
        DispatchRule.SLACK,
        DispatchRule.FIFO,
        DispatchRule.CR,
        DispatchRule.RANDOM,
    ]

    def __init__(self, config: Optional[RLConfig] = None):
        self.config = config or RLConfig()
        self.epsilon = self.config.epsilon_start

        if TORCH_AVAILABLE:
            self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

            # Policy and target networks
            self.policy_net = DQNNetwork(
                self.config.state_dim,
                self.config.action_dim,
                self.config.hidden_dim
            ).to(self.device)

            self.target_net = DQNNetwork(
                self.config.state_dim,
                self.config.action_dim,
                self.config.hidden_dim
            ).to(self.device)
            self.target_net.load_state_dict(self.policy_net.state_dict())

            self.optimizer = optim.Adam(
                self.policy_net.parameters(),
                lr=self.config.learning_rate
            )
        else:
            self.device = None
            self.policy_net = None
            self.target_net = None
            self.optimizer = None

        self.replay_buffer = ReplayBuffer(self.config.replay_capacity)
        self.episode_count = 0

        # Load pretrained model if available
        if self.config.model_path:
            self.load(self.config.model_path)

    def select_action(self, state: DispatchState, training: bool = False) -> DispatchRule:
        """Select dispatching rule based on current state."""
        if not TORCH_AVAILABLE or self.policy_net is None:
            # Fall back to random selection
            return random.choice(self.ACTIONS)

        # Epsilon-greedy exploration
        if training and random.random() < self.epsilon:
            return random.choice(self.ACTIONS)

        # Greedy action from policy network
        state_tensor = torch.FloatTensor(state.to_vector()).unsqueeze(0).to(self.device)

        with torch.no_grad():
            q_values = self.policy_net(state_tensor)
            action_idx = q_values.argmax().item()

        return self.ACTIONS[action_idx]

    def apply_rule(
        self,
        rule: DispatchRule,
        pending_ops: List[Dict[str, Any]],
        current_time: float
    ) -> Optional[Dict[str, Any]]:
        """Apply dispatching rule to select next operation."""
        if not pending_ops:
            return None

        if rule == DispatchRule.SPT:
            # Shortest Processing Time
            return min(
                pending_ops,
                key=lambda op: min(op['processing_times'].values()) if op['processing_times'] else float('inf')
            )

        elif rule == DispatchRule.LPT:
            # Longest Processing Time
            return max(
                pending_ops,
                key=lambda op: max(op['processing_times'].values()) if op['processing_times'] else 0
            )

        elif rule == DispatchRule.EDD:
            # Earliest Due Date
            return min(
                pending_ops,
                key=lambda op: op.get('due_date') or float('inf')
            )

        elif rule == DispatchRule.SLACK:
            # Minimum Slack
            def slack(op):
                if not op.get('due_date'):
                    return float('inf')
                proc = min(op['processing_times'].values()) if op['processing_times'] else 0
                return op['due_date'] - current_time - proc

            return min(pending_ops, key=slack)

        elif rule == DispatchRule.FIFO:
            # First In First Out (by operation sequence)
            return pending_ops[0]

        elif rule == DispatchRule.CR:
            # Critical Ratio
            def cr(op):
                if not op.get('due_date'):
                    return float('inf')
                proc = min(op['processing_times'].values()) if op['processing_times'] else 1
                return (op['due_date'] - current_time) / proc if proc > 0 else float('inf')

            return min(pending_ops, key=cr)

        elif rule == DispatchRule.RANDOM:
            return random.choice(pending_ops)

        else:
            return pending_ops[0]

    def calculate_reward(
        self,
        prev_state: DispatchState,
        action: DispatchRule,
        new_state: DispatchState,
        completed_jobs: int,
        tardiness: float
    ) -> float:
        """Calculate reward for state transition."""
        reward = 0.0

        # Reward for completing jobs
        reward += completed_jobs * 10.0

        # Penalty for tardiness
        reward -= tardiness * 0.1

        # Reward for maintaining high utilization
        reward += new_state.avg_utilization * 5.0

        # Penalty for urgent jobs
        reward -= new_state.max_urgency * 2.0

        # Small reward for reducing queue
        if new_state.num_pending_jobs < prev_state.num_pending_jobs:
            reward += 1.0

        return reward

    def train_step(self) -> Optional[float]:
        """Perform one training step on replay buffer."""
        if not TORCH_AVAILABLE or len(self.replay_buffer) < self.config.batch_size:
            return None

        experiences = self.replay_buffer.sample(self.config.batch_size)

        # Prepare batch
        states = torch.FloatTensor([e.state for e in experiences]).to(self.device)
        actions = torch.LongTensor([self.ACTIONS.index(DispatchRule(e.action)) if isinstance(e.action, str) else e.action for e in experiences]).to(self.device)
        rewards = torch.FloatTensor([e.reward for e in experiences]).to(self.device)
        next_states = torch.FloatTensor([e.next_state for e in experiences]).to(self.device)
        dones = torch.FloatTensor([float(e.done) for e in experiences]).to(self.device)

        # Current Q values
        current_q = self.policy_net(states).gather(1, actions.unsqueeze(1))

        # Target Q values
        with torch.no_grad():
            next_q = self.target_net(next_states).max(1)[0]
            target_q = rewards + (1 - dones) * self.config.gamma * next_q

        # Compute loss
        loss = nn.functional.mse_loss(current_q.squeeze(), target_q)

        # Optimize
        self.optimizer.zero_grad()
        loss.backward()
        self.optimizer.step()

        return loss.item()

    def update_target(self) -> None:
        """Update target network."""
        if TORCH_AVAILABLE and self.target_net is not None:
            self.target_net.load_state_dict(self.policy_net.state_dict())

    def end_episode(self) -> None:
        """Called at the end of an episode."""
        self.episode_count += 1

        # Decay epsilon
        self.epsilon = max(
            self.config.epsilon_end,
            self.epsilon * self.config.epsilon_decay
        )

        # Update target network periodically
        if self.episode_count % self.config.target_update == 0:
            self.update_target()

    def save(self, path: str) -> None:
        """Save model to disk."""
        if TORCH_AVAILABLE and self.policy_net is not None:
            torch.save({
                'policy_net': self.policy_net.state_dict(),
                'target_net': self.target_net.state_dict(),
                'optimizer': self.optimizer.state_dict(),
                'epsilon': self.epsilon,
                'episode_count': self.episode_count,
            }, path)
            logger.info(f"Saved RL model to {path}")

    def load(self, path: str) -> None:
        """Load model from disk."""
        if TORCH_AVAILABLE and Path(path).exists():
            checkpoint = torch.load(path, map_location=self.device)
            self.policy_net.load_state_dict(checkpoint['policy_net'])
            self.target_net.load_state_dict(checkpoint['target_net'])
            self.optimizer.load_state_dict(checkpoint['optimizer'])
            self.epsilon = checkpoint.get('epsilon', self.config.epsilon_end)
            self.episode_count = checkpoint.get('episode_count', 0)
            logger.info(f"Loaded RL model from {path}")


@SchedulerFactory.register(SchedulerType.RL_DISPATCH)
class RLDispatchScheduler(BaseScheduler):
    """
    Scheduler using RL-based dispatching.

    Uses a trained RL agent to select dispatching rules in real-time.
    """

    scheduler_type = SchedulerType.RL_DISPATCH

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)

        rl_config = RLConfig(
            model_path=config.get('model_path') if config else None,
        )
        self.dispatcher = RLDispatcher(rl_config)
        self.training_mode = config.get('training', False) if config else False

    def solve(self, problem: SchedulingProblem) -> Schedule:
        """Solve using RL-based dispatching."""
        schedule = Schedule(
            schedule_id=str(uuid4()),
            status=ScheduleStatus.FEASIBLE,
            solver_type=self.scheduler_type,
        )

        # Track machine availability
        machine_available: Dict[str, float] = {
            m.machine_id: m.available_from for m in problem.machines
        }

        # Track operation completion
        op_completion: Dict[str, float] = {}
        scheduled_ops: set = set()

        # Simulation loop
        current_time = 0.0
        max_time = problem.horizon

        while current_time < max_time:
            # Build current state
            state = DispatchState.from_problem(problem, schedule, current_time)

            if not state.pending_operations:
                break

            # Select dispatching rule
            rule = self.dispatcher.select_action(state, training=self.training_mode)

            # Find available machines
            available_machines = [
                m_id for m_id, m_state in state.machine_states.items()
                if m_state['available']
            ]

            if not available_machines:
                # Advance time to next machine availability
                next_available = min(
                    machine_available[m_id] for m_id in machine_available
                    if machine_available[m_id] > current_time
                )
                current_time = next_available
                continue

            # For each available machine, apply dispatching rule
            for machine_id in available_machines:
                # Get pending operations for this machine
                pending_for_machine = [
                    op for op in state.pending_operations
                    if machine_id in op.get('processing_times', {})
                ]

                if not pending_for_machine:
                    continue

                # Apply rule to select operation
                selected = self.dispatcher.apply_rule(rule, pending_for_machine, current_time)

                if selected and selected['operation_id'] not in scheduled_ops:
                    # Get job for release time
                    job = problem.get_job(selected['job_id'])
                    earliest = job.release_time if job else 0

                    # Check precedence
                    op_obj = None
                    for op in problem.get_all_operations():
                        if op.operation_id == selected['operation_id']:
                            op_obj = op
                            break

                    if op_obj:
                        for pred_id in op_obj.predecessors:
                            if pred_id in op_completion:
                                earliest = max(earliest, op_completion[pred_id])

                    # Schedule operation
                    start = max(current_time, earliest, machine_available.get(machine_id, 0))
                    proc_time = selected['processing_times'].get(machine_id, 0)
                    end = start + proc_time

                    scheduled_op = ScheduledOperation(
                        operation_id=selected['operation_id'],
                        job_id=selected['job_id'],
                        machine_id=machine_id,
                        start_time=start,
                        end_time=end,
                    )

                    schedule.add_operation(scheduled_op)
                    machine_available[machine_id] = end
                    op_completion[selected['operation_id']] = end
                    scheduled_ops.add(selected['operation_id'])

            # Advance time
            current_time = min(machine_available.values())

        # Calculate objectives
        calculator = ObjectiveCalculator()
        job_dicts = [j.to_dict() for j in problem.jobs]
        op_dicts = [op.to_dict() for op in schedule.operations]
        machine_dicts = {m.machine_id: m.to_dict() for m in problem.machines}

        schedule.objectives = calculator.calculate_full_objectives(
            job_dicts, op_dicts, machine_dicts
        )

        return schedule

    def train(
        self,
        problems: List[SchedulingProblem],
        num_episodes: int = 100
    ) -> Dict[str, Any]:
        """Train the RL dispatcher on a set of problems."""
        self.training_mode = True
        training_stats = {
            'episodes': [],
            'rewards': [],
            'losses': [],
        }

        for episode in range(num_episodes):
            problem = random.choice(problems)
            total_reward = 0.0
            losses = []

            # Solve with training enabled
            schedule = self.solve(problem)

            # Record final reward
            if schedule.objectives:
                reward = -schedule.objectives.total_tardiness
                reward += schedule.objectives.avg_utilization
                total_reward = reward

            # Train step
            loss = self.dispatcher.train_step()
            if loss is not None:
                losses.append(loss)

            self.dispatcher.end_episode()

            training_stats['episodes'].append(episode)
            training_stats['rewards'].append(total_reward)
            training_stats['losses'].append(sum(losses) / len(losses) if losses else 0)

            if (episode + 1) % 10 == 0:
                avg_reward = sum(training_stats['rewards'][-10:]) / 10
                logger.info(f"Episode {episode + 1}: Avg Reward = {avg_reward:.2f}")

        self.training_mode = False
        return training_stats
