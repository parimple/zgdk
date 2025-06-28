#!/usr/bin/env python3
"""Test various bot commands through MCP."""

import asyncio
import aiohttp
import json

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
                print(f"Title: {embed.get('title', 'No title')}")
                print(f"Description: {embed.get('description', 'No description')[:200]}...")
                if "fields" in embed:
                    print(f"Fields: {len(embed['fields'])}")
            elif "content" in response:
                print(f"Content: {response['content'][:200]}...")
        else:
            print("❓ No response")

async def main():
    """Test multiple commands."""
    commands = [
        # Basic commands
        ("help", {}),
        ("ping", {}),
        ("info", {}),
        
        # User info commands
        ("profile", {}),
        ("balance", {}),
        ("top", {}),
        
        # Shop commands  
        ("shop", {}),
        ("daily", {}),
        
        # Voice commands
        ("voice", {}),
        
        # Team commands
        ("team", {}),
    ]
    
    for cmd, params in commands:
        try:
            await test_command(cmd, params)
            await asyncio.sleep(1)  # Avoid rate limiting
        except Exception as e:
            print(f"❌ Failed to test {cmd}: {e}")

if __name__ == "__main__":
    asyncio.run(main())