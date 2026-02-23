"""
Advanced Reinforcement Learning Algorithms for Manufacturing Scheduling.

This module extends the RL dispatcher with state-of-the-art algorithms:
- PPO (Proximal Policy Optimization)
- SAC (Soft Actor-Critic)
- TD3 (Twin Delayed DDPG)
- Curriculum Learning

Research Value:
- Novel RL applications to manufacturing scheduling
- Comparative analysis of RL algorithms
- Curriculum learning for complex scheduling

References:
- Schulman, J., et al. (2017). Proximal Policy Optimization Algorithms
- Haarnoja, T., et al. (2018). Soft Actor-Critic
- Fujimoto, S., et al. (2018). Addressing Function Approximation Error
"""

from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from typing import (
    Dict, List, Optional, Set, Any, TypeVar, Generic,
    Callable, Tuple, Union
)
import numpy as np
import logging
from collections import deque
import random

logger = logging.getLogger(__name__)

# Check for PyTorch
try:
    import torch
    import torch.nn as nn
    import torch.nn.functional as F
    import torch.optim as optim
    from torch.distributions import Categorical, Normal
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False
    torch = nn = F = optim = None


# =============================================================================
# Neural Network Architectures
# =============================================================================

if TORCH_AVAILABLE:

    class ActorNetwork(nn.Module):
        """Actor network for policy-based methods."""

        def __init__(
            self,
            state_dim: int,
            action_dim: int,
            hidden_dims: List[int] = [256, 256],
            continuous: bool = False
        ):
            super().__init__()
            self.continuous = continuous

            layers = []
            prev_dim = state_dim
            for hidden_dim in hidden_dims:
                layers.append(nn.Linear(prev_dim, hidden_dim))
                layers.append(nn.ReLU())
                prev_dim = hidden_dim

            self.shared = nn.Sequential(*layers)

            if continuous:
                self.mean_head = nn.Linear(prev_dim, action_dim)
                self.log_std_head = nn.Linear(prev_dim, action_dim)
            else:
                self.action_head = nn.Linear(prev_dim, action_dim)

        def forward(self, state: torch.Tensor) -> Tuple[torch.Tensor, ...]:
            features = self.shared(state)

            if self.continuous:
                mean = self.mean_head(features)
                log_std = self.log_std_head(features)
                log_std = torch.clamp(log_std, -20, 2)
                return mean, log_std
            else:
                logits = self.action_head(features)
                return logits,

        def get_action(
            self,
            state: torch.Tensor,
            deterministic: bool = False
        ) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
            """Get action with log probability and entropy."""
            if self.continuous:
                mean, log_std = self.forward(state)
                std = log_std.exp()
                dist = Normal(mean, std)

                if deterministic:
                    action = mean
                else:
                    action = dist.rsample()

                log_prob = dist.log_prob(action).sum(-1, keepdim=True)
                entropy = dist.entropy().sum(-1, keepdim=True)

                # Squash to [-1, 1]
                action = torch.tanh(action)
                # Correct log prob for squashing
                log_prob -= (2 * (np.log(2) - action - F.softplus(-2 * action))).sum(-1, keepdim=True)

                return action, log_prob, entropy
            else:
                logits, = self.forward(state)
                dist = Categorical(logits=logits)

                if deterministic:
                    action = logits.argmax(-1)
                else:
                    action = dist.sample()

                log_prob = dist.log_prob(action).unsqueeze(-1)
                entropy = dist.entropy().unsqueeze(-1)

                return action, log_prob, entropy


    class CriticNetwork(nn.Module):
        """Critic network for value estimation."""

        def __init__(
            self,
            state_dim: int,
            action_dim: int = 0,
            hidden_dims: List[int] = [256, 256],
            use_action: bool = False
        ):
            super().__init__()
            self.use_action = use_action

            input_dim = state_dim + action_dim if use_action else state_dim

            layers = []
            prev_dim = input_dim
            for hidden_dim in hidden_dims:
                layers.append(nn.Linear(prev_dim, hidden_dim))
                layers.append(nn.ReLU())
                prev_dim = hidden_dim

            layers.append(nn.Linear(prev_dim, 1))
            self.network = nn.Sequential(*layers)

        def forward(
            self,
            state: torch.Tensor,
            action: Optional[torch.Tensor] = None
        ) -> torch.Tensor:
            if self.use_action and action is not None:
                x = torch.cat([state, action], dim=-1)
            else:
                x = state
            return self.network(x)


    class TwinCriticNetwork(nn.Module):
        """Twin critic network for SAC and TD3."""

        def __init__(
            self,
            state_dim: int,
            action_dim: int,
            hidden_dims: List[int] = [256, 256]
        ):
            super().__init__()
            self.q1 = CriticNetwork(state_dim, action_dim, hidden_dims, use_action=True)
            self.q2 = CriticNetwork(state_dim, action_dim, hidden_dims, use_action=True)

        def forward(
            self,
            state: torch.Tensor,
            action: torch.Tensor
        ) -> Tuple[torch.Tensor, torch.Tensor]:
            return self.q1(state, action), self.q2(state, action)

        def q1_forward(
            self,
            state: torch.Tensor,
            action: torch.Tensor
        ) -> torch.Tensor:
            return self.q1(state, action)


