"""Performance monitoring for high-scale Discord bot."""

import asyncio
import logging
import time
from collections import defaultdict, deque
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

import discord
import psutil

logger = logging.getLogger(__name__)


class PerformanceMonitor:
    """Monitor bot performance for 100k+ users."""

    def __init__(self, bot):
        """Initialize performance monitor."""
        self.bot = bot
        self.start_time = time.time()
        
        # Metrics storage
        self.command_times = defaultdict(lambda: deque(maxlen=1000))
        self.event_times = defaultdict(lambda: deque(maxlen=1000))
        self.db_query_times = deque(maxlen=1000)
        self.message_rate = deque(maxlen=300)  # 5 minutes of data
        
        # Thresholds for alerts
        self.thresholds = {
            "command_latency": 1000,  # ms
            "db_query": 500,  # ms
            "memory_percent": 80,  # %
            "cpu_percent": 90,  # %
            "message_rate": 1000  # messages per second
        }
        
        # Analytics channel ID (will be set after test category is created)
        self.analytics_channel_id = None
        
        # Start monitoring task
        self.monitoring_task = None

    async def start(self):
        """Start performance monitoring."""
        self.monitoring_task = asyncio.create_task(self._monitoring_loop())
        logger.info("Performance monitoring started")

    async def stop(self):
        """Stop performance monitoring."""
        if self.monitoring_task:
            self.monitoring_task.cancel()
            logger.info("Performance monitoring stopped")

    async def _monitoring_loop(self):
        """Main monitoring loop."""
        while True:
            try:
                await self._collect_metrics()
                await self._check_thresholds()
                await asyncio.sleep(60)  # Check every minute
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}", exc_info=True)
                await asyncio.sleep(60)

    async def _collect_metrics(self):
        """Collect current metrics."""
        # System metrics
        process = psutil.Process()
        memory_info = process.memory_info()
        
        metrics = {
            "timestamp": datetime.utcnow(),
            "memory_mb": memory_info.rss / 1024 / 1024,
            "memory_percent": process.memory_percent(),
            "cpu_percent": process.cpu_percent(interval=1),
            "thread_count": process.num_threads(),
            "guild_count": len(self.bot.guilds),
            "user_count": sum(g.member_count for g in self.bot.guilds),
            "message_rate": len(self.message_rate) / 5 if self.message_rate else 0,  # per minute
            "uptime_hours": (time.time() - self.start_time) / 3600
        }
        
        # Command performance
        if self.command_times:
            all_times = []
            for times in self.command_times.values():
                all_times.extend(times)
            if all_times:
                metrics["avg_command_latency"] = sum(all_times) / len(all_times)
                metrics["max_command_latency"] = max(all_times)
        
        # DB performance
        if self.db_query_times:
            metrics["avg_db_query"] = sum(self.db_query_times) / len(self.db_query_times)
            metrics["max_db_query"] = max(self.db_query_times)
        
        # Log metrics
        logger.info(f"Performance metrics: {metrics}")
        
        # Send to analytics channel if available
        if self.analytics_channel_id:
            await self._send_analytics(metrics)
        
        return metrics

    async def _check_thresholds(self):
        """Check if any metrics exceed thresholds."""
        process = psutil.Process()
        alerts = []
        
        # Memory check
        memory_percent = process.memory_percent()
        if memory_percent > self.thresholds["memory_percent"]:
            alerts.append(f"⚠️ High memory usage: {memory_percent:.1f}%")
        
        # CPU check
        cpu_percent = process.cpu_percent(interval=0.1)
        if cpu_percent > self.thresholds["cpu_percent"]:
            alerts.append(f"⚠️ High CPU usage: {cpu_percent:.1f}%")
        
        # Command latency check
        if self.command_times:
            recent_times = []
            for times in self.command_times.values():
                recent_times.extend(list(times)[-100:])  # Last 100 commands
            if recent_times:
                avg_latency = sum(recent_times) / len(recent_times)
                if avg_latency > self.thresholds["command_latency"]:
                    alerts.append(f"⚠️ High command latency: {avg_latency:.0f}ms")
        
        # Message rate check
        if self.message_rate:
            rate_per_second = len(self.message_rate) / 300  # 5 minutes
            if rate_per_second > self.thresholds["message_rate"]:
                alerts.append(f"⚠️ High message rate: {rate_per_second:.0f}/s")
        
        # Send alerts
        if alerts and self.analytics_channel_id:
            channel = self.bot.get_channel(self.analytics_channel_id)
            if channel:
                embed = discord.Embed(
                    title="🚨 Performance Alert",
                    description="\n".join(alerts),
                    color=discord.Color.red(),
                    timestamp=datetime.utcnow()
                )
                await channel.send(embed=embed)

    async def _send_analytics(self, metrics: Dict[str, Any]):
        """Send analytics to Discord channel."""
        channel = self.bot.get_channel(self.analytics_channel_id)
        if not channel:
            return
        
        embed = discord.Embed(
            title="📊 Performance Report",
            color=discord.Color.blue(),
            timestamp=metrics["timestamp"]
        )
        
        # System info
        embed.add_field(
            name="System",
            value=(
                f"Memory: {metrics['memory_mb']:.0f}MB ({metrics['memory_percent']:.1f}%)\n"
                f"CPU: {metrics['cpu_percent']:.1f}%\n"
                f"Threads: {metrics['thread_count']}"
            ),
            inline=True
        )
        
        # Bot info
        embed.add_field(
            name="Bot Stats",
            value=(
                f"Guilds: {metrics['guild_count']}\n"
                f"Users: {metrics['user_count']:,}\n"
                f"Uptime: {metrics['uptime_hours']:.1f}h"
            ),
            inline=True
        )
        
        # Performance info
        perf_text = f"Messages/min: {metrics['message_rate']:.0f}"
        if "avg_command_latency" in metrics:
            perf_text += f"\nCmd latency: {metrics['avg_command_latency']:.0f}ms"
        if "avg_db_query" in metrics:
            perf_text += f"\nDB query: {metrics['avg_db_query']:.0f}ms"
        
        embed.add_field(
            name="Performance",
            value=perf_text,
            inline=True
        )
        
        await channel.send(embed=embed)

    def record_command_time(self, command_name: str, duration_ms: float):
        """Record command execution time."""
        self.command_times[command_name].append(duration_ms)

    def record_event_time(self, event_name: str, duration_ms: float):
        """Record event processing time."""
        self.event_times[event_name].append(duration_ms)

    def record_db_query_time(self, duration_ms: float):
        """Record database query time."""
        self.db_query_times.append(duration_ms)

    def record_message(self):
        """Record message for rate calculation."""
        self.message_rate.append(time.time())