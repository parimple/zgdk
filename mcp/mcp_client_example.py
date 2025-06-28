#!/usr/bin/env python3
"""
Example MCP Client for testing ZGDK bot.
"""

import asyncio
import json

from mcp.client import Client
from mcp.client.stdio import stdio_transport


class ZGDKTestClient:
    """Test client for ZGDK MCP server."""

    def __init__(self):
        self.client = Client("zgdk-test-client")

    async def test_bot_status(self):
        """Test bot status command."""
        print("\n=== Testing Bot Status ===")
        result = await self.client.call_tool("bot_status", {})
        print(json.dumps(result, indent=2))
        return result

    async def test_user_info(self, user_id: str):
        """Test getting user information."""
        print(f"\n=== Testing User Info for {user_id} ===")
        result = await self.client.call_tool("get_user_info", {"user_id": user_id})
        print(json.dumps(result, indent=2))
        return result

    async def test_command_execution(self, command: str, user_id: str, args: str = ""):
        """Test command execution."""
        print(f"\n=== Testing Command: {command} ===")
        result = await self.client.call_tool("execute_command", {"command": command, "user_id": user_id, "args": args})
        print(json.dumps(result, indent=2))
        return result

    async def test_balance_modification(self, user_id: str, amount: int):
        """Test balance modification."""
        print("\n=== Testing Balance Modification ===")
        result = await self.client.call_tool(
            "modify_user_balance", {"user_id": user_id, "amount": amount, "reason": "Testing via MCP"}
        )
        print(json.dumps(result, indent=2))
        return result

    async def test_decision_analysis(self, user_id: str = None):
        """Test decision analysis."""
        print("\n=== Testing Decision Analysis ===")
        params = {"limit": 5}
        if user_id:
            params["user_id"] = user_id

        result = await self.client.call_tool("analyze_decisions", params)
        print(json.dumps(result, indent=2))
        return result

    async def test_performance_stats(self):
        """Test performance statistics."""
        print("\n=== Testing Performance Stats ===")
        result = await self.client.call_tool("get_performance_stats", {})
        print(json.dumps(result, indent=2))
        return result

    async def run_all_tests(self, test_user_id: str = "123456789"):
        """Run all tests in sequence."""
        print("Starting ZGDK MCP Tests...")

        # 1. Check bot status
        await self.test_bot_status()
        await asyncio.sleep(1)

        # 2. Get user info
        await self.test_user_info(test_user_id)
        await asyncio.sleep(1)

        # 3. Modify balance
        await self.test_balance_modification(test_user_id, 1000)
        await asyncio.sleep(1)

        # 4. Execute a command
        await self.test_command_execution("profile", test_user_id)
        await asyncio.sleep(1)

        # 5. Analyze decisions
        await self.test_decision_analysis(test_user_id)
        await asyncio.sleep(1)

        # 6. Get performance stats
        await self.test_performance_stats()

        print("\n✅ All tests completed!")

    async def interactive_mode(self):
        """Run in interactive mode."""
        print("\n🤖 ZGDK MCP Interactive Mode")
        print("Commands:")
        print("  status - Check bot status")
        print("  user <id> - Get user info")
        print("  cmd <command> <user_id> [args] - Execute command")
        print("  balance <user_id> <amount> - Modify balance")
        print("  decisions [user_id] - Analyze decisions")
        print("  perf [command] - Performance stats")
        print("  quit - Exit")

        while True:
            try:
                cmd = input("\n> ").strip().split()
                if not cmd:
                    continue

                if cmd[0] == "quit":
                    break
                elif cmd[0] == "status":
                    await self.test_bot_status()
                elif cmd[0] == "user" and len(cmd) > 1:
                    await self.test_user_info(cmd[1])
                elif cmd[0] == "cmd" and len(cmd) > 2:
                    args = " ".join(cmd[3:]) if len(cmd) > 3 else ""
                    await self.test_command_execution(cmd[1], cmd[2], args)
                elif cmd[0] == "balance" and len(cmd) > 2:
                    await self.test_balance_modification(cmd[1], int(cmd[2]))
                elif cmd[0] == "decisions":
                    user_id = cmd[1] if len(cmd) > 1 else None
                    await self.test_decision_analysis(user_id)
                elif cmd[0] == "perf":
                    await self.test_performance_stats()
                else:
                    print("❌ Invalid command")

            except KeyboardInterrupt:
                break
            except Exception as e:
                print(f"❌ Error: {e}")

        print("\n👋 Goodbye!")


async def main():
    """Main entry point."""
    client = ZGDKTestClient()

    # Connect to MCP server
    async with stdio_transport(client.client, "python", "mcp/zgdk_mcp_server.py") as transport:
        await transport.start()

        # Run tests or interactive mode
        import sys

        if len(sys.argv) > 1 and sys.argv[1] == "--test":
            test_user_id = sys.argv[2] if len(sys.argv) > 2 else "123456789"
            await client.run_all_tests(test_user_id)
        else:
            await client.interactive_mode()


if __name__ == "__main__":
    asyncio.run(main())