# =============================================================================
# Replay Buffer
# =============================================================================

@dataclass
class Transition:
    """Single transition in replay buffer."""
    state: np.ndarray
    action: Union[int, np.ndarray]
    reward: float
    next_state: np.ndarray
    done: bool
    log_prob: Optional[float] = None
    value: Optional[float] = None


class ReplayBuffer:
    """Experience replay buffer with priority sampling support."""

    def __init__(
        self,
        capacity: int = 100000,
        prioritized: bool = False,
        alpha: float = 0.6
    ):
        self.capacity = capacity
        self.buffer: deque = deque(maxlen=capacity)
        self.prioritized = prioritized
        self.alpha = alpha
        self.priorities = deque(maxlen=capacity)

    def push(self, transition: Transition, priority: float = 1.0) -> None:
        """Add transition to buffer."""
        self.buffer.append(transition)
        if self.prioritized:
            self.priorities.append(priority ** self.alpha)

    def sample(self, batch_size: int) -> List[Transition]:
        """Sample batch from buffer."""
        if self.prioritized and len(self.priorities) > 0:
            probs = np.array(self.priorities)
            probs = probs / probs.sum()
            indices = np.random.choice(len(self.buffer), batch_size, p=probs)
            return [self.buffer[i] for i in indices]
        else:
            return random.sample(list(self.buffer), min(batch_size, len(self.buffer)))

    def __len__(self) -> int:
        return len(self.buffer)

    def clear(self) -> None:
        self.buffer.clear()
        self.priorities.clear()


class RolloutBuffer:
    """Buffer for on-policy algorithms (PPO)."""

    def __init__(self):
        self.states: List[np.ndarray] = []
        self.actions: List[Union[int, np.ndarray]] = []
        self.rewards: List[float] = []
        self.log_probs: List[float] = []
        self.values: List[float] = []
        self.dones: List[bool] = []

    def push(
        self,
        state: np.ndarray,
        action: Union[int, np.ndarray],
        reward: float,
        log_prob: float,
        value: float,
        done: bool
    ) -> None:
        """Add experience to rollout."""
        self.states.append(state)
        self.actions.append(action)
        self.rewards.append(reward)
        self.log_probs.append(log_prob)
        self.values.append(value)
        self.dones.append(done)

    def get(self) -> Dict[str, np.ndarray]:
        """Get all data as numpy arrays."""
        return {
            'states': np.array(self.states),
            'actions': np.array(self.actions),
            'rewards': np.array(self.rewards),
            'log_probs': np.array(self.log_probs),
            'values': np.array(self.values),
            'dones': np.array(self.dones),
        }

    def __len__(self) -> int:
        return len(self.states)

    def clear(self) -> None:
        self.states.clear()
        self.actions.clear()
        self.rewards.clear()
        self.log_probs.clear()
        self.values.clear()
        self.dones.clear()


# =============================================================================
# PPO (Proximal Policy Optimization)
# =============================================================================

