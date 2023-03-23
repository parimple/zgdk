"""Helper functions for tests."""
from discord.ext import commands


def get_command(cog: commands.Cog, command_name: str) -> commands.Command:
    """Helper function to get a command from a cog by its name."""
    return next(cmd for cmd in cog.get_commands() if cmd.name == command_name)
