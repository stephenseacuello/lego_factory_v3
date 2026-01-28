#!/usr/bin/env python
"""
LEGO Factory v3 - Application Entry Point
==========================================
Run the Flask application with SocketIO support.
"""

import os
import sys
import logging

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app, socketio
from config.settings import get_config

logger = logging.getLogger(__name__)


def main():
    """Main entry point"""
    config = get_config()

    # Create Flask app
    app = create_app()

    # Start background services
    start_services()

    # Run with SocketIO
    logger.info(f"Starting LEGO Factory v3 on {config.flask.host}:{config.flask.port}")

    try:
        socketio.run(
            app,
            host=config.flask.host,
            port=config.flask.port,
            debug=config.flask.debug,
            use_reloader=config.flask.debug
        )
    except KeyboardInterrupt:
        logger.info("Shutting down...")
        stop_services()
    except Exception as e:
        logger.error(f"Error running application: {e}")
        stop_services()
        raise


def start_services():
    """Start background services"""
    from services.scada.historian.historian_service import start_historian
    from services.scada.alarm_management.alarm_service import start_alarm_processor

    try:
        start_historian()
        logger.info("Historian service started")
    except Exception as e:
        logger.warning(f"Failed to start historian: {e}")

    try:
        start_alarm_processor()
        logger.info("Alarm processor started")
    except Exception as e:
        logger.warning(f"Failed to start alarm processor: {e}")


def stop_services():
    """Stop background services"""
    from services.scada.historian.historian_service import stop_historian
    from services.scada.alarm_management.alarm_service import stop_alarm_processor

    try:
        stop_historian()
        logger.info("Historian service stopped")
    except Exception as e:
        logger.warning(f"Error stopping historian: {e}")

    try:
        stop_alarm_processor()
        logger.info("Alarm processor stopped")
    except Exception as e:
        logger.warning(f"Error stopping alarm processor: {e}")


if __name__ == '__main__':
    main()
