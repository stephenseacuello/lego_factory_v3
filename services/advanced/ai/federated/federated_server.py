"""
Federated Learning Server for Manufacturing.

This module implements the central server for federated learning:
- Client coordination and round management
- Model aggregation (FedAvg, FedProx, FedOpt)
- Secure aggregation protocols
- Adaptive client selection

Research Contributions:
- Manufacturing-aware client selection
- Quality-weighted aggregation
- Heterogeneous edge device support

References:
- McMahan, B., et al. (2017). Communication-Efficient Learning of Deep Networks
- Li, T., et al. (2020). Federated Optimization in Heterogeneous Networks
- Reddi, S., et al. (2021). Adaptive Federated Optimization
"""

import numpy as np
from typing import Dict, List, Optional, Tuple, Any, Union, Callable
from dataclasses import dataclass, field
from enum import Enum
from abc import ABC, abstractmethod
import logging
from datetime import datetime, timedelta
import hashlib
import secrets
from collections import defaultdict

logger = logging.getLogger(__name__)


class AggregationStrategy(Enum):
    """Aggregation strategies for federated learning."""
    FED_AVG = "fed_avg"  # Federated Averaging
    FED_PROX = "fed_prox"  # FedProx with proximal term
    FED_OPT = "fed_opt"  # Federated Optimization (Adam)
    FED_NOVA = "fed_nova"  # Normalized averaging
    WEIGHTED = "weighted"  # Quality-weighted aggregation
    ROBUST = "robust"  # Byzantine-robust aggregation


class ClientSelectionStrategy(Enum):
    """Strategies for selecting clients per round."""
    RANDOM = "random"
    ROUND_ROBIN = "round_robin"
    RESOURCE_AWARE = "resource_aware"
    CONTRIBUTION_BASED = "contribution_based"
    QUALITY_WEIGHTED = "quality_weighted"


class RoundStatus(Enum):
    """Status of a federated learning round."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    AGGREGATING = "aggregating"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class FederatedConfig:
    """Configuration for federated learning server."""
    aggregation_strategy: AggregationStrategy = AggregationStrategy.FED_AVG
    client_selection: ClientSelectionStrategy = ClientSelectionStrategy.RANDOM
    min_clients_per_round: int = 2
    max_clients_per_round: int = 10
    fraction_fit: float = 0.3  # Fraction of clients to select
    round_timeout: float = 300.0  # Seconds
    min_available_clients: int = 2  # Min clients to start training
    # FedProx parameters
    proximal_mu: float = 0.1
    # FedOpt parameters
    server_learning_rate: float = 1.0
    server_momentum: float = 0.9
    # Security
    enable_secure_aggregation: bool = False
    enable_differential_privacy: bool = False
    dp_epsilon: float = 1.0
    dp_delta: float = 1e-5
    # Manufacturing-specific
    quality_threshold: float = 0.8  # Min quality for client participation
    data_quality_weight: float = 0.5  # Weight for data quality in selection


@dataclass
class ClientInfo:
    """Information about a federated client."""
    client_id: str
    factory_id: str
    device_type: str
    compute_capability: float  # Relative compute power
    communication_bandwidth: float  # Mbps
    data_samples: int
    data_quality_score: float
    last_seen: datetime
    rounds_participated: int = 0
    contribution_score: float = 0.0
    is_available: bool = True

    @property
    def is_stale(self) -> bool:
        """Check if client hasn't been seen recently."""
        return (datetime.now() - self.last_seen).total_seconds() > 300

    def to_dict(self) -> Dict:
        return {
            'client_id': self.client_id,
            'factory_id': self.factory_id,
            'device_type': self.device_type,
            'compute_capability': self.compute_capability,
            'data_samples': self.data_samples,
            'data_quality_score': self.data_quality_score,
            'rounds_participated': self.rounds_participated,
            'contribution_score': self.contribution_score,
            'is_available': self.is_available
        }


@dataclass
class ModelUpdate:
    """Model update from a client."""
    client_id: str
    round_number: int
    parameters: Dict[str, np.ndarray]
    gradients: Optional[Dict[str, np.ndarray]]
    num_samples: int
    training_loss: float
    validation_metrics: Dict[str, float]
    training_time: float
    timestamp: datetime = field(default_factory=datetime.now)
    checksum: Optional[str] = None

    def compute_checksum(self) -> str:
        """Compute checksum for integrity verification."""
        param_bytes = b''
        for name in sorted(self.parameters.keys()):
            param_bytes += self.parameters[name].tobytes()
        return hashlib.sha256(param_bytes).hexdigest()

    def verify_checksum(self) -> bool:
        """Verify update integrity."""
        if self.checksum is None:
            return True
        return self.compute_checksum() == self.checksum


