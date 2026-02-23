"""
V8 Caching Services
===================

Provides high-performance caching for:
- KPI data with TTL and invalidation
- Dashboard aggregations
- Equipment state snapshots
- Query result caching
- Session data

Supports multiple backends:
- In-memory (default)
- Redis
- Memcached

Author: LEGO MCP Engineering Team
Version: 8.0.0
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import threading
import time
from abc import ABC, abstractmethod
from collections import OrderedDict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from functools import wraps
from typing import Any, Callable, Dict, Generic, List, Optional, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar('T')


# ============================================
# Cache Configuration
# ============================================

class CacheBackend(Enum):
    """Supported cache backends."""
    MEMORY = "memory"
    REDIS = "redis"
    MEMCACHED = "memcached"


@dataclass
class CacheConfig:
    """Cache configuration."""
    backend: CacheBackend = CacheBackend.MEMORY
    default_ttl_seconds: int = 300  # 5 minutes
    max_size: int = 10000
    redis_url: str = ""
    memcached_servers: List[str] = field(default_factory=list)
    namespace: str = "lego_mcp"
    compression_threshold: int = 1024  # Compress if > 1KB


# ============================================
# Cache Entry
# ============================================

@dataclass
class CacheEntry(Generic[T]):
    """A cached value with metadata."""
    key: str
    value: T
    created_at: datetime = field(default_factory=datetime.now)
    expires_at: Optional[datetime] = None
    tags: List[str] = field(default_factory=list)
    hits: int = 0
    version: int = 1

    def is_expired(self) -> bool:
        if self.expires_at is None:
            return False
        return datetime.now() > self.expires_at

    def to_dict(self) -> Dict[str, Any]:
        return {
            "key": self.key,
            "created_at": self.created_at.isoformat(),
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "tags": self.tags,
            "hits": self.hits,
            "version": self.version
        }


# ============================================
# Cache Statistics
# ============================================

@dataclass
class CacheStats:
    """Cache statistics."""
    hits: int = 0
    misses: int = 0
    sets: int = 0
    deletes: int = 0
    evictions: int = 0
    expired: int = 0
    size: int = 0
    max_size: int = 0

    @property
    def hit_rate(self) -> float:
        total = self.hits + self.misses
        return self.hits / total if total > 0 else 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "hits": self.hits,
            "misses": self.misses,
            "sets": self.sets,
            "deletes": self.deletes,
            "evictions": self.evictions,
            "expired": self.expired,
            "size": self.size,
            "max_size": self.max_size,
            "hit_rate": round(self.hit_rate, 3)
        }


# ============================================
# Abstract Cache Backend
# ============================================

class CacheBackendInterface(ABC):
    """Abstract cache backend interface."""

    @abstractmethod
    def get(self, key: str) -> Optional[Any]:
        """Get a value from cache."""
        pass

    @abstractmethod
    def set(self, key: str, value: Any, ttl: Optional[int] = None, tags: Optional[List[str]] = None) -> bool:
        """Set a value in cache."""
        pass

    @abstractmethod
    def delete(self, key: str) -> bool:
        """Delete a key from cache."""
        pass

    @abstractmethod
    def exists(self, key: str) -> bool:
        """Check if key exists."""
        pass

    @abstractmethod
    def clear(self) -> int:
        """Clear all cache entries."""
        pass

    @abstractmethod
    def get_stats(self) -> CacheStats:
        """Get cache statistics."""
        pass


# ============================================
# In-Memory Cache Backend
# ============================================

class MemoryCacheBackend(CacheBackendInterface):
    """Thread-safe in-memory LRU cache."""

    def __init__(self, max_size: int = 10000, default_ttl: int = 300):
        self._cache: OrderedDict[str, CacheEntry] = OrderedDict()
        self._max_size = max_size
        self._default_ttl = default_ttl
        self._lock = threading.RLock()
        self._stats = CacheStats(max_size=max_size)
        self._tag_index: Dict[str, set] = {}

    def get(self, key: str) -> Optional[Any]:
        with self._lock:
            entry = self._cache.get(key)

            if entry is None:
                self._stats.misses += 1
                return None

            if entry.is_expired():
                self._delete_entry(key)
                self._stats.expired += 1
                self._stats.misses += 1
                return None

            # Move to end (LRU)
            self._cache.move_to_end(key)
            entry.hits += 1
            self._stats.hits += 1

            return entry.value

    def set(self, key: str, value: Any, ttl: Optional[int] = None, tags: Optional[List[str]] = None) -> bool:
        ttl = ttl or self._default_ttl
        tags = tags or []

        with self._lock:
            # Check if we need to evict
            if len(self._cache) >= self._max_size and key not in self._cache:
                self._evict_oldest()

            expires_at = datetime.now() + timedelta(seconds=ttl) if ttl > 0 else None

            # Get existing version
            existing = self._cache.get(key)
            version = existing.version + 1 if existing else 1

            entry = CacheEntry(
                key=key,
                value=value,
                expires_at=expires_at,
                tags=tags,
                version=version
            )

            self._cache[key] = entry
            self._cache.move_to_end(key)

            # Update tag index
            for tag in tags:
                if tag not in self._tag_index:
                    self._tag_index[tag] = set()
                self._tag_index[tag].add(key)

            self._stats.sets += 1
            self._stats.size = len(self._cache)

            return True

    def delete(self, key: str) -> bool:
        with self._lock:
            return self._delete_entry(key)

    def _delete_entry(self, key: str) -> bool:
        if key in self._cache:
            entry = self._cache[key]

            # Remove from tag index
            for tag in entry.tags:
                if tag in self._tag_index:
                    self._tag_index[tag].discard(key)

            del self._cache[key]
            self._stats.deletes += 1
            self._stats.size = len(self._cache)
            return True
        return False

    def _evict_oldest(self):
        """Evict oldest entry (LRU)."""
        if self._cache:
            key, _ = self._cache.popitem(last=False)
            self._stats.evictions += 1
            self._stats.size = len(self._cache)

    def exists(self, key: str) -> bool:
        with self._lock:
            entry = self._cache.get(key)
            if entry and not entry.is_expired():
                return True
            return False

    def clear(self) -> int:
        with self._lock:
            count = len(self._cache)
            self._cache.clear()
            self._tag_index.clear()
            self._stats.size = 0
            return count

    def invalidate_by_tag(self, tag: str) -> int:
        """Invalidate all entries with a specific tag."""
        with self._lock:
            keys = self._tag_index.get(tag, set()).copy()
            count = 0
            for key in keys:
                if self._delete_entry(key):
                    count += 1
            return count

    def get_stats(self) -> CacheStats:
        return self._stats

    def cleanup_expired(self) -> int:
        """Remove expired entries."""
        with self._lock:
            expired_keys = [
                k for k, v in self._cache.items() if v.is_expired()
            ]
            for key in expired_keys:
                self._delete_entry(key)
                self._stats.expired += 1
            return len(expired_keys)


# ============================================
# Redis Cache Backend
# ============================================

class RedisCacheBackend(CacheBackendInterface):
    """Redis cache backend."""

    def __init__(self, redis_url: str, namespace: str = "lego_mcp", default_ttl: int = 300):
        self._redis_url = redis_url
        self._namespace = namespace
        self._default_ttl = default_ttl
        self._client = None
        self._stats = CacheStats()

        self._connect()

    def _connect(self):
        """Connect to Redis."""
        try:
            import redis
            self._client = redis.from_url(self._redis_url)
            self._client.ping()
            logger.info(f"Connected to Redis: {self._redis_url}")
        except Exception as e:
            logger.warning(f"Redis connection failed: {e}")
            self._client = None

    def _make_key(self, key: str) -> str:
        return f"{self._namespace}:{key}"

    def get(self, key: str) -> Optional[Any]:
        if not self._client:
            self._stats.misses += 1
            return None

        try:
            data = self._client.get(self._make_key(key))
            if data:
                self._stats.hits += 1
                return json.loads(data)
            else:
                self._stats.misses += 1
                return None
        except Exception as e:
            logger.error(f"Redis get error: {e}")
            self._stats.misses += 1
            return None

    def set(self, key: str, value: Any, ttl: Optional[int] = None, tags: Optional[List[str]] = None) -> bool:
        if not self._client:
            return False

        ttl = ttl or self._default_ttl

        try:
            data = json.dumps(value)
            redis_key = self._make_key(key)

            if ttl > 0:
                self._client.setex(redis_key, ttl, data)
            else:
                self._client.set(redis_key, data)

            # Store tags
            if tags:
                for tag in tags:
                    self._client.sadd(f"{self._namespace}:tag:{tag}", key)

            self._stats.sets += 1
            return True
        except Exception as e:
            logger.error(f"Redis set error: {e}")
            return False

    def delete(self, key: str) -> bool:
        if not self._client:
            return False

        try:
            result = self._client.delete(self._make_key(key))
            if result:
                self._stats.deletes += 1
            return bool(result)
        except Exception as e:
            logger.error(f"Redis delete error: {e}")
            return False

    def exists(self, key: str) -> bool:
        if not self._client:
            return False

        try:
            return bool(self._client.exists(self._make_key(key)))
        except Exception:
            return False

    def clear(self) -> int:
        if not self._client:
            return 0

        try:
            pattern = f"{self._namespace}:*"
            keys = self._client.keys(pattern)
            if keys:
                return self._client.delete(*keys)
            return 0
        except Exception as e:
            logger.error(f"Redis clear error: {e}")
            return 0

    def invalidate_by_tag(self, tag: str) -> int:
        """Invalidate all entries with a specific tag."""
        if not self._client:
            return 0

        try:
            tag_key = f"{self._namespace}:tag:{tag}"
            keys = self._client.smembers(tag_key)
            count = 0
            for key in keys:
                if self.delete(key.decode() if isinstance(key, bytes) else key):
                    count += 1
            self._client.delete(tag_key)
            return count
        except Exception as e:
            logger.error(f"Redis invalidate_by_tag error: {e}")
            return 0

    def get_stats(self) -> CacheStats:
        if self._client:
            try:
                info = self._client.info('keyspace')
                db_info = info.get('db0', {})
                self._stats.size = db_info.get('keys', 0)
            except Exception:
                pass
        return self._stats


# ============================================
# Cache Manager
# ============================================

class CacheManager:
    """Unified cache manager supporting multiple backends."""

    _instance: Optional[CacheManager] = None
    _lock = threading.Lock()

    def __init__(self, config: Optional[CacheConfig] = None):
        self._config = config or CacheConfig()
        self._backend: CacheBackendInterface

        # Initialize backend
        if self._config.backend == CacheBackend.REDIS and self._config.redis_url:
            self._backend = RedisCacheBackend(
                self._config.redis_url,
                self._config.namespace,
                self._config.default_ttl_seconds
            )
        else:
            self._backend = MemoryCacheBackend(
                self._config.max_size,
                self._config.default_ttl_seconds
            )

        logger.info(f"Cache manager initialized with backend: {self._config.backend.value}")

    @classmethod
    def get_instance(cls, config: Optional[CacheConfig] = None) -> CacheManager:
        """Get singleton instance."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls(config)
        return cls._instance

    def get(self, key: str) -> Optional[Any]:
        """Get a value from cache."""
        return self._backend.get(key)

    def set(self, key: str, value: Any, ttl: Optional[int] = None, tags: Optional[List[str]] = None) -> bool:
        """Set a value in cache."""
        return self._backend.set(key, value, ttl, tags)

    def delete(self, key: str) -> bool:
        """Delete a key from cache."""
        return self._backend.delete(key)

    def exists(self, key: str) -> bool:
        """Check if key exists."""
        return self._backend.exists(key)

    def clear(self) -> int:
        """Clear all cache entries."""
        return self._backend.clear()

    def invalidate_by_tag(self, tag: str) -> int:
        """Invalidate all entries with a specific tag."""
        if hasattr(self._backend, 'invalidate_by_tag'):
            return self._backend.invalidate_by_tag(tag)
        return 0

    def get_stats(self) -> CacheStats:
        """Get cache statistics."""
        return self._backend.get_stats()

    def get_or_set(self, key: str, factory: Callable[[], T], ttl: Optional[int] = None, tags: Optional[List[str]] = None) -> T:
        """Get from cache or compute and cache."""
        value = self.get(key)
        if value is not None:
            return value

        value = factory()
        self.set(key, value, ttl, tags)
        return value


