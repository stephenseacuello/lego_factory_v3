"""
LEGO Factory v3 - Reinforcement Learning Scheduler
===================================================
RL-based job dispatching using PPO agent from stable-baselines3.
Implements MESA-11 Operations/Detail Scheduling function.
"""

import logging
import os
import json
import numpy as np
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)

# Check for gymnasium and stable-baselines3
try:
    import gymnasium as gym
    from gymnasium import spaces
    HAS_GYM = True
except ImportError:
    HAS_GYM = False
    logger.warning("gymnasium not installed. RL scheduler will use heuristic fallback.")

try:
    from stable_baselines3 import PPO
    from stable_baselines3.common.callbacks import BaseCallback
    HAS_SB3 = True
except ImportError:
    HAS_SB3 = False
    logger.warning("stable-baselines3 not installed. RL scheduler will use heuristic fallback.")


@dataclass
class RLJob:
    """Job representation for RL environment."""
    job_id: str
    processing_time: float  # minutes
    due_date: Optional[datetime] = None
    priority: int = 5
    material_type: Optional[str] = None
    eligible_machines: List[str] = field(default_factory=list)
    release_time: float = 0.0  # minutes from start


@dataclass
class RLMachine:
    """Machine representation for RL environment."""
    machine_id: str
    name: str
    current_job: Optional[str] = None
    available_at: float = 0.0  # minutes from start
    capabilities: List[str] = field(default_factory=list)


@dataclass
class RLState:
    """State representation for RL agent."""
    machine_status: np.ndarray  # 0=idle, 1=busy for each machine
    machine_remaining: np.ndarray  # remaining time on current job
    queue_depths: np.ndarray  # jobs waiting per machine
    job_slacks: np.ndarray  # (due_date - now - remaining_time) for queued jobs
    avg_utilization: float
    wip_level: int
    current_time: float


