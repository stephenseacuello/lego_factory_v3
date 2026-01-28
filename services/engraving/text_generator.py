"""
Text Engraving G-code Generator
===============================
Generates G-code for text engraving using single-stroke fonts.

Features:
- Single-stroke font for clean engraving
- Configurable character height and spacing
- Multi-line text support
- Configurable cut depth and feed rates

Usage:
    from services.engraving.text_generator import TextEngravingGenerator

    gen = TextEngravingGenerator()
    gcode = gen.generate("SERIAL-001", x=0, y=0, height=5, depth=0.5)
"""

import logging
from typing import Optional, Dict, Any, List, Tuple
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class EngravingParams:
    """Parameters for text engraving."""
    char_height: float = 5.0          # Character height in mm
    char_width_ratio: float = 0.6     # Width as ratio of height
    char_spacing_ratio: float = 0.2   # Spacing between chars as ratio
    line_spacing_ratio: float = 1.5   # Line spacing as ratio of height
    cut_depth: float = 0.3            # Engraving depth in mm
    feed_rate: float = 300.0          # Feed rate in mm/min
    plunge_rate: float = 100.0        # Plunge rate in mm/min
    safe_z: float = 5.0               # Safe retract height


# Single-stroke font definition
# Each character is defined as a list of strokes
# Each stroke is a list of (x, y) points relative to character origin
# None indicates a pen-up move (lift between strokes)
# Coordinates are normalized to a 1x1 character cell

