#!/usr/bin/env python3
"""Test commands through MCP."""

import asyncio
import sys

import aiohttp


async def test_command(command, args=""):
    """Test a single command through API."""
    async with aiohttp.ClientSession() as session:
        async with session.post("http://localhost:8090/execute", json={"command": command, "args": args}) as resp:
            result = await resp.json()
            print(f"\n{'='*60}")
            print(f"Command: ,{command} {args}")
            print(f"{'='*60}")

            if result.get("success"):
                for response in result.get("responses", []):
                    if response.get("content"):
                        print(f"Content: {response['content']}")
                    if response.get("embeds"):
                        for embed in response["embeds"]:
                            print(f"\nEmbed Title: {embed.get('title', 'No title')}")
                            print(f"Color: {embed.get('color', 'No color')}")
                            if embed.get("author"):
                                print(f"Author Name: {embed['author'].get('name', 'No name')}")
                                print(f"Author Icon: {embed['author'].get('icon_url', 'No icon')[:50]}...")
                            else:
                                print("Author: Not set")
                            desc = embed.get("description", "No description")
                            print(f"Description: {desc}")
                            print(f"Fields: {len(embed.get('fields', []))} fields")
                            if embed.get("footer"):
                                print(f"Footer: {embed['footer'].get('text', 'No text')}")
            else:
                print("Error: Command failed")

            return result


async def main():
    """Test all ranking commands."""
    if len(sys.argv) > 1:
        # Single command mode
        command = sys.argv[1]
        args = " ".join(sys.argv[2:]) if len(sys.argv) > 2 else ""
        await test_command(command, args)
    else:
        # Test all ranking commands
        commands = [
            ("ranking", ""),
            ("stats", ""),
            ("my_rank", ""),
            ("top", "100"),
        ]

        for cmd, args in commands:
            await test_command(cmd, args)
            await asyncio.sleep(1)


if __name__ == "__main__":
    asyncio.run(main())
