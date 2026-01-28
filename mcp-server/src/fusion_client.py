"""
Fusion 360 API Client

HTTP client for communicating with the Fusion 360 add-in's REST API.
Handles brick creation, export, preview generation, and CAM operations.
"""

import asyncio
import aiohttp
import json
import logging
from typing import Dict, Any, Optional, List
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class FusionResponse:
    """Response from Fusion 360 API."""

    success: bool
    data: Dict[str, Any]
    error: Optional[str] = None


class FusionClient:
    """
    Async HTTP client for Fusion 360 add-in API.
    """

    def __init__(self, base_url: str = "http://127.0.0.1:8767"):
        self.base_url = base_url.rstrip("/")
        self.timeout = aiohttp.ClientTimeout(total=120)
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
    ) -> FusionResponse:
        url = f"{self.base_url}{endpoint}"

        try:
            session = await self._get_session()
            async with session.request(method, url, json=data) as response:
                result = await response.json()
                if response.status == 200:
                    return FusionResponse(success=True, data=result)
                else:
                    return FusionResponse(
                        success=False, data={}, error=result.get("error", f"HTTP {response.status}")
                    )
        except aiohttp.ClientConnectorError:
            return FusionResponse(
                success=False, data={}, error="Cannot connect to Fusion 360. Is the add-in running?"
            )
        except asyncio.TimeoutError:
            return FusionResponse(success=False, data={}, error="Request timed out")
        except Exception as e:
            logger.error(f"Fusion API error: {e}")
            return FusionResponse(success=False, data={}, error=str(e))

    async def health_check(self) -> bool:
        try:
            response = await self._request("GET", "/health")
            return response.success
        except:
            return False

    async def create_brick(self, brick_definition: Dict[str, Any]) -> Dict[str, Any]:
        # Add-in expects command in body, not URL path
        data = {"command": "create_brick", "params": brick_definition}
        response = await self._request("POST", "/", data)
        if response.success:
            return {
                "success": True,
                "component_name": response.data.get("component_name"),
                "brick_id": response.data.get("brick_id"),
                "dimensions": response.data.get("dimensions"),
                "volume_mm3": response.data.get("volume_mm3"),
                "message": f"Created brick: {brick_definition.get('name', 'unnamed')}",
            }
        return {"success": False, "error": response.error}

    async def export_stl(
        self, component_name: str, output_path: str, refinement: str = "medium"
    ) -> Dict[str, Any]:
        # Add-in expects command in body, not URL path
        data = {
            "command": "export_stl",
            "params": {
                "component_name": component_name,
                "output_path": output_path,
                "resolution": refinement,  # add-in uses 'resolution' not 'refinement'
            },
        }
        response = await self._request("POST", "/", data)
        if response.success:
            return {
                "success": True,
                "format": "stl",
                "output_path": response.data.get("path", output_path),
                "size_kb": response.data.get("size_kb"),
                "triangle_count": response.data.get("triangle_count"),
            }
        return {"success": False, "error": response.error}

    async def export_step(self, component_name: str, output_path: str) -> Dict[str, Any]:
        """Export component as STEP file for CAD exchange."""
        data = {
            "command": "export_step",
            "params": {
                "component_name": component_name,
                "output_path": output_path,
            },
        }
        response = await self._request("POST", "/", data)
        if response.success:
            return {
                "success": True,
                "format": "step",
                "output_path": response.data.get("path", output_path),
                "size_kb": response.data.get("size_kb"),
            }
        return {"success": False, "error": response.error}

    async def export_3mf(self, component_name: str, output_path: str) -> Dict[str, Any]:
        """Export component as 3MF file for 3D printing."""
        data = {
            "command": "export_3mf",
            "params": {
                "component_name": component_name,
                "output_path": output_path,
            },
        }
        response = await self._request("POST", "/", data)
        if response.success:
            return {
                "success": True,
                "format": "3mf",
                "output_path": response.data.get("path", output_path),
                "size_kb": response.data.get("size_kb"),
            }
        return {"success": False, "error": response.error}

    async def generate_preview(
        self,
        component_name: str,
        output_path: str,
        view: str = "isometric",
        width: int = 800,
        height: int = 600,
    ) -> Dict[str, Any]:
        # Note: preview generation not in add-in yet
        return {"success": False, "error": "Preview generation not yet implemented in Fusion 360 add-in"}

    async def generate_cam_setup(
        self, component_name: str, machine: str = "generic_3axis", material: str = "abs"
    ) -> Dict[str, Any]:
        # Add-in expects command in body
        data = {
            "command": "setup_cam",
            "params": {
                "component_name": component_name,
                "machine": machine,
                "material": material,
            },
        }
        response = await self._request("POST", "/", data)
        return response.data if response.success else {"success": False, "error": response.error}

    async def post_process(
        self, setup_name: str, output_path: str, post_processor: str = "grbl"
    ) -> Dict[str, Any]:
        # Add-in expects command in body
        data = {
            "command": "generate_gcode",
            "params": {
                "component_name": setup_name,
                "output_path": output_path,
                "machine": post_processor,
            },
        }
        response = await self._request("POST", "/", data)
        if response.success:
            return {"success": True, "output_path": output_path, "post_processor": post_processor}
        return {"success": False, "error": response.error}

    async def create_technic_brick(
        self, studs_x: int, studs_y: int, hole_axis: str = "x", name: str = None
    ) -> Dict[str, Any]:
        """Create a Technic brick with pin holes."""
        data = {
            "command": "create_technic",
            "params": {
                "studs_x": studs_x,
                "studs_y": studs_y,
                "hole_axis": hole_axis,
                "name": name,
            },
        }
        response = await self._request("POST", "/", data)
        if response.success:
            return {
                "success": True,
                "component_name": response.data.get("component_name"),
                "brick_id": response.data.get("brick_id"),
                "dimensions": response.data.get("dimensions"),
                "volume_mm3": response.data.get("volume_mm3"),
                "message": f"Created Technic brick: {studs_x}x{studs_y}",
            }
        return {"success": False, "error": response.error}

    async def create_round_brick(
        self, diameter_studs: int, height_units: float = 1.0, name: str = None
    ) -> Dict[str, Any]:
        """Create a cylindrical round brick."""
        data = {
            "command": "create_round",
            "params": {
                "diameter_studs": diameter_studs,
                "height_units": height_units,
                "name": name,
            },
        }
        response = await self._request("POST", "/", data)
        if response.success:
            return {
                "success": True,
                "component_name": response.data.get("component_name"),
                "brick_id": response.data.get("brick_id"),
                "dimensions": response.data.get("dimensions"),
                "volume_mm3": response.data.get("volume_mm3"),
                "message": f"Created round brick: {diameter_studs}x{diameter_studs}",
            }
        return {"success": False, "error": response.error}

    async def create_arch(
        self, studs_x: int, studs_y: int, arch_height: int = 1, name: str = None
    ) -> Dict[str, Any]:
        """Create an arch brick."""
        data = {
            "command": "create_arch",
            "params": {
                "studs_x": studs_x,
                "studs_y": studs_y,
                "arch_height": arch_height,
                "name": name,
            },
        }
        response = await self._request("POST", "/", data)
        if response.success:
            return {
                "success": True,
                "component_name": response.data.get("component_name"),
                "brick_id": response.data.get("brick_id"),
                "dimensions": response.data.get("dimensions"),
                "volume_mm3": response.data.get("volume_mm3"),
                "message": f"Created arch brick: {studs_x}x{studs_y}",
            }
        return {"success": False, "error": response.error}

    async def generate_preview(
        self,
        component_name: str,
        output_path: str,
        view: str = "isometric",
        width: int = 800,
        height: int = 600,
    ) -> Dict[str, Any]:
        """Generate a preview image of a component."""
        data = {
            "command": "generate_preview",
            "params": {
                "component_name": component_name,
                "output_path": output_path,
                "view": view,
                "width": width,
                "height": height,
            },
        }
        response = await self._request("POST", "/", data)
        if response.success:
            return {
                "success": True,
                "path": response.data.get("path", output_path),
                "width": response.data.get("width", width),
                "height": response.data.get("height", height),
                "size_kb": response.data.get("size_kb"),
                "view": response.data.get("view", view),
            }
        return {"success": False, "error": response.error}

    async def generate_thumbnail(
        self,
        component_name: str,
        output_path: str,
        size: int = 256,
    ) -> Dict[str, Any]:
        """Generate a thumbnail image of a component."""
        data = {
            "command": "generate_thumbnail",
            "params": {
                "component_name": component_name,
                "output_path": output_path,
                "size": size,
            },
        }
        response = await self._request("POST", "/", data)
        if response.success:
            return {
                "success": True,
                "path": response.data.get("path", output_path),
                "size": response.data.get("width", size),
                "size_kb": response.data.get("size_kb"),
            }
        return {"success": False, "error": response.error}
