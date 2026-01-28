"""
LEGO Factory v3 - Simulation State Management
===============================================
Persistent simulation state using Redis.
"""

import json
import logging
from typing import Optional, Dict, Any
from datetime import datetime

logger = logging.getLogger(__name__)

# Fallback in-memory storage if Redis unavailable
_memory_state: Dict[str, Dict] = {}


class SimulationState:
    """
    Persistent simulation state manager.

    Uses Redis for distributed state, with in-memory fallback.
    """

    REDIS_KEY_PREFIX = 'sim:state:'
    ACTIVE_KEY = 'sim:active'

    @classmethod
    def _get_redis(cls):
        """Get Redis client if available."""
        try:
            import redis
            from config.settings import get_config

            config = get_config()
            client = redis.Redis(
                host=config.redis.host,
                port=config.redis.port,
                db=config.redis.db,
                password=config.redis.password,
                socket_timeout=5.0,
            )
            client.ping()
            return client
        except Exception as e:
            logger.debug(f"Redis not available: {e}")
            return None

    @classmethod
    def create(cls, sim_id: str, data: Dict[str, Any]) -> bool:
        """
        Create new simulation state.

        Args:
            sim_id: Simulation ID
            data: Initial state data

        Returns:
            Success status
        """
        data['created_at'] = datetime.utcnow().isoformat()
        data['updated_at'] = datetime.utcnow().isoformat()

        redis_client = cls._get_redis()
        if redis_client:
            try:
                key = f"{cls.REDIS_KEY_PREFIX}{sim_id}"
                redis_client.hset(key, mapping={
                    k: json.dumps(v) if isinstance(v, (dict, list)) else str(v)
                    for k, v in data.items()
                })
                redis_client.set(cls.ACTIVE_KEY, sim_id)
                redis_client.expire(key, 86400)  # 24 hour TTL
                return True
            except Exception as e:
                logger.warning(f"Redis create failed: {e}")

        # Fallback to memory
        _memory_state[sim_id] = data
        _memory_state['_active'] = sim_id
        return True

    @classmethod
    def update(cls, sim_id: str, data: Dict[str, Any]) -> bool:
        """
        Update simulation state.

        Args:
            sim_id: Simulation ID
            data: Data to update

        Returns:
            Success status
        """
        data['updated_at'] = datetime.utcnow().isoformat()

        redis_client = cls._get_redis()
        if redis_client:
            try:
                key = f"{cls.REDIS_KEY_PREFIX}{sim_id}"
                redis_client.hset(key, mapping={
                    k: json.dumps(v) if isinstance(v, (dict, list)) else str(v)
                    for k, v in data.items()
                })
                return True
            except Exception as e:
                logger.warning(f"Redis update failed: {e}")

        # Fallback to memory
        if sim_id in _memory_state:
            _memory_state[sim_id].update(data)
        return True

    @classmethod
    def get(cls, sim_id: str) -> Optional[Dict[str, Any]]:
        """
        Get simulation state.

        Args:
            sim_id: Simulation ID

        Returns:
            State dict or None
        """
        redis_client = cls._get_redis()
        if redis_client:
            try:
                key = f"{cls.REDIS_KEY_PREFIX}{sim_id}"
                data = redis_client.hgetall(key)
                if data:
                    return {
                        k.decode(): cls._parse_value(v.decode())
                        for k, v in data.items()
                    }
            except Exception as e:
                logger.warning(f"Redis get failed: {e}")

        # Fallback to memory
        return _memory_state.get(sim_id)

    @classmethod
    def get_active(cls) -> Optional[Dict[str, Any]]:
        """
        Get currently active simulation state.

        Returns:
            State dict or None
        """
        redis_client = cls._get_redis()
        if redis_client:
            try:
                active_id = redis_client.get(cls.ACTIVE_KEY)
                if active_id:
                    return cls.get(active_id.decode())
            except Exception as e:
                logger.warning(f"Redis get_active failed: {e}")

        # Fallback to memory
        active_id = _memory_state.get('_active')
        if active_id:
            return _memory_state.get(active_id)
        return None

    @classmethod
    def get_active_id(cls) -> Optional[str]:
        """Get ID of active simulation."""
        redis_client = cls._get_redis()
        if redis_client:
            try:
                active_id = redis_client.get(cls.ACTIVE_KEY)
                if active_id:
                    return active_id.decode()
            except Exception as e:
                logger.warning(f"Redis get_active_id failed: {e}")

        return _memory_state.get('_active')

    @classmethod
    def delete(cls, sim_id: str) -> bool:
        """
        Delete simulation state.

        Args:
            sim_id: Simulation ID

        Returns:
            Success status
        """
        redis_client = cls._get_redis()
        if redis_client:
            try:
                key = f"{cls.REDIS_KEY_PREFIX}{sim_id}"
                redis_client.delete(key)

                # Clear active if this was active
                active_id = redis_client.get(cls.ACTIVE_KEY)
                if active_id and active_id.decode() == sim_id:
                    redis_client.delete(cls.ACTIVE_KEY)
                return True
            except Exception as e:
                logger.warning(f"Redis delete failed: {e}")

        # Fallback to memory
        if sim_id in _memory_state:
            del _memory_state[sim_id]
        if _memory_state.get('_active') == sim_id:
            del _memory_state['_active']
        return True

    @classmethod
    def clear_active(cls) -> bool:
        """Clear the active simulation marker."""
        redis_client = cls._get_redis()
        if redis_client:
            try:
                redis_client.delete(cls.ACTIVE_KEY)
                return True
            except Exception as e:
                logger.warning(f"Redis clear_active failed: {e}")

        if '_active' in _memory_state:
            del _memory_state['_active']
        return True

    @staticmethod
    def _parse_value(value: str) -> Any:
        """Parse string value to appropriate type."""
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            # Try numeric conversion
            try:
                if '.' in value:
                    return float(value)
                return int(value)
            except ValueError:
                return value


def get_simulation_state() -> Optional[Dict[str, Any]]:
    """Convenience function to get active simulation state."""
    return SimulationState.get_active()


def is_simulation_running() -> bool:
    """Check if a simulation is currently running."""
    state = SimulationState.get_active()
    if state:
        return state.get('status') == 'running'
    return False
