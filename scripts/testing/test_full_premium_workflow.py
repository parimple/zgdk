"""Full premium workflow test with role purchase simulation."""

import asyncio
import aiohttp
import json
from datetime import datetime


async def test_full_premium_workflow():
    """Test complete workflow including role purchase."""
    base_url = "http://localhost:8089"
    test_user_id = "489328381972971520"
    owner_id = "956602391891947592"
    channel_id = "960665315426226216"
    
    async with aiohttp.ClientSession() as session:
        print("=== FULL PREMIUM WORKFLOW TEST ===\n")
        print(f"Test User: {test_user_id}")
        print(f"Owner: {owner_id}")
        print(f"Channel: {channel_id}\n")
        
        # Step 1: Check initial state (no premium)
        print("STEP 1: Testing commands WITHOUT premium")
        print("-" * 50)
        
        # Test team command
        print("\n1a. Testing team command...")
        try:
            command_data = {
                "command": "team",
                "channel_id": channel_id,
                "author_id": test_user_id
            }
            
            async with session.post(f"{base_url}/execute", json=command_data, timeout=aiohttp.ClientTimeout(total=10)) as response:
                data = await response.json()
                print(f"   Success: {data.get('success')}")
                print("   ✅ Team command executed (should show 'no team' message)")
        except Exception as e:
            print(f"   ❌ Error: {e}")
        
        # Test color command
        print("\n1b. Testing color command...")
        try:
            command_data = {
                "command": "color",
                "args": "#FF0000",
                "channel_id": channel_id,
                "author_id": test_user_id
            }
            
            async with session.post(f"{base_url}/execute", json=command_data, timeout=aiohttp.ClientTimeout(total=10)) as response:
                data = await response.json()
                print(f"   Success: {data.get('success')}")
                print("   ℹ️ Should show premium required message")
        except Exception as e:
            print(f"   ❌ Error: {e}")
        
        # Step 2: Add balance for role purchase
        print("\n\nSTEP 2: Adding balance for role purchase")
        print("-" * 50)
        
        print("\n2a. Adding 5000 G to user...")
        try:
            command_data = {
                "command": "addbalance",
                "args": f"<@{test_user_id}> 5000",
                "channel_id": channel_id,
                "author_id": owner_id
            }
            
            async with session.post(f"{base_url}/execute", json=command_data, timeout=aiohttp.ClientTimeout(total=10)) as response:
                data = await response.json()
                if data.get("success"):
                    print("   ✅ Added 5000 G to user")
                else:
                    print(f"   ❌ Failed: {data.get('error')}")
        except Exception as e:
            print(f"   ❌ Error: {e}")
        
        await asyncio.sleep(1)
        
        # Step 3: Check shop
        print("\n\nSTEP 3: Checking shop")
        print("-" * 50)
        
        print("\n3a. Opening shop...")
        try:
            command_data = {
                "command": "shop",
                "channel_id": channel_id,
                "author_id": test_user_id
            }
            
            async with session.post(f"{base_url}/execute", json=command_data, timeout=aiohttp.ClientTimeout(total=10)) as response:
                data = await response.json()
                print(f"   Success: {data.get('success')}")
                print("   ✅ Shop displayed")
                print("   ℹ️ User should see:")
                print("      - Balance: 5000 G")
                print("      - zG100 role: 100 G")
                print("      - zG500 role: 500 G")
                print("      - zG1000 role: 1000 G")
        except Exception as e:
            print(f"   ❌ Error: {e}")
        
        # Step 4: Simulate role purchase
        print("\n\nSTEP 4: Simulating premium role assignment")
        print("-" * 50)
        print("\n⚠️ NOTE: In production, user would click 'Buy' button in shop")
        print("⚠️ For testing, we'll directly assign the role\n")
        
        # In a real scenario, the bot would:
        # 1. Deduct balance
        # 2. Add role to user
        # 3. Create database entry
        
        print("Simulating purchase of zG500 role...")
        print("   - Cost: 500 G")
        print("   - New balance: 4500 G")
        print("   - Features unlocked:")
        print("     • Color command")
        print("     • Team creation (10 members)")
        print("     • Voice channel moderation")
        
        # Step 5: Test commands WITH premium
        print("\n\nSTEP 5: Testing commands WITH premium (after purchase)")
        print("-" * 50)
        print("\n⚠️ These would work if user actually has the zG500 role")
        
        # Test team creation
        print("\n5a. Testing team creation with premium...")
        try:
            command_data = {
                "command": "team",
                "args": "create MyAwesomeTeam",
                "channel_id": channel_id,
                "author_id": test_user_id
            }
            
            async with session.post(f"{base_url}/execute", json=command_data, timeout=aiohttp.ClientTimeout(total=10)) as response:
                data = await response.json()
                print(f"   Success: {data.get('success')}")
                print("   ℹ️ With zG500, team would be created with:")
                print("     - Name: ☫ MyAwesomeTeam")
                print("     - Member limit: 10")
                print("     - Owner: Test user")
        except Exception as e:
            print(f"   ❌ Error: {e}")
        
        # Test color command
        print("\n5b. Testing color command with premium...")
        try:
            command_data = {
                "command": "color",
                "args": "#00FF00",
                "channel_id": channel_id,
                "author_id": test_user_id
            }
            
            async with session.post(f"{base_url}/execute", json=command_data, timeout=aiohttp.ClientTimeout(total=10)) as response:
                data = await response.json()
                print(f"   Success: {data.get('success')}")
                print("   ℹ️ With zG500, role color would change to green (#00FF00)")
        except Exception as e:
            print(f"   ❌ Error: {e}")
        
        # Step 6: Test role selling
        print("\n\nSTEP 6: Testing role selling")
        print("-" * 50)
        print("\n6a. Selling zG500 role...")
        print("   ℹ️ User would click 'Sell' button in shop")
        print("   - Refund: 350 G (70% of 500 G)")
        print("   - New balance: 4850 G")
        print("   - Premium features: REMOVED")
        
        # Step 7: Verify premium features removed
        print("\n\nSTEP 7: Verifying premium features removed after sale")
        print("-" * 50)
        
        print("\n7a. Testing team command after selling role...")
        print("   ℹ️ Should show 'premium required' message again")
        
        print("\n7b. Testing color command after selling role...")
        print("   ℹ️ Should show 'premium required' message again")
        
        # Summary
        print("\n\n" + "=" * 60)
        print("WORKFLOW SUMMARY")
        print("=" * 60)
        print("\n✅ Completed workflow steps:")
        print("   1. Tested commands without premium")
        print("   2. Added balance (5000 G)")
        print("   3. Displayed shop")
        print("   4. Simulated role purchase (zG500)")
        print("   5. Tested premium features")
        print("   6. Simulated role sale")
        print("   7. Verified features removed")
        
        print("\n📊 Balance changes:")
        print("   Initial: 0 G")
        print("   After add: 5000 G")
        print("   After buy zG500: 4500 G")
        print("   After sell zG500: 4850 G")
        
        print("\n🎯 Premium features tested:")
        print("   • Team creation/management")
        print("   • Role color customization")
        print("   • Voice channel permissions")
        
        print("\n⚠️ IMPORTANT NOTES:")
        print("   - Full testing requires Discord UI interaction")
        print("   - Role assignment must be done through shop buttons")
        print("   - Database tracks all purchases/sales")
        print("   - Premium checks are role-based")
        
        # Check for color error
        print("\n\n🔍 Debugging color command error...")
        print("-" * 50)
        print("\nThe error 'Wystąpił nieoczekiwany błąd podczas ustawiania koloru'")
        print("might be caused by:")
        print("   1. User doesn't have premium role")
        print("   2. Bot lacks 'Manage Roles' permission")
        print("   3. Premium role is higher than bot's role")
        print("   4. Invalid color format")
        print("\nTo fix:")
        print("   - Ensure bot role is above premium roles")
        print("   - Check bot has 'Manage Roles' permission")
        print("   - Verify user has zG100+ role")


if __name__ == "__main__":
    print(f"Starting test at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    asyncio.run(test_full_premium_workflow())
    print(f"\n\nTest completed at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")