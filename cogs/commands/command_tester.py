"""Command testing functionality for automated bot testing."""

import asyncio
import logging
from typing import Any, Dict

import discord
from aiohttp import web
from discord.ext import commands

from utils.permissions import is_zagadka_owner

logger = logging.getLogger(__name__)


class CommandTesterCog(commands.Cog):
    """Automated command testing functionality."""

    def __init__(self, bot):
        """Initialize command tester cog."""
        self.bot = bot
        # Get configuration from bot config
        self.owner_id = bot.config.get("owner_id", 956602391891947592)
        self.test_channel_id = bot.config.get("channels", {}).get("test_channel", 1387864734002446407)
        self.guild_id = bot.config.get("guild_id", 960665311701528596)
        # Webhook no longer needed with internal simulation
        # self.webhook_url = os.getenv("TEST_WEBHOOK_URL", "")

        # API server for automated testing
        self.app = web.Application()
        self.runner = None
        self.site = None
        self.api_port = 8090
        self.command_responses = {}

        # Setup API routes
        self.setup_routes()

    def setup_routes(self):
        """Setup HTTP API routes."""
        self.app.router.add_post("/execute", self.api_execute_command)
        self.app.router.add_get("/status", self.api_status)
        self.app.router.add_get("/responses", self.api_get_responses)
        self.app.router.add_get("/test", self.api_test)

    async def start_api_server(self):
        """Start the API server."""
        try:
            self.runner = web.AppRunner(self.app)
            await self.runner.setup()
            self.site = web.TCPSite(self.runner, "0.0.0.0", self.api_port)
            await self.site.start()
            logger.info(f"Command Tester API started on http://0.0.0.0:{self.api_port}")
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
        logger.info("Cog: command_tester.py Loaded")
        await self.start_api_server()

    def cog_unload(self):
        """Cleanup when cog is unloaded."""
        asyncio.create_task(self.stop_api_server())

    async def api_status(self, request):
        """API endpoint to check bot status."""
        return web.json_response(
            {
                "status": "online",
                "bot_name": self.bot.user.name if self.bot.user else "Not connected",
                "guild_id": self.guild_id,
                "test_channel_id": self.test_channel_id,
                "api_port": self.api_port,
                "commands_available": len(self.bot.commands),
            }
        )

    async def api_get_responses(self, request):
        """API endpoint to get command responses."""
        command_id = request.query.get("id", "")
        if command_id in self.command_responses:
            return web.json_response(self.command_responses[command_id])
        else:
            return web.json_response({"error": "Response not found"}, status=404)

    async def api_test(self, request):
        """API endpoint for quick testing."""
        try:
            # Test simple command
            result = await self._execute_command("help")
            return web.json_response(
                {"success": True, "test": "Command Tester API is working!", "sample_result": result}
            )
        except Exception as e:
            return web.json_response({"error": str(e)}, status=500)

    async def api_execute_command(self, request):
        """
        API endpoint to execute a command.

        Expected JSON payload:
        {
            "command": "profile",
            "args": "@user",  // optional
            "send_to_channel": true  // optional, default false
        }
        """
        try:
            data = await request.json()
            command = data.get("command", "")
            args = data.get("args", "")
            send_to_channel = data.get("send_to_channel", False)

            if not command:
                return web.json_response({"error": "Command is required"}, status=400)

            # Build full command string
            command_string = command
            if args:
                command_string += f" {args}"

            # Execute command in test channel
            result = await self._execute_command(command_string, send_to_channel=send_to_channel)

            # Store result
            command_id = f"{command}_{asyncio.get_event_loop().time()}"
            self.command_responses[command_id] = result

            return web.json_response({"success": result.get("success", False), "command_id": command_id, **result})

        except Exception as e:
            logger.error(f"API error: {e}")
            return web.json_response({"error": str(e)}, status=500)

    async def _execute_command(self, command_string: str, send_to_channel: bool = False) -> Dict[str, Any]:
        """Execute a command and capture responses."""
        try:
            # Get guild and channel
            guild = self.bot.get_guild(self.guild_id)
            if not guild:
                return {"success": False, "error": "Guild not found"}

            channel = guild.get_channel(self.test_channel_id)
            if not channel:
                return {"success": False, "error": "Test channel not found"}

            owner_member = guild.get_member(self.owner_id)
            if not owner_member:
                return {"success": False, "error": "Owner not found in guild"}

            # Use internal simulation instead of webhook
            prefix = self.bot.config.get("prefix", ",")

            # Setup response collection
            responses = []

            # Create a custom channel wrapper that captures sends
            class ChannelWrapper:
                def __init__(self, channel, send_to_channel=False):
                    self._channel = channel
                    self._send_to_channel = send_to_channel

                async def send(self, content=None, **kwargs):
                    """Capture bot responses and optionally send to channel."""
                    response_data = {"content": content, "embeds": [], "components": []}

                    if "embed" in kwargs:
                        embed = kwargs["embed"]
                        embed_data = {
                            "title": embed.title,
                            "description": embed.description,
                            "color": embed.color.value if embed.color else None,
                            "fields": [{"name": f.name, "value": f.value, "inline": f.inline} for f in embed.fields],
                        }
                        response_data["embeds"].append(embed_data)

                    if "embeds" in kwargs:
                        for embed in kwargs["embeds"]:
                            embed_data = {
                                "title": embed.title,
                                "description": embed.description,
                                "color": embed.color.value if embed.color else None,
                                "fields": [
                                    {"name": f.name, "value": f.value, "inline": f.inline} for f in embed.fields
                                ],
                            }
                            response_data["embeds"].append(embed_data)

                    # Capture view/components if present
                    if "view" in kwargs and kwargs["view"]:
                        view = kwargs["view"]
                        components_data = []
                        for item in view.children:
                            if hasattr(item, "label"):
                                component = {
                                    "type": "button",
                                    "label": item.label,
                                    "style": str(item.style),
                                    "emoji": str(item.emoji) if item.emoji else None,
                                    "url": item.url if hasattr(item, "url") else None,
                                    "custom_id": item.custom_id if hasattr(item, "custom_id") else None,
                                    "disabled": item.disabled if hasattr(item, "disabled") else False,
                                }
                                components_data.append(component)
                        if components_data:
                            response_data["components"] = components_data

                    responses.append(response_data)
                    logger.info(f"Captured response: {content[:50] if content else 'embed'}")

                    # Actually send to the channel if enabled
                    if getattr(self, "_send_to_channel", True):
                        actual_message = await self._channel.send(content=content, **kwargs)
                        return actual_message
                    else:
                        # Return a fake message
                        return FakeMessage(
                            content=content or "",
                            author=self._channel.guild.me,
                            channel=self._channel,
                            guild=self._channel.guild,
                            bot=self._channel.guild._state._get_client(),
                        )

                # Delegate all other attributes to the real channel
                def __getattr__(self, name):
                    return getattr(self._channel, name)

            # Wrap the channel
            wrapped_channel = ChannelWrapper(channel, send_to_channel=send_to_channel)

            # Create fake message with wrapped channel
            fake_message = FakeMessage(
                content=f"{prefix}{command_string}",
                author=owner_member,
                channel=wrapped_channel,
                guild=guild,
                bot=self.bot,
            )

            try:
                # Get context and invoke command
                ctx = await self.bot.get_context(fake_message)

                if ctx.valid:
                    # Also wrap ctx.send to capture responses
                    original_ctx_send = ctx.send
                    ctx.send = wrapped_channel.send

                    logger.info(f"Invoking command: {ctx.command}")
                    await self.bot.invoke(ctx)
                    logger.info(f"Command completed, captured {len(responses)} responses")

                    # Restore original send
                    ctx.send = original_ctx_send
                else:
                    logger.warning(f"Invalid command context for: {command_string}")
                    return {"success": False, "error": "Invalid command"}

            except Exception as e:
                logger.error(f"Error during command execution: {e}")
                return {"success": False, "error": str(e)}

            return {"success": True, "command": command_string, "responses": responses}

        except Exception as e:
            logger.error(f"Error executing command '{command_string}': {e}")
            return {"success": False, "command": command_string, "error": str(e)}

    @commands.command(name="test_api")
    @is_zagadka_owner()
    async def test_api(self, ctx: commands.Context):
        """Test if the API is running."""
        if self.site and self.site.name:
            await ctx.send(f"✅ Command Tester API is running on port {self.api_port}")
        else:
            await ctx.send("❌ Command Tester API is not running")


class FakeMessage:
    """Fake message object for simulating commands."""

    def __init__(
        self,
        content: str,
        author: discord.Member,
        channel: discord.TextChannel,
        guild: discord.Guild,
        bot: commands.Bot,
    ):
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

    async def reply(self, content: str = None, **kwargs):
        """Send a reply in the channel."""
        if content:
            await self.channel.send(content, **kwargs)
        elif "embed" in kwargs:
            await self.channel.send(embed=kwargs["embed"])
        elif "embeds" in kwargs:
            await self.channel.send(embeds=kwargs["embeds"])

    async def add_reaction(self, emoji):
        """Fake add reaction method."""


async def setup(bot: commands.Bot):
    """Setup function to add cog to bot."""
    await bot.add_cog(CommandTesterCog(bot))
