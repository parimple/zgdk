#!/usr/bin/env python3
"""
MCP server for Discord bot command execution.
This server communicates with the bot's HTTP API to execute commands.
"""

import asyncio
import logging
from typing import Any, Dict, List

import aiohttp

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Bot API configuration
import os

# Use command_tester API on port 8090 instead of owner_utils
API_BASE_URL = os.getenv("API_BASE_URL", "http://app:8090")

# Create server instance
server = Server("discord-bot-tester")


@server.list_tools()
async def list_tools() -> List[Tool]:
    """List available tools for Discord bot testing."""
    return [
        Tool(
            name="execute_command",
            description="Execute a Discord bot command as the owner",
            input_schema={
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "The command to execute (e.g., 'profile', 'shop')"
                    },
                    "args": {
                        "type": "string",
                        "description": "Optional command arguments"
                    }
                },
                "required": ["command"]
            }
        ),
        Tool(
            name="bot_status",
            description="Check if the bot API is running",
            input_schema={
                "type": "object",
                "properties": {}
            }
        ),
        Tool(
            name="last_response",
            description="Get the last response for a specific command",
            input_schema={
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "The command to get the last response for"
                    }
                },
                "required": ["command"]
            }
        )
    ]


@server.call_tool()
async def call_tool(name: str, arguments: Dict[str, Any]) -> List[TextContent]:
    """Handle tool calls."""

    async with aiohttp.ClientSession() as session:
        try:
            if name == "execute_command":
                command = arguments.get("command", "")
                args = arguments.get("args", "")

                # Call bot API
                url = f"{API_BASE_URL}/execute"
                payload = {"command": command, "args": args}

                async with session.post(url, json=payload) as resp:
                    if resp.status == 200:
                        data = await resp.json()

                        if data.get("success"):
                            text = f"✅ Command executed: ,{data['command']}\n\n"

                            responses = data.get("responses", [])
                            if responses:
                                text += f"Bot responses ({len(responses)}):\n"

                                for i, response in enumerate(responses, 1):
                                    text += f"\n--- Response {i} ---\n"

                                    if response.get("content"):
                                        text += f"Content: {response['content']}\n"

                                    if response.get("embeds"):
                                        for embed in response["embeds"]:
                                            text += f"Embed Title: {embed.get('title', 'No title')}\n"
                                            if embed.get("description"):
                                                text += f"Description: {embed['description'][:200]}...\n"
                                            if embed.get("fields"):
                                                text += f"Fields: {len(embed['fields'])}\n"
                                                for field in embed["fields"][:3]:
                                                    text += f"  - {field['name']}: {field['value']}\n"
                            else:
                                text += "No visible response captured."
                        else:
                            text = f"❌ Command failed: {data.get('error', 'Unknown error')}"
                    else:
                        error_text = await resp.text()
                        text = f"❌ API error (status {resp.status}): {error_text}"

                return [TextContent(type="text", text=text)]

            elif name == "bot_status":
                url = f"{API_BASE_URL}/status"

                try:
                    async with session.get(url) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            text = "🤖 Bot API Status:\n"
                            text += f"Status: {data.get('status', 'unknown')}\n"
                            text += f"Bot: {data.get('bot_name', 'Not connected')}\n"
                            text += f"Guild ID: {data.get('guild_id', 'N/A')}\n"
                            text += f"Test Channel ID: {data.get('test_channel_id', 'N/A')}\n"
                            text += f"API Port: {data.get('api_port', 'N/A')}"
                        else:
                            text = f"❌ Cannot connect to bot API (status {resp.status})"
                except aiohttp.ClientConnectorError:
                    text = "❌ Bot API is not running. Make sure the bot is running with owner_utils cog loaded."

                return [TextContent(type="text", text=text)]

            elif name == "last_response":
                command = arguments.get("command", "")
                url = f"{API_BASE_URL}/last_response?command={command}"

                async with session.get(url) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        text = f"📝 Last response for command '{command}':\n"
                        text += f"Success: {data.get('success', False)}\n"
                        text += f"Timestamp: {data.get('timestamp', 'N/A')}\n"

                        responses = data.get("responses", [])
                        if responses:
                            text += f"\nResponses ({len(responses)}):\n"
                            for i, response in enumerate(responses, 1):
                                if response.get("content"):
                                    text += f"{i}. {response['content'][:100]}...\n"
                                if response.get("embed"):
                                    text += f"{i}. Embed: {response['embed'].get('title', 'No title')}\n"
                    elif resp.status == 404:
                        text = f"❌ No response found for command '{command}'"
                    else:
                        text = f"❌ Error getting last response (status {resp.status})"

                return [TextContent(type="text", text=text)]

            else:
                return [TextContent(type="text", text=f"Unknown tool: {name}")]

        except Exception as e:
            return [TextContent(type="text", text=f"❌ Error: {str(e)}")]


async def main():
    """Run the MCP server."""
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, {})


if __name__ == "__main__":
    print("Starting Discord Bot MCP Server...")
    print("Make sure the bot is running with command_tester cog loaded.")
    print(f"Bot API expected at: {API_BASE_URL}")
    asyncio.run(main())
