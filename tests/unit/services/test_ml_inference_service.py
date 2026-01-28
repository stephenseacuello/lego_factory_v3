"""
Unit tests for ML Inference Service.

Tests model loading, prediction, fingerprint encoding, and historian integration.
"""

import pytest
import numpy as np
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock
import torch

from services.ml.inference.inference_service import (
    InferenceConfig,
    ModelRegistry,
    InferenceService,
    HistorianMLBridge,
    model_registry,
    inference_service,
    load_model,
    predict,
    encode,
    export_training_data,
)


class TestInferenceConfig:
    """Tests for InferenceConfig dataclass."""

    def test_default_config(self):
        """Test default configuration values."""
        config = InferenceConfig()

        assert config.device == 'cpu'
        assert config.batch_size == 1
        assert config.sequence_length == 256
        assert config.anomaly_threshold == 0.7

    def test_custom_config(self):
        """Test custom configuration."""
        config = InferenceConfig(
            device='cuda',
            batch_size=32,
            anomaly_threshold=0.9
        )

        assert config.device == 'cuda'
        assert config.batch_size == 32
        assert config.anomaly_threshold == 0.9


class TestModelRegistry:
    """Tests for ModelRegistry singleton."""

    @pytest.fixture
    def registry(self):
        """Create a fresh registry for testing."""
        ModelRegistry._instance = None
        return ModelRegistry()

    def test_singleton_pattern(self):
        """Test that ModelRegistry is a singleton."""
        ModelRegistry._instance = None
        r1 = ModelRegistry()
        r2 = ModelRegistry()

        assert r1 is r2

    def test_register_model(self, registry):
        """Test registering a model."""
        mock_model = Mock()
        registry.register("test_model", mock_model, {"param": "value"})

        assert registry.get("test_model") is mock_model
        assert registry.get_config("test_model") == {"param": "value"}

    def test_get_nonexistent_model(self, registry):
        """Test getting a nonexistent model."""
        assert registry.get("nonexistent") is None

    def test_list_models(self, registry):
        """Test listing registered models."""
        mock_model1 = Mock()
        mock_model2 = Mock()

        registry.register("model_1", mock_model1)
        registry.register("model_2", mock_model2)

        models = registry.list_models()
        assert "model_1" in models
        assert "model_2" in models

    def test_unregister_model(self, registry):
        """Test unregistering a model."""
        mock_model = Mock()
        registry.register("test_model", mock_model)
        registry.unregister("test_model")

        assert registry.get("test_model") is None


class TestInferenceService:
    """Tests for InferenceService class."""

    @pytest.fixture
    def service(self):
        """Create an inference service for testing."""
        return InferenceService(InferenceConfig())

    def test_no_model_loaded(self, service):
        """Test prediction without model loaded."""
        sensor_data = np.random.randn(256, 10)

        with pytest.raises(RuntimeError, match="No model loaded"):
            service.predict(sensor_data)

    def test_prepare_input_2d(self, service):
        """Test preparing 2D input data."""
        sensor_data = np.random.randn(256, 10)

        with patch.object(service, '_model', Mock()):
            mods, lengths = service._prepare_input(sensor_data)

        assert mods[0].shape[0] == 1  # Batch size 1
        assert mods[0].shape[1] == 256  # Sequence length
        assert mods[0].shape[2] == 10  # Features

    def test_prepare_input_3d(self, service):
        """Test preparing 3D input data."""
        sensor_data = np.random.randn(4, 256, 10)

        with patch.object(service, '_model', Mock()):
            mods, lengths = service._prepare_input(sensor_data)

        assert mods[0].shape[0] == 4  # Batch size 4

    def test_compare_fingerprints_identical(self, service):
        """Test comparing identical fingerprints."""
        fp1 = np.array([1.0, 0.0, 0.0])
        fp2 = np.array([1.0, 0.0, 0.0])

        similarity = service.compare_fingerprints(fp1, fp2)
        assert similarity == pytest.approx(1.0, rel=1e-5)

    def test_compare_fingerprints_orthogonal(self, service):
        """Test comparing orthogonal fingerprints."""
        fp1 = np.array([1.0, 0.0, 0.0])
        fp2 = np.array([0.0, 1.0, 0.0])

        similarity = service.compare_fingerprints(fp1, fp2)
        assert similarity == pytest.approx(0.0, rel=1e-5)

    def test_compare_fingerprints_opposite(self, service):
        """Test comparing opposite fingerprints."""
        fp1 = np.array([1.0, 0.0, 0.0])
        fp2 = np.array([-1.0, 0.0, 0.0])

        similarity = service.compare_fingerprints(fp1, fp2)
        assert similarity == pytest.approx(-1.0, rel=1e-5)

    def test_get_stats(self, service):
        """Test getting inference statistics."""
        stats = service.get_stats()

        assert 'inference_count' in stats
        assert 'model_loaded' in stats
        assert 'device' in stats
        assert 'running' in stats

    def test_predict_with_mock_model(self, service):
        """Test prediction with mocked model."""
        # Create mock model outputs
        mock_outputs = {
            'fingerprint': torch.randn(1, 128),
            'cls': torch.randn(1, 10),
            'anom': torch.tensor([[0.3]])  # Below threshold
        }

        mock_model = Mock()
        mock_model.return_value = mock_outputs
        service._model = mock_model

        sensor_data = np.random.randn(256, 10)
        results = service.predict(sensor_data)

        assert 'fingerprint' in results
        assert 'classification' in results
        assert 'anomaly_score' in results
        assert 'timestamp' in results
        assert 'inference_id' in results

    def test_anomaly_detection_trigger(self, service):
        """Test that anomaly detection triggers alarm."""
        # Create mock model outputs with high anomaly score
        mock_outputs = {
            'fingerprint': torch.randn(1, 128),
            'cls': torch.randn(1, 10),
            'anom': torch.tensor([[0.9]])  # Above threshold
        }

        mock_model = Mock()
        mock_model.return_value = mock_outputs
        service._model = mock_model

        with patch.object(service, '_trigger_alarm') as mock_trigger:
            sensor_data = np.random.randn(256, 10)
            results = service.predict(sensor_data)

            mock_trigger.assert_called_once()
            assert results.get('anomaly_detected') is True


