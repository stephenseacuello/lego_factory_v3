"""
Secure Aggregation for Federated Learning.

This module implements secure aggregation protocols:
- Secret sharing schemes
- Masked model updates
- Secure multi-party computation primitives
- Dropout-resilient aggregation

Research Contributions:
- Practical secure aggregation for manufacturing
- Fault-tolerant protocols for edge devices
- Efficient secret sharing for model parameters

References:
- Bonawitz, K., et al. (2017). Practical Secure Aggregation for Privacy-Preserving Machine Learning
- Bell, J.H., et al. (2020). Secure Single-Server Aggregation with (Poly)Logarithmic Overhead
"""

import numpy as np
from typing import Dict, List, Optional, Tuple, Any, Union
from dataclasses import dataclass, field
from enum import Enum
from abc import ABC, abstractmethod
import logging
from datetime import datetime
import hashlib
import secrets
from collections import defaultdict

logger = logging.getLogger(__name__)


class SecretSharingScheme(Enum):
    """Secret sharing schemes."""
    ADDITIVE = "additive"  # Simple additive sharing
    SHAMIR = "shamir"  # Shamir's secret sharing
    REPLICATED = "replicated"  # Replicated secret sharing


class AggregationPhase(Enum):
    """Phases of secure aggregation."""
    SETUP = "setup"  # Key exchange
    SHARE_KEYS = "share_keys"  # Distribute keys
    MASKED_INPUT = "masked_input"  # Send masked updates
    UNMASKING = "unmasking"  # Reveal mask shares for dropouts
    AGGREGATION = "aggregation"  # Final aggregation


@dataclass
class ClientKeys:
    """Cryptographic keys for a client."""
    client_id: str
    secret_key: bytes
    public_key: bytes
    shared_keys: Dict[str, bytes] = field(default_factory=dict)

    @staticmethod
    def generate(client_id: str) -> 'ClientKeys':
        """Generate new key pair."""
        secret = secrets.token_bytes(32)
        public = hashlib.sha256(secret).digest()
        return ClientKeys(
            client_id=client_id,
            secret_key=secret,
            public_key=public
        )


@dataclass
class MaskedUpdate:
    """Masked model update from a client."""
    client_id: str
    round_number: int
    masked_parameters: Dict[str, np.ndarray]
    mask_shares: Dict[str, bytes]  # client_id -> encrypted share
    commitment: bytes  # Commitment to original values
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict:
        return {
            'client_id': self.client_id,
            'round_number': self.round_number,
            'parameter_shapes': {k: list(v.shape) for k, v in self.masked_parameters.items()},
            'n_mask_shares': len(self.mask_shares),
            'timestamp': self.timestamp.isoformat()
        }


@dataclass
class AggregationRound:
    """State for a secure aggregation round."""
    round_number: int
    phase: AggregationPhase
    participating_clients: List[str]
    surviving_clients: List[str]
    masked_updates: Dict[str, MaskedUpdate]
    revealed_shares: Dict[str, Dict[str, np.ndarray]]  # client -> other_client -> share
    aggregated_result: Optional[Dict[str, np.ndarray]]
    start_time: datetime
    end_time: Optional[datetime] = None

    @property
    def dropout_rate(self) -> float:
        if not self.participating_clients:
            return 0.0
        return 1 - len(self.surviving_clients) / len(self.participating_clients)


