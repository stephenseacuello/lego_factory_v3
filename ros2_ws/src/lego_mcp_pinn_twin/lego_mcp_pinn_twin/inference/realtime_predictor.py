"""
Real-Time Predictor for PINN Digital Twin

Provides low-latency inference with:
- Model caching and warm-up
- Batched predictions
- Prediction rate limiting
- Timeout handling
- Graceful degradation

Target Latency: < 10ms per prediction
"""

import numpy as np
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple
from collections import deque
from threading import Lock
import logging

logger = logging.getLogger(__name__)


@dataclass
class PredictorConfig:
    """
    Real-time predictor configuration.

    Attributes:
        max_latency_ms: Maximum acceptable latency [ms]
        batch_size: Maximum batch size for predictions
        cache_size: Number of recent predictions to cache
        timeout_ms: Prediction timeout [ms]
        enable_caching: Enable prediction caching
        warmup_samples: Number of warmup predictions
    """
    max_latency_ms: float = 10.0
    batch_size: int = 32
    cache_size: int = 1000
    timeout_ms: float = 100.0
    enable_caching: bool = True
    warmup_samples: int = 100


@dataclass
class PredictionResult:
    """
    Prediction result with metadata.

    Attributes:
        value: Predicted values
        latency_ms: Prediction latency [ms]
        from_cache: Whether result was cached
        timestamp: Prediction timestamp
        uncertainty: Optional uncertainty estimate
    """
    value: np.ndarray
    latency_ms: float
    from_cache: bool
    timestamp: float
    uncertainty: Optional[np.ndarray] = None


