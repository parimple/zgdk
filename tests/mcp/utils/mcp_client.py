#!/usr/bin/env python3
"""
MCP Client for controlling Discord bot.
This client connects to the MCP server running in Docker container.
"""

import asyncio
import json
import subprocess
import sys
from typing import Any, Dict


async def call_mcp_tool(tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Call an MCP tool and return the result."""

    # Prepare the request
    request = {"jsonrpc": "2.0", "method": "tools/call", "params": {"name": tool_name, "arguments": arguments}, "id": 1}

    # Convert to JSON
    _request_json = json.dumps(request)

    # Call MCP server through docker exec
    cmd = [
        "docker",
        "exec",
        "-i",
        "zgdk-mcp-1",
        "python",
        "-c",
        """
import sys
import json
import asyncio
from mcp_bot_server import call_tool

async def main():
    result = await call_tool('{tool_name}', {json.dumps(arguments)})
    response = {{
        "jsonrpc": "2.0",
        "result": {{
            "content": [{{
                "type": r.type,
                "text": r.text
            }} for r in result]
        }},
        "id": 1
    }}
    print(json.dumps(response))

asyncio.run(main())
""",
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        response = json.loads(result.stdout)
        return response
    except subprocess.CalledProcessError as e:
        print(f"Error calling MCP: {e}")
        print(f"stderr: {e.stderr}")
        return {"error": str(e)}
    except json.JSONDecodeError as e:
        print(f"Error parsing response: {e}")
        print(f"stdout: {result.stdout}")
        return {"error": "Invalid JSON response"}


class MCPBotClient:
    """MCP Client for Discord bot control."""

    async def check_status(self) -> str:
        """Check bot API status."""
        response = await call_mcp_tool("bot_status", {})
        if "result" in response:
            return response["result"]["content"][0]["text"]
        return f"Error: {response.get('error', 'Unknown error')}"

    async def execute_command(self, command: str, args: str = "", send_to_channel: bool = False) -> str:
        """Execute a Discord bot command."""
        response = await call_mcp_tool("execute_command", {"command": command, "args": args})
        if "result" in response:
            return response["result"]["content"][0]["text"]
        return f"Error: {response.get('error', 'Unknown error')}"

    async def get_last_response(self, command: str) -> str:
        """Get the last response for a command."""
        response = await call_mcp_tool("last_response", {"command": command})
        if "result" in response:
            return response["result"]["content"][0]["text"]
        return f"Error: {response.get('error', 'Unknown error')}"


async def interactive_mode():
    """Run interactive MCP client."""
    client = MCPBotClient()

    print("MCP Bot Control Client")
    print("=" * 50)
    print("Commands:")
    print("  status - Check bot status")
    print("  exec <command> [args] - Execute a command")
    print("  last <command> - Get last response for command")
    print("  quit - Exit")
    print("=" * 50)

    # First check status
    print("\nChecking bot status...")
    status = await client.check_status()
    print(status)
    print()

    while True:
        try:
            user_input = input("mcp> ").strip()

            if not user_input:
                continue

            parts = user_input.split(maxsplit=2)
            cmd = parts[0].lower()

            if cmd == "quit" or cmd == "exit":
                print("Goodbye!")
                break

            elif cmd == "status":
                result = await client.check_status()
                print(result)

            elif cmd == "exec":
                if len(parts) < 2:
                    print("Usage: exec <command> [args]")
                    continue
                command = parts[1]
                args = parts[2] if len(parts) > 2 else ""
                print(f"Executing: ,{command} {args}")
                result = await client.execute_command(command, args)
                print(result)

            elif cmd == "last":
                if len(parts) < 2:
                    print("Usage: last <command>")
                    continue
                command = parts[1]
                result = await client.get_last_response(command)
                print(result)

            else:
                print(f"Unknown command: {cmd}")

        except KeyboardInterrupt:
            print("\nUse 'quit' to exit")
        except Exception as e:
            print(f"Error: {e}")


async def batch_test():
    """Run batch test of info commands."""
    client = MCPBotClient()

    print("Testing Info Module Commands via MCP")
    print("=" * 60)

    # Check status first
    print("Checking bot status...")
    status = await client.check_status()
    print(status)
    print()

    # List of commands to test
    commands = [
        ("profile", ""),
        ("profile", "bohun"),
        ("p", ""),
        ("help", ""),
        ("pomoc", ""),
        ("games", ""),
        ("ping", ""),
        ("serverinfo", ""),
        ("roles", ""),
    ]

    for cmd, args in commands:
        print(f"\nTesting: ,{cmd} {args}")
        print("-" * 40)
        result = await client.execute_command(cmd, args)
        print(result)
        await asyncio.sleep(0.5)

    print("\n" + "=" * 60)
    print("Testing complete!")


async def main():
    """Main function."""
    if len(sys.argv) > 1 and sys.argv[1] == "test":
        await batch_test()
    else:
        await interactive_mode()


if __name__ == "__main__":
    asyncio.run(main())
