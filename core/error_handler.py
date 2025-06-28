"""
Centralized error handling for Discord bot.

This module provides decorators and utilities for consistent error handling
across services and commands.
"""

import logging
from functools import wraps
from typing import Any, Callable, Dict, Optional, TypeVar

import discord
from discord.ext import commands

from .exceptions import (
    BotError,
    CooldownException,
    InsufficientBalanceError,
    PermissionError,
    RateLimitException,
    ResourceNotFoundException,
    ValidationError,
    ValidationException,
)
from .exceptions.database import DatabaseError as DatabaseException
from .exceptions.base import PermissionError as PermissionException

logger = logging.getLogger(__name__)

T = TypeVar("T")


class ErrorHandler:
    """Centralized error handler for the bot."""

    @staticmethod
    def format_error_message(error: Exception) -> str:
        """Format an error into a user-friendly message."""
        if isinstance(error, InsufficientBalanceError):
            return f"❌ {error.message}"

        elif isinstance(error, PermissionError):
            return "❌ Nie masz uprawnień do wykonania tej akcji."

        elif isinstance(error, ResourceNotFoundException):
            return f"❌ Nie znaleziono {error.details.get('resource_type', 'zasobu')}."

        elif isinstance(error, CooldownException):
            seconds = error.details.get("cooldown_seconds", 0)
            return f"⏱️ Musisz poczekać {seconds} sekund przed ponownym użyciem."

        elif isinstance(error, ValidationException):
            return f"❌ {error.message}"

        elif isinstance(error, RateLimitException):
            retry = error.details.get("retry_after")
            if retry:
                return f"⚠️ Limit zapytań przekroczony. Spróbuj ponownie za {retry} sekund."
            return "⚠️ Limit zapytań przekroczony. Spróbuj ponownie później."

        elif isinstance(error, BotError):
            return f"❌ {error.message}"

        else:
            logger.error(f"Unhandled error type: {type(error).__name__}: {error}")
            return "❌ Wystąpił nieoczekiwany błąd. Spróbuj ponownie później."

    @staticmethod
    def log_error(error: Exception, context: Optional[Dict[str, Any]] = None):
        """Log an error with context."""
        error_info = {"error_type": type(error).__name__, "error_message": str(error), "context": context or {}}

        if isinstance(error, BotError):
            error_info["error_code"] = error.error_code
            error_info["details"] = error.details

        if isinstance(error, DatabaseException) and error.original_error:
            error_info["original_error"] = str(error.original_error)

        # Log with appropriate level
        if isinstance(error, (ValidationException, PermissionException, CooldownException)):
            logger.warning(f"Handled error: {error_info}")
        else:
            logger.error(f"Error occurred: {error_info}", exc_info=True)

    @staticmethod
    async def handle_command_error(
        ctx: commands.Context, error: Exception, send_message: bool = True
    ) -> Optional[discord.Message]:
        """Handle an error in a command context."""
        # Log the error
        ErrorHandler.log_error(
            error,
            {
                "command": ctx.command.name if ctx.command else "unknown",
                "user_id": ctx.author.id,
                "guild_id": ctx.guild.id if ctx.guild else None,
                "channel_id": ctx.channel.id,
            },
        )

        # Send error message to user if requested
        if send_message:
            message = ErrorHandler.format_error_message(error)
            try:
                return await ctx.send(message)
            except discord.Forbidden:
                logger.warning(f"Cannot send error message to channel {ctx.channel.id}")
            except Exception as e:
                logger.error(f"Failed to send error message: {e}")

        return None

    @staticmethod
    async def handle_interaction_error(interaction: discord.Interaction, error: Exception):
        """Handle an error in an interaction context."""
        # Log the error
        ErrorHandler.log_error(
            error,
            {
                "interaction_type": interaction.type.name,
                "user_id": interaction.user.id,
                "guild_id": interaction.guild_id,
                "channel_id": interaction.channel_id if interaction.channel else None,
            },
        )

        # Send error message
        message = ErrorHandler.format_error_message(error)

        try:
            if interaction.response.is_done():
                await interaction.followup.send(message, ephemeral=True)
            else:
                await interaction.response.send_message(message, ephemeral=True)
        except discord.NotFound:
            logger.warning("Interaction expired before error could be sent")
        except Exception as e:
            logger.error(f"Failed to send interaction error: {e}")


