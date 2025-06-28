#!/usr/bin/env python3
"""Test specific bot commands through MCP."""

import asyncio

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
        print(f"Command: {command}")
        print(f"{'='*60}")

        if "error" in result:
            print(f"❌ Error: {result['error']}")
        elif "responses" in result and result["responses"]:
            response = result["responses"][0]
            if "embeds" in response and response["embeds"]:
                embed = response["embeds"][0]
                print(f"✅ Title: {embed.get('title', 'No title')}")
                desc = embed.get('description', 'No description')
                if desc:
                    print(f"Description: {desc[:200]}...")
                if "fields" in embed:
                    print(f"Fields: {len(embed['fields'])}")
                    for i, field in enumerate(embed['fields'][:3]):
                        print(f"  - {field.get('name', 'No name')}: {field.get('value', '')[:50]}...")
            elif "content" in response:
                print(f"✅ Content: {response['content'][:200]}...")
            else:
                print("✅ Response received (no content)")
        else:
            print("❓ No response")


async def main():
    """Test various commands."""
    # Test help with proper alias
    await test_command("pomoc")

    # Test profile
    await test_command("profile")
    await test_command("p")  # alias

    # Test shop
    await test_command("shop")

    # Test games
    await test_command("games")
    await test_command("gry")  # alias

    # Test ranking
    await test_command("ranking")
    await test_command("top")

    # Test ping
    await test_command("ping")

    # Test voice commands
    await test_command("voicechat")

    # Test team commands
    await test_command("team")
    await test_command("team help")

if __name__ == "__main__":
    asyncio.run(main())