@dataclass
class PPOConfig:
    """Configuration for PPO algorithm."""
    state_dim: int = 35
    action_dim: int = 7
    hidden_dims: List[int] = field(default_factory=lambda: [256, 256])
    lr_actor: float = 3e-4
    lr_critic: float = 1e-3
    gamma: float = 0.99
    gae_lambda: float = 0.95
    clip_epsilon: float = 0.2
    entropy_coef: float = 0.01
    value_coef: float = 0.5
    max_grad_norm: float = 0.5
    n_epochs: int = 10
    batch_size: int = 64
    rollout_steps: int = 2048


class PPOAgent:
    """
    Proximal Policy Optimization agent.

    PPO is a policy gradient method that uses a clipped surrogate
    objective for stable training.

    Research Value:
    - State-of-the-art policy gradient for scheduling
    - Stable training dynamics
    - Sample efficient learning
    """

    def __init__(self, config: PPOConfig):
        self.config = config
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu") if TORCH_AVAILABLE else None

        if TORCH_AVAILABLE:
            # Networks
            self.actor = ActorNetwork(
                config.state_dim,
                config.action_dim,
                config.hidden_dims,
                continuous=False
            ).to(self.device)

            self.critic = CriticNetwork(
                config.state_dim,
                hidden_dims=config.hidden_dims
            ).to(self.device)

            # Optimizers
            self.actor_optimizer = optim.Adam(
                self.actor.parameters(), lr=config.lr_actor
            )
            self.critic_optimizer = optim.Adam(
                self.critic.parameters(), lr=config.lr_critic
            )

        self.rollout = RolloutBuffer()
        self.training_stats: List[Dict[str, float]] = []

    def select_action(
        self,
        state: np.ndarray,
        deterministic: bool = False
    ) -> Tuple[int, float, float]:
        """Select action from policy."""
        if not TORCH_AVAILABLE:
            return random.randint(0, self.config.action_dim - 1), 0.0, 0.0

        with torch.no_grad():
            state_tensor = torch.FloatTensor(state).unsqueeze(0).to(self.device)
            action, log_prob, _ = self.actor.get_action(state_tensor, deterministic)
            value = self.critic(state_tensor)

        return action.item(), log_prob.item(), value.item()

    def store_transition(
        self,
        state: np.ndarray,
        action: int,
        reward: float,
        log_prob: float,
        value: float,
        done: bool
    ) -> None:
        """Store transition in rollout buffer."""
        self.rollout.push(state, action, reward, log_prob, value, done)

    def compute_gae(
        self,
        rewards: np.ndarray,
        values: np.ndarray,
        dones: np.ndarray,
        next_value: float
    ) -> Tuple[np.ndarray, np.ndarray]:
        """Compute Generalized Advantage Estimation."""
        n = len(rewards)
        advantages = np.zeros(n)
        returns = np.zeros(n)

        gae = 0.0
        next_val = next_value

        for t in reversed(range(n)):
            mask = 1.0 - dones[t]
            delta = rewards[t] + self.config.gamma * next_val * mask - values[t]
            gae = delta + self.config.gamma * self.config.gae_lambda * mask * gae
            advantages[t] = gae
            returns[t] = gae + values[t]
            next_val = values[t]

        return advantages, returns

    def update(self) -> Dict[str, float]:
        """Update policy and value networks."""
        if not TORCH_AVAILABLE or len(self.rollout) < self.config.batch_size:
            return {}

        data = self.rollout.get()
        states = torch.FloatTensor(data['states']).to(self.device)
        actions = torch.LongTensor(data['actions']).to(self.device)
        old_log_probs = torch.FloatTensor(data['log_probs']).to(self.device)
        rewards = data['rewards']
        values = data['values']
        dones = data['dones']

        # Compute GAE
        with torch.no_grad():
            next_value = self.critic(states[-1:]).item()
        advantages, returns = self.compute_gae(rewards, values, dones, next_value)

        advantages = torch.FloatTensor(advantages).to(self.device)
        returns = torch.FloatTensor(returns).to(self.device)

        # Normalize advantages
        advantages = (advantages - advantages.mean()) / (advantages.std() + 1e-8)

        # Training loop
        n = len(states)
        total_actor_loss = 0.0
        total_critic_loss = 0.0
        total_entropy = 0.0

        for _ in range(self.config.n_epochs):
            indices = np.random.permutation(n)

            for start in range(0, n, self.config.batch_size):
                end = start + self.config.batch_size
                batch_idx = indices[start:end]

                batch_states = states[batch_idx]
                batch_actions = actions[batch_idx]
                batch_old_log_probs = old_log_probs[batch_idx]
                batch_advantages = advantages[batch_idx]
                batch_returns = returns[batch_idx]

                # Get current policy
                _, new_log_probs, entropy = self.actor.get_action(batch_states)
                new_log_probs = new_log_probs[
                    torch.arange(len(batch_actions)), batch_actions
                ].unsqueeze(-1)

                # PPO clipped objective
                ratio = (new_log_probs - batch_old_log_probs).exp()
                surr1 = ratio * batch_advantages
                surr2 = torch.clamp(
                    ratio,
                    1 - self.config.clip_epsilon,
                    1 + self.config.clip_epsilon
                ) * batch_advantages
                actor_loss = -torch.min(surr1, surr2).mean()

                # Entropy bonus
                entropy_loss = -self.config.entropy_coef * entropy.mean()

                # Value loss
                values_pred = self.critic(batch_states)
                critic_loss = self.config.value_coef * F.mse_loss(
                    values_pred.squeeze(), batch_returns
                )

                # Total loss
                loss = actor_loss + entropy_loss + critic_loss

                # Update networks
                self.actor_optimizer.zero_grad()
                self.critic_optimizer.zero_grad()
                loss.backward()
                nn.utils.clip_grad_norm_(
                    list(self.actor.parameters()) + list(self.critic.parameters()),
                    self.config.max_grad_norm
                )
                self.actor_optimizer.step()
                self.critic_optimizer.step()

                total_actor_loss += actor_loss.item()
                total_critic_loss += critic_loss.item()
                total_entropy += entropy.mean().item()

        self.rollout.clear()

        stats = {
            'actor_loss': total_actor_loss / self.config.n_epochs,
            'critic_loss': total_critic_loss / self.config.n_epochs,
            'entropy': total_entropy / self.config.n_epochs,
        }
        self.training_stats.append(stats)
        return stats


