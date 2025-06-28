#!/usr/bin/env python3
"""
MCP (Model Context Protocol) server for Discord bot command execution.
This allows Claude to directly execute bot commands for testing.
"""

import asyncio
import json
import logging
from contextlib import asynccontextmanager
from typing import Any, Dict, List, Optional

import aiohttp

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

logger = logging.getLogger(__name__)

# Configuration
API_BASE_URL = "http://localhost:8089"


class BotCommandExecutor:
    """Handles Discord bot command execution."""
    
    def __init__(self):
        self.config = config
        self.owner_id = 956602391891947592
        self.test_channel_id = 1387864734002446407
        self.guild_id = 960665311701528596
        self.bot = None
        self.guild = None
        self.channel = None
        self.owner = None
        
    async def initialize(self):
        """Initialize the bot connection."""
        # Create bot instance
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        intents.guilds = True
        intents.presences = True
        
        self.bot = commands.Bot(
            command_prefix="!",
            intents=intents,
            help_command=None
        )
        
        # Add config and database
        self.bot.config = self.config
        db = Database(self.config["database"]["url"])
        await db.create_tables()
        self.bot.db = db
        self.bot.get_db = db.session
        
        # Add service getter
        async def get_service(interface, session):
            from core.service_container import ServiceContainer
            container = ServiceContainer(self.bot)
            return await container.get_service(interface, session)
        
        self.bot.get_service = get_service
        
        # Load all cogs
        await self._load_cogs()
        
        # Start bot in background
        asyncio.create_task(self.bot.start(self.config["discord"]["token"]))
        
        # Wait for bot to be ready
        await self.bot.wait_until_ready()
        
        # Get guild, channel, and owner
        self.guild = self.bot.get_guild(self.guild_id)
        if self.guild:
            self.channel = self.guild.get_channel(self.test_channel_id)
            self.owner = self.guild.get_member(self.owner_id)
            
        logger.info(f"Bot initialized: {self.bot.user.name}")
        
    async def _load_cogs(self):
        """Load all cogs from the cogs directory."""
        cogs_dir = os.path.join(os.path.dirname(__file__), "cogs", "commands")
        
        # Get all Python files in cogs directory
        for root, dirs, files in os.walk(cogs_dir):
            for file in files:
                if file.endswith('.py') and not file.startswith('__'):
                    # Convert file path to module path
                    rel_path = os.path.relpath(os.path.join(root, file), os.path.dirname(__file__))
                    module_path = rel_path.replace(os.sep, '.')[:-3]  # Remove .py
                    
                    try:
                        await self.bot.load_extension(module_path)
                        logger.info(f"Loaded cog: {module_path}")
                    except Exception as e:
                        logger.error(f"Failed to load cog {module_path}: {e}")
                        
    async def execute_command(self, command: str, args: List[str] = None) -> Dict[str, Any]:
        """
        Execute a bot command as the owner.
        
        Args:
            command: The command name (without prefix)
            args: Optional command arguments
            
        Returns:
            Dict with execution results
        """
        if not all([self.bot, self.guild, self.channel, self.owner]):
            return {
                "success": False,
                "error": "Bot not properly initialized"
            }
            
        # Build command string
        command_str = command
        if args:
            command_str += " " + " ".join(args)
            
        # Create fake message
        fake_message = FakeMessage(
            content=f"!{command_str}",
            author=self.owner,
            channel=self.channel,
            guild=self.guild,
            bot=self.bot
        )
        
        # Capture responses
        responses = []
        original_send = self.channel.send
        
        async def capture_send(content=None, **kwargs):
            """Capture channel.send calls."""
            response = {
                "content": content,
                "embeds": [],
                "components": []
            }
            
            if "embed" in kwargs:
                response["embeds"].append(kwargs["embed"].to_dict())
            if "embeds" in kwargs:
                response["embeds"].extend([e.to_dict() for e in kwargs["embeds"]])
            if "view" in kwargs:
                # TODO: Serialize view components
                response["has_view"] = True
                
            responses.append(response)
            return fake_message
            
        # Temporarily replace channel.send
        self.channel.send = capture_send
        
        try:
            # Get context and invoke
            ctx = await self.bot.get_context(fake_message)
            
            if not ctx.valid:
                return {
                    "success": False,
                    "error": f"Invalid command: {command}"
                }
                
            # Execute command
            await self.bot.invoke(ctx)
            
            return {
                "success": True,
                "command": command_str,
                "responses": responses
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "command": command_str
            }
        finally:
            # Restore original send
            self.channel.send = original_send
            
    async def get_bot_status(self) -> Dict[str, Any]:
        """Get current bot status."""
        return {
            "connected": self.bot and self.bot.user is not None,
            "bot_name": self.bot.user.name if self.bot and self.bot.user else "Not connected",
            "guild_name": self.guild.name if self.guild else "Not found",
            "channel_name": self.channel.name if self.channel else "Not found",
            "owner_name": str(self.owner) if self.owner else "Not found",
            "cogs_loaded": len(self.bot.cogs) if self.bot else 0,
            "commands_available": len(self.bot.commands) if self.bot else 0
        }