if HAS_GYM:
    class SchedulingEnv(gym.Env):
        """
        Gymnasium environment for job shop scheduling.

        Observation Space:
            - machine_status: Binary array (n_machines,) - 0=idle, 1=busy
            - machine_remaining: Float array (n_machines,) - remaining processing time
            - queue_depths: Int array (n_machines,) - jobs waiting per machine
            - global_features: [wip_level, avg_slack, avg_utilization, time_remaining]

        Action Space:
            Discrete(n_jobs * n_machines + 1)
            - Actions 0 to n_jobs*n_machines-1: Assign job i to machine j
            - Action n_jobs*n_machines: Do nothing (wait)

        Reward:
            - Negative tardiness contribution when job completes late
            - Small positive reward for on-time completion
            - Small negative reward for idle time
            - Bonus for high utilization
        """

        metadata = {"render_modes": ["human"]}

        def __init__(
            self,
            n_machines: int = 11,
            n_jobs: int = 20,
            horizon_minutes: float = 480.0,
            render_mode: Optional[str] = None
        ):
            super().__init__()

            self.n_machines = n_machines
            self.n_jobs = n_jobs
            self.horizon = horizon_minutes
            self.render_mode = render_mode

            # Observation space
            # machine_status (n_machines) + machine_remaining (n_machines) +
            # queue_depths (n_machines) + global_features (4)
            obs_dim = 3 * n_machines + 4
            self.observation_space = spaces.Box(
                low=-np.inf, high=np.inf, shape=(obs_dim,), dtype=np.float32
            )

            # Action space: assign any job to any machine, or wait
            self.action_space = spaces.Discrete(n_jobs * n_machines + 1)

            # Initialize state
            self.reset()

        def reset(self, seed=None, options=None):
            super().reset(seed=seed)

            # Reset simulation state
            self.current_time = 0.0
            self.machines = [RLMachine(f"machine_{i}", f"Machine {i}") for i in range(self.n_machines)]
            self.pending_jobs = []
            self.completed_jobs = []
            self.total_tardiness = 0.0
            self.total_completion_time = 0.0

            # Generate random jobs if not provided
            if options and 'jobs' in options:
                self.pending_jobs = options['jobs']
            else:
                self._generate_random_jobs()

            return self._get_observation(), {}

        def _generate_random_jobs(self):
            """Generate random jobs for training."""
            self.pending_jobs = []
            for i in range(self.n_jobs):
                processing_time = self.np_random.uniform(10, 60)
                due_offset = processing_time * self.np_random.uniform(1.5, 4.0)

                job = RLJob(
                    job_id=f"job_{i}",
                    processing_time=processing_time,
                    due_date=datetime.utcnow() + timedelta(minutes=due_offset),
                    priority=self.np_random.integers(1, 10),
                    eligible_machines=[f"machine_{j}" for j in range(self.n_machines)],
                    release_time=self.np_random.uniform(0, self.horizon * 0.3)
                )
                self.pending_jobs.append(job)

        def _get_observation(self) -> np.ndarray:
            """Get current state observation."""
            # Machine status (0=idle, 1=busy)
            machine_status = np.array([
                1.0 if m.current_job else 0.0 for m in self.machines
            ], dtype=np.float32)

            # Remaining time on current jobs
            machine_remaining = np.array([
                max(0, m.available_at - self.current_time) for m in self.machines
            ], dtype=np.float32) / self.horizon

            # Queue depths (simplified - count eligible jobs per machine)
            queue_depths = np.zeros(self.n_machines, dtype=np.float32)
            for job in self.pending_jobs:
                if job.release_time <= self.current_time:
                    for i, m in enumerate(self.machines):
                        if m.machine_id in job.eligible_machines or not job.eligible_machines:
                            queue_depths[i] += 1
            queue_depths = queue_depths / max(len(self.pending_jobs), 1)

            # Global features
            wip_level = sum(1 for m in self.machines if m.current_job) / self.n_machines

            # Average slack
            avg_slack = 0.0
            available_jobs = [j for j in self.pending_jobs if j.release_time <= self.current_time]
            if available_jobs:
                slacks = []
                for job in available_jobs:
                    if job.due_date:
                        due_min = (job.due_date - datetime.utcnow()).total_seconds() / 60
                        slack = (due_min - self.current_time - job.processing_time) / self.horizon
                        slacks.append(slack)
                avg_slack = np.mean(slacks) if slacks else 0.0

            avg_utilization = np.mean(machine_status)
            time_remaining = (self.horizon - self.current_time) / self.horizon

            global_features = np.array([
                wip_level, avg_slack, avg_utilization, time_remaining
            ], dtype=np.float32)

            return np.concatenate([machine_status, machine_remaining, queue_depths, global_features])

        def step(self, action: int):
            """Execute action and return new state."""
            reward = 0.0
            info = {}

            # Parse action
            if action == self.n_jobs * self.n_machines:
                # Wait action - advance time
                reward = -0.01  # Small penalty for waiting
                self._advance_time(1.0)
            else:
                job_idx = action // self.n_machines
                machine_idx = action % self.n_machines

                # Try to assign job to machine
                if job_idx < len(self.pending_jobs):
                    job = self.pending_jobs[job_idx]
                    machine = self.machines[machine_idx]

                    # Check if valid assignment
                    if (not machine.current_job and
                        job.release_time <= self.current_time and
                        (machine.machine_id in job.eligible_machines or not job.eligible_machines)):

                        # Assign job
                        machine.current_job = job.job_id
                        machine.available_at = self.current_time + job.processing_time
                        self.pending_jobs.remove(job)

                        # Calculate reward based on expected tardiness
                        if job.due_date:
                            expected_completion = self.current_time + job.processing_time
                            due_min = (job.due_date - datetime.utcnow()).total_seconds() / 60
                            expected_tardiness = max(0, expected_completion - due_min)
                            reward = -expected_tardiness / self.horizon * job.priority
                        else:
                            reward = 0.1  # Small reward for any assignment

                        info['assigned'] = True
                    else:
                        reward = -0.1  # Penalty for invalid action
                        info['assigned'] = False
                else:
                    reward = -0.1  # Penalty for invalid job index

            # Check for job completions
            for machine in self.machines:
                if machine.current_job and machine.available_at <= self.current_time:
                    # Job completed
                    self.completed_jobs.append(machine.current_job)
                    machine.current_job = None
                    reward += 0.05  # Small reward for completion

            # Check termination
            terminated = len(self.pending_jobs) == 0 and all(not m.current_job for m in self.machines)
            truncated = self.current_time >= self.horizon

            if terminated:
                # Final reward based on overall performance
                utilization = len(self.completed_jobs) / max(self.n_jobs, 1)
                reward += utilization * 0.5

            return self._get_observation(), reward, terminated, truncated, info

        def _advance_time(self, delta: float):
            """Advance simulation time."""
            self.current_time += delta

            # Complete finished jobs
            for machine in self.machines:
                if machine.current_job and machine.available_at <= self.current_time:
                    self.completed_jobs.append(machine.current_job)
                    machine.current_job = None


