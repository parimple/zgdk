"""
Cache management system for Discord bot.

Provides in-memory caching with TTL, LRU eviction,
and Redis support for distributed caching.
"""

import logging
import time
import asyncio
from typing import Dict, Any, Optional, Union, Callable, TypeVar
from datetime import datetime, timedelta
from collections import OrderedDict
from functools import wraps
import json
import pickle

logger = logging.getLogger(__name__)

T = TypeVar('T')


class CacheEntry:
    """Represents a cached value with metadata."""
    
    def __init__(self, value: Any, ttl_seconds: int):
        self.value = value
        self.created_at = time.time()
        self.ttl_seconds = ttl_seconds
        self.access_count = 0
        self.last_accessed = self.created_at
    
    @property
    def is_expired(self) -> bool:
        """Check if cache entry has expired."""
        return time.time() - self.created_at > self.ttl_seconds
    
    def access(self):
        """Record an access to this cache entry."""
        self.access_count += 1
        self.last_accessed = time.time()


class LRUCache:
    """Least Recently Used cache implementation."""
    
    def __init__(self, max_size: int = 1000):
        self.max_size = max_size
        self.cache: OrderedDict[str, CacheEntry] = OrderedDict()
        self.hits = 0
        self.misses = 0
    
    def get(self, key: str) -> Optional[Any]:
        """Get value from cache."""
        if key not in self.cache:
            self.misses += 1
            return None
        
        entry = self.cache[key]
        
        # Check expiration
        if entry.is_expired:
            del self.cache[key]
            self.misses += 1
            return None
        
        # Move to end (most recently used)
        self.cache.move_to_end(key)
        entry.access()
        self.hits += 1
        
        return entry.value
    
    def set(self, key: str, value: Any, ttl_seconds: int = 300):
        """Set value in cache."""
        # Remove if exists to update position
        if key in self.cache:
            del self.cache[key]
        
        # Add new entry
        self.cache[key] = CacheEntry(value, ttl_seconds)
        
        # Evict oldest if over capacity
        while len(self.cache) > self.max_size:
            self.cache.popitem(last=False)
    
    def delete(self, key: str) -> bool:
        """Delete key from cache."""
        if key in self.cache:
            del self.cache[key]
            return True
        return False
    
    def clear(self):
        """Clear all cache entries."""
        self.cache.clear()
        self.hits = 0
        self.misses = 0
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        total_requests = self.hits + self.misses
        hit_rate = self.hits / total_requests if total_requests > 0 else 0
        
        return {
            'size': len(self.cache),
            'max_size': self.max_size,
            'hits': self.hits,
            'misses': self.misses,
            'hit_rate': hit_rate,
            'total_requests': total_requests
        }
    
    def cleanup_expired(self):
        """Remove all expired entries."""
        expired_keys = [
            key for key, entry in self.cache.items()
            if entry.is_expired
        ]
        
        for key in expired_keys:
            del self.cache[key]
        
        return len(expired_keys)


