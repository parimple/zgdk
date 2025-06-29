"""Debug premium system configuration."""

import asyncio
from datetime import datetime

import aiohttp


async def test_debug_premium():
    """Debug test to understand premium system."""
    base_url = "http://localhost:8089"
    test_user_id = "489328381972971520"
    _owner_id = "489328381972971520"
    channel_id = "1387864734002446407"

    async with aiohttp.ClientSession() as session:
        print("🔍 PREMIUM SYSTEM DEBUG TEST")
        print("=" * 60)
        print(f"Test User ID: {test_user_id}")
        print(f"Channel ID: {channel_id}")
        print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

        # Test different scenarios
        test_cases = [
            {
                "description": "1. Testing as user without premium",
                "command": "team",
                "args": "create TestTeam",
                "author_id": test_user_id,
                "expected": "Should fail - no premium role",
            },
            {
                "description": "2. Testing team info command",
                "command": "team",
                "args": "",
                "author_id": test_user_id,
                "expected": "Should show 'no team' message",
            },
            {
                "description": "3. Testing color command",
                "command": "color",
                "args": "#FF0000",
                "author_id": test_user_id,
                "expected": "Should fail - no premium role",
            },
            {
                "description": "4. Testing profile command",
                "command": "profile",
                "args": "",
                "author_id": test_user_id,
                "expected": "Should work for everyone",
            },
            {
                "description": "5. Testing balance command",
                "command": "balance",
                "args": "",
                "author_id": test_user_id,
                "expected": "Should show current balance",
            },
            {
                "description": "6. Testing voice mod command",
                "command": "mod",
                "args": f"<@{test_user_id}>",
                "author_id": test_user_id,
                "expected": "Should fail - requires premium",
            },
        ]

        for test in test_cases:
            print(f"\n{'=' * 60}")
            print(f"🧪 {test['description']}")
            print(f"{'=' * 60}")
            print(f"Command: ,{test['command']} {test['args']}")
            print(f"Expected: {test['expected']}")

            command_data = {"command": test["command"], "channel_id": channel_id, "author_id": test["author_id"]}

            if test["args"]:
                command_data["args"] = test["args"]

            try:
                async with session.post(
                    f"{base_url}/execute", json=command_data, timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    data = await response.json()
                    print(f"Result: {'✅ Command accepted' if data.get('success') else '❌ Command failed'}")

                    if data.get("error"):
                        print(f"Error: {data['error']}")

            except Exception as e:
                print(f"❌ Exception: {e}")

            await asyncio.sleep(0.5)

        print("\n" + "=" * 60)
        print("📊 ANALYSIS")
        print("=" * 60)
        print("\nBased on Discord messages, the bot IS working correctly:")
        print("1. Team commands require premium roles (zG100, zG500, zG1000)")
        print("2. Color commands require premium roles")
        print("3. Voice mod commands require premium roles")
        print("\nThe issue: API responses are not being captured")
        print("This is because the bot sends messages to the real Discord channel")
        print("But the API wrapper doesn't forward those messages back")

        print("\n🔧 RECOMMENDATIONS:")
        print("1. Check Discord channel for actual bot messages")
        print("2. Verify user doesn't have any premium roles")
        print("3. Test with a user that has zG500 role to see success case")
        print("4. The '@nieznana rola' suggests role configuration might need checking")


if __name__ == "__main__":
    asyncio.run(test_debug_premium())
