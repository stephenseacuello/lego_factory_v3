"""
Slicer Service Client

HTTP client for communicating with the PrusaSlicer/OrcaSlicer service.
Handles STL slicing and G-code generation for 3D printing.
"""

import asyncio
import aiohttp
import logging
from typing import Dict, Any, Optional, List
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class SlicerResponse:
    """Response from slicer service."""

    success: bool
    data: Dict[str, Any]
    error: Optional[str] = None


class SlicerClient:
    """
    Async HTTP client for slicer service API.

    The slicer service wraps PrusaSlicer CLI for G-code generation.
    """

    def __init__(self, base_url: str = "http://localhost:8766"):
        self.base_url = base_url.rstrip("/")
        self.timeout = aiohttp.ClientTimeout(total=300)  # 5 min for large prints
        self._session: Optional[aiohttp.ClientSession] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(timeout=self.timeout)
        return self._session

    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()

    async def _request(
        self, method: str, endpoint: str, data: Dict[str, Any] = None
    ) -> SlicerResponse:
        url = f"{self.base_url}{endpoint}"

        try:
            session = await self._get_session()
            async with session.request(method, url, json=data) as response:
                result = await response.json()
                if response.status == 200:
                    return SlicerResponse(success=True, data=result)
                else:
                    return SlicerResponse(
                        success=False, data={}, error=result.get("error", f"HTTP {response.status}")
                    )
        except aiohttp.ClientConnectorError:
            return SlicerResponse(
                success=False, data={}, error="Cannot connect to slicer service. Is it running?"
            )
        except asyncio.TimeoutError:
            return SlicerResponse(
                success=False, data={}, error="Slicing timed out. The model may be too complex."
            )
        except Exception as e:
            logger.error(f"Slicer API error: {e}")
            return SlicerResponse(success=False, data={}, error=str(e))

    async def health_check(self) -> bool:
        """Check if slicer service is responding."""
        try:
            response = await self._request("GET", "/health")
            return response.success
        except:
            return False

    async def get_status(self) -> Dict[str, Any]:
        """Get slicer service status."""
        response = await self._request("GET", "/status")
        if response.success:
            return response.data
        return {"connected": False, "error": response.error}

    async def list_printers(self) -> Dict[str, Any]:
        """List available printer profiles."""
        response = await self._request("GET", "/printers")
        if response.success:
            return {"printers": response.data.get("printers", [])}
        return {"error": response.error}

    async def list_materials(self) -> Dict[str, Any]:
        """List available material profiles."""
        response = await self._request("GET", "/materials")
        if response.success:
            return {"materials": response.data.get("materials", [])}
        return {"error": response.error}

    async def list_quality_presets(self) -> Dict[str, Any]:
        """List available quality presets."""
        response = await self._request("GET", "/quality")
        if response.success:
            return {"presets": response.data.get("presets", [])}
        return {"error": response.error}

    async def slice(
        self,
        stl_path: str,
        printer: str,
        quality: str = "normal",
        material: str = "pla",
        output_path: Optional[str] = None,
        supports: bool = False,
        infill: int = 20,
    ) -> Dict[str, Any]:
        """
        Slice an STL file to G-code.

        Args:
            stl_path: Path to input STL file
            printer: Printer profile name
            quality: Quality preset (draft, normal, quality, ultra)
            material: Material profile name
            output_path: Path for output G-code (optional, auto-generated if not provided)
            supports: Enable support material
            infill: Infill percentage (0-100)

        Returns:
            Slicing result with G-code path and stats
        """
        response = await self._request(
            "POST",
            "/slice",
            {
                "stl_path": stl_path,
                "printer": printer,
                "quality": quality,
                "material": material,
                "output_path": output_path,
                "supports": supports,
                "infill": infill,
            },
        )

        if response.success:
            return {
                "success": True,
                "gcode_path": response.data.get("gcode_path"),
                "print_time": response.data.get("print_time"),
                "filament_used": response.data.get("filament_used"),
                "layers": response.data.get("layers"),
                "warnings": response.data.get("warnings", []),
            }
        return {"success": False, "error": response.error}

    async def slice_lego(
        self,
        stl_path: str,
        printer: str = "prusa_mk3s",
        brick_type: str = "standard",
        output_path: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Slice an STL with LEGO-optimized settings.

        Uses special settings for:
        - Accurate stud dimensions
        - Proper fit tolerance
        - Strong layer adhesion

        Args:
            stl_path: Path to input STL
            printer: Printer profile
            brick_type: Type of brick for optimizations
            output_path: Output G-code path

        Returns:
            Slicing result
        """
        response = await self._request(
            "POST",
            "/slice/lego",
            {
                "stl_path": stl_path,
                "printer": printer,
                "brick_type": brick_type,
                "output_path": output_path,
            },
        )

        if response.success:
            return {
                "success": True,
                "gcode_path": response.data.get("gcode_path"),
                "print_time": response.data.get("print_time"),
                "filament_used": response.data.get("filament_used"),
                "settings_used": response.data.get("settings", {}),
                "optimizations": [
                    "LEGO-optimized layer height (0.12mm)",
                    "XY compensation for stud fit",
                    "Extra perimeters for strength",
                    "Optimized seam position",
                ],
            }
        return {"success": False, "error": response.error}

    async def estimate(
        self, stl_path: str, printer: str, quality: str = "normal"
    ) -> Dict[str, Any]:
        """
        Estimate print time and material without generating G-code.

        Args:
            stl_path: Path to STL file
            printer: Printer profile
            quality: Quality preset

        Returns:
            Estimation results
        """
        response = await self._request(
            "POST", "/estimate", {"stl_path": stl_path, "printer": printer, "quality": quality}
        )

        if response.success:
            return {
                "success": True,
                "estimated_time": response.data.get("estimated_time"),
                "estimated_filament_m": response.data.get("filament_m"),
                "estimated_filament_g": response.data.get("filament_g"),
                "layer_count": response.data.get("layers"),
                "note": "This is an estimate. Actual values may vary.",
            }
        return {"success": False, "error": response.error}

    async def batch_slice(
        self,
        stl_files: List[str],
        printer: str,
        quality: str = "normal",
        output_dir: str = "/output/gcode",
    ) -> Dict[str, Any]:
        """
        Slice multiple STL files in a batch.

        Args:
            stl_files: List of STL file paths
            printer: Printer profile
            quality: Quality preset
            output_dir: Output directory for G-code files

        Returns:
            Batch slicing results
        """
        response = await self._request(
            "POST",
            "/slice/batch",
            {
                "stl_files": stl_files,
                "printer": printer,
                "quality": quality,
                "output_dir": output_dir,
            },
        )

        if response.success:
            return {
                "success": True,
                "sliced": response.data.get("sliced", 0),
                "failed": response.data.get("failed", 0),
                "results": response.data.get("results", []),
                "total_time": response.data.get("total_time"),
                "total_filament": response.data.get("total_filament"),
            }
        return {"success": False, "error": response.error}

    async def upload_and_slice(
        self, stl_data: bytes, filename: str, printer: str, quality: str = "normal"
    ) -> Dict[str, Any]:
        """
        Upload STL data and slice it.

        For cases where the STL isn't on the filesystem.

        Args:
            stl_data: Raw STL file bytes
            filename: Name for the file
            printer: Printer profile
            quality: Quality preset

        Returns:
            Slicing result
        """
        try:
            session = await self._get_session()

            # Create multipart form data
            data = aiohttp.FormData()
            data.add_field(
                "file", stl_data, filename=filename, content_type="application/octet-stream"
            )
            data.add_field("printer", printer)
            data.add_field("quality", quality)

            async with session.post(f"{self.base_url}/slice/upload", data=data) as response:
                result = await response.json()

                if response.status == 200:
                    return {
                        "success": True,
                        "gcode_path": result.get("gcode_path"),
                        "print_time": result.get("print_time"),
                    }
                return {"success": False, "error": result.get("error")}

        except Exception as e:
            return {"success": False, "error": str(e)}


# ============================================================================
# CONVENIENCE FUNCTIONS
# ============================================================================


async def quick_slice(
    stl_path: str,
    printer: str = "prusa_mk3s",
    quality: str = "normal",
    base_url: str = "http://localhost:8081",
) -> Dict[str, Any]:
    """Quick function to slice an STL file."""
    client = SlicerClient(base_url)
    try:
        return await client.slice(stl_path, printer, quality)
    finally:
        await client.close()


async def quick_slice_lego(
    stl_path: str, printer: str = "prusa_mk3s", base_url: str = "http://localhost:8081"
) -> Dict[str, Any]:
    """Quick function to slice with LEGO-optimized settings."""
    client = SlicerClient(base_url)
    try:
        return await client.slice_lego(stl_path, printer)
    finally:
        await client.close()
