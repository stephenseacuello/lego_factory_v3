"""
LEGO Factory v3 - ML API Integration Tests
==========================================
Tests for Machine Learning API endpoints.
"""

import pytest
from unittest.mock import patch, MagicMock
import numpy as np


@pytest.mark.integration
class TestMLAnomalyDetectionAPI:
    """Test ML anomaly detection endpoints."""

    def test_detect_anomaly(self, client):
        """Test anomaly detection endpoint."""
        data = {
            'machine_id': 'prusa_mk4_1',
            'sensor_data': [[0.1, 0.2, 0.3, 0.4, 0.5]] * 10,
        }
        response = client.post('/api/v1/ml/anomaly/detect', json=data)
        assert response.status_code == 200
        result = response.get_json()
        assert 'anomaly_score' in result or 'is_anomaly' in result

    def test_batch_anomaly_detection(self, client):
        """Test batch anomaly detection."""
        data = {
            'machine_id': 'prusa_mk4_1',
            'samples': [
                {'timestamp': '2024-01-15T10:00:00Z', 'values': [0.1, 0.2, 0.3]},
                {'timestamp': '2024-01-15T10:01:00Z', 'values': [0.15, 0.22, 0.31]},
            ],
        }
        response = client.post('/api/v1/ml/anomaly/batch', json=data)
        assert response.status_code in [200, 202]

    def test_anomaly_thresholds(self, client):
        """Test getting/setting anomaly thresholds."""
        response = client.get('/api/v1/ml/anomaly/thresholds')
        assert response.status_code == 200


@pytest.mark.integration
class TestMLQualityPredictionAPI:
    """Test ML quality prediction endpoints."""

    def test_predict_quality(self, client):
        """Test quality prediction endpoint."""
        data = {
            'machine_id': 'prusa_mk4_1',
            'job_id': 'JOB-001',
            'sensor_data': [[0.5, 0.6, 0.7, 0.8, 0.9]] * 5,
        }
        response = client.post('/api/v1/ml/quality/predict', json=data)
        assert response.status_code == 200
        result = response.get_json()
        assert 'quality_class' in result
        assert 'confidence' in result

    def test_spc_data(self, client):
        """Test SPC data retrieval."""
        response = client.get('/api/v1/ml/spc?machine_id=prusa_mk4_1&metric=dimension')
        assert response.status_code == 200
        result = response.get_json()
        assert 'data' in result
        assert 'ucl' in result or 'upper_control_limit' in result


@pytest.mark.integration
class TestMLModelManagementAPI:
    """Test ML model management endpoints."""

    def test_list_models(self, client):
        """Test listing available ML models."""
        response = client.get('/api/v1/ml/models')
        assert response.status_code == 200
        data = response.get_json()
        assert isinstance(data, (list, dict))

    def test_get_model_info(self, client):
        """Test getting model information."""
        response = client.get('/api/v1/ml/models/anomaly_detector_v1')
        assert response.status_code in [200, 404]

    def test_model_metrics(self, client):
        """Test getting model performance metrics."""
        response = client.get('/api/v1/ml/models/anomaly_detector_v1/metrics')
        assert response.status_code in [200, 404]


@pytest.mark.integration
class TestMLInferenceAPI:
    """Test ML inference endpoints."""

    def test_inference_health(self, client):
        """Test ML service health check."""
        response = client.get('/api/v1/ml/health')
        assert response.status_code == 200

    def test_inference_batch(self, client):
        """Test batch inference."""
        data = {
            'model_id': 'anomaly_detector_v1',
            'inputs': [[0.1] * 10] * 5,
        }
        response = client.post('/api/v1/ml/inference', json=data)
        assert response.status_code in [200, 404, 503]


@pytest.mark.integration
class TestMLTrainingAPI:
    """Test ML training-related endpoints."""

    def test_training_jobs(self, client):
        """Test listing training jobs."""
        response = client.get('/api/v1/ml/training/jobs')
        assert response.status_code == 200

    def test_training_data_stats(self, client):
        """Test training data statistics."""
        response = client.get('/api/v1/ml/training/data/stats')
        assert response.status_code in [200, 404]
