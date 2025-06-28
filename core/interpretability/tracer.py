"""
Command execution tracer for debugging and monitoring.
"""

import asyncio
import time
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
import logging

from discord.ext import commands

logger = logging.getLogger(__name__)


@dataclass
class TraceStep:
    """Represents a single step in command execution."""
    name: str
    start_time: float
    end_time: Optional[float] = None
    result: Optional[Any] = None
    error: Optional[Exception] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def duration_ms(self) -> Optional[float]:
        """Get step duration in milliseconds."""
        if self.end_time:
            return (self.end_time - self.start_time) * 1000
        return None
    
    def complete(self, result: Any = None, error: Exception = None):
        """Mark step as complete."""
        self.end_time = time.time()
        self.result = result
        self.error = error


@dataclass
class TraceContext:
    """Context for tracing command execution."""
    command_name: str
    user_id: str
    guild_id: Optional[str]
    start_time: float = field(default_factory=time.time)
    steps: List[TraceStep] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def total_duration_ms(self) -> float:
        """Get total execution time in milliseconds."""
        if self.steps:
            last_step = max(self.steps, key=lambda s: s.end_time or 0)
            if last_step.end_time:
                return (last_step.end_time - self.start_time) * 1000
        return (time.time() - self.start_time) * 1000
    
    def add_step(self, name: str, **metadata) -> TraceStep:
        """Add a new step to the trace."""
        step = TraceStep(name=name, start_time=time.time(), metadata=metadata)
        self.steps.append(step)
        return step
    
    def get_summary(self) -> Dict[str, Any]:
        """Get execution summary."""
        return {
            "command": self.command_name,
            "user_id": self.user_id,
            "guild_id": self.guild_id,
            "total_duration_ms": self.total_duration_ms,
            "steps_count": len(self.steps),
            "steps": [
                {
                    "name": step.name,
                    "duration_ms": step.duration_ms,
                    "success": step.error is None,
                    "error": str(step.error) if step.error else None
                }
                for step in self.steps
            ],
            "metadata": self.metadata
        }


class CommandTracer:
    """Traces command execution for debugging and performance monitoring."""
    
    def __init__(self, bot):
        self.bot = bot
        self.active_traces: Dict[str, TraceContext] = {}
        self.completed_traces: List[TraceContext] = []
        self.max_completed_traces = 100
    
    @asynccontextmanager
    async def trace_command(self, ctx: commands.Context):
        """Context manager for tracing command execution."""
        # Create trace context
        trace_id = f"{ctx.author.id}_{ctx.command.name}_{time.time()}"
        trace_ctx = TraceContext(
            command_name=ctx.command.name,
            user_id=str(ctx.author.id),
            guild_id=str(ctx.guild.id) if ctx.guild else None
        )
        
        self.active_traces[trace_id] = trace_ctx
        
        # Inject trace context into command context
        ctx.trace = trace_ctx
        
        try:
            yield trace_ctx
        finally:
            # Complete trace
            self._complete_trace(trace_id)
    
    @asynccontextmanager
    async def trace_step(self, trace_ctx: TraceContext, step_name: str, **metadata):
        """Context manager for tracing individual steps."""
        step = trace_ctx.add_step(step_name, **metadata)
        
        try:
            result = yield step
            step.complete(result=result)
        except Exception as e:
            step.complete(error=e)
            raise
    
    def _complete_trace(self, trace_id: str):
        """Mark trace as completed and store it."""
        if trace_id in self.active_traces:
            trace = self.active_traces.pop(trace_id)
            self.completed_traces.append(trace)
            
            # Keep only recent traces
            if len(self.completed_traces) > self.max_completed_traces:
                self.completed_traces.pop(0)
            
            # Log summary
            summary = trace.get_summary()
            logger.info(
                f"Command trace completed: {summary['command']} | "
                f"Duration: {summary['total_duration_ms']:.1f}ms | "
                f"Steps: {summary['steps_count']}"
            )
    
    def get_active_traces(self) -> List[Dict[str, Any]]:
        """Get all active trace summaries."""
        return [trace.get_summary() for trace in self.active_traces.values()]
    
    def get_recent_traces(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent completed trace summaries."""
        return [trace.get_summary() for trace in self.completed_traces[-limit:]]
    
    def get_command_performance(self, command_name: str) -> Dict[str, Any]:
        """Get performance statistics for a specific command."""
        command_traces = [
            trace for trace in self.completed_traces
            if trace.command_name == command_name
        ]
        
        if not command_traces:
            return {"message": f"No traces found for command: {command_name}"}
        
        durations = [trace.total_duration_ms for trace in command_traces]
        
        return {
            "command": command_name,
            "executions": len(command_traces),
            "avg_duration_ms": sum(durations) / len(durations),
            "min_duration_ms": min(durations),
            "max_duration_ms": max(durations),
            "recent_traces": [trace.get_summary() for trace in command_traces[-5:]]
        }
    
    async def trace_async_operation(
        self,
        operation_name: str,
        func,
        *args,
        trace_ctx: Optional[TraceContext] = None,
        **kwargs
    ):
        """Trace an async operation."""
        if trace_ctx:
            async with self.trace_step(trace_ctx, operation_name):
                return await func(*args, **kwargs)
        else:
            # Run without tracing
            return await func(*args, **kwargs)


# Decorator for automatic command tracing
def trace_command(func):
    """Decorator to automatically trace command execution."""
    async def wrapper(self, ctx: commands.Context, *args, **kwargs):
        if hasattr(ctx.bot, 'tracer'):
            async with ctx.bot.tracer.trace_command(ctx):
                return await func(self, ctx, *args, **kwargs)
        else:
            # No tracer available, run normally
            return await func(self, ctx, *args, **kwargs)
    
    return wrapper