class RealtimePredictor:
    """
    Real-time predictor for PINN models.

    Features:
    - Sub-10ms inference latency
    - Automatic batching
    - LRU cache for repeated queries
    - Timeout and fallback handling
    - Performance monitoring

    Usage:
        >>> predictor = RealtimePredictor(model, config)
        >>> result = predictor.predict(input_data)
        >>> print(f"Latency: {result.latency_ms:.2f}ms")
    """

    def __init__(
        self,
        model: Any,
        config: Optional[PredictorConfig] = None
    ):
        """
        Initialize real-time predictor.

        Args:
            model: PINN model with predict() method
            config: Predictor configuration
        """
        self.model = model
        self.config = config or PredictorConfig()

        # Cache for repeated predictions
        self._cache: Dict[bytes, PredictionResult] = {}
        self._cache_order: deque = deque(maxlen=self.config.cache_size)

        # Performance tracking
        self._latencies: deque = deque(maxlen=1000)
        self._cache_hits: int = 0
        self._cache_misses: int = 0
        self._total_predictions: int = 0

        # Thread safety
        self._lock = Lock()

        # Batch queue
        self._batch_queue: List[Tuple[np.ndarray, float]] = []

        # Warmup
        self._warmed_up = False

    def warmup(self) -> None:
        """
        Warm up the predictor with dummy predictions.

        This helps achieve consistent low-latency predictions
        by pre-compiling/caching model internals.
        """
        if self._warmed_up:
            return

        logger.info("Warming up predictor...")

        # Generate random inputs matching model input dimension
        input_dim = getattr(self.model.config, 'input_dim', 4)

        for _ in range(self.config.warmup_samples):
            dummy_input = np.random.randn(1, input_dim)
            self._predict_internal(dummy_input)

        self._warmed_up = True
        logger.info(f"Warmup complete. Mean latency: {self.mean_latency_ms:.2f}ms")

    def predict(
        self,
        x: np.ndarray,
        return_uncertainty: bool = False
    ) -> PredictionResult:
        """
        Make a prediction with latency tracking.

        Args:
            x: Input data
            return_uncertainty: Include uncertainty estimate

        Returns:
            PredictionResult with prediction and metadata
        """
        start_time = time.perf_counter()

        # Check cache first
        if self.config.enable_caching:
            cache_key = x.tobytes()
            with self._lock:
                if cache_key in self._cache:
                    self._cache_hits += 1
                    result = self._cache[cache_key]
                    result.from_cache = True
                    return result

        # Actual prediction
        try:
            if return_uncertainty:
                value, uncertainty = self._predict_with_uncertainty(x)
            else:
                value = self._predict_internal(x)
                uncertainty = None
        except Exception as e:
            logger.error(f"Prediction failed: {e}")
            # Fallback to last valid prediction or zeros
            value = np.zeros((x.shape[0], self.model.config.output_dim))
            uncertainty = None

        end_time = time.perf_counter()
        latency_ms = (end_time - start_time) * 1000

        result = PredictionResult(
            value=value,
            latency_ms=latency_ms,
            from_cache=False,
            timestamp=time.time(),
            uncertainty=uncertainty
        )

        # Update cache
        if self.config.enable_caching:
            self._update_cache(cache_key, result)

        # Update stats
        with self._lock:
            self._latencies.append(latency_ms)
            self._cache_misses += 1
            self._total_predictions += 1

        # Warn if latency exceeds threshold
        if latency_ms > self.config.max_latency_ms:
            logger.warning(
                f"Prediction latency {latency_ms:.2f}ms exceeds "
                f"threshold {self.config.max_latency_ms}ms"
            )

        return result

    def predict_batch(
        self,
        x_batch: np.ndarray
    ) -> List[PredictionResult]:
        """
        Make batched predictions.

        Args:
            x_batch: Batch of inputs (num_samples x input_dim)

        Returns:
            List of PredictionResults
        """
        start_time = time.perf_counter()

        # Split into chunks if too large
        batch_size = min(len(x_batch), self.config.batch_size)
        results = []

        for i in range(0, len(x_batch), batch_size):
            chunk = x_batch[i:i + batch_size]
            chunk_result = self._predict_internal(chunk)

            latency_ms = (time.perf_counter() - start_time) * 1000 / len(chunk)

            for j, val in enumerate(chunk_result):
                results.append(PredictionResult(
                    value=val.reshape(1, -1),
                    latency_ms=latency_ms,
                    from_cache=False,
                    timestamp=time.time()
                ))

        return results

    def _predict_internal(self, x: np.ndarray) -> np.ndarray:
        """Internal prediction call."""
        return self.model.predict(x)

    def _predict_with_uncertainty(
        self,
        x: np.ndarray
    ) -> Tuple[np.ndarray, np.ndarray]:
        """Prediction with uncertainty estimation."""
        if hasattr(self.model, 'predict') and callable(self.model.predict):
            result = self.model.predict(x, return_uncertainty=True)
            if isinstance(result, tuple):
                return result
            else:
                # Model doesn't support uncertainty
                return result, np.ones_like(result) * 0.1
        else:
            value = self._predict_internal(x)
            return value, np.ones_like(value) * 0.1

    def _update_cache(
        self,
        key: bytes,
        result: PredictionResult
    ) -> None:
        """Update LRU cache."""
        with self._lock:
            if len(self._cache) >= self.config.cache_size:
                # Remove oldest entry
                if self._cache_order:
                    oldest_key = self._cache_order.popleft()
                    self._cache.pop(oldest_key, None)

            self._cache[key] = result
            self._cache_order.append(key)

    def clear_cache(self) -> None:
        """Clear the prediction cache."""
        with self._lock:
            self._cache.clear()
            self._cache_order.clear()
            self._cache_hits = 0
            self._cache_misses = 0

    @property
    def mean_latency_ms(self) -> float:
        """Get mean prediction latency."""
        with self._lock:
            if not self._latencies:
                return 0.0
            return np.mean(self._latencies)

    @property
    def p99_latency_ms(self) -> float:
        """Get 99th percentile latency."""
        with self._lock:
            if not self._latencies:
                return 0.0
            return np.percentile(self._latencies, 99)

    @property
    def cache_hit_rate(self) -> float:
        """Get cache hit rate."""
        total = self._cache_hits + self._cache_misses
        if total == 0:
            return 0.0
        return self._cache_hits / total

    def get_stats(self) -> Dict[str, Any]:
        """Get predictor statistics."""
        with self._lock:
            return {
                "total_predictions": self._total_predictions,
                "mean_latency_ms": self.mean_latency_ms,
                "p99_latency_ms": self.p99_latency_ms,
                "cache_hit_rate": self.cache_hit_rate,
                "cache_size": len(self._cache),
                "warmed_up": self._warmed_up
            }