# ============================================
# KPI Cache
# ============================================

class KPICache:
    """Specialized cache for KPI data."""

    DEFAULT_TTL = 60  # 1 minute for real-time KPIs
    DASHBOARD_TTL = 30  # 30 seconds for dashboard
    HISTORY_TTL = 300  # 5 minutes for historical data

    def __init__(self, cache_manager: Optional[CacheManager] = None):
        self._cache = cache_manager or get_cache_manager()

    def get_kpi(self, name: str) -> Optional[Dict[str, Any]]:
        """Get a single KPI value."""
        return self._cache.get(f"kpi:{name}")

    def set_kpi(self, name: str, value: Dict[str, Any], category: str = "general") -> bool:
        """Set a KPI value."""
        return self._cache.set(
            f"kpi:{name}",
            value,
            ttl=self.DEFAULT_TTL,
            tags=["kpi", f"kpi:{category}"]
        )

    def get_dashboard(self) -> Optional[Dict[str, Any]]:
        """Get cached dashboard data."""
        return self._cache.get("kpi:dashboard")

    def set_dashboard(self, dashboard: Dict[str, Any]) -> bool:
        """Cache dashboard data."""
        return self._cache.set(
            "kpi:dashboard",
            dashboard,
            ttl=self.DASHBOARD_TTL,
            tags=["kpi", "dashboard"]
        )

    def get_history(self, name: str, period: str) -> Optional[List[Dict[str, Any]]]:
        """Get KPI history data."""
        return self._cache.get(f"kpi:history:{name}:{period}")

    def set_history(self, name: str, period: str, data: List[Dict[str, Any]]) -> bool:
        """Cache KPI history data."""
        return self._cache.set(
            f"kpi:history:{name}:{period}",
            data,
            ttl=self.HISTORY_TTL,
            tags=["kpi", "history"]
        )

    def invalidate_kpi(self, name: str) -> int:
        """Invalidate a specific KPI."""
        count = 0
        if self._cache.delete(f"kpi:{name}"):
            count += 1
        # Also invalidate dashboard
        if self._cache.delete("kpi:dashboard"):
            count += 1
        return count

    def invalidate_category(self, category: str) -> int:
        """Invalidate all KPIs in a category."""
        return self._cache.invalidate_by_tag(f"kpi:{category}")

    def invalidate_all(self) -> int:
        """Invalidate all KPI data."""
        return self._cache.invalidate_by_tag("kpi")


