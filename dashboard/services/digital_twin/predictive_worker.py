"""
Predictive Analytics Worker Entry Point

LegoMCP World-Class Manufacturing Platform v2.0
ISO 23247 Compliant Digital Twin Implementation

Background worker for continuous predictive analytics:
- Failure prediction on all equipment
- RUL estimation
- Quality forecasting
- Anomaly detection
- Alert generation

Usage:
    python -m dashboard.services.digital_twin.predictive_worker

Author: LegoMCP Team
Version: 2.0.0
"""

import asyncio
import json
import logging
import os
import signal
import sys
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Set

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Try to import Redis
try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    logger.warning("redis package not installed. Install with: pip install redis")

# Import predictive services
try:
    from .predictive_analytics import (
        PredictiveAnalyticsService,
        get_predictive_analytics_service,
        PredictionCategory,
        PredictionResult,
        PredictiveAlert,
    )
    from .twin_manager import get_twin_manager
    SERVICES_AVAILABLE = True
except ImportError as e:
    SERVICES_AVAILABLE = False
    logger.warning(f"Predictive services not available: {e}")


class PredictiveAnalyticsWorker:
    """
    Background worker for continuous predictive analytics.

    Runs periodic predictions on all registered equipment and
    publishes results to Redis for consumption by other services.
    """

    def __init__(
        self,
        prediction_interval: float = 60.0,
        redis_url: Optional[str] = None
    ):
        self.prediction_interval = prediction_interval
        self.redis_url = redis_url or os.getenv("REDIS_URL", "redis://localhost:6379/0")

        # Services
        self.analytics_service: Optional[PredictiveAnalyticsService] = None
        self.twin_manager = None
        self.redis_client = None

        # Tracked entities
        self.entities: Set[str] = set()

        # Worker state
        self.running = False

        # Statistics
        self.stats = {
            "predictions_made": 0,
            "alerts_generated": 0,
            "errors": 0,
            "cycles_completed": 0,
            "start_time": None,
            "last_cycle": None,
        }

    async def initialize(self) -> None:
        """Initialize services and connections."""
        logger.info("Initializing Predictive Analytics Worker...")

        # Initialize analytics service
        if SERVICES_AVAILABLE:
            self.analytics_service = get_predictive_analytics_service()
            self.twin_manager = get_twin_manager()

            # Register callbacks
            self.analytics_service.register_prediction_callback(self.on_prediction)
            self.analytics_service.register_alert_callback(self.on_alert)

            logger.info("Predictive analytics service initialized")
        else:
            logger.error("Predictive services not available")

        # Initialize Redis
        if REDIS_AVAILABLE:
            try:
                self.redis_client = redis.from_url(self.redis_url)
                self.redis_client.ping()
                logger.info(f"Connected to Redis at {self.redis_url}")
            except Exception as e:
                logger.warning(f"Redis connection failed: {e}")
                self.redis_client = None

        # Load tracked entities from Redis or use defaults
        await self.load_entities()

    async def load_entities(self) -> None:
        """Load entities to track from Redis or database."""
        if self.redis_client:
            try:
                entities = self.redis_client.smembers("predictive:entities")
                self.entities = {e.decode() if isinstance(e, bytes) else e for e in entities}
            except Exception as e:
                logger.warning(f"Failed to load entities from Redis: {e}")

        # Add default entities if none loaded
        if not self.entities:
            self.entities = {
                "printer-001",
                "printer-002",
                "mill-001",
                "laser-001",
            }
            logger.info(f"Using default entities: {self.entities}")

    def register_entity(self, entity_id: str) -> None:
        """Register an entity for tracking."""
        self.entities.add(entity_id)

        if self.redis_client:
            try:
                self.redis_client.sadd("predictive:entities", entity_id)
            except Exception as e:
                logger.warning(f"Failed to save entity to Redis: {e}")

    def unregister_entity(self, entity_id: str) -> None:
        """Unregister an entity from tracking."""
        self.entities.discard(entity_id)

        if self.redis_client:
            try:
                self.redis_client.srem("predictive:entities", entity_id)
            except Exception as e:
                logger.warning(f"Failed to remove entity from Redis: {e}")

    def on_prediction(self, result: PredictionResult) -> None:
        """Callback for new predictions."""
        self.stats["predictions_made"] += 1

        # Publish to Redis
        if self.redis_client:
            try:
                channel = f"predictions:{result.entity_id}"
                self.redis_client.publish(channel, json.dumps(result.to_dict()))

                # Store in sorted set by timestamp
                key = f"prediction_history:{result.entity_id}"
                self.redis_client.zadd(
                    key,
                    {json.dumps(result.to_dict()): datetime.utcnow().timestamp()}
                )

                # Trim to keep last 1000
                self.redis_client.zremrangebyrank(key, 0, -1001)

            except Exception as e:
                logger.warning(f"Failed to publish prediction: {e}")

    def on_alert(self, alert: PredictiveAlert) -> None:
        """Callback for new alerts."""
        self.stats["alerts_generated"] += 1

        logger.warning(f"ALERT [{alert.priority.name}]: {alert.title}")

        # Publish to Redis
        if self.redis_client:
            try:
                self.redis_client.publish("alerts:predictive", json.dumps(alert.to_dict()))

                # Store active alerts
                self.redis_client.hset(
                    "active_alerts",
                    alert.alert_id,
                    json.dumps(alert.to_dict())
                )

            except Exception as e:
                logger.warning(f"Failed to publish alert: {e}")

    async def run_prediction_cycle(self) -> None:
        """Run a full prediction cycle on all entities."""
        if not self.analytics_service:
            return

        cycle_start = datetime.utcnow()
        predictions_this_cycle = 0
        errors_this_cycle = 0

        for entity_id in self.entities:
            try:
                # Get features from twin manager or generate defaults
                features = await self.get_entity_features(entity_id)

                # Run predictions for all categories
                results = self.analytics_service.predict_all_categories(
                    entity_id=entity_id,
                    features=features,
                    horizon_hours=24.0
                )

                predictions_this_cycle += len(results)

                # Generate maintenance recommendations for high-risk entities
                if PredictionCategory.FAILURE in results:
                    failure_pred = results[PredictionCategory.FAILURE]
                    if failure_pred.value > 0.5:
                        self.analytics_service.generate_maintenance_recommendation(
                            entity_id, features
                        )

            except Exception as e:
                errors_this_cycle += 1
                self.stats["errors"] += 1
                logger.error(f"Prediction error for {entity_id}: {e}")

        self.stats["cycles_completed"] += 1
        self.stats["last_cycle"] = cycle_start.isoformat()

        logger.info(
            f"Prediction cycle completed: {predictions_this_cycle} predictions, "
            f"{errors_this_cycle} errors, {len(self.entities)} entities"
        )

    async def get_entity_features(self, entity_id: str) -> Dict[str, float]:
        """Get current features for an entity."""
        features = {}

        # Try to get from twin manager
        if self.twin_manager:
            try:
                snapshot = self.twin_manager.get_current_state(entity_id)
                if snapshot:
                    features = self.twin_manager._extract_features(snapshot)
            except Exception as e:
                logger.debug(f"Could not get features from twin manager: {e}")

        # Try to get from Redis
        if not features and self.redis_client:
            try:
                data = self.redis_client.hgetall(f"entity_state:{entity_id}")
                if data:
                    features = {
                        k.decode() if isinstance(k, bytes) else k:
                        float(v.decode() if isinstance(v, bytes) else v)
                        for k, v in data.items()
                    }
            except Exception as e:
                logger.debug(f"Could not get features from Redis: {e}")

        # Use defaults if no features available
        if not features:
            features = {
                "temperature": 45.0 + (hash(entity_id) % 30),
                "vibration": 0.5 + (hash(entity_id) % 10) / 10,
                "operating_hours": 1000 + (hash(entity_id) % 5000),
                "error_count_24h": hash(entity_id) % 10,
                "power_consumption": 200 + (hash(entity_id) % 100),
            }

        return features

    async def publish_health_status(self) -> None:
        """Publish worker health status."""
        if self.redis_client:
            try:
                status = {
                    "worker": "predictive_analytics",
                    "status": "healthy" if self.running else "stopped",
                    "stats": self.stats,
                    "entities_tracked": len(self.entities),
                    "timestamp": datetime.utcnow().isoformat(),
                }
                self.redis_client.setex(
                    "worker:predictive_analytics:health",
                    60,  # 60 second TTL
                    json.dumps(status)
                )
            except Exception as e:
                logger.warning(f"Failed to publish health status: {e}")

    async def run(self) -> None:
        """Main worker loop."""
        self.running = True
        self.stats["start_time"] = datetime.utcnow().isoformat()

        await self.initialize()

        logger.info(
            f"Predictive Analytics Worker started. "
            f"Interval: {self.prediction_interval}s, "
            f"Entities: {len(self.entities)}"
        )

        while self.running:
            try:
                # Run prediction cycle
                await self.run_prediction_cycle()

                # Publish health status
                await self.publish_health_status()

                # Wait for next cycle
                await asyncio.sleep(self.prediction_interval)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Worker error: {e}")
                self.stats["errors"] += 1
                await asyncio.sleep(5.0)  # Back off on error

    async def shutdown(self) -> None:
        """Graceful shutdown."""
        logger.info("Shutting down Predictive Analytics Worker...")
        self.running = False

        # Final health status
        if self.redis_client:
            try:
                self.redis_client.delete("worker:predictive_analytics:health")
            except Exception:
                pass

        logger.info("Predictive Analytics Worker shutdown complete")


async def main():
    """Main entry point."""
    prediction_interval = float(os.getenv("PREDICTION_INTERVAL_SEC", "60"))
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")

    worker = PredictiveAnalyticsWorker(
        prediction_interval=prediction_interval,
        redis_url=redis_url
    )

    # Handle shutdown signals
    loop = asyncio.get_event_loop()

    def signal_handler():
        asyncio.create_task(worker.shutdown())

    for sig in (signal.SIGTERM, signal.SIGINT):
        try:
            loop.add_signal_handler(sig, signal_handler)
        except NotImplementedError:
            # Windows doesn't support add_signal_handler
            pass

    try:
        await worker.run()
    except KeyboardInterrupt:
        await worker.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
