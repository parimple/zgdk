#!/usr/bin/env python3
"""Test voice commands through MCP."""

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
        print(f"Command: {command} {params if params else ''}")
        print(f"{'='*60}")

        if "error" in result:
            print(f"❌ Error: {result['error']}")
        elif "responses" in result and result["responses"]:
            response = result["responses"][0]
            if "embeds" in response and response["embeds"]:
                embed = response["embeds"][0]
                print("✅ Embed received")
                if embed.get('title'):
                    print(f"Title: {embed['title']}")
                if embed.get('description'):
                    print(f"Description: {embed['description'][:100]}...")
            elif "content" in response:
                print(f"✅ Content: {response['content'][:200]}...")
            else:
                print("✅ Response received (no content)")
        else:
            print("❓ No response")


async def main():
    """Test voice commands."""
    # Voice channel commands
    await test_command("voicechat")
    await test_command("voicechat", {"args": ["rename", "Test Channel"]})

    # Permission commands
    await test_command("speak")
    await test_command("view")
    await test_command("connect")
    await test_command("text")
    await test_command("live")

    # Channel management
    await test_command("limit", {"args": ["5"]})
    await test_command("reset")

    # Moderator commands
    await test_command("mod")
    await test_command("autokick")

if __name__ == "__main__":
    asyncio.run(main())