class RLDispatcher:
    """
    RL-based job dispatcher using trained PPO model.
    Falls back to heuristic if RL libraries not available.
    """

    def __init__(self, model_path: Optional[str] = None):
        self.model = None
        self.model_path = model_path or self._default_model_path()
        self.env = None

        if HAS_SB3 and HAS_GYM:
            self._load_model()

    def _default_model_path(self) -> str:
        """Get default model path."""
        base_dir = Path(__file__).parent.parent.parent
        return str(base_dir / 'models' / 'rl' / 'scheduling_ppo.zip')

    def _load_model(self):
        """Load trained PPO model if available."""
        if os.path.exists(self.model_path):
            try:
                self.model = PPO.load(self.model_path)
                logger.info(f"Loaded RL model from {self.model_path}")
            except Exception as e:
                logger.warning(f"Could not load RL model: {e}")

    def select_action(
        self,
        machines: List[Dict[str, Any]],
        pending_jobs: List[Dict[str, Any]],
        current_time: datetime
    ) -> Optional[Tuple[str, str]]:
        """
        Select best (job_id, machine_id) pair using RL or heuristic.

        Returns:
            Tuple of (job_id, machine_id) or None if no valid action
        """
        if not pending_jobs:
            return None

        # Convert to internal format
        rl_machines = [
            RLMachine(
                machine_id=m['machine_id'],
                name=m.get('name', m['machine_id']),
                current_job=m.get('current_job'),
                available_at=m.get('available_at', 0)
            )
            for m in machines
        ]

        rl_jobs = [
            RLJob(
                job_id=j['job_id'],
                processing_time=j.get('processing_time_mins', j.get('duration_minutes', 30)),
                due_date=j.get('due_date'),
                priority=j.get('priority', 5),
                eligible_machines=j.get('eligible_machines', []),
                release_time=j.get('release_time', 0)
            )
            for j in pending_jobs
        ]

        if self.model and HAS_GYM:
            return self._select_with_model(rl_machines, rl_jobs)
        else:
            return self._select_heuristic(rl_machines, rl_jobs)

    def _select_with_model(
        self,
        machines: List[RLMachine],
        jobs: List[RLJob]
    ) -> Optional[Tuple[str, str]]:
        """Select action using trained model."""
        # Create temporary environment
        env = SchedulingEnv(n_machines=len(machines), n_jobs=len(jobs))
        env.machines = machines
        env.pending_jobs = jobs

        obs = env._get_observation()
        action, _ = self.model.predict(obs, deterministic=True)

        # Decode action
        if action == len(jobs) * len(machines):
            return None  # Wait action

        job_idx = action // len(machines)
        machine_idx = action % len(machines)

        if job_idx < len(jobs) and machine_idx < len(machines):
            job = jobs[job_idx]
            machine = machines[machine_idx]

            # Validate assignment
            if not machine.current_job:
                return (job.job_id, machine.machine_id)

        return None

    def _select_heuristic(
        self,
        machines: List[RLMachine],
        jobs: List[RLJob]
    ) -> Optional[Tuple[str, str]]:
        """Fallback heuristic selection (WSPT-based)."""
        # Find available machines
        available_machines = [m for m in machines if not m.current_job]
        if not available_machines:
            return None

        # Score jobs by WSPT (priority / processing_time)
        job_scores = []
        for job in jobs:
            score = job.priority / max(job.processing_time, 1)

            # Boost score for urgent jobs
            if job.due_date:
                time_to_due = (job.due_date - datetime.utcnow()).total_seconds() / 60
                if time_to_due < job.processing_time * 2:
                    score *= 2.0

            job_scores.append((job, score))

        # Sort by score descending
        job_scores.sort(key=lambda x: x[1], reverse=True)

        # Find best job-machine pair
        for job, _ in job_scores:
            eligible = job.eligible_machines or [m.machine_id for m in available_machines]
            for machine in available_machines:
                if machine.machine_id in eligible:
                    return (job.job_id, machine.machine_id)

        return None


