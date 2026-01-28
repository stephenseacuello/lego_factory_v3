"""
Surface Analyzer - CV-Based Surface Quality Assessment

LegoMCP World-Class Manufacturing System v5.0
Phase 13: CV-Based Quality Control

Provides surface quality analysis for finished parts:
- Surface roughness estimation
- Finish quality grading
- Cosmetic defect detection
- LEGO compatibility surface assessment
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from enum import Enum
import uuid


class SurfaceDefectType(Enum):
    """Types of surface defects detectable by CV."""
    SCRATCHES = "scratches"
    PITTING = "pitting"
    BLOBS = "blobs"
    ZITS = "zits"
    LAYER_LINES = "visible_layer_lines"
    WARPING = "surface_warping"
    DISCOLORATION = "discoloration"
    ROUGH_PATCHES = "rough_patches"
    GLOSSY_SPOTS = "uneven_gloss"


class SurfaceGrade(Enum):
    """Surface quality grades."""
    EXCELLENT = "A"
    GOOD = "B"
    ACCEPTABLE = "C"
    MARGINAL = "D"
    REJECT = "F"


@dataclass
class SurfaceRegion:
    """Analysis of a specific surface region."""
    region_id: str
    location: Tuple[float, float]  # x, y coordinates
    roughness_ra: float  # Average roughness in microns
    gloss_level: float  # 0-100 gloss units
    defects: List[SurfaceDefectType] = field(default_factory=list)
    grade: SurfaceGrade = SurfaceGrade.GOOD


@dataclass
class SurfaceAnalysisResult:
    """Complete surface analysis result."""
    analysis_id: str
    part_id: str
    work_order_id: str
    regions_analyzed: int
    overall_roughness_ra: float
    roughness_uniformity: float  # Standard deviation
    average_gloss: float
    defect_map: Dict[str, List[Tuple[float, float]]]  # defect_type -> locations
    overall_grade: SurfaceGrade
    lego_compatibility: Dict[str, bool]
    recommendations: List[str]
    timestamp: datetime = field(default_factory=datetime.utcnow)


class SurfaceAnalyzer:
    """
    Surface quality analysis using computer vision.

    Evaluates finished part surfaces for quality grading,
    defect detection, and LEGO compatibility assessment.
    """

    def __init__(self):
        self.analysis_history: Dict[str, SurfaceAnalysisResult] = {}
        self.thresholds = {
            'max_roughness_ra': 1.6,  # microns for LEGO compatibility
            'min_gloss': 40,  # gloss units
            'max_defects_per_region': 2,
            'stud_roughness_max': 0.8,  # tighter for stud surfaces
            'tube_roughness_max': 1.2,  # interference fit surfaces
        }

    def analyze_surface(
        self,
        part_id: str,
        work_order_id: str,
        image_data: Optional[bytes] = None,
        regions: int = 6
    ) -> SurfaceAnalysisResult:
        """
        Perform complete surface analysis on a part.

        Args:
            part_id: Part identifier
            work_order_id: Associated work order
            image_data: Camera image data (optional for simulation)
            regions: Number of regions to analyze

        Returns:
            Complete surface analysis result
        """
        import random

        # Analyze multiple regions
        analyzed_regions = []
        defect_map: Dict[str, List[Tuple[float, float]]] = {}

        for i in range(regions):
            region = self._analyze_region(i, regions)
            analyzed_regions.append(region)

            # Build defect map
            for defect in region.defects:
                if defect.value not in defect_map:
                    defect_map[defect.value] = []
                defect_map[defect.value].append(region.location)

        # Calculate overall metrics
        overall_roughness = sum(r.roughness_ra for r in analyzed_regions) / len(analyzed_regions)
        roughness_values = [r.roughness_ra for r in analyzed_regions]
        roughness_std = (
            sum((r - overall_roughness) ** 2 for r in roughness_values) / len(roughness_values)
        ) ** 0.5

        average_gloss = sum(r.gloss_level for r in analyzed_regions) / len(analyzed_regions)

        # Determine overall grade
        overall_grade = self._calculate_grade(analyzed_regions, overall_roughness, average_gloss)

        # Check LEGO compatibility
        lego_compat = self._check_lego_compatibility(analyzed_regions, overall_roughness)

        # Generate recommendations
        recommendations = self._generate_recommendations(
            analyzed_regions, defect_map, overall_roughness, lego_compat
        )

        result = SurfaceAnalysisResult(
            analysis_id=str(uuid.uuid4()),
            part_id=part_id,
            work_order_id=work_order_id,
            regions_analyzed=len(analyzed_regions),
            overall_roughness_ra=overall_roughness,
            roughness_uniformity=roughness_std,
            average_gloss=average_gloss,
            defect_map=defect_map,
            overall_grade=overall_grade,
            lego_compatibility=lego_compat,
            recommendations=recommendations,
        )

        self.analysis_history[result.analysis_id] = result
        return result

    def _analyze_region(self, index: int, total: int) -> SurfaceRegion:
        """Analyze a single surface region."""
        import random

        # Calculate region location (normalized 0-1)
        x = (index % 3) / 2.0
        y = (index // 3) / (total // 3)

        # Simulate CV measurements
        roughness = abs(random.gauss(1.0, 0.4))
        gloss = max(0, min(100, random.gauss(60, 15)))

        # Detect defects probabilistically
        defects = []
        if random.random() < 0.1:
            defects.append(random.choice(list(SurfaceDefectType)))
        if random.random() < 0.05:
            defects.append(SurfaceDefectType.LAYER_LINES)

        # Grade region
        if roughness < 0.8 and gloss > 50 and not defects:
            grade = SurfaceGrade.EXCELLENT
        elif roughness < 1.2 and gloss > 40 and len(defects) <= 1:
            grade = SurfaceGrade.GOOD
        elif roughness < 1.6 and len(defects) <= 2:
            grade = SurfaceGrade.ACCEPTABLE
        elif roughness < 2.0:
            grade = SurfaceGrade.MARGINAL
        else:
            grade = SurfaceGrade.REJECT

        return SurfaceRegion(
            region_id=f"R{index:02d}",
            location=(x, y),
            roughness_ra=roughness,
            gloss_level=gloss,
            defects=defects,
            grade=grade,
        )

    def _calculate_grade(
        self,
        regions: List[SurfaceRegion],
        overall_roughness: float,
        average_gloss: float
    ) -> SurfaceGrade:
        """Calculate overall surface grade."""
        # Count grades
        grade_counts = {}
        for region in regions:
            grade_counts[region.grade] = grade_counts.get(region.grade, 0) + 1

        # If any region is reject, overall is reject
        if grade_counts.get(SurfaceGrade.REJECT, 0) > 0:
            return SurfaceGrade.REJECT

        # If more than 20% marginal, overall is marginal
        if grade_counts.get(SurfaceGrade.MARGINAL, 0) / len(regions) > 0.2:
            return SurfaceGrade.MARGINAL

        # Calculate weighted score
        grade_scores = {
            SurfaceGrade.EXCELLENT: 4,
            SurfaceGrade.GOOD: 3,
            SurfaceGrade.ACCEPTABLE: 2,
            SurfaceGrade.MARGINAL: 1,
            SurfaceGrade.REJECT: 0,
        }

        total_score = sum(
            grade_scores[r.grade] for r in regions
        ) / len(regions)

        if total_score >= 3.5:
            return SurfaceGrade.EXCELLENT
        elif total_score >= 2.5:
            return SurfaceGrade.GOOD
        elif total_score >= 1.5:
            return SurfaceGrade.ACCEPTABLE
        else:
            return SurfaceGrade.MARGINAL

    def _check_lego_compatibility(
        self,
        regions: List[SurfaceRegion],
        overall_roughness: float
    ) -> Dict[str, bool]:
        """Check compatibility with LEGO brick standards."""
        return {
            'stud_surface': overall_roughness <= self.thresholds['stud_roughness_max'],
            'tube_surface': overall_roughness <= self.thresholds['tube_roughness_max'],
            'general_surface': overall_roughness <= self.thresholds['max_roughness_ra'],
            'visual_quality': all(
                r.grade in [SurfaceGrade.EXCELLENT, SurfaceGrade.GOOD, SurfaceGrade.ACCEPTABLE]
                for r in regions
            ),
            'overall_compatible': (
                overall_roughness <= self.thresholds['max_roughness_ra'] and
                all(r.grade != SurfaceGrade.REJECT for r in regions)
            ),
        }

    def _generate_recommendations(
        self,
        regions: List[SurfaceRegion],
        defect_map: Dict[str, List],
        overall_roughness: float,
        lego_compat: Dict[str, bool]
    ) -> List[str]:
        """Generate actionable recommendations."""
        recommendations = []

        if overall_roughness > self.thresholds['max_roughness_ra']:
            recommendations.append(
                f"Reduce layer height or enable ironing to achieve Ra < {self.thresholds['max_roughness_ra']}μm"
            )

        if 'visible_layer_lines' in defect_map:
            recommendations.append(
                "Consider vapor smoothing or sanding for visible layer lines"
            )

        if 'blobs' in defect_map or 'zits' in defect_map:
            recommendations.append(
                "Adjust coasting/wipe settings or reduce nozzle temperature"
            )

        if not lego_compat['stud_surface']:
            recommendations.append(
                "Stud surfaces require finer finishing - consider post-processing"
            )

        if not recommendations:
            recommendations.append("Surface quality meets all requirements")

        return recommendations

    def compare_to_golden_sample(
        self,
        analysis_id: str,
        golden_analysis_id: str
    ) -> Dict:
        """Compare analysis to a golden sample."""
        current = self.analysis_history.get(analysis_id)
        golden = self.analysis_history.get(golden_analysis_id)

        if not current or not golden:
            return {'error': 'Analysis not found'}

        return {
            'roughness_delta': current.overall_roughness_ra - golden.overall_roughness_ra,
            'gloss_delta': current.average_gloss - golden.average_gloss,
            'grade_match': current.overall_grade == golden.overall_grade,
            'defect_count_delta': (
                sum(len(v) for v in current.defect_map.values()) -
                sum(len(v) for v in golden.defect_map.values())
            ),
            'within_tolerance': abs(
                current.overall_roughness_ra - golden.overall_roughness_ra
            ) < 0.2,
        }


# Singleton instance
_surface_analyzer: Optional[SurfaceAnalyzer] = None


def get_surface_analyzer() -> SurfaceAnalyzer:
    """Get or create the surface analyzer instance."""
    global _surface_analyzer
    if _surface_analyzer is None:
        _surface_analyzer = SurfaceAnalyzer()
    return _surface_analyzer
