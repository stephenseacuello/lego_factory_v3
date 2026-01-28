"""
Multi-Armed Bandit for Adaptive Experimentation.

LEGO MCP v6.0 World-Class Manufacturing Research Platform
Phase 6: Research Platform Infrastructure

Implements bandit algorithms for adaptive manufacturing experiments:
- Thompson Sampling
- Upper Confidence Bound (UCB)
- Epsilon-Greedy
- Contextual Bandits
"""

from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional, Tuple, Callable
from datetime import datetime
from enum import Enum
from abc import ABC, abstractmethod
import math
import random
import uuid


class BanditAlgorithm(Enum):
    """Available bandit algorithms."""
    EPSILON_GREEDY = "epsilon_greedy"
    UCB1 = "ucb1"
    THOMPSON_SAMPLING = "thompson_sampling"
    EXP3 = "exp3"  # Adversarial
    CONTEXTUAL_LINEAR = "contextual_linear"


class RewardType(Enum):
    """Type of reward distribution."""
    BERNOULLI = "bernoulli"  # Binary success/failure
    GAUSSIAN = "gaussian"  # Continuous normal
    BOUNDED = "bounded"  # [0, 1] continuous


@dataclass
class Arm:
    """A single arm (variant) in the bandit."""
    arm_id: str
    name: str
    description: str

    # Statistics
    pulls: int = 0
    total_reward: float = 0.0
    reward_squared: float = 0.0

    # For Thompson Sampling (Beta distribution parameters)
    alpha: float = 1.0  # Successes + 1
    beta: float = 1.0   # Failures + 1

    # Metadata
    created_at: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def mean_reward(self) -> float:
        """Calculate mean reward."""
        if self.pulls == 0:
            return 0.0
        return self.total_reward / self.pulls

    @property
    def variance(self) -> float:
        """Calculate reward variance."""
        if self.pulls < 2:
            return 0.0
        mean = self.mean_reward
        return (self.reward_squared / self.pulls) - mean ** 2

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "arm_id": self.arm_id,
            "name": self.name,
            "description": self.description,
            "pulls": self.pulls,
            "mean_reward": self.mean_reward,
            "variance": self.variance,
            "alpha": self.alpha,
            "beta": self.beta,
        }


@dataclass
class BanditConfig:
    """Configuration for multi-armed bandit experiment."""
    bandit_id: str
    name: str
    description: str
    algorithm: BanditAlgorithm
    reward_type: RewardType

    # Algorithm parameters
    epsilon: float = 0.1  # For epsilon-greedy
    exploration_bonus: float = 2.0  # For UCB

    # Experiment settings
    min_samples_per_arm: int = 10
    max_total_samples: Optional[int] = None

    # Early stopping
    enable_early_stopping: bool = True
    significance_threshold: float = 0.95

    # Metadata
    created_at: datetime = field(default_factory=datetime.now)
    created_by: str = "system"


@dataclass
class BanditResult:
    """Results from bandit experiment."""
    bandit_id: str
    best_arm_id: str
    best_arm_mean: float

    # All arm statistics
    arm_stats: List[Dict[str, Any]]

    # Experiment summary
    total_pulls: int
    total_reward: float
    regret_estimate: float

    # Confidence
    probability_best: Dict[str, float]

    # Metadata
    analyzed_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "bandit_id": self.bandit_id,
            "best_arm_id": self.best_arm_id,
            "best_arm_mean": self.best_arm_mean,
            "arm_stats": self.arm_stats,
            "total_pulls": self.total_pulls,
            "total_reward": self.total_reward,
            "regret_estimate": self.regret_estimate,
            "probability_best": self.probability_best,
            "analyzed_at": self.analyzed_at.isoformat(),
        }


class BanditStrategy(ABC):
    """Abstract base class for bandit strategies."""

    @abstractmethod
    def select_arm(self, arms: List[Arm], t: int) -> Arm:
        """Select an arm to pull."""
        pass

    @abstractmethod
    def update(self, arm: Arm, reward: float):
        """Update arm statistics after observing reward."""
        pass


class EpsilonGreedy(BanditStrategy):
    """Epsilon-greedy strategy."""

    def __init__(self, epsilon: float = 0.1, decay: bool = False):
        self.epsilon = epsilon
        self.decay = decay

    def select_arm(self, arms: List[Arm], t: int) -> Arm:
        """Select arm: random with probability epsilon, best otherwise."""
        eps = self.epsilon / math.sqrt(t + 1) if self.decay else self.epsilon

        if random.random() < eps:
            return random.choice(arms)

        return max(arms, key=lambda a: a.mean_reward)

    def update(self, arm: Arm, reward: float):
        """Update arm with observed reward."""
        arm.pulls += 1
        arm.total_reward += reward
        arm.reward_squared += reward ** 2


