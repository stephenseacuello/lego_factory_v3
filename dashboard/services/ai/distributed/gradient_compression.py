"""
Gradient Compression Service
LegoMCP PhD-Level Manufacturing Platform

Implements gradient compression for efficient distributed training:
- Top-k sparsification
- Random-k sparsification
- Quantization (1-bit, TernGrad)
- PowerSGD (low-rank approximation)
- Error feedback
"""

import logging
import numpy as np
from typing import Optional, List, Dict, Any, Tuple, Union
from dataclasses import dataclass, field
from enum import Enum
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)


class CompressionType(Enum):
    NONE = "none"
    TOP_K = "top_k"
    RANDOM_K = "random_k"
    QUANTIZE_1BIT = "quantize_1bit"
    TERNGRAD = "terngrad"
    POWERSGD = "powersgd"
    FP16 = "fp16"


@dataclass
class CompressionConfig:
    """Gradient compression configuration."""
    compression_type: CompressionType = CompressionType.TOP_K
    compression_ratio: float = 0.01  # For top-k, random-k
    error_feedback: bool = True
    warmup_epochs: int = 5  # No compression during warmup
    rank: int = 4  # For PowerSGD


@dataclass
class CompressionStats:
    """Compression statistics."""
    original_size: int
    compressed_size: int
    compression_ratio: float
    sparsity: float
    error_norm: float


class GradientCompressorBase(ABC):
    """Base class for gradient compressors."""

    @abstractmethod
    def compress(
        self,
        gradient: np.ndarray,
    ) -> Tuple[Any, np.ndarray]:
        """
        Compress gradient.

        Returns:
            Compressed representation and mask/indices
        """
        pass

    @abstractmethod
    def decompress(
        self,
        compressed: Any,
        shape: Tuple[int, ...],
        mask: np.ndarray = None,
    ) -> np.ndarray:
        """Decompress to original shape."""
        pass


