"""Unit tests for voice commands."""

import asyncio
import logging
from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import discord
import pytest

from tests.base.base_command_test import BaseCommandTest
from tests.config import TEST_USER_ID

logger = logging.getLogger(__name__)


class TestVoicePermissionCommands(BaseCommandTest):
    """Test voice permission commands."""

    @pytest.fixture(autouse=True)
    async def setup_voice_channel(self):
        """Set up a mock voice channel for tests."""
        self.voice_channel = MagicMock(spec=discord.VoiceChannel)
        self.voice_channel.id = 12345
        self.voice_channel.name = "Test Voice"
        self.voice_channel.guild = self.guild
        self.voice_channel.overwrites = {}
        
        # Mock voice state
        self.voice_state = MagicMock()
        self.voice_state.channel = self.voice_channel
        self.author.voice = self.voice_state
        
        # Mock channel methods
        async def set_permissions(target, *, overwrite=None, **kwargs):
            self.voice_channel.overwrites[target] = overwrite
            
        self.voice_channel.set_permissions = AsyncMock(side_effect=set_permissions)
        self.voice_channel.overwrites_for = lambda t: self.voice_channel.overwrites.get(t, discord.PermissionOverwrite())
        
        yield
        
        self.author.voice = None

    @pytest.mark.asyncio
    async def test_speak_command(self):
        """Test speak permission command."""
        # Give user mod permissions
        mod_perms = discord.PermissionOverwrite(manage_messages=True)
        self.voice_channel.overwrites[self.author] = mod_perms
        
        # Mock premium service
        with patch.object(self.bot, 'get_service') as mock_get_service:
            premium_service = AsyncMock()
            premium_service.check_command_access.return_value = (True, "Access granted")
            mock_get_service.return_value = premium_service
            
            # Test toggling speak permission
            ctx = self.create_context("speak @everyone")
            cog = self.bot.get_cog('VoiceCog')
            await cog.speak(ctx)
            
            # Check permission was set
            everyone_perms = self.voice_channel.overwrites.get(self.guild.default_role)
            assert everyone_perms is not None
            # Since it's a toggle and default is None, should be False
            assert everyone_perms.speak is False

    @pytest.mark.asyncio
    async def test_view_command(self):
        """Test view permission command."""
        # Give user mod permissions
        mod_perms = discord.PermissionOverwrite(manage_messages=True)
        self.voice_channel.overwrites[self.author] = mod_perms
        
        # Test setting view permission
        test_member = self.create_member(TEST_USER_ID, "TestUser")
        ctx = self.create_context(f"view <@{TEST_USER_ID}> +")
        ctx.author = self.author
        
        cog = self.bot.get_cog('VoiceCog')
        await cog.view(ctx, test_member, "+")
        
        # Check permission was set
        member_perms = self.voice_channel.overwrites.get(test_member)
        assert member_perms is not None
        assert member_perms.view_channel is True

    @pytest.mark.asyncio
    async def test_connect_command(self):
        """Test connect permission command."""
        # Give user owner permissions
        owner_perms = discord.PermissionOverwrite(priority_speaker=True)
        self.voice_channel.overwrites[self.author] = owner_perms
        
        # Test removing connect permission
        test_member = self.create_member(TEST_USER_ID, "TestUser")
        ctx = self.create_context(f"connect <@{TEST_USER_ID}> -")
        ctx.author = self.author
        
        cog = self.bot.get_cog('VoiceCog')
        await cog.connect(ctx, test_member, "-")
        
        # Check permission was set
        member_perms = self.voice_channel.overwrites.get(test_member)
        assert member_perms is not None
        assert member_perms.connect is False

    @pytest.mark.asyncio
    async def test_text_command(self):
        """Test text permission command."""
        # Give user mod permissions
        mod_perms = discord.PermissionOverwrite(manage_messages=True)
        self.voice_channel.overwrites[self.author] = mod_perms
        
        # Test setting text permission
        ctx = self.create_context("text @everyone +")
        ctx.author = self.author
        
        cog = self.bot.get_cog('VoiceCog')
        await cog.text(ctx, self.guild.default_role, "+")
        
        # Check permission was set
        everyone_perms = self.voice_channel.overwrites.get(self.guild.default_role)
        assert everyone_perms is not None
        assert everyone_perms.send_messages is True

    @pytest.mark.asyncio
    async def test_live_command_with_premium(self):
        """Test live permission command with premium access."""
        # Give user mod permissions
        mod_perms = discord.PermissionOverwrite(manage_messages=True)
        self.voice_channel.overwrites[self.author] = mod_perms
        
        # Mock premium service
        with patch.object(self.bot, 'get_service') as mock_get_service:
            premium_service = AsyncMock()
            premium_service.check_command_access.return_value = (True, "Access granted")
            mock_get_service.return_value = premium_service
            
            # Test setting live permission
            test_member = self.create_member(TEST_USER_ID, "TestUser")
            ctx = self.create_context(f"live <@{TEST_USER_ID}> +")
            ctx.author = self.author
            
            cog = self.bot.get_cog('VoiceCog')
            await cog.live(ctx, test_member, "+")
            
            # Check permission was set
            member_perms = self.voice_channel.overwrites.get(test_member)
            assert member_perms is not None
            assert member_perms.stream is True

    @pytest.mark.asyncio
    async def test_mod_command(self):
        """Test mod permission command."""
        # Give user owner permissions
        owner_perms = discord.PermissionOverwrite(priority_speaker=True)
        self.voice_channel.overwrites[self.author] = owner_perms
        
        # Add premium role
        premium_role = MagicMock()
        premium_role.name = "MVP"
        self.author.roles.append(premium_role)
        self.bot.config["premium_roles"] = [{"name": "MVP", "moderator_count": 3}]
        
        # Test adding mod
        test_member = self.create_member(TEST_USER_ID, "TestMod")
        ctx = self.create_context(f"mod <@{TEST_USER_ID}> +")
        ctx.author = self.author
        
        cog = self.bot.get_cog('VoiceCog')
        await cog.mod(ctx, test_member, "+")
        
        # Check permission was set
        member_perms = self.voice_channel.overwrites.get(test_member)
        assert member_perms is not None
        assert member_perms.manage_messages is True