class UCB1(BanditStrategy):
    """Upper Confidence Bound strategy."""

    def __init__(self, exploration_bonus: float = 2.0):
        self.c = exploration_bonus

    def select_arm(self, arms: List[Arm], t: int) -> Arm:
        """Select arm with highest UCB value."""
        # Pull each arm at least once
        for arm in arms:
            if arm.pulls == 0:
                return arm

        def ucb_value(arm: Arm) -> float:
            exploitation = arm.mean_reward
            exploration = math.sqrt(self.c * math.log(t + 1) / arm.pulls)
            return exploitation + exploration

        return max(arms, key=ucb_value)

    def update(self, arm: Arm, reward: float):
        """Update arm with observed reward."""
        arm.pulls += 1
        arm.total_reward += reward
        arm.reward_squared += reward ** 2


class ThompsonSampling(BanditStrategy):
    """Thompson Sampling strategy for Bernoulli rewards."""

    def select_arm(self, arms: List[Arm], t: int) -> Arm:
        """Select arm by sampling from posterior distributions."""
        samples = []
        for arm in arms:
            # Sample from Beta distribution
            sample = self._sample_beta(arm.alpha, arm.beta)
            samples.append((arm, sample))

        return max(samples, key=lambda x: x[1])[0]

    def update(self, arm: Arm, reward: float):
        """Update posterior with observed reward."""
        arm.pulls += 1
        arm.total_reward += reward
        arm.reward_squared += reward ** 2

        # Update Beta parameters
        if reward > 0.5:  # Success
            arm.alpha += 1
        else:  # Failure
            arm.beta += 1

    def _sample_beta(self, alpha: float, beta: float) -> float:
        """Sample from Beta distribution using gamma samples."""
        x = self._sample_gamma(alpha)
        y = self._sample_gamma(beta)
        return x / (x + y) if (x + y) > 0 else 0.5

    def _sample_gamma(self, shape: float) -> float:
        """Sample from Gamma distribution (Marsaglia and Tsang's method)."""
        if shape < 1:
            return self._sample_gamma(shape + 1) * (random.random() ** (1 / shape))

        d = shape - 1/3
        c = 1 / math.sqrt(9 * d)

        while True:
            x = random.gauss(0, 1)
            v = (1 + c * x) ** 3

            if v > 0:
                u = random.random()
                if u < 1 - 0.0331 * (x ** 2) ** 2:
                    return d * v
                if math.log(u) < 0.5 * x ** 2 + d * (1 - v + math.log(v)):
                    return d * v


class EXP3(BanditStrategy):
    """EXP3 algorithm for adversarial bandits."""

    def __init__(self, gamma: float = 0.1):
        self.gamma = gamma
        self.weights: Dict[str, float] = {}

    def select_arm(self, arms: List[Arm], t: int) -> Arm:
        """Select arm according to mixed strategy."""
        # Initialize weights
        for arm in arms:
            if arm.arm_id not in self.weights:
                self.weights[arm.arm_id] = 1.0

        # Calculate probabilities
        total_weight = sum(self.weights[a.arm_id] for a in arms)
        k = len(arms)

        probs = []
        for arm in arms:
            p = (1 - self.gamma) * (self.weights[arm.arm_id] / total_weight) + self.gamma / k
            probs.append((arm, p))

        # Sample according to probabilities
        r = random.random()
        cumsum = 0
        for arm, p in probs:
            cumsum += p
            if r <= cumsum:
                return arm

        return arms[-1]

    def update(self, arm: Arm, reward: float):
        """Update weights with observed reward."""
        arm.pulls += 1
        arm.total_reward += reward

        # Update weight with importance-weighted reward
        k = len(self.weights)
        total_weight = sum(self.weights.values())
        p = (1 - self.gamma) * (self.weights[arm.arm_id] / total_weight) + self.gamma / k

        estimated_reward = reward / p
        self.weights[arm.arm_id] *= math.exp(self.gamma * estimated_reward / k)