# =============================================================================
# SAC (Soft Actor-Critic)
# =============================================================================

@dataclass
class SACConfig:
    """Configuration for SAC algorithm."""
    state_dim: int = 35
    action_dim: int = 7
    hidden_dims: List[int] = field(default_factory=lambda: [256, 256])
    lr_actor: float = 3e-4
    lr_critic: float = 3e-4
    lr_alpha: float = 3e-4
    gamma: float = 0.99
    tau: float = 0.005
    alpha: float = 0.2  # Temperature parameter
    auto_alpha: bool = True
    buffer_size: int = 100000
    batch_size: int = 256


class SACAgent:
    """
    Soft Actor-Critic agent.

    SAC is an off-policy algorithm that maximizes both
    expected return and entropy for exploration.

    Research Value:
    - Maximum entropy RL for robust scheduling
    - Off-policy learning for sample efficiency
    - Automatic temperature tuning
    """

    def __init__(self, config: SACConfig):
        self.config = config
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu") if TORCH_AVAILABLE else None

        if TORCH_AVAILABLE:
            # Actor
            self.actor = ActorNetwork(
                config.state_dim,
                config.action_dim,
                config.hidden_dims,
                continuous=True
            ).to(self.device)

            # Twin critics
            self.critic = TwinCriticNetwork(
                config.state_dim,
                config.action_dim,
                config.hidden_dims
            ).to(self.device)

            self.critic_target = TwinCriticNetwork(
                config.state_dim,
                config.action_dim,
                config.hidden_dims
            ).to(self.device)
            self.critic_target.load_state_dict(self.critic.state_dict())

            # Optimizers
            self.actor_optimizer = optim.Adam(
                self.actor.parameters(), lr=config.lr_actor
            )
            self.critic_optimizer = optim.Adam(
                self.critic.parameters(), lr=config.lr_critic
            )

            # Entropy temperature
            self.log_alpha = torch.zeros(1, requires_grad=True, device=self.device)
            self.alpha = config.alpha
            self.target_entropy = -config.action_dim

            if config.auto_alpha:
                self.alpha_optimizer = optim.Adam(
                    [self.log_alpha], lr=config.lr_alpha
                )

        self.buffer = ReplayBuffer(config.buffer_size)
        self.training_stats: List[Dict[str, float]] = []

    def select_action(
        self,
        state: np.ndarray,
        deterministic: bool = False
    ) -> np.ndarray:
        """Select action from policy."""
        if not TORCH_AVAILABLE:
            return np.random.randn(self.config.action_dim)

        with torch.no_grad():
            state_tensor = torch.FloatTensor(state).unsqueeze(0).to(self.device)
            action, _, _ = self.actor.get_action(state_tensor, deterministic)

        return action.cpu().numpy().flatten()

    def store_transition(
        self,
        state: np.ndarray,
        action: np.ndarray,
        reward: float,
        next_state: np.ndarray,
        done: bool
    ) -> None:
        """Store transition in replay buffer."""
        self.buffer.push(Transition(state, action, reward, next_state, done))

    def update(self) -> Dict[str, float]:
        """Update actor and critic networks."""
        if not TORCH_AVAILABLE or len(self.buffer) < self.config.batch_size:
            return {}

        batch = self.buffer.sample(self.config.batch_size)

        states = torch.FloatTensor([t.state for t in batch]).to(self.device)
        actions = torch.FloatTensor([t.action for t in batch]).to(self.device)
        rewards = torch.FloatTensor([t.reward for t in batch]).unsqueeze(1).to(self.device)
        next_states = torch.FloatTensor([t.next_state for t in batch]).to(self.device)
        dones = torch.FloatTensor([t.done for t in batch]).unsqueeze(1).to(self.device)

        # Update critic
        with torch.no_grad():
            next_actions, next_log_probs, _ = self.actor.get_action(next_states)
            q1_target, q2_target = self.critic_target(next_states, next_actions)
            q_target = torch.min(q1_target, q2_target) - self.alpha * next_log_probs
            target_value = rewards + (1 - dones) * self.config.gamma * q_target

        q1, q2 = self.critic(states, actions)
        critic_loss = F.mse_loss(q1, target_value) + F.mse_loss(q2, target_value)

        self.critic_optimizer.zero_grad()
        critic_loss.backward()
        self.critic_optimizer.step()

        # Update actor
        new_actions, log_probs, _ = self.actor.get_action(states)
        q1_new, q2_new = self.critic(states, new_actions)
        q_new = torch.min(q1_new, q2_new)
        actor_loss = (self.alpha * log_probs - q_new).mean()

        self.actor_optimizer.zero_grad()
        actor_loss.backward()
        self.actor_optimizer.step()

        # Update alpha (temperature)
        alpha_loss = 0.0
        if self.config.auto_alpha:
            alpha_loss = -(self.log_alpha * (log_probs + self.target_entropy).detach()).mean()
            self.alpha_optimizer.zero_grad()
            alpha_loss.backward()
            self.alpha_optimizer.step()
            self.alpha = self.log_alpha.exp().item()

        # Soft update target networks
        for param, target_param in zip(
            self.critic.parameters(),
            self.critic_target.parameters()
        ):
            target_param.data.copy_(
                self.config.tau * param.data + (1 - self.config.tau) * target_param.data
            )

        stats = {
            'critic_loss': critic_loss.item(),
            'actor_loss': actor_loss.item(),
            'alpha': self.alpha,
            'alpha_loss': alpha_loss.item() if isinstance(alpha_loss, torch.Tensor) else alpha_loss,
        }
        self.training_stats.append(stats)
        return stats


