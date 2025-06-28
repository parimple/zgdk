"""
High-performance caching service for ZGDK Discord Bot.
Implements intelligent caching with TTL, invalidation patterns, and performance metrics.
"""

import asyncio
import hashlib
import json
import logging
import time
from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional, Set, Union

logger = logging.getLogger(__name__)


@dataclass
class CacheEntry:
    """Individual cache entry with metadata."""

    value: Any
    created_at: float
    expires_at: Optional[float]
    access_count: int = 0
    last_accessed: float = 0
    tags: Set[str] = None

    def __post_init__(self):
        if self.tags is None:
            self.tags = set()
        self.last_accessed = time.time()

    @property
    def is_expired(self) -> bool:
        """Check if entry is expired."""
        if self.expires_at is None:
            return False
        return time.time() > self.expires_at

    @property
    def age_seconds(self) -> float:
        """Get age of entry in seconds."""
        return time.time() - self.created_at

    def access(self) -> Any:
        """Record access and return value."""
        self.access_count += 1
        self.last_accessed = time.time()
        return self.value


@dataclass
class CacheStats:
    """Cache performance statistics."""

    hits: int = 0
    misses: int = 0
    sets: int = 0
    deletes: int = 0
    evictions: int = 0
    expired_cleanups: int = 0

    @property
    def hit_ratio(self) -> float:
        """Calculate cache hit ratio."""
        total = self.hits + self.misses
        return self.hits / total if total > 0 else 0.0

    @property
    def total_operations(self) -> int:
        """Total cache operations."""
        return self.hits + self.misses + self.sets + self.deletes


