"""
LEGO Factory v3 - Slicer Client
================================
Client for communicating with the Docker-based slicer service.
"""

import io
import json
import logging
import time
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Any, Union

import requests

logger = logging.getLogger(__name__)


class SlicerEngine(Enum):
    """Available slicer engines."""
    PRUSASLICER = "prusaslicer"
    CURAENGINE = "curaengine"
    AUTO = "auto"


class JobStatus(Enum):
    """Slicing job status."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class ModelAnalysis:
    """3D model analysis result."""
    valid: bool
    volume_mm3: float
    surface_area_mm2: float
    dimensions_mm: Dict[str, float]
    bounds_mm: Dict[str, List[float]]
    vertex_count: int
    face_count: int
    is_watertight: bool
    euler_number: int
    error: Optional[str] = None


@dataclass
class SliceJob:
    """Slicing job information."""
    job_id: str
    status: JobStatus
    engine: SlicerEngine
    input_file: str
    output_file: Optional[str]
    profile_name: str
    created_at: datetime
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    progress: float
    error: Optional[str]
    metadata: Dict[str, Any]

    @classmethod
    def from_dict(cls, data: Dict) -> 'SliceJob':
        """Create from API response dict."""
        return cls(
            job_id=data['job_id'],
            status=JobStatus(data['status']),
            engine=SlicerEngine(data['engine']),
            input_file=data['input_file'],
            output_file=data.get('output_file'),
            profile_name=data['profile_name'],
            created_at=datetime.fromisoformat(data['created_at']),
            started_at=datetime.fromisoformat(data['started_at']) if data.get('started_at') else None,
            completed_at=datetime.fromisoformat(data['completed_at']) if data.get('completed_at') else None,
            progress=data['progress'],
            error=data.get('error'),
            metadata=data.get('metadata', {}),
        )


@dataclass
class SliceResult:
    """Complete slicing result with G-code."""
    job: SliceJob
    gcode: Optional[bytes]
    print_time_seconds: float
    filament_used_mm: float
    filament_used_grams: float
    layer_count: int


class SlicerServiceError(Exception):
    """Slicer service error."""
    pass


class SlicerClient:
    """
    Client for the LEGO Factory slicer service.

    Provides methods for:
    - Analyzing 3D models (STL, 3MF, OBJ)
    - Submitting slicing jobs
    - Monitoring job progress
    - Downloading generated G-code
    - Managing slicer profiles
    """

    def __init__(
        self,
        base_url: str = "http://localhost:8766",
        timeout: int = 30
    ):
        """
        Initialize slicer client.

        Args:
            base_url: Slicer service URL
            timeout: Request timeout in seconds
        """
        self.base_url = base_url.rstrip('/')
        self.timeout = timeout
        self.session = requests.Session()
        logger.info(f"SlicerClient initialized: {self.base_url}")

    def _request(
        self,
        method: str,
        endpoint: str,
        **kwargs
    ) -> requests.Response:
        """Make HTTP request to slicer service."""
        url = f"{self.base_url}{endpoint}"
        kwargs.setdefault('timeout', self.timeout)

        try:
            response = self.session.request(method, url, **kwargs)
            response.raise_for_status()
            return response
        except requests.RequestException as e:
            logger.error(f"Slicer service request failed: {e}")
            raise SlicerServiceError(f"Request failed: {e}") from e

    def health_check(self) -> Dict[str, Any]:
        """Check slicer service health."""
        response = self._request('GET', '/health')
        return response.json()

    def is_available(self) -> bool:
        """Check if slicer service is available."""
        try:
            health = self.health_check()
            return health.get('status') == 'healthy'
        except SlicerServiceError:
            return False

    # Profile Management

    def list_profiles(self) -> Dict[str, Dict]:
        """List all available slicer profiles."""
        response = self._request('GET', '/profiles')
        return response.json().get('profiles', {})

    def get_profile(self, name: str) -> Optional[Dict]:
        """Get a specific slicer profile."""
        try:
            response = self._request('GET', f'/profiles/{name}')
            return response.json()
        except SlicerServiceError:
            return None

    def save_profile(self, name: str, profile: Dict) -> bool:
        """Save or update a slicer profile."""
        try:
            self._request('PUT', f'/profiles/{name}', json=profile)
            return True
        except SlicerServiceError:
            return False

    # Model Analysis

    def analyze_model(
        self,
        file_path: Union[str, Path] = None,
        file_content: bytes = None,
        filename: str = "model.stl"
    ) -> ModelAnalysis:
        """
        Analyze a 3D model file.

        Args:
            file_path: Path to model file
            file_content: Raw file bytes
            filename: Filename when using file_content

        Returns:
            ModelAnalysis with geometry information
        """
        if file_path:
            file_path = Path(file_path)
            with open(file_path, 'rb') as f:
                file_content = f.read()
            filename = file_path.name

        files = {'file': (filename, io.BytesIO(file_content))}
        response = self._request('POST', '/analyze', files=files)
        data = response.json()

        if data.get('valid', False):
            return ModelAnalysis(
                valid=True,
                volume_mm3=data.get('volume_mm3', 0),
                surface_area_mm2=data.get('surface_area_mm2', 0),
                dimensions_mm=data.get('dimensions_mm', {}),
                bounds_mm=data.get('bounds_mm', {}),
                vertex_count=data.get('vertex_count', 0),
                face_count=data.get('face_count', 0),
                is_watertight=data.get('is_watertight', False),
                euler_number=data.get('euler_number', 0),
            )
        else:
            return ModelAnalysis(
                valid=False,
                volume_mm3=0,
                surface_area_mm2=0,
                dimensions_mm={},
                bounds_mm={},
                vertex_count=0,
                face_count=0,
                is_watertight=False,
                euler_number=0,
                error=data.get('error', 'Unknown error'),
            )

    # Slicing Operations

    def submit_slice_job(
        self,
        file_path: Union[str, Path] = None,
        file_content: bytes = None,
        filename: str = "model.stl",
        profile: str = "lego_pla_quality",
        engine: SlicerEngine = SlicerEngine.AUTO,
        metadata: Dict = None,
    ) -> SliceJob:
        """
        Submit a model for slicing.

        Args:
            file_path: Path to model file
            file_content: Raw file bytes
            filename: Filename when using file_content
            profile: Slicer profile name
            engine: Slicer engine to use
            metadata: Additional metadata

        Returns:
            SliceJob with job ID for tracking
        """
        if file_path:
            file_path = Path(file_path)
            with open(file_path, 'rb') as f:
                file_content = f.read()
            filename = file_path.name

        files = {'file': (filename, io.BytesIO(file_content))}
        data = {
            'profile': profile,
            'engine': engine.value,
        }
        if metadata:
            data['metadata'] = json.dumps(metadata)

        response = self._request('POST', '/slice', files=files, data=data)
        return SliceJob.from_dict(response.json())

    def get_job(self, job_id: str) -> SliceJob:
        """Get job status by ID."""
        response = self._request('GET', f'/jobs/{job_id}')
        return SliceJob.from_dict(response.json())

    def list_jobs(
        self,
        status: JobStatus = None,
        limit: int = 100
    ) -> List[SliceJob]:
        """List slicing jobs."""
        params = {'limit': limit}
        if status:
            params['status'] = status.value

        response = self._request('GET', '/jobs', params=params)
        jobs_data = response.json().get('jobs', [])
        return [SliceJob.from_dict(j) for j in jobs_data]

    def cancel_job(self, job_id: str) -> bool:
        """Cancel a pending job."""
        try:
            self._request('DELETE', f'/jobs/{job_id}')
            return True
        except SlicerServiceError:
            return False

    def download_gcode(self, job_id: str) -> bytes:
        """Download G-code for a completed job."""
        response = self._request('GET', f'/jobs/{job_id}/gcode')
        return response.content

    def wait_for_job(
        self,
        job_id: str,
        poll_interval: float = 1.0,
        timeout: float = 600.0,
    ) -> SliceJob:
        """
        Wait for a job to complete.

        Args:
            job_id: Job ID to wait for
            poll_interval: Seconds between status checks
            timeout: Maximum wait time in seconds

        Returns:
            Completed SliceJob

        Raises:
            SlicerServiceError: If job fails or times out
        """
        start_time = time.time()

        while True:
            job = self.get_job(job_id)

            if job.status == JobStatus.COMPLETED:
                return job

            if job.status == JobStatus.FAILED:
                raise SlicerServiceError(f"Slicing failed: {job.error}")

            if job.status == JobStatus.CANCELLED:
                raise SlicerServiceError("Job was cancelled")

            if time.time() - start_time > timeout:
                raise SlicerServiceError(f"Timeout waiting for job {job_id}")

            time.sleep(poll_interval)

    def slice_and_wait(
        self,
        file_path: Union[str, Path] = None,
        file_content: bytes = None,
        filename: str = "model.stl",
        profile: str = "lego_pla_quality",
        engine: SlicerEngine = SlicerEngine.AUTO,
        metadata: Dict = None,
        timeout: float = 600.0,
    ) -> SliceResult:
        """
        Submit a slicing job and wait for completion.

        Convenience method that combines submit + wait + download.

        Args:
            file_path: Path to model file
            file_content: Raw file bytes
            filename: Filename when using file_content
            profile: Slicer profile name
            engine: Slicer engine to use
            metadata: Additional metadata
            timeout: Maximum wait time

        Returns:
            SliceResult with job info and G-code
        """
        job = self.submit_slice_job(
            file_path=file_path,
            file_content=file_content,
            filename=filename,
            profile=profile,
            engine=engine,
            metadata=metadata,
        )

        logger.info(f"Submitted slicing job: {job.job_id}")

        job = self.wait_for_job(job.job_id, timeout=timeout)

        gcode = self.download_gcode(job.job_id)

        return SliceResult(
            job=job,
            gcode=gcode,
            print_time_seconds=job.metadata.get('print_time_seconds', 0),
            filament_used_mm=job.metadata.get('filament_used_mm', 0),
            filament_used_grams=job.metadata.get('filament_used_grams', 0),
            layer_count=job.metadata.get('layer_count', 0),
        )

    # LEGO-specific Methods

    def slice_brick(
        self,
        brick_stl: bytes,
        brick_id: str,
        material: str = "PLA",
        quality: str = "quality",
    ) -> SliceResult:
        """
        Slice a LEGO brick model.

        Automatically selects the appropriate profile based on material.

        Args:
            brick_stl: STL file content
            brick_id: Brick identifier for metadata
            material: Material type (PLA, ABS, PETG)
            quality: Quality level (draft, standard, quality)

        Returns:
            SliceResult with G-code
        """
        # Select profile based on material
        profile_map = {
            'PLA': 'lego_pla_quality',
            'ABS': 'lego_abs_functional',
            'PETG': 'lego_petg_durable',
        }
        profile = profile_map.get(material.upper(), 'lego_pla_quality')

        # Adjust profile for quality
        if quality == 'draft':
            profile = profile.replace('quality', 'draft').replace('functional', 'draft')

        return self.slice_and_wait(
            file_content=brick_stl,
            filename=f"{brick_id}.stl",
            profile=profile,
            metadata={
                'brick_id': brick_id,
                'material': material,
                'quality': quality,
            },
        )

    def estimate_print_time(
        self,
        file_path: Union[str, Path] = None,
        file_content: bytes = None,
        filename: str = "model.stl",
        profile: str = "lego_pla_quality",
    ) -> Dict[str, float]:
        """
        Estimate print time and material usage without full slicing.

        Uses model analysis and profile settings for estimation.

        Args:
            file_path: Path to model file
            file_content: Raw file bytes
            filename: Filename when using file_content
            profile: Slicer profile for estimation

        Returns:
            Dict with estimated time and material usage
        """
        # Analyze model
        analysis = self.analyze_model(
            file_path=file_path,
            file_content=file_content,
            filename=filename,
        )

        if not analysis.valid:
            return {
                'error': analysis.error,
                'estimated_time_seconds': 0,
                'estimated_filament_mm': 0,
                'estimated_filament_grams': 0,
            }

        # Get profile settings
        profile_data = self.get_profile(profile)
        if not profile_data:
            profile_data = {'layer_height': 0.2, 'print_speed': 50, 'infill_percentage': 20}

        layer_height = profile_data.get('layer_height', 0.2)
        print_speed = profile_data.get('print_speed', 50)
        infill = profile_data.get('infill_percentage', 20) / 100

        # Rough estimation
        height = analysis.dimensions_mm.get('z', 10)
        layer_count = int(height / layer_height)

        # Estimate perimeter and infill lengths
        perimeter_per_layer = 2 * (
            analysis.dimensions_mm.get('x', 10) +
            analysis.dimensions_mm.get('y', 10)
        )
        infill_per_layer = (
            analysis.dimensions_mm.get('x', 10) *
            analysis.dimensions_mm.get('y', 10) *
            infill / 5  # Rough estimate
        )

        total_length_mm = (perimeter_per_layer + infill_per_layer) * layer_count

        # Time estimation (very rough)
        time_seconds = total_length_mm / (print_speed * 60)

        # Material estimation
        filament_diameter = 1.75
        nozzle_diameter = 0.4
        filament_mm = total_length_mm * (nozzle_diameter / filament_diameter) ** 2

        # Weight estimation (PLA density ~1.24 g/cm³)
        filament_volume_cm3 = (
            filament_mm * 3.14159 * (filament_diameter / 2) ** 2
        ) / 1000
        filament_grams = filament_volume_cm3 * 1.24

        return {
            'estimated_time_seconds': time_seconds,
            'estimated_filament_mm': filament_mm,
            'estimated_filament_grams': filament_grams,
            'estimated_layer_count': layer_count,
            'model_volume_mm3': analysis.volume_mm3,
            'model_dimensions_mm': analysis.dimensions_mm,
        }


# Global client instance
_slicer_client: Optional[SlicerClient] = None


def get_slicer_client(base_url: str = None) -> SlicerClient:
    """Get or create global slicer client instance."""
    global _slicer_client
    if _slicer_client is None or base_url:
        _slicer_client = SlicerClient(base_url or "http://localhost:8766")
    return _slicer_client