# =============================================================================
# TD3 (Twin Delayed DDPG)
# =============================================================================

@dataclass
class TD3Config:
    """Configuration for TD3 algorithm."""
    state_dim: int = 35
    action_dim: int = 7
    hidden_dims: List[int] = field(default_factory=lambda: [256, 256])
    lr_actor: float = 3e-4
    lr_critic: float = 3e-4
    gamma: float = 0.99
    tau: float = 0.005
    policy_noise: float = 0.2
    noise_clip: float = 0.5
    policy_delay: int = 2
    exploration_noise: float = 0.1
    buffer_size: int = 100000
    batch_size: int = 256


class TD3Agent:
    """
    Twin Delayed DDPG agent.

    TD3 addresses overestimation in actor-critic methods through:
    - Twin critics (taking minimum)
    - Delayed policy updates
    - Target policy smoothing

    Research Value:
    - Addresses Q-value overestimation
    - Stable learning for scheduling
    - Deterministic policy for manufacturing
    """

    def __init__(self, config: TD3Config):
        self.config = config
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu") if TORCH_AVAILABLE else None

        if TORCH_AVAILABLE:
            # Actor
            self.actor = ActorNetwork(
                config.state_dim,
                config.action_dim,
                config.hidden_dims,
                continuous=True
            ).to(self.device)

            self.actor_target = ActorNetwork(
                config.state_dim,
                config.action_dim,
                config.hidden_dims,
                continuous=True
            ).to(self.device)
            self.actor_target.load_state_dict(self.actor.state_dict())

            # Twin critics
            self.critic = TwinCriticNetwork(
                config.state_dim,
                config.action_dim,
                config.hidden_dims
            ).to(self.device)

            self.critic_target = TwinCriticNetwork(
                config.state_dim,
                config.action_dim,
                config.hidden_dims
            ).to(self.device)
            self.critic_target.load_state_dict(self.critic.state_dict())

            # Optimizers
            self.actor_optimizer = optim.Adam(
                self.actor.parameters(), lr=config.lr_actor
            )
            self.critic_optimizer = optim.Adam(
                self.critic.parameters(), lr=config.lr_critic
            )

        self.buffer = ReplayBuffer(config.buffer_size)
        self.update_count = 0
        self.training_stats: List[Dict[str, float]] = []

    def select_action(
        self,
        state: np.ndarray,
        add_noise: bool = True
    ) -> np.ndarray:
        """Select action from policy."""
        if not TORCH_AVAILABLE:
            return np.random.randn(self.config.action_dim)

        with torch.no_grad():
            state_tensor = torch.FloatTensor(state).unsqueeze(0).to(self.device)
            action, _, _ = self.actor.get_action(state_tensor, deterministic=True)
            action = action.cpu().numpy().flatten()

        if add_noise:
            noise = np.random.normal(
                0, self.config.exploration_noise,
                size=self.config.action_dim
            )
            action = np.clip(action + noise, -1, 1)

        return action

    def store_transition(
        self,
        state: np.ndarray,
        action: np.ndarray,
        reward: float,
        next_state: np.ndarray,
        done: bool
    ) -> None:
        """Store transition in replay buffer."""
        self.buffer.push(Transition(state, action, reward, next_state, done))

    def update(self) -> Dict[str, float]:
        """Update actor and critic networks."""
        if not TORCH_AVAILABLE or len(self.buffer) < self.config.batch_size:
            return {}

        self.update_count += 1
        batch = self.buffer.sample(self.config.batch_size)

        states = torch.FloatTensor([t.state for t in batch]).to(self.device)
        actions = torch.FloatTensor([t.action for t in batch]).to(self.device)
        rewards = torch.FloatTensor([t.reward for t in batch]).unsqueeze(1).to(self.device)
        next_states = torch.FloatTensor([t.next_state for t in batch]).to(self.device)
        dones = torch.FloatTensor([t.done for t in batch]).unsqueeze(1).to(self.device)

        # Update critic
        with torch.no_grad():
            # Target policy smoothing
            next_actions, _, _ = self.actor_target.get_action(next_states, deterministic=True)
            noise = torch.clamp(
                torch.randn_like(next_actions) * self.config.policy_noise,
                -self.config.noise_clip,
                self.config.noise_clip
            )
            next_actions = torch.clamp(next_actions + noise, -1, 1)

            # Twin Q-values
            q1_target, q2_target = self.critic_target(next_states, next_actions)
            q_target = torch.min(q1_target, q2_target)
            target_value = rewards + (1 - dones) * self.config.gamma * q_target

        q1, q2 = self.critic(states, actions)
        critic_loss = F.mse_loss(q1, target_value) + F.mse_loss(q2, target_value)

        self.critic_optimizer.zero_grad()
        critic_loss.backward()
        self.critic_optimizer.step()

        # Delayed policy updates
        actor_loss = 0.0
        if self.update_count % self.config.policy_delay == 0:
            # Update actor
            new_actions, _, _ = self.actor.get_action(states, deterministic=True)
            actor_loss = -self.critic.q1_forward(states, new_actions).mean()

            self.actor_optimizer.zero_grad()
            actor_loss.backward()
            self.actor_optimizer.step()

            # Soft update target networks
            for param, target_param in zip(
                self.actor.parameters(),
                self.actor_target.parameters()
            ):
                target_param.data.copy_(
                    self.config.tau * param.data + (1 - self.config.tau) * target_param.data
                )

            for param, target_param in zip(
                self.critic.parameters(),
                self.critic_target.parameters()
            ):
                target_param.data.copy_(
                    self.config.tau * param.data + (1 - self.config.tau) * target_param.data
                )

        stats = {
            'critic_loss': critic_loss.item(),
            'actor_loss': actor_loss.item() if isinstance(actor_loss, torch.Tensor) else 0.0,
        }
        self.training_stats.append(stats)
        return stats


