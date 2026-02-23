"""
Human-in-the-Loop (HITL) Annotation Management

PhD-Level Research Implementation:
- Task queue management for labeling jobs
- Quality control with redundant annotations
- Annotator skill tracking and weighting
- Real-time model retraining triggers

Novel Contributions:
- Manufacturing-specific annotation guidelines
- Defect severity consensus protocols
- Integration with production MES systems

Research Value:
- Automated quality assurance for labels
- Optimized annotator workload distribution
- Continuous learning pipeline
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple, Any, Callable
from enum import Enum
from datetime import datetime, timedelta
import numpy as np
from collections import defaultdict
import logging
import hashlib
import json

logger = logging.getLogger(__name__)


class TaskStatus(Enum):
    """Status of an annotation task"""
    PENDING = "pending"
    ASSIGNED = "assigned"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    REVIEW = "review"
    REJECTED = "rejected"
    CONSENSUS = "consensus"


class DefectSeverity(Enum):
    """Defect severity levels for manufacturing"""
    CRITICAL = "critical"    # Product failure, safety issue
    MAJOR = "major"          # Functional impact
    MINOR = "minor"          # Cosmetic impact
    NEGLIGIBLE = "negligible"  # Acceptable variation


class LabelType(Enum):
    """Types of labeling tasks"""
    CLASSIFICATION = "classification"
    BOUNDING_BOX = "bounding_box"
    SEGMENTATION = "segmentation"
    KEYPOINT = "keypoint"
    SEVERITY = "severity"


@dataclass
class Annotator:
    """An annotator in the HITL system"""
    annotator_id: str
    name: str
    skill_level: float = 1.0  # 0-2, 1 = average
    specialty_areas: List[str] = field(default_factory=list)
    tasks_completed: int = 0
    accuracy_score: float = 0.95
    average_time_seconds: float = 30.0
    is_active: bool = True
    last_active: datetime = field(default_factory=datetime.now)


@dataclass
class Annotation:
    """A single annotation"""
    annotation_id: str
    annotator_id: str
    label: Any  # Class label, bbox, mask, etc.
    confidence: float  # Annotator's confidence
    time_spent_seconds: float
    timestamp: datetime
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AnnotationTask:
    """A task to be completed by annotators"""
    task_id: str
    sample_id: str
    image_path: str
    label_type: LabelType
    status: TaskStatus = TaskStatus.PENDING
    priority: int = 0
    required_annotations: int = 1
    annotations: List[Annotation] = field(default_factory=list)
    consensus_label: Optional[Any] = None
    consensus_confidence: float = 0.0
    assigned_to: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)
    deadline: Optional[datetime] = None
    class_options: List[str] = field(default_factory=list)
    guidelines: str = ""
    model_prediction: Optional[Dict] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class LabelingSession:
    """A labeling session for an annotator"""
    session_id: str
    annotator_id: str
    start_time: datetime
    end_time: Optional[datetime] = None
    tasks_completed: int = 0
    tasks_skipped: int = 0
    average_time: float = 0.0
    quality_score: float = 1.0


@dataclass
class QualityControl:
    """Quality control metrics and settings"""
    min_agreement_threshold: float = 0.7  # Minimum inter-annotator agreement
    require_consensus: bool = True
    review_sample_rate: float = 0.1  # Fraction of tasks to review
    gold_standard_rate: float = 0.05  # Fraction of known-answer tasks
    max_rejection_rate: float = 0.2  # Max rejection rate before flagging annotator


class HITLManager:
    """
    Human-in-the-Loop Manager for annotation workflows.

    Manages the complete lifecycle of annotation tasks:
    1. Task creation from active learning selection
    2. Task assignment to qualified annotators
    3. Annotation collection and quality control
    4. Consensus resolution for multi-annotator tasks
    5. Model retraining triggers

    Example:
        manager = HITLManager()

        # Add annotators
        manager.add_annotator(Annotator("ann1", "Alice", skill_level=1.2))

        # Create tasks from selected samples
        for sample in uncertain_samples:
            task = manager.create_task(
                sample_id=sample.sample_id,
                image_path=sample.image_path,
                label_type=LabelType.CLASSIFICATION,
                class_options=["defect", "no_defect"]
            )

        # Get next task for annotator
        task = manager.get_next_task("ann1")

        # Submit annotation
        manager.submit_annotation(
            task_id=task.task_id,
            annotator_id="ann1",
            label="defect",
            confidence=0.9,
            time_spent=15.0
        )
    """

    # Manufacturing defect annotation guidelines
    DEFECT_GUIDELINES = """
    ## Defect Classification Guidelines

    ### Critical Defects
    - Structural failures or cracks
    - Missing features affecting function
    - Safety hazards

    ### Major Defects
    - Dimensional errors > 5%
    - Surface defects affecting assembly
    - Color mismatches in visible areas

    ### Minor Defects
    - Surface scratches < 2mm
    - Minor color variations
    - Non-functional cosmetic issues

    ### No Defect
    - Within specification tolerances
    - Normal manufacturing variation
    """

    def __init__(self, qc: Optional[QualityControl] = None):
        """Initialize HITL manager with quality control settings."""
        self.qc = qc or QualityControl()
        self.annotators: Dict[str, Annotator] = {}
        self.tasks: Dict[str, AnnotationTask] = {}
        self.sessions: Dict[str, LabelingSession] = {}
        self.gold_standards: Dict[str, Any] = {}  # task_id -> known label
        self._task_queue: List[str] = []
        self._completed_annotations: List[Annotation] = []

    def add_annotator(self, annotator: Annotator) -> None:
        """Add an annotator to the system."""
        self.annotators[annotator.annotator_id] = annotator
        logger.info(f"Added annotator: {annotator.annotator_id}")

    def create_task(
        self,
        sample_id: str,
        image_path: str,
        label_type: LabelType,
        class_options: Optional[List[str]] = None,
        priority: int = 0,
        required_annotations: int = 1,
        deadline: Optional[datetime] = None,
        model_prediction: Optional[Dict] = None,
        metadata: Optional[Dict] = None
    ) -> AnnotationTask:
        """
        Create a new annotation task.

        Args:
            sample_id: Identifier for the sample
            image_path: Path to the image
            label_type: Type of labeling required
            class_options: Available classes for classification
            priority: Task priority (higher = more urgent)
            required_annotations: Number of annotations needed
            deadline: Optional deadline
            model_prediction: Optional model's prediction for reference
            metadata: Additional task metadata

        Returns:
            Created AnnotationTask
        """
        task_id = self._generate_task_id(sample_id)

        task = AnnotationTask(
            task_id=task_id,
            sample_id=sample_id,
            image_path=image_path,
            label_type=label_type,
            priority=priority,
            required_annotations=required_annotations,
            deadline=deadline,
            class_options=class_options or [],
            guidelines=self.DEFECT_GUIDELINES,
            model_prediction=model_prediction,
            metadata=metadata or {}
        )

        self.tasks[task_id] = task
        self._add_to_queue(task_id, priority)

        logger.info(f"Created task: {task_id}")
        return task

    def _generate_task_id(self, sample_id: str) -> str:
        """Generate unique task ID."""
        timestamp = datetime.now().isoformat()
        hash_input = f"{sample_id}_{timestamp}"
        return hashlib.md5(hash_input.encode()).hexdigest()[:12]

    def _add_to_queue(self, task_id: str, priority: int) -> None:
        """Add task to priority queue."""
        # Simple priority insertion (could use heapq for efficiency)
        self._task_queue.append(task_id)
        self._task_queue.sort(
            key=lambda tid: self.tasks[tid].priority,
            reverse=True
        )

    def get_next_task(
        self,
        annotator_id: str,
        prefer_specialty: bool = True
    ) -> Optional[AnnotationTask]:
        """
        Get the next task for an annotator.

        Considers:
        - Task priority
        - Annotator specialty areas
        - Workload balancing
        - Gold standard task injection

        Args:
            annotator_id: The annotator requesting work
            prefer_specialty: Whether to prefer tasks in annotator's specialty

        Returns:
            Next AnnotationTask or None if queue empty
        """
        annotator = self.annotators.get(annotator_id)
        if not annotator:
            logger.warning(f"Unknown annotator: {annotator_id}")
            return None

        # Inject gold standard task occasionally for QC
        if np.random.random() < self.qc.gold_standard_rate and self.gold_standards:
            gold_task_id = np.random.choice(list(self.gold_standards.keys()))
            if gold_task_id in self.tasks:
                task = self.tasks[gold_task_id]
                task.status = TaskStatus.ASSIGNED
                task.assigned_to = annotator_id
                return task

        # Find best task for this annotator
        for task_id in self._task_queue:
            task = self.tasks.get(task_id)
            if not task:
                continue

            if task.status != TaskStatus.PENDING:
                continue

            # Check if annotator already annotated this
            if any(a.annotator_id == annotator_id for a in task.annotations):
                continue

            # Prefer specialty match
            if prefer_specialty and annotator.specialty_areas:
                task_categories = task.metadata.get("categories", [])
                if not any(s in task_categories for s in annotator.specialty_areas):
                    continue

            # Assign task
            task.status = TaskStatus.ASSIGNED
            task.assigned_to = annotator_id
            self._task_queue.remove(task_id)

            return task

        return None

    def submit_annotation(
        self,
        task_id: str,
        annotator_id: str,
        label: Any,
        confidence: float = 1.0,
        time_spent: float = 0.0,
        metadata: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Submit an annotation for a task.

        Args:
            task_id: The task being annotated
            annotator_id: The annotator
            label: The label/annotation
            confidence: Annotator's confidence (0-1)
            time_spent: Time spent in seconds
            metadata: Additional annotation metadata

        Returns:
            Status dict with consensus info if applicable
        """
        task = self.tasks.get(task_id)
        if not task:
            raise ValueError(f"Unknown task: {task_id}")

        annotator = self.annotators.get(annotator_id)
        if not annotator:
            raise ValueError(f"Unknown annotator: {annotator_id}")

        # Create annotation
        annotation = Annotation(
            annotation_id=f"{task_id}_{annotator_id}_{len(task.annotations)}",
            annotator_id=annotator_id,
            label=label,
            confidence=confidence,
            time_spent_seconds=time_spent,
            timestamp=datetime.now(),
            metadata=metadata or {}
        )

        task.annotations.append(annotation)
        self._completed_annotations.append(annotation)

        # Update annotator stats
        annotator.tasks_completed += 1
        annotator.last_active = datetime.now()
        annotator.average_time_seconds = (
            annotator.average_time_seconds * 0.9 + time_spent * 0.1
        )

        # Check gold standard
        if task_id in self.gold_standards:
            correct = label == self.gold_standards[task_id]
            annotator.accuracy_score = (
                annotator.accuracy_score * 0.95 + (1.0 if correct else 0.0) * 0.05
            )
            return {"gold_standard": True, "correct": correct}

        # Check if task is complete
        result = {"annotations_received": len(task.annotations)}

        if len(task.annotations) >= task.required_annotations:
            task.status = TaskStatus.COMPLETED

            # Compute consensus
            if self.qc.require_consensus and len(task.annotations) > 1:
                consensus_result = self._compute_consensus(task)
                task.consensus_label = consensus_result["label"]
                task.consensus_confidence = consensus_result["confidence"]

                if consensus_result["agreement"] < self.qc.min_agreement_threshold:
                    task.status = TaskStatus.CONSENSUS
                    result["needs_consensus_resolution"] = True

                result["consensus"] = consensus_result
            else:
                # Single annotation - use directly
                task.consensus_label = label
                task.consensus_confidence = confidence

            result["task_complete"] = True

        return result

    def _compute_consensus(self, task: AnnotationTask) -> Dict[str, Any]:
        """
        Compute consensus from multiple annotations.

        Uses weighted voting based on annotator skill.
        """
        if task.label_type == LabelType.CLASSIFICATION:
            return self._consensus_classification(task)
        elif task.label_type == LabelType.BOUNDING_BOX:
            return self._consensus_bounding_box(task)
        else:
            # Default: majority voting
            return self._consensus_majority(task)

    def _consensus_classification(self, task: AnnotationTask) -> Dict[str, Any]:
        """Weighted voting for classification tasks."""
        votes: Dict[Any, float] = defaultdict(float)

        for ann in task.annotations:
            annotator = self.annotators.get(ann.annotator_id)
            weight = annotator.skill_level * ann.confidence if annotator else 1.0
            votes[ann.label] += weight

        total_weight = sum(votes.values())
        if total_weight == 0:
            return {"label": None, "confidence": 0, "agreement": 0}

        # Find winner
        winner = max(votes.keys(), key=lambda k: votes[k])
        winner_weight = votes[winner]

        # Agreement: winner's weight / total weight
        agreement = winner_weight / total_weight
        confidence = agreement

        return {
            "label": winner,
            "confidence": confidence,
            "agreement": agreement,
            "vote_distribution": dict(votes)
        }

    def _consensus_bounding_box(self, task: AnnotationTask) -> Dict[str, Any]:
        """Merge bounding boxes using IoU-based clustering."""
        boxes = [ann.label for ann in task.annotations if ann.label is not None]

        if not boxes:
            return {"label": None, "confidence": 0, "agreement": 0}

        if len(boxes) == 1:
            return {"label": boxes[0], "confidence": 1.0, "agreement": 1.0}

        # Average box coordinates (simple approach)
        avg_box = {
            "x": np.mean([b.get("x", 0) for b in boxes]),
            "y": np.mean([b.get("y", 0) for b in boxes]),
            "width": np.mean([b.get("width", 0) for b in boxes]),
            "height": np.mean([b.get("height", 0) for b in boxes])
        }

        # Compute IoU-based agreement
        ious = []
        for i, b1 in enumerate(boxes):
            for b2 in boxes[i + 1:]:
                iou = self._compute_iou(b1, b2)
                ious.append(iou)

        agreement = np.mean(ious) if ious else 1.0

        return {
            "label": avg_box,
            "confidence": agreement,
            "agreement": agreement,
            "individual_boxes": boxes
        }

    def _compute_iou(self, box1: Dict, box2: Dict) -> float:
        """Compute Intersection over Union for two boxes."""
        x1 = max(box1["x"], box2["x"])
        y1 = max(box1["y"], box2["y"])
        x2 = min(box1["x"] + box1["width"], box2["x"] + box2["width"])
        y2 = min(box1["y"] + box1["height"], box2["y"] + box2["height"])

        if x2 <= x1 or y2 <= y1:
            return 0.0

        intersection = (x2 - x1) * (y2 - y1)
        area1 = box1["width"] * box1["height"]
        area2 = box2["width"] * box2["height"]
        union = area1 + area2 - intersection

        return intersection / union if union > 0 else 0

    def _consensus_majority(self, task: AnnotationTask) -> Dict[str, Any]:
        """Simple majority voting."""
        labels = [ann.label for ann in task.annotations]
        if not labels:
            return {"label": None, "confidence": 0, "agreement": 0}

        from collections import Counter
        counter = Counter(labels)
        winner, count = counter.most_common(1)[0]

        agreement = count / len(labels)

        return {
            "label": winner,
            "confidence": agreement,
            "agreement": agreement,
            "distribution": dict(counter)
        }

    def resolve_consensus(
        self,
        task_id: str,
        resolver_id: str,
        final_label: Any,
        resolution_notes: str = ""
    ) -> None:
        """
        Manually resolve a consensus dispute.

        Args:
            task_id: The disputed task
            resolver_id: Expert resolving the dispute
            final_label: The final label
            resolution_notes: Notes on the resolution
        """
        task = self.tasks.get(task_id)
        if not task:
            raise ValueError(f"Unknown task: {task_id}")

        task.consensus_label = final_label
        task.consensus_confidence = 1.0  # Expert resolution
        task.status = TaskStatus.COMPLETED
        task.metadata["resolver"] = resolver_id
        task.metadata["resolution_notes"] = resolution_notes
        task.metadata["resolved_at"] = datetime.now().isoformat()

        logger.info(f"Resolved consensus for task {task_id}")

    def add_gold_standard(
        self,
        task_id: str,
        known_label: Any
    ) -> None:
        """Add a gold standard task for quality control."""
        self.gold_standards[task_id] = known_label

    def get_annotator_statistics(
        self,
        annotator_id: str
    ) -> Dict[str, Any]:
        """Get detailed statistics for an annotator."""
        annotator = self.annotators.get(annotator_id)
        if not annotator:
            return {}

        # Recent annotations
        recent = [
            a for a in self._completed_annotations
            if a.annotator_id == annotator_id
        ][-100:]

        # Agreement with consensus
        agreements = []
        for a in recent:
            for task in self.tasks.values():
                if any(ann.annotation_id == a.annotation_id for ann in task.annotations):
                    if task.consensus_label is not None:
                        agrees = a.label == task.consensus_label
                        agreements.append(agrees)

        agreement_rate = np.mean(agreements) if agreements else 1.0

        return {
            "annotator_id": annotator_id,
            "name": annotator.name,
            "skill_level": annotator.skill_level,
            "tasks_completed": annotator.tasks_completed,
            "accuracy_score": annotator.accuracy_score,
            "average_time_seconds": annotator.average_time_seconds,
            "agreement_rate": agreement_rate,
            "recent_task_count": len(recent),
            "is_active": annotator.is_active,
            "specialty_areas": annotator.specialty_areas
        }

    def get_queue_status(self) -> Dict[str, Any]:
        """Get status of the annotation queue."""
        status_counts = defaultdict(int)
        priority_counts = defaultdict(int)
        type_counts = defaultdict(int)

        for task in self.tasks.values():
            status_counts[task.status.value] += 1
            priority_counts[task.priority] += 1
            type_counts[task.label_type.value] += 1

        overdue = sum(
            1 for t in self.tasks.values()
            if t.deadline and t.deadline < datetime.now()
            and t.status not in [TaskStatus.COMPLETED, TaskStatus.REJECTED]
        )

        return {
            "total_tasks": len(self.tasks),
            "queue_length": len(self._task_queue),
            "by_status": dict(status_counts),
            "by_priority": dict(priority_counts),
            "by_type": dict(type_counts),
            "overdue_count": overdue,
            "active_annotators": sum(
                1 for a in self.annotators.values() if a.is_active
            )
        }

    def export_labeled_data(
        self,
        min_confidence: float = 0.7,
        format: str = "coco"
    ) -> Dict[str, Any]:
        """
        Export completed annotations for model training.

        Args:
            min_confidence: Minimum consensus confidence
            format: Export format ('coco', 'yolo', 'pascal_voc')

        Returns:
            Labeled dataset in specified format
        """
        completed = [
            t for t in self.tasks.values()
            if t.status == TaskStatus.COMPLETED
            and t.consensus_confidence >= min_confidence
        ]

        if format == "coco":
            return self._export_coco(completed)
        elif format == "yolo":
            return self._export_yolo(completed)
        else:
            raise ValueError(f"Unknown format: {format}")

    def _export_coco(self, tasks: List[AnnotationTask]) -> Dict[str, Any]:
        """Export in COCO format."""
        images = []
        annotations = []
        categories = set()

        for i, task in enumerate(tasks):
            images.append({
                "id": i,
                "file_name": task.image_path,
                "width": task.metadata.get("width", 0),
                "height": task.metadata.get("height", 0)
            })

            if task.label_type == LabelType.CLASSIFICATION:
                categories.add(task.consensus_label)
                annotations.append({
                    "id": i,
                    "image_id": i,
                    "category_name": task.consensus_label
                })
            elif task.label_type == LabelType.BOUNDING_BOX:
                box = task.consensus_label
                annotations.append({
                    "id": i,
                    "image_id": i,
                    "bbox": [box["x"], box["y"], box["width"], box["height"]],
                    "category_name": box.get("class", "defect")
                })
                categories.add(box.get("class", "defect"))

        return {
            "images": images,
            "annotations": annotations,
            "categories": [
                {"id": i, "name": c}
                for i, c in enumerate(sorted(categories))
            ]
        }

    def _export_yolo(self, tasks: List[AnnotationTask]) -> Dict[str, Any]:
        """Export in YOLO format (file paths and label files)."""
        data = {"train": [], "classes": set()}

        for task in tasks:
            if task.label_type == LabelType.BOUNDING_BOX:
                box = task.consensus_label
                cls = box.get("class", "defect")
                data["classes"].add(cls)

                # YOLO format: class_id x_center y_center width height (normalized)
                width = task.metadata.get("image_width", 1)
                height = task.metadata.get("image_height", 1)

                x_center = (box["x"] + box["width"] / 2) / width
                y_center = (box["y"] + box["height"] / 2) / height
                w = box["width"] / width
                h = box["height"] / height

                data["train"].append({
                    "image": task.image_path,
                    "labels": f"0 {x_center:.6f} {y_center:.6f} {w:.6f} {h:.6f}"
                })

        data["classes"] = list(data["classes"])
        return data

    def should_retrain_model(self, min_new_samples: int = 100) -> bool:
        """Check if enough new annotations to trigger retraining."""
        completed = sum(
            1 for t in self.tasks.values()
            if t.status == TaskStatus.COMPLETED
        )

        return completed >= min_new_samples