SINGLE_STROKE_FONT = {
    'A': [[(0, 0), (0.5, 1), (1, 0)], [(0.2, 0.4), (0.8, 0.4)]],
    'B': [[(0, 0), (0, 1), (0.7, 1), (0.8, 0.9), (0.8, 0.6), (0.7, 0.5), (0, 0.5)],
          [(0.7, 0.5), (0.9, 0.4), (0.9, 0.1), (0.8, 0), (0, 0)]],
    'C': [[(0.9, 0.8), (0.7, 1), (0.3, 1), (0.1, 0.8), (0, 0.5), (0.1, 0.2), (0.3, 0), (0.7, 0), (0.9, 0.2)]],
    'D': [[(0, 0), (0, 1), (0.6, 1), (0.9, 0.8), (1, 0.5), (0.9, 0.2), (0.6, 0), (0, 0)]],
    'E': [[(0.9, 1), (0, 1), (0, 0.5), (0.7, 0.5)], [(0, 0.5), (0, 0), (0.9, 0)]],
    'F': [[(0.9, 1), (0, 1), (0, 0.5), (0.7, 0.5)], [(0, 0.5), (0, 0)]],
    'G': [[(0.9, 0.8), (0.7, 1), (0.3, 1), (0.1, 0.8), (0, 0.5), (0.1, 0.2), (0.3, 0), (0.7, 0), (0.9, 0.2), (0.9, 0.5), (0.5, 0.5)]],
    'H': [[(0, 0), (0, 1)], [(1, 0), (1, 1)], [(0, 0.5), (1, 0.5)]],
    'I': [[(0.3, 1), (0.7, 1)], [(0.5, 1), (0.5, 0)], [(0.3, 0), (0.7, 0)]],
    'J': [[(0.3, 1), (0.8, 1), (0.8, 0.2), (0.6, 0), (0.3, 0), (0.1, 0.2)]],
    'K': [[(0, 0), (0, 1)], [(0.9, 1), (0, 0.4)], [(0.3, 0.55), (0.9, 0)]],
    'L': [[(0, 1), (0, 0), (0.9, 0)]],
    'M': [[(0, 0), (0, 1), (0.5, 0.5), (1, 1), (1, 0)]],
    'N': [[(0, 0), (0, 1), (1, 0), (1, 1)]],
    'O': [[(0.5, 1), (0.2, 0.9), (0, 0.5), (0.2, 0.1), (0.5, 0), (0.8, 0.1), (1, 0.5), (0.8, 0.9), (0.5, 1)]],
    'P': [[(0, 0), (0, 1), (0.7, 1), (0.9, 0.85), (0.9, 0.65), (0.7, 0.5), (0, 0.5)]],
    'Q': [[(0.5, 1), (0.2, 0.9), (0, 0.5), (0.2, 0.1), (0.5, 0), (0.8, 0.1), (1, 0.5), (0.8, 0.9), (0.5, 1)], [(0.6, 0.3), (1, -0.1)]],
    'R': [[(0, 0), (0, 1), (0.7, 1), (0.9, 0.85), (0.9, 0.65), (0.7, 0.5), (0, 0.5)], [(0.5, 0.5), (0.9, 0)]],
    'S': [[(0.9, 0.85), (0.7, 1), (0.3, 1), (0.1, 0.85), (0.1, 0.65), (0.3, 0.5), (0.7, 0.5), (0.9, 0.35), (0.9, 0.15), (0.7, 0), (0.3, 0), (0.1, 0.15)]],
    'T': [[(0, 1), (1, 1)], [(0.5, 1), (0.5, 0)]],
    'U': [[(0, 1), (0, 0.2), (0.2, 0), (0.8, 0), (1, 0.2), (1, 1)]],
    'V': [[(0, 1), (0.5, 0), (1, 1)]],
    'W': [[(0, 1), (0.25, 0), (0.5, 0.5), (0.75, 0), (1, 1)]],
    'X': [[(0, 0), (1, 1)], [(0, 1), (1, 0)]],
    'Y': [[(0, 1), (0.5, 0.5), (1, 1)], [(0.5, 0.5), (0.5, 0)]],
    'Z': [[(0, 1), (1, 1), (0, 0), (1, 0)]],

    '0': [[(0.5, 1), (0.2, 0.9), (0, 0.5), (0.2, 0.1), (0.5, 0), (0.8, 0.1), (1, 0.5), (0.8, 0.9), (0.5, 1)], [(0.2, 0.2), (0.8, 0.8)]],
    '1': [[(0.3, 0.8), (0.5, 1), (0.5, 0)], [(0.3, 0), (0.7, 0)]],
    '2': [[(0.1, 0.8), (0.3, 1), (0.7, 1), (0.9, 0.8), (0.9, 0.6), (0, 0), (1, 0)]],
    '3': [[(0.1, 0.85), (0.3, 1), (0.7, 1), (0.9, 0.85), (0.9, 0.65), (0.7, 0.5), (0.4, 0.5)], [(0.7, 0.5), (0.9, 0.35), (0.9, 0.15), (0.7, 0), (0.3, 0), (0.1, 0.15)]],
    '4': [[(0.7, 0), (0.7, 1), (0, 0.3), (1, 0.3)]],
    '5': [[(0.9, 1), (0.1, 1), (0.1, 0.5), (0.7, 0.5), (0.9, 0.35), (0.9, 0.15), (0.7, 0), (0.3, 0), (0.1, 0.15)]],
    '6': [[(0.8, 0.9), (0.5, 1), (0.2, 0.9), (0, 0.5), (0.2, 0.1), (0.5, 0), (0.8, 0.1), (0.9, 0.3), (0.8, 0.5), (0.5, 0.55), (0.2, 0.5)]],
    '7': [[(0, 1), (1, 1), (0.4, 0)]],
    '8': [[(0.5, 1), (0.2, 0.9), (0.2, 0.6), (0.5, 0.5), (0.8, 0.6), (0.8, 0.9), (0.5, 1)], [(0.5, 0.5), (0.15, 0.35), (0.15, 0.15), (0.5, 0), (0.85, 0.15), (0.85, 0.35), (0.5, 0.5)]],
    '9': [[(0.2, 0.1), (0.5, 0), (0.8, 0.1), (1, 0.5), (0.8, 0.9), (0.5, 1), (0.2, 0.9), (0.1, 0.7), (0.2, 0.5), (0.5, 0.45), (0.8, 0.5)]],

    '-': [[(0.2, 0.5), (0.8, 0.5)]],
    '_': [[(0, 0), (1, 0)]],
    '.': [[(0.4, 0.1), (0.5, 0), (0.6, 0.1), (0.5, 0.15), (0.4, 0.1)]],
    ',': [[(0.5, 0.15), (0.5, 0), (0.4, -0.1)]],
    ':': [[(0.4, 0.7), (0.5, 0.6), (0.6, 0.7), (0.5, 0.75), (0.4, 0.7)], [(0.4, 0.15), (0.5, 0.05), (0.6, 0.15), (0.5, 0.2), (0.4, 0.15)]],
    '/': [[(0.2, 0), (0.8, 1)]],
    '(': [[(0.7, 1), (0.4, 0.7), (0.3, 0.5), (0.4, 0.3), (0.7, 0)]],
    ')': [[(0.3, 1), (0.6, 0.7), (0.7, 0.5), (0.6, 0.3), (0.3, 0)]],
    ' ': [],  # Space - no strokes

    # Lowercase (simplified)
    'a': [[(0.8, 0.5), (0.5, 0.6), (0.2, 0.5), (0.1, 0.3), (0.2, 0.1), (0.5, 0), (0.8, 0.1), (0.8, 0.6), (0.8, 0)]],
    'b': [[(0, 0), (0, 1)], [(0, 0.5), (0.3, 0.6), (0.6, 0.5), (0.7, 0.3), (0.6, 0.1), (0.3, 0), (0, 0.1)]],
    'c': [[(0.7, 0.5), (0.5, 0.6), (0.2, 0.5), (0.1, 0.3), (0.2, 0.1), (0.5, 0), (0.7, 0.1)]],
    'd': [[(0.8, 0), (0.8, 1)], [(0.8, 0.5), (0.5, 0.6), (0.2, 0.5), (0.1, 0.3), (0.2, 0.1), (0.5, 0), (0.8, 0.1)]],
    'e': [[(0.1, 0.3), (0.7, 0.3), (0.7, 0.45), (0.5, 0.6), (0.2, 0.5), (0.1, 0.3), (0.2, 0.1), (0.5, 0), (0.7, 0.1)]],
    'f': [[(0.3, 0), (0.3, 0.8), (0.5, 1), (0.7, 0.9)], [(0.1, 0.5), (0.5, 0.5)]],
    'g': [[(0.8, 0.6), (0.5, 0.6), (0.2, 0.5), (0.1, 0.3), (0.2, 0.1), (0.5, 0), (0.8, 0.1), (0.8, -0.2), (0.5, -0.3), (0.2, -0.2)]],
    'h': [[(0, 0), (0, 1)], [(0, 0.4), (0.4, 0.6), (0.7, 0.5), (0.8, 0.3), (0.8, 0)]],
    'i': [[(0.4, 0), (0.4, 0.5)], [(0.4, 0.75), (0.4, 0.8)]],
    'j': [[(0.5, 0.5), (0.5, -0.1), (0.3, -0.3), (0.1, -0.2)], [(0.5, 0.75), (0.5, 0.8)]],
    'k': [[(0.1, 0), (0.1, 1)], [(0.6, 0.6), (0.1, 0.25)], [(0.25, 0.35), (0.7, 0)]],
    'l': [[(0.4, 0), (0.4, 1)]],
    'm': [[(0.1, 0), (0.1, 0.6)], [(0.1, 0.5), (0.3, 0.6), (0.45, 0.5), (0.5, 0)], [(0.5, 0.5), (0.7, 0.6), (0.85, 0.5), (0.9, 0)]],
    'n': [[(0.1, 0), (0.1, 0.6)], [(0.1, 0.4), (0.4, 0.6), (0.7, 0.5), (0.8, 0.3), (0.8, 0)]],
    'o': [[(0.5, 0.6), (0.2, 0.5), (0.1, 0.3), (0.2, 0.1), (0.5, 0), (0.8, 0.1), (0.9, 0.3), (0.8, 0.5), (0.5, 0.6)]],
    'p': [[(0.1, -0.3), (0.1, 0.6)], [(0.1, 0.5), (0.4, 0.6), (0.7, 0.5), (0.8, 0.3), (0.7, 0.1), (0.4, 0), (0.1, 0.1)]],
    'q': [[(0.8, -0.3), (0.8, 0.6)], [(0.8, 0.5), (0.5, 0.6), (0.2, 0.5), (0.1, 0.3), (0.2, 0.1), (0.5, 0), (0.8, 0.1)]],
    'r': [[(0.2, 0), (0.2, 0.6)], [(0.2, 0.4), (0.4, 0.6), (0.6, 0.55), (0.7, 0.45)]],
    's': [[(0.7, 0.5), (0.5, 0.6), (0.2, 0.55), (0.2, 0.4), (0.5, 0.3), (0.8, 0.2), (0.8, 0.1), (0.5, 0), (0.2, 0.1)]],
    't': [[(0.3, 0.1), (0.3, 0.9)], [(0.1, 0.6), (0.5, 0.6)]],
    'u': [[(0.1, 0.6), (0.1, 0.2), (0.3, 0), (0.6, 0), (0.8, 0.2)], [(0.8, 0.6), (0.8, 0)]],
    'v': [[(0.1, 0.6), (0.45, 0), (0.8, 0.6)]],
    'w': [[(0.1, 0.6), (0.25, 0), (0.45, 0.4), (0.65, 0), (0.8, 0.6)]],
    'x': [[(0.1, 0), (0.8, 0.6)], [(0.1, 0.6), (0.8, 0)]],
    'y': [[(0.1, 0.6), (0.45, 0.1)], [(0.8, 0.6), (0.45, 0.1), (0.2, -0.3)]],
    'z': [[(0.1, 0.6), (0.8, 0.6), (0.1, 0), (0.8, 0)]],
}