class TestVoiceChannelCommands(BaseCommandTest):
    """Test voice channel management commands."""

    @pytest.mark.asyncio
    async def test_join_command(self):
        """Test join command (admin only)."""
        # Create voice channel for author
        voice_channel = MagicMock(spec=discord.VoiceChannel)
        voice_channel.id = 12345
        voice_channel.name = "Test Voice"
        
        voice_state = MagicMock()
        voice_state.channel = voice_channel
        self.author.voice = voice_state
        
        # Mock bot's voice client
        voice_client = MagicMock()
        voice_client.move_to = AsyncMock()
        self.guild.voice_client = None
        
        # Give admin permissions
        self.author.guild_permissions.administrator = True
        
        ctx = self.create_context("join")
        ctx.author = self.author
        
        # Mock connect method
        async def mock_connect():
            self.guild.voice_client = voice_client
            return voice_client
            
        voice_channel.connect = AsyncMock(side_effect=mock_connect)
        
        cog = self.bot.get_cog('VoiceCog')
        await cog.join(ctx)
        
        # Check bot connected
        voice_channel.connect.assert_called_once()

    @pytest.mark.asyncio
    async def test_limit_command(self):
        """Test limit command."""
        # Set up voice channel
        voice_channel = MagicMock(spec=discord.VoiceChannel)
        voice_channel.id = 12345
        voice_channel.name = "Test Voice"
        voice_channel.edit = AsyncMock()
        
        voice_state = MagicMock()
        voice_state.channel = voice_channel
        self.author.voice = voice_state
        
        # Give mod permissions
        mod_perms = discord.PermissionOverwrite(manage_messages=True)
        voice_channel.overwrites_for = lambda t: mod_perms if t == self.author else discord.PermissionOverwrite()
        
        # Mock premium check
        with patch.object(self.bot.cogs['VoiceCog'].premium_checker, 'check_voice_access', return_value=(True, None)):
            ctx = self.create_context("limit 10")
            ctx.author = self.author
            
            cog = self.bot.get_cog('VoiceCog')
            await cog.limit(ctx, 10)
            
            # Check limit was set
            voice_channel.edit.assert_called_once_with(user_limit=10)

    @pytest.mark.asyncio
    async def test_voicechat_command(self):
        """Test voicechat command."""
        # Set up voice channel
        voice_channel = MagicMock(spec=discord.VoiceChannel)
        voice_channel.id = 12345
        voice_channel.name = "Test Voice"
        voice_channel.mention = f"<#{voice_channel.id}>"
        voice_channel.overwrites = {}
        
        voice_state = MagicMock()
        voice_state.channel = voice_channel
        self.author.voice = voice_state
        
        # Mock premium check
        with patch.object(self.bot.cogs['VoiceCog'].premium_checker, 'check_voice_access', return_value=(True, None)):
            ctx = self.create_context("voicechat")
            ctx.author = self.author
            
            cog = self.bot.get_cog('VoiceCog')
            await cog.voicechat(ctx)
            
            # Check response sent
            ctx.send.assert_called()
            if hasattr(ctx.send.call_args[1], 'embed'):
                embed = ctx.send.call_args[1]['embed']
                assert voice_channel.name in embed.title