# ============================================
# Decorators
# ============================================

def cached(ttl: int = 300, tags: Optional[List[str]] = None, key_builder: Optional[Callable] = None):
    """Decorator to cache function results."""
    def decorator(func: Callable):
        @wraps(func)
        def wrapper(*args, **kwargs):
            cache = get_cache_manager()

            # Build cache key
            if key_builder:
                cache_key = key_builder(*args, **kwargs)
            else:
                key_parts = [func.__module__, func.__name__]
                key_parts.extend(str(a) for a in args)
                key_parts.extend(f"{k}={v}" for k, v in sorted(kwargs.items()))
                cache_key = hashlib.md5(":".join(key_parts).encode()).hexdigest()

            # Try to get from cache
            result = cache.get(cache_key)
            if result is not None:
                return result

            # Call function and cache result
            result = func(*args, **kwargs)
            cache.set(cache_key, result, ttl=ttl, tags=tags)

            return result
        return wrapper
    return decorator


def invalidate_on_change(tags: List[str]):
    """Decorator to invalidate cache tags when a function is called."""
    def decorator(func: Callable):
        @wraps(func)
        def wrapper(*args, **kwargs):
            result = func(*args, **kwargs)

            # Invalidate cache tags
            cache = get_cache_manager()
            for tag in tags:
                cache.invalidate_by_tag(tag)

            return result
        return wrapper
    return decorator


# ============================================
# Singleton Accessor
# ============================================

_cache_manager: Optional[CacheManager] = None
_kpi_cache: Optional[KPICache] = None


def get_cache_manager() -> CacheManager:
    """Get cache manager singleton."""
    global _cache_manager
    if _cache_manager is None:
        # Check for Redis configuration
        redis_url = os.environ.get("REDIS_URL", "")
        if redis_url:
            config = CacheConfig(
                backend=CacheBackend.REDIS,
                redis_url=redis_url
            )
        else:
            config = CacheConfig()

        _cache_manager = CacheManager.get_instance(config)
    return _cache_manager


def get_kpi_cache() -> KPICache:
    """Get KPI cache singleton."""
    global _kpi_cache
    if _kpi_cache is None:
        _kpi_cache = KPICache()
    return _kpi_cache


__all__ = [
    'CacheBackend',
    'CacheConfig',
    'CacheEntry',
    'CacheStats',
    'CacheManager',
    'KPICache',
    'MemoryCacheBackend',
    'RedisCacheBackend',
    'get_cache_manager',
    'get_kpi_cache',
    'cached',
    'invalidate_on_change',
]

__version__ = '8.0.0'
