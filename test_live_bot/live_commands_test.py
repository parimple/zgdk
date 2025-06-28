#!/usr/bin/env python3
"""
Working Discord API test using discord.py-self correctly
Fixed typing issues and proper error handling
"""
import asyncio
import glob
import json
import os
import subprocess
from datetime import datetime, timezone
from typing import Any, Dict, List

# Use discord.py-self (which is what's currently installed)
import discord

# Test configuration
TEST_GUILD_ID = 960665311701528596
TEST_CHANNEL_ID = 1387864734002446407
TEST_USER_ID = 968632323916566579
DELAY_BETWEEN_COMMANDS = 3


class DiscordAPITester:
    def __init__(self, token: str):
        self.token = token
        self.test_results: List[Dict[str, Any]] = []

        # Create client for user account (discord.py-self doesn't need Intents)
        self.client = discord.Client()

    async def run_tests(self) -> Dict[str, Any]:
        """Run Discord API tests"""

        @self.client.event
        async def on_ready():
            if not self.client.user:
                print("❌ Failed to authenticate")
                await self.client.close()
                return

            print(f"👤 Successfully logged in as: {self.client.user.name}")
            print(f"🆔 User ID: {self.client.user.id}")

            guild = self.client.get_guild(TEST_GUILD_ID)
            if not guild:
                print("❌ Could not find guild")
                await self.client.close()
                return

            channel = guild.get_channel(TEST_CHANNEL_ID)
            if not channel:
                print("❌ Could not find channel")
                await self.client.close()
                return

            # Type guard for text channel
            if not hasattr(channel, "send"):
                print("❌ Channel is not a text channel")
                await self.client.close()
                return

            print(f"✅ Connected to {guild.name} -> {channel.name}")

            # Test commands
            commands_to_test = [
                (f",addbalance <@{TEST_USER_ID}> 1000", "Add balance test"),
                (",profile", "Profile test"),
                (",shop", "Shop test"),
            ]

            for command, description in commands_to_test:
                print(f"\n🧪 {description}")
                print(f"📤 Command: {command}")

                try:
                    before_time = datetime.now(timezone.utc)
                    message = await channel.send(command)
                    print(f"✅ Command sent (ID: {message.id})")

                    # Wait for bot response
                    bot_responses = []
                    for i in range(15):
                        await asyncio.sleep(1)

                        if hasattr(channel, "history"):
                            async for msg in channel.history(limit=10, after=before_time):
                                if msg.author.bot and msg.id != message.id and msg not in bot_responses:
                                    bot_responses.append(msg)
                                    print(f"📥 Bot response: {msg.content[:100]}...")

                        if bot_responses:
                            break

                    if bot_responses:
                        status = "SUCCESS"
                        response_text = bot_responses[0].content
                    else:
                        status = "NO_RESPONSE"
                        response_text = ""

                    self.test_results.append(
                        {
                            "test": description,
                            "command": command,
                            "status": status,
                            "response": response_text,
                            "timestamp": datetime.now().isoformat(),
                        }
                    )

                    print(f"Status: {status}")
                    if response_text:
                        print(f"Response: {response_text[:150]}...")

                    await asyncio.sleep(DELAY_BETWEEN_COMMANDS)

                except Exception as e:
                    print(f"❌ Error with {command}: {e}")
                    self.test_results.append(
                        {
                            "test": description,
                            "command": command,
                            "status": "ERROR",
                            "error": str(e),
                            "timestamp": datetime.now().isoformat(),
                        }
                    )

            await self.client.close()

            # Print summary
            print("\n" + "=" * 50)
            print("📊 TEST RESULTS SUMMARY")
            print("=" * 50)

            success_count = 0
            for i, result in enumerate(self.test_results, 1):
                status = result["status"]
                if status == "SUCCESS":
                    success_count += 1
                    print(f"{i}. ✅ {result['test']}: {status}")
                    if "response" in result:
                        print(f"   💬 {result['response'][:100]}...")
                else:
                    print(f"{i}. ❌ {result['test']}: {status}")

            success_rate = (success_count / len(self.test_results) * 100) if self.test_results else 0
            print(f"\nSuccess Rate: {success_rate:.1f}% ({success_count}/{len(self.test_results)})")

            if success_rate >= 75:
                print("🎉 Overall Status: EXCELLENT")
            elif success_rate >= 50:
                print("👍 Overall Status: GOOD")
            else:
                print("⚠️ Overall Status: NEEDS ATTENTION")

            # Save results
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"test_live_bot/results/live_test_{timestamp}.json"

            try:
                os.makedirs("test_live_bot/results", exist_ok=True)
                with open(filename, "w") as f:
                    json.dump(
                        {
                            "success_rate": success_rate,
                            "total_tests": len(self.test_results),
                            "successful_tests": success_count,
                            "test_results": self.test_results,
                        },
                        f,
                        indent=2,
                        default=str,
                    )
                print(f"\n📄 Results saved to: {filename}")
            except Exception as e:
                print(f"❌ Failed to save results: {e}")

            # Check for errors after tests
            print("\n" + "=" * 50)
            print("🔍 CHECKING FOR ERRORS")
            print("=" * 50)

            await self.check_docker_logs()
            await self.check_error_logs()

            # Store results for return
            self.results = {
                "success_rate": success_rate,
                "total_tests": len(self.test_results),
                "successful_tests": success_count,
                "test_results": self.test_results,
            }

        # This will be set by on_ready event
        self.results = None

        try:
            await self.client.start(self.token)
        except Exception as e:
            print(f"💥 Failed to start client: {str(e)}")
            return {"error": str(e)}

        return self.results or {"error": "No results"}

    async def check_docker_logs(self):
        """Check Docker logs for recent errors"""
        print("🐳 Checking Docker logs for errors...")

        try:
            # Get recent Docker logs
            result = subprocess.run(
                ["docker-compose", "logs", "app", "--tail=50"], capture_output=True, text=True, timeout=10
            )

            if result.returncode == 0:
                logs = result.stdout

                # Look for error patterns
                error_patterns = ["ERROR", "Failed", "Exception", "Traceback", "Error:"]
                found_errors = []

                for line in logs.split("\n"):
                    for pattern in error_patterns:
                        if pattern in line and "add_activity" not in line:  # Skip activity logs
                            found_errors.append(line.strip())

                if found_errors:
                    print(f"⚠️ Found {len(found_errors)} potential errors in Docker logs:")
                    for error in found_errors[-5:]:  # Show last 5 errors
                        print(f"   🔸 {error}")
                else:
                    print("✅ No errors found in Docker logs")
            else:
                print("❌ Failed to get Docker logs")

        except Exception as e:
            print(f"❌ Error checking Docker logs: {e}")

    async def check_error_logs(self):
        """Check error log files for recent errors"""
        print("\n📁 Checking error log files...")

        try:
            # Look for error log files
            error_log_patterns = [
                "logs/error*.log",
                "logs/bot_errors*.log",
                "error_logs/*.log",
                "utils/error_logs/*.json",
            ]

            found_files = []
            for pattern in error_log_patterns:
                found_files.extend(glob.glob(pattern))

            if found_files:
                print(f"📂 Found {len(found_files)} error log file(s)")

                for log_file in found_files[-3:]:  # Check last 3 files
                    try:
                        with open(log_file, "r") as f:
                            content = f.read()

                        # Check if file has recent content (last hour)
                        file_time = os.path.getmtime(log_file)
                        current_time = datetime.now().timestamp()

                        if (current_time - file_time) < 3600:  # Last hour
                            print(f"   📄 {log_file} (recent)")
                            if content.strip():
                                lines = content.strip().split("\n")
                                print(f"      📝 {len(lines)} error entries")
                                # Show last few lines
                                for line in lines[-3:]:
                                    print(f"      🔸 {line[:100]}...")
                            else:
                                print("      ✅ File is empty")
                        else:
                            print(f"   📄 {log_file} (old)")

                    except Exception as e:
                        print(f"   ❌ Error reading {log_file}: {e}")
            else:
                print("✅ No error log files found")

        except Exception as e:
            print(f"❌ Error checking log files: {e}")


async def main():
    # Get token from environment
    token = os.getenv("CLAUDE_BOT_TOKEN")
    if not token:
        print("❌ CLAUDE_BOT_TOKEN environment variable not set")
        print("Set it with: export CLAUDE_BOT_TOKEN='your_token'")
        return

    print("🤖 Discord API Testing (Organized)")
    print("=================================")
    print(f"⏰ Start Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("🔑 Token found, starting tests...")
    print()

    tester = DiscordAPITester(token)
    await tester.run_tests()


if __name__ == "__main__":
    asyncio.run(main())
