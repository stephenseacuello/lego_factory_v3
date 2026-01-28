"""
Model Trainer for CNC Manufacturing Predictions.

Trains and evaluates ML models for:
- Cycle time prediction
- Tool wear prediction
- Quality forecasting
- Maintenance prediction
"""

import logging
from dataclasses import dataclass, field
from typing import Optional, Dict, List, Any, Tuple
from datetime import datetime
from pathlib import Path
import json

logger = logging.getLogger(__name__)


@dataclass
class TrainingConfig:
    """Configuration for model training."""
    # Data settings
    train_test_split: float = 0.2
    validation_split: float = 0.1
    shuffle: bool = True
    random_state: int = 42

    # Model settings
    model_type: str = "random_forest"  # random_forest, gradient_boost, neural_network
    hyperparameter_tuning: bool = True
    cv_folds: int = 5

    # Feature settings
    normalize_features: bool = True
    remove_outliers: bool = True
    outlier_std_threshold: float = 3.0

    # Training settings
    max_epochs: int = 100
    early_stopping_patience: int = 10
    batch_size: int = 32

    # Output settings
    save_path: str = "./models"
    model_name: str = ""


@dataclass
class ModelMetrics:
    """Model performance metrics."""
    # Regression metrics
    mae: float = 0.0  # Mean Absolute Error
    mse: float = 0.0  # Mean Squared Error
    rmse: float = 0.0  # Root Mean Squared Error
    r2: float = 0.0  # R-squared
    mape: float = 0.0  # Mean Absolute Percentage Error

    # Classification metrics (for quality/defect prediction)
    accuracy: float = 0.0
    precision: float = 0.0
    recall: float = 0.0
    f1: float = 0.0
    auc_roc: float = 0.0

    # Cross-validation scores
    cv_mean: float = 0.0
    cv_std: float = 0.0

    def to_dict(self) -> Dict[str, float]:
        """Convert to dictionary."""
        return {
            "regression": {
                "mae": self.mae,
                "mse": self.mse,
                "rmse": self.rmse,
                "r2": self.r2,
                "mape": self.mape,
            },
            "classification": {
                "accuracy": self.accuracy,
                "precision": self.precision,
                "recall": self.recall,
                "f1": self.f1,
                "auc_roc": self.auc_roc,
            },
            "cross_validation": {
                "mean": self.cv_mean,
                "std": self.cv_std,
            },
        }


@dataclass
class TrainingResult:
    """Result of model training."""
    success: bool
    model_type: str
    model_path: str
    metrics: ModelMetrics
    feature_importance: Dict[str, float]
    training_time_seconds: float
    samples_used: int

    # Metadata
    trained_at: datetime = field(default_factory=datetime.now)
    config: Optional[TrainingConfig] = None
    notes: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "success": self.success,
            "model_type": self.model_type,
            "model_path": self.model_path,
            "metrics": self.metrics.to_dict(),
            "feature_importance": self.feature_importance,
            "training_time_seconds": self.training_time_seconds,
            "samples_used": self.samples_used,
            "trained_at": self.trained_at.isoformat(),
            "notes": self.notes,
        }


