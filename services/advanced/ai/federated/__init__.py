"""
Federated Learning Module
=========================

LegoMCP PhD-Level Manufacturing Platform
Part of the Research Foundation (Phase 1)

This module implements privacy-preserving distributed machine learning,
enabling multiple manufacturing sites to collaboratively train AI models
without sharing sensitive production data.

Why Federated Learning for Manufacturing?
-----------------------------------------
- **Data Privacy**: Production data is proprietary and regulated
- **Data Sovereignty**: Data cannot leave factory premises (GDPR, etc.)
- **Network Constraints**: Sending large datasets is impractical
- **Competitive Advantage**: Share learnings without sharing secrets

Key Concepts:
-------------

1. **Federated Averaging (FedAvg)**:
   - Train local models at each factory
   - Send only model updates (gradients) to central server
   - Server aggregates updates into global model
   - Global model distributed back to factories

2. **Differential Privacy**:
   - Add calibrated noise to gradient updates
   - Provides mathematical privacy guarantees
   - Prevents model from "memorizing" individual samples
   - Configurable privacy budget (epsilon)

3. **Secure Aggregation**:
   - Cryptographic protocol for aggregation
   - Server cannot see individual client updates
   - Only aggregated result is revealed
   - Protects against malicious server

Components:
-----------

1. **FederatedServer**:
   - Coordinates training across clients
   - Aggregates model updates
   - Manages training rounds
   - Supports FedAvg, FedProx, FedOpt

2. **FederatedClient**:
   - Local training on factory data
   - Computes and sends model updates
   - Receives global model updates
   - Handles local constraints

3. **DifferentialPrivacy**:
   - Gradient clipping (bound sensitivity)
   - Gaussian noise addition
   - Privacy accountant (tracks budget)
   - Configurable epsilon/delta

4. **SecureAggregation**:
   - Secret sharing among clients
   - Masked updates
   - Dropout tolerance
   - Secure sum computation

Manufacturing Use Cases:
------------------------
- Cross-factory defect detection model
- Industry-wide predictive maintenance
- Supply chain quality models
- Benchmark models without data sharing

Example Usage:
--------------
    from services.ai.federated import (
        FederatedServer,
        FederatedClient,
        DifferentialPrivacy,
    )

    # Server setup
    server = FederatedServer(
        model=quality_model,
        aggregation_strategy="fedavg",
        num_rounds=100,
        min_clients=5,
    )

    # Client setup (at each factory)
    dp = DifferentialPrivacy(epsilon=1.0, delta=1e-5)
    client = FederatedClient(
        client_id="factory_1",
        local_data=production_data,
        differential_privacy=dp,
    )

    # Training round
    global_model = server.get_global_model()
    local_update = client.train(global_model, epochs=5)
    server.receive_update(client.client_id, local_update)

    # After enough clients
    new_global_model = server.aggregate()

Privacy Guarantees:
-------------------
- Epsilon (privacy loss): Lower = more private (recommend 1-10)
- Delta (failure probability): Should be < 1/dataset_size
- Noise scale = sensitivity / epsilon
- Composition: Privacy degrades over multiple rounds

References:
-----------
- McMahan, B. et al. (2017). Communication-Efficient Learning of Deep
  Networks from Decentralized Data. AISTATS.
- Bonawitz, K. et al. (2017). Practical Secure Aggregation for
  Privacy-Preserving Machine Learning. CCS.
- Abadi, M. et al. (2016). Deep Learning with Differential Privacy. CCS.
- Kairouz, P. et al. (2021). Advances and Open Problems in Federated Learning.

Author: LegoMCP Team
Version: 2.0.0
"""

# Federated Server
from .federated_server import (
    FederatedServer,
    FederatedConfig,
    AggregationStrategy,
    SecureAggregator,
    FederatedRound,
)

# Federated Client
from .federated_client import (
    FederatedClient,
    ClientConfig,
    LocalTrainer,
    ModelUpdate,
    ClientState,
)

# Differential Privacy
from .differential_privacy import (
    DifferentialPrivacy,
    DPConfig,
    NoiseGenerator,
    PrivacyAccountant,
    GradientClipper,
)

# Secure Aggregation
from .secure_aggregation import (
    SecureAggregationProtocol,
    SecretSharing,
    MaskedUpdate,
    AggregationRound,
)

__all__ = [
    # Server
    "FederatedServer",
    "FederatedConfig",
    "AggregationStrategy",
    "SecureAggregator",
    "FederatedRound",

    # Client
    "FederatedClient",
    "ClientConfig",
    "LocalTrainer",
    "ModelUpdate",
    "ClientState",

    # Differential Privacy
    "DifferentialPrivacy",
    "DPConfig",
    "NoiseGenerator",
    "PrivacyAccountant",
    "GradientClipper",

    # Secure Aggregation
    "SecureAggregationProtocol",
    "SecretSharing",
    "MaskedUpdate",
    "AggregationRound",
]

__version__ = "2.0.0"
__author__ = "LegoMCP Team"
