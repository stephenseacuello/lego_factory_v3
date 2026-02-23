"""
Data Service Layer - Dataset Management and Versioning.

LEGO MCP v6.0 World-Class Manufacturing Research Platform
Provides DVC-style data versioning, artifact storage, and dataset management.
"""

from .dataset_manager import DatasetManager, Dataset, DatasetVersion
from .artifact_store import ArtifactStore, Artifact, ArtifactType
from .data_versioning import DataVersionControl, DataCommit
from .data_pipeline import DataPipeline, PipelineStage, PipelineRun

__all__ = [
    # Dataset Management
    'DatasetManager',
    'Dataset',
    'DatasetVersion',
    # Artifact Storage
    'ArtifactStore',
    'Artifact',
    'ArtifactType',
    # Data Versioning
    'DataVersionControl',
    'DataCommit',
    # Data Pipeline
    'DataPipeline',
    'PipelineStage',
    'PipelineRun',
]