class TextEngravingGenerator:
    """
    Generates G-code for text engraving.

    Uses single-stroke font for efficient engraving paths.
    """

    def __init__(self):
        """Initialize text generator."""
        self.font = SINGLE_STROKE_FONT
        logger.info("TextEngravingGenerator initialized")

    def generate(
        self,
        text: str,
        x: float = 0,
        y: float = 0,
        params: Optional[EngravingParams] = None,
    ) -> str:
        """
        Generate G-code for text engraving.

        Args:
            text: Text to engrave (supports newlines)
            x: Starting X position
            y: Starting Y position
            params: Engraving parameters

        Returns:
            G-code string
        """
        if params is None:
            params = EngravingParams()

        lines = []

        # Header
        lines.append("; ========================================")
        lines.append("; Text Engraving G-code")
        lines.append(f"; Text: {text[:50]}{'...' if len(text) > 50 else ''}")
        lines.append(f"; Height: {params.char_height}mm")
        lines.append(f"; Depth: {params.cut_depth}mm")
        lines.append("; ========================================")
        lines.append("")

        # Setup
        lines.append("G21 ; Millimeters")
        lines.append("G90 ; Absolute positioning")
        lines.append(f"G0 Z{params.safe_z:.3f} ; Safe Z")
        lines.append("")

        # Calculate dimensions
        char_width = params.char_height * params.char_width_ratio
        char_spacing = params.char_height * params.char_spacing_ratio
        line_spacing = params.char_height * params.line_spacing_ratio

        # Process each line of text
        text_lines = text.split('\n')
        current_y = y

        for text_line in text_lines:
            current_x = x

            for char in text_line:
                char_upper = char.upper()

                if char_upper in self.font:
                    strokes = self.font[char_upper]

                    for stroke in strokes:
                        if not stroke:
                            continue

                        # Move to start of stroke (rapid, safe Z)
                        start_point = stroke[0]
                        start_x = current_x + start_point[0] * char_width
                        start_y = current_y + start_point[1] * params.char_height

                        lines.append(f"G0 X{start_x:.3f} Y{start_y:.3f}")
                        lines.append(f"G1 Z{-params.cut_depth:.3f} F{params.plunge_rate:.0f}")

                        # Cut stroke
                        for point in stroke[1:]:
                            px = current_x + point[0] * char_width
                            py = current_y + point[1] * params.char_height
                            lines.append(f"G1 X{px:.3f} Y{py:.3f} F{params.feed_rate:.0f}")

                        # Retract
                        lines.append(f"G0 Z{params.safe_z:.3f}")

                # Advance to next character
                current_x += char_width + char_spacing

            # Move to next line
            current_y -= line_spacing

        # End
        lines.append("")
        lines.append(f"G0 Z{params.safe_z:.3f} ; Safe retract")
        lines.append("G0 X0 Y0 ; Return home")
        lines.append("M30 ; Program end")

        return '\n'.join(lines)

    def estimate_time(self, text: str, params: Optional[EngravingParams] = None) -> float:
        """
        Estimate engraving time in seconds.

        Args:
            text: Text to engrave
            params: Engraving parameters

        Returns:
            Estimated time in seconds
        """
        if params is None:
            params = EngravingParams()

        # Rough estimation based on character count and strokes
        total_strokes = 0
        for char in text:
            char_upper = char.upper()
            if char_upper in self.font:
                total_strokes += len(self.font[char_upper])

        # Average stroke length * number of strokes / feed rate
        avg_stroke_length = params.char_height * 1.5  # mm
        cut_time = (total_strokes * avg_stroke_length) / (params.feed_rate / 60)

        # Add retract/rapid time
        rapid_time = total_strokes * 0.5  # 0.5 sec per retract/position

        return cut_time + rapid_time

    def get_text_bounds(
        self,
        text: str,
        params: Optional[EngravingParams] = None
    ) -> Tuple[float, float]:
        """
        Get bounding box dimensions of text.

        Args:
            text: Text to measure
            params: Engraving parameters

        Returns:
            Tuple of (width, height) in mm
        """
        if params is None:
            params = EngravingParams()

        char_width = params.char_height * params.char_width_ratio
        char_spacing = params.char_height * params.char_spacing_ratio
        line_spacing = params.char_height * params.line_spacing_ratio

        lines = text.split('\n')
        max_width = 0

        for line in lines:
            line_width = len(line) * (char_width + char_spacing) - char_spacing
            max_width = max(max_width, line_width)

        height = len(lines) * params.char_height + (len(lines) - 1) * (line_spacing - params.char_height)

        return max_width, height
