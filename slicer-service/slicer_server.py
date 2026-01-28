"""
LEGO Factory v3 - Slicer Service
================================
HTTP server for 3D model slicing using PrusaSlicer and CuraEngine.
"""

import json
import logging
import os
import shutil
import subprocess
import tempfile
import threading
import time
import uuid
from dataclasses import dataclass, asdict
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Any

from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import trimesh
import yaml

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)

# Directories
INPUT_DIR = Path("/app/input")
OUTPUT_DIR = Path("/app/output")
PROFILES_DIR = Path("/app/profiles")
TEMP_DIR = Path("/app/temp")

# Ensure directories exist
for d in [INPUT_DIR, OUTPUT_DIR, PROFILES_DIR, TEMP_DIR]:
    d.mkdir(parents=True, exist_ok=True)


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
class SliceJob:
    """Slicing job record."""
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

    def to_dict(self) -> Dict:
        return {
            'job_id': self.job_id,
            'status': self.status.value,
            'engine': self.engine.value,
            'input_file': self.input_file,
            'output_file': self.output_file,
            'profile_name': self.profile_name,
            'created_at': self.created_at.isoformat(),
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'progress': self.progress,
            'error': self.error,
            'metadata': self.metadata,
        }


@dataclass
class SliceResult:
    """Result of a slicing operation."""
    success: bool
    gcode_path: Optional[str]
    print_time_seconds: float
    filament_used_mm: float
    filament_used_grams: float
    layer_count: int
    warnings: List[str]
    metadata: Dict[str, Any]


