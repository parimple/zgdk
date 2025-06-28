#!/usr/bin/env python3
"""Test voice commands via MCP with proper channel support."""

import asyncio
import json
import sys

from mcp_client import call_mcp_tool

# Test channel ID where bot has permissions
TEST_CHANNEL_ID = 1387864734002446407

async def test_voice_command(command: str, args: str = "", channel_id: int = TEST_CHANNEL_ID):
    """Test a voice command using MCP."""
    full_command = f",{command}"
    if args:
        full_command += f" {args}"
    
    print(f"\n{'='*60}")
    print(f"Testing: {full_command}")
    print(f"Channel: {channel_id}")
    print(f"{'='*60}")
    
    try:
        result = await call_mcp_tool("execute_command", {
            "command": command,
            "args": args
        })
        
        if result and result.get("result"):
            content = result["result"].get("content", [])
            if content and len(content) > 0:
                response = content[0].get("text", "")
                if response:
                    try:
                        data = json.loads(response)
                        print(f"\nSuccess: Command executed")
                        
                        # Parse response
                        if 'content' in data:
                            print(f"Content: {data['content']}")
                        
                        if 'embeds' in data and data['embeds']:
                            for i, embed in enumerate(data['embeds']):
                                print(f"\nEmbed {i+1}:")
                                if embed.get('title'):
                                    print(f"  Title: {embed['title']}")
                                if embed.get('description'):
                                    print(f"  Description: {embed['description'][:200]}...")
                                if embed.get('fields'):
                                    print(f"  Fields: {len(embed['fields'])}")
                                    for field in embed['fields'][:3]:
                                        print(f"    - {field.get('name', 'No name')}: {field.get('value', 'No value')[:50]}...")
                        
                        if 'error' in data:
                            print(f"\nError: {data['error']}")
                            
                    except json.JSONDecodeError:
                        print(f"Response: {response}")
            else:
                print("Error: No response from command")
        else:
            print("Error: Command failed to execute")
            
    except Exception as e:
        print(f"Error: {e}")

async def main():
    """Test voice commands."""
    if len(sys.argv) > 1:
        # Single command mode
        command = sys.argv[1]
        args = " ".join(sys.argv[2:]) if len(sys.argv) > 2 else ""
        await test_voice_command(command, args)
    else:
        # Test common voice commands
        commands = [
            ("vc", ""),  # Show voice channel info
            ("c", ""),   # Toggle connect permission
            ("voicechat", ""),  # Full command name
            ("voice", "info"),  # Voice info subcommand
            ("voice", "limit 5"),  # Set member limit
            ("voice", "reset"),  # Reset channel
        ]
        
        for cmd, args in commands:
            await test_voice_command(cmd, args)
            await asyncio.sleep(2)

if __name__ == "__main__":
    asyncio.run(main())