"""
LEGO Factory v3 - Real-Time Anomaly Detection Hook
==================================================
Integration hook for real-time anomaly detection when new tag values arrive.
Designed for efficient processing in high-frequency data streams.
"""

from __future__ import annotations
import logging
import asyncio
import threading
from datetime import datetime
from typing import Optional, Dict, Any, List, Callable, Awaitable
from collections import deque
from dataclasses import dataclass, field
from concurrent.futures import ThreadPoolExecutor

from services.ml.anomaly.anomaly_types import (
    AnomalySeverity,
    AnomalyResult,
    AnomalyConfig,
)
from services.ml.anomaly.anomaly_detection_service import (
    anomaly_detection_service,
    AnomalyDetectionService,
)
from services.ml.anomaly.alarm_integration import generate_alarm_from_anomaly

logger = logging.getLogger(__name__)


# Type aliases for callbacks
SyncCallback = Callable[[AnomalyResult], None]
AsyncCallback = Callable[[AnomalyResult], Awaitable[None]]


@dataclass
class TagValueEvent:
    """Event representing a new tag value."""
    tag_id: str
    value: float
    timestamp: datetime
    tag_name: Optional[str] = None
    quality: int = 192  # OPC UA Good quality
    source: Optional[str] = None


@dataclass
class HookConfig:
    """Configuration for the real-time detection hook."""
    enabled: bool = True
    max_batch_size: int = 100
    batch_timeout_ms: float = 50.0
    min_severity_for_callback: AnomalySeverity = AnomalySeverity.LOW
    async_processing: bool = True
    max_queue_size: int = 10000
    worker_threads: int = 2
    # Alarm generation settings
    generate_alarms: bool = True
    min_severity_for_alarm: AnomalySeverity = AnomalySeverity.MEDIUM