class SlicerService:
    """Main slicer service."""

    def __init__(self):
        self.jobs: Dict[str, SliceJob] = {}
        self.job_queue: List[str] = []
        self.processing = False
        self.worker_thread = None
        self._load_profiles()
        self._start_worker()

    def _load_profiles(self):
        """Load slicer profiles from disk."""
        self.profiles: Dict[str, Dict] = {}

        for profile_file in PROFILES_DIR.glob("*.yaml"):
            try:
                with open(profile_file) as f:
                    profile = yaml.safe_load(f)
                    profile_name = profile_file.stem
                    self.profiles[profile_name] = profile
                    logger.info(f"Loaded profile: {profile_name}")
            except Exception as e:
                logger.error(f"Failed to load profile {profile_file}: {e}")

        # Create default profiles if none exist
        if not self.profiles:
            self._create_default_profiles()

    def _create_default_profiles(self):
        """Create default slicer profiles."""
        default_profiles = {
            'lego_pla_draft': {
                'name': 'LEGO PLA Draft',
                'material': 'PLA',
                'layer_height': 0.3,
                'infill_percentage': 15,
                'print_speed': 80,
                'nozzle_temperature': 210,
                'bed_temperature': 60,
                'support_enabled': False,
                'brim_width': 0,
                'retraction_enabled': True,
                'retraction_distance': 5.0,
                'retraction_speed': 45,
            },
            'lego_pla_quality': {
                'name': 'LEGO PLA Quality',
                'material': 'PLA',
                'layer_height': 0.12,
                'infill_percentage': 25,
                'print_speed': 50,
                'nozzle_temperature': 205,
                'bed_temperature': 60,
                'support_enabled': False,
                'brim_width': 3,
                'retraction_enabled': True,
                'retraction_distance': 5.0,
                'retraction_speed': 45,
            },
            'lego_abs_standard': {
                'name': 'LEGO ABS Standard',
                'material': 'ABS',
                'layer_height': 0.2,
                'infill_percentage': 20,
                'print_speed': 60,
                'nozzle_temperature': 245,
                'bed_temperature': 100,
                'support_enabled': False,
                'brim_width': 5,
                'retraction_enabled': True,
                'retraction_distance': 4.0,
                'retraction_speed': 40,
                'enclosure_temperature': 45,
            },
            'lego_petg_functional': {
                'name': 'LEGO PETG Functional',
                'material': 'PETG',
                'layer_height': 0.2,
                'infill_percentage': 30,
                'print_speed': 55,
                'nozzle_temperature': 240,
                'bed_temperature': 80,
                'support_enabled': False,
                'brim_width': 4,
                'retraction_enabled': True,
                'retraction_distance': 6.0,
                'retraction_speed': 35,
            },
            'lego_resin_high_detail': {
                'name': 'LEGO Resin High Detail',
                'material': 'RESIN',
                'layer_height': 0.05,
                'exposure_time': 2.5,
                'bottom_exposure_time': 30,
                'bottom_layers': 5,
                'lift_height': 5,
                'lift_speed': 60,
            },
        }

        for name, profile in default_profiles.items():
            profile_path = PROFILES_DIR / f"{name}.yaml"
            with open(profile_path, 'w') as f:
                yaml.dump(profile, f, default_flow_style=False)
            self.profiles[name] = profile
            logger.info(f"Created default profile: {name}")

    def _start_worker(self):
        """Start background job worker."""
        self.processing = True
        self.worker_thread = threading.Thread(target=self._process_jobs, daemon=True)
        self.worker_thread.start()

    def _process_jobs(self):
        """Process jobs from queue."""
        while self.processing:
            if self.job_queue:
                job_id = self.job_queue.pop(0)
                job = self.jobs.get(job_id)
                if job and job.status == JobStatus.PENDING:
                    self._execute_job(job)
            else:
                time.sleep(0.5)

    def _execute_job(self, job: SliceJob):
        """Execute a slicing job."""
        job.status = JobStatus.PROCESSING
        job.started_at = datetime.utcnow()
        logger.info(f"Starting job {job.job_id}")

        try:
            # Get profile
            profile = self.profiles.get(job.profile_name)
            if not profile:
                raise ValueError(f"Unknown profile: {job.profile_name}")

            # Determine engine
            engine = job.engine
            if engine == SlicerEngine.AUTO:
                engine = self._select_engine(job.input_file, profile)

            # Execute slicing
            if engine == SlicerEngine.PRUSASLICER:
                result = self._slice_with_prusaslicer(job.input_file, profile)
            elif engine == SlicerEngine.CURAENGINE:
                result = self._slice_with_curaengine(job.input_file, profile)
            else:
                raise ValueError(f"Unknown slicer engine: {engine}")

            if result.success:
                # Move output to final location
                output_filename = f"{job.job_id}.gcode"
                final_output = OUTPUT_DIR / output_filename
                shutil.move(result.gcode_path, final_output)

                job.output_file = str(final_output)
                job.status = JobStatus.COMPLETED
                job.metadata.update({
                    'print_time_seconds': result.print_time_seconds,
                    'filament_used_mm': result.filament_used_mm,
                    'filament_used_grams': result.filament_used_grams,
                    'layer_count': result.layer_count,
                    'warnings': result.warnings,
                })
                logger.info(f"Job {job.job_id} completed successfully")
            else:
                job.status = JobStatus.FAILED
                job.error = "Slicing failed"
                logger.error(f"Job {job.job_id} failed")

        except Exception as e:
            job.status = JobStatus.FAILED
            job.error = str(e)
            logger.error(f"Job {job.job_id} failed with error: {e}")

        job.completed_at = datetime.utcnow()
        job.progress = 1.0 if job.status == JobStatus.COMPLETED else 0.0

    def _select_engine(self, input_file: str, profile: Dict) -> SlicerEngine:
        """Select best slicer engine based on input and profile."""
        # Default to PrusaSlicer for most cases
        return SlicerEngine.PRUSASLICER

    def _slice_with_prusaslicer(self, input_file: str, profile: Dict) -> SliceResult:
        """Slice with PrusaSlicer CLI."""
        output_file = TEMP_DIR / f"{uuid.uuid4()}.gcode"

        # Build command
        cmd = [
            "prusa-slicer",
            "--export-gcode",
            "--output", str(output_file),
            "--layer-height", str(profile.get('layer_height', 0.2)),
            "--fill-density", f"{profile.get('infill_percentage', 20)}%",
            "--perimeters", "3",
            "--top-solid-layers", "4",
            "--bottom-solid-layers", "4",
        ]

        # Add temperature settings
        if 'nozzle_temperature' in profile:
            cmd.extend(["--temperature", str(profile['nozzle_temperature'])])
        if 'bed_temperature' in profile:
            cmd.extend(["--bed-temperature", str(profile['bed_temperature'])])

        # Add speed settings
        if 'print_speed' in profile:
            cmd.extend(["--perimeter-speed", str(profile['print_speed'])])
            cmd.extend(["--infill-speed", str(int(profile['print_speed'] * 1.2))])

        # Add support settings
        if profile.get('support_enabled'):
            cmd.append("--support-material")

        # Add brim settings
        brim_width = profile.get('brim_width', 0)
        if brim_width > 0:
            cmd.extend(["--brim-width", str(brim_width)])

        # Add retraction settings
        if profile.get('retraction_enabled', True):
            cmd.extend(["--retract-length", str(profile.get('retraction_distance', 5.0))])
            cmd.extend(["--retract-speed", str(profile.get('retraction_speed', 45))])

        # Add input file
        cmd.append(str(input_file))

        logger.info(f"Running PrusaSlicer: {' '.join(cmd)}")

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300,
            )

            if result.returncode == 0 and output_file.exists():
                # Parse G-code for metadata
                metadata = self._parse_gcode_metadata(output_file)
                return SliceResult(
                    success=True,
                    gcode_path=str(output_file),
                    print_time_seconds=metadata.get('print_time', 0),
                    filament_used_mm=metadata.get('filament_mm', 0),
                    filament_used_grams=metadata.get('filament_grams', 0),
                    layer_count=metadata.get('layer_count', 0),
                    warnings=[],
                    metadata=metadata,
                )
            else:
                logger.error(f"PrusaSlicer error: {result.stderr}")
                return SliceResult(
                    success=False,
                    gcode_path=None,
                    print_time_seconds=0,
                    filament_used_mm=0,
                    filament_used_grams=0,
                    layer_count=0,
                    warnings=[result.stderr],
                    metadata={},
                )

        except subprocess.TimeoutExpired:
            return SliceResult(
                success=False,
                gcode_path=None,
                print_time_seconds=0,
                filament_used_mm=0,
                filament_used_grams=0,
                layer_count=0,
                warnings=["Slicing timeout"],
                metadata={},
            )

    def _slice_with_curaengine(self, input_file: str, profile: Dict) -> SliceResult:
        """Slice with CuraEngine CLI."""
        output_file = TEMP_DIR / f"{uuid.uuid4()}.gcode"

        # CuraEngine requires a settings JSON
        settings = {
            "layer_height": profile.get('layer_height', 0.2),
            "infill_sparse_density": profile.get('infill_percentage', 20),
            "speed_print": profile.get('print_speed', 60),
            "material_print_temperature": profile.get('nozzle_temperature', 200),
            "material_bed_temperature": profile.get('bed_temperature', 60),
            "retraction_enable": profile.get('retraction_enabled', True),
            "retraction_amount": profile.get('retraction_distance', 5.0),
            "retraction_speed": profile.get('retraction_speed', 45),
            "support_enable": profile.get('support_enabled', False),
            "adhesion_type": "brim" if profile.get('brim_width', 0) > 0 else "none",
        }

        settings_file = TEMP_DIR / f"{uuid.uuid4()}_settings.json"
        with open(settings_file, 'w') as f:
            json.dump(settings, f)

        cmd = [
            "CuraEngine",
            "slice",
            "-j", str(settings_file),
            "-o", str(output_file),
            "-l", str(input_file),
        ]

        logger.info(f"Running CuraEngine: {' '.join(cmd)}")

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300,
            )

            # Clean up settings file
            settings_file.unlink(missing_ok=True)

            if result.returncode == 0 and output_file.exists():
                metadata = self._parse_gcode_metadata(output_file)
                return SliceResult(
                    success=True,
                    gcode_path=str(output_file),
                    print_time_seconds=metadata.get('print_time', 0),
                    filament_used_mm=metadata.get('filament_mm', 0),
                    filament_used_grams=metadata.get('filament_grams', 0),
                    layer_count=metadata.get('layer_count', 0),
                    warnings=[],
                    metadata=metadata,
                )
            else:
                logger.error(f"CuraEngine error: {result.stderr}")
                return SliceResult(
                    success=False,
                    gcode_path=None,
                    print_time_seconds=0,
                    filament_used_mm=0,
                    filament_used_grams=0,
                    layer_count=0,
                    warnings=[result.stderr],
                    metadata={},
                )

        except subprocess.TimeoutExpired:
            settings_file.unlink(missing_ok=True)
            return SliceResult(
                success=False,
                gcode_path=None,
                print_time_seconds=0,
                filament_used_mm=0,
                filament_used_grams=0,
                layer_count=0,
                warnings=["Slicing timeout"],
                metadata={},
            )

    def _parse_gcode_metadata(self, gcode_path: Path) -> Dict[str, Any]:
        """Parse metadata from G-code comments."""
        metadata = {
            'print_time': 0,
            'filament_mm': 0,
            'filament_grams': 0,
            'layer_count': 0,
        }

        try:
            with open(gcode_path) as f:
                for line in f:
                    if not line.startswith(';'):
                        continue

                    line = line[1:].strip()

                    # PrusaSlicer format
                    if line.startswith('estimated printing time'):
                        # Parse time like "1h 30m 45s"
                        pass
                    elif line.startswith('filament used [mm]'):
                        try:
                            metadata['filament_mm'] = float(line.split('=')[1].strip())
                        except (ValueError, IndexError):
                            pass
                    elif line.startswith('filament used [g]'):
                        try:
                            metadata['filament_grams'] = float(line.split('=')[1].strip())
                        except (ValueError, IndexError):
                            pass
                    elif line.startswith('LAYER_COUNT:'):
                        try:
                            metadata['layer_count'] = int(line.split(':')[1].strip())
                        except (ValueError, IndexError):
                            pass

                    # CuraEngine format
                    elif line.startswith('TIME:'):
                        try:
                            metadata['print_time'] = int(line.split(':')[1].strip())
                        except (ValueError, IndexError):
                            pass
                    elif line.startswith('Filament used:'):
                        try:
                            value = line.split(':')[1].strip().replace('m', '')
                            metadata['filament_mm'] = float(value) * 1000
                        except (ValueError, IndexError):
                            pass

        except Exception as e:
            logger.error(f"Failed to parse G-code metadata: {e}")

        return metadata

    def create_job(
        self,
        input_file: str,
        profile_name: str = "lego_pla_quality",
        engine: str = "auto",
        metadata: Dict = None,
    ) -> SliceJob:
        """Create a new slicing job."""
        job_id = str(uuid.uuid4())

        job = SliceJob(
            job_id=job_id,
            status=JobStatus.PENDING,
            engine=SlicerEngine(engine),
            input_file=input_file,
            output_file=None,
            profile_name=profile_name,
            created_at=datetime.utcnow(),
            started_at=None,
            completed_at=None,
            progress=0.0,
            error=None,
            metadata=metadata or {},
        )

        self.jobs[job_id] = job
        self.job_queue.append(job_id)
        logger.info(f"Created job {job_id}")

        return job

    def get_job(self, job_id: str) -> Optional[SliceJob]:
        """Get job by ID."""
        return self.jobs.get(job_id)

    def cancel_job(self, job_id: str) -> bool:
        """Cancel a pending job."""
        job = self.jobs.get(job_id)
        if job and job.status == JobStatus.PENDING:
            job.status = JobStatus.CANCELLED
            if job_id in self.job_queue:
                self.job_queue.remove(job_id)
            return True
        return False

    def list_jobs(self, status: JobStatus = None, limit: int = 100) -> List[SliceJob]:
        """List jobs, optionally filtered by status."""
        jobs = list(self.jobs.values())
        if status:
            jobs = [j for j in jobs if j.status == status]
        jobs.sort(key=lambda j: j.created_at, reverse=True)
        return jobs[:limit]

    def analyze_model(self, file_path: str) -> Dict[str, Any]:
        """Analyze a 3D model file."""
        try:
            mesh = trimesh.load(file_path)

            # Calculate model properties
            bounds = mesh.bounds
            dimensions = bounds[1] - bounds[0]

            return {
                'valid': mesh.is_watertight,
                'volume_mm3': float(mesh.volume),
                'surface_area_mm2': float(mesh.area),
                'dimensions_mm': {
                    'x': float(dimensions[0]),
                    'y': float(dimensions[1]),
                    'z': float(dimensions[2]),
                },
                'bounds_mm': {
                    'min': bounds[0].tolist(),
                    'max': bounds[1].tolist(),
                },
                'vertex_count': len(mesh.vertices),
                'face_count': len(mesh.faces),
                'is_watertight': mesh.is_watertight,
                'euler_number': int(mesh.euler_number),
            }
        except Exception as e:
            return {
                'valid': False,
                'error': str(e),
            }


