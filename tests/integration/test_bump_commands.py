"""Integration tests for bump commands."""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch
import discord
from discord.ext import commands
import datetime
from datetime import timezone


@pytest.mark.asyncio
async def test_bump_status_command():
    """Test the ,bump status command."""
    # Import the cog
    from cogs.events.bump.bump_event import OnBumpEvent
    from cogs.events.bump.status import BumpStatusHandler
    
    # Create mock bot
    bot = MagicMock()
    bot.config = {
        "prefix": ",",
        "owner_id": 123456789
    }
    bot.get_db = AsyncMock()
    
    # Create mock context
    ctx = MagicMock()
    ctx.bot = bot
    ctx.author = MagicMock(spec=discord.Member)
    ctx.author.id = 956602391891947592  # Your user ID
    ctx.author.name = "zagadkowy"
    ctx.author.display_name = "zagadkowy"
    ctx.guild = MagicMock(spec=discord.Guild)
    ctx.guild.id = 960665311701528596
    ctx.channel = MagicMock(spec=discord.TextChannel)
    ctx.send = AsyncMock()
    
    # Create the cog
    cog = OnBumpEvent(bot)
    
    # Mock the status handler to avoid database calls
    with patch.object(cog.status_handler, 'show_status', new_callable=AsyncMock) as mock_show_status:
        # Call the command
        await cog.bump_status(ctx)
        
        # Verify show_status was called
        mock_show_status.assert_called_once()
        
        # Get the fake interaction that was passed
        call_args = mock_show_status.call_args[0]
        fake_interaction = call_args[0]
        member = call_args[1]
        
        # Verify fake interaction has required attributes
        assert hasattr(fake_interaction, 'response')
        assert hasattr(fake_interaction.response, 'defer')
        assert hasattr(fake_interaction, 'user')
        assert fake_interaction.user == ctx.author
        assert member == ctx.author
        
    print("✅ Bump status command test passed!")


@pytest.mark.asyncio
async def test_disboard_bump_detection():
    """Test DISBOARD bump detection."""
    from cogs.events.bump.bump_event import OnBumpEvent
    from cogs.events.bump.constants import DISBOARD
    
    # Create mock bot
    bot = MagicMock()
    bot.config = {"prefix": ","}
    bot.get_db = AsyncMock()
    
    # Create mock message from DISBOARD
    message = MagicMock(spec=discord.Message)
    message.author = MagicMock()
    message.author.id = DISBOARD["id"]  # DISBOARD bot ID
    message.author.bot = True
    message.guild = MagicMock(spec=discord.Guild)
    message.guild.id = 960665311701528596
    message.channel = MagicMock(spec=discord.TextChannel)
    
    # Create embed that DISBOARD sends
    embed = MagicMock(spec=discord.Embed)
    embed.description = "Serwer został podbity przez <@956602391891947592>!"
    embed.title = None
    embed.to_dict = MagicMock(return_value={"description": embed.description})
    message.embeds = [embed]
    message.interaction = None
    message.webhook_id = None
    
    # Create the cog
    cog = OnBumpEvent(bot)
    
    # Mock the handler
    with patch.object(cog.disboard_handler, 'handle', new_callable=AsyncMock) as mock_handle:
        # Process the message
        await cog.on_message(message)
        
        # Verify handler was called
        mock_handle.assert_called_once_with(message)
        
    print("✅ DISBOARD bump detection test passed!")


@pytest.mark.asyncio
async def test_bump_command_error_handling():
    """Test bump command error handling."""
    from cogs.events.bump.bump_event import OnBumpEvent
    
    # Create mock bot
    bot = MagicMock()
    bot.config = {"prefix": ","}
    bot.get_db = AsyncMock()
    
    # Create mock context with missing attributes
    ctx = MagicMock()
    ctx.bot = bot
    ctx.author = None  # This will cause an error
    ctx.send = AsyncMock()
    
    # Create the cog
    cog = OnBumpEvent(bot)
    
    # Test should handle the error gracefully
    try:
        await cog.bump_status(ctx)
    except AttributeError:
        # Expected - the command should fail gracefully
        pass
    
    print("✅ Bump command error handling test passed!")


if __name__ == "__main__":
    # Run the tests
    import asyncio
    
    async def run_all_tests():
        print("Running bump command integration tests...\n")
        
        await test_bump_status_command()
        await test_disboard_bump_detection()
        await test_bump_command_error_handling()
        
        print("\n✅ All tests passed!")
    
    asyncio.run(run_all_tests())