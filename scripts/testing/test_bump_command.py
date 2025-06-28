#!/usr/bin/env python3
"""Test bump command via MCP."""

import asyncio
import json
import subprocess

async def test_bump_command():
    """Test the bump command."""
    
    print("Testing ,bump command via MCP")
    print("=" * 40)
    
    # Execute bump command via docker exec
    cmd = [
        "docker", "exec", "-i", "zgdk-mcp-1",
        "python", "-c",
        """
import asyncio
import json
from mcp_bot_server import call_tool

async def main():
    result = await call_tool('execute_command', {'command': 'bump', 'args': ''})
    for r in result:
        print(f"Type: {r.type}")
        print(f"Text: {r.text}")
        print()

asyncio.run(main())
"""
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        print("Output:")
        print(result.stdout)
        if result.stderr:
            print("Errors:")
            print(result.stderr)
    except subprocess.CalledProcessError as e:
        print(f"Error executing command: {e}")
        print(f"stdout: {e.stdout}")
        print(f"stderr: {e.stderr}")

if __name__ == "__main__":
    asyncio.run(test_bump_command())