@dataclass
class FederatedRound:
    """A single round of federated learning."""
    round_number: int
    status: RoundStatus
    selected_clients: List[str]
    received_updates: Dict[str, ModelUpdate]
    start_time: datetime
    end_time: Optional[datetime]
    aggregated_model: Optional[Dict[str, np.ndarray]]
    round_metrics: Dict[str, float]

    @property
    def participation_rate(self) -> float:
        """Rate of client participation."""
        if not self.selected_clients:
            return 0.0
        return len(self.received_updates) / len(self.selected_clients)

    @property
    def duration(self) -> Optional[float]:
        """Round duration in seconds."""
        if self.end_time is None:
            return None
        return (self.end_time - self.start_time).total_seconds()

    def to_dict(self) -> Dict:
        return {
            'round_number': self.round_number,
            'status': self.status.value,
            'selected_clients': self.selected_clients,
            'n_updates_received': len(self.received_updates),
            'participation_rate': self.participation_rate,
            'start_time': self.start_time.isoformat(),
            'end_time': self.end_time.isoformat() if self.end_time else None,
            'duration': self.duration,
            'round_metrics': self.round_metrics
        }


class SecureAggregator:
    """
    Secure aggregation for privacy-preserving model updates.

    Implements masking-based secure aggregation where
    individual updates are hidden but sum is revealed.
    """

    def __init__(self, threshold: int = 2):
        self.threshold = threshold  # Min clients for reconstruction
        self._masks: Dict[str, np.ndarray] = {}
        self._secret_shares: Dict[str, List[np.ndarray]] = {}

    def generate_mask(
        self,
        client_id: str,
        shape: Tuple[int, ...],
        dtype: np.dtype = np.float32
    ) -> np.ndarray:
        """Generate random mask for client."""
        seed = int(hashlib.sha256(client_id.encode()).hexdigest()[:8], 16)
        rng = np.random.default_rng(seed)
        mask = rng.standard_normal(shape).astype(dtype)
        self._masks[client_id] = mask
        return mask

    def mask_update(
        self,
        client_id: str,
        parameters: Dict[str, np.ndarray],
        masks: Dict[str, np.ndarray]
    ) -> Dict[str, np.ndarray]:
        """Apply masks to model update."""
        masked = {}
        for name, param in parameters.items():
            if name in masks:
                masked[name] = param + masks[name]
            else:
                masked[name] = param
        return masked

    def aggregate_masked(
        self,
        masked_updates: List[Dict[str, np.ndarray]],
        n_samples: List[int]
    ) -> Dict[str, np.ndarray]:
        """Aggregate masked updates."""
        if not masked_updates:
            return {}

        total_samples = sum(n_samples)
        aggregated = {}

        for name in masked_updates[0].keys():
            weighted_sum = np.zeros_like(masked_updates[0][name])
            for update, n in zip(masked_updates, n_samples):
                weighted_sum += update[name] * (n / total_samples)
            aggregated[name] = weighted_sum

        return aggregated


