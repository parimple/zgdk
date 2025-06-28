"""Live integration test using bot API."""

import asyncio
import aiohttp
import json


async def test_bot_api():
    """Test bot API endpoints."""
    base_url = "http://localhost:8089"
    
    async with aiohttp.ClientSession() as session:
        # Test 1: Check status
        print("1. Testing /status endpoint...")
        try:
            async with session.get(f"{base_url}/status", timeout=aiohttp.ClientTimeout(total=5)) as response:
                data = await response.json()
                print(f"   Status: {data}")
                assert data.get("status") == "online", "Bot not online"
                print("   ✅ Bot is connected")
        except Exception as e:
            print(f"   ❌ Error: {e}")
            return
        
        # Test 2: Execute shop command
        print("\n2. Testing shop command...")
        try:
            command_data = {
                "command": "shop",
                "channel_id": "960665315426226216",
                "author_id": "489328381972971520"
            }
            
            async with session.post(
                f"{base_url}/execute",
                json=command_data,
                timeout=aiohttp.ClientTimeout(total=10)
            ) as response:
                data = await response.json()
                print(f"   Response: {json.dumps(data, indent=2)}")
                
                if data.get("success"):
                    print("   ✅ Shop command executed successfully")
                else:
                    print(f"   ❌ Shop command failed: {data.get('error')}")
        except Exception as e:
            print(f"   ❌ Error executing shop: {e}")
        
        # Test 3: Execute addbalance command
        print("\n3. Testing addbalance command...")
        try:
            command_data = {
                "command": "addbalance",
                "args": "<@489328381972971520> 1000",
                "channel_id": "960665315426226216", 
                "author_id": "956602391891947592"  # Owner ID
            }
            
            async with session.post(
                f"{base_url}/execute",
                json=command_data,
                timeout=aiohttp.ClientTimeout(total=10)
            ) as response:
                data = await response.json()
                print(f"   Response: {json.dumps(data, indent=2)}")
                
                if data.get("success"):
                    print("   ✅ Addbalance command executed successfully")
                else:
                    print(f"   ❌ Addbalance command failed: {data.get('error')}")
        except Exception as e:
            print(f"   ❌ Error executing addbalance: {e}")
        
        # Test 4: Test voice commands
        print("\n4. Testing voice commands...")
        try:
            # First, simulate joining a voice channel
            command_data = {
                "command": "speak",
                "args": "@everyone -",
                "channel_id": "960665315426226216",
                "author_id": "489328381972971520",
                "voice_channel_id": "960665316894568459"  # Simulate being in voice
            }
            
            async with session.post(
                f"{base_url}/execute",
                json=command_data,
                timeout=aiohttp.ClientTimeout(total=10)
            ) as response:
                data = await response.json()
                print(f"   Response: {json.dumps(data, indent=2)}")
                
                if "nie jesteś na kanale głosowym" in str(data):
                    print("   ✅ Voice command correctly requires voice channel")
                elif data.get("success"):
                    print("   ✅ Voice command executed")
                else:
                    print(f"   ⚠️  Voice command result: {data}")
        except Exception as e:
            print(f"   ❌ Error executing voice command: {e}")
        
        # Test 5: Test team commands
        print("\n5. Testing team commands...")
        try:
            command_data = {
                "command": "team",
                "channel_id": "960665315426226216",
                "author_id": "489328381972971520"
            }
            
            async with session.post(
                f"{base_url}/execute",
                json=command_data,
                timeout=aiohttp.ClientTimeout(total=10)
            ) as response:
                data = await response.json()
                print(f"   Response: {json.dumps(data, indent=2)}")
                
                if data.get("success") or "premium" in str(data).lower():
                    print("   ✅ Team command executed (may require premium)")
                else:
                    print(f"   ❌ Team command failed: {data.get('error')}")
        except Exception as e:
            print(f"   ❌ Error executing team command: {e}")


if __name__ == "__main__":
    print("Starting live integration tests...\n")
    asyncio.run(test_bot_api())
    print("\nTests completed!")