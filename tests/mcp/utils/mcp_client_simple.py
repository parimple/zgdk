#!/usr/bin/env python3
"""
Simple MCP Client that uses the command_tester HTTP API.
This is a simpler approach that doesn't require the full MCP protocol.
"""

import asyncio
import sys
from typing import Any, Dict

import aiohttp


class SimpleMCPClient:
    """Simple client for bot control via HTTP API."""

    def __init__(self, api_url: str = "http://localhost:8090"):
        self.api_url = api_url

    async def check_status(self) -> Dict[str, Any]:
        """Check bot API status."""
        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(f"{self.api_url}/status") as resp:
                    return await resp.json()
            except Exception as e:
                return {"error": str(e)}

    async def execute_command(self, command: str, args: str = "", send_to_channel: bool = False) -> Dict[str, Any]:
        """Execute a Discord bot command."""
        payload = {"command": command, "args": args, "send_to_channel": send_to_channel}

        async with aiohttp.ClientSession() as session:
            try:
                async with session.post(f"{self.api_url}/execute", json=payload) as resp:
                    return await resp.json()
            except Exception as e:
                return {"error": str(e)}

    def format_response(self, response: Dict[str, Any]) -> str:
        """Format API response for display."""
        if response.get("error"):
            return f"❌ Error: {response['error']}"

        if not response.get("success"):
            return f"❌ Command failed: {response.get('error', 'Unknown error')}"

        output = f"✅ Command executed: ,{response.get('command', '')}\n"

        responses = response.get("responses", [])
        if responses:
            output += f"\nBot responses ({len(responses)}):\n"
            for i, resp in enumerate(responses, 1):
                output += f"\n--- Response {i} ---\n"

                if resp.get("content"):
                    output += f"Content: {resp['content']}\n"

                if resp.get("embeds"):
                    for embed in resp["embeds"]:
                        output += f"Embed: {embed.get('title', 'No title')}\n"
                        if embed.get("description"):
                            desc = embed["description"][:200]
                            if len(embed["description"]) > 200:
                                desc += "..."
                            output += f"Description: {desc}\n"
                        if embed.get("fields"):
                            output += f"Fields: {len(embed['fields'])}\n"
        else:
            output += "No visible responses captured."

        return output


async def interactive_mode():
    """Run interactive client."""
    client = SimpleMCPClient()

    print("Discord Bot Control Client")
    print("=" * 50)
    print("Commands:")
    print("  status - Check bot status")
    print("  <command> [args] - Execute a Discord command")
    print("  send <command> [args] - Execute and send to channel")
    print("  quit - Exit")
    print("=" * 50)

    # Check initial status
    print("\nChecking bot status...")
    status = await client.check_status()
    if "error" not in status:
        print(f"✅ Bot Status: {status.get('status', 'unknown')}")
        print(f"   Bot: {status.get('bot_name', 'Not connected')}")
        print(f"   Commands available: {status.get('commands_available', 0)}")
    else:
        print(f"❌ {status['error']}")
    print()

    while True:
        try:
            user_input = input("bot> ").strip()

            if not user_input:
                continue

            if user_input.lower() in ["quit", "exit"]:
                print("Goodbye!")
                break

            elif user_input.lower() == "status":
                status = await client.check_status()
                if "error" not in status:
                    print(f"✅ Bot Status: {status.get('status', 'unknown')}")
                    print(f"   Bot: {status.get('bot_name', 'Not connected')}")
                    print(f"   Guild: {status.get('guild_id', 'N/A')}")
                    print(f"   Test Channel: {status.get('test_channel_id', 'N/A')}")
                    print(f"   Commands: {status.get('commands_available', 0)}")
                else:
                    print(f"❌ {status['error']}")

            else:
                # Parse command
                send_to_channel = False
                if user_input.startswith("send "):
                    send_to_channel = True
                    user_input = user_input[5:]

                parts = user_input.split(maxsplit=1)
                command = parts[0]
                args = parts[1] if len(parts) > 1 else ""

                # Execute command
                result = await client.execute_command(command, args, send_to_channel)
                print(client.format_response(result))

        except KeyboardInterrupt:
            print("\nUse 'quit' to exit")
        except Exception as e:
            print(f"Error: {e}")


async def test_info_commands():
    """Test all info module commands."""
    client = SimpleMCPClient()

    print("Testing Info Module Commands")
    print("=" * 60)

    # Check status
    status = await client.check_status()
    if "error" not in status:
        print(f"✅ Bot connected: {status.get('bot_name', 'Unknown')}")
    else:
        print(f"❌ Cannot connect to bot: {status['error']}")
        return

    # Commands to test
    commands = [
        ("profile", ""),
        ("profile", "bohun"),
        ("p", ""),
        ("bypass", "check bohun"),
        ("pomoc", ""),
        ("help", ""),
        ("games", ""),
        ("gry", ""),
        ("ping", ""),
        ("serverinfo", ""),
        ("si", ""),
        ("roles", ""),
        ("allroles", ""),
        ("invites", ""),
        ("invites", "bohun"),
        ("checkroles", "bohun"),
        ("checkstatus", "bohun"),
    ]

    success = 0
    failed = 0

    for cmd, args in commands:
        print(f"\n{'='*60}")
        print(f"Testing: ,{cmd} {args}")
        print(f"{'='*60}")

        result = await client.execute_command(cmd, args)
        formatted = client.format_response(result)
        print(formatted)

        if result.get("success"):
            success += 1
        else:
            failed += 1

        await asyncio.sleep(0.5)

    print(f"\n{'='*60}")
    print("Testing complete!")
    print(f"✅ Successful: {success}")
    print(f"❌ Failed: {failed}")
    print(f"{'='*60}")


async def main():
    """Main function."""
    if len(sys.argv) > 1:
        if sys.argv[1] == "test":
            await test_info_commands()
        elif sys.argv[1] == "send" and len(sys.argv) > 2:
            # Quick send command
            client = SimpleMCPClient()
            parts = " ".join(sys.argv[2:]).split(maxsplit=1)
            command = parts[0]
            args = parts[1] if len(parts) > 1 else ""
            result = await client.execute_command(command, args, send_to_channel=True)
            print(client.format_response(result))
        else:
            # Execute single command
            client = SimpleMCPClient()
            parts = " ".join(sys.argv[1:]).split(maxsplit=1)
            command = parts[0]
            args = parts[1] if len(parts) > 1 else ""
            result = await client.execute_command(command, args)
            print(client.format_response(result))
    else:
        await interactive_mode()


if __name__ == "__main__":
    asyncio.run(main())
