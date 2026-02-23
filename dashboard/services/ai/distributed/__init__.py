"""
Distributed Training Module
===========================

LegoMCP PhD-Level Manufacturing Platform
Part of the Advanced AI/ML Operations (Phase 8.2)

This module provides distributed training capabilities for scaling AI/ML
workloads across multiple GPUs and nodes. Essential for:

1. **Large-Scale Training**: Train on massive manufacturing datasets
2. **Faster Iteration**: Reduce training time from days to hours
3. **Complex Models**: Train foundation models and large ensembles
4. **Resource Efficiency**: Utilize cluster resources effectively

Distributed Training Paradigms:
-------------------------------

1. **Data Parallelism** (primary approach):
   - Same model replicated across workers
   - Each worker processes different data batches
   - Gradients synchronized across workers
   - Implemented via: Horovod, Ray

2. **Model Parallelism** (for very large models):
   - Model split across workers
   - Each worker handles part of the model
   - Activations passed between workers

3. **Pipeline Parallelism**:
   - Model split into stages
   - Different stages run on different workers
   - Overlapping computation for efficiency

Components:
-----------

1. **HorovodTrainer**:
   - Ring-allreduce for efficient gradient synchronization
   - Supports PyTorch, TensorFlow, MXNet
   - Excellent scaling to 100s of GPUs
   - Mixed precision (FP16) support
   - Fault tolerance via elastic training

2. **RayTrainer**:
   - Flexible distributed execution
   - Built-in hyperparameter tuning (Ray Tune)
   - Elastic scaling (add/remove workers)
   - Easy cluster deployment
   - Supports various ML frameworks

3. **GradientCompressor**:
   - Reduce communication overhead
   - Methods: Top-k, Random-k, Quantization, PowerSGD
   - Trade-off: compression vs. accuracy
   - Essential for bandwidth-limited environments

Performance Considerations:
---------------------------
- Gradient synchronization is the bottleneck
- Use gradient compression for slow networks
- Batch size scales with worker count
- Learning rate should scale accordingly
- Monitor gradient statistics for debugging

Example Usage:
--------------
    from services.ai.distributed import (
        HorovodTrainer,
        RayTrainer,
        GradientCompressor,
    )

    # Horovod distributed training
    trainer = HorovodTrainer()
    trainer.initialize()
    model, optimizer = trainer.setup_model(model, optimizer)
    metrics = trainer.train(
        model, optimizer, train_loader, val_loader,
        loss_fn=nn.CrossEntropyLoss(),
        epochs=100,
    )

    # Ray distributed training with tuning
    ray_trainer = RayTrainer(num_workers=4, use_gpu=True)
    result = ray_trainer.tune_hyperparameters(
        model_fn=create_model,
        train_dataset=train_data,
        val_dataset=val_data,
        param_space={"lr": tune.loguniform(1e-4, 1e-1)},
        num_samples=20,
    )

    # Gradient compression for bandwidth efficiency
    compressor = GradientCompressor(method="topk", ratio=0.01)
    compressed = compressor.compress(gradients, epoch=current_epoch)
    # ... send compressed gradients ...
    gradients = compressor.decompress(compressed)

Scaling Best Practices:
-----------------------
1. Start with single GPU, verify correctness
2. Scale to multi-GPU on single node
3. Then scale to multi-node
4. Monitor throughput at each scale
5. Adjust batch size and learning rate
6. Use gradient compression if network-bound

References:
-----------
- Sergeev, A., & Del Balso, M. (2018). Horovod: fast and easy distributed DL
- Moritz, P. et al. (2018). Ray: A Distributed Framework for Emerging AI
- Lin, Y. et al. (2018). Deep Gradient Compression
- Vogels, T. et al. (2019). PowerSGD: Practical Low-Rank Gradient Compression

Author: LegoMCP Team
Version: 2.0.0
"""

# Horovod Distributed Training
from .horovod_trainer import (
    HorovodTrainer,
    HorovodConfig,
    MixedPrecisionTrainer,
    DistributedMetrics,
)

# Ray Distributed Training
from .ray_trainer import (
    RayTrainer,
    RayConfig,
    RayTrainingResult,
    ElasticRayTrainer,
)

# Gradient Compression
from .gradient_compression import (
    GradientCompressor,
    CompressionConfig,
    CompressionMethod,
    TopKCompressor,
    RandomKCompressor,
    OneBitQuantizer,
    TernGradCompressor,
    PowerSGDCompressor,
)

__all__ = [
    # Horovod
    "HorovodTrainer",
    "HorovodConfig",
    "MixedPrecisionTrainer",
    "DistributedMetrics",

    # Ray
    "RayTrainer",
    "RayConfig",
    "RayTrainingResult",
    "ElasticRayTrainer",

    # Compression
    "GradientCompressor",
    "CompressionConfig",
    "CompressionMethod",
    "TopKCompressor",
    "RandomKCompressor",
    "OneBitQuantizer",
    "TernGradCompressor",
    "PowerSGDCompressor",
]

__version__ = "2.0.0"
__author__ = "LegoMCP Team"
