"""
Uncertainty Quantification Service
==================================

LegoMCP PhD-Level Manufacturing Platform
Part of the Advanced AI/ML Operations (Phase 8.2)

This module implements comprehensive uncertainty estimation methods for
manufacturing AI predictions. Uncertainty quantification is critical for:

- **Quality Control**: Flagging low-confidence defect predictions for human review
- **Predictive Maintenance**: Providing confidence bounds on RUL (Remaining Useful Life)
- **Process Optimization**: Understanding parameter sensitivity and prediction reliability
- **Safety-Critical Decisions**: Ensuring predictions meet reliability thresholds

Uncertainty Types:
------------------
1. **Epistemic Uncertainty** (Model Uncertainty):
   - Caused by limited training data or model capacity
   - Can be reduced with more data
   - Captured by: MC Dropout, Deep Ensembles

2. **Aleatoric Uncertainty** (Data Uncertainty):
   - Inherent noise in the data/process
   - Cannot be reduced with more data
   - Captured by: Heteroscedastic models, variance outputs

Implementation Notes:
---------------------
- All estimators follow the UncertaintyEstimatorBase interface
- Results are returned in UncertaintyResult dataclass for consistency
- Methods gracefully degrade to mock implementations when PyTorch unavailable
- Confidence intervals use percentile-based or parametric approaches

References:
-----------
[1] Gal, Y., & Ghahramani, Z. (2016). Dropout as a Bayesian Approximation:
    Representing Model Uncertainty in Deep Learning. ICML.
[2] Lakshminarayanan, B., et al. (2017). Simple and Scalable Predictive
    Uncertainty Estimation using Deep Ensembles. NeurIPS.
[3] Vovk, V., et al. (2005). Algorithmic Learning in a Random World.
    Springer. (Conformal Prediction)
[4] Guo, C., et al. (2017). On Calibration of Modern Neural Networks. ICML.
"""

import logging
import numpy as np
from typing import Optional, List, Dict, Any, Tuple, Union, Callable
from dataclasses import dataclass, field
from enum import Enum
from abc import ABC, abstractmethod

# Configure module logger
logger = logging.getLogger(__name__)


# =============================================================================
# ENUMERATIONS
# =============================================================================

