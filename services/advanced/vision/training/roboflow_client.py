"""
Roboflow Client - Workspace & Project Management

LegoMCP World-Class Manufacturing System v6.0
Phase 26: Vision AI & ML Training

Provides Roboflow integration:
- Workspace management
- Project creation
- Dataset upload/download
- Model training triggers
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Any
from enum import Enum
import uuid
import os


class ProjectType(Enum):
    """Roboflow project types."""
    OBJECT_DETECTION = "object-detection"
    CLASSIFICATION = "classification"
    INSTANCE_SEGMENTATION = "instance-segmentation"
    SEMANTIC_SEGMENTATION = "semantic-segmentation"


class AnnotationFormat(Enum):
    """Supported annotation formats."""
    YOLO = "yolov8"
    YOLO_DARKNET = "darknet"
    COCO = "coco"
    VOC = "voc"
    CREATEML = "createml"
    TFRECORD = "tfrecord"


class ModelFramework(Enum):
    """Supported training frameworks."""
    YOLOV8 = "yolov8"
    YOLOV5 = "yolov5"
    YOLOV11 = "yolov11"
    FASTER_RCNN = "faster-rcnn"
    EFFICIENTDET = "efficientdet"


@dataclass
class RoboflowDataset:
    """A Roboflow dataset version."""
    dataset_id: str
    version: int
    name: str
    project_id: str
    image_count: int
    split: Dict[str, int]  # train/valid/test counts
    preprocessing: Dict[str, Any]
    augmentation: Dict[str, Any]
    created_at: datetime = field(default_factory=datetime.utcnow)
    export_formats: List[str] = field(default_factory=list)


@dataclass
class RoboflowProject:
    """A Roboflow project."""
    project_id: str
    name: str
    project_type: ProjectType
    workspace_id: str
    classes: List[str]
    created_at: datetime = field(default_factory=datetime.utcnow)
    annotation_group: str = ""
    versions: List[RoboflowDataset] = field(default_factory=list)
    image_count: int = 0


@dataclass
class RoboflowWorkspace:
    """A Roboflow workspace."""
    workspace_id: str
    name: str
    url: str
    projects: Dict[str, RoboflowProject] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class TrainingJob:
    """A model training job."""
    job_id: str
    project_id: str
    dataset_version: int
    framework: ModelFramework
    status: str  # queued, training, completed, failed
    epochs: int
    batch_size: int
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    metrics: Dict[str, float] = field(default_factory=dict)
    model_id: Optional[str] = None


class RoboflowClient:
    """
    Roboflow API client for dataset and model management.

    Provides integration with Roboflow for:
    - Creating and managing workspaces/projects
    - Uploading and annotating images
    - Dataset versioning
    - Model training
    """

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize Roboflow client.

        Args:
            api_key: Roboflow API key (or set ROBOFLOW_API_KEY env var)
        """
        self.api_key = api_key or os.environ.get("ROBOFLOW_API_KEY")
        self.workspaces: Dict[str, RoboflowWorkspace] = {}
        self.training_jobs: Dict[str, TrainingJob] = {}
        self._connected = False
        self._setup_demo_data()

    def _setup_demo_data(self):
        """Set up demo workspace and projects."""
        workspace = RoboflowWorkspace(
            workspace_id="legomcp",
            name="LegoMCP Manufacturing",
            url="https://app.roboflow.com/legomcp",
        )

        # LEGO brick detection project
        brick_project = RoboflowProject(
            project_id="lego-bricks",
            name="LEGO Brick Detection",
            project_type=ProjectType.OBJECT_DETECTION,
            workspace_id=workspace.workspace_id,
            classes=[
                "brick_2x4", "brick_2x2", "brick_1x4", "brick_1x2", "brick_1x1",
                "plate_2x4", "plate_2x2", "plate_1x4", "plate_1x2",
                "slope_2x2", "slope_1x2", "tile_2x2", "tile_1x4",
                "technic_beam", "technic_pin", "technic_axle",
                "minifig_head", "minifig_torso", "minifig_legs",
            ],
            annotation_group="lego-bricks",
            image_count=0,
        )

        # 3D print defect detection project
        defect_project = RoboflowProject(
            project_id="print-defects",
            name="3D Print Defect Detection",
            project_type=ProjectType.OBJECT_DETECTION,
            workspace_id=workspace.workspace_id,
            classes=[
                "layer_shift", "stringing", "warping", "under_extrusion",
                "over_extrusion", "z_wobble", "blob", "gap",
            ],
            annotation_group="print-defects",
            image_count=0,
        )

        # Surface quality classification project
        quality_project = RoboflowProject(
            project_id="surface-quality",
            name="Surface Quality Classification",
            project_type=ProjectType.CLASSIFICATION,
            workspace_id=workspace.workspace_id,
            classes=["excellent", "good", "acceptable", "poor", "defective"],
            annotation_group="surface-quality",
            image_count=0,
        )

        workspace.projects = {
            brick_project.project_id: brick_project,
            defect_project.project_id: defect_project,
            quality_project.project_id: quality_project,
        }

        self.workspaces[workspace.workspace_id] = workspace

    def connect(self) -> bool:
        """
        Connect to Roboflow API.

        Returns:
            True if connection successful
        """
        if not self.api_key:
            # Demo mode without API key
            self._connected = True
            return True

        # Real connection would validate API key here
        self._connected = True
        return True

    def disconnect(self):
        """Disconnect from Roboflow API."""
        self._connected = False

    @property
    def is_connected(self) -> bool:
        """Check if connected to Roboflow."""
        return self._connected

    def get_workspace(self, workspace_id: str) -> Optional[RoboflowWorkspace]:
        """Get workspace by ID."""
        return self.workspaces.get(workspace_id)

    def list_workspaces(self) -> List[RoboflowWorkspace]:
        """List all workspaces."""
        return list(self.workspaces.values())

    def create_project(
        self,
        workspace_id: str,
        name: str,
        project_type: ProjectType,
        classes: List[str],
        annotation_group: Optional[str] = None
    ) -> Optional[RoboflowProject]:
        """
        Create a new project in workspace.

        Args:
            workspace_id: Workspace ID
            name: Project name
            project_type: Type of project
            classes: List of class names
            annotation_group: Optional annotation group

        Returns:
            Created project or None
        """
        if workspace_id not in self.workspaces:
            return None

        project_id = name.lower().replace(" ", "-")
        project = RoboflowProject(
            project_id=project_id,
            name=name,
            project_type=project_type,
            workspace_id=workspace_id,
            classes=classes,
            annotation_group=annotation_group or project_id,
        )

        self.workspaces[workspace_id].projects[project_id] = project
        return project

    def get_project(
        self,
        workspace_id: str,
        project_id: str
    ) -> Optional[RoboflowProject]:
        """Get project by ID."""
        workspace = self.workspaces.get(workspace_id)
        if workspace:
            return workspace.projects.get(project_id)
        return None

    def upload_images(
        self,
        workspace_id: str,
        project_id: str,
        image_paths: List[str],
        annotations: Optional[Dict[str, Any]] = None,
        batch_name: Optional[str] = None,
        split: str = "train"
    ) -> Dict[str, Any]:
        """
        Upload images to project.

        Args:
            workspace_id: Workspace ID
            project_id: Project ID
            image_paths: List of image file paths
            annotations: Optional annotations dict
            batch_name: Optional batch name for grouping
            split: Dataset split (train/valid/test)

        Returns:
            Upload result with counts
        """
        project = self.get_project(workspace_id, project_id)
        if not project:
            return {"success": False, "error": "Project not found"}

        # Simulate upload
        uploaded_count = len(image_paths)
        project.image_count += uploaded_count

        return {
            "success": True,
            "uploaded": uploaded_count,
            "batch_name": batch_name or str(uuid.uuid4())[:8],
            "split": split,
            "project_image_count": project.image_count,
        }

    def generate_version(
        self,
        workspace_id: str,
        project_id: str,
        preprocessing: Optional[Dict[str, Any]] = None,
        augmentation: Optional[Dict[str, Any]] = None,
        train_split: float = 0.7,
        valid_split: float = 0.2,
        test_split: float = 0.1
    ) -> Optional[RoboflowDataset]:
        """
        Generate a new dataset version.

        Args:
            workspace_id: Workspace ID
            project_id: Project ID
            preprocessing: Preprocessing config
            augmentation: Augmentation config
            train_split: Training split ratio
            valid_split: Validation split ratio
            test_split: Test split ratio

        Returns:
            Generated dataset version
        """
        project = self.get_project(workspace_id, project_id)
        if not project:
            return None

        version_num = len(project.versions) + 1
        total_images = project.image_count

        dataset = RoboflowDataset(
            dataset_id=f"{project_id}-v{version_num}",
            version=version_num,
            name=f"{project.name} v{version_num}",
            project_id=project_id,
            image_count=total_images,
            split={
                "train": int(total_images * train_split),
                "valid": int(total_images * valid_split),
                "test": int(total_images * test_split),
            },
            preprocessing=preprocessing or {
                "resize": {"width": 640, "height": 640},
                "auto_orient": True,
            },
            augmentation=augmentation or {},
            export_formats=["yolov8", "coco", "darknet"],
        )

        project.versions.append(dataset)
        return dataset

    def export_dataset(
        self,
        workspace_id: str,
        project_id: str,
        version: int,
        format: AnnotationFormat = AnnotationFormat.YOLO,
        output_dir: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Export dataset in specified format.

        Args:
            workspace_id: Workspace ID
            project_id: Project ID
            version: Dataset version number
            format: Export format
            output_dir: Output directory path

        Returns:
            Export result with paths
        """
        project = self.get_project(workspace_id, project_id)
        if not project:
            return {"success": False, "error": "Project not found"}

        dataset = None
        for ds in project.versions:
            if ds.version == version:
                dataset = ds
                break

        if not dataset:
            return {"success": False, "error": f"Version {version} not found"}

        export_path = output_dir or f"/tmp/roboflow/{project_id}/v{version}"

        return {
            "success": True,
            "format": format.value,
            "version": version,
            "export_path": export_path,
            "files": {
                "data.yaml": f"{export_path}/data.yaml",
                "train": f"{export_path}/train/images",
                "valid": f"{export_path}/valid/images",
                "test": f"{export_path}/test/images",
            },
        }

    def start_training(
        self,
        workspace_id: str,
        project_id: str,
        version: int,
        framework: ModelFramework = ModelFramework.YOLOV8,
        epochs: int = 100,
        batch_size: int = 16,
        image_size: int = 640
    ) -> Optional[TrainingJob]:
        """
        Start model training on Roboflow.

        Args:
            workspace_id: Workspace ID
            project_id: Project ID
            version: Dataset version
            framework: Training framework
            epochs: Number of epochs
            batch_size: Batch size
            image_size: Input image size

        Returns:
            Training job object
        """
        project = self.get_project(workspace_id, project_id)
        if not project:
            return None

        job = TrainingJob(
            job_id=str(uuid.uuid4()),
            project_id=project_id,
            dataset_version=version,
            framework=framework,
            status="queued",
            epochs=epochs,
            batch_size=batch_size,
        )

        self.training_jobs[job.job_id] = job
        return job

    def get_training_status(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get training job status."""
        job = self.training_jobs.get(job_id)
        if not job:
            return None

        return {
            "job_id": job.job_id,
            "project_id": job.project_id,
            "status": job.status,
            "framework": job.framework.value,
            "epochs": job.epochs,
            "metrics": job.metrics,
            "model_id": job.model_id,
        }

    def get_model_inference_url(
        self,
        workspace_id: str,
        project_id: str,
        version: int
    ) -> Optional[str]:
        """
        Get hosted inference URL for model.

        Args:
            workspace_id: Workspace ID
            project_id: Project ID
            version: Model version

        Returns:
            Inference API URL
        """
        return f"https://detect.roboflow.com/{project_id}/{version}"

    def get_status(self) -> Dict[str, Any]:
        """Get client status."""
        return {
            "connected": self._connected,
            "api_key_set": bool(self.api_key),
            "workspace_count": len(self.workspaces),
            "total_projects": sum(
                len(w.projects) for w in self.workspaces.values()
            ),
            "active_training_jobs": len([
                j for j in self.training_jobs.values()
                if j.status in ["queued", "training"]
            ]),
        }


# Singleton instance
_roboflow_client: Optional[RoboflowClient] = None


def get_roboflow_client() -> RoboflowClient:
    """Get or create the Roboflow client instance."""
    global _roboflow_client
    if _roboflow_client is None:
        _roboflow_client = RoboflowClient()
    return _roboflow_client