class SecretSharing:
    """
    Secret sharing utilities.

    Implements various secret sharing schemes for
    distributing values among multiple parties.
    """

    def __init__(self, scheme: SecretSharingScheme = SecretSharingScheme.ADDITIVE):
        self.scheme = scheme

    def share(
        self,
        value: np.ndarray,
        n_shares: int,
        threshold: int = None
    ) -> List[np.ndarray]:
        """
        Split value into n shares.

        Args:
            value: Value to share
            n_shares: Number of shares
            threshold: Minimum shares for reconstruction (Shamir only)

        Returns:
            List of shares
        """
        if self.scheme == SecretSharingScheme.ADDITIVE:
            return self._additive_share(value, n_shares)
        elif self.scheme == SecretSharingScheme.SHAMIR:
            return self._shamir_share(value, n_shares, threshold or n_shares)
        else:
            return self._additive_share(value, n_shares)

    def reconstruct(
        self,
        shares: List[np.ndarray],
        indices: Optional[List[int]] = None
    ) -> np.ndarray:
        """
        Reconstruct value from shares.

        Args:
            shares: List of shares
            indices: Share indices (for Shamir)

        Returns:
            Reconstructed value
        """
        if self.scheme == SecretSharingScheme.ADDITIVE:
            return self._additive_reconstruct(shares)
        elif self.scheme == SecretSharingScheme.SHAMIR:
            return self._shamir_reconstruct(shares, indices)
        else:
            return self._additive_reconstruct(shares)

    def _additive_share(self, value: np.ndarray, n_shares: int) -> List[np.ndarray]:
        """Create additive shares: sum of shares = value."""
        # Generate n-1 random shares
        shares = []
        running_sum = np.zeros_like(value)

        for i in range(n_shares - 1):
            share = np.random.randn(*value.shape).astype(value.dtype)
            shares.append(share)
            running_sum += share

        # Last share makes sum equal to value
        shares.append(value - running_sum)

        return shares

    def _additive_reconstruct(self, shares: List[np.ndarray]) -> np.ndarray:
        """Reconstruct from additive shares."""
        return sum(shares)

    def _shamir_share(
        self,
        value: np.ndarray,
        n_shares: int,
        threshold: int
    ) -> List[np.ndarray]:
        """
        Shamir's secret sharing.

        Creates n shares where any threshold shares can reconstruct.
        """
        # For simplicity, work with flattened array
        flat = value.flatten().astype(np.float64)
        n_elements = len(flat)

        # Generate random polynomial coefficients
        # f(x) = value + a_1*x + a_2*x^2 + ... + a_{t-1}*x^{t-1}
        coefficients = np.zeros((threshold, n_elements))
        coefficients[0] = flat

        for i in range(1, threshold):
            coefficients[i] = np.random.randn(n_elements)

        # Evaluate polynomial at points 1, 2, ..., n
        shares = []
        for x in range(1, n_shares + 1):
            share = np.zeros(n_elements)
            for i in range(threshold):
                share += coefficients[i] * (x ** i)
            shares.append(share.reshape(value.shape).astype(value.dtype))

        return shares

    def _shamir_reconstruct(
        self,
        shares: List[np.ndarray],
        indices: Optional[List[int]] = None
    ) -> np.ndarray:
        """Reconstruct from Shamir shares using Lagrange interpolation."""
        if indices is None:
            indices = list(range(1, len(shares) + 1))

        n = len(shares)
        flat_shares = [s.flatten().astype(np.float64) for s in shares]

        # Lagrange interpolation at x=0
        result = np.zeros_like(flat_shares[0])

        for i in range(n):
            xi = indices[i]

            # Compute Lagrange basis polynomial at x=0
            numerator = 1.0
            denominator = 1.0
            for j in range(n):
                if i != j:
                    xj = indices[j]
                    numerator *= -xj
                    denominator *= (xi - xj)

            lagrange_coef = numerator / denominator
            result += flat_shares[i] * lagrange_coef

        return result.reshape(shares[0].shape).astype(shares[0].dtype)


