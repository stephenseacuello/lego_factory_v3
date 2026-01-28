"""
QR Code Engraving G-code Generator
==================================
Generates G-code for QR code engraving.

Features:
- QR code generation from text/URLs
- Configurable module (cell) size
- Efficient toolpath optimization
- Traceability integration

Requirements:
- qrcode library (pip install qrcode)

Usage:
    from services.engraving.qr_generator import QRCodeGenerator

    gen = QRCodeGenerator()
    gcode = gen.generate("https://example.com/trace/123", x=0, y=0, size=20)
"""

import logging
from typing import Optional, List, Tuple
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# Try to import qrcode library
try:
    import qrcode
    from qrcode.constants import ERROR_CORRECT_M
    HAS_QRCODE = True
except ImportError:
    HAS_QRCODE = False
    logger.warning("qrcode library not installed. QR generation will use fallback.")


@dataclass
class QREngravingParams:
    """Parameters for QR code engraving."""
    size: float = 20.0            # Total QR size in mm
    cut_depth: float = 0.3        # Engraving depth in mm
    feed_rate: float = 500.0      # Feed rate in mm/min
    plunge_rate: float = 100.0    # Plunge rate in mm/min
    safe_z: float = 5.0           # Safe retract height
    error_correction: str = "M"   # L, M, Q, H
    quiet_zone: int = 4           # Modules of quiet zone
    invert: bool = False          # Invert (engrave light, leave dark)


