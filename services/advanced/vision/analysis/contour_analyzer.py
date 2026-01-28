"""
Contour Analysis - Shape Detection and Classification

LegoMCP World-Class Manufacturing System v6.0
Phase 26: Vision AI & ML Training

Provides contour analysis:
- Shape detection
- Geometric feature extraction
- LEGO brick shape matching
- Defect boundary detection
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple
from enum import Enum
import math


class ShapeClassification(Enum):
    """Shape classifications."""
    RECTANGLE = "rectangle"
    SQUARE = "square"
    CIRCLE = "circle"
    ELLIPSE = "ellipse"
    TRIANGLE = "triangle"
    POLYGON = "polygon"
    IRREGULAR = "irregular"
    LEGO_BRICK = "lego_brick"
    LEGO_STUD = "lego_stud"


class ContourType(Enum):
    """Contour type."""
    EXTERNAL = "external"
    INTERNAL = "internal"  # Holes


@dataclass
class ContourFeatures:
    """Geometric features of a contour."""
    contour_id: str
    area: float
    perimeter: float
    centroid: Tuple[float, float]
    bounding_box: Tuple[int, int, int, int]  # x, y, w, h
    min_enclosing_circle: Tuple[Tuple[float, float], float]  # center, radius
    aspect_ratio: float
    extent: float  # Object area / bounding box area
    solidity: float  # Object area / convex hull area
    circularity: float  # 4*pi*area / perimeter^2
    rectangularity: float  # How rectangular the shape is
    orientation_degrees: float
    convex_hull_vertices: int
    moments: Dict[str, float]
    hu_moments: List[float]
    contour_type: ContourType = ContourType.EXTERNAL
    shape: ShapeClassification = ShapeClassification.IRREGULAR
    confidence: float = 0.0


@dataclass
class ContourAnalysisResult:
    """Complete contour analysis result."""
    image_id: str
    total_contours: int
    external_contours: int
    internal_contours: int
    contours: List[ContourFeatures]
    shape_distribution: Dict[str, int]
    avg_area: float
    total_area: float
    coverage_percent: float
    processing_time_ms: float
    timestamp: datetime = field(default_factory=datetime.utcnow)


class ContourAnalyzer:
    """
    Contour detection and analysis.

    Provides shape detection and classification
    optimized for LEGO brick and 3D print analysis.
    """

    def __init__(
        self,
        min_area: float = 100.0,
        max_area: Optional[float] = None,
        approximate_epsilon: float = 0.02
    ):
        """
        Initialize contour analyzer.

        Args:
            min_area: Minimum contour area to consider
            max_area: Maximum contour area (None for no limit)
            approximate_epsilon: Contour approximation epsilon
        """
        self.min_area = min_area
        self.max_area = max_area
        self.approximate_epsilon = approximate_epsilon

        # LEGO brick aspect ratios for matching
        self._lego_aspect_ratios = {
            "2x4": 2.0,
            "2x2": 1.0,
            "1x4": 4.0,
            "1x2": 2.0,
            "1x1": 1.0,
        }

    def analyze(
        self,
        image: Any,
        mode: str = "external"
    ) -> ContourAnalysisResult:
        """
        Analyze contours in image.

        Args:
            image: Input image (numpy array)
            mode: "external" for outer contours, "all" for all

        Returns:
            Contour analysis result
        """
        import time
        start_time = time.time()

        # Detect contours (simulated)
        contours = self._detect_contours(image, mode)

        # Analyze each contour
        analyzed = []
        for contour in contours:
            features = self._extract_features(contour)
            features.shape = self._classify_shape(features)
            analyzed.append(features)

        # Filter by area
        analyzed = [
            c for c in analyzed
            if c.area >= self.min_area and
            (self.max_area is None or c.area <= self.max_area)
        ]

        # Calculate statistics
        total_area = sum(c.area for c in analyzed)
        avg_area = total_area / len(analyzed) if analyzed else 0

        # Assume 640x640 image
        image_area = 640 * 640
        coverage = total_area / image_area * 100

        # Shape distribution
        shape_dist = {}
        for c in analyzed:
            shape_name = c.shape.value
            shape_dist[shape_name] = shape_dist.get(shape_name, 0) + 1

        external = sum(1 for c in analyzed if c.contour_type == ContourType.EXTERNAL)
        internal = len(analyzed) - external

        processing_time = (time.time() - start_time) * 1000

        return ContourAnalysisResult(
            image_id=str(id(image)),
            total_contours=len(analyzed),
            external_contours=external,
            internal_contours=internal,
            contours=analyzed,
            shape_distribution=shape_dist,
            avg_area=avg_area,
            total_area=total_area,
            coverage_percent=coverage,
            processing_time_ms=processing_time,
        )

    def _detect_contours(
        self,
        image: Any,
        mode: str
    ) -> List[Any]:
        """Detect contours in image."""
        # Simulated contour detection
        # Real implementation:
        # gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        # _, thresh = cv2.threshold(gray, 127, 255, cv2.THRESH_BINARY)
        # contours, hierarchy = cv2.findContours(
        #     thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        # )

        import random
        num_contours = random.randint(10, 50)
        return list(range(num_contours))  # Placeholder

    def _extract_features(self, contour: Any) -> ContourFeatures:
        """Extract geometric features from contour."""
        import random
        import uuid

        # Simulated feature extraction
        # Real implementation uses cv2.moments, cv2.contourArea, etc.

        area = random.uniform(500, 50000)
        perimeter = random.uniform(100, 1000)

        # Bounding box
        x = random.randint(0, 500)
        y = random.randint(0, 500)
        w = random.randint(20, 140)
        h = random.randint(20, 140)

        # Aspect ratio
        aspect_ratio = max(w, h) / min(w, h) if min(w, h) > 0 else 1

        # Extent (object area / bounding box area)
        bbox_area = w * h
        extent = area / bbox_area if bbox_area > 0 else 0

        # Circularity
        circularity = 4 * math.pi * area / (perimeter ** 2) if perimeter > 0 else 0

        # Solidity (assume convex hull is 10-20% larger than contour)
        solidity = random.uniform(0.7, 0.95)

        # Rectangularity
        rectangularity = min(1.0, area / bbox_area) if bbox_area > 0 else 0

        # Orientation
        orientation = random.uniform(-90, 90)

        # Centroid
        cx = x + w / 2
        cy = y + h / 2

        # Moments (simplified)
        moments = {
            "m00": area,
            "m10": area * cx,
            "m01": area * cy,
            "mu20": random.uniform(1000, 10000),
            "mu11": random.uniform(-1000, 1000),
            "mu02": random.uniform(1000, 10000),
        }

        # Hu moments
        hu_moments = [random.uniform(-10, 0) for _ in range(7)]

        # Contour type
        contour_type = (
            ContourType.EXTERNAL
            if random.random() > 0.2
            else ContourType.INTERNAL
        )

        return ContourFeatures(
            contour_id=str(uuid.uuid4())[:8],
            area=area,
            perimeter=perimeter,
            centroid=(cx, cy),
            bounding_box=(x, y, w, h),
            min_enclosing_circle=((cx, cy), max(w, h) / 2),
            aspect_ratio=aspect_ratio,
            extent=extent,
            solidity=solidity,
            circularity=circularity,
            rectangularity=rectangularity,
            orientation_degrees=orientation,
            convex_hull_vertices=random.randint(4, 20),
            moments=moments,
            hu_moments=hu_moments,
            contour_type=contour_type,
        )

    def _classify_shape(self, features: ContourFeatures) -> ShapeClassification:
        """Classify shape based on features."""
        circularity = features.circularity
        aspect_ratio = features.aspect_ratio
        solidity = features.solidity
        rectangularity = features.rectangularity
        vertices = features.convex_hull_vertices

        # Confidence score
        confidence = 0.0

        # Circle detection
        if circularity > 0.85 and aspect_ratio < 1.2:
            features.confidence = min(1.0, circularity)
            # Check for LEGO stud (small circle)
            if features.area < 2000:
                return ShapeClassification.LEGO_STUD
            return ShapeClassification.CIRCLE

        # Ellipse
        if circularity > 0.7 and aspect_ratio > 1.3:
            features.confidence = circularity
            return ShapeClassification.ELLIPSE

        # Rectangle/Square
        if rectangularity > 0.85 and solidity > 0.9:
            features.confidence = rectangularity * solidity

            # Check for LEGO brick
            if self._is_lego_brick(features):
                return ShapeClassification.LEGO_BRICK

            if aspect_ratio < 1.1:
                return ShapeClassification.SQUARE
            return ShapeClassification.RECTANGLE

        # Triangle
        if vertices == 3:
            features.confidence = 0.9
            return ShapeClassification.TRIANGLE

        # Polygon
        if vertices >= 4 and vertices <= 8 and solidity > 0.8:
            features.confidence = 0.7
            return ShapeClassification.POLYGON

        # Irregular
        features.confidence = 0.5
        return ShapeClassification.IRREGULAR

    def _is_lego_brick(self, features: ContourFeatures) -> bool:
        """Check if contour matches LEGO brick dimensions."""
        aspect_ratio = features.aspect_ratio

        # Check against known LEGO aspect ratios
        for brick_type, ratio in self._lego_aspect_ratios.items():
            tolerance = 0.2
            if abs(aspect_ratio - ratio) < tolerance:
                return True

        return False

    def match_template(
        self,
        contour_features: ContourFeatures,
        template_features: ContourFeatures,
        method: str = "hu_moments"
    ) -> float:
        """
        Match contour to template.

        Args:
            contour_features: Features of contour to match
            template_features: Features of template
            method: Matching method (hu_moments, shape, geometric)

        Returns:
            Similarity score (0-1)
        """
        if method == "hu_moments":
            # Compare Hu moments
            return self._compare_hu_moments(
                contour_features.hu_moments,
                template_features.hu_moments
            )
        elif method == "geometric":
            # Compare geometric features
            return self._compare_geometric(contour_features, template_features)
        else:
            return 0.0

    def _compare_hu_moments(
        self,
        moments1: List[float],
        moments2: List[float]
    ) -> float:
        """Compare Hu moments for shape matching."""
        if len(moments1) != len(moments2):
            return 0.0

        # Euclidean distance between log-transformed moments
        distance = 0.0
        for m1, m2 in zip(moments1, moments2):
            if m1 != 0 and m2 != 0:
                d = abs(math.log(abs(m1)) - math.log(abs(m2)))
                distance += d

        # Convert to similarity (closer = higher score)
        similarity = 1.0 / (1.0 + distance)
        return similarity

    def _compare_geometric(
        self,
        f1: ContourFeatures,
        f2: ContourFeatures
    ) -> float:
        """Compare geometric features."""
        # Compare key features
        aspect_diff = abs(f1.aspect_ratio - f2.aspect_ratio)
        circularity_diff = abs(f1.circularity - f2.circularity)
        solidity_diff = abs(f1.solidity - f2.solidity)

        # Weighted average
        total_diff = (
            aspect_diff * 0.3 +
            circularity_diff * 0.4 +
            solidity_diff * 0.3
        )

        similarity = max(0, 1.0 - total_diff)
        return similarity

    def find_lego_bricks(
        self,
        result: ContourAnalysisResult
    ) -> List[ContourFeatures]:
        """Find LEGO brick contours in analysis result."""
        bricks = [
            c for c in result.contours
            if c.shape == ShapeClassification.LEGO_BRICK
        ]
        return bricks

    def find_defects(
        self,
        result: ContourAnalysisResult,
        min_irregularity: float = 0.3
    ) -> List[ContourFeatures]:
        """Find potential defect contours."""
        defects = [
            c for c in result.contours
            if (c.shape == ShapeClassification.IRREGULAR or
                c.solidity < 0.7 or
                c.circularity < 0.3)
        ]
        return defects

    def get_status(self) -> Dict[str, Any]:
        """Get analyzer status."""
        return {
            "min_area": self.min_area,
            "max_area": self.max_area,
            "approximate_epsilon": self.approximate_epsilon,
            "lego_aspect_ratios": self._lego_aspect_ratios,
        }


# Singleton instance
_contour_analyzer: Optional[ContourAnalyzer] = None


def get_contour_analyzer() -> ContourAnalyzer:
    """Get or create the contour analyzer instance."""
    global _contour_analyzer
    if _contour_analyzer is None:
        _contour_analyzer = ContourAnalyzer()
    return _contour_analyzer
