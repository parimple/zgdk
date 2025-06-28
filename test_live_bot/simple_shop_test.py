#!/usr/bin/env python3
"""
Simple Shop Testing - Test shop display and basic functionality
Since shop uses interactive buttons, this test focuses on:
1. Shop command execution
2. Bot response verification
3. Error monitoring
4. Balance operations
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
TEST_USER_ID = 1387857653748732046  # claude_username ID (test account)
DELAY_BETWEEN_COMMANDS = 6  # Increased delay for better rate limiting


class SimpleShopTester:
    def __init__(self, token: str):
        self.token = token
        self.test_results: List[Dict[str, Any]] = []

        # Create client for user account (discord.py-self doesn't need Intents)
        self.client = discord.Client()

    async def run_simple_shop_tests(self) -> Dict[str, Any]:
        """Run simple shop testing workflow"""

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

            # Simple shop test scenarios
            test_scenarios = [
                # Balance and profile tests
                (f",addbalance <@{TEST_USER_ID}> 2000", "💰 Add testing balance (2000)", 15),
                (",profile", "👤 Check profile before shop", 10),
                # Shop functionality tests
                (",shop", "🏪 Display shop (main test)", 15),
                (",profile", "👤 Check profile after shop display", 10),
                # Additional balance for testing
                (f",addbalance <@{TEST_USER_ID}> 1000", "💰 Add more balance (1000)", 15),
                (",profile", "👤 Final profile check", 10),
            ]

            for command, description, wait_time in test_scenarios:
                print(f"\n🧪 {description}")
                print(f"📤 Command: {command}")

                try:
                    before_time = datetime.now(timezone.utc)
                    message = await channel.send(command)
                    print(f"✅ Command sent (ID: {message.id})")

                    # Wait for bot response
                    bot_responses = []
                    for i in range(wait_time):
                        await asyncio.sleep(1)

                        if hasattr(channel, "history"):
                            async for msg in channel.history(limit=15, after=before_time):
                                if msg.author.bot and msg.id != message.id and msg not in bot_responses:
                                    bot_responses.append(msg)
                                    print(f"📥 Bot response: {msg.content[:100]}...")

                                    # Check if message has components (buttons)
                                    if hasattr(msg, "components") and msg.components:
                                        print(f"🔘 Message has {len(msg.components)} component row(s)")
                                        for i, row in enumerate(msg.components):
                                            if hasattr(row, "children"):
                                                print(f"   Row {i+1}: {len(row.children)} button(s)")

                        if bot_responses:
                            break

                    if bot_responses:
                        status = "SUCCESS"
                        response_text = bot_responses[0].content
                        has_components = (
                            bool(bot_responses[0].components) if hasattr(bot_responses[0], "components") else False
                        )
                    else:
                        status = "NO_RESPONSE"
                        response_text = ""
                        has_components = False

                    self.test_results.append(
                        {
                            "test": description,
                            "command": command,
                            "status": status,
                            "response": response_text,
                            "has_buttons": has_components,
                            "timestamp": datetime.now().isoformat(),
                        }
                    )

                    print(f"Status: {status}")
                    if response_text:
                        print(f"Response: {response_text[:200]}...")
                    if has_components:
                        print("🔘 Message includes interactive buttons")

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

            # Check for errors after tests
            print("\n" + "=" * 60)
            print("🔍 CHECKING FOR ERRORS AFTER SHOP TESTS")
            print("=" * 60)

            await self.check_docker_logs()
            await self.check_error_logs()

            await self.client.close()

            # Print summary
            print("\n" + "=" * 60)
            print("📊 SIMPLE SHOP TEST RESULTS")
            print("=" * 60)

            success_count = 0
            button_tests = 0
            for i, result in enumerate(self.test_results, 1):
                status = result["status"]
                if status == "SUCCESS":
                    success_count += 1
                    print(f"{i:2d}. ✅ {result['test']}")

                    # Special handling for shop test
                    if "shop" in result["test"].lower() and result.get("has_buttons"):
                        button_tests += 1
                        print("      🔘 Shop displayed with interactive buttons!")
                    elif "balance" in result["test"].lower():
                        print("      💰 Balance operation completed")
                    elif "profile" in result["test"].lower():
                        print("      👤 Profile displayed successfully")

                else:
                    print(f"{i:2d}. ❌ {result['test']}: {status}")
                    if "error" in result:
                        print(f"      🔸 {result['error']}")

            success_rate = (success_count / len(self.test_results) * 100) if self.test_results else 0
            print("\n📈 Shop Test Results:")
            print(f"   Success Rate: {success_rate:.1f}% ({success_count}/{len(self.test_results)})")
            print(f"   Shop UI Tests: {button_tests} shop display(s) with buttons")

            if success_rate >= 90:
                print("🎉 Overall Status: EXCELLENT - Shop system accessible!")
            elif success_rate >= 75:
                print("👍 Overall Status: GOOD - Shop system mostly working")
            elif success_rate >= 50:
                print("⚠️ Overall Status: PARTIAL - Some shop features working")
            else:
                print("😞 Overall Status: POOR - Shop system needs attention")

            # Note about button interaction
            if button_tests > 0:
                print("\n📝 Note: Shop buttons detected! Manual testing needed:")
                print("   1. Go to Discord #cicd channel")
                print("   2. Use ,shop command")
                print("   3. Click on role buttons (zG50, zG100, etc.)")
                print("   4. Test purchase flow manually")

            # Save results
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"test_live_bot/results/simple_shop_test_{timestamp}.json"

            try:
                os.makedirs("test_live_bot/results", exist_ok=True)
                with open(filename, "w") as f:
                    json.dump(
                        {
                            "test_type": "simple_shop_test",
                            "success_rate": success_rate,
                            "total_tests": len(self.test_results),
                            "successful_tests": success_count,
                            "button_tests": button_tests,
                            "test_results": self.test_results,
                            "test_scenarios_covered": [
                                "Balance addition",
                                "Profile checking",
                                "Shop display with buttons",
                                "Error monitoring",
                            ],
                        },
                        f,
                        indent=2,
                        default=str,
                    )
                print(f"\n📄 Results saved to: {filename}")
            except Exception as e:
                print(f"❌ Failed to save results: {e}")

            # Store results for return
            self.results = {
                "test_type": "simple_shop_test",
                "success_rate": success_rate,
                "total_tests": len(self.test_results),
                "successful_tests": success_count,
                "button_tests": button_tests,
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
        print("🐳 Checking Docker logs for shop-related errors...")

        try:
            result = subprocess.run(
                ["docker-compose", "logs", "app", "--tail=50"], capture_output=True, text=True, timeout=10
            )

            if result.returncode == 0:
                logs = result.stdout

                # Look for shop-specific error patterns
                error_patterns = ["ERROR", "Failed", "Exception", "Traceback", "SHOP"]
                found_errors = []

                for line in logs.split("\n"):
                    for pattern in error_patterns:
                        if pattern in line and "add_activity" not in line:
                            found_errors.append(line.strip())

                if found_errors:
                    print(f"⚠️ Found {len(found_errors)} potential errors:")
                    for error in found_errors[-5:]:
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
            error_log_patterns = [
                "logs/error*.log",
                "logs/shop_errors*.log",
                "error_logs/*.log",
                "utils/error_logs/*.json",
            ]

            found_files = []
            for pattern in error_log_patterns:
                found_files.extend(glob.glob(pattern))

            if found_files:
                print(f"📂 Found {len(found_files)} error log file(s)")
                for log_file in found_files[-3:]:
                    try:
                        with open(log_file, "r") as f:
                            content = f.read()

                        file_time = os.path.getmtime(log_file)
                        current_time = datetime.now().timestamp()

                        if (current_time - file_time) < 3600:  # Last hour
                            print(f"   📄 {log_file} (recent)")
                            if content.strip():
                                lines = content.strip().split("\n")
                                print(f"      📝 {len(lines)} error entries")
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

    print("🏪 Simple Shop Testing Framework")
    print("===============================")
    print(f"⏰ Start Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("🎯 Testing shop display and basic functionality:")
    print("   • Balance management")
    print("   • Profile checking")
    print("   • Shop command execution")
    print("   • Button detection")
    print("   • Error monitoring")
    print()
    print("📝 Note: This test verifies shop accessibility.")
    print("   Manual button testing required for purchases.")
    print()

    tester = SimpleShopTester(token)
    await tester.run_simple_shop_tests()


if __name__ == "__main__":
    asyncio.run(main())
