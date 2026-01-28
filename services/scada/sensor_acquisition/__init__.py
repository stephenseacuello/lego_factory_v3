"""
LEGO Factory v3 - Sensor Acquisition Services
==============================================
Real-time sensor data collection and processing.
"""

from .sensor_service import (
    SensorService,
    SensorConfig,
    SensorType,
    DataQuality,
    get_sensor_service,
)

__all__ = [
    'SensorService',
    'SensorConfig',
    'SensorType',
    'DataQuality',
    'get_sensor_service',
]
