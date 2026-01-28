"""
Drilling Templates for G-code generation.

Provides templates for:
- Spot drilling
- Standard drilling
- Peck drilling (G83)
- Tapping
"""

from dataclasses import dataclass
from typing import List, Optional
from datetime import datetime


@dataclass
class DrillHole:
    """Definition of a hole to drill."""
    x: float
    y: float
    depth: float
    diameter: Optional[float] = None


@dataclass
class DrillParameters:
    """Drilling parameters."""
    tool_number: int = 1
    spindle_speed: int = 3000
    feed_rate: float = 10.0
    safe_z: float = 0.1
    retract_z: float = 0.05
    peck_depth: Optional[float] = None
    dwell_seconds: float = 0.0


class DrillingTemplates:
    """Templates for drilling operations."""

    @staticmethod
    def spot_drill(
        holes: List[DrillHole],
        params: DrillParameters,
        spot_depth: float = 0.03,
    ) -> str:
        """Generate spot drilling G-code."""
        lines = [
            f"( Spot Drilling Operation )",
            f"( Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')} )",
            f"( Holes: {len(holes)} )",
            "",
            "G90 G94 G17",
            "G54",
            "",
            f"T{params.tool_number} M6 ( Spot drill )",
            f"S{params.spindle_speed} M3",
            "G4 P2.0",
            "M8",
            "",
            f"G0 Z{params.safe_z}",
        ]

        for i, hole in enumerate(holes):
            lines.extend([
                "",
                f"( Hole {i+1} )",
                f"G0 X{hole.x:.4f} Y{hole.y:.4f}",
                f"G0 Z{params.retract_z}",
                f"G1 Z{-spot_depth:.4f} F{params.feed_rate}",
                f"G0 Z{params.safe_z}",
            ])

        lines.extend([
            "",
            "M9",
            "M5",
            "G0 X0 Y0",
            "M30",
        ])

        return "\n".join(lines)

    @staticmethod
    def drill_simple(
        holes: List[DrillHole],
        params: DrillParameters,
    ) -> str:
        """Generate simple drilling G-code (G81-style)."""
        lines = [
            f"( Simple Drilling Operation )",
            f"( Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')} )",
            f"( Holes: {len(holes)} )",
            "",
            "G90 G94 G17",
            "G54",
            "",
            f"T{params.tool_number} M6",
            f"S{params.spindle_speed} M3",
            "G4 P2.0",
            "M8",
            "",
            f"G0 Z{params.safe_z}",
        ]

        for i, hole in enumerate(holes):
            lines.extend([
                "",
                f"( Hole {i+1} - Depth: {hole.depth}\" )",
                f"G0 X{hole.x:.4f} Y{hole.y:.4f}",
                f"G81 Z{-hole.depth:.4f} R{params.retract_z} F{params.feed_rate}",
            ])

        lines.extend([
            "",
            "G80 ( Cancel canned cycle )",
            "M9",
            "M5",
            f"G0 Z{params.safe_z}",
            "G0 X0 Y0",
            "M30",
        ])

        return "\n".join(lines)

    @staticmethod
    def peck_drill(
        holes: List[DrillHole],
        params: DrillParameters,
    ) -> str:
        """Generate peck drilling G-code (G83)."""
        peck = params.peck_depth or 0.1

        lines = [
            f"( Peck Drilling Operation )",
            f"( Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')} )",
            f"( Holes: {len(holes)}, Peck: {peck}\" )",
            "",
            "G90 G94 G17",
            "G54",
            "",
            f"T{params.tool_number} M6",
            f"S{params.spindle_speed} M3",
            "G4 P2.0",
            "M8",
            "",
            f"G0 Z{params.safe_z}",
        ]

        for i, hole in enumerate(holes):
            lines.extend([
                "",
                f"( Hole {i+1} - Depth: {hole.depth}\" )",
                f"G0 X{hole.x:.4f} Y{hole.y:.4f}",
                f"G83 Z{-hole.depth:.4f} R{params.retract_z} Q{peck:.4f} F{params.feed_rate}",
            ])

        lines.extend([
            "",
            "G80",
            "M9",
            "M5",
            f"G0 Z{params.safe_z}",
            "G0 X0 Y0",
            "M30",
        ])

        return "\n".join(lines)

    @staticmethod
    def tapping(
        holes: List[DrillHole],
        params: DrillParameters,
        thread_pitch: float = 0.05,  # Pitch in inches (20 TPI = 0.05)
        right_hand: bool = True,
    ) -> str:
        """Generate rigid tapping G-code (G84)."""
        direction = "M3" if right_hand else "M4"

        # Calculate feed rate from pitch and RPM
        # Feed = RPM * Pitch
        tap_feed = params.spindle_speed * thread_pitch

        lines = [
            f"( Tapping Operation )",
            f"( Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')} )",
            f"( Holes: {len(holes)}, Pitch: {thread_pitch}\" )",
            "",
            "G90 G94 G17",
            "G54",
            "",
            f"T{params.tool_number} M6 ( Tap )",
            f"S{params.spindle_speed} {direction}",
            "G4 P2.0",
            "M8",
            "",
            f"G0 Z{params.safe_z}",
        ]

        for i, hole in enumerate(holes):
            lines.extend([
                "",
                f"( Hole {i+1} )",
                f"G0 X{hole.x:.4f} Y{hole.y:.4f}",
                f"G84 Z{-hole.depth:.4f} R{params.retract_z} F{tap_feed:.2f}",
            ])

        lines.extend([
            "",
            "G80",
            "M9",
            "M5",
            f"G0 Z{params.safe_z}",
            "G0 X0 Y0",
            "M30",
        ])

        return "\n".join(lines)

    @staticmethod
    def helical_interpolate(
        holes: List[DrillHole],
        params: DrillParameters,
        tool_diameter: float = 0.25,
        helix_pitch: float = 0.02,
    ) -> str:
        """Generate helical interpolation for hole making."""
        lines = [
            f"( Helical Hole Interpolation )",
            f"( Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')} )",
            f"( Holes: {len(holes)}, Tool: {tool_diameter}\" )",
            "",
            "G90 G94 G17",
            "G54",
            "",
            f"T{params.tool_number} M6",
            f"S{params.spindle_speed} M3",
            "G4 P2.0",
            "M8",
            "",
            f"G0 Z{params.safe_z}",
        ]

        for i, hole in enumerate(holes):
            hole_radius = (hole.diameter or 0.25) / 2
            helix_radius = hole_radius - tool_diameter / 2

            if helix_radius <= 0:
                lines.append(f"( Hole {i+1} - SKIPPED: hole too small for tool )")
                continue

            # Calculate number of helix passes
            passes = int(hole.depth / helix_pitch)

            lines.extend([
                "",
                f"( Hole {i+1} - {hole.diameter}\" diameter )",
                f"G0 X{hole.x + helix_radius:.4f} Y{hole.y:.4f}",
                f"G0 Z{params.retract_z}",
            ])

            # Helix entry
            current_z = 0
            for p in range(passes):
                current_z -= helix_pitch
                lines.append(
                    f"G2 X{hole.x + helix_radius:.4f} Y{hole.y:.4f} "
                    f"I{-helix_radius:.4f} J0 Z{current_z:.4f} F{params.feed_rate}"
                )

            # Final circle at depth
            lines.append(
                f"G2 X{hole.x + helix_radius:.4f} Y{hole.y:.4f} "
                f"I{-helix_radius:.4f} J0 F{params.feed_rate}"
            )

            lines.append(f"G0 Z{params.safe_z}")

        lines.extend([
            "",
            "M9",
            "M5",
            "G0 X0 Y0",
            "M30",
        ])

        return "\n".join(lines)
