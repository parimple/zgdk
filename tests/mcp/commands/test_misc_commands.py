#!/usr/bin/env python3
"""Test miscellaneous commands through MCP."""

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
        print(f"Command: /{command}")
        print(f"{'='*60}")
        
        if "error" in result:
            print(f"❌ Error: {result['error']}")
        elif "responses" in result and result["responses"]:
            response = result["responses"][0]
            if "embeds" in response and response["embeds"]:
                embed = response["embeds"][0]
                print(f"✅ Title: {embed.get('title', 'No title')}")
                if embed.get('description'):
                    print(f"Description: {embed['description'][:150]}...")
                if embed.get('fields'):
                    print(f"Fields: {len(embed['fields'])}")
            elif "content" in response:
                print(f"✅ Content: {response['content'][:200]}...")
            else:
                print("✅ Response received")
        else:
            print("❓ No response")

async def main():
    """Test various commands."""
    # Giveaway commands
    await test_command("giveaway")
    
    # Owner commands
    await test_command("owner")
    
    # Bypass info
    await test_command("bypass")
    await test_command("t")
    
    # Stats command
    await test_command("stats")
    
    # Server info
    await test_command("serverinfo")
    await test_command("serwer")
    
    # Try some aliases
    await test_command("profil")  # Polish alias for profile
    await test_command("sklep")   # Polish alias for shop

if __name__ == "__main__":
    asyncio.run(main())