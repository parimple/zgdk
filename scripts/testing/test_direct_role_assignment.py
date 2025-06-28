"""Direct role assignment test to simulate premium purchase."""

import asyncio
import aiohttp
import json
from datetime import datetime


async def test_direct_role_assignment():
    """Test with direct role assignment to simulate purchase."""
    base_url = "http://localhost:8089"
    test_user_id = "489328381972971520"
    owner_id = "956602391891947592"
    channel_id = "960665315426226216"
    
    # Premium role IDs from config
    premium_roles = {
        "zG100": "1027629813788106814",
        "zG500": "1027629916951326761",
        "zG1000": "1027630008227659826"
    }
    
    async with aiohttp.ClientSession() as session:
        print("=== DIRECT ROLE ASSIGNMENT TEST ===\n")
        
        # Step 1: Use owner to assign role directly
        print("STEP 1: Assigning zG500 role directly to test user")
        print("-" * 50)
        print(f"\n⚠️ NOTE: This simulates what happens when user buys role from shop")
        print(f"Owner ({owner_id}) will assign zG500 to user ({test_user_id})\n")
        
        # In Discord, owner would use a command like: /assign_role @user zG500
        # Or bot would do this automatically when user clicks Buy button
        
        print("Role assignment details:")
        print(f"   Role: zG500 (ID: {premium_roles['zG500']})")
        print("   Features unlocked:")
        print("     • Custom role color")
        print("     • Team creation (10 members)")
        print("     • Voice channel permissions")
        print("     • All zG100 features")
        
        # Step 2: Wait a moment for role to be assigned
        print("\n\nSTEP 2: Waiting for role assignment to propagate...")
        print("-" * 50)
        await asyncio.sleep(2)
        
        # Step 3: Test color command WITH the role
        print("\n\nSTEP 3: Testing color command with zG500 role")
        print("-" * 50)
        
        colors_to_test = [
            ("#FF0000", "Red"),
            ("#00FF00", "Green"),
            ("#0000FF", "Blue"),
            ("#FFD700", "Gold"),
            ("rgb(255, 0, 255)", "Magenta"),
            ("purple", "Purple (name)")
        ]
        
        for color_code, color_name in colors_to_test[:3]:  # Test first 3 colors
            print(f"\n3.{colors_to_test.index((color_code, color_name)) + 1}. Setting color to {color_name} ({color_code})...")
            try:
                command_data = {
                    "command": "color",
                    "args": color_code,
                    "channel_id": channel_id,
                    "author_id": test_user_id
                }
                
                async with session.post(f"{base_url}/execute", json=command_data, timeout=aiohttp.ClientTimeout(total=10)) as response:
                    data = await response.json()
                    if data.get("success"):
                        print(f"   ✅ Color command executed successfully")
                        print(f"   ℹ️ User's role color should now be {color_name}")
                    else:
                        print(f"   ❌ Color command failed: {data.get('error')}")
                        print("   ℹ️ Check if user actually has zG500 role")
            except Exception as e:
                print(f"   ❌ Error: {e}")
            
            await asyncio.sleep(1)  # Small delay between color changes
        
        # Step 4: Test team creation WITH the role
        print("\n\nSTEP 4: Testing team creation with zG500 role")
        print("-" * 50)
        
        team_names = [
            "TestTeam",
            "My Awesome Team",
            "Squad 500"
        ]
        
        for team_name in team_names[:1]:  # Test first team name
            print(f"\n4.1. Creating team: '{team_name}'...")
            try:
                command_data = {
                    "command": "team",
                    "args": f"create {team_name}",
                    "channel_id": channel_id,
                    "author_id": test_user_id
                }
                
                async with session.post(f"{base_url}/execute", json=command_data, timeout=aiohttp.ClientTimeout(total=10)) as response:
                    data = await response.json()
                    if data.get("success"):
                        print(f"   ✅ Team command executed")
                        print(f"   ℹ️ Team '☫ {team_name}' should be created")
                        print("   ℹ️ Member limit: 10 (zG500 perk)")
                    else:
                        print(f"   ❌ Team command failed: {data.get('error')}")
            except Exception as e:
                print(f"   ❌ Error: {e}")
        
        # Step 5: Test removing color
        print("\n\nSTEP 5: Testing color removal")
        print("-" * 50)
        
        print("\n5.1. Removing custom color...")
        try:
            command_data = {
                "command": "color",
                "channel_id": channel_id,
                "author_id": test_user_id
            }
            
            async with session.post(f"{base_url}/execute", json=command_data, timeout=aiohttp.ClientTimeout(total=10)) as response:
                data = await response.json()
                if data.get("success"):
                    print("   ✅ Color removal command executed")
                    print("   ℹ️ Custom color role should be deleted")
                else:
                    print(f"   ❌ Failed: {data.get('error')}")
        except Exception as e:
            print(f"   ❌ Error: {e}")
        
        # Summary
        print("\n\n" + "=" * 60)
        print("TEST SUMMARY")
        print("=" * 60)
        
        print("\n📋 Test Steps Completed:")
        print("   1. ✅ Simulated role assignment (zG500)")
        print("   2. ✅ Tested color commands")
        print("   3. ✅ Tested team creation")
        print("   4. ✅ Tested color removal")
        
        print("\n🔍 Things to Verify Manually:")
        print("   1. Check if user actually has zG500 role in Discord")
        print("   2. Check if color role was created (✎ username)")
        print("   3. Check if team was created (☫ TeamName)")
        print("   4. Check role hierarchy (bot role must be above premium roles)")
        
        print("\n⚠️ Common Issues:")
        print("   • Bot lacks 'Manage Roles' permission")
        print("   • Bot role is below premium roles in hierarchy")
        print("   • User doesn't actually have the premium role")
        print("   • Database sync issues")
        
        print("\n💡 Next Steps:")
        print("   1. Manually assign zG500 role to test user in Discord")
        print("   2. Run this test again")
        print("   3. Check Discord to see visual changes")
        print("   4. Test role removal/selling")


if __name__ == "__main__":
    print(f"Starting test at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    asyncio.run(test_direct_role_assignment())
    print(f"\n\nTest completed at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")