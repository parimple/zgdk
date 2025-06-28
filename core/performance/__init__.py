"""
Performance optimization utilities for Discord bot.

This module provides tools for:
- Database query optimization
- Caching frequently accessed data
- Performance monitoring and metrics
- Connection pool management
"""

from .cache_manager import (
    CacheManager,
    CacheKeyBuilder,
    cache_manager,
    cache
)

from .database_optimizer import (
    DatabaseOptimizer,
    QueryPerformanceMonitor,
    QueryBatcher,
    db_optimizer,
    optimize_query,
    cache_result
)

__all__ = [
    # Cache management
    'CacheManager',
    'CacheKeyBuilder', 
    'cache_manager',
    'cache',
    
    # Database optimization
    'DatabaseOptimizer',
    'QueryPerformanceMonitor',
    'QueryBatcher',
    'db_optimizer',
    'optimize_query',
    'cache_result',
]