class QRCodeGenerator:
    """
    Generates G-code for QR code engraving.

    Uses raster-scan pattern with optimized toolpath to minimize
    retracts and rapid moves.
    """

    def __init__(self):
        """Initialize QR generator."""
        self.has_qrcode = HAS_QRCODE
        logger.info(f"QRCodeGenerator initialized (qrcode lib: {HAS_QRCODE})")

    def generate(
        self,
        data: str,
        x: float = 0,
        y: float = 0,
        params: Optional[QREngravingParams] = None,
    ) -> str:
        """
        Generate G-code for QR code engraving.

        Args:
            data: Data to encode in QR code
            x: Starting X position (bottom-left corner)
            y: Starting Y position (bottom-left corner)
            params: Engraving parameters

        Returns:
            G-code string
        """
        if params is None:
            params = QREngravingParams()

        # Generate QR matrix
        matrix = self._generate_qr_matrix(data, params.error_correction)

        if matrix is None:
            # Fallback to simple pattern if qrcode not available
            return self._generate_fallback(data, x, y, params)

        return self._matrix_to_gcode(matrix, x, y, params)

    def _generate_qr_matrix(
        self,
        data: str,
        error_correction: str = "M"
    ) -> Optional[List[List[bool]]]:
        """
        Generate QR code matrix.

        Returns:
            2D list of booleans (True = dark module)
        """
        if not self.has_qrcode:
            return None

        # Map error correction level
        ec_map = {
            "L": qrcode.constants.ERROR_CORRECT_L,
            "M": qrcode.constants.ERROR_CORRECT_M,
            "Q": qrcode.constants.ERROR_CORRECT_Q,
            "H": qrcode.constants.ERROR_CORRECT_H,
        }
        ec_level = ec_map.get(error_correction.upper(), ERROR_CORRECT_M)

        try:
            qr = qrcode.QRCode(
                version=None,  # Auto-size
                error_correction=ec_level,
                box_size=1,
                border=0,
            )
            qr.add_data(data)
            qr.make(fit=True)

            # Get matrix
            matrix = qr.get_matrix()
            return matrix

        except Exception as e:
            logger.error(f"QR generation failed: {e}")
            return None

    def _matrix_to_gcode(
        self,
        matrix: List[List[bool]],
        x: float,
        y: float,
        params: QREngravingParams,
    ) -> str:
        """
        Convert QR matrix to G-code.

        Uses optimized horizontal line scanning.
        """
        lines = []

        # Calculate module size
        matrix_size = len(matrix)
        total_size = params.size - (2 * params.quiet_zone * params.size / (matrix_size + 2 * params.quiet_zone))
        module_size = total_size / matrix_size

        # Header
        lines.append("; ========================================")
        lines.append("; QR Code Engraving G-code")
        lines.append(f"; Size: {params.size}mm x {params.size}mm")
        lines.append(f"; Modules: {matrix_size} x {matrix_size}")
        lines.append(f"; Module size: {module_size:.3f}mm")
        lines.append(f"; Depth: {params.cut_depth}mm")
        lines.append("; ========================================")
        lines.append("")

        # Setup
        lines.append("G21 ; Millimeters")
        lines.append("G90 ; Absolute positioning")
        lines.append(f"G0 Z{params.safe_z:.3f} ; Safe Z")
        lines.append("")

        # Calculate quiet zone offset
        quiet_offset = params.quiet_zone * module_size

        # Process each row (bottom to top for standard coordinate system)
        for row_idx in range(matrix_size - 1, -1, -1):
            row = matrix[row_idx]
            row_y = y + quiet_offset + (matrix_size - 1 - row_idx) * module_size + module_size / 2

            # Find continuous dark segments in row
            segments = self._find_segments(row, params.invert)

            for start_col, end_col in segments:
                # Calculate positions
                start_x = x + quiet_offset + start_col * module_size
                end_x = x + quiet_offset + (end_col + 1) * module_size

                # Rapid to start position
                lines.append(f"G0 X{start_x:.3f} Y{row_y:.3f}")

                # Plunge
                lines.append(f"G1 Z{-params.cut_depth:.3f} F{params.plunge_rate:.0f}")

                # Cut to end
                lines.append(f"G1 X{end_x:.3f} F{params.feed_rate:.0f}")

                # Retract
                lines.append(f"G0 Z{params.safe_z:.3f}")

        # End
        lines.append("")
        lines.append(f"G0 Z{params.safe_z:.3f} ; Safe retract")
        lines.append("G0 X0 Y0 ; Return home")
        lines.append("M30 ; Program end")

        return '\n'.join(lines)

    def _find_segments(
        self,
        row: List[bool],
        invert: bool = False
    ) -> List[Tuple[int, int]]:
        """
        Find continuous segments of modules to cut.

        Returns list of (start_col, end_col) tuples.
        """
        segments = []
        in_segment = False
        start_col = 0

        for col, is_dark in enumerate(row):
            should_cut = is_dark if not invert else not is_dark

            if should_cut and not in_segment:
                # Start new segment
                start_col = col
                in_segment = True
            elif not should_cut and in_segment:
                # End segment
                segments.append((start_col, col - 1))
                in_segment = False

        # Close final segment if needed
        if in_segment:
            segments.append((start_col, len(row) - 1))

        return segments

    def _generate_fallback(
        self,
        data: str,
        x: float,
        y: float,
        params: QREngravingParams,
    ) -> str:
        """
        Generate fallback pattern when qrcode library not available.

        Creates a simple bordered square with text indication.
        """
        lines = []

        lines.append("; ========================================")
        lines.append("; QR Code Placeholder (qrcode lib not installed)")
        lines.append(f"; Data: {data[:30]}...")
        lines.append("; Install: pip install qrcode")
        lines.append("; ========================================")
        lines.append("")

        # Setup
        lines.append("G21 ; Millimeters")
        lines.append("G90 ; Absolute positioning")
        lines.append(f"G0 Z{params.safe_z:.3f}")
        lines.append("")

        # Draw border
        size = params.size
        lines.append(f"G0 X{x:.3f} Y{y:.3f}")
        lines.append(f"G1 Z{-params.cut_depth:.3f} F{params.plunge_rate:.0f}")
        lines.append(f"G1 X{x + size:.3f} Y{y:.3f} F{params.feed_rate:.0f}")
        lines.append(f"G1 X{x + size:.3f} Y{y + size:.3f}")
        lines.append(f"G1 X{x:.3f} Y{y + size:.3f}")
        lines.append(f"G1 X{x:.3f} Y{y:.3f}")
        lines.append(f"G0 Z{params.safe_z:.3f}")

        # Draw X to indicate placeholder
        lines.append(f"G0 X{x:.3f} Y{y:.3f}")
        lines.append(f"G1 Z{-params.cut_depth:.3f} F{params.plunge_rate:.0f}")
        lines.append(f"G1 X{x + size:.3f} Y{y + size:.3f} F{params.feed_rate:.0f}")
        lines.append(f"G0 Z{params.safe_z:.3f}")

        lines.append(f"G0 X{x + size:.3f} Y{y:.3f}")
        lines.append(f"G1 Z{-params.cut_depth:.3f} F{params.plunge_rate:.0f}")
        lines.append(f"G1 X{x:.3f} Y{y + size:.3f} F{params.feed_rate:.0f}")
        lines.append(f"G0 Z{params.safe_z:.3f}")

        # End
        lines.append("")
        lines.append("G0 X0 Y0")
        lines.append("M30")

        return '\n'.join(lines)

    def estimate_time(
        self,
        data: str,
        params: Optional[QREngravingParams] = None
    ) -> float:
        """
        Estimate engraving time in seconds.

        Args:
            data: Data for QR code
            params: Engraving parameters

        Returns:
            Estimated time in seconds
        """
        if params is None:
            params = QREngravingParams()

        # Generate matrix to count modules
        matrix = self._generate_qr_matrix(data, params.error_correction)

        if matrix is None:
            # Fallback estimate
            return 30.0

        # Count dark modules
        dark_count = sum(sum(1 for cell in row if cell) for row in matrix)

        # Estimate based on horizontal scan
        matrix_size = len(matrix)
        module_size = params.size / matrix_size

        # Average segment length
        avg_segment_length = module_size * 3  # Typical segment is 3 modules

        # Cut time
        cut_distance = dark_count * module_size
        cut_time = cut_distance / (params.feed_rate / 60)

        # Retract/rapid time (rough estimate)
        retracts = dark_count // 3  # One retract per ~3 modules on average
        retract_time = retracts * 0.3  # 0.3 sec per retract cycle

        return cut_time + retract_time

    def get_qr_bounds(
        self,
        data: str,
        params: Optional[QREngravingParams] = None
    ) -> Tuple[float, float]:
        """
        Get bounding box dimensions of QR code.

        Args:
            data: Data for QR code
            params: Engraving parameters

        Returns:
            Tuple of (width, height) in mm
        """
        if params is None:
            params = QREngravingParams()

        return params.size, params.size
