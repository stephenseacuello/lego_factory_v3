"""
LEGO Factory v3 - ML Trainer
=============================
Training loop for MM-DTAE-LSTM fingerprinting model.
"""

import json
import logging
import os
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any, Callable

import torch
import torch.nn as nn
from torch.optim import AdamW
from torch.optim.lr_scheduler import CosineAnnealingLR, OneCycleLR
from torch.cuda.amp import autocast, GradScaler

logger = logging.getLogger(__name__)


@dataclass
class TrainingConfig:
    """Training configuration."""
    # Model
    model_name: str = "mm_dtae_lstm"
    sensor_dims: List[int] = field(default_factory=lambda: [6, 3, 3])
    d_model: int = 256
    lstm_layers: int = 2
    n_heads: int = 4
    dropout: float = 0.1
    gcode_vocab: int = 128
    fp_dim: int = 128

    # Training
    epochs: int = 100
    batch_size: int = 32
    learning_rate: float = 1e-4
    weight_decay: float = 0.01
    warmup_epochs: int = 5
    gradient_clip: float = 1.0

    # Scheduler
    scheduler: str = "cosine"  # cosine, onecycle, none
    min_lr: float = 1e-6

    # Loss weights
    loss_weights: Dict[str, float] = field(default_factory=lambda: {
        'reconstruction': 1.0,
        'classification': 1.0,
        'regression': 1.0,
        'anomaly': 1.0,
        'gcode': 0.5,
        'fingerprint': 1.0,
        'future': 0.5,
    })

    # Data
    sequence_length: int = 256
    train_split: float = 0.8
    val_split: float = 0.1
    augment: bool = True

    # Hardware
    device: str = "cuda" if torch.cuda.is_available() else "cpu"
    mixed_precision: bool = True
    num_workers: int = 4

    # Checkpointing
    checkpoint_dir: str = "services/ml/checkpoints"
    save_every: int = 5
    keep_last_n: int = 3

    # Logging
    log_every: int = 10
    eval_every: int = 1

    # Early stopping
    early_stopping_patience: int = 20
    early_stopping_min_delta: float = 1e-4