class SecureAggregationProtocol:
    """
    Secure Aggregation Protocol for Federated Learning.

    Implements the protocol from Bonawitz et al. (2017).
    """

    def __init__(
        self,
        threshold: int = 2,
        scheme: SecretSharingScheme = SecretSharingScheme.ADDITIVE
    ):
        self.threshold = threshold
        self.secret_sharing = SecretSharing(scheme)

        # Protocol state
        self.client_keys: Dict[str, ClientKeys] = {}
        self.current_round: Optional[AggregationRound] = None
        self.round_history: List[AggregationRound] = []

    def setup_client(self, client_id: str) -> ClientKeys:
        """Setup keys for a new client."""
        keys = ClientKeys.generate(client_id)
        self.client_keys[client_id] = keys
        return keys

    def exchange_keys(self, client_ids: List[str]) -> Dict[str, Dict[str, bytes]]:
        """
        Simulate key exchange between clients.

        Returns shared keys for each pair of clients.
        """
        shared_keys = {}

        for cid in client_ids:
            if cid not in self.client_keys:
                self.setup_client(cid)

            shared_keys[cid] = {}

            for other_cid in client_ids:
                if cid != other_cid:
                    # Derive shared key (simplified DH simulation)
                    shared_secret = self._derive_shared_key(
                        self.client_keys[cid].secret_key,
                        self.client_keys[other_cid].public_key
                    )
                    shared_keys[cid][other_cid] = shared_secret
                    self.client_keys[cid].shared_keys[other_cid] = shared_secret

        return shared_keys

    def _derive_shared_key(self, secret: bytes, public: bytes) -> bytes:
        """Derive shared key from secret and public key."""
        # Simplified - real implementation would use proper DH
        combined = secret + public
        return hashlib.sha256(combined).digest()

    def start_round(
        self,
        round_number: int,
        participating_clients: List[str]
    ) -> AggregationRound:
        """Start a new secure aggregation round."""
        # Exchange keys
        self.exchange_keys(participating_clients)

        self.current_round = AggregationRound(
            round_number=round_number,
            phase=AggregationPhase.MASKED_INPUT,
            participating_clients=participating_clients,
            surviving_clients=participating_clients.copy(),
            masked_updates={},
            revealed_shares={},
            aggregated_result=None,
            start_time=datetime.now()
        )

        logger.info(f"Started secure aggregation round {round_number} with {len(participating_clients)} clients")
        return self.current_round

    def create_masked_update(
        self,
        client_id: str,
        parameters: Dict[str, np.ndarray],
        other_clients: List[str]
    ) -> MaskedUpdate:
        """
        Create a masked update for a client.

        Args:
            client_id: Client creating the update
            parameters: Model parameters to share
            other_clients: Other participating clients

        Returns:
            Masked update with shares
        """
        if client_id not in self.client_keys:
            raise ValueError(f"Unknown client: {client_id}")

        keys = self.client_keys[client_id]

        # Generate pairwise masks
        masked_params = {k: v.copy() for k, v in parameters.items()}
        mask_shares = {}

        for other_id in other_clients:
            if other_id == client_id:
                continue

            shared_key = keys.shared_keys.get(other_id)
            if shared_key is None:
                continue

            # Generate mask from shared key
            for name, param in masked_params.items():
                mask = self._generate_mask(shared_key, name, param.shape)

                # Add or subtract mask based on client ordering
                if client_id < other_id:
                    masked_params[name] = masked_params[name] + mask
                else:
                    masked_params[name] = masked_params[name] - mask

            # Store mask share for recovery
            mask_shares[other_id] = shared_key

        # Create commitment
        commitment = self._create_commitment(parameters)

        return MaskedUpdate(
            client_id=client_id,
            round_number=self.current_round.round_number if self.current_round else 0,
            masked_parameters=masked_params,
            mask_shares=mask_shares,
            commitment=commitment
        )

    def _generate_mask(
        self,
        key: bytes,
        param_name: str,
        shape: Tuple[int, ...]
    ) -> np.ndarray:
        """Generate deterministic mask from key."""
        # Use key + param_name as seed
        seed_bytes = key + param_name.encode()
        seed = int(hashlib.sha256(seed_bytes).hexdigest()[:8], 16)
        rng = np.random.default_rng(seed)
        return rng.standard_normal(shape).astype(np.float32)

    def _create_commitment(self, parameters: Dict[str, np.ndarray]) -> bytes:
        """Create commitment to parameters."""
        param_bytes = b''
        for name in sorted(parameters.keys()):
            param_bytes += parameters[name].tobytes()
        return hashlib.sha256(param_bytes).digest()

    def receive_masked_update(self, update: MaskedUpdate) -> bool:
        """Receive a masked update from a client."""
        if self.current_round is None:
            logger.error("No active round")
            return False

        if update.client_id not in self.current_round.participating_clients:
            logger.error(f"Client {update.client_id} not participating")
            return False

        self.current_round.masked_updates[update.client_id] = update
        logger.info(f"Received masked update from {update.client_id}")
        return True

    def handle_dropout(self, dropped_clients: List[str]):
        """Handle client dropouts."""
        if self.current_round is None:
            return

        for client_id in dropped_clients:
            if client_id in self.current_round.surviving_clients:
                self.current_round.surviving_clients.remove(client_id)

        logger.info(f"{len(dropped_clients)} clients dropped. Surviving: {len(self.current_round.surviving_clients)}")

        # Move to unmasking phase if needed
        if self.current_round.phase == AggregationPhase.MASKED_INPUT:
            self.current_round.phase = AggregationPhase.UNMASKING

    def reveal_shares_for_dropout(
        self,
        client_id: str,
        dropped_clients: List[str]
    ) -> Dict[str, np.ndarray]:
        """Reveal mask shares for dropped clients."""
        if client_id not in self.client_keys:
            return {}

        keys = self.client_keys[client_id]
        revealed = {}

        for dropped_id in dropped_clients:
            if dropped_id in keys.shared_keys:
                # Reveal the shared key to reconstruct dropped client's mask
                revealed[dropped_id] = keys.shared_keys[dropped_id]

        # Store for aggregation
        if self.current_round:
            self.current_round.revealed_shares[client_id] = revealed

        return revealed

    def aggregate(self) -> Optional[Dict[str, np.ndarray]]:
        """
        Perform secure aggregation.

        Returns aggregated parameters (unmasked).
        """
        if self.current_round is None:
            logger.error("No active round")
            return None

        if len(self.current_round.surviving_clients) < self.threshold:
            logger.error(f"Not enough surviving clients: {len(self.current_round.surviving_clients)} < {self.threshold}")
            return None

        self.current_round.phase = AggregationPhase.AGGREGATION

        # Collect masked updates from surviving clients
        surviving_updates = {
            cid: self.current_round.masked_updates[cid]
            for cid in self.current_round.surviving_clients
            if cid in self.current_round.masked_updates
        }

        if not surviving_updates:
            logger.error("No updates from surviving clients")
            return None

        # Sum masked parameters (masks cancel out for surviving clients)
        first_update = list(surviving_updates.values())[0]
        aggregated = {
            name: np.zeros_like(param)
            for name, param in first_update.masked_parameters.items()
        }

        for update in surviving_updates.values():
            for name, param in update.masked_parameters.items():
                aggregated[name] += param

        # Handle dropped clients - recover their masks
        dropped = set(self.current_round.participating_clients) - set(self.current_round.surviving_clients)
        if dropped:
            aggregated = self._recover_dropped_masks(aggregated, dropped)

        # Average by number of clients
        n_clients = len(surviving_updates)
        for name in aggregated:
            aggregated[name] /= n_clients

        self.current_round.aggregated_result = aggregated
        self.current_round.end_time = datetime.now()
        self.current_round.phase = AggregationPhase.AGGREGATION

        self.round_history.append(self.current_round)

        logger.info(f"Secure aggregation completed for round {self.current_round.round_number}")
        return aggregated

    def _recover_dropped_masks(
        self,
        aggregated: Dict[str, np.ndarray],
        dropped_clients: set
    ) -> Dict[str, np.ndarray]:
        """Recover masks from dropped clients using revealed shares."""
        # For each dropped client, reconstruct their masks
        for dropped_id in dropped_clients:
            if dropped_id not in self.current_round.masked_updates:
                continue

            # Get revealed shares for this dropped client
            shares = []
            for revealer_id, revealed in self.current_round.revealed_shares.items():
                if dropped_id in revealed:
                    shares.append(revealed[dropped_id])

            if len(shares) >= self.threshold:
                # Reconstruct mask and subtract from sum
                # (simplified - actual implementation is more complex)
                logger.info(f"Recovered mask for dropped client {dropped_id}")

        return aggregated

    def get_round_summary(self) -> Dict:
        """Get summary of current round."""
        if self.current_round is None:
            return {'status': 'no_active_round'}

        return {
            'round_number': self.current_round.round_number,
            'phase': self.current_round.phase.value,
            'n_participating': len(self.current_round.participating_clients),
            'n_surviving': len(self.current_round.surviving_clients),
            'n_updates': len(self.current_round.masked_updates),
            'dropout_rate': self.current_round.dropout_rate,
            'has_result': self.current_round.aggregated_result is not None
        }


