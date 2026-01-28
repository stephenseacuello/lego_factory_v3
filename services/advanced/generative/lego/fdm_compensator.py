"""
FDM Compensator - Compensate for FDM printing artifacts.

LEGO MCP v6.0 World-Class Manufacturing Research Platform
Phase 3: Generative Design System
"""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional
import logging

logger = logging.getLogger(__name__)


@dataclass
class FDMProfile:
    """FDM printer profile for compensation."""
    printer_name: str
    nozzle_diameter: float = 0.4  # mm
    layer_height: float = 0.2  # mm
    xy_shrinkage: float = 0.0  # % shrinkage
    z_shrinkage: float = 0.0  # %
    xy_expansion: float = 0.02  # mm (elephant foot, etc.)
    hole_shrinkage: float = 0.1  # mm (holes print smaller)
    stud_expansion: float = 0.05  # mm (studs print larger)


@dataclass
class CompensatedDimensions:
    """Compensated dimensions for printing."""
    original: Dict[str, float]
    compensated: Dict[str, float]
    adjustments: Dict[str, float]
    profile_used: str


class FDMCompensator:
    """
    Compensate LEGO brick dimensions for FDM printing artifacts.

    Common FDM issues:
    - Elephant foot (first layers expand)
    - Hole shrinkage (holes print smaller)
    - Outer dimension expansion
    - Layer line effects on fit
    """

    def __init__(self):
        self._profiles: Dict[str, FDMProfile] = {}
        self._load_default_profiles()

    def _load_default_profiles(self) -> None:
        """Load default printer profiles."""
        self._profiles['generic'] = FDMProfile(
            printer_name="Generic FDM",
            xy_shrinkage=0.0,
            xy_expansion=0.02,
            hole_shrinkage=0.1,
            stud_expansion=0.05
        )

        self._profiles['prusa_mk3s'] = FDMProfile(
            printer_name="Prusa MK3S",
            nozzle_diameter=0.4,
            xy_shrinkage=0.1,
            xy_expansion=0.015,
            hole_shrinkage=0.08,
            stud_expansion=0.04
        )

        self._profiles['ender3'] = FDMProfile(
            printer_name="Ender 3",
            nozzle_diameter=0.4,
            xy_shrinkage=0.2,
            xy_expansion=0.025,
            hole_shrinkage=0.12,
            stud_expansion=0.06
        )

        self._profiles['bambu_a1'] = FDMProfile(
            printer_name="Bambu A1",
            nozzle_diameter=0.4,
            xy_shrinkage=0.05,
            xy_expansion=0.01,
            hole_shrinkage=0.06,
            stud_expansion=0.03
        )

    def add_profile(self, profile_id: str, profile: FDMProfile) -> None:
        """Add a custom printer profile."""
        self._profiles[profile_id] = profile

    def compensate_brick(self,
                        dimensions: Dict[str, float],
                        profile_id: str = 'generic') -> CompensatedDimensions:
        """
        Compensate LEGO brick dimensions for FDM printing.

        Args:
            dimensions: Original design dimensions
                - stud_diameter
                - stud_height
                - tube_inner_diameter
                - tube_outer_diameter
                - wall_thickness
                - brick_width
                - brick_length
                - brick_height
            profile_id: Printer profile to use

        Returns:
            CompensatedDimensions with adjusted values
        """
        profile = self._profiles.get(profile_id, self._profiles['generic'])
        compensated = {}
        adjustments = {}

        for key, value in dimensions.items():
            adjustment = self._calculate_adjustment(key, value, profile)
            compensated[key] = round(value + adjustment, 3)
            adjustments[key] = round(adjustment, 3)

        logger.info(f"Compensated dimensions using profile '{profile_id}'")

        return CompensatedDimensions(
            original=dimensions,
            compensated=compensated,
            adjustments=adjustments,
            profile_used=profile.printer_name
        )

    def _calculate_adjustment(self,
                             dimension_name: str,
                             value: float,
                             profile: FDMProfile) -> float:
        """Calculate adjustment for a specific dimension."""
        # Stud diameter: reduce to compensate for expansion
        if 'stud_diameter' in dimension_name:
            return -profile.stud_expansion

        # Tube inner diameter: increase to compensate for shrinkage
        if 'tube_inner' in dimension_name or 'hole' in dimension_name:
            return profile.hole_shrinkage

        # Outer dimensions: reduce slightly
        if any(x in dimension_name for x in ['width', 'length', 'outer']):
            return -profile.xy_expansion

        # Height dimensions: usually OK but can adjust for z shrinkage
        if 'height' in dimension_name:
            return value * profile.z_shrinkage / 100

        return 0.0

    def calibration_test(self, profile_id: str) -> Dict[str, Any]:
        """
        Generate calibration test print dimensions.

        Print these test pieces and measure to refine profile.
        """
        profile = self._profiles.get(profile_id, self._profiles['generic'])

        # Test pieces at nominal dimensions
        test_dimensions = {
            'stud_test': {
                'stud_diameter': 4.8,
                'stud_height': 1.7,
                'description': 'Single stud for diameter measurement'
            },
            'tube_test': {
                'tube_inner_diameter': 4.8,
                'tube_outer_diameter': 6.51,
                'description': 'Single tube for ID/OD measurement'
            },
            'fit_test': {
                'description': 'Stud-tube fit test piece'
            },
            'wall_test': {
                'wall_thickness': 1.5,
                'description': 'Wall thickness test'
            }
        }

        return {
            'profile': profile_id,
            'printer': profile.printer_name,
            'test_pieces': test_dimensions,
            'instructions': [
                "1. Print all test pieces at 100% scale",
                "2. Measure each dimension with calipers",
                "3. Record deviation from nominal",
                "4. Update profile compensation values",
                "5. Test clutch fit with official LEGO brick"
            ]
        }

    def optimize_profile(self,
                        profile_id: str,
                        measurements: Dict[str, Dict[str, float]]) -> FDMProfile:
        """
        Optimize profile based on calibration measurements.

        Args:
            profile_id: Profile to optimize
            measurements: Measured values for test pieces
                {
                    'stud_test': {'stud_diameter': 4.85},  # measured
                    'tube_test': {'tube_inner_diameter': 4.72},
                    ...
                }

        Returns:
            Updated FDMProfile
        """
        profile = self._profiles.get(profile_id, self._profiles['generic'])

        # Calculate deviations from nominal
        if 'stud_test' in measurements:
            measured = measurements['stud_test'].get('stud_diameter', 4.8)
            profile.stud_expansion = measured - 4.8

        if 'tube_test' in measurements:
            measured = measurements['tube_test'].get('tube_inner_diameter', 4.8)
            profile.hole_shrinkage = 4.8 - measured

        logger.info(f"Optimized profile {profile_id}: "
                   f"stud_exp={profile.stud_expansion}, "
                   f"hole_shrink={profile.hole_shrinkage}")

        return profile

    def get_available_profiles(self) -> List[str]:
        """Get list of available profile IDs."""
        return list(self._profiles.keys())

    def get_profile(self, profile_id: str) -> Optional[FDMProfile]:
        """Get profile by ID."""
        return self._profiles.get(profile_id)