# Global service instance
slicer_service = SlicerService()


# Flask routes
@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint."""
    return jsonify({
        'status': 'healthy',
        'version': '1.0.0',
        'engines': ['prusaslicer', 'curaengine'],
        'profiles': list(slicer_service.profiles.keys()),
        'pending_jobs': len(slicer_service.job_queue),
    })


@app.route('/profiles', methods=['GET'])
def list_profiles():
    """List available slicer profiles."""
    return jsonify({
        'profiles': slicer_service.profiles,
    })


@app.route('/profiles/<name>', methods=['GET'])
def get_profile(name: str):
    """Get a specific profile."""
    profile = slicer_service.profiles.get(name)
    if profile:
        return jsonify(profile)
    return jsonify({'error': 'Profile not found'}), 404


@app.route('/profiles/<name>', methods=['PUT'])
def update_profile(name: str):
    """Update or create a profile."""
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400

    # Save to disk
    profile_path = PROFILES_DIR / f"{name}.yaml"
    with open(profile_path, 'w') as f:
        yaml.dump(data, f, default_flow_style=False)

    slicer_service.profiles[name] = data
    return jsonify({'status': 'saved', 'name': name})


@app.route('/analyze', methods=['POST'])
def analyze_model():
    """Analyze a 3D model file."""
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400

    # Save file temporarily
    temp_path = TEMP_DIR / f"{uuid.uuid4()}_{file.filename}"
    file.save(temp_path)

    try:
        result = slicer_service.analyze_model(str(temp_path))
        return jsonify(result)
    finally:
        temp_path.unlink(missing_ok=True)


@app.route('/slice', methods=['POST'])
def slice_model():
    """Submit a model for slicing."""
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400

    # Get parameters
    profile_name = request.form.get('profile', 'lego_pla_quality')
    engine = request.form.get('engine', 'auto')
    metadata = {}
    if request.form.get('metadata'):
        try:
            metadata = json.loads(request.form['metadata'])
        except json.JSONDecodeError:
            pass

    # Save input file
    input_filename = f"{uuid.uuid4()}_{file.filename}"
    input_path = INPUT_DIR / input_filename
    file.save(input_path)

    # Create job
    job = slicer_service.create_job(
        input_file=str(input_path),
        profile_name=profile_name,
        engine=engine,
        metadata=metadata,
    )

    return jsonify(job.to_dict()), 202


@app.route('/jobs', methods=['GET'])
def list_jobs():
    """List slicing jobs."""
    status_str = request.args.get('status')
    status = JobStatus(status_str) if status_str else None
    limit = int(request.args.get('limit', 100))

    jobs = slicer_service.list_jobs(status=status, limit=limit)
    return jsonify({
        'jobs': [j.to_dict() for j in jobs],
    })


@app.route('/jobs/<job_id>', methods=['GET'])
def get_job(job_id: str):
    """Get job status."""
    job = slicer_service.get_job(job_id)
    if job:
        return jsonify(job.to_dict())
    return jsonify({'error': 'Job not found'}), 404


@app.route('/jobs/<job_id>', methods=['DELETE'])
def cancel_job(job_id: str):
    """Cancel a pending job."""
    if slicer_service.cancel_job(job_id):
        return jsonify({'status': 'cancelled'})
    return jsonify({'error': 'Cannot cancel job'}), 400


@app.route('/jobs/<job_id>/gcode', methods=['GET'])
def download_gcode(job_id: str):
    """Download generated G-code."""
    job = slicer_service.get_job(job_id)
    if not job:
        return jsonify({'error': 'Job not found'}), 404

    if job.status != JobStatus.COMPLETED or not job.output_file:
        return jsonify({'error': 'G-code not available'}), 400

    return send_file(
        job.output_file,
        mimetype='text/plain',
        as_attachment=True,
        download_name=f"{job_id}.gcode",
    )


if __name__ == '__main__':
    logger.info("Starting Slicer Service on port 8766")
    app.run(host='0.0.0.0', port=8766, debug=False)
