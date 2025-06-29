"""
Database performance optimization utilities.

This module provides tools for optimizing database queries,
managing connection pools, and implementing caching strategies.
"""

import asyncio
import logging
import time
from collections import defaultdict
from datetime import datetime, timedelta
from functools import wraps
from typing import Any, Callable, Dict, List, Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


class QueryPerformanceMonitor:
    """Monitor and analyze database query performance."""

    def __init__(self):
        self.query_stats = defaultdict(
            lambda: {"count": 0, "total_time": 0.0, "min_time": float("inf"), "max_time": 0.0, "last_executed": None}
        )
        self.slow_query_threshold = 1.0  # seconds
        self.slow_queries = []

    def record_query(self, query_name: str, execution_time: float):
        """Record query execution statistics."""
        stats = self.query_stats[query_name]
        stats["count"] += 1
        stats["total_time"] += execution_time
        stats["min_time"] = min(stats["min_time"], execution_time)
        stats["max_time"] = max(stats["max_time"], execution_time)
        stats["last_executed"] = datetime.now()

        # Track slow queries
        if execution_time > self.slow_query_threshold:
            self.slow_queries.append({"query": query_name, "time": execution_time, "timestamp": datetime.now()})
            logger.warning(f"Slow query detected: {query_name} took {execution_time:.3f}s")

    def get_statistics(self) -> Dict[str, Any]:
        """Get performance statistics."""
        stats = {}

        for query_name, data in self.query_stats.items():
            avg_time = data["total_time"] / data["count"] if data["count"] > 0 else 0
            stats[query_name] = {
                "count": data["count"],
                "avg_time": avg_time,
                "min_time": data["min_time"],
                "max_time": data["max_time"],
                "total_time": data["total_time"],
                "last_executed": data["last_executed"],
            }

        return {
            "queries": stats,
            "slow_queries": self.slow_queries[-100:],  # Last 100 slow queries
            "total_queries": sum(s["count"] for s in self.query_stats.values()),
        }