class UncertaintyMethod(Enum):
    """
    Available uncertainty estimation methods.

    Each method has different characteristics:
    - MC_DROPOUT: Fast, requires dropout layers, approximates Bayesian inference
    - DEEP_ENSEMBLE: Most accurate, requires multiple trained models
    - CONFORMAL: Distribution-free, requires calibration set
    - BAYESIAN: Full Bayesian inference, computationally expensive
    - TEMPERATURE_SCALING: For classification calibration only
    """
    MC_DROPOUT = "mc_dropout"           # Monte Carlo Dropout
    DEEP_ENSEMBLE = "deep_ensemble"     # Ensemble of independently trained models
    CONFORMAL = "conformal"             # Conformal prediction intervals
    BAYESIAN = "bayesian"               # Full Bayesian neural network
    TEMPERATURE_SCALING = "temperature_scaling"  # Post-hoc calibration


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class UncertaintyResult:
    """
    Container for uncertainty estimation results.

    This dataclass standardizes the output from all uncertainty estimators,
    providing consistent access to predictions, uncertainty measures, and
    confidence intervals.

    Attributes:
        prediction: Mean/point prediction from the model
        uncertainty: Total uncertainty estimate (standard deviation)
        confidence_lower: Lower bound of confidence interval
        confidence_upper: Upper bound of confidence interval
        confidence_level: Probability level for intervals (e.g., 0.95 = 95%)
        method: Which uncertainty method was used
        epistemic_uncertainty: Model uncertainty component (reducible)
        aleatoric_uncertainty: Data uncertainty component (irreducible)
        metadata: Additional method-specific information

    Example:
        >>> result = estimator.estimate(model, inputs)
        >>> print(f"Prediction: {result.prediction[0]:.2f}")
        >>> print(f"95% CI: [{result.confidence_lower[0]:.2f}, "
        ...       f"{result.confidence_upper[0]:.2f}]")
        >>> if result.is_reliable[0]:
        ...     print("High confidence prediction")
    """
    # Core outputs
    prediction: np.ndarray          # Shape: (n_samples, n_outputs)
    uncertainty: np.ndarray         # Shape: (n_samples, n_outputs)
    confidence_lower: np.ndarray    # Shape: (n_samples, n_outputs)
    confidence_upper: np.ndarray    # Shape: (n_samples, n_outputs)

    # Configuration
    confidence_level: float = 0.95
    method: UncertaintyMethod = UncertaintyMethod.MC_DROPOUT

    # Decomposed uncertainty (optional)
    epistemic_uncertainty: Optional[np.ndarray] = None  # Model uncertainty
    aleatoric_uncertainty: Optional[np.ndarray] = None  # Data uncertainty

    # Additional information
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert result to JSON-serializable dictionary.

        Useful for API responses and logging.

        Returns:
            Dictionary with all uncertainty information
        """
        return {
            "prediction": self.prediction.tolist(),
            "uncertainty": self.uncertainty.tolist(),
            "confidence_lower": self.confidence_lower.tolist(),
            "confidence_upper": self.confidence_upper.tolist(),
            "confidence_level": self.confidence_level,
            "method": self.method.value,
            "epistemic_uncertainty": (
                self.epistemic_uncertainty.tolist()
                if self.epistemic_uncertainty is not None else None
            ),
            "aleatoric_uncertainty": (
                self.aleatoric_uncertainty.tolist()
                if self.aleatoric_uncertainty is not None else None
            ),
            "metadata": self.metadata,
        }

    @property
    def is_reliable(self) -> np.ndarray:
        """
        Determine which predictions are reliable (low uncertainty).

        Uses the 75th percentile of uncertainty as threshold.
        Predictions below this threshold are considered reliable.

        Returns:
            Boolean array where True indicates reliable prediction
        """
        threshold = np.percentile(self.uncertainty, 75)
        return self.uncertainty < threshold

    @property
    def interval_width(self) -> np.ndarray:
        """
        Calculate width of confidence intervals.

        Useful for comparing prediction precision across samples.

        Returns:
            Array of interval widths
        """
        return self.confidence_upper - self.confidence_lower


# =============================================================================
# BASE CLASS
# =============================================================================

class UncertaintyEstimatorBase(ABC):
    """
    Abstract base class for uncertainty estimators.

    All uncertainty estimation methods must implement this interface,
    ensuring consistent behavior across different approaches.

    Subclasses must implement:
        - estimate(): Core uncertainty estimation method
    """

    @abstractmethod
    def estimate(
        self,
        model: Any,
        inputs: np.ndarray,
        confidence_level: float = 0.95,
    ) -> UncertaintyResult:
        """
        Estimate uncertainty for model predictions.

        Args:
            model: Trained prediction model (PyTorch, sklearn, etc.)
            inputs: Input data array of shape (n_samples, n_features)
            confidence_level: Desired confidence level (0-1) for intervals

        Returns:
            UncertaintyResult containing predictions and uncertainty estimates

        Raises:
            ValueError: If inputs are invalid or model incompatible
        """
        pass


# =============================================================================
# MONTE CARLO DROPOUT
# =============================================================================

class MCDropout(UncertaintyEstimatorBase):
    """
    Monte Carlo Dropout for Bayesian uncertainty estimation.

    This method uses dropout at inference time with multiple forward passes
    to approximate Bayesian inference. By keeping dropout active during
    prediction, we sample from the posterior distribution of model weights.

    Theory:
    -------
    Dropout can be interpreted as approximate variational inference in a
    Bayesian neural network. Each forward pass with dropout samples a
    different "sub-network", and the variance across samples estimates
    model (epistemic) uncertainty.

    Key Properties:
    ---------------
    - Captures epistemic uncertainty (model uncertainty)
    - Requires model to have dropout layers
    - Computational cost scales linearly with n_samples
    - No additional training required

    Manufacturing Applications:
    ---------------------------
    - Defect detection with confidence scoring
    - Process parameter prediction uncertainty
    - Sensor anomaly detection reliability

    References:
    -----------
    Gal & Ghahramani (2016): "Dropout as a Bayesian Approximation"

    Attributes:
        n_samples: Number of forward passes (more = better estimate, slower)
        dropout_rate: Dropout probability (typically 0.1-0.5)

    Example:
        >>> mc_dropout = MCDropout(n_samples=100, dropout_rate=0.2)
        >>> result = mc_dropout.estimate(model, sensor_data, confidence_level=0.95)
        >>> print(f"Epistemic uncertainty: {result.epistemic_uncertainty.mean():.4f}")
    """

    def __init__(
        self,
        n_samples: int = 100,
        dropout_rate: float = 0.1,
    ):
        """
        Initialize MC Dropout estimator.

        Args:
            n_samples: Number of stochastic forward passes (default: 100)
                       Higher values give more accurate estimates but are slower.
                       Recommended: 50-200 for production use.
            dropout_rate: Dropout probability to use during inference.
                          Should match training dropout rate for best results.
        """
        self.n_samples = n_samples
        self.dropout_rate = dropout_rate

    def estimate(
        self,
        model: Any,
        inputs: np.ndarray,
        confidence_level: float = 0.95,
    ) -> UncertaintyResult:
        """
        Estimate uncertainty using MC Dropout.

        Performs multiple forward passes with dropout enabled, then computes
        mean prediction and uncertainty from the distribution of outputs.

        Args:
            model: PyTorch model with dropout layers
            inputs: Input data of shape (n_samples, n_features)
            confidence_level: Confidence level for prediction intervals

        Returns:
            UncertaintyResult with:
                - prediction: Mean across forward passes
                - uncertainty: Std dev across forward passes (epistemic)
                - confidence_lower/upper: Percentile-based intervals

        Note:
            If PyTorch is unavailable, returns mock predictions for testing.
        """
        predictions = []

        try:
            import torch

            # Enable dropout during inference (train mode activates dropout)
            model.train()

            with torch.no_grad():
                for _ in range(self.n_samples):
                    # Convert numpy to tensor if needed
                    if isinstance(inputs, np.ndarray):
                        x = torch.tensor(inputs, dtype=torch.float32)
                    else:
                        x = inputs

                    # Forward pass with dropout active
                    pred = model(x).cpu().numpy()
                    predictions.append(pred)

            # Restore evaluation mode
            model.eval()

        except ImportError:
            # Mock implementation for testing without PyTorch
            logger.warning("PyTorch not available, using mock predictions")
            for _ in range(self.n_samples):
                noise = np.random.randn(*inputs.shape[:-1], 1) * 0.1
                pred = inputs.mean(axis=-1, keepdims=True) + noise
                predictions.append(pred)

        # Stack predictions: shape (n_samples, n_data_points, n_outputs)
        predictions = np.array(predictions)

        # Compute statistics across forward passes
        mean_pred = predictions.mean(axis=0)  # Mean prediction
        epistemic = predictions.std(axis=0)   # Epistemic uncertainty (std dev)

        # Compute percentile-based confidence intervals
        alpha = 1 - confidence_level
        lower = np.percentile(predictions, alpha / 2 * 100, axis=0)
        upper = np.percentile(predictions, (1 - alpha / 2) * 100, axis=0)

        return UncertaintyResult(
            prediction=mean_pred,
            uncertainty=epistemic,
            confidence_lower=lower,
            confidence_upper=upper,
            confidence_level=confidence_level,
            method=UncertaintyMethod.MC_DROPOUT,
            epistemic_uncertainty=epistemic,
            aleatoric_uncertainty=None,  # MC Dropout doesn't separate aleatoric
            metadata={
                "n_samples": self.n_samples,
                "dropout_rate": self.dropout_rate,
            },
        )


# =============================================================================
# DEEP ENSEMBLE
# =============================================================================

class DeepEnsemble(UncertaintyEstimatorBase):
    """
    Deep Ensemble for robust uncertainty estimation.

    Uses multiple independently trained models to estimate both epistemic
    and aleatoric uncertainty. Each model is trained with different random
    initialization and data shuffling.

    Theory:
    -------
    The variance across ensemble members captures epistemic uncertainty,
    while the average of individual model variances captures aleatoric
    uncertainty. Deep ensembles are considered the gold standard for
    uncertainty estimation in deep learning.

    Key Properties:
    ---------------
    - Captures both epistemic and aleatoric uncertainty
    - More accurate than MC Dropout in most cases
    - Requires training multiple models (5-10 typically)
    - Predictions are averaged for better accuracy

    Manufacturing Applications:
    ---------------------------
    - Critical quality predictions requiring high reliability
    - Predictive maintenance with confidence bounds
    - Process control with uncertainty-aware decisions

    References:
    -----------
    Lakshminarayanan et al. (2017): "Simple and Scalable Predictive
    Uncertainty Estimation using Deep Ensembles"

    Attributes:
        models: List of trained ensemble members

    Example:
        >>> ensemble = DeepEnsemble()
        >>> for model in trained_models:
        ...     ensemble.add_model(model)
        >>> result = ensemble.estimate(inputs=sensor_data)
    """

    def __init__(self, models: List[Any] = None):
        """
        Initialize Deep Ensemble.

        Args:
            models: Optional list of pre-trained models to include.
                    Models can also be added later with add_model().
        """
        self.models = models or []

    def add_model(self, model: Any) -> None:
        """
        Add a trained model to the ensemble.

        Args:
            model: Trained model instance (should have same architecture
                   as other ensemble members)
        """
        self.models.append(model)
        logger.info(f"Added model to ensemble. Total: {len(self.models)}")

    def estimate(
        self,
        model: Any = None,
        inputs: np.ndarray = None,
        confidence_level: float = 0.95,
    ) -> UncertaintyResult:
        """
        Estimate uncertainty using deep ensemble.

        Runs each ensemble member on the inputs, then computes uncertainty
        from the distribution of predictions.

        Args:
            model: Ignored (uses self.models instead)
            inputs: Input data of shape (n_samples, n_features)
            confidence_level: Confidence level for prediction intervals

        Returns:
            UncertaintyResult with:
                - prediction: Mean across ensemble
                - uncertainty: Total uncertainty (sqrt of combined variance)
                - epistemic_uncertainty: Variance across ensemble members
                - aleatoric_uncertainty: Mean of predicted variances (if available)

        Raises:
            ValueError: If no models in ensemble
        """
        if not self.models:
            raise ValueError("No models in ensemble. Add models with add_model().")

        predictions = []
        variances = []  # For models that output variance

        try:
            import torch

            for m in self.models:
                m.eval()
                with torch.no_grad():
                    if isinstance(inputs, np.ndarray):
                        x = torch.tensor(inputs, dtype=torch.float32)
                    else:
                        x = inputs

                    # Handle models that output (mean, variance) tuple
                    output = m(x)
                    if isinstance(output, tuple) and len(output) == 2:
                        pred, var = output
                        predictions.append(pred.cpu().numpy())
                        variances.append(var.cpu().numpy())
                    else:
                        predictions.append(output.cpu().numpy())

        except ImportError:
            # Mock implementation for testing
            logger.warning("PyTorch not available, using mock predictions")
            for i in range(len(self.models)):
                noise = np.random.randn(*inputs.shape[:-1], 1) * 0.1
                pred = inputs.mean(axis=-1, keepdims=True) + noise * (i + 1)
                predictions.append(pred)

        # Stack predictions
        predictions = np.array(predictions)

        # Compute ensemble mean
        mean_pred = predictions.mean(axis=0)

        # Epistemic uncertainty: variance across ensemble members
        epistemic = predictions.var(axis=0)

        # Aleatoric uncertainty: mean of predicted variances (if available)
        if variances:
            aleatoric = np.array(variances).mean(axis=0)
        else:
            aleatoric = None

        # Total uncertainty: epistemic + aleatoric
        total = epistemic if aleatoric is None else epistemic + aleatoric

        # Compute parametric confidence intervals using z-score
        z = self._get_z_score(confidence_level)
        lower = mean_pred - z * np.sqrt(total)
        upper = mean_pred + z * np.sqrt(total)

        return UncertaintyResult(
            prediction=mean_pred,
            uncertainty=np.sqrt(total),
            confidence_lower=lower,
            confidence_upper=upper,
            confidence_level=confidence_level,
            method=UncertaintyMethod.DEEP_ENSEMBLE,
            epistemic_uncertainty=np.sqrt(epistemic),
            aleatoric_uncertainty=np.sqrt(aleatoric) if aleatoric is not None else None,
            metadata={"n_models": len(self.models)},
        )

    def _get_z_score(self, confidence_level: float) -> float:
        """
        Get z-score for given confidence level (normal distribution).

        Args:
            confidence_level: Desired confidence level (e.g., 0.95)

        Returns:
            z-score value (e.g., 1.96 for 95% confidence)
        """
        try:
            from scipy import stats
            return stats.norm.ppf((1 + confidence_level) / 2)
        except ImportError:
            # Approximate z-scores for common confidence levels
            z_table = {0.90: 1.645, 0.95: 1.96, 0.99: 2.576}
            return z_table.get(confidence_level, 1.96)


# =============================================================================
# CONFORMAL PREDICTION
# =============================================================================

class ConformalPredictor(UncertaintyEstimatorBase):
    """
    Conformal Prediction for distribution-free uncertainty.

    Provides valid prediction intervals without assumptions about the
    underlying data distribution. Uses a calibration set to compute
    non-conformity scores, then applies these to new predictions.

    Theory:
    -------
    Conformal prediction guarantees that the true value falls within
    the prediction interval with probability >= confidence_level,
    regardless of the data distribution. This is achieved by using
    a holdout calibration set to empirically determine interval widths.

    Key Properties:
    ---------------
    - Distribution-free: No assumptions about data distribution
    - Finite-sample guarantees: Valid for any sample size
    - Requires calibration set (holdout data)
    - Intervals may be conservative but always valid

    Manufacturing Applications:
    ---------------------------
    - Quality predictions requiring guaranteed coverage
    - Regulatory compliance with confidence requirements
    - Safety-critical decisions with provable bounds

    References:
    -----------
    Vovk, V., et al. (2005): "Algorithmic Learning in a Random World"
    Romano et al. (2019): "Conformalized Quantile Regression"

    Attributes:
        calibration_scores: Non-conformity scores from calibration set

    Example:
        >>> conformal = ConformalPredictor()
        >>> conformal.calibrate(val_predictions, val_true_values)
        >>> result = conformal.estimate(model, test_inputs, confidence_level=0.95)
    """

    def __init__(self, calibration_data: Tuple[np.ndarray, np.ndarray] = None):
        """
        Initialize Conformal Predictor.

        Args:
            calibration_data: Optional tuple of (predictions, true_values)
                              for immediate calibration. Can also calibrate
                              later with calibrate() method.
        """
        self.calibration_scores = None
        if calibration_data is not None:
            self.calibrate(*calibration_data)

    def calibrate(
        self,
        predictions: np.ndarray,
        true_values: np.ndarray,
    ) -> None:
        """
        Calibrate conformal predictor using holdout data.

        Computes non-conformity scores (absolute residuals) from the
        calibration set. These scores determine prediction interval widths.

        Args:
            predictions: Model predictions on calibration set
            true_values: True target values for calibration set

        Note:
            Calibration set should be representative of test distribution.
            Larger calibration sets give tighter intervals.
        """
        # Compute non-conformity scores as absolute residuals
        self.calibration_scores = np.abs(true_values - predictions).flatten()
        logger.info(
            f"Calibrated conformal predictor with {len(self.calibration_scores)} samples. "
            f"Median score: {np.median(self.calibration_scores):.4f}"
        )

    def estimate(
        self,
        model: Any,
        inputs: np.ndarray,
        confidence_level: float = 0.95,
    ) -> UncertaintyResult:
        """
        Estimate uncertainty using conformal prediction.

        Computes prediction intervals by finding the quantile of calibration
        scores that provides the desired coverage level.

        Args:
            model: Trained prediction model
            inputs: Input data of shape (n_samples, n_features)
            confidence_level: Desired coverage probability (0-1)

        Returns:
            UncertaintyResult with conformal prediction intervals

        Raises:
            ValueError: If predictor not calibrated
        """
        if self.calibration_scores is None:
            raise ValueError(
                "Conformal predictor not calibrated. "
                "Call calibrate(predictions, true_values) first."
            )

        # Get point predictions from model
        try:
            import torch

            model.eval()
            with torch.no_grad():
                if isinstance(inputs, np.ndarray):
                    x = torch.tensor(inputs, dtype=torch.float32)
                else:
                    x = inputs
                predictions = model(x).cpu().numpy()
        except (ImportError, AttributeError):
            # Fallback for testing
            predictions = inputs.mean(axis=-1, keepdims=True)

        # Compute conformal quantile
        # Using finite-sample correction: ceil((n+1) * level) / n
        n = len(self.calibration_scores)
        quantile_level = np.ceil((n + 1) * confidence_level) / n
        quantile_level = min(quantile_level, 1.0)

        # Get the quantile of non-conformity scores
        q = np.quantile(self.calibration_scores, quantile_level)

        # Prediction intervals: prediction +/- quantile
        lower = predictions - q
        upper = predictions + q

        return UncertaintyResult(
            prediction=predictions,
            uncertainty=np.full_like(predictions, q),  # Uniform uncertainty
            confidence_lower=lower,
            confidence_upper=upper,
            confidence_level=confidence_level,
            method=UncertaintyMethod.CONFORMAL,
            metadata={
                "n_calibration": len(self.calibration_scores),
                "quantile": float(q),
                "quantile_level": float(quantile_level),
            },
        )


# =============================================================================
# TEMPERATURE SCALING
# =============================================================================

class TemperatureScaling:
    """
    Temperature scaling for classification probability calibration.

    Adjusts model confidence (softmax probabilities) to match empirical
    accuracy. After calibration, a prediction with 80% confidence will
    be correct approximately 80% of the time.

    Theory:
    -------
    Modern neural networks tend to be overconfident. Temperature scaling
    divides logits by a learned temperature parameter T > 1, which
    "softens" the probability distribution and typically improves
    calibration without affecting accuracy.

    Key Properties:
    ---------------
    - Post-hoc calibration (no retraining needed)
    - Single parameter to learn (T)
    - Preserves model accuracy and ranking
    - For classification only

    Manufacturing Applications:
    ---------------------------
    - Defect classification confidence calibration
    - Quality grade prediction reliability
    - Multi-class fault diagnosis

    References:
    -----------
    Guo et al. (2017): "On Calibration of Modern Neural Networks"

    Attributes:
        temperature: Learned temperature parameter (T >= 1)

    Example:
        >>> scaler = TemperatureScaling()
        >>> scaler.calibrate(val_logits, val_labels)
        >>> calibrated_probs = scaler.get_calibrated_probs(test_logits)
    """

    def __init__(self):
        """Initialize temperature scaling with T=1 (no scaling)."""
        self.temperature = 1.0

    def calibrate(
        self,
        logits: np.ndarray,
        labels: np.ndarray,
    ) -> None:
        """
        Learn optimal temperature from validation data.

        Minimizes negative log-likelihood on the validation set by
        optimizing the temperature parameter.

        Args:
            logits: Model logits (pre-softmax) of shape (n_samples, n_classes)
            labels: True class labels of shape (n_samples,)
        """
        try:
            import torch
            import torch.nn as nn
            from torch.optim import LBFGS

            # Convert to tensors
            logits_t = torch.tensor(logits, dtype=torch.float32)
            labels_t = torch.tensor(labels, dtype=torch.long)

            # Temperature as learnable parameter
            temperature = nn.Parameter(torch.ones(1))

            # Optimize using L-BFGS (good for single-parameter optimization)
            optimizer = LBFGS([temperature], lr=0.01, max_iter=50)
            nll = nn.CrossEntropyLoss()

            def closure():
                optimizer.zero_grad()
                scaled = logits_t / temperature
                loss = nll(scaled, labels_t)
                loss.backward()
                return loss

            optimizer.step(closure)
            self.temperature = float(temperature.item())

        except ImportError:
            # Fallback: grid search for optimal temperature
            logger.warning("PyTorch not available, using grid search")
            best_temp = 1.0
            best_ece = float('inf')

            for temp in np.arange(0.5, 3.0, 0.1):
                scaled = logits / temp
                probs = self._softmax(scaled)
                ece = self._expected_calibration_error(probs, labels)
                if ece < best_ece:
                    best_ece = ece
                    best_temp = temp

            self.temperature = best_temp

        logger.info(f"Calibrated temperature: {self.temperature:.4f}")

    def scale(self, logits: np.ndarray) -> np.ndarray:
        """
        Apply temperature scaling to logits.

        Args:
            logits: Raw model logits

        Returns:
            Temperature-scaled logits
        """
        return logits / self.temperature

    def get_calibrated_probs(self, logits: np.ndarray) -> np.ndarray:
        """
        Get calibrated class probabilities.

        Args:
            logits: Raw model logits

        Returns:
            Calibrated probability distribution
        """
        scaled = self.scale(logits)
        return self._softmax(scaled)

    def _softmax(self, x: np.ndarray) -> np.ndarray:
        """
        Compute softmax probabilities (numerically stable).

        Args:
            x: Input logits

        Returns:
            Probability distribution (sums to 1)
        """
        # Subtract max for numerical stability
        exp_x = np.exp(x - np.max(x, axis=-1, keepdims=True))
        return exp_x / exp_x.sum(axis=-1, keepdims=True)

    def _expected_calibration_error(
        self,
        probs: np.ndarray,
        labels: np.ndarray,
        n_bins: int = 15,
    ) -> float:
        """
        Calculate Expected Calibration Error (ECE).

        ECE measures how well confidence matches accuracy across
        different confidence levels.

        Args:
            probs: Predicted probabilities
            labels: True labels
            n_bins: Number of confidence bins

        Returns:
            ECE value (lower is better, 0 = perfectly calibrated)
        """
        confidences = probs.max(axis=-1)
        predictions = probs.argmax(axis=-1)
        accuracies = predictions == labels

        ece = 0.0
        bin_boundaries = np.linspace(0, 1, n_bins + 1)

        for i in range(n_bins):
            # Find samples in this confidence bin
            bin_mask = (
                (confidences > bin_boundaries[i]) &
                (confidences <= bin_boundaries[i + 1])
            )
            if bin_mask.sum() > 0:
                bin_accuracy = accuracies[bin_mask].mean()
                bin_confidence = confidences[bin_mask].mean()
                bin_size = bin_mask.sum() / len(labels)
                # Weighted absolute difference
                ece += bin_size * abs(bin_accuracy - bin_confidence)

        return ece


# =============================================================================
# UNIFIED INTERFACE
# =============================================================================

class UncertaintyEstimator:
    """
    Unified interface for uncertainty estimation.

    Provides a single entry point for all uncertainty methods, with
    utilities for calibration and reliability assessment.

    This is the recommended way to use uncertainty estimation in the
    LegoMCP platform, as it handles method selection and provides
    consistent APIs across different approaches.

    Attributes:
        default_method: Method to use if not specified
        _estimators: Dictionary of available estimators
        temperature_scaler: For classification calibration

    Example:
        >>> # Initialize
        >>> estimator = UncertaintyEstimator(
        ...     default_method=UncertaintyMethod.MC_DROPOUT
        ... )

        >>> # Estimate uncertainty
        >>> result = estimator.estimate(model, inputs, confidence_level=0.95)

        >>> # Check reliability
        >>> reliable = estimator.is_prediction_reliable(result)

        >>> # For conformal prediction, calibrate first
        >>> estimator.calibrate_conformal(val_preds, val_true)
        >>> result = estimator.estimate(
        ...     model, inputs, method=UncertaintyMethod.CONFORMAL
        ... )
    """

    def __init__(
        self,
        default_method: UncertaintyMethod = UncertaintyMethod.MC_DROPOUT
    ):
        """
        Initialize unified uncertainty estimator.

        Args:
            default_method: Default method to use when not specified.
                            MC_DROPOUT is recommended as a good default.
        """
        self.default_method = default_method

        # Initialize available estimators
        self._estimators: Dict[UncertaintyMethod, UncertaintyEstimatorBase] = {
            UncertaintyMethod.MC_DROPOUT: MCDropout(),
            UncertaintyMethod.DEEP_ENSEMBLE: DeepEnsemble(),
            UncertaintyMethod.CONFORMAL: ConformalPredictor(),
        }

        # Temperature scaling for classification
        self.temperature_scaler = TemperatureScaling()

    def estimate(
        self,
        model: Any,
        inputs: np.ndarray,
        method: UncertaintyMethod = None,
        confidence_level: float = 0.95,
    ) -> UncertaintyResult:
        """
        Estimate uncertainty using specified method.

        Args:
            model: Trained prediction model
            inputs: Input data
            method: Uncertainty method (defaults to self.default_method)
            confidence_level: Confidence level for intervals

        Returns:
            UncertaintyResult with predictions and uncertainty

        Raises:
            ValueError: If unknown method specified
        """
        method = method or self.default_method
        estimator = self._estimators.get(method)

        if estimator is None:
            raise ValueError(
                f"Unknown uncertainty method: {method}. "
                f"Available: {list(self._estimators.keys())}"
            )

        return estimator.estimate(model, inputs, confidence_level)

    def calibrate_conformal(
        self,
        predictions: np.ndarray,
        true_values: np.ndarray,
    ) -> None:
        """
        Calibrate conformal predictor with validation data.

        Must be called before using CONFORMAL method.

        Args:
            predictions: Model predictions on validation set
            true_values: True values for validation set
        """
        conformal = self._estimators[UncertaintyMethod.CONFORMAL]
        conformal.calibrate(predictions, true_values)

    def calibrate_temperature(
        self,
        logits: np.ndarray,
        labels: np.ndarray,
    ) -> None:
        """
        Calibrate temperature scaling for classification.

        Args:
            logits: Model logits on validation set
            labels: True labels for validation set
        """
        self.temperature_scaler.calibrate(logits, labels)

    def add_ensemble_model(self, model: Any) -> None:
        """
        Add model to deep ensemble.

        Args:
            model: Trained model to add
        """
        ensemble = self._estimators[UncertaintyMethod.DEEP_ENSEMBLE]
        ensemble.add_model(model)

    def is_prediction_reliable(
        self,
        result: UncertaintyResult,
        threshold_percentile: float = 75,
    ) -> np.ndarray:
        """
        Determine which predictions are reliable (low uncertainty).

        Args:
            result: Uncertainty estimation result
            threshold_percentile: Percentile threshold for reliability

        Returns:
            Boolean array (True = reliable)
        """
        threshold = np.percentile(result.uncertainty, threshold_percentile)
        return result.uncertainty < threshold

    def get_rejection_curve(
        self,
        result: UncertaintyResult,
        true_values: np.ndarray,
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Compute rejection curve (accuracy vs. rejection rate).

        Shows how accuracy improves when rejecting uncertain predictions.
        Useful for determining optimal uncertainty threshold.

        Args:
            result: Uncertainty estimation result
            true_values: True target values

        Returns:
            Tuple of (rejection_rates, accuracies) arrays
        """
        errors = np.abs(result.prediction.flatten() - true_values.flatten())
        uncertainties = result.uncertainty.flatten()

        # Sort by uncertainty (ascending)
        sorted_indices = np.argsort(uncertainties)
        sorted_errors = errors[sorted_indices]

        # Compute accuracy at each rejection threshold
        n = len(sorted_errors)
        rejection_rates = np.arange(n) / n
        accuracies = []

        for i in range(n):
            if i < n - 1:
                # Accuracy on non-rejected samples
                remaining_errors = sorted_errors[:n - i]
                acc = 1 - remaining_errors.mean()
            else:
                acc = 1.0
            accuracies.append(acc)

        return rejection_rates, np.array(accuracies)


# =============================================================================
# MODULE-LEVEL INSTANCE
# =============================================================================

# Global convenience instance
uncertainty_estimator = UncertaintyEstimator()
"""
Global uncertainty estimator instance.

Provides convenient access to uncertainty estimation without explicit
instantiation. Suitable for most use cases.

Example:
    from services.ai.uncertainty import uncertainty_estimator

    result = uncertainty_estimator.estimate(model, inputs)
"""