class ModelTrainer:
    """
    Trains ML models for manufacturing predictions.

    Supports multiple model types and automatic hyperparameter tuning.
    """

    SUPPORTED_MODELS = [
        "random_forest",
        "gradient_boost",
        "xgboost",
        "linear_regression",
        "ridge",
        "lasso",
        "svr",
        "neural_network",
    ]

    def __init__(
        self,
        config: Optional[TrainingConfig] = None,
    ):
        """
        Initialize model trainer.

        Args:
            config: Training configuration
        """
        self.config = config or TrainingConfig()
        self._ensure_dependencies()

    def _ensure_dependencies(self):
        """Check for required dependencies."""
        self._has_sklearn = False
        self._has_xgboost = False
        self._has_tensorflow = False

        try:
            import sklearn
            self._has_sklearn = True
        except ImportError:
            logger.warning("scikit-learn not installed - training limited")

        try:
            import xgboost
            self._has_xgboost = True
        except ImportError:
            logger.debug("xgboost not installed")

        try:
            import tensorflow
            self._has_tensorflow = True
        except ImportError:
            logger.debug("tensorflow not installed")

    def train_cycle_time_model(
        self,
        training_data: List[Dict[str, Any]],
        feature_columns: List[str],
        target_column: str = "actual_cycle_time",
    ) -> TrainingResult:
        """
        Train a cycle time prediction model.

        Args:
            training_data: List of training samples
            feature_columns: Feature column names
            target_column: Target column name

        Returns:
            Training result
        """
        return self._train_regression_model(
            training_data,
            feature_columns,
            target_column,
            model_name="cycle_time",
        )

    def train_tool_wear_model(
        self,
        training_data: List[Dict[str, Any]],
        feature_columns: List[str],
        target_column: str = "wear_percentage",
    ) -> TrainingResult:
        """
        Train a tool wear prediction model.

        Args:
            training_data: List of training samples
            feature_columns: Feature column names
            target_column: Target column name

        Returns:
            Training result
        """
        return self._train_regression_model(
            training_data,
            feature_columns,
            target_column,
            model_name="tool_wear",
        )

    def train_quality_model(
        self,
        training_data: List[Dict[str, Any]],
        feature_columns: List[str],
        target_column: str = "quality_score",
        is_classification: bool = False,
    ) -> TrainingResult:
        """
        Train a quality prediction model.

        Args:
            training_data: List of training samples
            feature_columns: Feature column names
            target_column: Target column name
            is_classification: Whether to train classifier (defect/no defect)

        Returns:
            Training result
        """
        if is_classification:
            return self._train_classification_model(
                training_data,
                feature_columns,
                target_column,
                model_name="quality_classifier",
            )
        else:
            return self._train_regression_model(
                training_data,
                feature_columns,
                target_column,
                model_name="quality",
            )

    def train_maintenance_model(
        self,
        training_data: List[Dict[str, Any]],
        feature_columns: List[str],
        target_column: str = "days_to_failure",
    ) -> TrainingResult:
        """
        Train a maintenance prediction model.

        Args:
            training_data: List of training samples
            feature_columns: Feature column names
            target_column: Target column name

        Returns:
            Training result
        """
        return self._train_regression_model(
            training_data,
            feature_columns,
            target_column,
            model_name="maintenance",
        )

    def _train_regression_model(
        self,
        training_data: List[Dict[str, Any]],
        feature_columns: List[str],
        target_column: str,
        model_name: str,
    ) -> TrainingResult:
        """Train a regression model."""
        if not self._has_sklearn:
            return TrainingResult(
                success=False,
                model_type="none",
                model_path="",
                metrics=ModelMetrics(),
                feature_importance={},
                training_time_seconds=0,
                samples_used=0,
                notes=["scikit-learn not installed"],
            )

        import time
        start_time = time.time()

        try:
            import numpy as np
            from sklearn.model_selection import train_test_split, cross_val_score
            from sklearn.preprocessing import StandardScaler
            from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
            import joblib

            # Prepare data
            X, y = self._prepare_data(training_data, feature_columns, target_column)

            if len(X) < 10:
                return TrainingResult(
                    success=False,
                    model_type="none",
                    model_path="",
                    metrics=ModelMetrics(),
                    feature_importance={},
                    training_time_seconds=0,
                    samples_used=len(X),
                    notes=["Insufficient training data (need at least 10 samples)"],
                )

            # Remove outliers
            if self.config.remove_outliers:
                X, y = self._remove_outliers(X, y)

            # Split data
            X_train, X_test, y_train, y_test = train_test_split(
                X, y,
                test_size=self.config.train_test_split,
                random_state=self.config.random_state,
            )

            # Normalize features
            scaler = None
            if self.config.normalize_features:
                scaler = StandardScaler()
                X_train = scaler.fit_transform(X_train)
                X_test = scaler.transform(X_test)

            # Create model
            model = self._create_regression_model()

            # Train model
            model.fit(X_train, y_train)

            # Evaluate
            y_pred = model.predict(X_test)

            metrics = ModelMetrics(
                mae=mean_absolute_error(y_test, y_pred),
                mse=mean_squared_error(y_test, y_pred),
                rmse=np.sqrt(mean_squared_error(y_test, y_pred)),
                r2=r2_score(y_test, y_pred),
                mape=np.mean(np.abs((y_test - y_pred) / np.maximum(y_test, 1))) * 100,
            )

            # Cross-validation
            if self.config.cv_folds > 1:
                cv_scores = cross_val_score(
                    model, X_train, y_train,
                    cv=self.config.cv_folds,
                    scoring='neg_mean_absolute_error'
                )
                metrics.cv_mean = -cv_scores.mean()
                metrics.cv_std = cv_scores.std()

            # Feature importance
            feature_importance = self._get_feature_importance(
                model, feature_columns
            )

            # Save model
            model_path = self._save_model(model, scaler, model_name, feature_columns)

            training_time = time.time() - start_time

            return TrainingResult(
                success=True,
                model_type=self.config.model_type,
                model_path=model_path,
                metrics=metrics,
                feature_importance=feature_importance,
                training_time_seconds=training_time,
                samples_used=len(X),
                config=self.config,
                notes=[f"Model trained successfully with R² = {metrics.r2:.3f}"],
            )

        except Exception as e:
            logger.error(f"Training failed: {e}")
            return TrainingResult(
                success=False,
                model_type=self.config.model_type,
                model_path="",
                metrics=ModelMetrics(),
                feature_importance={},
                training_time_seconds=time.time() - start_time,
                samples_used=len(training_data),
                notes=[f"Training failed: {str(e)}"],
            )

    def _train_classification_model(
        self,
        training_data: List[Dict[str, Any]],
        feature_columns: List[str],
        target_column: str,
        model_name: str,
    ) -> TrainingResult:
        """Train a classification model."""
        if not self._has_sklearn:
            return TrainingResult(
                success=False,
                model_type="none",
                model_path="",
                metrics=ModelMetrics(),
                feature_importance={},
                training_time_seconds=0,
                samples_used=0,
                notes=["scikit-learn not installed"],
            )

        import time
        start_time = time.time()

        try:
            import numpy as np
            from sklearn.model_selection import train_test_split, cross_val_score
            from sklearn.preprocessing import StandardScaler
            from sklearn.metrics import (
                accuracy_score, precision_score, recall_score,
                f1_score, roc_auc_score
            )
            import joblib

            # Prepare data
            X, y = self._prepare_data(training_data, feature_columns, target_column)

            # Convert to binary if needed
            if y.dtype != bool:
                y = (y > y.median()).astype(int)

            if len(X) < 10:
                return TrainingResult(
                    success=False,
                    model_type="none",
                    model_path="",
                    metrics=ModelMetrics(),
                    feature_importance={},
                    training_time_seconds=0,
                    samples_used=len(X),
                    notes=["Insufficient training data"],
                )

            # Split data
            X_train, X_test, y_train, y_test = train_test_split(
                X, y,
                test_size=self.config.train_test_split,
                random_state=self.config.random_state,
                stratify=y,
            )

            # Normalize features
            scaler = None
            if self.config.normalize_features:
                scaler = StandardScaler()
                X_train = scaler.fit_transform(X_train)
                X_test = scaler.transform(X_test)

            # Create model
            model = self._create_classification_model()

            # Train model
            model.fit(X_train, y_train)

            # Evaluate
            y_pred = model.predict(X_test)
            y_prob = model.predict_proba(X_test)[:, 1] if hasattr(model, 'predict_proba') else y_pred

            metrics = ModelMetrics(
                accuracy=accuracy_score(y_test, y_pred),
                precision=precision_score(y_test, y_pred, zero_division=0),
                recall=recall_score(y_test, y_pred, zero_division=0),
                f1=f1_score(y_test, y_pred, zero_division=0),
                auc_roc=roc_auc_score(y_test, y_prob) if len(np.unique(y_test)) > 1 else 0,
            )

            # Cross-validation
            if self.config.cv_folds > 1:
                cv_scores = cross_val_score(
                    model, X_train, y_train,
                    cv=self.config.cv_folds,
                    scoring='accuracy'
                )
                metrics.cv_mean = cv_scores.mean()
                metrics.cv_std = cv_scores.std()

            # Feature importance
            feature_importance = self._get_feature_importance(
                model, feature_columns
            )

            # Save model
            model_path = self._save_model(model, scaler, model_name, feature_columns)

            training_time = time.time() - start_time

            return TrainingResult(
                success=True,
                model_type=self.config.model_type,
                model_path=model_path,
                metrics=metrics,
                feature_importance=feature_importance,
                training_time_seconds=training_time,
                samples_used=len(X),
                config=self.config,
                notes=[f"Model trained successfully with accuracy = {metrics.accuracy:.3f}"],
            )

        except Exception as e:
            logger.error(f"Training failed: {e}")
            return TrainingResult(
                success=False,
                model_type=self.config.model_type,
                model_path="",
                metrics=ModelMetrics(),
                feature_importance={},
                training_time_seconds=time.time() - start_time,
                samples_used=len(training_data),
                notes=[f"Training failed: {str(e)}"],
            )

    def _prepare_data(
        self,
        training_data: List[Dict[str, Any]],
        feature_columns: List[str],
        target_column: str,
    ) -> Tuple[Any, Any]:
        """Prepare data for training."""
        import numpy as np

        X = []
        y = []

        for sample in training_data:
            try:
                features = [float(sample.get(col, 0)) for col in feature_columns]
                target = float(sample.get(target_column, 0))
                X.append(features)
                y.append(target)
            except (ValueError, TypeError):
                continue

        return np.array(X), np.array(y)

    def _remove_outliers(
        self,
        X: Any,
        y: Any,
    ) -> Tuple[Any, Any]:
        """Remove outliers from data."""
        import numpy as np

        # Remove based on target variable
        mean = np.mean(y)
        std = np.std(y)
        threshold = self.config.outlier_std_threshold

        mask = np.abs(y - mean) <= threshold * std

        return X[mask], y[mask]

    def _create_regression_model(self) -> Any:
        """Create regression model based on config."""
        from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
        from sklearn.linear_model import LinearRegression, Ridge, Lasso
        from sklearn.svm import SVR

        model_type = self.config.model_type

        if model_type == "random_forest":
            return RandomForestRegressor(
                n_estimators=100,
                max_depth=10,
                random_state=self.config.random_state,
                n_jobs=-1,
            )
        elif model_type == "gradient_boost":
            return GradientBoostingRegressor(
                n_estimators=100,
                max_depth=5,
                random_state=self.config.random_state,
            )
        elif model_type == "xgboost" and self._has_xgboost:
            import xgboost as xgb
            return xgb.XGBRegressor(
                n_estimators=100,
                max_depth=6,
                random_state=self.config.random_state,
            )
        elif model_type == "linear_regression":
            return LinearRegression()
        elif model_type == "ridge":
            return Ridge(alpha=1.0)
        elif model_type == "lasso":
            return Lasso(alpha=0.1)
        elif model_type == "svr":
            return SVR(kernel='rbf', C=1.0)
        else:
            # Default to random forest
            return RandomForestRegressor(
                n_estimators=100,
                random_state=self.config.random_state,
            )

    def _create_classification_model(self) -> Any:
        """Create classification model based on config."""
        from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
        from sklearn.linear_model import LogisticRegression
        from sklearn.svm import SVC

        model_type = self.config.model_type

        if model_type == "random_forest":
            return RandomForestClassifier(
                n_estimators=100,
                max_depth=10,
                random_state=self.config.random_state,
                n_jobs=-1,
            )
        elif model_type == "gradient_boost":
            return GradientBoostingClassifier(
                n_estimators=100,
                max_depth=5,
                random_state=self.config.random_state,
            )
        elif model_type == "xgboost" and self._has_xgboost:
            import xgboost as xgb
            return xgb.XGBClassifier(
                n_estimators=100,
                max_depth=6,
                random_state=self.config.random_state,
            )
        else:
            return RandomForestClassifier(
                n_estimators=100,
                random_state=self.config.random_state,
            )

    def _get_feature_importance(
        self,
        model: Any,
        feature_names: List[str],
    ) -> Dict[str, float]:
        """Get feature importance from trained model."""
        importance = {}

        if hasattr(model, 'feature_importances_'):
            for name, imp in zip(feature_names, model.feature_importances_):
                importance[name] = float(imp)
        elif hasattr(model, 'coef_'):
            import numpy as np
            coef = np.abs(model.coef_)
            if coef.ndim > 1:
                coef = coef.mean(axis=0)
            for name, imp in zip(feature_names, coef):
                importance[name] = float(imp)

        # Sort by importance
        importance = dict(sorted(
            importance.items(),
            key=lambda x: x[1],
            reverse=True
        ))

        return importance

    def _save_model(
        self,
        model: Any,
        scaler: Any,
        model_name: str,
        feature_names: List[str],
    ) -> str:
        """Save trained model to disk."""
        import joblib

        # Create save directory
        save_path = Path(self.config.save_path)
        save_path.mkdir(parents=True, exist_ok=True)

        # Generate filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        model_filename = f"{model_name}_{timestamp}.pkl"
        model_path = save_path / model_filename

        # Save model
        joblib.dump(model, model_path)

        # Save scaler if exists
        if scaler is not None:
            scaler_path = save_path / f"{model_name}_{timestamp}_scaler.pkl"
            joblib.dump(scaler, scaler_path)

        # Save metadata
        metadata = {
            "model_name": model_name,
            "model_type": self.config.model_type,
            "feature_names": feature_names,
            "trained_at": datetime.now().isoformat(),
            "config": {
                "train_test_split": self.config.train_test_split,
                "normalize_features": self.config.normalize_features,
                "cv_folds": self.config.cv_folds,
            },
        }
        metadata_path = save_path / f"{model_name}_{timestamp}_metadata.json"
        with open(metadata_path, 'w') as f:
            json.dump(metadata, f, indent=2)

        logger.info(f"Model saved to {model_path}")

        return str(model_path)

    def load_model(
        self,
        model_path: str,
    ) -> Tuple[Any, Any, Dict[str, Any]]:
        """
        Load a trained model from disk.

        Returns:
            Tuple of (model, scaler, metadata)
        """
        import joblib

        model_path = Path(model_path)

        # Load model
        model = joblib.load(model_path)

        # Try to load scaler
        scaler_path = model_path.with_name(
            model_path.stem.replace('.pkl', '_scaler.pkl')
        )
        scaler = None
        if scaler_path.exists():
            scaler = joblib.load(scaler_path)

        # Try to load metadata
        metadata_path = model_path.with_name(
            model_path.stem.replace('.pkl', '_metadata.json')
        )
        metadata = {}
        if metadata_path.exists():
            with open(metadata_path) as f:
                metadata = json.load(f)

        return model, scaler, metadata

    def get_available_models(self) -> List[Dict[str, Any]]:
        """List available trained models."""
        save_path = Path(self.config.save_path)
        if not save_path.exists():
            return []

        models = []
        for model_file in save_path.glob("*.pkl"):
            if "_scaler" in model_file.name:
                continue

            metadata_file = model_file.with_name(
                model_file.stem + "_metadata.json"
            )
            if metadata_file.exists():
                with open(metadata_file) as f:
                    metadata = json.load(f)
                models.append({
                    "path": str(model_file),
                    "name": metadata.get("model_name", model_file.stem),
                    "type": metadata.get("model_type", "unknown"),
                    "trained_at": metadata.get("trained_at", "unknown"),
                })
            else:
                models.append({
                    "path": str(model_file),
                    "name": model_file.stem,
                    "type": "unknown",
                })

        return models