class RLTrainer:
    """Trainer for RL scheduling agent."""

    def __init__(
        self,
        n_machines: int = 11,
        n_jobs: int = 20,
        save_path: Optional[str] = None
    ):
        self.n_machines = n_machines
        self.n_jobs = n_jobs
        self.save_path = save_path or self._default_save_path()
        self.model = None
        self.env = None

    def _default_save_path(self) -> str:
        """Get default save path."""
        base_dir = Path(__file__).parent.parent.parent
        return str(base_dir / 'models' / 'rl' / 'scheduling_ppo.zip')

    def train(
        self,
        total_timesteps: int = 100000,
        learning_rate: float = 3e-4,
        n_steps: int = 2048,
        batch_size: int = 64,
        verbose: int = 1
    ) -> Dict[str, Any]:
        """
        Train PPO agent on scheduling environment.

        Returns:
            Training metrics dict
        """
        if not HAS_GYM or not HAS_SB3:
            logger.error("gymnasium and stable-baselines3 required for training")
            return {'error': 'Missing dependencies'}

        # Create environment
        self.env = SchedulingEnv(n_machines=self.n_machines, n_jobs=self.n_jobs)

        # Create model
        self.model = PPO(
            "MlpPolicy",
            self.env,
            learning_rate=learning_rate,
            n_steps=n_steps,
            batch_size=batch_size,
            verbose=verbose,
            tensorboard_log="./logs/rl_scheduler/"
        )

        # Train
        start_time = datetime.now()
        self.model.learn(total_timesteps=total_timesteps)
        training_time = (datetime.now() - start_time).total_seconds()

        # Save model
        os.makedirs(os.path.dirname(self.save_path), exist_ok=True)
        self.model.save(self.save_path)
        logger.info(f"Model saved to {self.save_path}")

        return {
            'total_timesteps': total_timesteps,
            'training_time_seconds': training_time,
            'model_path': self.save_path
        }

    def evaluate(self, n_episodes: int = 100) -> Dict[str, Any]:
        """Evaluate trained model."""
        if not self.model:
            if os.path.exists(self.save_path):
                self.model = PPO.load(self.save_path)
            else:
                return {'error': 'No trained model available'}

        if not self.env:
            self.env = SchedulingEnv(n_machines=self.n_machines, n_jobs=self.n_jobs)

        rewards = []
        completions = []

        for _ in range(n_episodes):
            obs, _ = self.env.reset()
            episode_reward = 0
            done = False

            while not done:
                action, _ = self.model.predict(obs, deterministic=True)
                obs, reward, terminated, truncated, _ = self.env.step(action)
                episode_reward += reward
                done = terminated or truncated

            rewards.append(episode_reward)
            completions.append(len(self.env.completed_jobs))

        return {
            'mean_reward': np.mean(rewards),
            'std_reward': np.std(rewards),
            'mean_completions': np.mean(completions),
            'n_episodes': n_episodes
        }


# =============================================================================
# Module-level functions
# =============================================================================

def get_rl_dispatcher(model_path: Optional[str] = None) -> RLDispatcher:
    """Get RL dispatcher instance."""
    return RLDispatcher(model_path)


def schedule_with_rl(
    jobs: List[Dict[str, Any]],
    machines: List[Dict[str, Any]],
    current_time: Optional[datetime] = None
) -> List[Dict[str, Any]]:
    """
    Schedule jobs using RL agent.

    Args:
        jobs: List of job dicts with job_id, processing_time_mins, due_date, priority
        machines: List of machine dicts with machine_id, name
        current_time: Current simulation time

    Returns:
        List of scheduled jobs with machine_id and scheduled_start assigned
    """
    current_time = current_time or datetime.utcnow()
    dispatcher = get_rl_dispatcher()

    scheduled = []
    pending = list(jobs)
    machine_available = {m['machine_id']: current_time for m in machines}

    while pending:
        # Get current machine states
        machine_states = [
            {
                'machine_id': m['machine_id'],
                'name': m.get('name', m['machine_id']),
                'current_job': None,
                'available_at': (machine_available[m['machine_id']] - current_time).total_seconds() / 60
            }
            for m in machines
        ]

        # Get pending jobs with remaining time
        pending_states = [
            {
                'job_id': j['job_id'],
                'processing_time_mins': j.get('processing_time_mins', j.get('duration_minutes', 30)),
                'due_date': j.get('due_date'),
                'priority': j.get('priority', 5),
                'eligible_machines': j.get('eligible_machines', [m['machine_id'] for m in machines])
            }
            for j in pending
        ]

        # Select next action
        action = dispatcher.select_action(machine_states, pending_states, current_time)

        if action is None:
            break

        job_id, machine_id = action

        # Find and schedule the job
        for job in pending:
            if job['job_id'] == job_id:
                start_time = machine_available[machine_id]
                duration = job.get('processing_time_mins', job.get('duration_minutes', 30))
                end_time = start_time + timedelta(minutes=duration)

                scheduled.append({
                    **job,
                    'machine_id': machine_id,
                    'scheduled_start': start_time.isoformat(),
                    'scheduled_end': end_time.isoformat()
                })

                machine_available[machine_id] = end_time
                pending.remove(job)
                break

    return scheduled
