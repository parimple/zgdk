"""Owner utilities for testing and debugging commands."""

import logging
from typing import Optional, Dict, Any, List
import asyncio
import json

import discord
from discord.ext import commands
from aiohttp import web

from utils.permissions import is_zagadka_owner

logger = logging.getLogger(__name__)


class OwnerUtilsCog(commands.Cog):
    """Owner-only utilities for testing and debugging."""

    def __init__(self, bot):
        """Initialize owner utils cog."""
        self.bot = bot
        # Get configuration from bot config
        self.owner_id = bot.config.get("owner_id", 956602391891947592)
        self.test_channel_id = bot.config.get("channels", {}).get("test_channel", 1387864734002446407)
        self.guild_id = bot.config.get("guild_id", 960665311701528596)
        
        # API server for automated testing
        self.app = web.Application()
        self.runner = None
        self.site = None
        self.api_port = 8089
        self.last_responses = {}  # Store last responses for each command
        
        # Setup API routes
        self.setup_routes()

    def setup_routes(self):
        """Setup HTTP API routes."""
        self.app.router.add_post('/execute', self.api_execute_command)
        self.app.router.add_get('/status', self.api_status)
        self.app.router.add_get('/last_response', self.api_last_response)
        
    async def start_api_server(self):
        """Start the API server."""
        try:
            self.runner = web.AppRunner(self.app)
            await self.runner.setup()
            self.site = web.TCPSite(self.runner, '0.0.0.0', self.api_port)
            await self.site.start()
            logger.info(f"Owner Utils API started on http://localhost:{self.api_port}")
        except Exception as e:
            logger.error(f"Failed to start API server: {e}")
            
    async def stop_api_server(self):
        """Stop the API server."""
        if self.site:
            await self.site.stop()
        if self.runner:
            await self.runner.cleanup()

    @commands.Cog.listener()
    async def on_ready(self):
        """Event listener which is called when the bot goes online."""
        logger.info("Cog: owner_utils.py Loaded")
        await self.start_api_server()
        
    def cog_unload(self):
        """Cleanup when cog is unloaded."""
        asyncio.create_task(self.stop_api_server())

    @commands.command(name="simulate", aliases=["sim"])
    @is_zagadka_owner()
    async def simulate_command(self, ctx: commands.Context, *, command_string: str):
        """
        Simulate a command execution as the owner.
        
        Usage: !simulate <command>
        Example: !simulate profile
        Example: !simulate profile @someuser
        Example: !simulate shop
        """
        # Get the guild and channel
        guild = self.bot.get_guild(self.guild_id)
        if not guild:
            await ctx.send("❌ Cannot find the specified guild.")
            return

        channel = guild.get_channel(self.test_channel_id)
        if not channel:
            await ctx.send("❌ Cannot find the specified test channel.")
            return

        # Get owner member object
        owner_member = guild.get_member(self.owner_id)
        if not owner_member:
            await ctx.send("❌ Cannot find owner member in the guild.")
            return

        # Create a fake message from the owner
        fake_message = FakeMessage(
            content=f"{ctx.prefix}{command_string}",
            author=owner_member,
            channel=channel,
            guild=guild,
            bot=self.bot
        )

        # Create context from the fake message
        fake_ctx = await self.bot.get_context(fake_message)
        
        # Log the simulation
        logger.info(f"Simulating command '{command_string}' as {owner_member} in #{channel.name}")
        
        # Send notification that we're simulating
        embed = discord.Embed(
            title="🔧 Command Simulation",
            description=f"Simulating command: `{command_string}`\nAs: {owner_member.mention}\nIn: {channel.mention}",
            color=discord.Color.blue()
        )
        await ctx.send(embed=embed)

        try:
            # Invoke the command
            if fake_ctx.valid:
                await self.bot.invoke(fake_ctx)
                
                # Send success notification
                success_embed = discord.Embed(
                    title="✅ Simulation Complete",
                    description=f"Command `{command_string}` executed successfully.",
                    color=discord.Color.green()
                )
                await ctx.send(embed=success_embed)
            else:
                # Invalid command
                error_embed = discord.Embed(
                    title="❌ Invalid Command",
                    description=f"Command `{command_string}` is not valid or not found.",
                    color=discord.Color.red()
                )
                await ctx.send(embed=error_embed)
                
        except Exception as e:
            logger.error(f"Error simulating command '{command_string}': {e}")
            error_embed = discord.Embed(
                title="❌ Simulation Error",
                description=f"Error executing command: {str(e)}",
                color=discord.Color.red()
            )
            await ctx.send(embed=error_embed)

    @commands.command(name="test_profile", aliases=["tp"])
    @is_zagadka_owner()
    async def test_profile(self, ctx: commands.Context, member: Optional[discord.Member] = None):
        """
        Quick test of profile command as owner.
        """
        target = member.mention if member else ""
        await self.simulate_command(ctx, command_string=f"profile {target}")

    @commands.command(name="test_shop", aliases=["ts"])
    @is_zagadka_owner()
    async def test_shop(self, ctx: commands.Context):
        """
        Quick test of shop command as owner.
        """
        await self.simulate_command(ctx, command_string="shop")

    @commands.command(name="send_as_owner", aliases=["sao"])
    @is_zagadka_owner()
    async def send_as_owner(self, ctx: commands.Context, *, message: str):
        """
        Send a message in the test channel as if it was from the owner.
        """
        guild = self.bot.get_guild(self.guild_id)
        if not guild:
            await ctx.send("❌ Cannot find the specified guild.")
            return

        channel = guild.get_channel(self.test_channel_id)
        if not channel:
            await ctx.send("❌ Cannot find the specified test channel.")
            return

        # Send the message
        await channel.send(message)
        
        # Confirm
        embed = discord.Embed(
            title="✅ Message Sent",
            description=f"Sent message in {channel.mention}:\n```{message}```",
            color=discord.Color.green()
        )
        await ctx.send(embed=embed)
    
    async def api_status(self, request):
        """API endpoint to check bot status."""
        return web.json_response({
            "status": "online",
            "bot_name": self.bot.user.name if self.bot.user else "Not connected",
            "guild_id": self.guild_id,
            "test_channel_id": self.test_channel_id,
            "api_port": self.api_port
        })
        
    async def api_last_response(self, request):
        """API endpoint to get last command response."""
        command = request.query.get('command', '')
        if command in self.last_responses:
            return web.json_response(self.last_responses[command])
        else:
            return web.json_response({"error": "No response found for command"}, status=404)
            
    async def api_execute_command(self, request):
        """
        API endpoint to execute a command.
        
        Expected JSON payload:
        {
            "command": "profile",
            "args": "@user"  // optional
        }
        """
        try:
            data = await request.json()
            command = data.get("command", "")
            args = data.get("args", "")
            
            if not command:
                return web.json_response({"error": "Command is required"}, status=400)
                
            # Build full command string
            command_string = command
            if args:
                command_string += f" {args}"
                
            # Get guild and channel
            guild = self.bot.get_guild(self.guild_id)
            if not guild:
                return web.json_response({"error": "Guild not found"}, status=500)
                
            # Get channel from request or use default
            channel_id = data.get("channel_id", self.test_channel_id)
            if isinstance(channel_id, str):
                channel_id = int(channel_id)
            
            channel = guild.get_channel(channel_id)
            if not channel:
                return web.json_response({"error": "Channel not found"}, status=500)
                
            # Get author from request or use owner
            author_id = data.get("author_id", self.owner_id)
            if isinstance(author_id, str):
                author_id = int(author_id)
                
            author_member = guild.get_member(author_id)
            if not author_member:
                return web.json_response({"error": f"Author {author_id} not found in guild"}, status=500)
                
            # Prepare to capture responses
            responses = []
            
            # Create a wrapper channel to capture sends
            class ChannelWrapper:
                def __init__(self, channel):
                    self._channel = channel
                    self.id = channel.id
                    self.name = channel.name
                    self.guild = channel.guild
                    self._state = channel._state
                    self.type = channel.type
                    
                async def send(self, content=None, **kwargs):
                    """Capture bot responses."""
                    response = {"content": content}
                    
                    if "embed" in kwargs:
                        embed = kwargs["embed"]
                        response["embed"] = {
                            "title": embed.title,
                            "description": embed.description,
                            "color": embed.color.value if embed.color else None,
                            "fields": [{"name": f.name, "value": f.value, "inline": f.inline} for f in embed.fields]
                        }
                        
                    if "embeds" in kwargs:
                        response["embeds"] = []
                        for embed in kwargs["embeds"]:
                            response["embeds"].append({
                                "title": embed.title,
                                "description": embed.description,
                                "color": embed.color.value if embed.color else None,
                                "fields": [{"name": f.name, "value": f.value, "inline": f.inline} for f in embed.fields]
                            })
                            
                    responses.append(response)
                    return fake_message
                    
                def __getattr__(self, name):
                    return getattr(self._channel, name)
                    
            # Use wrapper channel
            wrapped_channel = ChannelWrapper(channel)
            
            # Create fake message with wrapped channel
            fake_message = FakeMessage(
                content=f"{self.bot.command_prefix[0]}{command_string}",
                author=author_member,
                channel=wrapped_channel,
                guild=guild,
                bot=self.bot
            )
            
            try:
                # Get context and invoke
                fake_ctx = await self.bot.get_context(fake_message)
                
                if not fake_ctx.valid:
                    return web.json_response({
                        "success": False,
                        "error": f"Invalid command: {command}"
                    })
                    
                # Execute command
                await self.bot.invoke(fake_ctx)
                
                # Store response
                self.last_responses[command] = {
                    "success": True,
                    "command": command_string,
                    "responses": responses,
                    "timestamp": discord.utils.utcnow().isoformat()
                }
                
                return web.json_response({
                    "success": True,
                    "command": command_string,
                    "responses": responses
                })
                
            except Exception as e:
                logger.error(f"Error executing command '{command_string}': {e}")
                return web.json_response({
                    "success": False,
                    "error": str(e)
                }, status=500)
                
                
        except Exception as e:
            logger.error(f"API error: {e}")
            return web.json_response({"error": str(e)}, status=500)