class TestHistorianMLBridge:
    """Tests for HistorianMLBridge class."""

    @pytest.fixture
    def bridge(self):
        """Create a bridge for testing."""
        return HistorianMLBridge()

    def test_export_empty_data(self, bridge, tmp_path):
        """Test exporting when no data found."""
        output_path = str(tmp_path / "export.npz")

        with patch.object(bridge.reader, 'get_raw') as mock_raw:
            import pandas as pd
            mock_raw.return_value = pd.DataFrame()

            result = bridge.export_training_data(
                ["tag_001"],
                datetime.utcnow() - timedelta(hours=1),
                datetime.utcnow(),
                output_path
            )

            assert result == output_path

    def test_batch_inference_empty(self, bridge):
        """Test batch inference with no data."""
        with patch.object(bridge.reader, 'get_raw') as mock_raw:
            import pandas as pd
            mock_raw.return_value = pd.DataFrame()

            results = bridge.batch_inference(
                ["tag_001"],
                datetime.utcnow() - timedelta(hours=1),
                datetime.utcnow()
            )

            assert results == []


class TestModuleFunctions:
    """Tests for module-level convenience functions."""

    def test_load_model_file_not_found(self):
        """Test load_model with nonexistent file."""
        with pytest.raises(Exception):
            load_model("/nonexistent/path.pt")

    def test_predict_no_model(self):
        """Test predict without model loaded."""
        # Reset service
        inference_service._model = None
        inference_service._encoder = None

        sensor_data = np.random.randn(256, 10)
        with pytest.raises(RuntimeError):
            predict(sensor_data)

    def test_encode_no_model(self):
        """Test encode without model loaded."""
        # Reset service
        inference_service._model = None
        inference_service._encoder = None

        sensor_data = np.random.randn(256, 10)
        with pytest.raises(RuntimeError):
            encode(sensor_data)


class TestFingerprinting:
    """Tests for sensor-to-gcode fingerprinting."""

    @pytest.fixture
    def service(self):
        return InferenceService(InferenceConfig())

    def test_fingerprint_similarity_same_data(self, service):
        """Test that same data produces similar fingerprints."""
        # With a real model, same input should give same fingerprint
        data = np.random.randn(256, 10)

        fp1 = data.flatten()[:128]  # Simulated fingerprint
        fp2 = data.flatten()[:128]  # Same data

        similarity = service.compare_fingerprints(fp1, fp2)
        assert similarity == pytest.approx(1.0, rel=1e-5)

    def test_fingerprint_threshold(self, service):
        """Test fingerprint similarity threshold."""
        config = InferenceConfig(fingerprint_similarity_threshold=0.85)
        service_with_threshold = InferenceService(config)

        fp1 = np.random.randn(128)
        fp2 = fp1 + np.random.randn(128) * 0.1  # Small perturbation

        similarity = service_with_threshold.compare_fingerprints(fp1, fp2)
        # With small perturbation, should still be above threshold
        assert similarity > 0.7


class TestAnomalyDetection:
    """Tests for anomaly detection functionality."""

    @pytest.fixture
    def service(self):
        return InferenceService(InferenceConfig(anomaly_threshold=0.8))

    def test_anomaly_threshold_config(self, service):
        """Test anomaly threshold is configurable."""
        assert service.config.anomaly_threshold == 0.8

    def test_trigger_alarm_called_on_anomaly(self, service):
        """Test that alarm is triggered when anomaly detected."""
        # Patch at the location where it's used, not where it's defined
        with patch('services.ml.inference.inference_service.alarm_processor') as mock_processor:
            results = {
                'anomaly_score': np.array([[0.95]]),
                'fingerprint': np.random.randn(1, 128),
            }

            service._trigger_alarm(results)
            # Should call process_value on alarm processor
            mock_processor.process_value.assert_called()
