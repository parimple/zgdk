"""
Global error handler for Discord bot commands.

This cog provides centralized error handling for all commands,
with user-friendly error messages and detailed logging.
"""

import logging
import discord
from discord.ext import commands

from core.error_handler import ErrorHandler
from core.exceptions import (
    BotError,
    CooldownException,
    PermissionError,
    ValidationException,
    InsufficientFundsException,
    ResourceNotFoundException
)

logger = logging.getLogger(__name__)


class ErrorHandlerCog(commands.Cog):
    """Global error handler cog."""
    
    def __init__(self, bot):
        self.bot = bot
        self.error_handler = ErrorHandler()
    
    @commands.Cog.listener()
    async def on_command_error(self, ctx: commands.Context, error: Exception):
        """Handle command errors globally."""
        
        # Ignore command not found errors
        if isinstance(error, commands.CommandNotFound):
            return
        
        # Handle command on cooldown
        if isinstance(error, commands.CommandOnCooldown):
            cooldown_error = CooldownException(int(error.retry_after))
            await self.error_handler.handle_command_error(ctx, cooldown_error)
            return
        
        # Handle missing permissions
        if isinstance(error, commands.MissingPermissions):
            perm_error = PermissionError("Brak wymaganych uprawnień")
            await self.error_handler.handle_command_error(ctx, perm_error)
            return
        
        # Handle bot missing permissions
        if isinstance(error, commands.BotMissingPermissions):
            await ctx.send("❌ Bot nie ma wystarczających uprawnień do wykonania tej akcji.")
            return
        
        # Handle bad arguments
        if isinstance(error, commands.BadArgument):
            validation_error = ValidationException(str(error))
            await self.error_handler.handle_command_error(ctx, validation_error)
            return
        
        # Handle missing required argument
        if isinstance(error, commands.MissingRequiredArgument):
            validation_error = ValidationException(
                f"Brakujący argument: `{error.param.name}`"
            )
            await self.error_handler.handle_command_error(ctx, validation_error)
            return
        
        # Handle user input errors
        if isinstance(error, commands.UserInputError):
            validation_error = ValidationException("Nieprawidłowe użycie komendy")
            await self.error_handler.handle_command_error(ctx, validation_error)
            return
        
        # Handle check failures
        if isinstance(error, commands.CheckFailure):
            perm_error = PermissionError("Nie spełniasz wymagań do użycia tej komendy")
            await self.error_handler.handle_command_error(ctx, perm_error)
            return
        
        # Handle command invoke errors
        if isinstance(error, commands.CommandInvokeError):
            # Get the original error
            original_error = error.original
            
            # Handle our custom exceptions
            if isinstance(original_error, BotError):
                await self.error_handler.handle_command_error(ctx, original_error)
                return
            
            # Handle Discord API errors
            if isinstance(original_error, discord.Forbidden):
                await ctx.send("❌ Bot nie ma uprawnień do wykonania tej akcji.")
                return
            
            if isinstance(original_error, discord.NotFound):
                await ctx.send("❌ Nie znaleziono żądanego zasobu.")
                return
            
            # Log unexpected errors
            logger.error(
                f"Unexpected error in command {ctx.command}: {original_error}",
                exc_info=original_error
            )
            
            # Send generic error message
            await ctx.send(
                "❌ Wystąpił nieoczekiwany błąd podczas wykonywania komendy. "
                "Administratorzy zostali powiadomieni."
            )
            return
        
        # Handle any other errors
        await self.error_handler.handle_command_error(ctx, error)
    
    @commands.Cog.listener()
    async def on_application_command_error(
        self, 
        interaction: discord.Interaction, 
        error: Exception
    ):
        """Handle slash command errors."""
        
        # Convert to command error format if possible
        if isinstance(error, discord.app_commands.CommandOnCooldown):
            cooldown_error = CooldownException(int(error.retry_after))
            await self.error_handler.handle_interaction_error(interaction, cooldown_error)
            return
        
        if isinstance(error, discord.app_commands.MissingPermissions):
            perm_error = PermissionError("Brak wymaganych uprawnień")
            await self.error_handler.handle_interaction_error(interaction, perm_error)
            return
        
        # Handle our custom exceptions
        if isinstance(error, BotError):
            await self.error_handler.handle_interaction_error(interaction, error)
            return
        
        # Log unexpected errors
        logger.error(
            f"Unexpected error in slash command: {error}",
            exc_info=error
        )
        
        # Send generic error message
        try:
            if interaction.response.is_done():
                await interaction.followup.send(
                    "❌ Wystąpił nieoczekiwany błąd. Spróbuj ponownie później.",
                    ephemeral=True
                )
            else:
                await interaction.response.send_message(
                    "❌ Wystąpił nieoczekiwany błąd. Spróbuj ponownie później.",
                    ephemeral=True
                )
        except:
            pass


async def setup(bot):
    """Setup the error handler cog."""
    await bot.add_cog(ErrorHandlerCog(bot))