class CacheManager:
    """Main cache manager supporting multiple cache backends."""
    
    def __init__(self, default_ttl: int = 300):
        self.default_ttl = default_ttl
        self.caches: Dict[str, LRUCache] = {
            'default': LRUCache(max_size=1000),
            'members': LRUCache(max_size=5000),
            'roles': LRUCache(max_size=500),
            'activities': LRUCache(max_size=2000),
            'permissions': LRUCache(max_size=1000),
        }
        self._cleanup_task = None
        # Don't start cleanup task in __init__, start it manually when bot starts
    
    def _start_cleanup_task(self):
        """Start periodic cleanup of expired entries."""
        async def cleanup_loop():
            while True:
                await asyncio.sleep(60)  # Run every minute
                total_cleaned = 0
                
                for cache_name, cache in self.caches.items():
                    cleaned = cache.cleanup_expired()
                    if cleaned > 0:
                        logger.info(f"Cleaned {cleaned} expired entries from {cache_name} cache")
                    total_cleaned += cleaned
        
        try:
            self._cleanup_task = asyncio.create_task(cleanup_loop())
        except RuntimeError:
            # No event loop running yet, skip cleanup task
            logger.debug("Skipping cleanup task creation - no event loop")
            
    async def start(self):
        """Start the cache manager cleanup task."""
        if self._cleanup_task is None:
            self._start_cleanup_task()
    
    def get_cache(self, namespace: str = 'default') -> LRUCache:
        """Get cache for specific namespace."""
        if namespace not in self.caches:
            self.caches[namespace] = LRUCache()
        return self.caches[namespace]
    
    async def get(
        self, 
        key: str, 
        namespace: str = 'default'
    ) -> Optional[Any]:
        """Get value from cache."""
        cache = self.get_cache(namespace)
        return cache.get(key)
    
    async def set(
        self, 
        key: str, 
        value: Any,
        ttl: Optional[int] = None,
        namespace: str = 'default'
    ):
        """Set value in cache."""
        cache = self.get_cache(namespace)
        ttl = ttl or self.default_ttl
        cache.set(key, value, ttl)
    
    async def delete(self, key: str, namespace: str = 'default') -> bool:
        """Delete key from cache."""
        cache = self.get_cache(namespace)
        return cache.delete(key)
    
    async def clear(self, namespace: Optional[str] = None):
        """Clear cache(s)."""
        if namespace:
            cache = self.get_cache(namespace)
            cache.clear()
        else:
            for cache in self.caches.values():
                cache.clear()
    
    def get_stats(self) -> Dict[str, Any]:
        """Get statistics for all caches."""
        stats = {}
        total_size = 0
        total_hits = 0
        total_misses = 0
        
        for name, cache in self.caches.items():
            cache_stats = cache.get_stats()
            stats[name] = cache_stats
            total_size += cache_stats['size']
            total_hits += cache_stats['hits']
            total_misses += cache_stats['misses']
        
        total_requests = total_hits + total_misses
        overall_hit_rate = total_hits / total_requests if total_requests > 0 else 0
        
        stats['overall'] = {
            'total_size': total_size,
            'total_hits': total_hits,
            'total_misses': total_misses,
            'overall_hit_rate': overall_hit_rate,
            'total_requests': total_requests
        }
        
        return stats
    
    def cache(
        self,
        namespace: str = 'default',
        ttl: Optional[int] = None,
        key_func: Optional[Callable] = None
    ):
        """
        Decorator for caching function results.
        
        Args:
            namespace: Cache namespace to use
            ttl: Time to live in seconds
            key_func: Function to generate cache key from arguments
        """
        def decorator(func: Callable) -> Callable:
            @wraps(func)
            async def wrapper(*args, **kwargs):
                # Generate cache key
                if key_func:
                    cache_key = key_func(*args, **kwargs)
                else:
                    # Default key generation
                    key_parts = [func.__name__]
                    
                    # Add args (skip self if method)
                    if args and hasattr(args[0], '__class__'):
                        key_parts.extend(str(arg) for arg in args[1:])
                    else:
                        key_parts.extend(str(arg) for arg in args)
                    
                    # Add kwargs
                    key_parts.extend(f"{k}={v}" for k, v in sorted(kwargs.items()))
                    
                    cache_key = ":".join(key_parts)
                
                # Check cache
                cached_value = await self.get(cache_key, namespace)
                if cached_value is not None:
                    logger.debug(f"Cache hit for {func.__name__} with key {cache_key}")
                    return cached_value
                
                # Execute function
                result = await func(*args, **kwargs)
                
                # Store in cache
                await self.set(cache_key, result, ttl, namespace)
                
                return result
            
            # Add cache control methods
            wrapper.invalidate = lambda *args, **kwargs: self._invalidate_cached(
                func, namespace, key_func, *args, **kwargs
            )
            
            return wrapper
        return decorator
    
    async def _invalidate_cached(
        self,
        func: Callable,
        namespace: str,
        key_func: Optional[Callable],
        *args,
        **kwargs
    ):
        """Invalidate cached result for specific arguments."""
        if key_func:
            cache_key = key_func(*args, **kwargs)
        else:
            # Same key generation as in decorator
            key_parts = [func.__name__]
            if args and hasattr(args[0], '__class__'):
                key_parts.extend(str(arg) for arg in args[1:])
            else:
                key_parts.extend(str(arg) for arg in args)
            key_parts.extend(f"{k}={v}" for k, v in sorted(kwargs.items()))
            cache_key = ":".join(key_parts)
        
        await self.delete(cache_key, namespace)


class CacheKeyBuilder:
    """Utility for building cache keys."""
    
    @staticmethod
    def member_key(member_id: int) -> str:
        """Build cache key for member data."""
        return f"member:{member_id}"
    
    @staticmethod
    def role_key(member_id: int, role_id: int) -> str:
        """Build cache key for member role."""
        return f"role:{member_id}:{role_id}"
    
    @staticmethod
    def activity_key(member_id: int, date: Optional[datetime] = None) -> str:
        """Build cache key for activity data."""
        if date:
            date_str = date.strftime("%Y-%m-%d")
            return f"activity:{member_id}:{date_str}"
        return f"activity:{member_id}"
    
    @staticmethod
    def permission_key(channel_id: int, user_id: int) -> str:
        """Build cache key for permissions."""
        return f"perm:{channel_id}:{user_id}"
    
    @staticmethod
    def invite_key(invite_code: str) -> str:
        """Build cache key for invite data."""
        return f"invite:{invite_code}"
    
    @staticmethod
    def leaderboard_key(type: str, days: int = 7) -> str:
        """Build cache key for leaderboard data."""
        return f"leaderboard:{type}:{days}"


# Global cache manager instance
cache_manager = CacheManager()

# Convenience decorator
cache = cache_manager.cache