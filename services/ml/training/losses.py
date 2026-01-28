"""
LEGO Factory v3 - ML Loss Functions
====================================
Custom loss functions for MM-DTAE-LSTM training.

Multi-task losses for:
- G-code fingerprinting (contrastive)
- Anomaly detection (BCE)
- Tool wear prediction (regression)
- Operation classification
- G-code generation (cross-entropy)
- Reconstruction (MSE)
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
from typing import Dict, Optional, Tuple


class ContrastiveLoss(nn.Module):
    """
    Contrastive loss for fingerprint learning (InfoNCE/NT-Xent).

    Pulls similar fingerprints together, pushes dissimilar apart.
    Used for learning G-code program embeddings.
    """

    def __init__(self, temperature: float = 0.07, reduction: str = 'mean'):
        """
        Args:
            temperature: Softmax temperature for scaling
            reduction: 'mean', 'sum', or 'none'
        """
        super().__init__()
        self.temperature = temperature
        self.reduction = reduction

    def forward(
        self,
        embeddings: torch.Tensor,
        labels: torch.Tensor = None,
        mask: torch.Tensor = None
    ) -> torch.Tensor:
        """
        Compute contrastive loss.

        Args:
            embeddings: [batch, embedding_dim] L2-normalized embeddings
            labels: [batch] integer labels (same label = positive pair)
            mask: [batch, batch] binary mask for valid pairs

        Returns:
            Scalar loss value
        """
        batch_size = embeddings.shape[0]
        device = embeddings.device

        # Compute similarity matrix
        similarity = torch.matmul(embeddings, embeddings.T) / self.temperature

        # Create positive pair mask from labels
        if labels is not None:
            labels = labels.contiguous().view(-1, 1)
            pos_mask = torch.eq(labels, labels.T).float()
        else:
            # Self-supervised: use data augmentation (positive = same sample)
            pos_mask = torch.eye(batch_size, device=device)

        # Remove diagonal (self-similarity)
        logits_mask = torch.ones_like(pos_mask) - torch.eye(batch_size, device=device)

        # Mask out invalid pairs
        if mask is not None:
            logits_mask = logits_mask * mask

        pos_mask = pos_mask * logits_mask

        # Compute log-softmax
        exp_logits = torch.exp(similarity) * logits_mask
        log_prob = similarity - torch.log(exp_logits.sum(dim=1, keepdim=True) + 1e-8)

        # Mean over positive pairs
        mean_log_prob_pos = (pos_mask * log_prob).sum(dim=1) / (pos_mask.sum(dim=1) + 1e-8)

        # Loss is negative of mean positive log probability
        loss = -mean_log_prob_pos

        if self.reduction == 'mean':
            return loss.mean()
        elif self.reduction == 'sum':
            return loss.sum()
        return loss


class TripletLoss(nn.Module):
    """
    Triplet loss for fingerprint learning.

    anchor, positive, negative triplets where:
    - anchor-positive: same program ID
    - anchor-negative: different program ID
    """

    def __init__(self, margin: float = 0.2, reduction: str = 'mean'):
        super().__init__()
        self.margin = margin
        self.reduction = reduction

    def forward(
        self,
        anchor: torch.Tensor,
        positive: torch.Tensor,
        negative: torch.Tensor
    ) -> torch.Tensor:
        """
        Compute triplet loss.

        Args:
            anchor: [batch, dim] anchor embeddings
            positive: [batch, dim] positive embeddings
            negative: [batch, dim] negative embeddings

        Returns:
            Scalar loss
        """
        pos_dist = F.pairwise_distance(anchor, positive, p=2)
        neg_dist = F.pairwise_distance(anchor, negative, p=2)

        loss = F.relu(pos_dist - neg_dist + self.margin)

        if self.reduction == 'mean':
            return loss.mean()
        elif self.reduction == 'sum':
            return loss.sum()
        return loss


class FingerprintLoss(nn.Module):
    """
    Combined loss for G-code fingerprint learning.

    Combines contrastive loss with regularization.
    """

    def __init__(
        self,
        temperature: float = 0.07,
        margin: float = 0.2,
        use_triplet: bool = False,
        l2_reg: float = 0.01
    ):
        super().__init__()
        self.use_triplet = use_triplet
        self.l2_reg = l2_reg

        if use_triplet:
            self.loss_fn = TripletLoss(margin=margin)
        else:
            self.loss_fn = ContrastiveLoss(temperature=temperature)

    def forward(
        self,
        embeddings: torch.Tensor,
        labels: torch.Tensor = None,
        anchor: torch.Tensor = None,
        positive: torch.Tensor = None,
        negative: torch.Tensor = None
    ) -> Tuple[torch.Tensor, Dict[str, float]]:
        """
        Compute fingerprint loss.

        Returns:
            loss: Scalar loss
            metrics: Dict with loss components
        """
        metrics = {}

        if self.use_triplet and anchor is not None:
            contrast_loss = self.loss_fn(anchor, positive, negative)
        else:
            contrast_loss = self.loss_fn(embeddings, labels)

        metrics['contrastive'] = contrast_loss.item()

        # L2 regularization on embeddings
        l2_loss = self.l2_reg * (embeddings ** 2).mean()
        metrics['l2_reg'] = l2_loss.item()

        total_loss = contrast_loss + l2_loss
        metrics['total'] = total_loss.item()

        return total_loss, metrics


class MultiTaskLoss(nn.Module):
    """
    Multi-task loss for MM-DTAE-LSTM model.

    Combines losses for:
    - Reconstruction (DTAE)
    - Classification (operation type)
    - Regression (tool wear, remaining life)
    - Anomaly detection
    - G-code generation
    - Fingerprint embedding
    """

    def __init__(
        self,
        num_classes: int = 5,
        vocab_size: int = 128,
        weights: Dict[str, float] = None,
        use_uncertainty_weighting: bool = False
    ):
        """
        Args:
            num_classes: Number of classification classes
            vocab_size: G-code vocabulary size
            weights: Loss weights per task
            use_uncertainty_weighting: Use learned task weights
        """
        super().__init__()

        self.weights = weights or {
            'reconstruction': 1.0,
            'classification': 1.0,
            'regression': 1.0,
            'anomaly': 1.0,
            'gcode': 0.5,
            'fingerprint': 1.0,
            'future': 0.5,
        }

        self.use_uncertainty_weighting = use_uncertainty_weighting
        if use_uncertainty_weighting:
            # Learned log-variance parameters for uncertainty weighting
            self.log_vars = nn.ParameterDict({
                name: nn.Parameter(torch.zeros(1))
                for name in self.weights.keys()
            })

        # Loss functions
        self.mse_loss = nn.MSELoss(reduction='mean')
        self.ce_loss = nn.CrossEntropyLoss(reduction='mean')
        self.bce_loss = nn.BCEWithLogitsLoss(reduction='mean')
        self.fingerprint_loss = FingerprintLoss()

    def forward(
        self,
        outputs: Dict[str, torch.Tensor],
        targets: Dict[str, torch.Tensor]
    ) -> Tuple[torch.Tensor, Dict[str, float]]:
        """
        Compute multi-task loss.

        Args:
            outputs: Model outputs dict with keys:
                - recon: Reconstruction for DTAE
                - cls: Classification logits [batch, num_classes]
                - reg: Regression outputs [batch, 3]
                - anom: Anomaly scores [batch, 1]
                - gcode_logits: G-code generation [batch, seq, vocab]
                - fingerprint: Fingerprint embeddings [batch, fp_dim]
                - future: Future predictions [batch, future_len, dim]

            targets: Target dict with keys:
                - input: Original input for reconstruction
                - cls: Classification labels [batch]
                - reg: Regression targets [batch, 3]
                - anom: Anomaly labels [batch]
                - gcode: G-code token targets [batch, seq]
                - program_id: Program IDs for contrastive learning
                - future: Future ground truth [batch, future_len, dim]

        Returns:
            total_loss: Weighted sum of all losses
            metrics: Dict with individual loss values
        """
        losses = {}
        metrics = {}

        # Reconstruction loss (MSE)
        if 'recon' in outputs and 'input' in targets:
            losses['reconstruction'] = self.mse_loss(outputs['recon'], targets['input'])

        # Classification loss (Cross-entropy)
        if 'cls' in outputs and 'cls' in targets:
            losses['classification'] = self.ce_loss(outputs['cls'], targets['cls'])

        # Regression loss (MSE for tool wear, remaining life, etc.)
        if 'reg' in outputs and 'reg' in targets:
            losses['regression'] = self.mse_loss(outputs['reg'], targets['reg'])

        # Anomaly detection loss (BCE)
        if 'anom' in outputs and 'anom' in targets:
            losses['anomaly'] = self.bce_loss(
                outputs['anom'].squeeze(),
                targets['anom'].float()
            )

        # G-code generation loss (Cross-entropy)
        if 'gcode_logits' in outputs and 'gcode' in targets:
            # Flatten for cross-entropy
            batch, seq, vocab = outputs['gcode_logits'].shape
            logits = outputs['gcode_logits'].view(-1, vocab)
            gcode_targets = targets['gcode'].view(-1)
            losses['gcode'] = self.ce_loss(logits, gcode_targets)

        # Fingerprint contrastive loss
        if 'fingerprint' in outputs and 'program_id' in targets:
            fp_loss, fp_metrics = self.fingerprint_loss(
                outputs['fingerprint'],
                targets['program_id']
            )
            losses['fingerprint'] = fp_loss
            for k, v in fp_metrics.items():
                metrics[f'fp_{k}'] = v

        # Future prediction loss (MSE)
        if 'future' in outputs and 'future' in targets:
            losses['future'] = self.mse_loss(outputs['future'], targets['future'])

        # Compute total loss with weighting
        total_loss = torch.tensor(0.0, device=next(iter(outputs.values())).device)

        for name, loss in losses.items():
            weight = self.weights.get(name, 1.0)

            if self.use_uncertainty_weighting and name in self.log_vars:
                # Uncertainty weighting: loss / (2 * sigma^2) + log(sigma)
                precision = torch.exp(-self.log_vars[name])
                weighted_loss = precision * loss + self.log_vars[name]
                metrics[f'{name}_weight'] = precision.item()
            else:
                weighted_loss = weight * loss

            total_loss = total_loss + weighted_loss
            metrics[name] = loss.item()

        metrics['total'] = total_loss.item()

        return total_loss, metrics


class FocalLoss(nn.Module):
    """
    Focal loss for handling class imbalance in anomaly detection.

    Reduces loss for well-classified examples, focusing on hard examples.
    """

    def __init__(
        self,
        alpha: float = 0.25,
        gamma: float = 2.0,
        reduction: str = 'mean'
    ):
        super().__init__()
        self.alpha = alpha
        self.gamma = gamma
        self.reduction = reduction

    def forward(
        self,
        inputs: torch.Tensor,
        targets: torch.Tensor
    ) -> torch.Tensor:
        """
        Compute focal loss.

        Args:
            inputs: Logits [batch, ...]
            targets: Binary labels [batch, ...]
        """
        p = torch.sigmoid(inputs)
        ce_loss = F.binary_cross_entropy_with_logits(inputs, targets, reduction='none')

        # Focal weight
        p_t = p * targets + (1 - p) * (1 - targets)
        alpha_t = self.alpha * targets + (1 - self.alpha) * (1 - targets)
        focal_weight = alpha_t * (1 - p_t) ** self.gamma

        loss = focal_weight * ce_loss

        if self.reduction == 'mean':
            return loss.mean()
        elif self.reduction == 'sum':
            return loss.sum()
        return loss


class SmoothL1Loss(nn.Module):
    """
    Smooth L1 loss for regression tasks.

    Less sensitive to outliers than MSE.
    """

    def __init__(self, beta: float = 1.0, reduction: str = 'mean'):
        super().__init__()
        self.beta = beta
        self.reduction = reduction

    def forward(
        self,
        inputs: torch.Tensor,
        targets: torch.Tensor
    ) -> torch.Tensor:
        diff = torch.abs(inputs - targets)
        loss = torch.where(
            diff < self.beta,
            0.5 * diff ** 2 / self.beta,
            diff - 0.5 * self.beta
        )

        if self.reduction == 'mean':
            return loss.mean()
        elif self.reduction == 'sum':
            return loss.sum()
        return loss
