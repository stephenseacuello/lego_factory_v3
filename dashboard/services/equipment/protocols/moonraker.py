"""
Moonraker Protocol - Moonraker/Klipper API adapter.

LEGO MCP v6.0 World-Class Manufacturing Research Platform
Phase 5: Algorithm-to-Action Bridge
"""

from typing import Any, Dict, List, Optional
import logging
import aiohttp
import json

logger = logging.getLogger(__name__)


class MoonrakerProtocol:
    """
    Moonraker API protocol adapter.

    Communicates with Moonraker (Klipper) for printer control.
    """

    def __init__(self,
                 host: str = "localhost",
                 port: int = 7125):
        self.host = host
        self.port = port
        self.base_url = f"http://{host}:{port}"
        self._session: Optional[aiohttp.ClientSession] = None

    async def connect(self) -> bool:
        """Connect to Moonraker server."""
        try:
            self._session = aiohttp.ClientSession()

            # Test connection
            async with self._session.get(f"{self.base_url}/server/info") as resp:
                if resp.status == 200:
                    data = await resp.json()
                    result = data.get("result", {})
                    logger.info(f"Connected to Moonraker - Klipper {result.get('klippy_state', 'unknown')}")
                    return True
                else:
                    logger.error(f"Moonraker connection failed: {resp.status}")
                    return False
        except Exception as e:
            logger.error(f"Moonraker connection error: {e}")
            return False

    async def disconnect(self) -> None:
        """Disconnect from Moonraker."""
        if self._session:
            await self._session.close()
            self._session = None

    async def send_gcode(self, commands: List[str]) -> str:
        """Send G-code commands to printer."""
        if not self._session:
            raise ConnectionError("Not connected to Moonraker")

        gcode_script = "\n".join(commands)

        try:
            async with self._session.post(
                f"{self.base_url}/printer/gcode/script",
                params={"script": gcode_script}
            ) as resp:
                if resp.status == 200:
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
            objects = "extruder,heater_bed,print_stats,virtual_sdcard"
            async with self._session.get(
                f"{self.base_url}/printer/objects/query",
                params={"extruder": None, "heater_bed": None, "print_stats": None}
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data.get("result", {}).get("status", {})
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

        extruder = status.get("extruder", {})
        if extruder:
            temps["nozzle"] = extruder.get("temperature", 0)
            temps["nozzle_target"] = extruder.get("target", 0)

        bed = status.get("heater_bed", {})
        if bed:
            temps["bed"] = bed.get("temperature", 0)
            temps["bed_target"] = bed.get("target", 0)

        return temps

    async def get_job_info(self) -> Dict[str, Any]:
        """Get current job information."""
        status = await self.get_status()

        if "error" in status:
            return status

        print_stats = status.get("print_stats", {})
        virtual_sdcard = status.get("virtual_sdcard", {})

        return {
            "state": print_stats.get("state", "unknown"),
            "filename": print_stats.get("filename", ""),
            "print_duration": print_stats.get("print_duration", 0),
            "progress": virtual_sdcard.get("progress", 0)
        }

    async def pause_print(self) -> bool:
        """Pause current print."""
        result = await self.send_gcode(["PAUSE"])
        return "OK" in result

    async def resume_print(self) -> bool:
        """Resume paused print."""
        result = await self.send_gcode(["RESUME"])
        return "OK" in result

    async def cancel_print(self) -> bool:
        """Cancel current print."""
        result = await self.send_gcode(["CANCEL_PRINT"])
        return "OK" in result

    async def emergency_stop(self) -> bool:
        """Emergency stop."""
        try:
            async with self._session.post(
                f"{self.base_url}/printer/emergency_stop"
            ) as resp:
                return resp.status == 200
        except Exception as e:
            logger.error(f"Emergency stop error: {e}")
            return False

    async def firmware_restart(self) -> bool:
        """Restart Klipper firmware."""
        try:
            async with self._session.post(
                f"{self.base_url}/printer/firmware_restart"
            ) as resp:
                return resp.status == 200
        except Exception as e:
            logger.error(f"Firmware restart error: {e}")
            return False
