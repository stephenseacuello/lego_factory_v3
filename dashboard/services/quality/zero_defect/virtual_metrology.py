"""
Virtual Metrology - Predict Measurements from Process Data

LegoMCP World-Class Manufacturing System v5.0
Phase 21: Zero-Defect Manufacturing

Predicts physical measurements without actual measurement:
- Stud diameter from temperature/speed profiles
- Height accuracy from layer data
- Clutch power from material/process parameters
- Surface quality from extrusion patterns

Uses ML models trained on historical process-measurement pairs.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class PredictedDimensions:
    """Predicted dimensional measurements."""
    part_id: str
    prediction_timestamp: datetime

    # Core LEGO dimensions (mm)
    stud_diameter: float = 4.8
    stud_diameter_confidence: float = 0.95
    stud_height: float = 1.8
    stud_height_confidence: float = 0.95

    # Overall dimensions
    height_mm: float = 9.6  # Standard 1-brick height
    height_confidence: float = 0.95
    width_mm: float = 7.8  # 1 stud width with clearance
    width_confidence: float = 0.95
    length_mm: float = 7.8
    length_confidence: float = 0.95

    # Wall measurements
    wall_thickness: float = 1.6
    wall_thickness_confidence: float = 0.90

    # Derived quality metrics
    predicted_clutch_power_n: float = 2.0  # Target: 1.0-3.0N
    clutch_power_confidence: float = 0.85

    # Tolerances
    tolerance_class: str = "STANDARD"  # TIGHT, STANDARD, LOOSE
    within_spec: bool = True
    out_of_spec_dimensions: List[str] = field(default_factory=list)

    def get_tolerance_status(self) -> Dict[str, Any]:
        """Get detailed tolerance status."""
        # LEGO tolerances (mm)
        tolerances = {
            'stud_diameter': (4.78, 4.82),  # ±0.02mm
            'stud_height': (1.78, 1.82),
            'height': (9.58, 9.62),
            'width': (7.78, 7.82),
            'wall_thickness': (1.58, 1.62),
            'clutch_power': (1.0, 3.0),
        }

        status = {}
        for dim, (low, high) in tolerances.items():
            if dim == 'stud_diameter':
                value = self.stud_diameter
            elif dim == 'stud_height':
                value = self.stud_height
            elif dim == 'height':
                value = self.height_mm
            elif dim == 'width':
                value = self.width_mm
            elif dim == 'wall_thickness':
                value = self.wall_thickness
            elif dim == 'clutch_power':
                value = self.predicted_clutch_power_n
            else:
                continue

            in_spec = low <= value <= high
            deviation = 0
            if value < low:
                deviation = value - low
            elif value > high:
                deviation = value - high

            status[dim] = {
                'value': value,
                'min': low,
                'max': high,
                'in_spec': in_spec,
                'deviation': deviation,
            }

        return status


@dataclass
class ProcessMeasurementPair:
    """Training data: process parameters paired with actual measurements."""
    run_id: str
    timestamp: datetime

    # Process parameters
    nozzle_temp: float
    bed_temp: float
    print_speed: float
    layer_height: float
    extrusion_multiplier: float
    fan_speed_percent: float
    ambient_temp: float
    humidity_percent: float

    # Actual measurements (from inspection)
    actual_stud_diameter: float
    actual_stud_height: float
    actual_height: float
    actual_width: float
    actual_clutch_power: float

    def to_feature_vector(self) -> np.ndarray:
        """Convert to feature vector for ML."""
        return np.array([
            self.nozzle_temp,
            self.bed_temp,
            self.print_speed,
            self.layer_height,
            self.extrusion_multiplier,
            self.fan_speed_percent,
            self.ambient_temp,
            self.humidity_percent,
        ], dtype=np.float32)

    def to_target_vector(self) -> np.ndarray:
        """Convert to target vector for ML."""
        return np.array([
            self.actual_stud_diameter,
            self.actual_stud_height,
            self.actual_height,
            self.actual_width,
            self.actual_clutch_power,
        ], dtype=np.float32)


@dataclass
class MetrologyModel:
    """Virtual metrology prediction model."""
    model_id: str
    model_type: str  # LINEAR, POLYNOMIAL, NEURAL, GAUSSIAN_PROCESS
    target_dimension: str

    # Model parameters
    coefficients: Optional[np.ndarray] = None
    intercept: float = 0.0

    # Training metadata
    training_samples: int = 0
    training_r2: float = 0.0
    validation_mae: float = 0.0

    # Feature importance
    feature_importance: Dict[str, float] = field(default_factory=dict)

    # Calibration
    last_calibration: Optional[datetime] = None
    calibration_offset: float = 0.0

    def predict(self, features: np.ndarray) -> Tuple[float, float]:
        """
        Predict dimension value with confidence.

        Returns:
            (predicted_value, confidence)
        """
        if self.coefficients is None:
            # Default prediction without trained model
            return self._default_prediction(features)

        # Linear prediction
        prediction = np.dot(features, self.coefficients) + self.intercept
        prediction += self.calibration_offset

        # Confidence based on training R²
        confidence = min(0.99, self.training_r2)

        return float(prediction), confidence

    def _default_prediction(self, features: np.ndarray) -> Tuple[float, float]:
        """Default predictions based on process physics."""
        # Extract features
        nozzle_temp = features[0] if len(features) > 0 else 210.0
        print_speed = features[2] if len(features) > 2 else 40.0
        extrusion_mult = features[4] if len(features) > 4 else 1.0

        # Physics-based defaults for LEGO dimensions
        defaults = {
            'stud_diameter': 4.8 + (extrusion_mult - 1.0) * 0.1,
            'stud_height': 1.8,
            'height': 9.6,
            'width': 7.8 + (extrusion_mult - 1.0) * 0.05,
            'clutch_power': 2.0 + (nozzle_temp - 210) * 0.01,
        }

        value = defaults.get(self.target_dimension, 0.0)
        return value, 0.70  # Low confidence without trained model


class VirtualMetrology:
    """
    Predict physical measurements from process data.

    Eliminates need for 100% inspection by predicting quality
    from process parameters with high accuracy.
    """

    # Target dimensions to predict
    DIMENSIONS = [
        'stud_diameter',
        'stud_height',
        'height',
        'width',
        'wall_thickness',
        'clutch_power',
    ]

    # Feature names
    FEATURES = [
        'nozzle_temp',
        'bed_temp',
        'print_speed',
        'layer_height',
        'extrusion_multiplier',
        'fan_speed_percent',
        'ambient_temp',
        'humidity_percent',
    ]

    def __init__(
        self,
        min_training_samples: int = 50,
        config: Optional[Dict[str, Any]] = None,
    ):
        self.min_training_samples = min_training_samples
        self.config = config or {}

        # Models for each dimension
        self._models: Dict[str, MetrologyModel] = {}
        self._initialize_models()

        # Training data storage
        self._training_data: List[ProcessMeasurementPair] = []

        # Feature normalization
        self._feature_means: Optional[np.ndarray] = None
        self._feature_stds: Optional[np.ndarray] = None

    def _initialize_models(self) -> None:
        """Initialize models for each dimension."""
        from uuid import uuid4

        for dim in self.DIMENSIONS:
            self._models[dim] = MetrologyModel(
                model_id=str(uuid4()),
                model_type='LINEAR',
                target_dimension=dim,
            )

    def add_training_sample(self, sample: ProcessMeasurementPair) -> None:
        """Add a process-measurement pair for training."""
        self._training_data.append(sample)
        logger.debug(f"Added training sample. Total: {len(self._training_data)}")

        # Retrain if enough new samples
        if len(self._training_data) % 10 == 0:
            self._update_normalization()

    def _update_normalization(self) -> None:
        """Update feature normalization parameters."""
        if len(self._training_data) < 5:
            return

        features = np.array([s.to_feature_vector() for s in self._training_data])
        self._feature_means = np.mean(features, axis=0)
        self._feature_stds = np.std(features, axis=0) + 1e-10

    def train_model(
        self,
        dimension: str,
        force: bool = False
    ) -> Dict[str, Any]:
        """
        Train virtual metrology model for a dimension.

        Args:
            dimension: Target dimension to predict
            force: Train even with fewer than min samples

        Returns:
            Training results
        """
        if dimension not in self.DIMENSIONS:
            return {'status': 'error', 'message': f'Unknown dimension: {dimension}'}

        if len(self._training_data) < self.min_training_samples and not force:
            return {
                'status': 'insufficient_data',
                'samples': len(self._training_data),
                'required': self.min_training_samples,
            }

        # Prepare training data
        X = np.array([s.to_feature_vector() for s in self._training_data])

        # Get target values
        y_map = {
            'stud_diameter': lambda s: s.actual_stud_diameter,
            'stud_height': lambda s: s.actual_stud_height,
            'height': lambda s: s.actual_height,
            'width': lambda s: s.actual_width,
            'clutch_power': lambda s: s.actual_clutch_power,
        }

        if dimension not in y_map:
            return {'status': 'error', 'message': 'No target mapping'}

        y = np.array([y_map[dimension](s) for s in self._training_data])

        # Normalize features
        if self._feature_means is not None:
            X_norm = (X - self._feature_means) / self._feature_stds
        else:
            X_norm = X

        # Train linear regression (could be extended to more complex models)
        try:
            # Add bias term
            X_bias = np.column_stack([X_norm, np.ones(len(X_norm))])

            # Solve least squares
            coeffs, residuals, rank, s = np.linalg.lstsq(X_bias, y, rcond=None)

            # Extract coefficients and intercept
            model = self._models[dimension]
            model.coefficients = coeffs[:-1]
            model.intercept = coeffs[-1]
            model.training_samples = len(self._training_data)
            model.last_calibration = datetime.utcnow()

            # Calculate R²
            y_pred = X_bias @ coeffs
            ss_res = np.sum((y - y_pred) ** 2)
            ss_tot = np.sum((y - np.mean(y)) ** 2)
            model.training_r2 = 1 - (ss_res / (ss_tot + 1e-10))

            # Calculate MAE
            model.validation_mae = np.mean(np.abs(y - y_pred))

            # Feature importance (normalized coefficient magnitudes)
            importance = np.abs(model.coefficients) / (np.sum(np.abs(model.coefficients)) + 1e-10)
            model.feature_importance = dict(zip(self.FEATURES, importance.tolist()))

            logger.info(f"Trained {dimension} model. R²={model.training_r2:.3f}, MAE={model.validation_mae:.4f}")

            return {
                'status': 'trained',
                'dimension': dimension,
                'samples': model.training_samples,
                'r2': model.training_r2,
                'mae': model.validation_mae,
                'feature_importance': model.feature_importance,
            }

        except Exception as e:
            logger.error(f"Training error for {dimension}: {e}")
            return {'status': 'error', 'message': str(e)}

    def train_all_models(self) -> Dict[str, Any]:
        """Train models for all dimensions."""
        results = {}
        for dim in self.DIMENSIONS:
            results[dim] = self.train_model(dim)
        return results

    def predict_dimensions(
        self,
        process_data: Dict[str, float],
        part_id: str = "unknown"
    ) -> PredictedDimensions:
        """
        Predict all dimensions from process parameters.

        Args:
            process_data: Dict with keys matching FEATURES
            part_id: Part identifier

        Returns:
            PredictedDimensions with all predictions
        """
        # Build feature vector
        features = np.array([
            process_data.get('nozzle_temp', 210.0),
            process_data.get('bed_temp', 60.0),
            process_data.get('print_speed', 40.0),
            process_data.get('layer_height', 0.2),
            process_data.get('extrusion_multiplier', 1.0),
            process_data.get('fan_speed_percent', 100.0),
            process_data.get('ambient_temp', 22.0),
            process_data.get('humidity_percent', 50.0),
        ], dtype=np.float32)

        # Normalize if we have training stats
        if self._feature_means is not None:
            features_norm = (features - self._feature_means) / self._feature_stds
        else:
            features_norm = features

        # Predict each dimension
        predictions = {}
        confidences = {}

        for dim in self.DIMENSIONS:
            model = self._models.get(dim)
            if model:
                pred, conf = model.predict(features_norm)
                predictions[dim] = pred
                confidences[dim] = conf

        # Check tolerances
        out_of_spec = []
        within_spec = True

        tolerances = {
            'stud_diameter': (4.78, 4.82),
            'stud_height': (1.78, 1.82),
            'height': (9.58, 9.62),
            'width': (7.78, 7.82),
            'clutch_power': (1.0, 3.0),
        }

        for dim, (low, high) in tolerances.items():
            if dim in predictions:
                if not (low <= predictions[dim] <= high):
                    out_of_spec.append(dim)
                    within_spec = False

        # Determine tolerance class
        avg_confidence = np.mean(list(confidences.values()))
        if avg_confidence > 0.95:
            tolerance_class = "TIGHT"
        elif avg_confidence > 0.85:
            tolerance_class = "STANDARD"
        else:
            tolerance_class = "LOOSE"

        return PredictedDimensions(
            part_id=part_id,
            prediction_timestamp=datetime.utcnow(),
            stud_diameter=predictions.get('stud_diameter', 4.8),
            stud_diameter_confidence=confidences.get('stud_diameter', 0.70),
            stud_height=predictions.get('stud_height', 1.8),
            stud_height_confidence=confidences.get('stud_height', 0.70),
            height_mm=predictions.get('height', 9.6),
            height_confidence=confidences.get('height', 0.70),
            width_mm=predictions.get('width', 7.8),
            width_confidence=confidences.get('width', 0.70),
            wall_thickness=predictions.get('wall_thickness', 1.6),
            wall_thickness_confidence=confidences.get('wall_thickness', 0.70),
            predicted_clutch_power_n=predictions.get('clutch_power', 2.0),
            clutch_power_confidence=confidences.get('clutch_power', 0.70),
            tolerance_class=tolerance_class,
            within_spec=within_spec,
            out_of_spec_dimensions=out_of_spec,
        )

    def calibrate_model(
        self,
        dimension: str,
        actual_measurement: float,
        predicted_value: float
    ) -> None:
        """
        Calibrate model based on actual vs predicted.

        Updates calibration offset to improve accuracy.
        """
        if dimension not in self._models:
            return

        model = self._models[dimension]
        error = actual_measurement - predicted_value

        # Exponential moving average of calibration offset
        alpha = 0.1
        model.calibration_offset = alpha * error + (1 - alpha) * model.calibration_offset
        model.last_calibration = datetime.utcnow()

        logger.debug(f"Calibrated {dimension}. Offset: {model.calibration_offset:.4f}")

    def get_model_status(self) -> Dict[str, Any]:
        """Get status of all models."""
        return {
            dim: {
                'trained': model.training_samples > 0,
                'samples': model.training_samples,
                'r2': model.training_r2,
                'mae': model.validation_mae,
                'last_calibration': model.last_calibration.isoformat() if model.last_calibration else None,
                'calibration_offset': model.calibration_offset,
            }
            for dim, model in self._models.items()
        }

    def should_verify(self, predictions: PredictedDimensions) -> bool:
        """
        Determine if physical measurement is needed.

        Returns True if confidence is low or dimensions are borderline.
        """
        # Always verify if out of spec
        if not predictions.within_spec:
            return True

        # Verify if any confidence is low
        confidences = [
            predictions.stud_diameter_confidence,
            predictions.height_confidence,
            predictions.clutch_power_confidence,
        ]
        if min(confidences) < 0.80:
            return True

        # Verify if clutch power is borderline
        if not (1.5 <= predictions.predicted_clutch_power_n <= 2.5):
            return True

        return False

    def get_sampling_plan(
        self,
        batch_size: int,
        predictions: List[PredictedDimensions]
    ) -> List[int]:
        """
        Determine which parts to physically inspect.

        Returns indices of parts that should be measured.
        """
        # Always inspect first and last
        to_inspect = {0, batch_size - 1}

        # Add any that failed should_verify
        for i, pred in enumerate(predictions[:batch_size]):
            if self.should_verify(pred):
                to_inspect.add(i)

        # Add random sample for model improvement (10%)
        sample_count = max(1, batch_size // 10)
        available = set(range(batch_size)) - to_inspect
        if available:
            import random
            random_sample = random.sample(list(available), min(sample_count, len(available)))
            to_inspect.update(random_sample)

        return sorted(to_inspect)


class VirtualMetrologyIntegration:
    """
    Integration layer for virtual metrology with production.

    Connects to process data streams and quality inspection.
    """

    def __init__(
        self,
        metrology: VirtualMetrology,
        inspection_service: Optional[Any] = None,
    ):
        self.metrology = metrology
        self.inspection_service = inspection_service

        self._pending_verifications: Dict[str, PredictedDimensions] = {}

    async def on_print_complete(
        self,
        part_id: str,
        process_data: Dict[str, float]
    ) -> Dict[str, Any]:
        """
        Handle print completion event.

        Predicts dimensions and determines if inspection needed.
        """
        # Predict dimensions
        predictions = self.metrology.predict_dimensions(process_data, part_id)

        # Determine if verification needed
        needs_verification = self.metrology.should_verify(predictions)

        result = {
            'part_id': part_id,
            'predictions': {
                'stud_diameter': predictions.stud_diameter,
                'height': predictions.height_mm,
                'clutch_power': predictions.predicted_clutch_power_n,
            },
            'within_spec': predictions.within_spec,
            'needs_verification': needs_verification,
            'tolerance_class': predictions.tolerance_class,
        }

        if needs_verification:
            self._pending_verifications[part_id] = predictions
            result['verification_reason'] = (
                'out_of_spec' if not predictions.within_spec
                else 'low_confidence'
            )

        return result

    async def on_inspection_complete(
        self,
        part_id: str,
        measurements: Dict[str, float]
    ) -> None:
        """
        Handle inspection completion.

        Uses actual measurements to calibrate models.
        """
        if part_id in self._pending_verifications:
            predictions = self._pending_verifications.pop(part_id)

            # Calibrate models
            if 'stud_diameter' in measurements:
                self.metrology.calibrate_model(
                    'stud_diameter',
                    measurements['stud_diameter'],
                    predictions.stud_diameter
                )

            if 'height' in measurements:
                self.metrology.calibrate_model(
                    'height',
                    measurements['height'],
                    predictions.height_mm
                )

            if 'clutch_power' in measurements:
                self.metrology.calibrate_model(
                    'clutch_power',
                    measurements['clutch_power'],
                    predictions.predicted_clutch_power_n
                )