# =============================================================================
# Curriculum Learning
# =============================================================================

class CurriculumType(Enum):
    """Types of curriculum learning strategies."""
    LINEAR = auto()  # Linear difficulty increase
    SELF_PACED = auto()  # Agent-driven pacing
    TEACHER_STUDENT = auto()  # Teacher guides student
    REVERSE = auto()  # Start hard, go easy


@dataclass
class CurriculumConfig:
    """Configuration for curriculum learning."""
    curriculum_type: CurriculumType = CurriculumType.LINEAR
    initial_difficulty: float = 0.1
    max_difficulty: float = 1.0
    difficulty_increment: float = 0.1
    success_threshold: float = 0.8
    window_size: int = 10


class CurriculumLearning:
    """
    Curriculum Learning for manufacturing scheduling.

    Gradually increases problem difficulty as the agent improves.

    Research Value:
    - Faster learning for complex scheduling
    - Transfer learning capabilities
    - Robust policy learning
    """

    def __init__(self, config: CurriculumConfig):
        self.config = config
        self.current_difficulty = config.initial_difficulty
        self.success_history: deque = deque(maxlen=config.window_size)

    def get_difficulty(self) -> float:
        """Get current difficulty level."""
        return self.current_difficulty

    def update(self, success: bool) -> bool:
        """
        Update curriculum based on recent performance.

        Returns True if difficulty was increased.
        """
        self.success_history.append(1.0 if success else 0.0)

        if len(self.success_history) < self.config.window_size:
            return False

        success_rate = sum(self.success_history) / len(self.success_history)

        if self.config.curriculum_type == CurriculumType.LINEAR:
            if success_rate >= self.config.success_threshold:
                if self.current_difficulty < self.config.max_difficulty:
                    self.current_difficulty = min(
                        self.config.max_difficulty,
                        self.current_difficulty + self.config.difficulty_increment
                    )
                    self.success_history.clear()
                    return True

        elif self.config.curriculum_type == CurriculumType.SELF_PACED:
            # Adjust based on performance variance
            if len(self.success_history) > 1:
                variance = np.var(list(self.success_history))
                if variance < 0.1 and success_rate > 0.5:
                    self.current_difficulty = min(
                        self.config.max_difficulty,
                        self.current_difficulty + self.config.difficulty_increment
                    )
                    return True

        return False

    def generate_problem_params(self) -> Dict[str, Any]:
        """Generate problem parameters based on difficulty."""
        d = self.current_difficulty

        return {
            'n_jobs': int(5 + d * 20),  # 5-25 jobs
            'n_machines': int(2 + d * 8),  # 2-10 machines
            'due_date_tightness': 1.5 - d * 0.5,  # 1.5-1.0 (tighter = harder)
            'machine_breakdown_prob': d * 0.1,  # 0-10% breakdown
            'job_priority_variance': d,  # More varied priorities
            'processing_time_variance': 0.1 + d * 0.3,  # More varied times
        }


