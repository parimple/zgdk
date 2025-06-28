"""Base test class for Discord bot command testing."""

import asyncio
import logging
from typing import Any, Dict, Optional
from unittest.mock import AsyncMock, MagicMock, patch

import discord
import pytest


logger = logging.getLogger(__name__)


class BaseCommandTest:
    """Base class for Discord bot command tests."""
    
    @pytest.fixture(autouse=True)
    async def setup_base(self):
        """Set up base test environment."""
        # Create mock bot
        self.bot = MagicMock()
        self.bot.config = {
            "premium_roles": [],
            "mute_roles": [],
            "team": {},
            "channels_voice": {"afk": 12345}
        }
        self.bot.command_prefix = [","]
        self.bot.get_cog = MagicMock()
        self.bot.cogs = {}
        self.bot.wait_for = AsyncMock()
        
        # Create mock guild
        self.guild = MagicMock(spec=discord.Guild)
        self.guild.id = 960665311701528596
        self.guild.name = "Test Guild"
        self.guild.default_role = MagicMock()
        self.guild.default_role.id = self.guild.id
        self.guild.get_member = MagicMock()
        self.guild.get_channel = MagicMock()
        self.guild.get_role = MagicMock()
        self.guild.members = []
        self.guild.roles = []
        self.guild.channels = []
        
        self.bot.guild = self.guild
        self.bot.guilds = [self.guild]
        
        # Create mock author
        self.author = MagicMock(spec=discord.Member)
        self.author.id = 123456789
        self.author.name = "TestAuthor"
        self.author.display_name = "TestAuthor"
        self.author.mention = f"<@{self.author.id}>"
        self.author.roles = []
        self.author.guild = self.guild
        self.author.guild_permissions = MagicMock()
        self.author.guild_permissions.administrator = False
        self.author.add_roles = AsyncMock()
        self.author.remove_roles = AsyncMock()
        self.author.send = AsyncMock()
        
        # Create mock context
        self.ctx = MagicMock()
        self.ctx.author = self.author
        self.ctx.guild = self.guild
        self.ctx.channel = MagicMock()
        self.ctx.channel.id = 960665315426226216
        self.ctx.channel.send = AsyncMock()
        self.ctx.send = AsyncMock()
        self.ctx.interaction = None
        self.ctx.message = MagicMock()
        self.ctx.message.content = ""
        self.ctx.message.created_at = MagicMock()
        
        # Mock database session
        self.session = AsyncMock()
        self.session.commit = AsyncMock()
        self.session.rollback = AsyncMock()
        self.session.close = AsyncMock()
        
        # Mock get_db
        async def mock_get_db():
            return self.session
            
        self.bot.get_db = MagicMock()
        self.bot.get_db.return_value.__aenter__ = AsyncMock(return_value=self.session)
        self.bot.get_db.return_value.__aexit__ = AsyncMock()
        
        # Mock service container
        self.bot.service_container = MagicMock()
        self.bot.service_container.create_unit_of_work = MagicMock()
        
        # Mock get_service
        self.bot.get_service = AsyncMock()
        
        yield
        
    def create_member(self, user_id: int, name: str):
        """Create a mock member."""
        member = MagicMock(spec=discord.Member)
        member.id = user_id
        member.name = name
        member.display_name = name
        member.mention = f"<@{user_id}>"
        member.roles = []
        member.guild = self.guild
        member.add_roles = AsyncMock()
        member.remove_roles = AsyncMock()
        member.send = AsyncMock()
        member.voice = None
        return member
    
    def create_role(self, role_id: int, name: str, color: int = 0):
        """Create a mock role."""
        role = MagicMock(spec=discord.Role)
        role.id = role_id
        role.name = name
        role.mention = f"<@&{role_id}>"
        role.color = discord.Color(color)
        role.position = 10
        role.hoist = False
        role.mentionable = True
        role.edit = AsyncMock()
        role.delete = AsyncMock()
        return role
    
    def create_context(self, command: str) -> Any:
        """Create a mock context for a command."""
        self.ctx.message.content = f",{command}"
        self.ctx.command = MagicMock()
        self.ctx.command.name = command.split()[0]
        return self.ctx
    
    def add_cog_to_bot(self, cog_name: str, cog_instance: Any):
        """Add a cog to the bot."""
        self.bot.cogs[cog_name] = cog_instance
        self.bot.get_cog = MagicMock(side_effect=lambda name: self.bot.cogs.get(name))
    
    async def run_command(self, cog: Any, command_name: str, *args, **kwargs):
        """Run a command from a cog."""
        command_method = getattr(cog, command_name)
        return await command_method(self.ctx, *args, **kwargs)