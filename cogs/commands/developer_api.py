"""Developer API for automated command testing."""

import asyncio
import logging
from typing import Any, Dict

import discord
from aiohttp import web
from discord.ext import commands, tasks

from utils.permissions import is_zagadka_owner

logger = logging.getLogger(__name__)


class DeveloperAPICog(commands.Cog):
    """Developer API for automated testing of bot commands."""

    def __init__(self, bot):
        """Initialize developer API cog."""
        self.bot = bot
        self.owner_id = 956602391891947592
        self.test_channel_id = 1387864734002446407
        self.guild_id = 960665311701528596

        # Web server for API
        self.app = web.Application()
        self.runner = None
        self.site = None
        self.port = 8089  # API port

        # Command queue
        self.command_queue = asyncio.Queue()

        # Setup routes
        self.setup_routes()

    def setup_routes(self):
        """Setup HTTP routes for the API."""
        self.app.router.add_post("/execute", self.handle_execute_command)
        self.app.router.add_get("/status", self.handle_status)
        self.app.router.add_post("/test", self.handle_test_command)

    async def start_api_server(self):
        """Start the API server."""
        try:
            self.runner = web.AppRunner(self.app)
            await self.runner.setup()
            self.site = web.TCPSite(self.runner, "0.0.0.0", self.port)
            await self.site.start()
            logger.info(f"Developer API started on http://localhost:{self.port}")
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
        """Start API server when bot is ready."""
        logger.info("Cog: developer_api.py Loaded")
        await self.start_api_server()
        self.process_commands.start()

    def cog_unload(self):
        """Cleanup when cog is unloaded."""
        self.process_commands.cancel()
        asyncio.create_task(self.stop_api_server())

    @tasks.loop(seconds=0.5)
    async def process_commands(self):
        """Process queued commands."""
        try:
            while not self.command_queue.empty():
                command_data = await self.command_queue.get()
                await self._execute_command_internal(command_data)
        except Exception as e:
            logger.error(f"Error processing command queue: {e}")

    @process_commands.before_loop
    async def before_process_commands(self):
        """Wait for bot to be ready."""
        await self.bot.wait_until_ready()

    async def handle_status(self, request):
        """Handle status check requests."""
        return web.json_response(
            {
                "status": "online",
                "bot_name": self.bot.user.name if self.bot.user else "Not connected",
                "guild_id": self.guild_id,
                "test_channel_id": self.test_channel_id,
                "commands_in_queue": self.command_queue.qsize(),
            }
        )

    async def handle_execute_command(self, request):
        """
        Handle command execution requests.

        Expected JSON payload:
        {
            "command": "profile",
            "args": ["@user"],  // optional
            "channel_id": 123,  // optional, defaults to test channel
            "as_owner": true    // optional, defaults to true
        }
        """
        try:
            data = await request.json()
            command = data.get("command")
            args = data.get("args", [])
            channel_id = data.get("channel_id", self.test_channel_id)
            as_owner = data.get("as_owner", True)

            if not command:
                return web.json_response({"error": "Command is required"}, status=400)

            # Queue the command
            command_id = f"{command}_{asyncio.get_event_loop().time()}"
            await self.command_queue.put(
                {"id": command_id, "command": command, "args": args, "channel_id": channel_id, "as_owner": as_owner}
            )

            return web.json_response(
                {"success": True, "command_id": command_id, "message": f"Command '{command}' queued for execution"}
            )

        except Exception as e:
            logger.error(f"Error handling execute command: {e}")
            return web.json_response({"error": str(e)}, status=500)

    async def handle_test_command(self, request):
        """
        Handle test command requests with response capture.

        This endpoint executes a command and waits for the response.
        """
        try:
            data = await request.json()
            command = data.get("command")
            args = data.get("args", [])
            timeout = data.get("timeout", 5)

            if not command:
                return web.json_response({"error": "Command is required"}, status=400)

            # Execute and capture response
            result = await self._test_command(command, args, timeout)

            return web.json_response(result)

        except Exception as e:
            logger.error(f"Error handling test command: {e}")
            return web.json_response({"error": str(e)}, status=500)

    async def _execute_command_internal(self, command_data: Dict[str, Any]):
        """Execute a command internally."""
        try:
            guild = self.bot.get_guild(self.guild_id)
            if not guild:
                logger.error("Guild not found")
                return

            channel = guild.get_channel(command_data["channel_id"])
            if not channel:
                logger.error(f"Channel {command_data['channel_id']} not found")
                return

            # Get member to execute as
            member_id = self.owner_id if command_data["as_owner"] else self.bot.user.id
            member = guild.get_member(member_id)
            if not member:
                logger.error(f"Member {member_id} not found")
                return

            # Build command string
            command_str = command_data["command"]
            if command_data["args"]:
                command_str += " " + " ".join(command_data["args"])

            # Create fake message
            fake_message = FakeMessage(
                content=f"!{command_str}", author=member, channel=channel, guild=guild, bot=self.bot
            )

            # Get context and invoke
            ctx = await self.bot.get_context(fake_message)
            if ctx.valid:
                await self.bot.invoke(ctx)
                logger.info(f"Executed command: {command_str}")
            else:
                logger.error(f"Invalid command: {command_str}")

        except Exception as e:
            logger.error(f"Error executing command: {e}")

    async def _test_command(self, command: str, args: list, timeout: int) -> Dict[str, Any]:
        """Test a command and capture the response."""
        try:
            guild = self.bot.get_guild(self.guild_id)
            channel = guild.get_channel(self.test_channel_id)
            member = guild.get_member(self.owner_id)

            if not all([guild, channel, member]):
                return {"success": False, "error": "Failed to get guild/channel/member"}

            # Prepare to capture responses
            _responses = []

            def check(m):
                """Check if message is from bot in response to our command."""
                return m.channel == channel and m.author == self.bot.user

            # Build command string
            command_str = command
            if args:
                command_str += " " + " ".join(args)

            # Create fake message and context
            fake_message = FakeMessage(
                content=f"!{command_str}", author=member, channel=channel, guild=guild, bot=self.bot
            )

            ctx = await self.bot.get_context(fake_message)

            if not ctx.valid:
                return {"success": False, "error": "Invalid command"}

            # Start listening for responses
            response_task = asyncio.create_task(self.bot.wait_for("message", check=check, timeout=timeout))

            # Execute command
            await self.bot.invoke(ctx)

            # Wait for response
            try:
                response_msg = await response_task

                # Extract response data
                response_data = {
                    "content": response_msg.content,
                    "embeds": [embed.to_dict() for embed in response_msg.embeds],
                    "components": [
                        {"type": comp.type, "custom_id": getattr(comp, "custom_id", None)}
                        for comp in response_msg.components
                    ]
                    if response_msg.components
                    else [],
                }

                return {"success": True, "command": command_str, "response": response_data}

            except asyncio.TimeoutError:
                return {"success": False, "command": command_str, "error": "No response within timeout"}

        except Exception as e:
            return {"success": False, "error": str(e)}

    @commands.command(name="api_status")
    @is_zagadka_owner()
    async def api_status(self, ctx: commands.Context):
        """Check the status of the developer API."""
        if self.site and self.site.name:
            await ctx.send(f"✅ Developer API is running on http://localhost:{self.port}")
        else:
            await ctx.send("❌ Developer API is not running")

    @commands.command(name="api_test")
    @is_zagadka_owner()
    async def api_test(self, ctx: commands.Context, *, command: str):
        """Test the API by executing a command."""
        result = await self._test_command(command, [], 5)

        if result["success"]:
            await ctx.send(f"✅ Command executed successfully: `{command}`")
        else:
            await ctx.send(f"❌ Command failed: {result.get('error', 'Unknown error')}")


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
    await bot.add_cog(DeveloperAPICog(bot))