class CacheService:
    """
    High-performance memory cache with advanced features:
    - TTL (Time To Live) support
    - Tag-based invalidation
    - LRU eviction
    - Performance metrics
    - Key namespacing
    """

    def __init__(self, max_size: int = 10000, default_ttl: int = 300):
        self._cache: Dict[str, CacheEntry] = {}
        self._max_size = max_size
        self._default_ttl = default_ttl
        self._stats = CacheStats()
        self._lock = asyncio.Lock()

        # Tag tracking for invalidation
        self._tag_to_keys: Dict[str, Set[str]] = {}

        # Start background cleanup task
        self._cleanup_task = asyncio.create_task(self._cleanup_expired())

    def _generate_key(self, namespace: str, key: str, **kwargs) -> str:
        """Generate cache key with namespace and parameters."""
        if kwargs:
            # Sort kwargs for consistent key generation
            params_str = json.dumps(kwargs, sort_keys=True, default=str)
            key_data = f"{namespace}:{key}:{params_str}"
        else:
            key_data = f"{namespace}:{key}"

        # Hash long keys to avoid memory issues
        if len(key_data) > 250:
            return f"{namespace}:{hashlib.md5(key_data.encode()).hexdigest()}"
        return key_data

    async def get(self, namespace: str, key: str, default: Any = None, **kwargs) -> Any:
        """Get value from cache."""
        cache_key = self._generate_key(namespace, key, **kwargs)

        async with self._lock:
            entry = self._cache.get(cache_key)

            if entry is None:
                self._stats.misses += 1
                logger.debug(f"Cache MISS: {cache_key}")
                return default

            if entry.is_expired:
                # Remove expired entry
                await self._remove_entry(cache_key)
                self._stats.misses += 1
                self._stats.expired_cleanups += 1
                logger.debug(f"Cache EXPIRED: {cache_key}")
                return default

            # Cache hit
            self._stats.hits += 1
            logger.debug(f"Cache HIT: {cache_key} (age: {entry.age_seconds:.1f}s)")
            return entry.access()

    async def set(
        self, namespace: str, key: str, value: Any, ttl: Optional[int] = None, tags: Optional[Set[str]] = None, **kwargs
    ) -> None:
        """Set value in cache with optional TTL and tags."""
        cache_key = self._generate_key(namespace, key, **kwargs)

        if ttl is None:
            ttl = self._default_ttl

        expires_at = time.time() + ttl if ttl > 0 else None
        entry_tags = tags or set()

        async with self._lock:
            # Check if we need to evict entries
            if len(self._cache) >= self._max_size:
                await self._evict_lru()

            # Remove old entry if exists (for tag cleanup)
            if cache_key in self._cache:
                await self._remove_entry(cache_key)

            # Create new entry
            entry = CacheEntry(value=value, created_at=time.time(), expires_at=expires_at, tags=entry_tags)

            self._cache[cache_key] = entry
            self._stats.sets += 1

            # Update tag tracking
            for tag in entry_tags:
                if tag not in self._tag_to_keys:
                    self._tag_to_keys[tag] = set()
                self._tag_to_keys[tag].add(cache_key)

            logger.debug(f"Cache SET: {cache_key} (ttl: {ttl}s, tags: {entry_tags})")

    async def delete(self, namespace: str, key: str, **kwargs) -> bool:
        """Delete specific cache entry."""
        cache_key = self._generate_key(namespace, key, **kwargs)

        async with self._lock:
            if cache_key in self._cache:
                await self._remove_entry(cache_key)
                self._stats.deletes += 1
                logger.debug(f"Cache DELETE: {cache_key}")
                return True
            return False

    async def invalidate_by_tags(self, tags: Union[str, Set[str]]) -> int:
        """Invalidate all cache entries with specified tags."""
        if isinstance(tags, str):
            tags = {tags}

        async with self._lock:
            keys_to_remove = set()

            for tag in tags:
                if tag in self._tag_to_keys:
                    keys_to_remove.update(self._tag_to_keys[tag])

            removed_count = 0
            for cache_key in keys_to_remove:
                if cache_key in self._cache:
                    await self._remove_entry(cache_key)
                    removed_count += 1

            logger.info(f"Cache invalidated {removed_count} entries by tags: {tags}")
            return removed_count

    async def invalidate_namespace(self, namespace: str) -> int:
        """Invalidate all entries in a namespace."""
        async with self._lock:
            prefix = f"{namespace}:"
            keys_to_remove = [key for key in self._cache.keys() if key.startswith(prefix)]

            removed_count = 0
            for cache_key in keys_to_remove:
                await self._remove_entry(cache_key)
                removed_count += 1

            logger.info(f"Cache invalidated {removed_count} entries in namespace: {namespace}")
            return removed_count

    async def clear(self) -> None:
        """Clear all cache entries."""
        async with self._lock:
            count = len(self._cache)
            self._cache.clear()
            self._tag_to_keys.clear()
            logger.info(f"Cache cleared {count} entries")

    def get_stats(self) -> Dict[str, Any]:
        """Get cache performance statistics."""
        return {
            "hits": self._stats.hits,
            "misses": self._stats.misses,
            "sets": self._stats.sets,
            "deletes": self._stats.deletes,
            "evictions": self._stats.evictions,
            "expired_cleanups": self._stats.expired_cleanups,
            "hit_ratio": self._stats.hit_ratio,
            "total_operations": self._stats.total_operations,
            "current_size": len(self._cache),
            "max_size": self._max_size,
            "tag_count": len(self._tag_to_keys),
        }

    async def get_or_set(
        self,
        namespace: str,
        key: str,
        factory: Callable,
        ttl: Optional[int] = None,
        tags: Optional[Set[str]] = None,
        **kwargs,
    ) -> Any:
        """Get value from cache or set it using factory function."""
        # Try to get from cache first
        value = await self.get(namespace, key, **kwargs)

        if value is not None:
            return value

        # Value not in cache, create it
        try:
            if asyncio.iscoroutinefunction(factory):
                value = await factory()
            else:
                value = factory()

            # Store in cache
            await self.set(namespace, key, value, ttl=ttl, tags=tags, **kwargs)
            return value

        except Exception as e:
            logger.error(f"Factory function failed for {namespace}:{key}: {e}")
            raise

    async def _remove_entry(self, cache_key: str) -> None:
        """Remove cache entry and clean up tags."""
        if cache_key not in self._cache:
            return

        entry = self._cache[cache_key]

        # Clean up tag references
        for tag in entry.tags:
            if tag in self._tag_to_keys:
                self._tag_to_keys[tag].discard(cache_key)
                if not self._tag_to_keys[tag]:
                    del self._tag_to_keys[tag]

        del self._cache[cache_key]

    async def _evict_lru(self) -> None:
        """Evict least recently used entries."""
        if not self._cache:
            return

        # Find LRU entries (oldest last_accessed)
        sorted_entries = sorted(self._cache.items(), key=lambda x: x[1].last_accessed)

        # Evict 10% of cache size to avoid frequent evictions
        evict_count = max(1, len(self._cache) // 10)

        for i in range(evict_count):
            if i < len(sorted_entries):
                cache_key = sorted_entries[i][0]
                await self._remove_entry(cache_key)
                self._stats.evictions += 1

    async def _cleanup_expired(self) -> None:
        """Background task to clean up expired entries."""
        while True:
            try:
                await asyncio.sleep(60)  # Run every minute

                async with self._lock:
                    expired_keys = []
                    for cache_key, entry in self._cache.items():
                        if entry.is_expired:
                            expired_keys.append(cache_key)

                    for cache_key in expired_keys:
                        await self._remove_entry(cache_key)
                        self._stats.expired_cleanups += 1

                    if expired_keys:
                        logger.debug(f"Cleaned up {len(expired_keys)} expired cache entries")

            except Exception as e:
                logger.error(f"Error in cache cleanup task: {e}")

    def __del__(self):
        """Cleanup when service is destroyed."""
        if hasattr(self, "_cleanup_task") and not self._cleanup_task.done():
            self._cleanup_task.cancel()


# Decorator for easy caching
def cached(namespace: str, ttl: int = 300, tags: Optional[Set[str]] = None, key_func: Optional[Callable] = None):
    """
    Decorator to cache function results.

    Args:
        namespace: Cache namespace
        ttl: Time to live in seconds
        tags: Cache tags for invalidation
        key_func: Function to generate cache key from args
    """

    def decorator(func):
        async def wrapper(*args, **kwargs):
            # Get cache service from first argument (assumed to be self with cache_service)
            if args and hasattr(args[0], "cache_service"):
                cache_service = args[0].cache_service
            else:
                # Fallback - create temporary cache
                cache_service = CacheService()

            # Generate cache key
            if key_func:
                cache_key = key_func(*args, **kwargs)
            else:
                # Default key generation
                func_name = func.__name__
                args_str = str(args[1:])  # Skip self
                kwargs_str = str(sorted(kwargs.items()))
                cache_key = f"{func_name}:{args_str}:{kwargs_str}"

            # Try cache first
            result = await cache_service.get(namespace, cache_key)
            if result is not None:
                return result

            # Execute function
            if asyncio.iscoroutinefunction(func):
                result = await func(*args, **kwargs)
            else:
                result = func(*args, **kwargs)

            # Store in cache
            await cache_service.set(namespace, cache_key, result, ttl=ttl, tags=tags)

            return result

        return wrapper

    return decorator


# Global cache instance
_global_cache: Optional[CacheService] = None


def get_cache() -> CacheService:
    """Get global cache instance."""
    global _global_cache
    if _global_cache is None:
        _global_cache = CacheService()
    return _global_cache
