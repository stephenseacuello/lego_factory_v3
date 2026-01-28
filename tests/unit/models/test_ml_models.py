"""
LEGO Factory v3 - ML Models Unit Tests
======================================
"""

import pytest
from datetime import datetime


class TestMLModelModel:
    """Tests for MLModel model."""

    def test_create_ml_model(self, db_session, sample_ml_model_data):
        """Test creating an ML model."""
        from models.ml.ml_models import MLModel

        model = MLModel(**sample_ml_model_data)
        db_session.add(model)
        db_session.flush()

        assert model.id is not None
        assert model.model_id == 'test-model-001'
        assert model.model_version == '1.0.0'

    def test_ml_model_to_dict(self, db_session, sample_ml_model_data):
        """Test ML model serialization."""
        from models.ml.ml_models import MLModel

        model = MLModel(**sample_ml_model_data)
        db_session.add(model)
        db_session.flush()

        data = model.to_dict()

        assert 'model_id' in data
        assert 'model_type' in data
        assert 'status' in data


class TestTrainingRunModel:
    """Tests for TrainingRun model."""

    def test_create_training_run(self, db_session, sample_ml_model_data):
        """Test creating a training run."""
        from models.ml.ml_models import MLModel, TrainingRun, TrainingStatus

        model = MLModel(**sample_ml_model_data)
        db_session.add(model)
        db_session.flush()

        run = TrainingRun(
            run_id='RUN-TEST-001',
            model_id=model.id,
            status=TrainingStatus.QUEUED,
            hyperparameters={'learning_rate': 0.001},
            total_epochs=100,
        )
        db_session.add(run)
        db_session.flush()

        assert run.id is not None
        assert run.run_id == 'RUN-TEST-001'
        assert run.status == TrainingStatus.QUEUED


class TestInferenceJobModel:
    """Tests for InferenceJob model."""

    def test_create_inference_job(self, db_session, sample_ml_model_data):
        """Test creating an inference job."""
        from models.ml.ml_models import MLModel, InferenceJob, InferenceStatus

        model = MLModel(**sample_ml_model_data)
        db_session.add(model)
        db_session.flush()

        job = InferenceJob(
            job_id='INF-TEST-001',
            model_id=model.id,
            status=InferenceStatus.PENDING,
            input_type='sensor_data',
            input_data={'temperature': 200, 'vibration': 0.1},
            machine_id='test_machine',
        )
        db_session.add(job)
        db_session.flush()

        assert job.id is not None
        assert job.job_id == 'INF-TEST-001'


class TestPredictionModel:
    """Tests for Prediction model."""

    def test_create_prediction(self, db_session):
        """Test creating a prediction record."""
        from models.ml.ml_models import Prediction, AnomalyType

        prediction = Prediction(
            model_id='test-model',
            machine_id='test_machine',
            timestamp=datetime.now(),
            prediction_type='anomaly',
            predicted_value=0.85,
            confidence=0.92,
            is_anomaly=True,
            anomaly_type=AnomalyType.VIBRATION,
            anomaly_score=0.85,
        )
        db_session.add(prediction)
        db_session.flush()

        assert prediction.id is not None
        assert prediction.is_anomaly is True
        assert prediction.anomaly_type == AnomalyType.VIBRATION


class TestGCodeFingerprintModel:
    """Tests for GCodeFingerprint model."""

    def test_create_gcode_fingerprint(self, db_session):
        """Test creating a G-code fingerprint."""
        from models.ml.ml_models import GCodeFingerprint

        fingerprint = GCodeFingerprint(
            fingerprint_id='FP-TEST-001',
            gcode_file='test.gcode',
            gcode_hash='abc123',
            gcode_lines=1000,
            token_count=5000,
            unique_tokens=200,
            embedding_dim=256,
            embedding=[0.1] * 256,
            machine_id='test_machine',
            machine_confidence=0.95,
        )
        db_session.add(fingerprint)
        db_session.flush()

        assert fingerprint.id is not None
        assert fingerprint.fingerprint_id == 'FP-TEST-001'
        assert fingerprint.machine_confidence == 0.95
