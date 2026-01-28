"""
LEGO Factory v3 - ML Data Loaders
==================================
PyTorch Dataset and DataLoader for sensor fingerprinting.
"""

import json
import logging
import numpy as np
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any

import torch
from torch.utils.data import Dataset, DataLoader, random_split

logger = logging.getLogger(__name__)


class SensorDataset(Dataset):
    """
    PyTorch Dataset for sensor-to-gcode fingerprinting.

    Loads data from NPZ files containing:
    - sensor_data: [N, seq_len, num_sensors] sensor readings
    - gcode_tokens: [N, gcode_len] tokenized G-code
    - program_ids: [N] unique program identifiers
    - labels: [N] operation labels (optional)
    - anomaly_labels: [N] anomaly flags (optional)
    - regression_targets: [N, 3] tool wear, remaining life, etc. (optional)
    """

    def __init__(
        self,
        data_path: str,
        sequence_length: int = 256,
        sensor_dims: List[int] = None,
        transform=None,
        augment: bool = False
    ):
        """
        Args:
            data_path: Path to NPZ file or directory of NPZ files
            sequence_length: Fixed sequence length (pad/truncate)
            sensor_dims: List of dimensions per sensor modality
            transform: Optional transform function
            augment: Enable data augmentation
        """
        self.sequence_length = sequence_length
        self.sensor_dims = sensor_dims or [6, 3, 3]  # pos, accel, temp
        self.transform = transform
        self.augment = augment

        self.data = self._load_data(data_path)
        logger.info(f"Loaded dataset with {len(self)} samples")

    def _load_data(self, path: str) -> Dict[str, np.ndarray]:
        """Load data from NPZ file(s)."""
        path = Path(path)

        if path.is_file() and path.suffix == '.npz':
            return dict(np.load(path, allow_pickle=True))

        elif path.is_dir():
            # Load and concatenate multiple NPZ files
            all_data = {}
            for npz_file in path.glob('*.npz'):
                data = dict(np.load(npz_file, allow_pickle=True))
                for key, arr in data.items():
                    if key in all_data:
                        all_data[key] = np.concatenate([all_data[key], arr])
                    else:
                        all_data[key] = arr
            return all_data

        else:
            raise ValueError(f"Invalid data path: {path}")

    def __len__(self) -> int:
        return len(self.data.get('sensor_data', []))

    def __getitem__(self, idx: int) -> Dict[str, torch.Tensor]:
        """Get a single sample."""
        sample = {}

        # Sensor data
        sensor_data = self.data['sensor_data'][idx]

        # Pad or truncate to sequence_length
        if len(sensor_data) < self.sequence_length:
            pad_length = self.sequence_length - len(sensor_data)
            sensor_data = np.pad(
                sensor_data,
                ((0, pad_length), (0, 0)),
                mode='constant'
            )
        elif len(sensor_data) > self.sequence_length:
            sensor_data = sensor_data[:self.sequence_length]

        # Split into modalities based on sensor_dims
        modalities = []
        offset = 0
        for dim in self.sensor_dims:
            modality = sensor_data[:, offset:offset + dim]
            modalities.append(torch.tensor(modality, dtype=torch.float32))
            offset += dim

        sample['sensors'] = modalities

        # G-code tokens
        if 'gcode_tokens' in self.data:
            gcode = self.data['gcode_tokens'][idx]
            sample['gcode'] = torch.tensor(gcode, dtype=torch.long)

        # Program ID for contrastive learning
        if 'program_ids' in self.data:
            sample['program_id'] = torch.tensor(
                self.data['program_ids'][idx],
                dtype=torch.long
            )

        # Classification labels
        if 'labels' in self.data:
            sample['cls'] = torch.tensor(
                self.data['labels'][idx],
                dtype=torch.long
            )

        # Anomaly labels
        if 'anomaly_labels' in self.data:
            sample['anom'] = torch.tensor(
                self.data['anomaly_labels'][idx],
                dtype=torch.float32
            )

        # Regression targets
        if 'regression_targets' in self.data:
            sample['reg'] = torch.tensor(
                self.data['regression_targets'][idx],
                dtype=torch.float32
            )

        # Future prediction targets (next N steps)
        if 'future_data' in self.data:
            sample['future'] = torch.tensor(
                self.data['future_data'][idx],
                dtype=torch.float32
            )

        # Apply augmentation
        if self.augment:
            sample = self._augment(sample)

        # Apply transform
        if self.transform:
            sample = self.transform(sample)

        return sample

    def _augment(self, sample: Dict[str, torch.Tensor]) -> Dict[str, torch.Tensor]:
        """Apply data augmentation."""
        # Random noise injection
        if np.random.rand() < 0.5:
            noise_scale = 0.01
            for i, modality in enumerate(sample['sensors']):
                noise = torch.randn_like(modality) * noise_scale
                sample['sensors'][i] = modality + noise

        # Random time shift
        if np.random.rand() < 0.3:
            shift = np.random.randint(-10, 10)
            for i, modality in enumerate(sample['sensors']):
                sample['sensors'][i] = torch.roll(modality, shifts=shift, dims=0)

        # Random dropout (zero out some timesteps)
        if np.random.rand() < 0.2:
            dropout_mask = torch.rand(self.sequence_length) > 0.1
            for i, modality in enumerate(sample['sensors']):
                sample['sensors'][i] = modality * dropout_mask.unsqueeze(1)

        return sample