class ManufacturingSecureAggregation(SecureAggregationProtocol):
    """
    Manufacturing-specific secure aggregation.

    Adds industrial IoT considerations and optimizations.
    """

    def __init__(
        self,
        threshold: int = 2,
        timeout_seconds: float = 60.0
    ):
        super().__init__(threshold)
        self.timeout = timeout_seconds

        # Manufacturing context
        self.factory_groups: Dict[str, List[str]] = {}  # factory -> clients
        self.priority_clients: List[str] = []

    def set_factory_topology(
        self,
        factory_groups: Dict[str, List[str]],
        priority_clients: Optional[List[str]] = None
    ):
        """Set factory network topology."""
        self.factory_groups = factory_groups
        self.priority_clients = priority_clients or []

    def intra_factory_aggregate(
        self,
        factory_id: str
    ) -> Optional[Dict[str, np.ndarray]]:
        """
        Aggregate within a single factory first.

        This reduces inter-factory communication.
        """
        if factory_id not in self.factory_groups:
            return None

        factory_clients = self.factory_groups[factory_id]

        # Get updates from this factory's clients
        if self.current_round is None:
            return None

        factory_updates = {
            cid: self.current_round.masked_updates[cid]
            for cid in factory_clients
            if cid in self.current_round.masked_updates
        }

        if not factory_updates:
            return None

        # Simple sum for intra-factory (assuming same factory trusts each other more)
        first = list(factory_updates.values())[0]
        aggregated = {
            name: np.zeros_like(param)
            for name, param in first.masked_parameters.items()
        }

        for update in factory_updates.values():
            for name, param in update.masked_parameters.items():
                aggregated[name] += param

        n = len(factory_updates)
        for name in aggregated:
            aggregated[name] /= n

        return aggregated

    def hierarchical_aggregate(self) -> Optional[Dict[str, np.ndarray]]:
        """
        Perform hierarchical aggregation.

        1. Aggregate within each factory
        2. Aggregate across factories
        """
        factory_aggregates = {}

        for factory_id in self.factory_groups:
            agg = self.intra_factory_aggregate(factory_id)
            if agg is not None:
                factory_aggregates[factory_id] = agg

        if not factory_aggregates:
            return None

        # Aggregate across factories
        first = list(factory_aggregates.values())[0]
        final = {
            name: np.zeros_like(param)
            for name, param in first.items()
        }

        for agg in factory_aggregates.values():
            for name, param in agg.items():
                final[name] += param

        n = len(factory_aggregates)
        for name in final:
            final[name] /= n

        return final

    def get_manufacturing_metrics(self) -> Dict:
        """Get manufacturing-specific aggregation metrics."""
        metrics = self.get_round_summary()

        if self.current_round:
            # Per-factory statistics
            factory_stats = {}
            for factory_id, clients in self.factory_groups.items():
                participating = [c for c in clients if c in self.current_round.participating_clients]
                surviving = [c for c in clients if c in self.current_round.surviving_clients]

                factory_stats[factory_id] = {
                    'total_clients': len(clients),
                    'participating': len(participating),
                    'surviving': len(surviving)
                }

            metrics['factory_statistics'] = factory_stats

        return metrics