class MultiArmedBandit:
    """
    Multi-Armed Bandit for adaptive manufacturing experiments.

    Use cases:
    - Parameter optimization (temperature, speed, etc.)
    - Material selection
    - Process variant comparison
    - Dynamic resource allocation
    """

    def __init__(self, config: BanditConfig):
        self.config = config
        self.arms: Dict[str, Arm] = {}
        self.history: List[Tuple[str, float, datetime]] = []

        # Initialize strategy
        self.strategy = self._create_strategy()

    def _create_strategy(self) -> BanditStrategy:
        """Create the appropriate bandit strategy."""
        if self.config.algorithm == BanditAlgorithm.EPSILON_GREEDY:
            return EpsilonGreedy(epsilon=self.config.epsilon)
        elif self.config.algorithm == BanditAlgorithm.UCB1:
            return UCB1(exploration_bonus=self.config.exploration_bonus)
        elif self.config.algorithm == BanditAlgorithm.THOMPSON_SAMPLING:
            return ThompsonSampling()
        elif self.config.algorithm == BanditAlgorithm.EXP3:
            return EXP3()
        else:
            raise ValueError(f"Unknown algorithm: {self.config.algorithm}")

    def add_arm(
        self,
        name: str,
        description: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Arm:
        """Add a new arm to the bandit."""
        arm = Arm(
            arm_id=str(uuid.uuid4()),
            name=name,
            description=description,
            metadata=metadata or {},
        )
        self.arms[arm.arm_id] = arm
        return arm

    def select_arm(self) -> Arm:
        """Select an arm to pull."""
        if not self.arms:
            raise ValueError("No arms added to bandit")

        t = sum(arm.pulls for arm in self.arms.values())
        arms_list = list(self.arms.values())

        return self.strategy.select_arm(arms_list, t)

    def update(self, arm_id: str, reward: float):
        """Update arm with observed reward."""
        if arm_id not in self.arms:
            raise ValueError(f"Arm {arm_id} not found")

        arm = self.arms[arm_id]
        self.strategy.update(arm, reward)

        # Record history
        self.history.append((arm_id, reward, datetime.now()))

    def pull_and_update(self, reward_func: Callable[[Arm], float]) -> Tuple[Arm, float]:
        """Select arm, get reward, and update."""
        arm = self.select_arm()
        reward = reward_func(arm)
        self.update(arm.arm_id, reward)
        return arm, reward

    def get_best_arm(self) -> Arm:
        """Get the arm with highest estimated mean reward."""
        if not self.arms:
            raise ValueError("No arms in bandit")
        return max(self.arms.values(), key=lambda a: a.mean_reward)

    def get_results(self) -> BanditResult:
        """Get current bandit results."""
        if not self.arms:
            raise ValueError("No arms in bandit")

        best_arm = self.get_best_arm()
        total_pulls = sum(arm.pulls for arm in self.arms.values())
        total_reward = sum(arm.total_reward for arm in self.arms.values())

        # Estimate regret (compared to always pulling best arm)
        regret = best_arm.mean_reward * total_pulls - total_reward

        # Calculate probability each arm is best (via simulation)
        prob_best = self._calculate_probability_best()

        return BanditResult(
            bandit_id=self.config.bandit_id,
            best_arm_id=best_arm.arm_id,
            best_arm_mean=best_arm.mean_reward,
            arm_stats=[arm.to_dict() for arm in self.arms.values()],
            total_pulls=total_pulls,
            total_reward=total_reward,
            regret_estimate=regret,
            probability_best=prob_best,
        )

    def _calculate_probability_best(self, n_simulations: int = 1000) -> Dict[str, float]:
        """Calculate probability each arm is the best via simulation."""
        if not self.arms:
            return {}

        wins = {arm_id: 0 for arm_id in self.arms}

        for _ in range(n_simulations):
            samples = {}
            for arm_id, arm in self.arms.items():
                if self.config.reward_type == RewardType.BERNOULLI:
                    # Sample from Beta posterior
                    sample = self._sample_beta(arm.alpha, arm.beta)
                else:
                    # Sample from Normal posterior
                    if arm.pulls > 0:
                        mean = arm.mean_reward
                        std = math.sqrt(arm.variance / arm.pulls) if arm.variance > 0 else 0.1
                        sample = random.gauss(mean, std)
                    else:
                        sample = random.random()
                samples[arm_id] = sample

            best_arm_id = max(samples, key=samples.get)
            wins[best_arm_id] += 1

        return {arm_id: count / n_simulations for arm_id, count in wins.items()}

    def _sample_beta(self, alpha: float, beta: float) -> float:
        """Sample from Beta distribution."""
        x = random.gammavariate(alpha, 1)
        y = random.gammavariate(beta, 1)
        return x / (x + y) if (x + y) > 0 else 0.5

    def should_stop_early(self) -> Tuple[bool, Optional[str]]:
        """Check if experiment should stop early."""
        if not self.config.enable_early_stopping:
            return False, None

        # Check minimum samples
        min_pulls = min(arm.pulls for arm in self.arms.values())
        if min_pulls < self.config.min_samples_per_arm:
            return False, None

        # Check if one arm is clearly best
        prob_best = self._calculate_probability_best()
        best_prob = max(prob_best.values())

        if best_prob >= self.config.significance_threshold:
            best_arm_id = max(prob_best, key=prob_best.get)
            return True, f"Arm {best_arm_id} has {best_prob:.1%} probability of being best"

        # Check max samples
        total_pulls = sum(arm.pulls for arm in self.arms.values())
        if self.config.max_total_samples and total_pulls >= self.config.max_total_samples:
            return True, "Maximum samples reached"

        return False, None


class ContextualBandit(MultiArmedBandit):
    """
    Contextual bandit for context-dependent arm selection.

    Uses linear model to estimate rewards based on context features.
    """

    def __init__(self, config: BanditConfig, n_features: int):
        super().__init__(config)
        self.n_features = n_features

        # Linear model parameters per arm
        self.theta: Dict[str, List[float]] = {}
        self.covariance: Dict[str, List[List[float]]] = {}

    def add_arm(
        self,
        name: str,
        description: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Arm:
        """Add arm with initialized linear model."""
        arm = super().add_arm(name, description, metadata)

        # Initialize theta to zeros
        self.theta[arm.arm_id] = [0.0] * self.n_features

        # Initialize covariance to identity
        self.covariance[arm.arm_id] = [
            [1.0 if i == j else 0.0 for j in range(self.n_features)]
            for i in range(self.n_features)
        ]

        return arm

    def select_arm_with_context(self, context: List[float]) -> Arm:
        """Select arm based on context features."""
        if len(context) != self.n_features:
            raise ValueError(f"Context must have {self.n_features} features")

        best_arm = None
        best_ucb = float("-inf")

        for arm_id, arm in self.arms.items():
            # Predicted reward
            theta = self.theta[arm_id]
            predicted = sum(t * c for t, c in zip(theta, context))

            # Exploration bonus
            cov = self.covariance[arm_id]
            variance = sum(
                context[i] * sum(cov[i][j] * context[j] for j in range(self.n_features))
                for i in range(self.n_features)
            )
            bonus = self.config.exploration_bonus * math.sqrt(variance)

            ucb = predicted + bonus

            if ucb > best_ucb:
                best_ucb = ucb
                best_arm = arm

        return best_arm

    def update_with_context(self, arm_id: str, context: List[float], reward: float):
        """Update arm's model with observed context and reward."""
        if arm_id not in self.arms:
            raise ValueError(f"Arm {arm_id} not found")

        # Update base statistics
        self.update(arm_id, reward)

        # Update linear model (simplified ridge regression update)
        theta = self.theta[arm_id]

        # Predicted reward
        predicted = sum(t * c for t, c in zip(theta, context))
        error = reward - predicted

        # Gradient update with learning rate
        lr = 0.1
        for i in range(self.n_features):
            theta[i] += lr * error * context[i]


# Factory functions
def create_bandit(
    name: str,
    description: str,
    algorithm: BanditAlgorithm = BanditAlgorithm.THOMPSON_SAMPLING,
    reward_type: RewardType = RewardType.BERNOULLI,
) -> MultiArmedBandit:
    """Create a multi-armed bandit experiment."""
    config = BanditConfig(
        bandit_id=str(uuid.uuid4()),
        name=name,
        description=description,
        algorithm=algorithm,
        reward_type=reward_type,
    )
    return MultiArmedBandit(config)


def create_contextual_bandit(
    name: str,
    description: str,
    n_features: int,
) -> ContextualBandit:
    """Create a contextual bandit experiment."""
    config = BanditConfig(
        bandit_id=str(uuid.uuid4()),
        name=name,
        description=description,
        algorithm=BanditAlgorithm.CONTEXTUAL_LINEAR,
        reward_type=RewardType.GAUSSIAN,
    )
    return ContextualBandit(config, n_features)
