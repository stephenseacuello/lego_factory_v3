"""
LEGO Factory v3 - ML Inference Service
======================================
Real-time inference for sensor-to-gcode fingerprinting and anomaly detection.
"""

import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List, Tuple
from dataclasses import dataclass
from pathlib import Path
import threading
import asyncio

import torch
import numpy as np

from services.ml.model.mm_dtae_lstm import MM_DTAE_LSTM, ModelConfig, EnhancedEncoder
from services.scada.historian.historian_service import read_from_historian, HistorianReader
from services.scada.alarm_management.alarm_service import alarm_processor

logger = logging.getLogger(__name__)


@dataclass
class InferenceConfig:
    """Configuration for inference service."""
    model_path: Optional[str] = None
    device: str = 'cpu'
    batch_size: int = 1
    sequence_length: int = 256
    overlap: int = 64
    anomaly_threshold: float = 0.7
    fingerprint_similarity_threshold: float = 0.85


class ModelRegistry:
    """Registry for ML models."""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._models: Dict[str, torch.nn.Module] = {}
            cls._instance._configs: Dict[str, Any] = {}
            cls._instance._lock = threading.Lock()
        return cls._instance

    def register(self, name: str, model: torch.nn.Module, config: Any = None):
        """Register a model."""
        with self._lock:
            self._models[name] = model
            if config:
                self._configs[name] = config
            logger.info(f"Registered model: {name}")

    def get(self, name: str) -> Optional[torch.nn.Module]:
        """Get a registered model."""
        return self._models.get(name)

    def get_config(self, name: str) -> Optional[Any]:
        """Get model config."""
        return self._configs.get(name)

    def list_models(self) -> List[str]:
        """List all registered models."""
        return list(self._models.keys())

    def unregister(self, name: str):
        """Unregister a model."""
        with self._lock:
            self._models.pop(name, None)
            self._configs.pop(name, None)


model_registry = ModelRegistry()


class InferenceService:
    """Service for running ML inference on sensor data."""

    def __init__(self, config: InferenceConfig = None):
        self.config = config or InferenceConfig()
        self.device = torch.device(self.config.device)
        self._model: Optional[torch.nn.Module] = None
        self._encoder: Optional[EnhancedEncoder] = None
        self._running = False
        self._inference_count = 0

    def load_model(self, model_path: str, model_type: str = 'mm_dtae_lstm'):
        """Load a pretrained model."""
        try:
            checkpoint = torch.load(model_path, map_location=self.device)

            if model_type == 'mm_dtae_lstm':
                config_dict = checkpoint.get('config', {})
                model_config = ModelConfig(**config_dict)
                self._model = MM_DTAE_LSTM(model_config)
            elif model_type == 'enhanced_encoder':
                self._encoder = EnhancedEncoder(**checkpoint.get('config', {}))
                self._encoder.load_state_dict(checkpoint['model_state_dict'])
                self._encoder.to(self.device)
                self._encoder.eval()
                return

            self._model.load_state_dict(checkpoint['model_state_dict'])
            self._model.to(self.device)
            self._model.eval()

            model_registry.register(model_type, self._model, checkpoint.get('config'))
            logger.info(f"Loaded model from {model_path}")

        except Exception as e:
            logger.error(f"Error loading model: {e}")
            raise

    def _prepare_input(self, sensor_data: np.ndarray) -> Tuple[List[torch.Tensor], torch.Tensor]:
        """Prepare sensor data for model input."""
        if sensor_data.ndim == 2:
            sensor_data = sensor_data[np.newaxis, ...]

        B, T, D = sensor_data.shape

        tensor = torch.from_numpy(sensor_data).float().to(self.device)
        mods = [tensor]
        lengths = torch.tensor([T] * B, device=self.device)

        return mods, lengths

    @torch.no_grad()
    def predict(self, sensor_data: np.ndarray) -> Dict[str, Any]:
        """Run inference on sensor data."""
        if self._model is None:
            raise RuntimeError("No model loaded. Call load_model() first.")

        mods, lengths = self._prepare_input(sensor_data)

        outputs = self._model(mods, lengths)

        self._inference_count += 1

        results = {
            'fingerprint': outputs['fingerprint'].cpu().numpy(),
            'classification': torch.softmax(outputs['cls'], dim=-1).cpu().numpy(),
            'anomaly_score': torch.sigmoid(outputs['anom']).cpu().numpy(),
            'timestamp': datetime.utcnow().isoformat(),
            'inference_id': self._inference_count,
        }

        if outputs['anom'].sigmoid().item() > self.config.anomaly_threshold:
            results['anomaly_detected'] = True
            self._trigger_alarm(results)

        return results

    @torch.no_grad()
    def encode(self, sensor_data: np.ndarray) -> np.ndarray:
        """Encode sensor data to fingerprint embedding."""
        if self._encoder is not None:
            tensor = torch.from_numpy(sensor_data).float().to(self.device)
            if tensor.ndim == 2:
                tensor = tensor.unsqueeze(0)
            lengths = torch.tensor([tensor.size(1)], device=self.device)
            outputs = self._encoder(tensor, lengths)
            return outputs['features'].cpu().numpy()

        if self._model is not None:
            results = self.predict(sensor_data)
            return results['fingerprint']

        raise RuntimeError("No model or encoder loaded.")

    @torch.no_grad()
    def compare_fingerprints(self, fp1: np.ndarray, fp2: np.ndarray) -> float:
        """Compare two fingerprints using cosine similarity."""
        fp1 = fp1.flatten()
        fp2 = fp2.flatten()

        fp1_norm = fp1 / (np.linalg.norm(fp1) + 1e-8)
        fp2_norm = fp2 / (np.linalg.norm(fp2) + 1e-8)

        similarity = float(np.dot(fp1_norm, fp2_norm))
        return similarity

    def _trigger_alarm(self, results: Dict[str, Any]):
        """Trigger an alarm for detected anomaly."""
        try:
            alarm_processor.process_value(
                'ML_ANOMALY',
                results['anomaly_score'].item()
            )
            logger.warning(f"ML anomaly detected with score {results['anomaly_score']}")
        except Exception as e:
            logger.error(f"Error triggering alarm: {e}")

    def get_stats(self) -> Dict[str, Any]:
        """Get inference statistics."""
        return {
            'inference_count': self._inference_count,
            'model_loaded': self._model is not None or self._encoder is not None,
            'device': str(self.device),
            'running': self._running,
        }


