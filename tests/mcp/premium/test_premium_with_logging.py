"""Test premium features with detailed logging."""

import asyncio
import json
from datetime import datetime

import aiohttp


def format_embed(embed_data):
    """Format embed data for readable display."""
    if not embed_data:
        return "No embed"
    
    title = embed_data.get("title", "")
    desc = embed_data.get("description", "")
    color = embed_data.get("color", 0)
    
    # Format output
    output = []
    if title:
        output.append(f"📋 {title}")
    if desc:
        # Show first few lines of description
        lines = desc.split("\n")
        for i, line in enumerate(lines[:5]):  # Show first 5 lines
            output.append(f"   {line}")
        if len(lines) > 5:
            output.append(f"   ... ({len(lines) - 5} more lines)")
    
    return "\n".join(output)


async def execute_and_log(session, base_url, command_data, description):
    """Execute command and log the full response."""
    print(f"\n{'=' * 60}")
    print(f"🔧 {description}")
    print(f"{'=' * 60}")
    print(f"Command: {command_data.get('command')}")
    print(f"Args: {command_data.get('args', 'none')}")
    print(f"User: {command_data.get('author_id')}")
    
    try:
        async with session.post(
            f"{base_url}/execute", 
            json=command_data, 
            timeout=aiohttp.ClientTimeout(total=10)
        ) as response:
            data = await response.json()
            
            print(f"\nStatus: {'✅ Success' if data.get('success') else '❌ Failed'}")
            
            if data.get("error"):
                print(f"Error: {data['error']}")
            
            # Log all responses
            if data.get("responses"):
                for i, resp in enumerate(data["responses"]):
                    print(f"\nResponse {i + 1}:")
                    if resp.get("content"):
                        print(f"Content: {resp['content']}")
                    if resp.get("embeds"):
                        for embed in resp["embeds"]:
                            print(format_embed(embed))
                    elif resp.get("embed"):
                        print(format_embed(resp["embed"]))
            else:
                print("\n⚠️ No responses captured")
                
            return data
            
    except Exception as e:
        print(f"\n❌ Exception: {e}")
        return {"success": False, "error": str(e)}


async def test_premium_workflow():
    """Test premium workflow with detailed logging."""
    # Configuration
    base_url = "http://localhost:8089"  # Back to original API
    test_user_id = "489328381972971520"
    channel_id = "1387864734002446407"
    
    async with aiohttp.ClientSession() as session:
        print("🚀 PREMIUM FEATURE TEST WITH DETAILED LOGGING")
        print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        
        # Test 1: Color command without premium
        await execute_and_log(
            session, base_url,
            {
                "command": "color",
                "args": "#FF0000",
                "channel_id": channel_id,
                "author_id": test_user_id
            },
            "Testing COLOR command (expecting premium requirement)"
        )
        
        await asyncio.sleep(1)
        
        # Test 2: Team create without premium
        await execute_and_log(
            session, base_url,
            {
                "command": "team",
                "args": "create TestTeam",
                "channel_id": channel_id,
                "author_id": test_user_id
            },
            "Testing TEAM CREATE command (expecting premium requirement)"
        )
        
        await asyncio.sleep(1)
        
        # Test 3: Check team status
        await execute_and_log(
            session, base_url,
            {
                "command": "team",
                "channel_id": channel_id,
                "author_id": test_user_id
            },
            "Testing TEAM command (check current status)"
        )
        
        await asyncio.sleep(1)
        
        # Test 4: Shop command
        await execute_and_log(
            session, base_url,
            {
                "command": "shop",
                "channel_id": channel_id,
                "author_id": test_user_id
            },
            "Testing SHOP command"
        )
        
        print("\n" + "=" * 60)
        print("📊 TEST SUMMARY")
        print("=" * 60)
        print("✅ All commands executed")
        print("📝 Check Discord channel for actual messages")
        print("🔍 Review responses above for premium requirements")


if __name__ == "__main__":
    asyncio.run(test_premium_workflow())