class RealtimeAnomalyHook:
    """
    Real-time anomaly detection hook for integration with SCADA/historian systems.

    This class provides an efficient interface for processing incoming tag values
    and detecting anomalies in real-time. It supports both synchronous and
    asynchronous callbacks for anomaly notifications.

    Usage:
        hook = RealtimeAnomalyHook()

        # Register callbacks
        hook.on_anomaly(my_callback)
        hook.on_anomaly_async(my_async_callback)

        # Process incoming values
        for value in data_stream:
            hook.process(value.tag_id, value.value)

        # Or use with historian integration
        historian.subscribe(hook.process)
    """

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self._config = HookConfig()
        self._detection_service = anomaly_detection_service

        # Callbacks
        self._sync_callbacks: List[SyncCallback] = []
        self._async_callbacks: List[AsyncCallback] = []

        # Async processing
        self._event_queue: asyncio.Queue = None
        self._processing_task: asyncio.Task = None
        self._executor = ThreadPoolExecutor(max_workers=self._config.worker_threads)

        # Batching for efficiency
        self._batch_queue: deque = deque(maxlen=self._config.max_batch_size)
        self._batch_lock = threading.Lock()

        # Statistics
        self._stats = {
            'values_processed': 0,
            'anomalies_detected': 0,
            'alarms_generated': 0,
            'callbacks_invoked': 0,
            'errors': 0,
        }

        self._running = False
        self._initialized = True

        logger.info("Real-time anomaly detection hook initialized")

    def configure(self, config: HookConfig):
        """Update hook configuration."""
        self._config = config
        logger.info("Real-time hook configuration updated")

    def on_anomaly(self, callback: SyncCallback):
        """
        Register a synchronous callback for anomaly notifications.

        The callback will be invoked for each detected anomaly that meets
        the minimum severity threshold.

        Args:
            callback: Function accepting an AnomalyResult parameter
        """
        self._sync_callbacks.append(callback)
        logger.debug(f"Registered sync anomaly callback: {callback.__name__}")

    def on_anomaly_async(self, callback: AsyncCallback):
        """
        Register an asynchronous callback for anomaly notifications.

        The callback will be awaited for each detected anomaly.

        Args:
            callback: Async function accepting an AnomalyResult parameter
        """
        self._async_callbacks.append(callback)
        logger.debug(f"Registered async anomaly callback: {callback.__name__}")

    def remove_callback(self, callback: SyncCallback):
        """Remove a registered callback."""
        if callback in self._sync_callbacks:
            self._sync_callbacks.remove(callback)

    def remove_async_callback(self, callback: AsyncCallback):
        """Remove a registered async callback."""
        if callback in self._async_callbacks:
            self._async_callbacks.remove(callback)

    def process(
        self,
        tag_id: str,
        value: float,
        timestamp: datetime = None,
        tag_name: str = None,
        **kwargs
    ) -> Optional[AnomalyResult]:
        """
        Process a single tag value for anomaly detection.

        This is the main entry point for real-time processing. It performs
        anomaly detection and triggers callbacks if an anomaly is detected.

        Args:
            tag_id: Tag identifier
            value: Numeric value
            timestamp: Value timestamp (defaults to now)
            tag_name: Human-readable tag name
            **kwargs: Additional context (quality, source, etc.)

        Returns:
            AnomalyResult if anomaly detected, None otherwise
        """
        if not self._config.enabled:
            return None

        timestamp = timestamp or datetime.utcnow()
        tag_name = tag_name or tag_id

        self._stats['values_processed'] += 1

        try:
            # Run detection
            result = self._detection_service.detect_realtime(
                tag_id=tag_id,
                value=value,
                timestamp=timestamp,
                tag_name=tag_name
            )

            if result and result.severity >= self._config.min_severity_for_callback:
                self._stats['anomalies_detected'] += 1
                self._invoke_callbacks(result)

                # Generate ISA-18.2 alarm if enabled and severity threshold met
                if (self._config.generate_alarms and
                        result.severity >= self._config.min_severity_for_alarm):
                    self._generate_alarm(result)

            return result

        except Exception as e:
            self._stats['errors'] += 1
            logger.error(f"Error processing value for {tag_id}: {e}")
            return None

    async def process_async(
        self,
        tag_id: str,
        value: float,
        timestamp: datetime = None,
        tag_name: str = None,
        **kwargs
    ) -> Optional[AnomalyResult]:
        """
        Async version of process() for use in async contexts.
        """
        if not self._config.enabled:
            return None

        timestamp = timestamp or datetime.utcnow()
        tag_name = tag_name or tag_id

        self._stats['values_processed'] += 1

        try:
            # Run detection (offload to thread pool for CPU-bound work)
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                self._executor,
                self._detection_service.detect_realtime,
                tag_id, value, timestamp, tag_name
            )

            if result and result.severity >= self._config.min_severity_for_callback:
                self._stats['anomalies_detected'] += 1
                await self._invoke_callbacks_async(result)

                # Generate ISA-18.2 alarm if enabled and severity threshold met
                if (self._config.generate_alarms and
                        result.severity >= self._config.min_severity_for_alarm):
                    await loop.run_in_executor(
                        self._executor,
                        self._generate_alarm,
                        result
                    )

            return result

        except Exception as e:
            self._stats['errors'] += 1
            logger.error(f"Error in async processing for {tag_id}: {e}")
            return None

    def process_batch(
        self,
        events: List[TagValueEvent]
    ) -> List[AnomalyResult]:
        """
        Process a batch of tag values.

        More efficient than processing one at a time for high-volume streams.

        Args:
            events: List of TagValueEvent objects

        Returns:
            List of AnomalyResult for detected anomalies
        """
        if not self._config.enabled:
            return []

        results = []

        for event in events:
            self._stats['values_processed'] += 1

            try:
                result = self._detection_service.detect_realtime(
                    tag_id=event.tag_id,
                    value=event.value,
                    timestamp=event.timestamp,
                    tag_name=event.tag_name
                )

                if result:
                    results.append(result)

                    if result.severity >= self._config.min_severity_for_callback:
                        self._stats['anomalies_detected'] += 1

            except Exception as e:
                self._stats['errors'] += 1
                logger.error(f"Error processing batch event for {event.tag_id}: {e}")

        # Invoke callbacks for significant anomalies
        significant = [r for r in results if r.severity >= self._config.min_severity_for_callback]
        for result in significant:
            self._invoke_callbacks(result)

            # Generate alarms for severe anomalies
            if (self._config.generate_alarms and
                    result.severity >= self._config.min_severity_for_alarm):
                self._generate_alarm(result)

        return results

    def _invoke_callbacks(self, result: AnomalyResult):
        """Invoke registered callbacks for an anomaly."""
        for callback in self._sync_callbacks:
            try:
                callback(result)
                self._stats['callbacks_invoked'] += 1
            except Exception as e:
                self._stats['errors'] += 1
                logger.error(f"Error in anomaly callback {callback.__name__}: {e}")

        # Handle async callbacks in sync context
        if self._async_callbacks:
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    # Schedule async callbacks
                    for callback in self._async_callbacks:
                        asyncio.create_task(self._safe_async_callback(callback, result))
                else:
                    # Run in new loop
                    asyncio.run(self._invoke_callbacks_async(result))
            except RuntimeError:
                # No event loop, skip async callbacks
                pass

    async def _invoke_callbacks_async(self, result: AnomalyResult):
        """Invoke all callbacks asynchronously."""
        # Sync callbacks
        for callback in self._sync_callbacks:
            try:
                callback(result)
                self._stats['callbacks_invoked'] += 1
            except Exception as e:
                self._stats['errors'] += 1
                logger.error(f"Error in anomaly callback {callback.__name__}: {e}")

        # Async callbacks
        for callback in self._async_callbacks:
            await self._safe_async_callback(callback, result)

    async def _safe_async_callback(self, callback: AsyncCallback, result: AnomalyResult):
        """Safely invoke an async callback with error handling."""
        try:
            await callback(result)
            self._stats['callbacks_invoked'] += 1
        except Exception as e:
            self._stats['errors'] += 1
            logger.error(f"Error in async anomaly callback {callback.__name__}: {e}")

    def _generate_alarm(self, result: AnomalyResult):
        """
        Generate an ISA-18.2 alarm from an anomaly result.

        This method submits the anomaly to the alarm integration module
        which converts it to an ISA-18.2 compliant alarm and submits it
        to the alarm processor for tracking and broadcasting.

        Args:
            result: The anomaly detection result
        """
        try:
            alarm_data = generate_alarm_from_anomaly(result)
            if alarm_data:
                self._stats['alarms_generated'] += 1
                logger.debug(
                    f"Generated alarm for anomaly: {result.tag_name} - "
                    f"{result.category.value}"
                )
        except Exception as e:
            self._stats['errors'] += 1
            logger.error(f"Failed to generate alarm for anomaly: {e}")

    def get_stats(self) -> Dict[str, Any]:
        """Get processing statistics."""
        return {
            **self._stats,
            'config': {
                'enabled': self._config.enabled,
                'min_severity': self._config.min_severity_for_callback.name,
                'async_processing': self._config.async_processing,
                'generate_alarms': self._config.generate_alarms,
                'min_severity_for_alarm': self._config.min_severity_for_alarm.name,
            },
            'callbacks_registered': {
                'sync': len(self._sync_callbacks),
                'async': len(self._async_callbacks),
            },
        }

    def reset_stats(self):
        """Reset processing statistics."""
        self._stats = {
            'values_processed': 0,
            'anomalies_detected': 0,
            'alarms_generated': 0,
            'callbacks_invoked': 0,
            'errors': 0,
        }


