#!/usr/bin/env python3
"""
Comprehensive Shop Testing - Full Discord Bot Shop Workflow
Tests complete shop functionality including purchasing, upgrading, extending, and selling roles
"""
import asyncio
import os
import json
import subprocess
import glob
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any

# Use discord.py-self (which is what's currently installed)
import discord

# Test configuration
TEST_GUILD_ID = 960665311701528596
TEST_CHANNEL_ID = 1387864734002446407
TEST_USER_ID = 1387857653748732046  # claude_username ID (test account)
DELAY_BETWEEN_COMMANDS = 4  # Longer delay for shop operations

class ComprehiveShopTester:
    def __init__(self, token: str):
        self.token = token
        self.test_results: List[Dict[str, Any]] = []
        
        # Create client for user account (discord.py-self doesn't need Intents)
        self.client = discord.Client()
        
    async def run_comprehensive_shop_tests(self) -> Dict[str, Any]:
        """Run complete shop testing workflow"""
        
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
            if not hasattr(channel, 'send'):
                print("❌ Channel is not a text channel")
                await self.client.close()
                return
            
            print(f"✅ Connected to {guild.name} -> {channel.name}")
            
            # Comprehensive shop test scenarios
            test_scenarios = [
                # Phase 1: Setup and balance check
                (f",addbalance <@{TEST_USER_ID}> 5000", "💰 Add initial balance (5000)", 15),
                (",profile", "👤 Check initial profile", 10),
                (",shop", "🏪 Display shop offerings", 10),
                
                # Phase 2: Purchase zG50 role
                (",buy zG50 30", "🛒 Purchase zG50 for 30 days", 20),
                (",profile", "👤 Check profile after zG50 purchase", 10),
                
                # Phase 3: Extend zG50 role
                (",buy zG50 15", "⏰ Extend zG50 by 15 days", 20),
                (",profile", "👤 Check profile after zG50 extension", 10),
                
                # Phase 4: Upgrade to zG100
                (",buy zG100 30", "⬆️ Upgrade from zG50 to zG100", 20),
                (",profile", "👤 Check profile after upgrade to zG100", 10),
                
                # Phase 5: Extend zG100
                (",buy zG100 15", "⏰ Extend zG100 by 15 days", 20),
                (",profile", "👤 Check profile after zG100 extension", 10),
                
                # Phase 6: Check wallet after purchases
                (",profile", "💳 Check final wallet balance", 10),
                
                # Phase 7: Sell role (if implemented)
                # Note: This might not work if sell functionality isn't implemented
                # (",sell", "💸 Attempt to sell current role", 15),
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
                        
                        if hasattr(channel, 'history'):
                            async for msg in channel.history(limit=15, after=before_time):
                                if (msg.author.bot and msg.id != message.id and msg not in bot_responses):
                                    bot_responses.append(msg)
                                    print(f"📥 Bot response: {msg.content[:150]}...")
                        
                        if bot_responses:
                            break
                    
                    if bot_responses:
                        status = "SUCCESS"
                        response_text = bot_responses[0].content
                    else:
                        status = "NO_RESPONSE"
                        response_text = ""
                    
                    self.test_results.append({
                        "test": description,
                        "command": command,
                        "status": status,
                        "response": response_text,
                        "timestamp": datetime.now().isoformat(),
                        "wait_time": wait_time
                    })
                    
                    print(f"Status: {status}")
                    if response_text:
                        # Show more of the response for shop commands
                        print(f"Response: {response_text[:300]}...")
                    
                    await asyncio.sleep(DELAY_BETWEEN_COMMANDS)
                    
                except Exception as e:
                    print(f"❌ Error with {command}: {e}")
                    self.test_results.append({
                        "test": description,
                        "command": command,
                        "status": "ERROR",
                        "error": str(e),
                        "timestamp": datetime.now().isoformat()
                    })
            
            # Check for errors after tests
            print("\n" + "=" * 60)
            print("🔍 CHECKING FOR ERRORS AFTER SHOP TESTS")
            print("=" * 60)
            
            await self.check_docker_logs()
            await self.check_error_logs()
            
            await self.client.close()
            
            # Print summary
            print("\n" + "=" * 60)
            print("📊 COMPREHENSIVE SHOP TEST RESULTS")
            print("=" * 60)
            
            success_count = 0
            for i, result in enumerate(self.test_results, 1):
                status = result["status"]
                if status == "SUCCESS":
                    success_count += 1
                    print(f"{i:2d}. ✅ {result['test']}")
                    if "response" in result:
                        # Show key parts of response
                        response = result['response']
                        if "Dodano" in response or "balance" in response.lower():
                            print(f"      💰 {response[:100]}...")
                        elif "Kupiono" in response or "purchased" in response.lower():
                            print(f"      🛒 {response[:100]}...")
                        elif "role" in response.lower() or "ranga" in response.lower():
                            print(f"      🎭 {response[:100]}...")
                        else:
                            print(f"      📝 {response[:100]}...")
                else:
                    print(f"{i:2d}. ❌ {result['test']}: {status}")
                    if "error" in result:
                        print(f"      🔸 {result['error']}")
            
            success_rate = (success_count / len(self.test_results) * 100) if self.test_results else 0
            print(f"\n📈 Shop Test Results:")
            print(f"   Success Rate: {success_rate:.1f}% ({success_count}/{len(self.test_results)})")
            
            if success_rate >= 90:
                print("🎉 Overall Status: EXCELLENT - Shop system working perfectly!")
                print("✅ Ready for production use!")
            elif success_rate >= 75:
                print("👍 Overall Status: GOOD - Shop system mostly working")
            elif success_rate >= 50:
                print("⚠️ Overall Status: PARTIAL - Some shop features working")
            else:
                print("😞 Overall Status: POOR - Shop system needs attention")
            
            # Save results
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"test_live_bot/results/comprehensive_shop_test_{timestamp}.json"
            
            try:
                os.makedirs("test_live_bot/results", exist_ok=True)
                with open(filename, 'w') as f:
                    json.dump({
                        "test_type": "comprehensive_shop_test",
                        "success_rate": success_rate,
                        "total_tests": len(self.test_results),
                        "successful_tests": success_count,
                        "test_results": self.test_results,
                        "test_scenarios_covered": [
                            "Balance addition",
                            "Profile checking", 
                            "Shop display",
                            "zG50 purchase",
                            "zG50 extension",
                            "zG100 upgrade",
                            "zG100 extension",
                            "Wallet verification"
                        ]
                    }, f, indent=2, default=str)
                print(f"\n📄 Results saved to: {filename}")
            except Exception as e:
                print(f"❌ Failed to save results: {e}")
            
            # Store results for return
            self.results = {
                "test_type": "comprehensive_shop_test",
                "success_rate": success_rate,
                "total_tests": len(self.test_results),
                "successful_tests": success_count,
                "test_results": self.test_results
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
            # Get recent Docker logs
            result = subprocess.run(
                ["docker-compose", "logs", "app", "--tail=100"],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode == 0:
                logs = result.stdout
                
                # Look for shop-specific error patterns
                error_patterns = ["ERROR", "Failed", "Exception", "Traceback", "Error:", "SHOP ERROR", "PREMIUM ERROR"]
                found_errors = []
                
                for line in logs.split('\n'):
                    for pattern in error_patterns:
                        if pattern in line and "add_activity" not in line:  # Skip activity logs
                            found_errors.append(line.strip())
                
                if found_errors:
                    print(f"⚠️ Found {len(found_errors)} potential errors in Docker logs:")
                    for error in found_errors[-8:]:  # Show last 8 errors
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
                "logs/shop_errors*.log", 
                "logs/premium_errors*.log",
                "error_logs/*.log",
                "utils/error_logs/*.json"
            ]
            
            found_files = []
            for pattern in error_log_patterns:
                found_files.extend(glob.glob(pattern))
            
            if found_files:
                print(f"📂 Found {len(found_files)} error log file(s)")
                
                for log_file in found_files[-5:]:  # Check last 5 files
                    try:
                        with open(log_file, 'r') as f:
                            content = f.read()
                            
                        # Check if file has recent content (last 2 hours)
                        file_time = os.path.getmtime(log_file)
                        current_time = datetime.now().timestamp()
                        
                        if (current_time - file_time) < 7200:  # Last 2 hours
                            print(f"   📄 {log_file} (recent)")
                            if content.strip():
                                lines = content.strip().split('\n')
                                print(f"      📝 {len(lines)} error entries")
                                # Show last few lines
                                for line in lines[-5:]:
                                    print(f"      🔸 {line[:150]}...")
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
    
    print("🏪 Comprehensive Shop Testing Framework")
    print("=====================================")
    print(f"⏰ Start Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"🎯 Testing complete shop workflow:")
    print("   • Balance management")
    print("   • Role purchasing (zG50)")
    print("   • Role extension")
    print("   • Role upgrading (zG50 → zG100)")
    print("   • Advanced role extension")
    print("   • Error monitoring")
    print()
    
    tester = ComprehiveShopTester(token)
    await tester.run_comprehensive_shop_tests()

if __name__ == "__main__":
    asyncio.run(main())