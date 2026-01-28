"""
Engraving Services for Flask CNC SCADA
======================================
G-code generation for text and QR code engraving.

Provides:
- Text engraving with single-stroke fonts
- QR code engraving with configurable sizes
- Serial number and batch code generation

Usage:
    from services.engraving import get_engraving_service

    service = get_engraving_service()
    gcode = service.generate_text_engraving("SERIAL-001", height=5)
    gcode = service.generate_qr_engraving("https://example.com/trace/123", size=20)
"""

from services.engraving.text_generator import TextEngravingGenerator
from services.engraving.qr_generator import QRCodeGenerator
from services.engraving.engraving_service import (
    EngravingService,
    get_engraving_service,
)

__all__ = [
    "TextEngravingGenerator",
    "QRCodeGenerator",
    "EngravingService",
    "get_engraving_service",
]