class HistorianDataset(Dataset):
    """
    Dataset that loads directly from historian database.

    Queries TimescaleDB for sensor data and joins with G-code job info.
    """

    def __init__(
        self,
        tag_names: List[str],
        start_time: str,
        end_time: str,
        sequence_length: int = 256,
        step_size: int = 64,
        machine_id: str = None
    ):
        """
        Args:
            tag_names: List of sensor tag names to query
            start_time: Query start time (ISO format)
            end_time: Query end time (ISO format)
            sequence_length: Sequence length per sample
            step_size: Sliding window step size
            machine_id: Filter by machine
        """
        self.tag_names = tag_names
        self.sequence_length = sequence_length
        self.step_size = step_size

        self.data = self._query_historian(start_time, end_time, machine_id)

    def _query_historian(
        self,
        start_time: str,
        end_time: str,
        machine_id: str = None
    ) -> np.ndarray:
        """Query historian for sensor data."""
        try:
            from services.scada.historian import get_historian_service
            historian = get_historian_service()

            # Query each tag
            data_frames = []
            for tag_name in self.tag_names:
                df = historian.query_tag(
                    tag_name=tag_name,
                    start_time=start_time,
                    end_time=end_time
                )
                data_frames.append(df)

            # Join on timestamp and convert to numpy
            # This is a simplified version - real implementation would
            # properly align timestamps
            if data_frames:
                import pandas as pd
                combined = pd.concat(data_frames, axis=1)
                return combined.values

        except Exception as e:
            logger.error(f"Failed to query historian: {e}")

        return np.array([])

    def __len__(self) -> int:
        if len(self.data) < self.sequence_length:
            return 0
        return (len(self.data) - self.sequence_length) // self.step_size + 1

    def __getitem__(self, idx: int) -> Dict[str, torch.Tensor]:
        start = idx * self.step_size
        end = start + self.sequence_length
        sequence = self.data[start:end]

        return {
            'sensors': [torch.tensor(sequence, dtype=torch.float32)],
        }


def collate_fn(batch: List[Dict[str, Any]]) -> Dict[str, torch.Tensor]:
    """
    Custom collate function for variable-length sensor modalities.
    """
    result = {}

    # Collate sensor modalities
    if 'sensors' in batch[0]:
        num_modalities = len(batch[0]['sensors'])
        result['sensors'] = [
            torch.stack([sample['sensors'][i] for sample in batch])
            for i in range(num_modalities)
        ]

    # Collate other tensors
    for key in batch[0].keys():
        if key == 'sensors':
            continue
        result[key] = torch.stack([sample[key] for sample in batch])

    return result


def create_data_loaders(
    data_path: str,
    batch_size: int = 32,
    sequence_length: int = 256,
    sensor_dims: List[int] = None,
    train_split: float = 0.8,
    val_split: float = 0.1,
    num_workers: int = 4,
    augment_train: bool = True
) -> Tuple[DataLoader, DataLoader, DataLoader]:
    """
    Create train/val/test data loaders.

    Args:
        data_path: Path to data
        batch_size: Batch size
        sequence_length: Sequence length
        sensor_dims: Sensor dimensions per modality
        train_split: Fraction for training
        val_split: Fraction for validation
        num_workers: DataLoader workers
        augment_train: Augment training data

    Returns:
        train_loader, val_loader, test_loader
    """
    # Create full dataset
    full_dataset = SensorDataset(
        data_path=data_path,
        sequence_length=sequence_length,
        sensor_dims=sensor_dims,
        augment=False  # Augment only train split
    )

    # Calculate split sizes
    total_size = len(full_dataset)
    train_size = int(total_size * train_split)
    val_size = int(total_size * val_split)
    test_size = total_size - train_size - val_size

    # Split dataset
    train_dataset, val_dataset, test_dataset = random_split(
        full_dataset,
        [train_size, val_size, test_size],
        generator=torch.Generator().manual_seed(42)
    )

    # Create augmented train dataset wrapper
    if augment_train:
        class AugmentedSubset(Dataset):
            def __init__(self, subset, parent_dataset):
                self.subset = subset
                self.parent_dataset = parent_dataset

            def __len__(self):
                return len(self.subset)

            def __getitem__(self, idx):
                sample = self.subset[idx]
                return self.parent_dataset._augment(sample)

        train_dataset = AugmentedSubset(train_dataset, full_dataset)

    # Create data loaders
    train_loader = DataLoader(
        train_dataset,
        batch_size=batch_size,
        shuffle=True,
        num_workers=num_workers,
        collate_fn=collate_fn,
        pin_memory=True,
        drop_last=True
    )

    val_loader = DataLoader(
        val_dataset,
        batch_size=batch_size,
        shuffle=False,
        num_workers=num_workers,
        collate_fn=collate_fn,
        pin_memory=True
    )

    test_loader = DataLoader(
        test_dataset,
        batch_size=batch_size,
        shuffle=False,
        num_workers=num_workers,
        collate_fn=collate_fn,
        pin_memory=True
    )

    logger.info(f"Created data loaders: train={train_size}, val={val_size}, test={test_size}")

    return train_loader, val_loader, test_loader
