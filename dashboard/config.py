"""
Flask Dashboard Configuration
"""

import os
from pathlib import Path


class Config:
    """Base configuration."""

    # Flask
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key-change-in-production")

    # Paths
    BASE_DIR = Path(__file__).parent.parent
    SHARED_DIR = BASE_DIR / "shared"
    OUTPUT_DIR = BASE_DIR / "output"
    MCP_SERVER_DIR = BASE_DIR / "mcp-server" / "src"

    # External services (corrected ports to match actual services)
    # Port 8767 = Fusion 360 add-in HTTP server (from LegoMCP.py line 22)
    # Port 8766 = Slicer service (from docker-compose.yml)
    FUSION_API_URL = os.environ.get("FUSION_API_URL", "http://localhost:8767")
    SLICER_API_URL = os.environ.get("SLICER_API_URL", "http://localhost:8766")

    # Timeouts
    CONNECTION_TIMEOUT = int(os.environ.get("CONNECTION_TIMEOUT", 30))
    OPERATION_TIMEOUT = int(os.environ.get("OPERATION_TIMEOUT", 120))

    # Defaults
    DEFAULT_PRINTER = "prusa_mk3s"
    DEFAULT_MATERIAL = "pla_generic"
    DEFAULT_QUALITY = "lego"
    DEFAULT_STL_REFINEMENT = "high"

    # History
    HISTORY_DIR = os.environ.get("HISTORY_DIR", "/tmp/lego-mcp-history")

    # WebSocket
    WEBSOCKET_PING_INTERVAL = 25
    WEBSOCKET_PING_TIMEOUT = 120


class DevelopmentConfig(Config):
    """Development configuration."""

    DEBUG = True
    TESTING = False


class ProductionConfig(Config):
    """Production configuration."""

    DEBUG = False
    TESTING = False


class TestingConfig(Config):
    """Testing configuration."""

    DEBUG = True
    TESTING = True


config = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "testing": TestingConfig,
    "default": DevelopmentConfig,
}


def get_config():
    """Get configuration based on environment."""
    env = os.environ.get("FLASK_ENV", "development")
    return config.get(env, config["default"])
