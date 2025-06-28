"""Test premium system after fixing role IDs."""

import asyncio
from datetime import datetime

import aiohttp


async def test_premium_fixed():
    """Test premium features after fix."""
    base_url = "http://localhost:8089"
    test_user_id = "489328381972971520"
    channel_id = "1387864734002446407"

    # Test configuration
    test_scenarios = [
        {
            "name": "Color Command Test",
            "commands": [
                {"cmd": "color", "args": "#FF0000", "desc": "Set red color"},
                {"cmd": "color", "args": "blue", "desc": "Set blue color"},
                {"cmd": "color", "args": "", "desc": "Remove color"},
            ]
        },
        {
            "name": "Team Command Test",
            "commands": [
                {"cmd": "team", "args": "", "desc": "Check team status"},
                {"cmd": "team", "args": "create TestTeam2025", "desc": "Create team"},
                {"cmd": "team", "args": "delete", "desc": "Delete team"},
            ]
        },
        {
            "name": "Shop Command Test",
            "commands": [
                {"cmd": "shop", "args": "", "desc": "Open shop"},
                {"cmd": "profile", "args": "", "desc": "Check profile"},
            ]
        }
    ]

    async with aiohttp.ClientSession() as session:
        print("🧪 PREMIUM SYSTEM TEST - POST FIX")
        print("=" * 60)
        print(f"Test User: {test_user_id}")
        print(f"Channel: {channel_id}")
        print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("\n📝 Note: Check Discord channel for actual bot responses!")
        print("Bot should now show correct role names instead of '@nieznana rola'\n")

        for scenario in test_scenarios:
            print(f"\n{'=' * 60}")
            print(f"📋 {scenario['name']}")
            print(f"{'=' * 60}")

            for i, test in enumerate(scenario['commands'], 1):
                print(f"\n{i}. {test['desc']}")
                print(f"   Command: ,{test['cmd']} {test['args']}")

                command_data = {
                    "command": test['cmd'],
                    "channel_id": channel_id,
                    "author_id": test_user_id
                }

                if test['args']:
                    command_data["args"] = test['args']

                try:
                    async with session.post(
                        f"{base_url}/execute",
                        json=command_data,
                        timeout=aiohttp.ClientTimeout(total=10)
                    ) as response:
                        data = await response.json()
                        status = "✅ Sent" if data.get("success") else "❌ Failed"
                        print(f"   Status: {status}")

                        if not data.get("success"):
                            print(f"   Error: {data.get('error')}")

                except Exception as e:
                    print(f"   ❌ Exception: {e}")

                await asyncio.sleep(1)  # Delay between commands

        print("\n\n" + "=" * 60)
        print("🔍 EXPECTED DISCORD RESPONSES")
        print("=" * 60)
        print("\nFor user WITHOUT premium roles:")
        print("1. Color command → '❌ Nie masz uprawnień' + proper role mentions")
        print("2. Team create → '❌ Brak wymaganych uprawnień' + proper role mentions")
        print("3. Team info → 'Nie masz teamu' message")
        print("4. Shop → Should display with correct role names and IDs")
        print("\nFor user WITH premium roles:")
        print("1. Color command → '✅ Twój kolor roli został ustawiony'")
        print("2. Team create → '✅ Team został utworzony'")
        print("3. Premium features should work correctly")

        print("\n💡 VERIFICATION CHECKLIST:")
        print("□ No more '@nieznana rola' in messages")
        print("□ Roles show as: @zG50, @zG100, @zG500, @zG1000")
        print("□ Shop displays correct prices and role names")
        print("□ Premium checks work correctly")

        print("\n🎯 ROLE ID MAPPING:")
        print("zG50  → 1306588378829164565")
        print("zG100 → 1306588380141846528")
        print("zG500 → 1317129475271557221")
        print("zG1000 → 1321432424101576705")


if __name__ == "__main__":
    asyncio.run(test_premium_fixed())
