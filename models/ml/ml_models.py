"""
LEGO Factory v3 - ML Models
===========================
Models for ML inference, training, and fingerprinting.
"""

from datetime import datetime
from typing import Optional, Dict, Any, List
from enum import Enum

from sqlalchemy import (
    Column, String, Integer, Float, DateTime, Boolean, Text,
    ForeignKey, Enum as SQLEnum, JSON, Index, LargeBinary
)
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID, ARRAY

from models.base import BaseModel, AuditedModel, VersionedModel


class ModelType(str, Enum):
    """Types of ML models."""
    MM_DTAE_LSTM = 'mm_dtae_lstm'  # Multimodal Deep Transformer Autoencoder + LSTM
    ANOMALY_DETECTOR = 'anomaly_detector'
    TOOL_WEAR_PREDICTOR = 'tool_wear_predictor'
    QUALITY_CLASSIFIER = 'quality_classifier'
    FINGERPRINT_MATCHER = 'fingerprint_matcher'
    CUSTOM = 'custom'


class ModelStatus(str, Enum):
    """Model deployment status."""
    DRAFT = 'draft'
    TRAINING = 'training'
    VALIDATING = 'validating'
    READY = 'ready'
    DEPLOYED = 'deployed'
    DEPRECATED = 'deprecated'
    ARCHIVED = 'archived'


class InferenceStatus(str, Enum):
    """Inference job status."""
    PENDING = 'pending'
    RUNNING = 'running'
    COMPLETED = 'completed'
    FAILED = 'failed'
    TIMEOUT = 'timeout'


class TrainingStatus(str, Enum):
    """Training job status."""
    QUEUED = 'queued'
    PREPARING = 'preparing'
    TRAINING = 'training'
    VALIDATING = 'validating'
    COMPLETED = 'completed'
    FAILED = 'failed'
    CANCELLED = 'cancelled'


class AnomalyType(str, Enum):
    """Types of detected anomalies."""
    NORMAL = 'normal'
    VIBRATION = 'vibration'
    TEMPERATURE = 'temperature'
    CURRENT = 'current'
    TOOL_WEAR = 'tool_wear'
    MATERIAL_DEFECT = 'material_defect'
    MOTION_ERROR = 'motion_error'
    UNKNOWN = 'unknown'