class FakeMessage:
    """Fake message object for simulating commands."""
    
    def __init__(self, content: str, author: discord.Member, channel: discord.TextChannel, 
                 guild: discord.Guild, bot: commands.Bot):
        self.content = content
        self.author = author
        self.channel = channel
        self.guild = guild
        self.bot = bot
        self._state = bot._connection
        
        # Set required attributes
        self.id = 0  # Fake ID
        self.webhook_id = None
        self.reactions = []
        self.attachments = []
        self.embeds = []
        self.edited_at = None
        self.type = discord.MessageType.default
        self.pinned = False
        self.mention_everyone = False
        self.tts = False
        self.mentions = []
        self.channel_mentions = []
        self.role_mentions = []
        self.flags = discord.MessageFlags._from_value(0)
        self.stickers = []
        self.reference = None
        self.interaction = None
        self.created_at = discord.utils.utcnow()
        
    @property
    def jump_url(self):
        """Return a fake jump URL."""
        return f"https://discord.com/channels/{self.guild.id}/{self.channel.id}/{self.id}"
    
    @property
    def clean_content(self):
        """Return clean content."""
        return self.content
    
    async def delete(self, *, delay: float = None):
        """Fake delete method."""
        pass
    
    async def reply(self, content: str = None, **kwargs):
        """Send a reply in the channel."""
        if content:
            await self.channel.send(content, **kwargs)
        elif 'embed' in kwargs:
            await self.channel.send(embed=kwargs['embed'])
        elif 'embeds' in kwargs:
            await self.channel.send(embeds=kwargs['embeds'])
    
    async def add_reaction(self, emoji):
        """Fake add reaction method."""
        pass


async def setup(bot: commands.Bot):
    """Setup function to add cog to bot."""
    await bot.add_cog(OwnerUtilsCog(bot))