class FakeMessage:
    """Fake message object for command simulation."""
    
    def __init__(self, content: str, author: discord.Member, channel: discord.TextChannel,
                 guild: discord.Guild, bot: commands.Bot):
        self.content = content
        self.author = author
        self.channel = channel
        self.guild = guild
        self.bot = bot
        self._state = bot._connection
        
        # Required attributes
        self.id = 0
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
        
    async def reply(self, content=None, **kwargs):
        """Fake reply method."""
        if content or kwargs:
            await self.channel.send(content, **kwargs)
        return self


# MCP Server setup
executor = BotCommandExecutor()
server = Server("discord-bot-mcp")


@server.list_tools()
async def list_tools() -> List[Tool]:
    """List available tools."""
    return [
        Tool(
            name="execute_bot_command",
            description="Execute a Discord bot command as the owner",
            input_schema={
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "The command to execute (without prefix)"
                    },
                    "args": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Optional command arguments"
                    }
                },
                "required": ["command"]
            }
        ),
        Tool(
            name="get_bot_status",
            description="Get current bot status and connection info",
            input_schema={
                "type": "object",
                "properties": {}
            }
        ),
        Tool(
            name="test_profile",
            description="Quick test of the profile command",
            input_schema={
                "type": "object",
                "properties": {
                    "user_mention": {
                        "type": "string",
                        "description": "Optional user mention (e.g., @username)"
                    }
                }
            }
        ),
        Tool(
            name="test_shop",
            description="Quick test of the shop command",
            input_schema={
                "type": "object",
                "properties": {}
            }
        )
    ]


@server.call_tool()
async def call_tool(name: str, arguments: Dict[str, Any]) -> List[TextContent]:
    """Handle tool calls."""
    
    if name == "execute_bot_command":
        command = arguments.get("command")
        args = arguments.get("args", [])
        
        result = await executor.execute_command(command, args)
        
        # Format response
        if result["success"]:
            text = f"✅ Command executed: !{result['command']}\n\n"
            
            if result["responses"]:
                text += f"Bot sent {len(result['responses'])} response(s):\n"
                
                for i, response in enumerate(result["responses"], 1):
                    text += f"\nResponse {i}:\n"
                    
                    if response["content"]:
                        text += f"Content: {response['content']}\n"
                        
                    if response["embeds"]:
                        text += f"Embeds: {len(response['embeds'])}\n"
                        for j, embed in enumerate(response["embeds"], 1):
                            title = embed.get("title", "No title")
                            text += f"  Embed {j}: {title}\n"
                            
                    if response.get("has_view"):
                        text += "Has interactive components (buttons/selects)\n"
            else:
                text += "No visible response (command may have executed silently)"
        else:
            text = f"❌ Command failed: {result.get('error', 'Unknown error')}"
            
        return [TextContent(type="text", text=text)]
        
    elif name == "get_bot_status":
        status = await executor.get_bot_status()
        
        text = "🤖 Bot Status:\n"
        text += f"Connected: {'✅' if status['connected'] else '❌'}\n"
        text += f"Bot: {status['bot_name']}\n"
        text += f"Guild: {status['guild_name']}\n"
        text += f"Channel: {status['channel_name']}\n"
        text += f"Owner: {status['owner_name']}\n"
        text += f"Cogs loaded: {status['cogs_loaded']}\n"
        text += f"Commands available: {status['commands_available']}"
        
        return [TextContent(type="text", text=text)]
        
    elif name == "test_profile":
        user_mention = arguments.get("user_mention", "")
        args = [user_mention] if user_mention else []
        
        result = await executor.execute_command("profile", args)
        
        if result["success"]:
            text = "✅ Profile command executed\n"
            if result["responses"] and result["responses"][0]["embeds"]:
                embed = result["responses"][0]["embeds"][0]
                text += f"\nProfile: {embed.get('title', 'Unknown')}\n"
                
                # Extract some fields
                if "fields" in embed:
                    for field in embed["fields"]:
                        text += f"{field['name']}: {field['value']}\n"
        else:
            text = f"❌ Profile test failed: {result.get('error', 'Unknown error')}"
            
        return [TextContent(type="text", text=text)]
        
    elif name == "test_shop":
        result = await executor.execute_command("shop", [])
        
        if result["success"]:
            text = "✅ Shop command executed\n"
            if result["responses"] and result["responses"][0]["embeds"]:
                embed = result["responses"][0]["embeds"][0]
                text += f"\nShop: {embed.get('title', 'Unknown')}\n"
                text += f"Description: {embed.get('description', '')[:200]}..."
        else:
            text = f"❌ Shop test failed: {result.get('error', 'Unknown error')}"
            
        return [TextContent(type="text", text=text)]
        
    else:
        return [TextContent(type="text", text=f"Unknown tool: {name}")]


async def main():
    """Main entry point."""
    # Initialize bot executor
    print("Initializing Discord bot connection...")
    await executor.initialize()
    print("Bot connected! Starting MCP server...")
    
    # Run MCP server
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream)


if __name__ == "__main__":
    asyncio.run(main())