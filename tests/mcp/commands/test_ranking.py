#!/usr/bin/env python3
"""Test ranking command through MCP."""

import asyncio
import subprocess


async def test_ranking():
    """Test the ranking command."""

    # Test through docker exec with direct Python
    cmd = [
        "docker",
        "exec",
        "-i",
        "zgdk-mcp-1",
        "python",
        "-c",
        """
import asyncio
import aiohttp

async def test():
    async with aiohttp.ClientSession() as session:
        # Execute ranking command
        async with session.post('http://localhost:8090/execute',
                              json={'command': 'ranking', 'args': ''}) as resp:
            result = await resp.json()
            print(f"Ranking result: {result}")

asyncio.run(test())
""",
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    print("stdout:", result.stdout)
    print("stderr:", result.stderr)
    print("returncode:", result.returncode)


if __name__ == "__main__":
    asyncio.run(test_ranking())