# Global hook instance
realtime_hook = RealtimeAnomalyHook()


def process_tag_value(
    tag_id: str,
    value: float,
    timestamp: datetime = None,
    tag_name: str = None,
    **kwargs
) -> Optional[AnomalyResult]:
    """
    Process a tag value for anomaly detection.

    Convenience function wrapping the global hook instance.
    """
    return realtime_hook.process(tag_id, value, timestamp, tag_name, **kwargs)


async def process_tag_value_async(
    tag_id: str,
    value: float,
    timestamp: datetime = None,
    tag_name: str = None,
    **kwargs
) -> Optional[AnomalyResult]:
    """
    Async version of process_tag_value().
    """
    return await realtime_hook.process_async(tag_id, value, timestamp, tag_name, **kwargs)


def on_anomaly(callback: SyncCallback):
    """Register a callback for anomaly notifications."""
    realtime_hook.on_anomaly(callback)


def on_anomaly_async(callback: AsyncCallback):
    """Register an async callback for anomaly notifications."""
    realtime_hook.on_anomaly_async(callback)


# Integration with historian service
def create_historian_callback():
    """
    Create a callback function for integration with the historian service.

    Returns a function that can be passed to the historian's subscription
    mechanism to enable real-time anomaly detection on incoming data.

    Usage:
        from services.scada.historian import historian_service
        from services.ml.anomaly.realtime_hook import create_historian_callback

        callback = create_historian_callback()
        historian_service.subscribe(callback)
    """
    def historian_callback(tag_id: str, value: float, timestamp: datetime, quality: int = 192):
        """Callback for historian subscription."""
        if quality >= 192:  # Only process good quality data
            result = process_tag_value(tag_id, value, timestamp)
            return result
        return None

    return historian_callback


def create_opc_callback():
    """
    Create a callback function for integration with OPC UA clients.

    Returns a function that can be used as a data change callback
    in OPC UA subscriptions.

    Usage:
        from asyncua import Client

        callback = create_opc_callback()
        subscription = await client.create_subscription(100, callback)
    """
    async def opc_callback(node, value, data):
        """OPC UA data change callback."""
        try:
            tag_id = str(node.nodeid)
            timestamp = data.monitored_item.Value.SourceTimestamp or datetime.utcnow()
            numeric_value = float(value)

            result = await process_tag_value_async(tag_id, numeric_value, timestamp)
            return result

        except (ValueError, TypeError) as e:
            logger.warning(f"Could not process OPC value for {node}: {e}")
            return None

    return opc_callback


class HistorianAnomalyBridge:
    """
    Bridge between historian service and anomaly detection.

    Provides automatic anomaly detection on all historized tag values.
    """

    def __init__(self, detection_service: AnomalyDetectionService = None):
        self._detection_service = detection_service or anomaly_detection_service
        self._hook = realtime_hook
        self._subscriptions: Dict[str, Any] = {}
        self._active = False

    def start(self, tag_ids: List[str] = None):
        """
        Start monitoring tags for anomalies.

        Args:
            tag_ids: List of tag IDs to monitor (None = all)
        """
        self._active = True
        logger.info(f"Historian anomaly bridge started for {len(tag_ids) if tag_ids else 'all'} tags")

    def stop(self):
        """Stop monitoring."""
        self._active = False
        logger.info("Historian anomaly bridge stopped")

    def process_historian_value(
        self,
        tag_id: str,
        value: float,
        timestamp: datetime,
        tag_name: str = None
    ) -> Optional[AnomalyResult]:
        """
        Process a value from the historian.

        This method should be called by the historian service when
        new values are recorded.
        """
        if not self._active:
            return None

        return self._hook.process(tag_id, value, timestamp, tag_name)


# Global bridge instance
historian_anomaly_bridge = HistorianAnomalyBridge()