class FederatedServer:
    """
    Federated Learning Server for Manufacturing Quality Models.

    Coordinates distributed training across factory edge devices
    while preserving data privacy.
    """

    def __init__(self, config: Optional[FederatedConfig] = None):
        self.config = config or FederatedConfig()

        # Global model
        self.global_model: Dict[str, np.ndarray] = {}
        self.model_version: int = 0

        # Client management
        self.clients: Dict[str, ClientInfo] = {}
        self.client_updates: Dict[str, List[ModelUpdate]] = defaultdict(list)

        # Round management
        self.current_round: Optional[FederatedRound] = None
        self.round_history: List[FederatedRound] = []

        # Aggregation
        self.secure_aggregator = SecureAggregator() if self.config.enable_secure_aggregation else None

        # Optimizer state (for FedOpt)
        self._momentum: Dict[str, np.ndarray] = {}
        self._velocity: Dict[str, np.ndarray] = {}

        logger.info(f"Federated server initialized with {self.config.aggregation_strategy.value}")

    def initialize_model(self, model_parameters: Dict[str, np.ndarray]):
        """Initialize global model parameters."""
        self.global_model = {k: v.copy() for k, v in model_parameters.items()}
        self.model_version = 0

        # Initialize optimizer state
        if self.config.aggregation_strategy == AggregationStrategy.FED_OPT:
            for name, param in self.global_model.items():
                self._momentum[name] = np.zeros_like(param)
                self._velocity[name] = np.zeros_like(param)

        logger.info(f"Global model initialized with {len(self.global_model)} parameters")

    def register_client(
        self,
        client_id: str,
        factory_id: str,
        device_type: str = "edge",
        compute_capability: float = 1.0,
        communication_bandwidth: float = 100.0,
        data_samples: int = 1000,
        data_quality_score: float = 0.9
    ) -> Dict:
        """Register a new client with the server."""
        client = ClientInfo(
            client_id=client_id,
            factory_id=factory_id,
            device_type=device_type,
            compute_capability=compute_capability,
            communication_bandwidth=communication_bandwidth,
            data_samples=data_samples,
            data_quality_score=data_quality_score,
            last_seen=datetime.now()
        )
        self.clients[client_id] = client

        logger.info(f"Client {client_id} registered from factory {factory_id}")

        return {
            'status': 'registered',
            'client_id': client_id,
            'current_model_version': self.model_version
        }

    def start_round(self) -> FederatedRound:
        """Start a new federated learning round."""
        # Check minimum clients
        available_clients = self._get_available_clients()
        if len(available_clients) < self.config.min_available_clients:
            raise ValueError(f"Not enough clients: {len(available_clients)} < {self.config.min_available_clients}")

        # Select clients for this round
        selected = self._select_clients(available_clients)

        round_number = len(self.round_history) + 1
        self.current_round = FederatedRound(
            round_number=round_number,
            status=RoundStatus.IN_PROGRESS,
            selected_clients=selected,
            received_updates={},
            start_time=datetime.now(),
            end_time=None,
            aggregated_model=None,
            round_metrics={}
        )

        logger.info(f"Started round {round_number} with {len(selected)} clients")

        return self.current_round

    def _get_available_clients(self) -> List[str]:
        """Get list of available clients."""
        available = []
        for client_id, info in self.clients.items():
            if info.is_available and not info.is_stale:
                if info.data_quality_score >= self.config.quality_threshold:
                    available.append(client_id)
        return available

    def _select_clients(self, available: List[str]) -> List[str]:
        """Select clients for the current round."""
        n_select = max(
            self.config.min_clients_per_round,
            min(
                int(len(available) * self.config.fraction_fit),
                self.config.max_clients_per_round
            )
        )

        if self.config.client_selection == ClientSelectionStrategy.RANDOM:
            return list(np.random.choice(available, size=min(n_select, len(available)), replace=False))

        elif self.config.client_selection == ClientSelectionStrategy.QUALITY_WEIGHTED:
            # Weight by data quality
            weights = np.array([
                self.clients[cid].data_quality_score * self.clients[cid].data_samples
                for cid in available
            ])
            weights = weights / weights.sum()
            return list(np.random.choice(
                available,
                size=min(n_select, len(available)),
                replace=False,
                p=weights
            ))

        elif self.config.client_selection == ClientSelectionStrategy.CONTRIBUTION_BASED:
            # Sort by contribution score
            sorted_clients = sorted(
                available,
                key=lambda cid: self.clients[cid].contribution_score,
                reverse=True
            )
            # Mix top contributors with some randomness
            top_half = sorted_clients[:len(sorted_clients)//2]
            random_half = np.random.choice(
                sorted_clients[len(sorted_clients)//2:],
                size=min(n_select//2, len(sorted_clients)//2),
                replace=False
            ).tolist()
            selected = top_half[:n_select//2] + random_half
            return selected[:n_select]

        else:
            return available[:n_select]

    def receive_update(self, update: ModelUpdate) -> Dict:
        """Receive model update from a client."""
        if self.current_round is None:
            return {'status': 'error', 'message': 'No active round'}

        if update.client_id not in self.current_round.selected_clients:
            return {'status': 'error', 'message': 'Client not selected for this round'}

        # Verify update integrity
        if not update.verify_checksum():
            return {'status': 'error', 'message': 'Checksum verification failed'}

        # Store update
        self.current_round.received_updates[update.client_id] = update
        self.client_updates[update.client_id].append(update)

        # Update client info
        if update.client_id in self.clients:
            self.clients[update.client_id].last_seen = datetime.now()
            self.clients[update.client_id].rounds_participated += 1

        logger.info(f"Received update from {update.client_id} for round {update.round_number}")

        # Check if we have enough updates to aggregate
        if len(self.current_round.received_updates) >= len(self.current_round.selected_clients):
            self._trigger_aggregation()

        return {
            'status': 'accepted',
            'round': self.current_round.round_number,
            'updates_received': len(self.current_round.received_updates)
        }

    def _trigger_aggregation(self):
        """Trigger model aggregation when enough updates received."""
        if self.current_round is None:
            return

        self.current_round.status = RoundStatus.AGGREGATING
        logger.info(f"Triggering aggregation for round {self.current_round.round_number}")

        try:
            # Aggregate updates
            aggregated = self._aggregate_updates()

            # Update global model
            self._update_global_model(aggregated)

            # Compute round metrics
            self._compute_round_metrics()

            # Complete round
            self.current_round.status = RoundStatus.COMPLETED
            self.current_round.end_time = datetime.now()
            self.current_round.aggregated_model = self.global_model.copy()

            self.round_history.append(self.current_round)
            self.model_version += 1

            logger.info(f"Round {self.current_round.round_number} completed. Model version: {self.model_version}")

        except Exception as e:
            logger.error(f"Aggregation failed: {e}")
            self.current_round.status = RoundStatus.FAILED
            self.current_round.end_time = datetime.now()
            self.round_history.append(self.current_round)

    def _aggregate_updates(self) -> Dict[str, np.ndarray]:
        """Aggregate client updates based on strategy."""
        updates = list(self.current_round.received_updates.values())

        if not updates:
            return self.global_model.copy()

        if self.config.aggregation_strategy == AggregationStrategy.FED_AVG:
            return self._federated_averaging(updates)
        elif self.config.aggregation_strategy == AggregationStrategy.FED_PROX:
            return self._federated_prox(updates)
        elif self.config.aggregation_strategy == AggregationStrategy.FED_OPT:
            return self._federated_opt(updates)
        elif self.config.aggregation_strategy == AggregationStrategy.WEIGHTED:
            return self._quality_weighted_aggregation(updates)
        elif self.config.aggregation_strategy == AggregationStrategy.ROBUST:
            return self._robust_aggregation(updates)
        else:
            return self._federated_averaging(updates)

    def _federated_averaging(
        self,
        updates: List[ModelUpdate]
    ) -> Dict[str, np.ndarray]:
        """Standard FedAvg aggregation."""
        total_samples = sum(u.num_samples for u in updates)
        aggregated = {}

        for name in updates[0].parameters.keys():
            weighted_sum = np.zeros_like(updates[0].parameters[name])
            for update in updates:
                weight = update.num_samples / total_samples
                weighted_sum += update.parameters[name] * weight
            aggregated[name] = weighted_sum

        return aggregated

    def _federated_prox(
        self,
        updates: List[ModelUpdate]
    ) -> Dict[str, np.ndarray]:
        """FedProx aggregation with proximal regularization."""
        # FedProx modifies client training, but server-side is same as FedAvg
        # The proximal term is applied during client training
        return self._federated_averaging(updates)

    def _federated_opt(
        self,
        updates: List[ModelUpdate]
    ) -> Dict[str, np.ndarray]:
        """FedOpt with server-side optimization."""
        # Compute pseudo-gradient (difference from global model)
        avg_update = self._federated_averaging(updates)

        aggregated = {}
        for name in self.global_model.keys():
            # Pseudo-gradient
            delta = avg_update[name] - self.global_model[name]

            # Momentum update
            self._momentum[name] = (
                self.config.server_momentum * self._momentum[name] +
                (1 - self.config.server_momentum) * delta
            )

            # Apply update with server learning rate
            aggregated[name] = (
                self.global_model[name] +
                self.config.server_learning_rate * self._momentum[name]
            )

        return aggregated

    def _quality_weighted_aggregation(
        self,
        updates: List[ModelUpdate]
    ) -> Dict[str, np.ndarray]:
        """Weight by both sample count and data quality."""
        weights = []
        for update in updates:
            client = self.clients.get(update.client_id)
            quality = client.data_quality_score if client else 1.0
            weight = update.num_samples * (
                self.config.data_quality_weight * quality +
                (1 - self.config.data_quality_weight)
            )
            weights.append(weight)

        total_weight = sum(weights)
        aggregated = {}

        for name in updates[0].parameters.keys():
            weighted_sum = np.zeros_like(updates[0].parameters[name])
            for update, weight in zip(updates, weights):
                weighted_sum += update.parameters[name] * (weight / total_weight)
            aggregated[name] = weighted_sum

        return aggregated

    def _robust_aggregation(
        self,
        updates: List[ModelUpdate]
    ) -> Dict[str, np.ndarray]:
        """Byzantine-robust aggregation using coordinate-wise median."""
        aggregated = {}

        for name in updates[0].parameters.keys():
            stacked = np.stack([u.parameters[name] for u in updates], axis=0)
            # Coordinate-wise median for robustness
            aggregated[name] = np.median(stacked, axis=0)

        return aggregated

    def _update_global_model(self, aggregated: Dict[str, np.ndarray]):
        """Update global model with aggregated parameters."""
        self.global_model = {k: v.copy() for k, v in aggregated.items()}

    def _compute_round_metrics(self):
        """Compute metrics for the current round."""
        updates = list(self.current_round.received_updates.values())

        if not updates:
            return

        # Average training loss
        avg_loss = np.mean([u.training_loss for u in updates])

        # Average validation metrics
        val_metrics = defaultdict(list)
        for update in updates:
            for metric, value in update.validation_metrics.items():
                val_metrics[metric].append(value)

        avg_val_metrics = {k: np.mean(v) for k, v in val_metrics.items()}

        # Total samples used
        total_samples = sum(u.num_samples for u in updates)

        # Average training time
        avg_training_time = np.mean([u.training_time for u in updates])

        self.current_round.round_metrics = {
            'average_training_loss': float(avg_loss),
            'total_samples': total_samples,
            'average_training_time': float(avg_training_time),
            'participation_rate': self.current_round.participation_rate,
            **{f'avg_{k}': float(v) for k, v in avg_val_metrics.items()}
        }

    def get_global_model(self) -> Tuple[Dict[str, np.ndarray], int]:
        """Get current global model and version."""
        return self.global_model.copy(), self.model_version

    def get_training_config_for_client(self, client_id: str) -> Dict:
        """Get training configuration for a specific client."""
        base_config = {
            'model_version': self.model_version,
            'round_number': len(self.round_history) + 1,
            'local_epochs': 5,
            'local_batch_size': 32,
            'learning_rate': 0.01
        }

        # FedProx specific
        if self.config.aggregation_strategy == AggregationStrategy.FED_PROX:
            base_config['proximal_mu'] = self.config.proximal_mu

        # Differential privacy
        if self.config.enable_differential_privacy:
            base_config['dp_enabled'] = True
            base_config['dp_epsilon'] = self.config.dp_epsilon
            base_config['dp_delta'] = self.config.dp_delta

        return base_config

    def get_round_status(self) -> Dict:
        """Get current round status."""
        if self.current_round is None:
            return {
                'status': 'no_active_round',
                'total_rounds': len(self.round_history),
                'model_version': self.model_version
            }

        return {
            'round': self.current_round.to_dict(),
            'total_rounds': len(self.round_history),
            'model_version': self.model_version
        }

    def get_client_statistics(self) -> Dict:
        """Get statistics about registered clients."""
        if not self.clients:
            return {'n_clients': 0}

        available = [c for c in self.clients.values() if c.is_available and not c.is_stale]

        return {
            'n_clients': len(self.clients),
            'n_available': len(available),
            'total_samples': sum(c.data_samples for c in self.clients.values()),
            'avg_data_quality': float(np.mean([c.data_quality_score for c in self.clients.values()])),
            'factories': list(set(c.factory_id for c in self.clients.values())),
            'device_types': list(set(c.device_type for c in self.clients.values()))
        }

    def get_training_history(self) -> List[Dict]:
        """Get history of all training rounds."""
        return [r.to_dict() for r in self.round_history]


class ManufacturingFederatedServer(FederatedServer):
    """
    Manufacturing-specific federated learning server.

    Adds domain-specific features:
    - Factory-aware client selection
    - Quality-based weighting
    - Production-aware scheduling
    """

    def __init__(self, config: Optional[FederatedConfig] = None):
        super().__init__(config)

        # Manufacturing context
        self.factory_metadata: Dict[str, Dict] = {}
        self.production_schedules: Dict[str, List] = {}

    def set_factory_metadata(
        self,
        factory_id: str,
        metadata: Dict
    ):
        """Set metadata for a factory."""
        self.factory_metadata[factory_id] = metadata

    def set_production_schedule(
        self,
        factory_id: str,
        schedule: List[Dict]
    ):
        """Set production schedule to avoid training during peak times."""
        self.production_schedules[factory_id] = schedule

    def is_factory_available(self, factory_id: str) -> bool:
        """Check if factory is available for training (not in peak production)."""
        if factory_id not in self.production_schedules:
            return True

        now = datetime.now()
        for slot in self.production_schedules[factory_id]:
            if slot.get('start') <= now <= slot.get('end'):
                if slot.get('peak', False):
                    return False

        return True

    def _get_available_clients(self) -> List[str]:
        """Get available clients considering production schedules."""
        available = super()._get_available_clients()

        # Filter by factory availability
        return [
            cid for cid in available
            if self.is_factory_available(self.clients[cid].factory_id)
        ]

    def generate_federated_report(self) -> Dict:
        """Generate comprehensive federated learning report."""
        return {
            'server_status': {
                'model_version': self.model_version,
                'total_rounds': len(self.round_history),
                'aggregation_strategy': self.config.aggregation_strategy.value
            },
            'client_statistics': self.get_client_statistics(),
            'factory_participation': self._compute_factory_participation(),
            'training_progress': self._compute_training_progress(),
            'recommendations': self._generate_recommendations()
        }

    def _compute_factory_participation(self) -> Dict[str, Dict]:
        """Compute participation statistics per factory."""
        factory_stats = defaultdict(lambda: {
            'clients': 0,
            'rounds_participated': 0,
            'total_samples': 0
        })

        for client in self.clients.values():
            stats = factory_stats[client.factory_id]
            stats['clients'] += 1
            stats['rounds_participated'] += client.rounds_participated
            stats['total_samples'] += client.data_samples

        return dict(factory_stats)

    def _compute_training_progress(self) -> Dict:
        """Compute training progress metrics."""
        if not self.round_history:
            return {'status': 'no_training_yet'}

        losses = [r.round_metrics.get('average_training_loss', float('inf'))
                  for r in self.round_history]

        return {
            'rounds_completed': len(self.round_history),
            'initial_loss': losses[0] if losses else None,
            'current_loss': losses[-1] if losses else None,
            'loss_improvement': (losses[0] - losses[-1]) / losses[0] if losses and losses[0] > 0 else 0,
            'convergence_rate': self._estimate_convergence_rate(losses)
        }

    def _estimate_convergence_rate(self, losses: List[float]) -> float:
        """Estimate convergence rate from loss history."""
        if len(losses) < 2:
            return 0.0

        # Simple exponential decay fit
        improvements = []
        for i in range(1, len(losses)):
            if losses[i-1] > 0:
                improvements.append((losses[i-1] - losses[i]) / losses[i-1])

        return float(np.mean(improvements)) if improvements else 0.0

    def _generate_recommendations(self) -> List[str]:
        """Generate recommendations for improving federated training."""
        recommendations = []

        stats = self.get_client_statistics()

        if stats['n_available'] < self.config.min_clients_per_round:
            recommendations.append(
                f"Insufficient available clients ({stats['n_available']}). "
                f"Consider lowering quality threshold or adding more edge devices."
            )

        if stats.get('avg_data_quality', 1.0) < 0.7:
            recommendations.append(
                "Average data quality is low. Consider implementing data preprocessing on edge devices."
            )

        if len(self.round_history) > 5:
            recent_participation = np.mean([
                r.participation_rate for r in self.round_history[-5:]
            ])
            if recent_participation < 0.8:
                recommendations.append(
                    f"Recent participation rate ({recent_participation:.1%}) is low. "
                    "Check network connectivity and client availability."
                )

        if not recommendations:
            recommendations.append("Federated learning is progressing normally.")

        return recommendations
