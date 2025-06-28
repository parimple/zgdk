"""
Comprehensive error logging system with full traceback and context.
"""

import datetime
import logging
import os
import traceback
from pathlib import Path
from typing import Any, Dict, Optional


class DetailedErrorLogger:
    """Logger for detailed error information with context."""

    def __init__(self, log_dir: str = "logs"):
        """Initialize the error logger."""
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(exist_ok=True)

        # Create detailed error log file
        self.error_log_file = self.log_dir / "detailed_errors.log"

        # Setup logger
        self.logger = logging.getLogger("detailed_errors")
        self.logger.setLevel(logging.ERROR)

        # Remove existing handlers to avoid duplicates
        for handler in self.logger.handlers[:]:
            self.logger.removeHandler(handler)

        # File handler for detailed errors
        file_handler = logging.FileHandler(self.error_log_file, encoding="utf-8")
        file_handler.setLevel(logging.ERROR)

        # Detailed formatter
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
        )
        file_handler.setFormatter(formatter)

        self.logger.addHandler(file_handler)

    def log_error(
        self,
        error: Exception,
        context: Optional[Dict[str, Any]] = None,
        user_id: Optional[int] = None,
        guild_id: Optional[int] = None,
        command_name: Optional[str] = None,
        additional_info: Optional[str] = None,
    ):
        """Log a detailed error with full context."""

        # Get full traceback
        tb_str = "".join(traceback.format_exception(type(error), error, error.__traceback__))

        # Build error message
        error_msg = [
            f"=== ERROR DETAILS ===",
            f"Error Type: {type(error).__name__}",
            f"Error Message: {str(error)}",
            f"Timestamp: {datetime.datetime.now().isoformat()}",
        ]

        if user_id:
            error_msg.append(f"User ID: {user_id}")
        if guild_id:
            error_msg.append(f"Guild ID: {guild_id}")
        if command_name:
            error_msg.append(f"Command: {command_name}")
        if additional_info:
            error_msg.append(f"Additional Info: {additional_info}")

        if context:
            error_msg.append("Context:")
            for key, value in context.items():
                error_msg.append(f"  {key}: {value}")

        error_msg.extend(["Full Traceback:", tb_str, "=" * 50, ""])  # Empty line for separation

        # Log the complete error
        self.logger.error("\n".join(error_msg))

    def log_command_error(
        self, error: Exception, ctx: Any, additional_context: Optional[Dict[str, Any]] = None  # commands.Context
    ):
        """Log a command error with Discord context."""
        context = {
            "command": ctx.command.name if ctx.command else "Unknown",
            "channel_id": ctx.channel.id if ctx.channel else None,
            "channel_name": getattr(ctx.channel, "name", "Unknown"),
            "message_content": ctx.message.content if hasattr(ctx, "message") else None,
            "message_id": ctx.message.id if hasattr(ctx, "message") else None,
        }

        if additional_context:
            context.update(additional_context)

        self.log_error(
            error=error,
            context=context,
            user_id=ctx.author.id if ctx.author else None,
            guild_id=ctx.guild.id if ctx.guild else None,
            command_name=ctx.command.name if ctx.command else None,
        )


# Global instance
error_logger = DetailedErrorLogger()