class DatabaseOptimizer:
    """Optimize database operations and manage performance."""

    def __init__(self):
        self.monitor = QueryPerformanceMonitor()
        self._cache = {}
        self._cache_ttl = {}
        self._connection_pool_size = 20
        self._connection_pool_overflow = 10

    def optimize_query(self, func: Callable) -> Callable:
        """Decorator to optimize and monitor database queries."""

        @wraps(func)
        async def wrapper(*args, **kwargs):
            start_time = time.time()
            query_name = f"{func.__module__}.{func.__name__}"

            try:
                result = await func(*args, **kwargs)
                execution_time = time.time() - start_time

                self.monitor.record_query(query_name, execution_time)

                if execution_time > 0.5:
                    logger.info(f"Query {query_name} took {execution_time:.3f}s")

                return result

            except Exception as e:
                execution_time = time.time() - start_time
                logger.error(f"Query {query_name} failed after {execution_time:.3f}s: {e}")
                raise

        return wrapper

    def cache_result(self, ttl_seconds: int = 300, key_func: Optional[Callable] = None) -> Callable:
        """
        Decorator to cache query results.

        Args:
            ttl_seconds: Time to live for cache entries
            key_func: Function to generate cache key from arguments
        """

        def decorator(func: Callable) -> Callable:
            @wraps(func)
            async def wrapper(*args, **kwargs):
                # Generate cache key
                if key_func:
                    cache_key = key_func(*args, **kwargs)
                else:
                    # Simple key generation
                    cache_key = f"{func.__name__}:{str(args)}:{str(kwargs)}"

                # Check cache
                if cache_key in self._cache:
                    if datetime.now() < self._cache_ttl[cache_key]:
                        logger.debug(f"Cache hit for {cache_key}")
                        return self._cache[cache_key]
                    else:
                        # Expired
                        del self._cache[cache_key]
                        del self._cache_ttl[cache_key]

                # Execute query
                result = await func(*args, **kwargs)

                # Store in cache
                self._cache[cache_key] = result
                self._cache_ttl[cache_key] = datetime.now() + timedelta(seconds=ttl_seconds)

                return result

            return wrapper

        return decorator

    def clear_cache(self, pattern: Optional[str] = None):
        """Clear cache entries matching pattern."""
        if pattern:
            keys_to_remove = [k for k in self._cache.keys() if pattern in k]
            for key in keys_to_remove:
                del self._cache[key]
                del self._cache_ttl[key]

            logger.info(f"Cleared {len(keys_to_remove)} cache entries matching '{pattern}'")
        else:
            self._cache.clear()
            self._cache_ttl.clear()
            logger.info("Cleared all cache entries")

    async def analyze_indexes(self, session: AsyncSession) -> Dict[str, Any]:
        """Analyze database indexes and suggest optimizations."""
        results = {}

        # Get table statistics
        table_stats_query = text(
            """
            SELECT
                schemaname,
                tablename,
                n_live_tup as row_count,
                n_dead_tup as dead_rows,
                last_vacuum,
                last_autovacuum
            FROM pg_stat_user_tables
            ORDER BY n_live_tup DESC
        """
        )

        result = await session.execute(table_stats_query)
        results["table_stats"] = [dict(row) for row in result]

        # Get index usage
        index_usage_query = text(
            """
            SELECT
                schemaname,
                tablename,
                indexname,
                idx_scan as index_scans,
                idx_tup_read as tuples_read,
                idx_tup_fetch as tuples_fetched
            FROM pg_stat_user_indexes
            ORDER BY idx_scan DESC
        """
        )

        result = await session.execute(index_usage_query)
        results["index_usage"] = [dict(row) for row in result]

        # Get unused indexes
        unused_indexes_query = text(
            """
            SELECT
                schemaname,
                tablename,
                indexname,
                idx_scan as index_scans
            FROM pg_stat_user_indexes
            WHERE idx_scan = 0
            AND indexname NOT LIKE '%_pkey'
        """
        )

        result = await session.execute(unused_indexes_query)
        results["unused_indexes"] = [dict(row) for row in result]

        return results

    async def get_slow_queries(self, session: AsyncSession) -> List[Dict[str, Any]]:
        """Get slow queries from PostgreSQL."""
        slow_queries_query = text(
            """
            SELECT
                query,
                calls,
                total_time,
                mean_time,
                min_time,
                max_time
            FROM pg_stat_statements
            WHERE query NOT LIKE '%pg_stat_statements%'
            ORDER BY mean_time DESC
            LIMIT 20
        """
        )

        try:
            result = await session.execute(slow_queries_query)
            return [dict(row) for row in result]
        except Exception as e:
            logger.warning(f"Could not fetch slow queries (pg_stat_statements may not be enabled): {e}")
            return []

    def get_connection_pool_config(self) -> Dict[str, Any]:
        """Get optimized connection pool configuration."""
        return {
            "pool_size": self._connection_pool_size,
            "max_overflow": self._connection_pool_overflow,
            "pool_timeout": 30,
            "pool_recycle": 1800,  # Recycle connections after 30 minutes
            "pool_pre_ping": True,  # Test connections before using
            "echo_pool": False,  # Set to True for debugging
        }

    async def optimize_tables(self, session: AsyncSession) -> Dict[str, Any]:
        """Run maintenance operations on tables."""
        results = {}

        # Get tables that need vacuum
        vacuum_query = text(
            """
            SELECT
                schemaname,
                tablename,
                n_dead_tup,
                n_live_tup,
                last_vacuum,
                last_autovacuum
            FROM pg_stat_user_tables
            WHERE n_dead_tup > 1000
            OR (n_dead_tup > 0.1 * n_live_tup AND n_live_tup > 0)
            ORDER BY n_dead_tup DESC
        """
        )

        result = await session.execute(vacuum_query)
        tables_to_vacuum = [dict(row) for row in result]
        results["tables_needing_vacuum"] = tables_to_vacuum

        # Analyze tables
        for table in tables_to_vacuum[:5]:  # Limit to top 5
            try:
                await session.execute(text(f"VACUUM ANALYZE {table['schemaname']}.{table['tablename']}"))
                logger.info(f"Vacuumed table {table['tablename']}")
            except Exception as e:
                logger.error(f"Failed to vacuum {table['tablename']}: {e}")

        return results


class QueryBatcher:
    """Batch multiple queries for efficient execution."""

    def __init__(self, batch_size: int = 100, delay_ms: int = 10):
        self.batch_size = batch_size
        self.delay_ms = delay_ms
        self._pending_queries = []
        self._results = {}
        self._batch_task = None

    async def add_query(self, query_id: str, query_func: Callable) -> Any:
        """Add a query to the batch."""
        future = asyncio.Future()
        self._pending_queries.append((query_id, query_func, future))

        # Start batch processing if not already running
        if not self._batch_task or self._batch_task.done():
            self._batch_task = asyncio.create_task(self._process_batch())

        return await future

    async def _process_batch(self):
        """Process pending queries in batch."""
        # Wait for more queries to accumulate
        await asyncio.sleep(self.delay_ms / 1000)

        # Process up to batch_size queries
        batch = self._pending_queries[: self.batch_size]
        self._pending_queries = self._pending_queries[self.batch_size :]

        if not batch:
            return

        # Execute all queries concurrently
        tasks = []
        futures = []

        for query_id, query_func, future in batch:
            tasks.append(query_func())
            futures.append(future)

        try:
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Set results or exceptions
            for i, (result, future) in enumerate(zip(results, futures)):
                if isinstance(result, Exception):
                    future.set_exception(result)
                else:
                    future.set_result(result)

        except Exception as e:
            # Set exception for all futures
            for future in futures:
                if not future.done():
                    future.set_exception(e)


# Global optimizer instance
db_optimizer = DatabaseOptimizer()


# Convenience decorators
optimize_query = db_optimizer.optimize_query
cache_result = db_optimizer.cache_result
