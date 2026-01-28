"""
Pocketing Templates for G-code generation.

Provides templates for:
- Rectangular pockets
- Circular pockets
- Island avoidance (basic)
"""

import math
from dataclasses import dataclass
from typing import List, Optional, Tuple
from datetime import datetime


@dataclass
class PocketParameters:
    """Pocketing parameters."""
    tool_number: int = 1
    tool_diameter: float = 0.25
    spindle_speed: int = 10000
    feed_rate: float = 30.0
    plunge_rate: float = 10.0
    safe_z: float = 0.1
    step_over: float = 0.4  # Factor of tool diameter
    step_down: float = 0.1  # Depth per pass
    climb_milling: bool = True


class PocketingTemplates:
    """Templates for pocketing operations."""

    @staticmethod
    def rectangular_pocket(
        center_x: float,
        center_y: float,
        width: float,
        length: float,
        depth: float,
        params: PocketParameters,
        corner_radius: Optional[float] = None,
    ) -> str:
        """
        Generate rectangular pocket G-code.

        Uses outward spiral pattern with ramp entry.
        """
        tool_rad = params.tool_diameter / 2
        step_over = params.tool_diameter * params.step_over
        corner_rad = corner_radius or tool_rad

        # Calculate pocket bounds with tool offset
        x_min = center_x - width / 2 + tool_rad
        x_max = center_x + width / 2 - tool_rad
        y_min = center_y - length / 2 + tool_rad
        y_max = center_y + length / 2 - tool_rad

        # Number of depth passes
        num_z_passes = math.ceil(depth / params.step_down)
        actual_step_down = depth / num_z_passes

        lines = [
            f"( Rectangular Pocket )",
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

        current_z = 0

        for z_pass in range(num_z_passes):
            current_z -= actual_step_down

            lines.extend([
                "",
                f"( Depth pass {z_pass + 1}/{num_z_passes} at Z{current_z:.4f} )",
            ])

            # Ramp entry at center
            lines.extend([
                f"G0 X{center_x:.4f} Y{center_y:.4f}",
                f"G0 Z0.05",
            ])

            # Helical ramp entry
            ramp_radius = min(step_over, (x_max - x_min) / 4)
            ramp_passes = max(1, int(actual_step_down / 0.01))
            z_per_circle = actual_step_down / ramp_passes

            for ramp in range(ramp_passes):
                target_z = -((z_pass * actual_step_down) + (ramp + 1) * z_per_circle)
                lines.append(
                    f"G2 X{center_x + ramp_radius:.4f} Y{center_y:.4f} "
                    f"I{ramp_radius / 2:.4f} J0 Z{target_z:.4f} F{params.plunge_rate}"
                )

            # Outward spiral clearing
            y_current = center_y
            x_start = center_x - step_over
            direction = 1

            while y_current >= y_min and y_current <= y_max:
                # Move to start of row
                lines.append(f"G1 X{x_min:.4f} Y{y_current:.4f} F{params.feed_rate}")

                # Cut across
                if direction == 1:
                    lines.append(f"G1 X{x_max:.4f}")
                else:
                    lines.append(f"G1 X{x_min:.4f}")

                y_current += step_over * direction

                # Alternate direction for better finish
                direction *= -1
                if abs(y_current - center_y) > (y_max - y_min) / 2:
                    break

            # Clean up walls - perimeter pass
            lines.extend([
                "",
                "( Perimeter cleanup )",
                f"G1 X{x_min:.4f} Y{y_min:.4f} F{params.feed_rate}",
            ])

            if corner_rad > tool_rad:
                # With corner radius
                lines.extend([
                    f"G1 X{x_max - corner_rad:.4f}",
                    f"G2 X{x_max:.4f} Y{y_min + corner_rad:.4f} R{corner_rad:.4f}",
                    f"G1 Y{y_max - corner_rad:.4f}",
                    f"G2 X{x_max - corner_rad:.4f} Y{y_max:.4f} R{corner_rad:.4f}",
                    f"G1 X{x_min + corner_rad:.4f}",
                    f"G2 X{x_min:.4f} Y{y_max - corner_rad:.4f} R{corner_rad:.4f}",
                    f"G1 Y{y_min + corner_rad:.4f}",
                    f"G2 X{x_min + corner_rad:.4f} Y{y_min:.4f} R{corner_rad:.4f}",
                ])
            else:
                # Sharp corners
                lines.extend([
                    f"G1 X{x_max:.4f}",
                    f"G1 Y{y_max:.4f}",
                    f"G1 X{x_min:.4f}",
                    f"G1 Y{y_min:.4f}",
                ])

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
    def circular_pocket(
        center_x: float,
        center_y: float,
        diameter: float,
        depth: float,
        params: PocketParameters,
    ) -> str:
        """
        Generate circular pocket G-code.

        Uses outward spiral pattern with helical entry.
        """
        tool_rad = params.tool_diameter / 2
        pocket_radius = diameter / 2 - tool_rad
        step_over = params.tool_diameter * params.step_over

        if pocket_radius <= 0:
            return "( ERROR: Pocket too small for tool )\nM30\n"

        # Number of depth passes
        num_z_passes = math.ceil(depth / params.step_down)
        actual_step_down = depth / num_z_passes

        # Number of radial passes
        num_radial = max(1, int(pocket_radius / step_over))
        actual_step_over = pocket_radius / num_radial

        lines = [
            f"( Circular Pocket )",
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

        current_z = 0

        for z_pass in range(num_z_passes):
            current_z -= actual_step_down

            lines.extend([
                "",
                f"( Depth pass {z_pass + 1}/{num_z_passes} at Z{current_z:.4f} )",
                f"G0 X{center_x:.4f} Y{center_y:.4f}",
                f"G0 Z0.05",
            ])

            # Helical plunge at center
            plunge_radius = min(actual_step_over, pocket_radius * 0.3)
            lines.append(
                f"G2 X{center_x + plunge_radius:.4f} Y{center_y:.4f} "
                f"I{plunge_radius:.4f} J0 Z{current_z:.4f} F{params.plunge_rate}"
            )

            # Outward spiral
            current_radius = plunge_radius
            while current_radius < pocket_radius:
                next_radius = min(current_radius + actual_step_over, pocket_radius)

                # Spiral out one turn
                lines.append(
                    f"G2 X{center_x + next_radius:.4f} Y{center_y:.4f} "
                    f"I{-current_radius:.4f} J0 F{params.feed_rate}"
                )
                current_radius = next_radius

            # Final full circle at perimeter
            lines.append(
                f"G2 X{center_x + pocket_radius:.4f} Y{center_y:.4f} "
                f"I{-pocket_radius:.4f} J0 F{params.feed_rate}"
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
    def slot(
        start_x: float,
        start_y: float,
        end_x: float,
        end_y: float,
        width: float,
        depth: float,
        params: PocketParameters,
    ) -> str:
        """
        Generate slot G-code.

        Creates a slot from start to end with specified width and depth.
        """
        tool_rad = params.tool_diameter / 2
        slot_offset = (width / 2) - tool_rad

        # Number of depth passes
        num_z_passes = math.ceil(depth / params.step_down)
        actual_step_down = depth / num_z_passes

        # Calculate slot direction
        dx = end_x - start_x
        dy = end_y - start_y
        length = math.sqrt(dx**2 + dy**2)

        if length == 0:
            return "( ERROR: Slot has zero length )\nM30\n"

        # Normalize direction
        nx = dx / length
        ny = dy / length

        # Perpendicular for offset
        px = -ny * slot_offset
        py = nx * slot_offset

        lines = [
            f"( Slot Operation )",
            f"( Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')} )",
            f"( Width: {width}\", Length: {length:.3f}\", Depth: {depth}\" )",
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

        current_z = 0

        for z_pass in range(num_z_passes):
            current_z -= actual_step_down

            lines.extend([
                "",
                f"( Pass {z_pass + 1}/{num_z_passes} at Z{current_z:.4f} )",
            ])

            # Ramp entry
            lines.extend([
                f"G0 X{start_x:.4f} Y{start_y:.4f}",
                f"G0 Z0.05",
                f"G1 Z{current_z:.4f} F{params.plunge_rate}",
            ])

            # Center pass
            lines.append(f"G1 X{end_x:.4f} Y{end_y:.4f} F{params.feed_rate}")

            if slot_offset > 0.001:
                # Offset passes for full width
                # Right side
                lines.extend([
                    f"G1 X{end_x + px:.4f} Y{end_y + py:.4f}",
                    f"G1 X{start_x + px:.4f} Y{start_y + py:.4f}",
                ])
                # Left side
                lines.extend([
                    f"G1 X{start_x - px:.4f} Y{start_y - py:.4f}",
                    f"G1 X{end_x - px:.4f} Y{end_y - py:.4f}",
                ])

            # End arc
            if width > params.tool_diameter:
                lines.append(
                    f"G2 X{end_x + px:.4f} Y{end_y + py:.4f} "
                    f"R{slot_offset:.4f}"
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
