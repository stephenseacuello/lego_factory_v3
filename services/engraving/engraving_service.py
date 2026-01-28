"""
Engraving Service for Flask CNC SCADA
=====================================
Unified service for text and QR code engraving G-code generation.

Features:
- Text engraving with single-stroke fonts
- QR code generation with configurable sizes
- Serial number and batch code templates
- Traceability URL generation
- Job queue integration

Usage:
    from services.engraving import get_engraving_service

    service = get_engraving_service()

    # Text engraving
    gcode = service.generate_text("SERIAL-001", height=5, depth=0.5)

    # QR code engraving
    gcode = service.generate_qr("https://trace.example.com/123", size=20)

    # Serial number with auto-increment
    gcode = service.generate_serial(prefix="SN", start=1000)
"""

import logging
import re
from datetime import datetime
from typing import Optional, Dict, Any, Tuple

from services.engraving.text_generator import TextEngravingGenerator, EngravingParams
from services.engraving.qr_generator import QRCodeGenerator, QREngravingParams

logger = logging.getLogger(__name__)


class EngravingService:
    """
    Unified engraving service for text and QR codes.

    Provides high-level methods for common engraving tasks with
    integration to job queue and traceability systems.
    """

    def __init__(self):
        """Initialize engraving service."""
        self.text_gen = TextEngravingGenerator()
        self.qr_gen = QRCodeGenerator()

        # Serial number counter
        self._serial_counter = 0

        logger.info("EngravingService initialized")

    def generate_text(
        self,
        text: str,
        x: float = 0,
        y: float = 0,
        height: float = 5.0,
        depth: float = 0.3,
        feed_rate: float = 300.0,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Generate G-code for text engraving.

        Args:
            text: Text to engrave
            x: Starting X position
            y: Starting Y position
            height: Character height in mm
            depth: Cut depth in mm
            feed_rate: Feed rate in mm/min

        Returns:
            Dictionary with gcode, metadata, and estimates
        """
        params = EngravingParams(
            char_height=height,
            cut_depth=depth,
            feed_rate=feed_rate,
            **kwargs
        )

        gcode = self.text_gen.generate(text, x, y, params)
        bounds = self.text_gen.get_text_bounds(text, params)
        time_est = self.text_gen.estimate_time(text, params)

        return {
            "gcode": gcode,
            "type": "text",
            "text": text,
            "position": {"x": x, "y": y},
            "bounds": {"width": bounds[0], "height": bounds[1]},
            "params": {
                "height": height,
                "depth": depth,
                "feed_rate": feed_rate,
            },
            "estimated_time_sec": time_est,
            "line_count": len(gcode.splitlines()),
        }

    def generate_qr(
        self,
        data: str,
        x: float = 0,
        y: float = 0,
        size: float = 20.0,
        depth: float = 0.3,
        feed_rate: float = 500.0,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Generate G-code for QR code engraving.

        Args:
            data: Data to encode (text, URL, etc.)
            x: Starting X position (bottom-left)
            y: Starting Y position (bottom-left)
            size: QR code size in mm
            depth: Cut depth in mm
            feed_rate: Feed rate in mm/min

        Returns:
            Dictionary with gcode, metadata, and estimates
        """
        params = QREngravingParams(
            size=size,
            cut_depth=depth,
            feed_rate=feed_rate,
            **kwargs
        )

        gcode = self.qr_gen.generate(data, x, y, params)
        bounds = self.qr_gen.get_qr_bounds(data, params)
        time_est = self.qr_gen.estimate_time(data, params)

        return {
            "gcode": gcode,
            "type": "qr",
            "data": data,
            "position": {"x": x, "y": y},
            "bounds": {"width": bounds[0], "height": bounds[1]},
            "params": {
                "size": size,
                "depth": depth,
                "feed_rate": feed_rate,
            },
            "estimated_time_sec": time_est,
            "line_count": len(gcode.splitlines()),
        }

    def generate_serial_number(
        self,
        prefix: str = "SN",
        number: Optional[int] = None,
        suffix: str = "",
        x: float = 0,
        y: float = 0,
        height: float = 5.0,
        depth: float = 0.3,
    ) -> Dict[str, Any]:
        """
        Generate serial number engraving.

        Args:
            prefix: Serial number prefix
            number: Serial number (auto-increment if None)
            suffix: Serial number suffix
            x: Starting X position
            y: Starting Y position
            height: Character height
            depth: Cut depth

        Returns:
            Dictionary with gcode and serial number
        """
        if number is None:
            self._serial_counter += 1
            number = self._serial_counter

        serial = f"{prefix}{number:06d}{suffix}"

        result = self.generate_text(serial, x, y, height, depth)
        result["serial_number"] = serial
        result["serial_prefix"] = prefix
        result["serial_sequence"] = number
        result["serial_suffix"] = suffix

        return result

    def generate_date_code(
        self,
        format_str: str = "%Y%m%d",
        x: float = 0,
        y: float = 0,
        height: float = 3.0,
        depth: float = 0.3,
    ) -> Dict[str, Any]:
        """
        Generate date code engraving.

        Args:
            format_str: Date format string
            x: Starting X position
            y: Starting Y position
            height: Character height
            depth: Cut depth

        Returns:
            Dictionary with gcode and date string
        """
        date_str = datetime.now().strftime(format_str)
        result = self.generate_text(date_str, x, y, height, depth)
        result["date_code"] = date_str
        result["date_format"] = format_str

        return result

    def generate_trace_qr(
        self,
        trace_id: str,
        base_url: str = "http://localhost:5000/api/traceability",
        x: float = 0,
        y: float = 0,
        size: float = 15.0,
        depth: float = 0.3,
    ) -> Dict[str, Any]:
        """
        Generate traceability QR code.

        Creates QR code linking to trace record.

        Args:
            trace_id: Trace record ID
            base_url: Base URL for traceability API
            x: Starting X position
            y: Starting Y position
            size: QR code size
            depth: Cut depth

        Returns:
            Dictionary with gcode and trace URL
        """
        trace_url = f"{base_url}/records/{trace_id}"

        result = self.generate_qr(trace_url, x, y, size, depth)
        result["trace_id"] = trace_id
        result["trace_url"] = trace_url

        return result

    def generate_combined(
        self,
        serial: str,
        trace_id: str,
        x: float = 0,
        y: float = 0,
        serial_height: float = 4.0,
        qr_size: float = 15.0,
        depth: float = 0.3,
        spacing: float = 5.0,
    ) -> Dict[str, Any]:
        """
        Generate combined serial number and QR code.

        Creates layout with serial number above QR code.

        Args:
            serial: Serial number text
            trace_id: Trace ID for QR
            x: Starting X position
            y: Starting Y position
            serial_height: Serial character height
            qr_size: QR code size
            depth: Cut depth
            spacing: Space between serial and QR

        Returns:
            Combined G-code and metadata
        """
        # Generate QR at base position
        qr_result = self.generate_trace_qr(
            trace_id,
            x=x,
            y=y,
            size=qr_size,
            depth=depth
        )

        # Generate serial above QR
        serial_y = y + qr_size + spacing
        serial_result = self.generate_text(
            serial,
            x=x,
            y=serial_y,
            height=serial_height,
            depth=depth
        )

        # Combine G-code
        # Remove end commands from first gcode
        qr_gcode_lines = qr_result["gcode"].splitlines()
        combined_lines = []

        for line in qr_gcode_lines:
            if not line.startswith("M30") and "Return home" not in line:
                combined_lines.append(line)

        # Add serial gcode (skip header and setup)
        serial_gcode_lines = serial_result["gcode"].splitlines()
        in_body = False

        for line in serial_gcode_lines:
            if line.startswith("G0 X") or line.startswith("G1"):
                in_body = True
            if in_body:
                combined_lines.append(line)

        combined_gcode = '\n'.join(combined_lines)

        # Calculate combined bounds
        qr_width = qr_result["bounds"]["width"]
        serial_width = serial_result["bounds"]["width"]
        total_height = qr_size + spacing + serial_height

        return {
            "gcode": combined_gcode,
            "type": "combined",
            "serial_number": serial,
            "trace_id": trace_id,
            "position": {"x": x, "y": y},
            "bounds": {
                "width": max(qr_width, serial_width),
                "height": total_height,
            },
            "estimated_time_sec": qr_result["estimated_time_sec"] + serial_result["estimated_time_sec"],
            "line_count": len(combined_gcode.splitlines()),
            "components": {
                "qr": qr_result,
                "serial": serial_result,
            }
        }

    def validate_engraving_area(
        self,
        bounds: Dict[str, float],
        position: Dict[str, float],
        machine_limits: Optional[Dict[str, float]] = None,
    ) -> Tuple[bool, str]:
        """
        Validate that engraving fits within machine limits.

        Args:
            bounds: Engraving bounds (width, height)
            position: Starting position (x, y)
            machine_limits: Machine work area limits

        Returns:
            Tuple of (valid, message)
        """
        if machine_limits is None:
            # Default TinyG-sized work area
            machine_limits = {
                "x_min": 0,
                "x_max": 200,
                "y_min": 0,
                "y_max": 200,
            }

        x_end = position["x"] + bounds["width"]
        y_end = position["y"] + bounds["height"]

        errors = []

        if position["x"] < machine_limits["x_min"]:
            errors.append(f"X start ({position['x']}) below minimum ({machine_limits['x_min']})")
        if x_end > machine_limits["x_max"]:
            errors.append(f"X end ({x_end}) exceeds maximum ({machine_limits['x_max']})")
        if position["y"] < machine_limits["y_min"]:
            errors.append(f"Y start ({position['y']}) below minimum ({machine_limits['y_min']})")
        if y_end > machine_limits["y_max"]:
            errors.append(f"Y end ({y_end}) exceeds maximum ({machine_limits['y_max']})")

        if errors:
            return False, "; ".join(errors)

        return True, "OK"


# Global service instance
_engraving_service: Optional[EngravingService] = None


def get_engraving_service() -> EngravingService:
    """Get global engraving service instance."""
    global _engraving_service
    if _engraving_service is None:
        _engraving_service = EngravingService()
    return _engraving_service
