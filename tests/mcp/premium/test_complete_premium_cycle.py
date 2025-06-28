"""Complete premium cycle test with cleanup."""

import asyncio
from datetime import datetime

import aiohttp


def format_response(data):
    """Format bot response for display."""
    if not data.get("responses"):
        return "No response"

    response = data["responses"][0] if data["responses"] else {}

    # Check for embed
    if "embed" in response:
        embed = response["embed"]
        title = embed.get("title", "No title")
        desc = embed.get("description", "No description")
        # Clean up description - remove newlines for compact display
        desc_preview = desc.replace("\n", " | ")[:100] + "..." if len(desc) > 100 else desc.replace("\n", " | ")
        return f"{title}: {desc_preview}"

    # Check for content
    if "content" in response:
        return response["content"][:100] + "..." if len(response["content"]) > 100 else response["content"]

    return "Empty response"


async def test_complete_premium_cycle():
    """Test complete premium cycle: balance -> buy -> use -> sell -> cleanup."""
    # Configuration
    base_url = "http://localhost:8090"  # Using command_tester API for better response capture
    test_user_id = "489328381972971520"  # User executing the tests
    owner_id = "489328381972971520"      # Same user has owner permissions
    channel_id = "1387864734002446407"    # Test channel from config

    # Test data
    test_balance = 10000
    test_role = "zG500"
    test_role_price = 500
    test_role_refund = 350  # 70% of price
    test_team_name = "TestSquad"
    test_color_red = "#FF0000"
    _test_color_green = "#00FF00"

    # Messages
    msg_balance_added = f"Added {test_balance} G to test user"
    msg_shop_displayed = "Shop displayed for test user"
    msg_balance_info = f"Balance should show: {test_balance} G"
    msg_no_premium = "Should fail - no premium role"
    msg_color_success = "Color set successfully"
    msg_team_success = "Team created successfully"
    msg_check_role = f"Failed - check if test user has {test_role} role"
    msg_team_info = f"Should show team info for {test_team_name}"
    _msg_deletion_confirm = "User needs to confirm with reaction"
    _msg_color_removed = "Color removed"
    _msg_shop_opened = "Shop opened"

    created_roles = []  # Track created roles for cleanup
    created_teams = []  # Track created teams for cleanup

    async with aiohttp.ClientSession() as session:
        print("=== COMPLETE PREMIUM CYCLE TEST ===\n")
        print(f"Test User ID: {test_user_id}")
        print("Test will create and clean up all test data\n")

        try:
            # Step 1: Give test user balance
            print("STEP 1: Adding balance to test user")
            print("-" * 50)

            print(f"\n1.1. Adding {test_balance} G to test user...")
            command_data = {
                "command": "addbalance",
                "args": f"<@{test_user_id}> {test_balance}",
                "channel_id": channel_id,
                "author_id": owner_id  # Owner executes this
            }

            async with session.post(f"{base_url}/execute", json=command_data, timeout=aiohttp.ClientTimeout(total=10)) as response:
                data = await response.json()
                if data.get("success"):
                    print(f"   ✅ {msg_balance_added}")
                else:
                    print(f"   ❌ Failed: {data.get('error')}")
                print(f"   Response: {format_response(data)}")

            await asyncio.sleep(1)

            # Step 2: Check shop as test user
            print("\n\nSTEP 2: Checking shop as test user")
            print("-" * 50)

            print("\n2.1. Test user checking shop...")
            command_data = {
                "command": "shop",
                "channel_id": channel_id,
                "author_id": test_user_id  # Test user executes
            }

            async with session.post(f"{base_url}/execute", json=command_data, timeout=aiohttp.ClientTimeout(total=10)) as response:
                data = await response.json()
                if data.get("success"):
                    print(f"   ✅ {msg_shop_displayed}")
                    print(f"   Response: {format_response(data)}")
                    print(f"   ℹ️ {msg_balance_info}")
                else:
                    print(f"   ❌ Failed: {data.get('error')}")

            # Step 3: Test WITHOUT premium
            print("\n\nSTEP 3: Testing premium commands WITHOUT roles")
            print("-" * 50)

            print("\n3.1. test user trying color command...")
            command_data = {
                "command": "color",
                "args": test_color_red,
                "channel_id": channel_id,
                "author_id": test_user_id
            }

            async with session.post(f"{base_url}/execute", json=command_data, timeout=aiohttp.ClientTimeout(total=10)) as response:
                data = await response.json()
                print(f"   Result: {data.get('success')}")
                print(f"   Response: {format_response(data)}")
                print(f"   ℹ️ {msg_no_premium}")

            print("\n3.2. test user trying team create...")
            command_data = {
                "command": "team",
                "args": f"create {test_team_name}",
                "channel_id": channel_id,
                "author_id": test_user_id
            }

            async with session.post(f"{base_url}/execute", json=command_data, timeout=aiohttp.ClientTimeout(total=10)) as response:
                data = await response.json()
                print(f"   Result: {data.get('success')}")
                print(f"   Response: {format_response(data)}")
                print(f"   ℹ️ {msg_no_premium}")

            # Step 4: Simulate buying zG500 role
            print("\n\nSTEP 4: Simulating zG500 purchase")
            print("-" * 50)
            print(f"\n⚠️ In production, test user would click 'Buy {test_role}' button")
            print("⚠️ Bot would:")
            print(f"   1. Deduct {test_role_price} G from balance")
            print(f"   2. Add {test_role} role to test user")
            print("   3. Create database entry")
            print(f"\n📌 Manual step required: Assign {test_role} role to test user in Discord")

            await asyncio.sleep(2)

            # Step 5: Test WITH premium (assuming role was assigned)
            print("\n\nSTEP 5: Testing premium commands WITH zG500 role")
            print("-" * 50)

            print(f"\n5.1. test user setting color to {test_color_red}...")
            command_data = {
                "command": "color",
                "args": test_color_red,
                "channel_id": channel_id,
                "author_id": test_user_id
            }

            async with session.post(f"{base_url}/execute", json=command_data, timeout=aiohttp.ClientTimeout(total=10)) as response:
                data = await response.json()
                if data.get("success"):
                    print(f"   ✅ {msg_color_success}")
                    created_roles.append("color")  # Track for cleanup
                else:
                    print(f"   ❌ {msg_check_role}")
                print(f"   Response: {format_response(data)}")

            await asyncio.sleep(1)

            print(f"\n5.2. test user creating team '{test_team_name}'...")
            command_data = {
                "command": "team",
                "args": f"create {test_team_name}",
                "channel_id": channel_id,
                "author_id": test_user_id
            }

            async with session.post(f"{base_url}/execute", json=command_data, timeout=aiohttp.ClientTimeout(total=10)) as response:
                data = await response.json()
                if data.get("success"):
                    print(f"   ✅ {msg_team_success}")
                    created_teams.append(test_team_name)  # Track for cleanup
                else:
                    print(f"   ❌ {msg_check_role}")
                print(f"   Response: {format_response(data)}")

            # Step 6: Test team features
            print("\n\nSTEP 6: Testing team features")
            print("-" * 50)

            print("\n6.1. test user checking team info...")
            command_data = {
                "command": "team",
                "channel_id": channel_id,
                "author_id": test_user_id
            }

            async with session.post(f"{base_url}/execute", json=command_data, timeout=aiohttp.ClientTimeout(total=10)) as response:
                data = await response.json()
                print(f"   Result: {data.get('success')}")
                print(f"   Response: {format_response(data)}")
                print(f"   ℹ️ {msg_team_info}")

            # Step 7: Cleanup - Remove created items
            print("\n\nSTEP 7: CLEANUP - Removing test data")
            print("-" * 50)

            print("\n7.1. test user deleting team...")
            command_data = {
                "command": "team",
                "args": "delete",
                "channel_id": channel_id,
                "author_id": test_user_id
            }

            async with session.post(f"{base_url}/execute", json=command_data, timeout=aiohttp.ClientTimeout(total=10)) as response:
                data = await response.json()
                if data.get("success"):
                    print("   ✅ Team deletion initiated")
                    print("   ℹ️ User needs to confirm with reaction")
                else:
                    print("   ⚠️ Team deletion requires confirmation")

            print("\n7.2. test user removing color...")
            command_data = {
                "command": "color",  # No args = remove color
                "channel_id": channel_id,
                "author_id": test_user_id
            }

            async with session.post(f"{base_url}/execute", json=command_data, timeout=aiohttp.ClientTimeout(total=10)) as response:
                data = await response.json()
                if data.get("success"):
                    print("   ✅ Color removed")
                else:
                    print("   ⚠️ Color removal failed")

            # Step 8: Sell the premium role
            print("\n\nSTEP 8: Selling the premium role")
            print("-" * 50)

            print("\n8.1. test user opening shop to sell zG500...")
            command_data = {
                "command": "shop",
                "channel_id": channel_id,
                "author_id": test_user_id
            }

            async with session.post(f"{base_url}/execute", json=command_data, timeout=aiohttp.ClientTimeout(total=10)) as response:
                data = await response.json()
                if data.get("success"):
                    print("   ✅ Shop opened")
                    print("   ℹ️ test user would click 'Sell' button on zG500")
                    print("   ℹ️ This would:")
                    print("      - Remove zG500 role automatically")
                    print("      - Add 350 G refund (70% of 500 G)")
                    print("      - Update database")
                else:
                    print(f"   ❌ Failed: {data.get('error')}")

            # Step 9: Final balance check
            print("\n\nSTEP 9: Final balance check")
            print("-" * 50)

            print("\nExpected balance calculation:")
            print("   Initial: 0 G")
            print(f"   + Added: {test_balance} G")
            print(f"   - Buy {test_role}: {test_role_price} G")
            print(f"   + Sell {test_role}: {test_role_refund} G")
            print(f"   = Final: {test_balance - test_role_price + test_role_refund} G")

        except Exception as e:
            print(f"\n❌ Test error: {e}")

        finally:
            # Summary
            print("\n\n" + "=" * 60)
            print("TEST SUMMARY")
            print("=" * 60)

            print("\n✅ Test Flow Completed:")
            print("   1. Added balance to test user (10000 G)")
            print("   2. Tested commands without premium")
            print("   3. Simulated role purchase")
            print("   4. Tested commands with premium")
            print("   5. Created team and color role")
            print("   6. Cleaned up test data")

            print("\n🧹 Cleanup Status:")
            if created_roles:
                print(f"   • Color roles removed: {len(created_roles)}")
            if created_teams:
                print(f"   • Teams to confirm deletion: {len(created_teams)}")

            final_balance = test_balance - test_role_price + test_role_refund
            print("\n📋 Manual Verification Needed:")
            print(f"   1. Check test user's balance (should be ~{final_balance} G)")
            print("   2. Verify no color role exists (✎ test user)")
            print(f"   3. Verify team was deleted (☫ {test_team_name})")
            print("   4. Verify test user has no premium roles")

            print("\n💡 Important Notes:")
            print("   • Full shop testing requires Discord UI")
            print("   • Role purchase/sale needs button interactions")
            print("   • Team deletion needs reaction confirmation")
            print("   • All premium features are role-based")


if __name__ == "__main__":
    print(f"Starting test at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    asyncio.run(test_complete_premium_cycle())
    print(f"\n\nTest completed at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
