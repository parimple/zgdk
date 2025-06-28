#!/usr/bin/env python3
"""Test moderation commands through MCP."""

import asyncio
import json

import aiohttp


async def test_command(command: str, params: dict = None):
    """Test a single command."""
    async with aiohttp.ClientSession() as session:
        payload = {
            "command": command,
            "user_id": "956602391891947592"
        }
        if params:
            payload.update(params)
            
        async with session.post("http://localhost:8090/execute", json=payload) as resp:
            result = await resp.json()
            
        print(f"\n{'='*60}")
        print(f"Command: {command} {params.get('args', []) if params else []}")
        print(f"{'='*60}")
        
        if "error" in result:
            print(f"❌ Error: {result['error']}")
        elif "responses" in result and result["responses"]:
            response = result["responses"][0]
            if "embeds" in response and response["embeds"]:
                embed = response["embeds"][0]
                print(f"✅ Embed Title: {embed.get('title', 'No title')}")
                if embed.get('description'):
                    print(f"Description: {embed['description'][:100]}...")
            elif "content" in response:
                print(f"✅ Content: {response['content'][:200]}...")
            else:
                print("✅ Response received")
        else:
            print("❓ No response")

async def main():
    """Test moderation commands."""
    # Timeout commands
    await test_command("timeout")
    await test_command("untimeout")
    
    # Mute commands  
    await test_command("mute")
    await test_command("unmute")
    
    # Nickname moderation
    await test_command("nick")
    await test_command("mutenick")
    
    # Clear commands
    await test_command("clear", {"args": ["10"]})
    await test_command("clearall")
    
    # Team commands
    await test_command("team", {"args": ["info"]})
    await test_command("team", {"args": ["create", "TestTeam"]})
    
    # Color commands
    await test_command("color")
    await test_command("kolor")

if __name__ == "__main__":
    asyncio.run(main())