class MLModel(VersionedModel):
    """
    ML model definition and versioning.

    Tracks model versions, parameters, and deployment status.
    """
    __tablename__ = 'ml_models'

    # Identification
    model_id = Column(String(50), unique=True, nullable=False, index=True)
    name = Column(String(200), nullable=False)
    description = Column(Text)

    # Model type and architecture
    model_type = Column(SQLEnum(ModelType), nullable=False)
    architecture = Column(JSON)  # Model architecture config

    # Version info
    model_version = Column(String(50), nullable=False)
    parent_model_id = Column(String(50))  # For transfer learning

    # Status (index in __table_args__)
    status = Column(SQLEnum(ModelStatus), default=ModelStatus.DRAFT)

    # Training configuration
    hyperparameters = Column(JSON, default=dict)
    training_config = Column(JSON, default=dict)

    # Model weights (stored separately or path)
    weights_path = Column(String(500))
    weights_hash = Column(String(64))  # SHA-256 hash

    # Input/output specs
    input_shape = Column(JSON)  # e.g., [batch, seq_len, features]
    output_shape = Column(JSON)
    input_features = Column(JSON)  # List of feature names
    output_labels = Column(JSON)  # Output label names

    # Performance metrics
    metrics = Column(JSON, default=dict)  # accuracy, loss, etc.
    validation_metrics = Column(JSON, default=dict)
    test_metrics = Column(JSON, default=dict)

    # Dataset info
    training_samples = Column(Integer)
    validation_samples = Column(Integer)
    test_samples = Column(Integer)
    dataset_version = Column(String(50))

    # Deployment info
    deployed_at = Column(DateTime)
    inference_count = Column(Integer, default=0)
    avg_inference_ms = Column(Float)

    # Resource requirements
    requires_gpu = Column(Boolean, default=True)
    min_memory_mb = Column(Integer)
    model_size_mb = Column(Float)

    # Relationships
    training_runs = relationship('TrainingRun', back_populates='model')
    inference_jobs = relationship('InferenceJob', back_populates='model')

    __table_args__ = (
        Index('ix_ml_models_type', 'model_type'),
        Index('ix_ml_models_status', 'status'),
        Index('ix_ml_models_version', 'model_id', 'model_version'),
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': str(self.id),
            'model_id': self.model_id,
            'name': self.name,
            'description': self.description,
            'model_type': self.model_type.value if self.model_type else None,
            'model_version': self.model_version,
            'status': self.status.value if self.status else None,
            'metrics': self.metrics,
            'inference_count': self.inference_count,
            'avg_inference_ms': self.avg_inference_ms,
            'deployed_at': self.deployed_at.isoformat() if self.deployed_at else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


class TrainingRun(AuditedModel):
    """
    Training run record.

    Tracks a single training session including epochs, metrics, and artifacts.
    """
    __tablename__ = 'ml_training_runs'

    # Identification
    run_id = Column(String(50), unique=True, nullable=False, index=True)

    # Model reference
    model_id = Column(UUID(as_uuid=True), ForeignKey('ml_models.id'), nullable=False)

    # Status
    status = Column(SQLEnum(TrainingStatus), default=TrainingStatus.QUEUED)
    progress = Column(Float, default=0)  # 0-100

    # Configuration
    hyperparameters = Column(JSON, default=dict)
    training_config = Column(JSON, default=dict)

    # Dataset
    dataset_path = Column(String(500))
    dataset_version = Column(String(50))
    train_samples = Column(Integer)
    val_samples = Column(Integer)

    # Training progress
    current_epoch = Column(Integer, default=0)
    total_epochs = Column(Integer)
    current_step = Column(Integer, default=0)
    total_steps = Column(Integer)

    # Timing
    started_at = Column(DateTime)
    completed_at = Column(DateTime)
    training_time_seconds = Column(Float)

    # Metrics history (per epoch)
    train_loss_history = Column(JSON, default=list)
    val_loss_history = Column(JSON, default=list)
    metrics_history = Column(JSON, default=list)

    # Final metrics
    final_train_loss = Column(Float)
    final_val_loss = Column(Float)
    final_metrics = Column(JSON, default=dict)
    best_epoch = Column(Integer)
    best_metrics = Column(JSON, default=dict)

    # Output
    checkpoint_path = Column(String(500))
    tensorboard_path = Column(String(500))
    logs_path = Column(String(500))

    # Error info
    error_message = Column(Text)
    error_traceback = Column(Text)

    # Hardware
    gpu_used = Column(String(100))
    gpu_memory_mb = Column(Integer)

    # Relationships
    model = relationship('MLModel', back_populates='training_runs')

    __table_args__ = (
        Index('ix_training_runs_status', 'status'),
        Index('ix_training_runs_model', 'model_id'),
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': str(self.id),
            'run_id': self.run_id,
            'model_id': str(self.model_id),
            'status': self.status.value if self.status else None,
            'progress': self.progress,
            'current_epoch': self.current_epoch,
            'total_epochs': self.total_epochs,
            'final_train_loss': self.final_train_loss,
            'final_val_loss': self.final_val_loss,
            'best_epoch': self.best_epoch,
            'training_time_seconds': self.training_time_seconds,
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
        }


class InferenceJob(BaseModel):
    """
    Inference job record.

    Tracks individual inference requests and results.
    """
    __tablename__ = 'ml_inference_jobs'

    # Identification
    job_id = Column(String(50), unique=True, nullable=False, index=True)

    # Model reference
    model_id = Column(UUID(as_uuid=True), ForeignKey('ml_models.id'), nullable=False)

    # Status
    status = Column(SQLEnum(InferenceStatus), default=InferenceStatus.PENDING)

    # Input
    input_type = Column(String(50))  # 'gcode', 'sensor_data', 'image', etc.
    input_data = Column(JSON)  # Small inputs stored directly
    input_file = Column(String(500))  # Large inputs stored as file
    input_hash = Column(String(64))

    # Context
    machine_id = Column(String(50))
    job_reference = Column(String(100))  # Work order, job ID, etc.

    # Timing
    queued_at = Column(DateTime, default=datetime.utcnow)
    started_at = Column(DateTime)
    completed_at = Column(DateTime)
    inference_time_ms = Column(Float)

    # Output
    predictions = Column(JSON)  # Model output
    confidence = Column(Float)  # Overall confidence score
    raw_output = Column(JSON)  # Raw model output if needed

    # Interpretation
    predicted_class = Column(String(100))
    predicted_label = Column(String(200))
    top_predictions = Column(JSON)  # Top-K predictions with scores

    # Error info
    error_message = Column(Text)

    # Feedback (for model improvement)
    feedback_label = Column(String(200))  # Corrected label if wrong
    feedback_notes = Column(Text)
    feedback_at = Column(DateTime)
    feedback_by = Column(String(100))

    # Relationships
    model = relationship('MLModel', back_populates='inference_jobs')

    __table_args__ = (
        Index('ix_inference_jobs_status', 'status'),
        Index('ix_inference_jobs_model', 'model_id'),
        Index('ix_inference_jobs_machine', 'machine_id'),
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': str(self.id),
            'job_id': self.job_id,
            'model_id': str(self.model_id),
            'status': self.status.value if self.status else None,
            'input_type': self.input_type,
            'machine_id': self.machine_id,
            'inference_time_ms': self.inference_time_ms,
            'predicted_class': self.predicted_class,
            'predicted_label': self.predicted_label,
            'confidence': self.confidence,
            'top_predictions': self.top_predictions,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


class Prediction(BaseModel):
    """
    Time-series prediction record.

    Stores predictions with timestamps for historian-style querying.
    This table is converted to a TimescaleDB hypertable.
    """
    __tablename__ = 'ml_predictions'

    # Time (primary for hypertable)
    timestamp = Column(DateTime(timezone=True), nullable=False, index=True)

    # References
    model_id = Column(String(50), nullable=False, index=True)
    machine_id = Column(String(50), index=True)
    tag_id = Column(String(100), index=True)

    # Prediction type
    prediction_type = Column(String(50), nullable=False)  # anomaly, tool_wear, quality, etc.

    # Prediction output
    predicted_value = Column(Float)
    predicted_class = Column(String(100))
    confidence = Column(Float)
    probabilities = Column(JSON)  # Class probabilities

    # Anomaly detection specific
    anomaly_score = Column(Float)
    anomaly_type = Column(SQLEnum(AnomalyType))
    is_anomaly = Column(Boolean, default=False)
    threshold_used = Column(Float)

    # Context
    input_summary = Column(JSON)  # Summary of input features
    sensor_readings = Column(JSON)  # Associated sensor data

    # Alarm integration
    alarm_triggered = Column(Boolean, default=False)
    alarm_id = Column(String(50))

    __table_args__ = (
        Index('ix_predictions_time_machine', 'timestamp', 'machine_id'),
        Index('ix_predictions_anomaly', 'is_anomaly', 'timestamp'),
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': str(self.id),
            'timestamp': self.timestamp.isoformat() if self.timestamp else None,
            'model_id': self.model_id,
            'machine_id': self.machine_id,
            'prediction_type': self.prediction_type,
            'predicted_value': self.predicted_value,
            'predicted_class': self.predicted_class,
            'confidence': self.confidence,
            'is_anomaly': self.is_anomaly,
            'anomaly_type': self.anomaly_type.value if self.anomaly_type else None,
            'anomaly_score': self.anomaly_score,
        }


class GCodeFingerprint(BaseModel):
    """
    G-code fingerprint for machine identification.

    Stores the learned fingerprint from G-code analysis.
    """
    __tablename__ = 'gcode_fingerprints'

    # Identification
    fingerprint_id = Column(String(50), unique=True, nullable=False, index=True)

    # Source
    gcode_file = Column(String(500))
    gcode_hash = Column(String(64), index=True)
    gcode_lines = Column(Integer)

    # Token analysis
    token_count = Column(Integer)
    unique_tokens = Column(Integer)
    token_distribution = Column(JSON)  # Token frequency distribution

    # Embedding
    embedding_version = Column(String(50))
    embedding = Column(JSON)  # Latent space representation (list of floats)
    embedding_dim = Column(Integer)

    # Machine association
    machine_id = Column(String(50), index=True)
    machine_confidence = Column(Float)

    # Analysis results
    estimated_print_time = Column(Float)  # minutes
    estimated_movements = Column(Integer)
    axis_usage = Column(JSON)  # X, Y, Z, E usage stats
    feature_stats = Column(JSON)  # Various extracted features

    # Comparison
    similarity_scores = Column(JSON)  # Similarity to known fingerprints

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': str(self.id),
            'fingerprint_id': self.fingerprint_id,
            'gcode_file': self.gcode_file,
            'gcode_hash': self.gcode_hash,
            'token_count': self.token_count,
            'machine_id': self.machine_id,
            'machine_confidence': self.machine_confidence,
            'embedding_dim': self.embedding_dim,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


class ToolWearPrediction(BaseModel):
    """
    Tool wear prediction record.

    Stores tool wear analysis and remaining life predictions.
    """
    __tablename__ = 'tool_wear_predictions'

    # References
    machine_id = Column(String(50), nullable=False, index=True)
    tool_id = Column(String(50), nullable=False, index=True)

    # Timestamp
    timestamp = Column(DateTime(timezone=True), nullable=False, index=True)

    # Measurements
    current_wear_level = Column(Float)  # 0-100%
    wear_rate = Column(Float)  # % per hour
    vibration_level = Column(Float)
    temperature = Column(Float)
    current_draw = Column(Float)

    # Predictions
    remaining_life_hours = Column(Float)
    remaining_life_parts = Column(Integer)
    confidence = Column(Float)

    # Recommendation
    recommended_action = Column(String(100))
    urgency = Column(String(20))  # low, medium, high, critical

    # Model info
    model_id = Column(String(50))
    model_version = Column(String(50))

    __table_args__ = (
        Index('ix_tool_wear_machine_tool', 'machine_id', 'tool_id'),
        Index('ix_tool_wear_time', 'timestamp'),
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': str(self.id),
            'machine_id': self.machine_id,
            'tool_id': self.tool_id,
            'timestamp': self.timestamp.isoformat() if self.timestamp else None,
            'current_wear_level': self.current_wear_level,
            'remaining_life_hours': self.remaining_life_hours,
            'remaining_life_parts': self.remaining_life_parts,
            'confidence': self.confidence,
            'recommended_action': self.recommended_action,
            'urgency': self.urgency,
        }
