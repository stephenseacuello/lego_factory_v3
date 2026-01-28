"""
Profiling Templates for G-code generation.

Provides templates for:
- Rectangular profiles
- Circular profiles
- Profile with holding tabs
"""

import math
from dataclasses import dataclass
from typing import List, Optional, Tuple
from datetime import datetime


@dataclass
class ProfileParameters:
    """Profiling parameters."""
    tool_number: int = 1
    tool_diameter: float = 0.25
    spindle_speed: int = 10000
    feed_rate: float = 30.0
    plunge_rate: float = 10.0
    safe_z: float = 0.1
    step_down: float = 0.1
    stock_to_leave: float = 0.0  # For finishing passes
    climb_milling: bool = True
    outside_profile: bool = True  # False for inside/hole


@dataclass
class Tab:
    """Holding tab definition."""
    position: float  # Position along perimeter (0-1)
    width: float = 0.25
    height: float = 0.05


class ProfilingTemplates:
    """Templates for profiling operations."""

    @staticmethod
    def _calculate_offset_points(
        points: List[Tuple[float, float]],
        offset_distance: float,
        outside_profile: bool,
        climb_milling: bool,
    ) -> List[Tuple[float, float]]:
        """
        Calculate offset points for tool compensation.

        Args:
            points: Original profile points
            offset_distance: Distance to offset (tool radius + stock to leave)
            outside_profile: True for outside profile, False for inside/pocket
            climb_milling: True for climb milling, False for conventional

        Returns:
            List of offset points
        """
        if len(points) < 2:
            return points

        offset_points = []

        # Determine offset direction
        # For outside profile with climb milling: offset left of travel
        # For inside profile with climb milling: offset right of travel
        # Conventional milling reverses the direction
        offset_sign = 1.0 if outside_profile else -1.0
        if not climb_milling:
            offset_sign *= -1.0

        for i in range(len(points)):
            # Get previous and next points for calculating normal
            prev_idx = (i - 1) % len(points)
            next_idx = (i + 1) % len(points)

            p_prev = points[prev_idx]
            p_curr = points[i]
            p_next = points[next_idx]

            # Calculate vectors
            v1 = (p_curr[0] - p_prev[0], p_curr[1] - p_prev[1])
            v2 = (p_next[0] - p_curr[0], p_next[1] - p_curr[1])

            # Normalize vectors
            len1 = math.sqrt(v1[0]**2 + v1[1]**2)
            len2 = math.sqrt(v2[0]**2 + v2[1]**2)

            if len1 > 0:
                v1 = (v1[0] / len1, v1[1] / len1)
            if len2 > 0:
                v2 = (v2[0] / len2, v2[1] / len2)

            # Calculate normals (perpendicular, pointing left of travel)
            n1 = (-v1[1], v1[0])
            n2 = (-v2[1], v2[0])

            # Average normal for corner bisector
            avg_normal = (n1[0] + n2[0], n1[1] + n2[1])
            avg_len = math.sqrt(avg_normal[0]**2 + avg_normal[1]**2)

            if avg_len > 0:
                avg_normal = (avg_normal[0] / avg_len, avg_normal[1] / avg_len)
            else:
                avg_normal = n1

            # Calculate offset point
            offset_x = p_curr[0] + offset_sign * offset_distance * avg_normal[0]
            offset_y = p_curr[1] + offset_sign * offset_distance * avg_normal[1]

            offset_points.append((offset_x, offset_y))

        return offset_points

    @staticmethod
    def rectangular_profile(
        center_x: float,
        center_y: float,
        width: float,
        length: float,
        depth: float,
        params: ProfileParameters,
        corner_radius: Optional[float] = None,
        tabs: Optional[List[Tab]] = None,
    ) -> str:
        """
        Generate rectangular profile G-code.

        Cuts around a rectangle with optional corner radii and tabs.
        """
        tool_rad = params.tool_diameter / 2

        # Calculate offset direction
        if params.outside_profile:
            offset = tool_rad + params.stock_to_leave
        else:
            offset = -(tool_rad + params.stock_to_leave)

        # Profile corners
        x1 = center_x - width / 2 - offset
        x2 = center_x + width / 2 + offset
        y1 = center_y - length / 2 - offset
        y2 = center_y + length / 2 + offset

        corner_rad = corner_radius or 0

        # Number of depth passes
        num_passes = math.ceil(depth / params.step_down)
        actual_step = depth / num_passes

        lines = [
            f"( {'Outside' if params.outside_profile else 'Inside'} Profile )",
            f"( Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')} )",
            f"( Size: {width}\" x {length}\" x {depth}\" deep )",
            f"( Tool: {params.tool_diameter}\" end mill )",
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

        # Lead-in point (away from corner)
        lead_in_x = x1 - 0.1 if params.outside_profile else x1 + 0.1
        lead_in_y = y1

        current_z = 0

        for pass_num in range(num_passes):
            current_z -= actual_step
            tab_z = current_z + (tabs[0].height if tabs else 0)

            lines.extend([
                "",
                f"( Pass {pass_num + 1}/{num_passes} at Z{current_z:.4f} )",
                f"G0 X{lead_in_x:.4f} Y{lead_in_y:.4f}",
                f"G0 Z0.05",
            ])

            # Ramp or plunge entry
            lines.append(f"G1 Z{current_z:.4f} F{params.plunge_rate}")

            # Lead-in arc
            if params.outside_profile:
                lines.append(f"G2 X{x1:.4f} Y{y1:.4f} R0.1 F{params.feed_rate}")
            else:
                lines.append(f"G3 X{x1:.4f} Y{y1:.4f} R0.1 F{params.feed_rate}")

            # Profile path (CCW for outside climb, CW for inside climb)
            if corner_rad > 0:
                if params.climb_milling == params.outside_profile:
                    # CCW
                    lines.extend([
                        f"G1 X{x2 - corner_rad:.4f} F{params.feed_rate}",
                        f"G3 X{x2:.4f} Y{y1 + corner_rad:.4f} R{corner_rad:.4f}",
                        f"G1 Y{y2 - corner_rad:.4f}",
                        f"G3 X{x2 - corner_rad:.4f} Y{y2:.4f} R{corner_rad:.4f}",
                        f"G1 X{x1 + corner_rad:.4f}",
                        f"G3 X{x1:.4f} Y{y2 - corner_rad:.4f} R{corner_rad:.4f}",
                        f"G1 Y{y1 + corner_rad:.4f}",
                        f"G3 X{x1 + corner_rad:.4f} Y{y1:.4f} R{corner_rad:.4f}",
                        f"G1 X{x2 - corner_rad:.4f}",
                    ])
                else:
                    # CW
                    lines.extend([
                        f"G1 Y{y2 - corner_rad:.4f} F{params.feed_rate}",
                        f"G2 X{x1 + corner_rad:.4f} Y{y2:.4f} R{corner_rad:.4f}",
                        f"G1 X{x2 - corner_rad:.4f}",
                        f"G2 X{x2:.4f} Y{y2 - corner_rad:.4f} R{corner_rad:.4f}",
                        f"G1 Y{y1 + corner_rad:.4f}",
                        f"G2 X{x2 - corner_rad:.4f} Y{y1:.4f} R{corner_rad:.4f}",
                        f"G1 X{x1 + corner_rad:.4f}",
                        f"G2 X{x1:.4f} Y{y1 + corner_rad:.4f} R{corner_rad:.4f}",
                    ])
            else:
                # Sharp corners
                if params.climb_milling == params.outside_profile:
                    lines.extend([
                        f"G1 X{x2:.4f} F{params.feed_rate}",
                        f"G1 Y{y2:.4f}",
                        f"G1 X{x1:.4f}",
                        f"G1 Y{y1:.4f}",
                    ])
                else:
                    lines.extend([
                        f"G1 Y{y2:.4f} F{params.feed_rate}",
                        f"G1 X{x2:.4f}",
                        f"G1 Y{y1:.4f}",
                        f"G1 X{x1:.4f}",
                    ])

            # Lead-out
            if params.outside_profile:
                lines.append(f"G2 X{lead_in_x:.4f} Y{lead_in_y:.4f} R0.1")
            else:
                lines.append(f"G3 X{lead_in_x:.4f} Y{lead_in_y:.4f} R0.1")

        lines.extend([
            "",
            f"G0 Z{params.safe_z}",
            "M9",
            "M5",
            "G0 X0 Y0",
            "M30",
        ])

        return "\n".join(lines)

    @staticmethod
    def circular_profile(
        center_x: float,
        center_y: float,
        diameter: float,
        depth: float,
        params: ProfileParameters,
        tabs: Optional[List[Tab]] = None,
    ) -> str:
        """
        Generate circular profile G-code.

        Cuts around a circle with optional tabs.
        """
        tool_rad = params.tool_diameter / 2
        radius = diameter / 2

        # Calculate offset direction
        if params.outside_profile:
            cut_radius = radius + tool_rad + params.stock_to_leave
        else:
            cut_radius = radius - tool_rad - params.stock_to_leave

        if cut_radius <= 0:
            return "( ERROR: Profile too small for tool )\nM30\n"

        # Number of depth passes
        num_passes = math.ceil(depth / params.step_down)
        actual_step = depth / num_passes

        lines = [
            f"( Circular {'Outside' if params.outside_profile else 'Inside'} Profile )",
            f"( Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')} )",
            f"( Diameter: {diameter}\", Depth: {depth}\" )",
            f"( Tool: {params.tool_diameter}\" end mill )",
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

        # Start point with lead-in
        lead_in_radius = cut_radius + 0.1 if params.outside_profile else cut_radius - 0.1
        start_x = center_x + lead_in_radius
        start_y = center_y

        current_z = 0

        for pass_num in range(num_passes):
            current_z -= actual_step

            lines.extend([
                "",
                f"( Pass {pass_num + 1}/{num_passes} at Z{current_z:.4f} )",
                f"G0 X{start_x:.4f} Y{start_y:.4f}",
                f"G0 Z0.05",
                f"G1 Z{current_z:.4f} F{params.plunge_rate}",
            ])

            # Lead-in arc
            arc_code = "G2" if (params.climb_milling == params.outside_profile) else "G3"
            lines.append(
                f"{arc_code} X{center_x + cut_radius:.4f} Y{center_y:.4f} "
                f"R0.1 F{params.feed_rate}"
            )

            # Full circle
            if params.climb_milling == params.outside_profile:
                # CCW for outside climb
                lines.append(
                    f"G3 X{center_x + cut_radius:.4f} Y{center_y:.4f} "
                    f"I{-cut_radius:.4f} J0"
                )
            else:
                # CW for inside climb or outside conventional
                lines.append(
                    f"G2 X{center_x + cut_radius:.4f} Y{center_y:.4f} "
                    f"I{-cut_radius:.4f} J0"
                )

            # Lead-out arc
            lines.append(
                f"{arc_code} X{start_x:.4f} Y{start_y:.4f} R0.1"
            )

        lines.extend([
            "",
            f"G0 Z{params.safe_z}",
            "M9",
            "M5",
            "G0 X0 Y0",
            "M30",
        ])

        return "\n".join(lines)

    @staticmethod
    def contour_from_points(
        points: List[Tuple[float, float]],
        depth: float,
        params: ProfileParameters,
        closed: bool = True,
    ) -> str:
        """
        Generate contour profile from a list of points.

        Args:
            points: List of (x, y) coordinates
            depth: Cutting depth
            params: Profile parameters
            closed: Whether to close the contour back to start
        """
        if len(points) < 2:
            return "( ERROR: Need at least 2 points )\nM30\n"

        tool_rad = params.tool_diameter / 2

        # Number of depth passes
        num_passes = math.ceil(depth / params.step_down)
        actual_step = depth / num_passes

        lines = [
            f"( Contour Profile from Points )",
            f"( Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')} )",
            f"( Points: {len(points)}, Depth: {depth}\" )",
            f"( Tool: {params.tool_diameter}\" end mill )",
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

        # Calculate tool offset based on profile direction
        # For outside profile: offset outward (left of travel direction for climb milling)
        # For inside profile: offset inward (right of travel direction for climb milling)
        offset_distance = tool_rad + params.stock_to_leave

        # Calculate offset points
        offset_points = ProfilingTemplates._calculate_offset_points(
            points, offset_distance, params.outside_profile, params.climb_milling
        )

        current_z = 0

        for pass_num in range(num_passes):
            current_z -= actual_step

            lines.extend([
                "",
                f"( Pass {pass_num + 1}/{num_passes} at Z{current_z:.4f} )",
                f"G0 X{offset_points[0][0]:.4f} Y{offset_points[0][1]:.4f}",
                f"G0 Z0.05",
                f"G1 Z{current_z:.4f} F{params.plunge_rate}",
            ])

            # Cut through all offset points
            for i, (x, y) in enumerate(offset_points[1:], 1):
                lines.append(f"G1 X{x:.4f} Y{y:.4f} F{params.feed_rate}")

            # Close contour if requested
            if closed:
                lines.append(
                    f"G1 X{offset_points[0][0]:.4f} Y{offset_points[0][1]:.4f}"
                )

        lines.extend([
            "",
            f"G0 Z{params.safe_z}",
            "M9",
            "M5",
            "G0 X0 Y0",
            "M30",
        ])

        return "\n".join(lines)

    @staticmethod
    def chamfer_profile(
        points: List[Tuple[float, float]],
        chamfer_depth: float,
        chamfer_width: float,
        params: ProfileParameters,
    ) -> str:
        """
        Generate chamfer along a profile.

        Uses a chamfer mill or V-bit to break edges.
        """
        if len(points) < 2:
            return "( ERROR: Need at least 2 points )\nM30\n"

        lines = [
            f"( Chamfer Profile )",
            f"( Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')} )",
            f"( Chamfer: {chamfer_width}\" x {chamfer_depth}\" )",
            "",
            "G90 G94 G17",
            "G54",
            "",
            f"T{params.tool_number} M6 ( Chamfer tool )",
            f"S{params.spindle_speed} M3",
            "G4 P2.0",
            "",
            f"G0 Z{params.safe_z}",
            f"G0 X{points[0][0]:.4f} Y{points[0][1]:.4f}",
            f"G0 Z0.05",
            f"G1 Z{-chamfer_depth:.4f} F{params.plunge_rate}",
        ]

        for x, y in points[1:]:
            lines.append(f"G1 X{x:.4f} Y{y:.4f} F{params.feed_rate}")

        # Close to start
        lines.append(f"G1 X{points[0][0]:.4f} Y{points[0][1]:.4f}")

        lines.extend([
            "",
            f"G0 Z{params.safe_z}",
            "M5",
            "G0 X0 Y0",
            "M30",
        ])

        return "\n".join(lines)
