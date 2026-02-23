"""
OctoPrint Protocol - OctoPrint API adapter.

LEGO MCP v6.0 World-Class Manufacturing Research Platform
Phase 5: Algorithm-to-Action Bridge
"""

from typing import Any, Dict, List, Optional
import logging
import aiohttp

logger = logging.getLogger(__name__)


class OctoPrintProtocol:
    """
    OctoPrint REST API protocol adapter.

    Communicates with OctoPrint server for printer control.
    """

    def __init__(self,
                 host: str = "localhost",
                 port: int = 5000,
                 api_key: str = ""):
        self.host = host
        self.port = port
        self.api_key = api_key
        self.base_url = f"http://{host}:{port}/api"
        self._session: Optional[aiohttp.ClientSession] = None

    async def connect(self) -> bool:
        """Connect to OctoPrint server."""
        try:
            self._session = aiohttp.ClientSession(
                headers={"X-Api-Key": self.api_key}
            )
            # Test connection
            async with self._session.get(f"{self.base_url}/version") as resp:
                if resp.status == 200:
                    data = await resp.json()
                    logger.info(f"Connected to OctoPrint {data.get('text', 'unknown')}")
                    return True
                else:
                    logger.error(f"OctoPrint connection failed: {resp.status}")
                    return False
        except Exception as e:
            logger.error(f"OctoPrint connection error: {e}")
            return False

    async def disconnect(self) -> None:
        """Disconnect from OctoPrint."""
        if self._session:
            await self._session.close()
            self._session = None

    async def send_gcode(self, commands: List[str]) -> str:
        """Send G-code commands to printer."""
        if not self._session:
            raise ConnectionError("Not connected to OctoPrint")

        payload = {"commands": commands}

        try:
            async with self._session.post(
                f"{self.base_url}/printer/command",
                json=payload
            ) as resp:
                if resp.status == 204:
                    return "OK"
                else:
                    text = await resp.text()
                    return f"Error: {resp.status} - {text}"
        except Exception as e:
            return f"Error: {str(e)}"

    async def get_status(self) -> Dict[str, Any]:
        """Get printer status."""
        if not self._session:
            return {"error": "Not connected"}

        try:
            async with self._session.get(f"{self.base_url}/printer") as resp:
                if resp.status == 200:
                    return await resp.json()
                else:
                    return {"error": f"Status code: {resp.status}"}
        except Exception as e:
            return {"error": str(e)}

    async def get_temperatures(self) -> Dict[str, float]:
        """Get current temperatures."""
        status = await self.get_status()

        if "error" in status:
            return {}

        temps = {}
        temp_data = status.get("temperature", {})

        if "tool0" in temp_data:
            temps["nozzle"] = temp_data["tool0"].get("actual", 0)
            temps["nozzle_target"] = temp_data["tool0"].get("target", 0)

        if "bed" in temp_data:
            temps["bed"] = temp_data["bed"].get("actual", 0)
            temps["bed_target"] = temp_data["bed"].get("target", 0)

        return temps

    async def get_job_info(self) -> Dict[str, Any]:
        """Get current job information."""
        if not self._session:
            return {"error": "Not connected"}

        try:
            async with self._session.get(f"{self.base_url}/job") as resp:
                if resp.status == 200:
                    return await resp.json()
                return {}
        except Exception as e:
            return {"error": str(e)}

    async def pause_print(self) -> bool:
        """Pause current print."""
        return await self._job_command("pause", "pause")

    async def resume_print(self) -> bool:
        """Resume paused print."""
        return await self._job_command("pause", "resume")

    async def cancel_print(self) -> bool:
        """Cancel current print."""
        return await self._job_command("cancel")

    async def _job_command(self, command: str, action: str = None) -> bool:
        """Send job command."""
        if not self._session:
            return False

        payload = {"command": command}
        if action:
            payload["action"] = action

        try:
            async with self._session.post(
                f"{self.base_url}/job",
                json=payload
            ) as resp:
                return resp.status == 204
        except Exception as e:
            logger.error(f"Job command error: {e}")
            return False