class HistorianMLBridge:
    """Bridge between historian and ML services for batch processing."""

    def __init__(self, inference_service: InferenceService = None):
        self.inference_service = inference_service or InferenceService()
        self.reader = HistorianReader()

    def export_training_data(
        self,
        tag_ids: List[str],
        start: datetime,
        end: datetime,
        output_path: str,
        sequence_length: int = 256,
        stride: int = 64,
    ) -> str:
        """Export historian data to NPZ format for ML training."""
        df = self.reader.get_raw(tag_ids, start, end)

        if df.empty:
            logger.warning("No data found for export")
            return output_path

        pivot = df.pivot(index='time', columns='tag_id', values='value')
        pivot = pivot.fillna(method='ffill').fillna(0)

        values = pivot.values
        timestamps = pivot.index.values

        sequences = []
        for i in range(0, len(values) - sequence_length + 1, stride):
            sequences.append(values[i:i + sequence_length])

        if sequences:
            sequences = np.stack(sequences)
        else:
            sequences = np.array([])

        np.savez(
            output_path,
            sequences=sequences,
            tag_ids=np.array(tag_ids),
            timestamps=timestamps,
            start=str(start),
            end=str(end),
        )

        logger.info(f"Exported {len(sequences)} sequences to {output_path}")
        return output_path

    def batch_inference(
        self,
        tag_ids: List[str],
        start: datetime,
        end: datetime,
        sequence_length: int = 256,
        stride: int = 64,
    ) -> List[Dict[str, Any]]:
        """Run batch inference on historian data."""
        df = self.reader.get_raw(tag_ids, start, end)

        if df.empty:
            return []

        pivot = df.pivot(index='time', columns='tag_id', values='value')
        pivot = pivot.fillna(method='ffill').fillna(0)

        values = pivot.values
        results = []

        for i in range(0, len(values) - sequence_length + 1, stride):
            sequence = values[i:i + sequence_length]
            result = self.inference_service.predict(sequence)
            result['start_idx'] = i
            result['end_idx'] = i + sequence_length
            results.append(result)

        return results


inference_service = InferenceService()
historian_ml_bridge = HistorianMLBridge(inference_service)


def load_model(model_path: str, model_type: str = 'mm_dtae_lstm'):
    """Load a pretrained model."""
    inference_service.load_model(model_path, model_type)


def predict(sensor_data: np.ndarray) -> Dict[str, Any]:
    """Run inference on sensor data."""
    return inference_service.predict(sensor_data)


def encode(sensor_data: np.ndarray) -> np.ndarray:
    """Encode sensor data to fingerprint."""
    return inference_service.encode(sensor_data)


def export_training_data(
    tag_ids: List[str],
    start: datetime,
    end: datetime,
    output_path: str,
) -> str:
    """Export historian data for ML training."""
    return historian_ml_bridge.export_training_data(tag_ids, start, end, output_path)