# =============================================================================
# Advanced RL Dispatcher Manager
# =============================================================================

class RLAlgorithm(Enum):
    """Available RL algorithms."""
    DQN = auto()
    PPO = auto()
    SAC = auto()
    TD3 = auto()


class AdvancedRLManager:
    """
    Manager for advanced RL scheduling algorithms.

    Provides unified interface for training and using
    different RL algorithms with curriculum learning.
    """

    def __init__(
        self,
        algorithm: RLAlgorithm = RLAlgorithm.PPO,
        state_dim: int = 35,
        action_dim: int = 7,
        use_curriculum: bool = True
    ):
        self.algorithm = algorithm
        self.state_dim = state_dim
        self.action_dim = action_dim

        # Create agent
        if algorithm == RLAlgorithm.PPO:
            config = PPOConfig(state_dim=state_dim, action_dim=action_dim)
            self.agent = PPOAgent(config)
        elif algorithm == RLAlgorithm.SAC:
            config = SACConfig(state_dim=state_dim, action_dim=action_dim)
            self.agent = SACAgent(config)
        elif algorithm == RLAlgorithm.TD3:
            config = TD3Config(state_dim=state_dim, action_dim=action_dim)
            self.agent = TD3Agent(config)
        else:
            raise ValueError(f"Unknown algorithm: {algorithm}")

        # Curriculum learning
        if use_curriculum:
            self.curriculum = CurriculumLearning(CurriculumConfig())
        else:
            self.curriculum = None

        self.training_history: List[Dict[str, Any]] = []

    def select_action(
        self,
        state: np.ndarray,
        deterministic: bool = False
    ) -> Union[int, np.ndarray]:
        """Select action using current policy."""
        if self.algorithm == RLAlgorithm.PPO:
            action, _, _ = self.agent.select_action(state, deterministic)
            return action
        else:
            return self.agent.select_action(state, not deterministic)

    def train_step(
        self,
        state: np.ndarray,
        action: Union[int, np.ndarray],
        reward: float,
        next_state: np.ndarray,
        done: bool,
        log_prob: Optional[float] = None,
        value: Optional[float] = None
    ) -> Dict[str, float]:
        """Perform single training step."""
        if self.algorithm == RLAlgorithm.PPO:
            self.agent.store_transition(state, action, reward, log_prob, value, done)
            if done:
                return self.agent.update()
        else:
            self.agent.store_transition(state, action, reward, next_state, done)
            return self.agent.update()

        return {}

    def update_curriculum(self, success: bool) -> None:
        """Update curriculum learning."""
        if self.curriculum:
            self.curriculum.update(success)

    def get_problem_difficulty(self) -> float:
        """Get current problem difficulty."""
        if self.curriculum:
            return self.curriculum.get_difficulty()
        return 1.0

    def save(self, path: str) -> None:
        """Save agent to disk."""
        if TORCH_AVAILABLE:
            state = {
                'algorithm': self.algorithm.name,
                'actor': self.agent.actor.state_dict() if hasattr(self.agent, 'actor') else None,
                'critic': self.agent.critic.state_dict() if hasattr(self.agent, 'critic') else None,
                'training_stats': self.agent.training_stats,
            }
            if self.curriculum:
                state['curriculum_difficulty'] = self.curriculum.current_difficulty

            torch.save(state, path)
            logger.info(f"Saved RL agent to {path}")

    def load(self, path: str) -> None:
        """Load agent from disk."""
        if TORCH_AVAILABLE:
            state = torch.load(path, map_location=self.agent.device)

            if hasattr(self.agent, 'actor') and state.get('actor'):
                self.agent.actor.load_state_dict(state['actor'])
            if hasattr(self.agent, 'critic') and state.get('critic'):
                self.agent.critic.load_state_dict(state['critic'])

            if self.curriculum and 'curriculum_difficulty' in state:
                self.curriculum.current_difficulty = state['curriculum_difficulty']

            logger.info(f"Loaded RL agent from {path}")


# Export public API
__all__ = [
    # Algorithms
    'PPOAgent',
    'PPOConfig',
    'SACAgent',
    'SACConfig',
    'TD3Agent',
    'TD3Config',
    # Curriculum
    'CurriculumLearning',
    'CurriculumConfig',
    'CurriculumType',
    # Manager
    'AdvancedRLManager',
    'RLAlgorithm',
    # Networks
    'ActorNetwork',
    'CriticNetwork',
    'TwinCriticNetwork',
    # Buffers
    'ReplayBuffer',
    'RolloutBuffer',
    'Transition',
]