@dataclass
class TrainingMetrics:
    """Training metrics container."""
    epoch: int = 0
    train_loss: float = 0.0
    val_loss: float = 0.0
    train_metrics: Dict[str, float] = field(default_factory=dict)
    val_metrics: Dict[str, float] = field(default_factory=dict)
    learning_rate: float = 0.0
    epoch_time: float = 0.0
    best_val_loss: float = float('inf')
    epochs_without_improvement: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class Trainer:
    """
    Trainer for MM-DTAE-LSTM model.

    Handles:
    - Training loop with validation
    - Learning rate scheduling
    - Mixed precision training
    - Checkpointing
    - Early stopping
    - Metrics logging
    """

    def __init__(self, config: TrainingConfig):
        """
        Initialize trainer.

        Args:
            config: Training configuration
        """
        self.config = config
        self.device = torch.device(config.device)

        # Model
        self.model = None
        self.optimizer = None
        self.scheduler = None
        self.loss_fn = None

        # Mixed precision
        self.scaler = GradScaler() if config.mixed_precision and config.device == 'cuda' else None

        # Metrics
        self.metrics = TrainingMetrics()
        self.history: List[TrainingMetrics] = []

        # Callbacks
        self.callbacks: List[Callable] = []

        # Setup checkpoint directory
        self.checkpoint_dir = Path(config.checkpoint_dir)
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)

        logger.info(f"Trainer initialized on {self.device}")

    def build_model(self) -> nn.Module:
        """Build the model."""
        from services.ml.model import MM_DTAE_LSTM, ModelConfig

        model_config = ModelConfig(
            sensor_dims=self.config.sensor_dims,
            d_model=self.config.d_model,
            lstm_layers=self.config.lstm_layers,
            n_heads=self.config.n_heads,
            dropout=self.config.dropout,
            gcode_vocab=self.config.gcode_vocab,
            fp_dim=self.config.fp_dim,
        )

        self.model = MM_DTAE_LSTM(model_config)
        self.model = self.model.to(self.device)

        # Count parameters
        total_params = sum(p.numel() for p in self.model.parameters())
        trainable_params = sum(p.numel() for p in self.model.parameters() if p.requires_grad)
        logger.info(f"Model parameters: {total_params:,} total, {trainable_params:,} trainable")

        return self.model

    def build_optimizer(self) -> None:
        """Build optimizer and scheduler."""
        self.optimizer = AdamW(
            self.model.parameters(),
            lr=self.config.learning_rate,
            weight_decay=self.config.weight_decay
        )

        if self.config.scheduler == 'cosine':
            self.scheduler = CosineAnnealingLR(
                self.optimizer,
                T_max=self.config.epochs,
                eta_min=self.config.min_lr
            )
        elif self.config.scheduler == 'onecycle':
            # Note: OneCycleLR needs total steps, set after data loader creation
            self.scheduler = None
        else:
            self.scheduler = None

    def build_loss(self) -> None:
        """Build loss function."""
        from .losses import MultiTaskLoss

        self.loss_fn = MultiTaskLoss(
            weights=self.config.loss_weights,
            use_uncertainty_weighting=True
        )

    def train_epoch(self, train_loader) -> Dict[str, float]:
        """Train for one epoch."""
        self.model.train()
        total_loss = 0.0
        metrics_sum = {}
        num_batches = 0

        for batch_idx, batch in enumerate(train_loader):
            # Move to device
            sensors = [s.to(self.device) for s in batch['sensors']]

            # Build targets dict
            targets = {}
            for key in ['cls', 'reg', 'anom', 'gcode', 'program_id', 'future']:
                if key in batch:
                    targets[key] = batch[key].to(self.device)

            # Forward pass
            self.optimizer.zero_grad()

            if self.scaler is not None:
                with autocast():
                    outputs = self.model(sensors)
                    targets['input'] = torch.cat(sensors, dim=-1)  # For reconstruction
                    loss, batch_metrics = self.loss_fn(outputs, targets)

                # Backward pass with gradient scaling
                self.scaler.scale(loss).backward()

                # Gradient clipping
                if self.config.gradient_clip > 0:
                    self.scaler.unscale_(self.optimizer)
                    torch.nn.utils.clip_grad_norm_(
                        self.model.parameters(),
                        self.config.gradient_clip
                    )

                self.scaler.step(self.optimizer)
                self.scaler.update()
            else:
                outputs = self.model(sensors)
                targets['input'] = torch.cat(sensors, dim=-1)
                loss, batch_metrics = self.loss_fn(outputs, targets)

                loss.backward()

                if self.config.gradient_clip > 0:
                    torch.nn.utils.clip_grad_norm_(
                        self.model.parameters(),
                        self.config.gradient_clip
                    )

                self.optimizer.step()

            # Accumulate metrics
            total_loss += loss.item()
            for k, v in batch_metrics.items():
                metrics_sum[k] = metrics_sum.get(k, 0.0) + v
            num_batches += 1

            # Logging
            if batch_idx % self.config.log_every == 0:
                logger.debug(
                    f"Batch {batch_idx}/{len(train_loader)} - "
                    f"Loss: {loss.item():.4f}"
                )

        # Average metrics
        avg_loss = total_loss / num_batches
        avg_metrics = {k: v / num_batches for k, v in metrics_sum.items()}

        return {'loss': avg_loss, **avg_metrics}

    @torch.no_grad()
    def validate(self, val_loader) -> Dict[str, float]:
        """Validate the model."""
        self.model.eval()
        total_loss = 0.0
        metrics_sum = {}
        num_batches = 0

        for batch in val_loader:
            sensors = [s.to(self.device) for s in batch['sensors']]

            targets = {}
            for key in ['cls', 'reg', 'anom', 'gcode', 'program_id', 'future']:
                if key in batch:
                    targets[key] = batch[key].to(self.device)

            if self.scaler is not None:
                with autocast():
                    outputs = self.model(sensors)
                    targets['input'] = torch.cat(sensors, dim=-1)
                    loss, batch_metrics = self.loss_fn(outputs, targets)
            else:
                outputs = self.model(sensors)
                targets['input'] = torch.cat(sensors, dim=-1)
                loss, batch_metrics = self.loss_fn(outputs, targets)

            total_loss += loss.item()
            for k, v in batch_metrics.items():
                metrics_sum[k] = metrics_sum.get(k, 0.0) + v
            num_batches += 1

        avg_loss = total_loss / num_batches
        avg_metrics = {k: v / num_batches for k, v in metrics_sum.items()}

        return {'loss': avg_loss, **avg_metrics}

    def train(
        self,
        train_loader,
        val_loader,
        resume_from: str = None
    ) -> TrainingMetrics:
        """
        Full training loop.

        Args:
            train_loader: Training data loader
            val_loader: Validation data loader
            resume_from: Path to checkpoint to resume from

        Returns:
            Final training metrics
        """
        # Build components if not already built
        if self.model is None:
            self.build_model()
        if self.optimizer is None:
            self.build_optimizer()
        if self.loss_fn is None:
            self.build_loss()

        # Setup OneCycleLR if needed
        if self.config.scheduler == 'onecycle':
            total_steps = len(train_loader) * self.config.epochs
            self.scheduler = OneCycleLR(
                self.optimizer,
                max_lr=self.config.learning_rate,
                total_steps=total_steps,
                pct_start=self.config.warmup_epochs / self.config.epochs
            )

        # Resume from checkpoint
        start_epoch = 0
        if resume_from:
            start_epoch = self.load_checkpoint(resume_from)

        logger.info(f"Starting training from epoch {start_epoch}")

        for epoch in range(start_epoch, self.config.epochs):
            epoch_start = time.time()

            # Train
            train_metrics = self.train_epoch(train_loader)
            self.metrics.train_loss = train_metrics['loss']
            self.metrics.train_metrics = train_metrics

            # Validate
            if (epoch + 1) % self.config.eval_every == 0:
                val_metrics = self.validate(val_loader)
                self.metrics.val_loss = val_metrics['loss']
                self.metrics.val_metrics = val_metrics
            else:
                val_metrics = {}

            # Update scheduler
            if self.scheduler is not None:
                if isinstance(self.scheduler, OneCycleLR):
                    # OneCycleLR steps per batch
                    pass
                else:
                    self.scheduler.step()

            # Get current learning rate
            self.metrics.learning_rate = self.optimizer.param_groups[0]['lr']

            # Timing
            epoch_time = time.time() - epoch_start
            self.metrics.epoch = epoch
            self.metrics.epoch_time = epoch_time

            # Logging
            logger.info(
                f"Epoch {epoch+1}/{self.config.epochs} - "
                f"Train Loss: {train_metrics['loss']:.4f} - "
                f"Val Loss: {val_metrics.get('loss', 0):.4f} - "
                f"LR: {self.metrics.learning_rate:.2e} - "
                f"Time: {epoch_time:.1f}s"
            )

            # Save history
            self.history.append(TrainingMetrics(**asdict(self.metrics)))

            # Checkpointing
            if (epoch + 1) % self.config.save_every == 0:
                self.save_checkpoint(epoch)

            # Best model
            if val_metrics.get('loss', float('inf')) < self.metrics.best_val_loss:
                self.metrics.best_val_loss = val_metrics['loss']
                self.metrics.epochs_without_improvement = 0
                self.save_checkpoint(epoch, is_best=True)
            else:
                self.metrics.epochs_without_improvement += 1

            # Early stopping
            if self.metrics.epochs_without_improvement >= self.config.early_stopping_patience:
                logger.info(f"Early stopping at epoch {epoch+1}")
                break

            # Callbacks
            for callback in self.callbacks:
                callback(self.metrics)

        # Final save
        self.save_checkpoint(epoch, is_final=True)

        return self.metrics

    def save_checkpoint(self, epoch: int, is_best: bool = False, is_final: bool = False) -> str:
        """Save model checkpoint."""
        if is_best:
            filename = 'best_model.pt'
        elif is_final:
            filename = 'final_model.pt'
        else:
            filename = f'checkpoint_epoch_{epoch+1}.pt'

        path = self.checkpoint_dir / filename

        checkpoint = {
            'epoch': epoch,
            'model_state_dict': self.model.state_dict(),
            'optimizer_state_dict': self.optimizer.state_dict(),
            'scheduler_state_dict': self.scheduler.state_dict() if self.scheduler else None,
            'metrics': asdict(self.metrics),
            'config': asdict(self.config),
            'history': [asdict(m) for m in self.history],
        }

        torch.save(checkpoint, path)
        logger.info(f"Saved checkpoint to {path}")

        # Clean up old checkpoints
        self._cleanup_checkpoints()

        return str(path)

    def load_checkpoint(self, path: str) -> int:
        """Load model checkpoint."""
        checkpoint = torch.load(path, map_location=self.device)

        self.model.load_state_dict(checkpoint['model_state_dict'])
        self.optimizer.load_state_dict(checkpoint['optimizer_state_dict'])

        if self.scheduler and checkpoint.get('scheduler_state_dict'):
            self.scheduler.load_state_dict(checkpoint['scheduler_state_dict'])

        self.metrics = TrainingMetrics(**checkpoint['metrics'])
        self.history = [TrainingMetrics(**m) for m in checkpoint.get('history', [])]

        logger.info(f"Loaded checkpoint from {path}")
        return checkpoint['epoch'] + 1

    def _cleanup_checkpoints(self) -> None:
        """Remove old checkpoints, keep only last N."""
        checkpoints = sorted(
            self.checkpoint_dir.glob('checkpoint_epoch_*.pt'),
            key=lambda p: int(p.stem.split('_')[-1])
        )

        while len(checkpoints) > self.config.keep_last_n:
            old_ckpt = checkpoints.pop(0)
            old_ckpt.unlink()
            logger.debug(f"Removed old checkpoint: {old_ckpt}")

    def export_metrics(self, path: str = None) -> str:
        """Export training history to JSON."""
        path = path or (self.checkpoint_dir / 'training_history.json')

        history_data = {
            'config': asdict(self.config),
            'history': [m.to_dict() for m in self.history],
            'best_val_loss': self.metrics.best_val_loss,
            'final_epoch': self.metrics.epoch,
        }

        with open(path, 'w') as f:
            json.dump(history_data, f, indent=2)

        logger.info(f"Exported training history to {path}")
        return str(path)

    def add_callback(self, callback: Callable[[TrainingMetrics], None]) -> None:
        """Add training callback."""
        self.callbacks.append(callback)


# Global trainer instance
_trainer: Optional[Trainer] = None


def get_trainer(config: TrainingConfig = None) -> Trainer:
    """Get or create global trainer instance."""
    global _trainer
    if _trainer is None or config is not None:
        _trainer = Trainer(config or TrainingConfig())
    return _trainer
