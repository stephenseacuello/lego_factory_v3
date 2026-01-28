"""
3D Printer Controller - Multi-protocol printer integration.

Supports:
- OctoPrint REST API (most common)
- Bambu Lab Cloud API
- Prusa Connect API
- Klipper/Moonraker API
"""

import asyncio
import aiohttp
import logging
from datetime import datetime
from typing import Optional, Dict, Any, List
from enum import Enum

from .base_controller import (
    BaseEquipmentController,
    EquipmentState,
    EquipmentStatus,
    JobStatus,
    JobResult
)

logger = logging.getLogger(__name__)


class PrinterProtocol(Enum):
    """Supported printer communication protocols."""
    OCTOPRINT = "octoprint"
    BAMBU = "bambu"
    PRUSA_CONNECT = "prusa_connect"
    MOONRAKER = "moonraker"  # Klipper


class PrinterController(BaseEquipmentController):
    """
    3D Printer Controller with multi-protocol support.

    Connection info structure:
    {
        "protocol": "octoprint",  # or "bambu", "prusa_connect", "moonraker"
        "host": "192.168.1.100",
        "port": 80,
        "api_key": "xxx",  # OctoPrint/Moonraker API key
        "access_code": "xxx",  # Bambu Lab access code
        "serial": "xxx",  # Bambu Lab printer serial
        "ssl": false
    }
    """

    def __init__(
        self,
        work_center_id: str,
        name: str,
        connection_info: Dict[str, Any]
    ):
        super().__init__(work_center_id, name, connection_info)
        self.protocol = PrinterProtocol(
            connection_info.get('protocol', 'octoprint')
        )
        self._session: Optional[aiohttp.ClientSession] = None
        self._current_job_id: Optional[str] = None
        self._job_start_time: Optional[datetime] = None

    @property
    def base_url(self) -> str:
        """Build base URL from connection info."""
        host = self.connection_info.get('host', 'localhost')
        port = self.connection_info.get('port', 80)
        ssl = self.connection_info.get('ssl', False)
        scheme = 'https' if ssl else 'http'
        return f"{scheme}://{host}:{port}"

    @property
    def headers(self) -> Dict[str, str]:
        """Build request headers with authentication."""
        headers = {'Content-Type': 'application/json'}

        if self.protocol == PrinterProtocol.OCTOPRINT:
            api_key = self.connection_info.get('api_key', '')
            headers['X-Api-Key'] = api_key

        elif self.protocol == PrinterProtocol.MOONRAKER:
            api_key = self.connection_info.get('api_key')
            if api_key:
                headers['Authorization'] = f'Bearer {api_key}'

        elif self.protocol == PrinterProtocol.PRUSA_CONNECT:
            api_key = self.connection_info.get('api_key', '')
            headers['X-Api-Key'] = api_key

        return headers

    # Connection Management

    async def connect(self) -> bool:
        """Establish connection to printer."""
        try:
            if self._session is None:
                timeout = aiohttp.ClientTimeout(total=10)
                self._session = aiohttp.ClientSession(
                    headers=self.headers,
                    timeout=timeout
                )

            # Verify connection with ping
            if await self.ping():
                self._connected = True
                logger.info(f"Connected to printer: {self.name}")
                return True

            return False

        except Exception as e:
            logger.error(f"Failed to connect to {self.name}: {e}")
            self._connected = False
            return False

    async def disconnect(self):
        """Disconnect from printer."""
        if self._session:
            await self._session.close()
            self._session = None
        self._connected = False
        logger.info(f"Disconnected from printer: {self.name}")

    async def ping(self) -> bool:
        """Check if printer is responsive."""
        try:
            if self.protocol == PrinterProtocol.OCTOPRINT:
                async with self._session.get(f"{self.base_url}/api/version") as resp:
                    return resp.status == 200

            elif self.protocol == PrinterProtocol.MOONRAKER:
                async with self._session.get(f"{self.base_url}/server/info") as resp:
                    return resp.status == 200

            elif self.protocol == PrinterProtocol.PRUSA_CONNECT:
                async with self._session.get(f"{self.base_url}/api/v1/status") as resp:
                    return resp.status == 200

            elif self.protocol == PrinterProtocol.BAMBU:
                # Bambu uses MQTT, simplified check
                return True

        except Exception as e:
            logger.debug(f"Ping failed for {self.name}: {e}")
            return False

    # Status Monitoring

    async def get_state(self) -> EquipmentState:
        """Get current printer state."""
        try:
            if self.protocol == PrinterProtocol.OCTOPRINT:
                return await self._get_octoprint_state()
            elif self.protocol == PrinterProtocol.MOONRAKER:
                return await self._get_moonraker_state()
            elif self.protocol == PrinterProtocol.PRUSA_CONNECT:
                return await self._get_prusa_state()
            elif self.protocol == PrinterProtocol.BAMBU:
                return await self._get_bambu_state()

        except Exception as e:
            logger.error(f"Failed to get state from {self.name}: {e}")
            return EquipmentState(
                status=EquipmentStatus.ERROR,
                error_message=str(e)
            )

    async def _get_octoprint_state(self) -> EquipmentState:
        """Get state from OctoPrint API."""
        async with self._session.get(f"{self.base_url}/api/printer") as resp:
            if resp.status == 409:
                # Printer not connected
                return EquipmentState(status=EquipmentStatus.OFFLINE)

            data = await resp.json()

        # Get job info
        async with self._session.get(f"{self.base_url}/api/job") as resp:
            job_data = await resp.json()

        # Parse state
        state_flags = data.get('state', {}).get('flags', {})
        temps = data.get('temperature', {})

        if state_flags.get('error'):
            status = EquipmentStatus.ERROR
        elif state_flags.get('printing'):
            status = EquipmentStatus.RUNNING
        elif state_flags.get('paused'):
            status = EquipmentStatus.PAUSED
        elif state_flags.get('operational'):
            status = EquipmentStatus.IDLE
        else:
            status = EquipmentStatus.OFFLINE

        # Extract temperatures
        temperatures = {}
        for key, val in temps.items():
            if isinstance(val, dict):
                temperatures[f"{key}_actual"] = val.get('actual', 0)
                temperatures[f"{key}_target"] = val.get('target', 0)

        # Job progress
        progress = job_data.get('progress', {})
        job_progress = progress.get('completion', 0) or 0
        time_elapsed = progress.get('printTime', 0) or 0
        time_remaining = progress.get('printTimeLeft', 0) or 0

        return EquipmentState(
            status=status,
            current_job_id=self._current_job_id,
            job_progress_percent=job_progress,
            job_elapsed_seconds=time_elapsed,
            job_remaining_seconds=time_remaining,
            temperatures=temperatures,
            extra_data={
                'file': job_data.get('job', {}).get('file', {}).get('name'),
                'state_text': data.get('state', {}).get('text', '')
            }
        )

    async def _get_moonraker_state(self) -> EquipmentState:
        """Get state from Moonraker/Klipper API."""
        async with self._session.get(
            f"{self.base_url}/printer/objects/query",
            params={'print_stats': None, 'heater_bed': None, 'extruder': None}
        ) as resp:
            data = await resp.json()

        result = data.get('result', {}).get('status', {})
        print_stats = result.get('print_stats', {})
        heater_bed = result.get('heater_bed', {})
        extruder = result.get('extruder', {})

        state_str = print_stats.get('state', 'standby')
        status_map = {
            'standby': EquipmentStatus.IDLE,
            'printing': EquipmentStatus.RUNNING,
            'paused': EquipmentStatus.PAUSED,
            'complete': EquipmentStatus.IDLE,
            'cancelled': EquipmentStatus.IDLE,
            'error': EquipmentStatus.ERROR
        }
        status = status_map.get(state_str, EquipmentStatus.OFFLINE)

        return EquipmentState(
            status=status,
            current_job_id=self._current_job_id,
            job_progress_percent=print_stats.get('progress', 0) * 100,
            job_elapsed_seconds=print_stats.get('print_duration', 0),
            temperatures={
                'bed_actual': heater_bed.get('temperature', 0),
                'bed_target': heater_bed.get('target', 0),
                'tool0_actual': extruder.get('temperature', 0),
                'tool0_target': extruder.get('target', 0)
            },
            extra_data={'filename': print_stats.get('filename', '')}
        )

    async def _get_prusa_state(self) -> EquipmentState:
        """Get state from Prusa Connect API."""
        async with self._session.get(f"{self.base_url}/api/v1/status") as resp:
            data = await resp.json()

        printer_state = data.get('printer', {}).get('state', 'IDLE')
        status_map = {
            'IDLE': EquipmentStatus.IDLE,
            'PRINTING': EquipmentStatus.RUNNING,
            'PAUSED': EquipmentStatus.PAUSED,
            'FINISHED': EquipmentStatus.IDLE,
            'STOPPED': EquipmentStatus.IDLE,
            'ERROR': EquipmentStatus.ERROR,
            'ATTENTION': EquipmentStatus.ERROR
        }
        status = status_map.get(printer_state, EquipmentStatus.OFFLINE)

        job = data.get('job', {})

        return EquipmentState(
            status=status,
            current_job_id=self._current_job_id,
            job_progress_percent=job.get('progress', 0),
            job_elapsed_seconds=job.get('time_printing', 0),
            job_remaining_seconds=job.get('time_remaining', 0),
            temperatures={
                'bed_actual': data.get('printer', {}).get('temp_bed', 0),
                'tool0_actual': data.get('printer', {}).get('temp_nozzle', 0)
            }
        )

    async def _get_bambu_state(self) -> EquipmentState:
        """Get state from Bambu Lab printer (MQTT-based, simplified)."""
        # Bambu Lab uses MQTT protocol - this is a placeholder
        # Full implementation requires bambu-lab Python client
        logger.warning("Bambu Lab integration requires MQTT client - returning mock state")
        return EquipmentState(
            status=EquipmentStatus.OFFLINE,
            extra_data={'note': 'Bambu MQTT integration pending'}
        )

    async def get_capabilities(self) -> Dict[str, Any]:
        """Get printer capabilities."""
        try:
            if self.protocol == PrinterProtocol.OCTOPRINT:
                async with self._session.get(f"{self.base_url}/api/printerprofiles") as resp:
                    data = await resp.json()

                profiles = data.get('profiles', {})
                default_profile = profiles.get('_default', {})

                return {
                    'name': default_profile.get('name', self.name),
                    'model': default_profile.get('model', 'Unknown'),
                    'build_volume': {
                        'x': default_profile.get('volume', {}).get('width', 0),
                        'y': default_profile.get('volume', {}).get('depth', 0),
                        'z': default_profile.get('volume', {}).get('height', 0)
                    },
                    'heated_bed': default_profile.get('heatedBed', False),
                    'heated_chamber': default_profile.get('heatedChamber', False),
                    'extruder_count': default_profile.get('extruder', {}).get('count', 1)
                }

            elif self.protocol == PrinterProtocol.MOONRAKER:
                async with self._session.get(f"{self.base_url}/printer/info") as resp:
                    data = await resp.json()
                return data.get('result', {})

            else:
                return {'protocol': self.protocol.value}

        except Exception as e:
            logger.error(f"Failed to get capabilities: {e}")
            return {}

    # Job Control

    async def submit_job(
        self,
        job_id: str,
        file_path: str,
        parameters: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Submit a G-code file for printing."""
        try:
            if self.protocol == PrinterProtocol.OCTOPRINT:
                return await self._octoprint_submit_job(job_id, file_path)
            elif self.protocol == PrinterProtocol.MOONRAKER:
                return await self._moonraker_submit_job(job_id, file_path)
            else:
                logger.warning(f"Job submission not implemented for {self.protocol}")
                return False

        except Exception as e:
            logger.error(f"Failed to submit job: {e}")
            return False

    async def _octoprint_submit_job(self, job_id: str, file_path: str) -> bool:
        """Upload and select file in OctoPrint."""
        import os

        # Upload file
        filename = os.path.basename(file_path)
        with open(file_path, 'rb') as f:
            form = aiohttp.FormData()
            form.add_field('file', f, filename=filename)
            form.add_field('select', 'true')

            async with self._session.post(
                f"{self.base_url}/api/files/local",
                data=form,
                headers={'X-Api-Key': self.connection_info.get('api_key', '')}
            ) as resp:
                if resp.status in (200, 201):
                    self._current_job_id = job_id
                    self._job_start_time = None
                    logger.info(f"Uploaded and selected: {filename}")
                    return True
                else:
                    text = await resp.text()
                    logger.error(f"Upload failed: {text}")
                    return False

    async def _moonraker_submit_job(self, job_id: str, file_path: str) -> bool:
        """Upload file to Moonraker."""
        import os

        filename = os.path.basename(file_path)
        with open(file_path, 'rb') as f:
            form = aiohttp.FormData()
            form.add_field('file', f, filename=filename)

            async with self._session.post(
                f"{self.base_url}/server/files/upload",
                data=form
            ) as resp:
                if resp.status == 201:
                    self._current_job_id = job_id
                    return True
                return False

    async def start_job(self) -> bool:
        """Start the selected print job."""
        try:
            if self.protocol == PrinterProtocol.OCTOPRINT:
                async with self._session.post(
                    f"{self.base_url}/api/job",
                    json={'command': 'start'}
                ) as resp:
                    if resp.status == 204:
                        self._job_start_time = datetime.utcnow()
                        return True
                    return False

            elif self.protocol == PrinterProtocol.MOONRAKER:
                state = await self.get_state()
                filename = state.extra_data.get('filename', '')
                if filename:
                    async with self._session.post(
                        f"{self.base_url}/printer/print/start",
                        json={'filename': filename}
                    ) as resp:
                        if resp.status == 200:
                            self._job_start_time = datetime.utcnow()
                            return True
                return False

            else:
                logger.warning(f"Start job not implemented for {self.protocol}")
                return False

        except Exception as e:
            logger.error(f"Failed to start job: {e}")
            return False

    async def pause_job(self) -> bool:
        """Pause the current print."""
        try:
            if self.protocol == PrinterProtocol.OCTOPRINT:
                async with self._session.post(
                    f"{self.base_url}/api/job",
                    json={'command': 'pause', 'action': 'pause'}
                ) as resp:
                    return resp.status == 204

            elif self.protocol == PrinterProtocol.MOONRAKER:
                async with self._session.post(
                    f"{self.base_url}/printer/print/pause"
                ) as resp:
                    return resp.status == 200

            return False

        except Exception as e:
            logger.error(f"Failed to pause job: {e}")
            return False

    async def resume_job(self) -> bool:
        """Resume a paused print."""
        try:
            if self.protocol == PrinterProtocol.OCTOPRINT:
                async with self._session.post(
                    f"{self.base_url}/api/job",
                    json={'command': 'pause', 'action': 'resume'}
                ) as resp:
                    return resp.status == 204

            elif self.protocol == PrinterProtocol.MOONRAKER:
                async with self._session.post(
                    f"{self.base_url}/printer/print/resume"
                ) as resp:
                    return resp.status == 200

            return False

        except Exception as e:
            logger.error(f"Failed to resume job: {e}")
            return False

    async def cancel_job(self) -> bool:
        """Cancel the current print."""
        try:
            job_id = self._current_job_id
            start_time = self._job_start_time or datetime.utcnow()

            if self.protocol == PrinterProtocol.OCTOPRINT:
                async with self._session.post(
                    f"{self.base_url}/api/job",
                    json={'command': 'cancel'}
                ) as resp:
                    if resp.status == 204:
                        self._current_job_id = None
                        self._job_start_time = None
                        return True
                    return False

            elif self.protocol == PrinterProtocol.MOONRAKER:
                async with self._session.post(
                    f"{self.base_url}/printer/print/cancel"
                ) as resp:
                    if resp.status == 200:
                        self._current_job_id = None
                        return True
                    return False

            return False

        except Exception as e:
            logger.error(f"Failed to cancel job: {e}")
            return False

    async def get_job_result(self, job_id: str) -> Optional[JobResult]:
        """Get result of a completed print job."""
        # In a real implementation, this would query job history
        # For now, return None - job tracking would be in the database
        return None

    # Equipment Control

    async def home(self) -> bool:
        """Home all printer axes."""
        try:
            if self.protocol == PrinterProtocol.OCTOPRINT:
                async with self._session.post(
                    f"{self.base_url}/api/printer/printhead",
                    json={'command': 'home', 'axes': ['x', 'y', 'z']}
                ) as resp:
                    return resp.status == 204

            elif self.protocol == PrinterProtocol.MOONRAKER:
                async with self._session.post(
                    f"{self.base_url}/printer/gcode/script",
                    json={'script': 'G28'}
                ) as resp:
                    return resp.status == 200

            return False

        except Exception as e:
            logger.error(f"Failed to home: {e}")
            return False

    async def emergency_stop(self) -> bool:
        """Emergency stop the printer."""
        try:
            if self.protocol == PrinterProtocol.OCTOPRINT:
                # Send M112 emergency stop
                async with self._session.post(
                    f"{self.base_url}/api/printer/command",
                    json={'command': 'M112'}
                ) as resp:
                    return resp.status == 204

            elif self.protocol == PrinterProtocol.MOONRAKER:
                async with self._session.post(
                    f"{self.base_url}/printer/emergency_stop"
                ) as resp:
                    return resp.status == 200

            return False

        except Exception as e:
            logger.error(f"Failed to emergency stop: {e}")
            return False

    # Printer-specific methods

    async def set_temperature(
        self,
        tool: str = "tool0",
        temperature: float = 0
    ) -> bool:
        """
        Set target temperature.

        Args:
            tool: "tool0", "tool1", "bed", "chamber"
            temperature: Target temperature in Celsius
        """
        try:
            if self.protocol == PrinterProtocol.OCTOPRINT:
                if tool.startswith("tool"):
                    endpoint = f"{self.base_url}/api/printer/tool"
                    json_data = {'command': 'target', 'targets': {tool: temperature}}
                elif tool == "bed":
                    endpoint = f"{self.base_url}/api/printer/bed"
                    json_data = {'command': 'target', 'target': temperature}
                else:
                    return False

                async with self._session.post(endpoint, json=json_data) as resp:
                    return resp.status == 204

            elif self.protocol == PrinterProtocol.MOONRAKER:
                if tool.startswith("tool"):
                    gcode = f"M104 T{tool[-1]} S{temperature}"
                elif tool == "bed":
                    gcode = f"M140 S{temperature}"
                else:
                    return False

                async with self._session.post(
                    f"{self.base_url}/printer/gcode/script",
                    json={'script': gcode}
                ) as resp:
                    return resp.status == 200

            return False

        except Exception as e:
            logger.error(f"Failed to set temperature: {e}")
            return False

    async def get_files(self) -> List[Dict[str, Any]]:
        """Get list of files on the printer."""
        try:
            if self.protocol == PrinterProtocol.OCTOPRINT:
                async with self._session.get(f"{self.base_url}/api/files") as resp:
                    data = await resp.json()
                    files = data.get('files', [])
                    return [
                        {
                            'name': f.get('name'),
                            'path': f.get('path'),
                            'size': f.get('size'),
                            'date': f.get('date')
                        }
                        for f in files
                        if f.get('type') == 'machinecode'
                    ]

            elif self.protocol == PrinterProtocol.MOONRAKER:
                async with self._session.get(
                    f"{self.base_url}/server/files/list"
                ) as resp:
                    data = await resp.json()
                    return data.get('result', [])

            return []

        except Exception as e:
            logger.error(f"Failed to get files: {e}")
            return []
