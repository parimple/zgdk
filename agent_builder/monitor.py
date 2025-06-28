"""Monitoring and optimization for AI agents."""

import asyncio
import logging
from collections import deque
from datetime import datetime, timedelta
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


class AgentMonitor:
    """Monitor agent performance and health."""

    def __init__(self, agent_id: str, agent: Any):
        self.agent_id = agent_id
        self.agent = agent
        self.running = False
        self._monitor_task = None

        # Metrics storage
        self.metrics_history = deque(maxlen=1000)
        self.error_log = deque(maxlen=100)
        self.performance_stats = {
            "avg_response_time": 0,
            "success_rate": 100.0,
            "throughput": 0,
            "last_optimization": None,
        }

    async def start(self):
        """Start monitoring the agent."""
        self.running = True
        self._monitor_task = asyncio.create_task(self._monitor_loop())
        logger.info(f"Started monitoring for agent '{self.agent_id}'")

    async def stop(self):
        """Stop monitoring."""
        self.running = False
        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass

    async def _monitor_loop(self):
        """Main monitoring loop."""
        while self.running:
            try:
                # Collect metrics
                metrics = await self._collect_metrics()
                self.metrics_history.append({"timestamp": datetime.now(), "metrics": metrics})

                # Analyze performance
                self._analyze_performance()

                # Check for issues
                issues = self._detect_issues()
                if issues:
                    await self._handle_issues(issues)

                # Check if optimization needed
                if self._needs_optimization():
                    await self._trigger_optimization()

                await asyncio.sleep(30)  # Monitor every 30 seconds

            except Exception as e:
                logger.error(f"Monitor error for '{self.agent_id}': {e}")
                self.error_log.append({"timestamp": datetime.now(), "error": str(e)})

    async def _collect_metrics(self) -> Dict[str, Any]:
        """Collect current metrics from agent."""
        metrics = {}

        if hasattr(self.agent, "get_metrics"):
            agent_metrics = await self.agent.get_metrics()
            metrics.update(agent_metrics)

        # Add system metrics
        metrics["memory_usage"] = self._get_memory_usage()
        metrics["cpu_usage"] = self._get_cpu_usage()

        return metrics

    def _analyze_performance(self):
        """Analyze performance trends."""
        if len(self.metrics_history) < 10:
            return

        recent_metrics = list(self.metrics_history)[-10:]

        # Calculate average response time
        response_times = [m["metrics"].get("avg_duration", 0) for m in recent_metrics]
        self.performance_stats["avg_response_time"] = sum(response_times) / len(response_times)

        # Calculate success rate
        total_processed = sum(m["metrics"].get("total_processed", 0) for m in recent_metrics)
        total_errors = sum(m["metrics"].get("total_errors", 0) for m in recent_metrics)

        if total_processed > 0:
            self.performance_stats["success_rate"] = (total_processed - total_errors) / total_processed * 100

        # Calculate throughput
        time_span = (recent_metrics[-1]["timestamp"] - recent_metrics[0]["timestamp"]).total_seconds()
        if time_span > 0:
            self.performance_stats["throughput"] = total_processed / time_span

    def _detect_issues(self) -> List[Dict[str, Any]]:
        """Detect performance or health issues."""
        issues = []

        # High error rate
        if self.performance_stats["success_rate"] < 90:
            issues.append(
                {"type": "high_error_rate", "severity": "high", "value": self.performance_stats["success_rate"]}
            )

        # Slow response time
        if self.performance_stats["avg_response_time"] > 5.0:  # 5 seconds
            issues.append(
                {"type": "slow_response", "severity": "medium", "value": self.performance_stats["avg_response_time"]}
            )

        # Low throughput
        if self.performance_stats["throughput"] < 0.1:  # Less than 1 request per 10 seconds
            issues.append({"type": "low_throughput", "severity": "low", "value": self.performance_stats["throughput"]})

        return issues

    async def _handle_issues(self, issues: List[Dict[str, Any]]):
        """Handle detected issues."""
        for issue in issues:
            logger.warning(
                f"Issue detected for '{self.agent_id}': "
                f"{issue['type']} (severity: {issue['severity']}, value: {issue['value']})"
            )

            # Auto-remediation for critical issues
            if issue["severity"] == "high":
                if issue["type"] == "high_error_rate":
                    # Could trigger agent restart or scaling
                    logger.info(f"Consider restarting agent '{self.agent_id}' due to high error rate")

    def _needs_optimization(self) -> bool:
        """Check if agent needs optimization."""
        # Don't optimize too frequently
        if self.performance_stats["last_optimization"]:
            time_since_optimization = datetime.now() - self.performance_stats["last_optimization"]
            if time_since_optimization < timedelta(hours=1):
                return False

        # Check if performance is degrading
        if self.performance_stats["avg_response_time"] > 3.0:
            return True

        if self.performance_stats["success_rate"] < 95:
            return True

        return False

    async def _trigger_optimization(self):
        """Trigger agent optimization."""
        logger.info(f"Triggering optimization for agent '{self.agent_id}'")

        # This could trigger various optimizations:
        # - Code optimization via optimizer agent
        # - Cache warming
        # - Resource reallocation
        # - Model fine-tuning

        self.performance_stats["last_optimization"] = datetime.now()

    def get_metrics(self) -> Dict[str, Any]:
        """Get current metrics summary."""
        return {
            "performance": self.performance_stats.copy(),
            "recent_errors": len(self.error_log),
            "metrics_collected": len(self.metrics_history),
        }

    def _get_memory_usage(self) -> float:
        """Get memory usage (mock implementation)."""
        # In real implementation, would use psutil or similar
        return 256.0  # MB

    def _get_cpu_usage(self) -> float:
        """Get CPU usage (mock implementation)."""
        # In real implementation, would use psutil or similar
        return 15.0  # Percentage