def handle_errors(log_errors: bool = True, raise_on: Optional[tuple] = None, default_return: Any = None):
    """
    Decorator for handling errors in service methods.

    Args:
        log_errors: Whether to log errors
        raise_on: Tuple of exception types to re-raise
        default_return: Default value to return on error
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> T:
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                # Re-raise specific exceptions if requested
                if raise_on and isinstance(e, raise_on):
                    raise

                # Log error if requested
                if log_errors:
                    ErrorHandler.log_error(
                        e,
                        {
                            "function": func.__name__,
                            "args": str(args)[:200],  # Truncate for safety
                            "kwargs": str(kwargs)[:200],
                        },
                    )

                # Re-raise BotErrors by default
                if isinstance(e, BotError):
                    raise

                # Wrap other exceptions
                raise BotError(f"Error in {func.__name__}: {str(e)}", error_code=ErrorCodes.INTERNAL) from e

        return wrapper

    return decorator


def handle_service_errors(func: Callable[..., T]) -> Callable[..., T]:
    """Decorator specifically for service methods."""
    return handle_errors(log_errors=True)(func)


def handle_repository_errors(func: Callable[..., T]) -> Callable[..., T]:
    """Decorator specifically for repository methods."""

    @wraps(func)
    async def wrapper(*args, **kwargs) -> T:
        try:
            return await func(*args, **kwargs)
        except BotError:
            # Re-raise our exceptions
            raise
        except Exception as e:
            # Wrap database errors
            raise DatabaseException(f"Database error in {func.__name__}", original_error=e) from e

    return wrapper


class CommandErrorHandler(commands.Cog):
    """Global command error handler cog."""

    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_command_error(self, ctx: commands.Context, error: Exception):
        """Global error handler for commands."""

        # Ignore command not found
        if isinstance(error, commands.CommandNotFound):
            return

        # Handle command on cooldown
        if isinstance(error, commands.CommandOnCooldown):
            cooldown_error = BotError(
                f"Command on cooldown for {int(error.retry_after)} seconds",
                code="COOLDOWN",
                details={"retry_after": int(error.retry_after)},
                user_message=f"⏱️ Musisz poczekać {int(error.retry_after)} sekund przed ponownym użyciem.",
            )
            await ErrorHandler.handle_command_error(ctx, cooldown_error)
            return

        # Handle missing permissions
        if isinstance(error, commands.MissingPermissions):
            perm_error = PermissionError(action="command", user_message="Brak uprawnień do wykonania tej komendy.")
            await ErrorHandler.handle_command_error(ctx, perm_error)
            return

        # Handle bad arguments
        if isinstance(error, commands.BadArgument):
            validation_error = ValidationError(message=str(error), user_message=str(error))
            await ErrorHandler.handle_command_error(ctx, validation_error)
            return

        # Handle missing required argument
        if isinstance(error, commands.MissingRequiredArgument):
            validation_error = ValidationError(
                message=f"Missing required argument: {error.param.name}",
                field=error.param.name,
                user_message=f"Brakujący argument: {error.param.name}",
            )
            await ErrorHandler.handle_command_error(ctx, validation_error)
            return

        # Handle command invoke errors
        if isinstance(error, commands.CommandInvokeError):
            # Get the original error
            original_error = error.original
            await ErrorHandler.handle_command_error(ctx, original_error)
            return

        # Handle any other errors
        await ErrorHandler.handle_command_error(ctx, error)


async def setup(bot):
    """Setup the error handler cog."""
    await bot.add_cog(CommandErrorHandler(bot))
