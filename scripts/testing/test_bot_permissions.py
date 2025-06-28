#!/usr/bin/env python3
"""Test bot permissions on bump channel."""

import asyncio
import json

import aiohttp


async def check_permissions():
    async with aiohttp.ClientSession() as session:
        payload = {"action": "check_permissions", "channel_id": "1326322441383051385"}  # bump channel

        async with session.post("http://localhost:8090/execute", json=payload) as resp:
            result = await resp.json()
            print(json.dumps(result, indent=2))


if __name__ == "__main__":
    asyncio.run(check_permissions())
