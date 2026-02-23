"""
Redis Query Cache Service
===========================
Decorator-based caching using Redis for query results.
"""
import json
import functools
import hashlib
import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)

_redis_client = None


def _get_redis():
    global _redis_client
    if _redis_client is None:
        try:
            import redis
            from config.settings import get_config
            config = get_config()
            # Use REDIS_URL if available (handles Docker network names)
            redis_url = config.redis.url
            _redis_client = redis.Redis.from_url(
                redis_url,
                decode_responses=True,
                socket_timeout=2,
                socket_connect_timeout=2,
            )
            _redis_client.ping()
            logger.info(f"Redis cache connected")
        except Exception as e:
            logger.warning(f"Redis cache unavailable: {e}")
            _redis_client = None
    return _redis_client


def cached(ttl: int = 60, prefix: str = 'cache'):
    """Decorator to cache function results in Redis.

    Args:
        ttl: Time-to-live in seconds
        prefix: Cache key prefix
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            client = _get_redis()
            if client is None:
                return func(*args, **kwargs)

            # Build cache key from function name and args
            key_parts = [prefix, func.__module__, func.__qualname__]
            # Skip 'self' argument
            cache_args = args[1:] if args and hasattr(args[0], '__class__') else args
            arg_str = json.dumps({'args': str(cache_args), 'kwargs': str(kwargs)}, sort_keys=True)
            key_hash = hashlib.md5(arg_str.encode()).hexdigest()[:12]
            cache_key = ':'.join(key_parts) + ':' + key_hash

            try:
                cached_val = client.get(cache_key)
                if cached_val is not None:
                    return json.loads(cached_val)
            except Exception:
                pass

            result = func(*args, **kwargs)

            try:
                client.setex(cache_key, ttl, json.dumps(result, default=str))
            except Exception:
                pass

            return result
        return wrapper
    return decorator


def invalidate(pattern: str):
    """Invalidate cache keys matching a pattern."""
    client = _get_redis()
    if client is None:
        return 0
    try:
        keys = client.keys(f'cache:*{pattern}*')
        if keys:
            return client.delete(*keys)
    except Exception:
        pass
    return 0


class CacheService:
    """Cache management service."""

    @staticmethod
    def get(key: str) -> Optional[Any]:
        client = _get_redis()
        if client is None:
            return None
        try:
            val = client.get(key)
            return json.loads(val) if val else None
        except Exception:
            return None

    @staticmethod
    def set(key: str, value: Any, ttl: int = 60) -> bool:
        client = _get_redis()
        if client is None:
            return False
        try:
            client.setex(key, ttl, json.dumps(value, default=str))
            return True
        except Exception:
            return False

    @staticmethod
    def delete(key: str) -> bool:
        client = _get_redis()
        if client is None:
            return False
        try:
            client.delete(key)
            return True
        except Exception:
            return False

    @staticmethod
    def clear_all(prefix: str = 'cache') -> int:
        client = _get_redis()
        if client is None:
            return 0
        try:
            keys = client.keys(f'{prefix}:*')
            if keys:
                return client.delete(*keys)
        except Exception:
            pass
        return 0
