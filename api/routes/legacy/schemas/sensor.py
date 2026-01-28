"""
Pydantic schemas for sensor-related API endpoints.
"""

from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field, field_validator


class SensorConfigRequest(BaseModel):
    """Request to configure sensor connection."""

    port: str = Field(
        ...,
        min_length=1,
        max_length=256,
        description="Serial port path for sensor connection"
    )
    baud: int = Field(
        default=115200,
        ge=9600,
        le=921600,
        description="Baud rate for serial communication"
    )
    sensor_id: str = Field(
        ...,
        min_length=1,
        max_length=64,
        pattern="^[a-zA-Z0-9_-]+$",
        description="Unique sensor identifier"
    )
    machine_id: Optional[str] = Field(
        None,
        max_length=64,
        pattern="^[a-zA-Z0-9_-]+$",
        description="Associated machine identifier"
    )

    @field_validator("port")
    @classmethod
    def validate_port(cls, v: str) -> str:
        """Validate serial port path."""
        valid_prefixes = ("/dev/tty", "/dev/cu.", "COM", "/dev/serial")
        if not any(v.startswith(prefix) for prefix in valid_prefixes):
            raise ValueError(
                f"Invalid serial port. Must start with one of: {valid_prefixes}"
            )
        return v


class SensorDataRequest(BaseModel):
    """Request to write sensor data manually."""

    sensor_id: str = Field(
        ...,
        pattern="^[a-zA-Z0-9_-]+$",
        description="Sensor identifier"
    )
    timestamp: Optional[float] = Field(
        None,
        ge=0,
        description="Unix timestamp (uses current time if not provided)"
    )
    data: Dict[str, Any] = Field(
        ...,
        description="Sensor readings"
    )


class SensorPollingRequest(BaseModel):
    """Request to start/configure sensor polling."""

    interval: float = Field(
        default=0.1,
        ge=0.01,
        le=10.0,
        description="Polling interval in seconds"
    )
    log_to_file: bool = Field(
        default=True,
        description="Whether to log data to CSV file"
    )
    publish_mqtt: bool = Field(
        default=True,
        description="Whether to publish to MQTT"
    )
    write_influxdb: bool = Field(
        default=True,
        description="Whether to write to InfluxDB"
    )


class IMUData(BaseModel):
    """IMU sensor data (accelerometer, gyroscope)."""

    ax: float = Field(..., description="Accelerometer X (g)")
    ay: float = Field(..., description="Accelerometer Y (g)")
    az: float = Field(..., description="Accelerometer Z (g)")
    gx: float = Field(..., description="Gyroscope X (deg/s)")
    gy: float = Field(..., description="Gyroscope Y (deg/s)")
    gz: float = Field(..., description="Gyroscope Z (deg/s)")
    mx: Optional[float] = Field(None, description="Magnetometer X")
    my: Optional[float] = Field(None, description="Magnetometer Y")
    mz: Optional[float] = Field(None, description="Magnetometer Z")


class EnvironmentalData(BaseModel):
    """Environmental sensor data."""

    pressure: Optional[float] = Field(None, ge=0, description="Pressure (Pa)")
    temperature: Optional[float] = Field(
        None,
        ge=-50,
        le=150,
        description="Temperature (°C)"
    )
    humidity: Optional[float] = Field(
        None,
        ge=0,
        le=100,
        description="Relative humidity (%)"
    )
    proximity: Optional[int] = Field(
        None,
        ge=0,
        description="Proximity sensor reading"
    )


class ColorSensorData(BaseModel):
    """Color/light sensor data."""

    r: int = Field(..., ge=0, le=65535, description="Red channel")
    g: int = Field(..., ge=0, le=65535, description="Green channel")
    b: int = Field(..., ge=0, le=65535, description="Blue channel")
    a: Optional[int] = Field(None, ge=0, le=65535, description="Alpha/clear channel")
    lux: Optional[float] = Field(None, ge=0, description="Calculated lux")


class CompleteSensorReading(BaseModel):
    """Complete sensor reading with all modalities."""

    sensor_id: str
    timestamp: float
    imu: Optional[IMUData] = None
    environmental: Optional[EnvironmentalData] = None
    color: Optional[ColorSensorData] = None
    rms: Optional[float] = Field(None, ge=0, description="RMS vibration")
    gesture: Optional[str] = Field(None, description="Detected gesture")


class SensorStatus(BaseModel):
    """Sensor controller status."""

    connected: bool
    port: Optional[str] = None
    sensor_id: Optional[str] = None
    machine_id: Optional[str] = None
    polling: bool = False
    poll_count: int = 0
    last_reading: Optional[Dict[str, Any]] = None
    errors: int = 0


class SensorRegistration(BaseModel):
    """Sensor registration for the sensor registry."""

    sensor_id: str = Field(
        ...,
        pattern="^[a-zA-Z0-9_-]+$",
        description="Unique sensor identifier"
    )
    sensor_type: str = Field(
        ...,
        pattern="^(imu|environmental|color|proximity|custom)$",
        description="Type of sensor"
    )
    location: Optional[str] = Field(
        None,
        max_length=128,
        description="Physical location description"
    )
    machine_id: Optional[str] = Field(
        None,
        pattern="^[a-zA-Z0-9_-]+$",
        description="Associated machine"
    )
    calibration: Optional[Dict[str, Any]] = Field(
        None,
        description="Calibration parameters"
    )
    metadata: Optional[Dict[str, Any]] = Field(
        None,
        description="Additional metadata"
    )


class SensorCalibrationRequest(BaseModel):
    """Request to calibrate a sensor."""

    sensor_id: str = Field(
        ...,
        pattern="^[a-zA-Z0-9_-]+$"
    )
    calibration_type: str = Field(
        ...,
        pattern="^(zero|scale|full)$",
        description="Type of calibration"
    )
    reference_values: Optional[Dict[str, float]] = Field(
        None,
        description="Known reference values for calibration"
    )
    samples: int = Field(
        default=100,
        ge=10,
        le=10000,
        description="Number of samples to collect"
    )