class TopKCompressor(GradientCompressorBase):
    """
    Top-K gradient sparsification.

    Keeps only the K largest magnitude gradients.
    """

    def __init__(self, k_ratio: float = 0.01):
        self.k_ratio = k_ratio
        self._error_buffer: Dict[str, np.ndarray] = {}

    def compress(
        self,
        gradient: np.ndarray,
        name: str = "default",
        error_feedback: bool = True,
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Compress gradient using top-k sparsification.

        Args:
            gradient: Gradient to compress
            name: Gradient name for error feedback
            error_feedback: Whether to use error feedback

        Returns:
            (values, indices) tuple
        """
        flat = gradient.flatten()

        # Add error feedback
        if error_feedback and name in self._error_buffer:
            flat = flat + self._error_buffer[name]

        # Get top-k
        k = max(1, int(len(flat) * self.k_ratio))
        indices = np.argpartition(np.abs(flat), -k)[-k:]
        values = flat[indices]

        # Store error
        if error_feedback:
            error = flat.copy()
            error[indices] = 0
            self._error_buffer[name] = error

        return (values, indices)

    def decompress(
        self,
        compressed: Tuple[np.ndarray, np.ndarray],
        shape: Tuple[int, ...],
        mask: np.ndarray = None,
    ) -> np.ndarray:
        """Decompress top-k gradient."""
        values, indices = compressed
        flat = np.zeros(np.prod(shape))
        flat[indices] = values
        return flat.reshape(shape)


class RandomKCompressor(GradientCompressorBase):
    """
    Random-K gradient sparsification.

    Randomly samples K gradients (unbiased estimator).
    """

    def __init__(self, k_ratio: float = 0.01):
        self.k_ratio = k_ratio

    def compress(
        self,
        gradient: np.ndarray,
    ) -> Tuple[np.ndarray, np.ndarray]:
        """Compress using random sampling."""
        flat = gradient.flatten()
        k = max(1, int(len(flat) * self.k_ratio))

        # Random indices
        indices = np.random.choice(len(flat), k, replace=False)
        values = flat[indices] / self.k_ratio  # Scale for unbiased estimate

        return (values, indices)

    def decompress(
        self,
        compressed: Tuple[np.ndarray, np.ndarray],
        shape: Tuple[int, ...],
        mask: np.ndarray = None,
    ) -> np.ndarray:
        """Decompress random-k gradient."""
        values, indices = compressed
        flat = np.zeros(np.prod(shape))
        flat[indices] = values
        return flat.reshape(shape)


class OneBitQuantizer(GradientCompressorBase):
    """
    1-bit gradient quantization.

    Quantizes gradients to +1/-1 based on sign.
    """

    def compress(
        self,
        gradient: np.ndarray,
    ) -> Tuple[np.ndarray, float]:
        """
        Compress using 1-bit quantization.

        Returns:
            (signs, scale) where signs are packed bits
        """
        flat = gradient.flatten()
        scale = np.abs(flat).mean()
        signs = np.sign(flat).astype(np.int8)

        # Pack bits
        packed = np.packbits(signs > 0)

        return (packed, scale)

    def decompress(
        self,
        compressed: Tuple[np.ndarray, float],
        shape: Tuple[int, ...],
        mask: np.ndarray = None,
    ) -> np.ndarray:
        """Decompress 1-bit quantized gradient."""
        packed, scale = compressed
        n_elements = np.prod(shape)

        # Unpack bits
        unpacked = np.unpackbits(packed)[:n_elements]
        signs = unpacked.astype(np.float32) * 2 - 1

        return (signs * scale).reshape(shape)


class TernGradCompressor(GradientCompressorBase):
    """
    TernGrad: Ternary gradient compression.

    Quantizes to {-1, 0, +1} with stochastic rounding.
    """

    def compress(
        self,
        gradient: np.ndarray,
    ) -> Tuple[np.ndarray, float]:
        """Compress using ternary quantization."""
        flat = gradient.flatten()
        max_val = np.max(np.abs(flat))

        if max_val == 0:
            return (np.zeros_like(flat, dtype=np.int8), 0.0)

        # Stochastic ternary quantization
        probs = np.abs(flat) / max_val
        random_vals = np.random.rand(len(flat))

        ternary = np.zeros_like(flat, dtype=np.int8)
        mask = random_vals < probs
        ternary[mask] = np.sign(flat[mask]).astype(np.int8)

        return (ternary, float(max_val))

    def decompress(
        self,
        compressed: Tuple[np.ndarray, float],
        shape: Tuple[int, ...],
        mask: np.ndarray = None,
    ) -> np.ndarray:
        """Decompress ternary gradient."""
        ternary, scale = compressed
        return (ternary.astype(np.float32) * scale).reshape(shape)


class PowerSGDCompressor(GradientCompressorBase):
    """
    PowerSGD: Low-rank gradient compression.

    Uses power iteration to find low-rank approximation.
    """

    def __init__(self, rank: int = 4, n_iters: int = 2):
        self.rank = rank
        self.n_iters = n_iters
        self._Q: Dict[str, np.ndarray] = {}  # Persistent Q matrices

    def compress(
        self,
        gradient: np.ndarray,
        name: str = "default",
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Compress using low-rank approximation.

        Returns:
            (P, Q) matrices where gradient ≈ P @ Q.T
        """
        # Reshape to 2D
        if gradient.ndim == 1:
            M = gradient.reshape(-1, 1)
        elif gradient.ndim == 2:
            M = gradient
        else:
            # Flatten all but first dimension
            M = gradient.reshape(gradient.shape[0], -1)

        m, n = M.shape
        rank = min(self.rank, m, n)

        # Initialize or reuse Q
        if name not in self._Q or self._Q[name].shape != (n, rank):
            self._Q[name] = np.random.randn(n, rank)
            self._Q[name], _ = np.linalg.qr(self._Q[name])

        Q = self._Q[name]

        # Power iteration
        for _ in range(self.n_iters):
            P = M @ Q
            P, _ = np.linalg.qr(P)
            Q = M.T @ P
            Q, _ = np.linalg.qr(Q)

        self._Q[name] = Q

        # Final P
        P = M @ Q

        return (P, Q)

    def decompress(
        self,
        compressed: Tuple[np.ndarray, np.ndarray],
        shape: Tuple[int, ...],
        mask: np.ndarray = None,
    ) -> np.ndarray:
        """Decompress low-rank gradient."""
        P, Q = compressed
        M = P @ Q.T
        return M.reshape(shape)


class GradientCompressor:
    """
    Unified gradient compression interface.

    Supports multiple compression methods with
    automatic selection and error feedback.
    """

    def __init__(self, config: CompressionConfig = None):
        self.config = config or CompressionConfig()

        self._compressors: Dict[CompressionType, GradientCompressorBase] = {
            CompressionType.TOP_K: TopKCompressor(self.config.compression_ratio),
            CompressionType.RANDOM_K: RandomKCompressor(self.config.compression_ratio),
            CompressionType.QUANTIZE_1BIT: OneBitQuantizer(),
            CompressionType.TERNGRAD: TernGradCompressor(),
            CompressionType.POWERSGD: PowerSGDCompressor(self.config.rank),
        }

        self._current_epoch = 0
        self._stats_history: List[CompressionStats] = []

    def compress(
        self,
        gradients: Dict[str, np.ndarray],
        epoch: int = None,
    ) -> Dict[str, Any]:
        """
        Compress gradients for all parameters.

        Args:
            gradients: Dict of parameter name -> gradient
            epoch: Current epoch for warmup

        Returns:
            Dict of parameter name -> compressed gradient
        """
        if epoch is not None:
            self._current_epoch = epoch

        # No compression during warmup
        if self._current_epoch < self.config.warmup_epochs:
            return gradients

        if self.config.compression_type == CompressionType.NONE:
            return gradients

        compressor = self._compressors.get(self.config.compression_type)
        if compressor is None:
            return gradients

        compressed = {}
        total_original = 0
        total_compressed = 0

        for name, grad in gradients.items():
            original_size = grad.nbytes
            total_original += original_size

            if isinstance(compressor, (TopKCompressor, PowerSGDCompressor)):
                comp = compressor.compress(grad, name=name)
            else:
                comp = compressor.compress(grad)

            compressed[name] = {
                "data": comp,
                "shape": grad.shape,
                "dtype": str(grad.dtype),
            }

            # Estimate compressed size
            if isinstance(comp, tuple):
                compressed_size = sum(
                    c.nbytes if hasattr(c, 'nbytes') else 8
                    for c in comp
                )
            else:
                compressed_size = comp.nbytes if hasattr(comp, 'nbytes') else 8

            total_compressed += compressed_size

        # Record stats
        self._stats_history.append(CompressionStats(
            original_size=total_original,
            compressed_size=total_compressed,
            compression_ratio=total_compressed / total_original if total_original > 0 else 1.0,
            sparsity=1 - self.config.compression_ratio,
            error_norm=0.0,
        ))

        return compressed

    def decompress(
        self,
        compressed: Dict[str, Any],
    ) -> Dict[str, np.ndarray]:
        """Decompress gradients."""
        if self.config.compression_type == CompressionType.NONE:
            return compressed

        compressor = self._compressors.get(self.config.compression_type)
        if compressor is None:
            return compressed

        decompressed = {}
        for name, comp_data in compressed.items():
            if isinstance(comp_data, dict):
                grad = compressor.decompress(
                    comp_data["data"],
                    comp_data["shape"],
                )
            else:
                grad = comp_data

            decompressed[name] = grad

        return decompressed

    def get_statistics(self) -> Dict[str, Any]:
        """Get compression statistics."""
        if not self._stats_history:
            return {}

        recent = self._stats_history[-100:]
        return {
            "compression_type": self.config.compression_type.value,
            "average_compression_ratio": np.mean([s.compression_ratio for s in recent]),
            "total_original_bytes": sum(s.original_size for s in recent),
            "total_compressed_bytes": sum(s.compressed_size for s in recent),
            "bandwidth_savings": 1 - np.mean([s.compression_ratio for s in recent]),
        }


class AdaptiveCompressor(GradientCompressor):
    """
    Adaptive gradient compressor.

    Automatically adjusts compression based on:
    - Training progress
    - Gradient statistics
    - Communication costs
    """

    def __init__(self, config: CompressionConfig = None):
        super().__init__(config)
        self._gradient_norms: Dict[str, List[float]] = {}

    def compress(
        self,
        gradients: Dict[str, np.ndarray],
        epoch: int = None,
    ) -> Dict[str, Any]:
        """Compress with adaptive ratio."""
        # Track gradient norms
        for name, grad in gradients.items():
            norm = np.linalg.norm(grad)
            if name not in self._gradient_norms:
                self._gradient_norms[name] = []
            self._gradient_norms[name].append(norm)

        # Adjust compression ratio based on gradient variance
        if epoch and epoch > self.config.warmup_epochs:
            self._adapt_compression_ratio()

        return super().compress(gradients, epoch)

    def _adapt_compression_ratio(self):
        """Adapt compression ratio based on gradients."""
        variances = []
        for name, norms in self._gradient_norms.items():
            if len(norms) > 10:
                recent = norms[-10:]
                variances.append(np.var(recent) / (np.mean(recent) ** 2 + 1e-8))

        if variances:
            avg_cv = np.mean(variances)  # Coefficient of variation

            # Higher variance -> less compression
            if avg_cv > 0.5:
                new_ratio = min(0.1, self.config.compression_ratio * 1.5)
            elif avg_cv < 0.1:
                new_ratio = max(0.001, self.config.compression_ratio * 0.7)
            else:
                new_ratio = self.config.compression_ratio

            # Update compressor
            if self.config.compression_type == CompressionType.TOP_K:
                self._compressors[CompressionType.TOP_K] = TopKCompressor(new_ratio)
            elif self.config.compression_type == CompressionType.RANDOM_K:
                self._compressors[CompressionType.RANDOM_K] = RandomKCompressor(new_ratio)


# Global instances
gradient_compressor = GradientCompressor()
adaptive_compressor = AdaptiveCompressor()