class TestVoiceAdminCommands(BaseCommandTest):
    """Test voice admin commands."""

    @pytest.fixture(autouse=True)
    async def setup_voice_owner(self):
        """Set up voice channel with owner permissions."""
        self.voice_channel = MagicMock(spec=discord.VoiceChannel)
        self.voice_channel.id = 12345
        self.voice_channel.name = "Test Voice"
        self.voice_channel.guild = self.guild
        self.voice_channel.overwrites = {}
        
        # Give author owner permissions
        owner_perms = discord.PermissionOverwrite(priority_speaker=True)
        self.voice_channel.overwrites[self.author] = owner_perms
        
        # Mock voice state
        self.voice_state = MagicMock()
        self.voice_state.channel = self.voice_channel
        self.author.voice = self.voice_state
        
        # Mock channel methods
        self.voice_channel.set_permissions = AsyncMock()
        self.voice_channel.overwrites_for = lambda t: self.voice_channel.overwrites.get(t, discord.PermissionOverwrite())
        
        yield
        
        self.author.voice = None

    @pytest.mark.asyncio
    async def test_autokick_command(self):
        """Test autokick command."""
        # Mock premium tier check
        with patch.object(self.bot.cogs['VoiceCog'].premium_checker, 'check_premium_tier', return_value=(True, None)):
            # Test listing empty autokick
            ctx = self.create_context("autokick")
            ctx.author = self.author
            
            cog = self.bot.get_cog('VoiceCog')
            await cog.autokick(ctx)
            
            # Check embed sent
            ctx.send.assert_called()
            embed_call = ctx.send.call_args[1]
            if 'embed' in embed_call:
                embed = embed_call['embed']
                assert "Lista autokick" in embed.title

    @pytest.mark.asyncio
    async def test_reset_command(self):
        """Test reset command."""
        # Mock premium access check
        with patch.object(self.bot.cogs['VoiceCog'].premium_checker, 'check_voice_access', return_value=(True, None)):
            # Test reset all permissions
            ctx = self.create_context("reset")
            ctx.author = self.author
            
            cog = self.bot.get_cog('VoiceCog')
            await cog.reset(ctx)
            
            # Check response sent
            ctx.send.assert_called()

    @pytest.mark.asyncio
    async def test_debug_access_command(self):
        """Test debug_access command."""
        # Test checking own access
        ctx = self.create_context("debug_access")
        ctx.author = self.author
        
        # Mock debug method
        with patch.object(self.bot.cogs['VoiceCog'].premium_checker, 'debug_alternative_access', return_value="Debug info"):
            cog = self.bot.get_cog('VoiceCog')
            await cog.debug_access(ctx)
            
            # Check response sent
            ctx.send.assert_called()
            assert "Debug info" in ctx.send.call_args[0][0]

    @pytest.mark.asyncio
    async def test_voice_stats_command(self):
        """Test voice_stats command."""
        # Give admin permissions
        self.author.guild_permissions.administrator = True
        
        # Mock voice event handler with metrics
        voice_event = MagicMock()
        voice_event.metrics = {
            "voice_state_updates": 100,
            "voice_joins": 30,
            "voice_switches": 20,
            "voice_leaves": 50,
            "channels_created": 10,
            "channels_deleted": 5,
            "active_channels": set([12345, 67890]),
            "events_processed": 100,
            "errors": 2,
            "avg_processing_time": 15.5,
            "cache_hits": 80,
            "cache_misses": 20
        }
        
        # Add to bot cogs
        self.bot.cogs['VoiceEvent'] = voice_event
        
        ctx = self.create_context("voice_stats")
        ctx.author = self.author
        
        cog = self.bot.get_cog('VoiceCog')
        await cog.voice_stats(ctx)
        
        # Check embed sent
        ctx.send.assert_called()
        embed_call = ctx.send.call_args[1]
        if 'embed' in embed_call:
            embed = embed_call['embed']
            assert "Voice System Statistics" in embed.title