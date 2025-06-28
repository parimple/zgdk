#!/usr/bin/env python3
"""Test ranking command fix."""

import asyncio
import json

import aiohttp


async def test_ranking():
    async with aiohttp.ClientSession() as session:
        payload = {
            "command": "ranking",
            "user_id": "956602391891947592"
        }

        async with session.post("http://localhost:8090/execute", json=payload) as resp:
            result = await resp.json()

        print(json.dumps(result, indent=2))

        if "error" in result:
            print(f"\n❌ Still getting error: {result['error']}")
        elif "responses" in result and result["responses"]:
            response = result["responses"][0]
            if "content" in response and "błąd" in response["content"]:
                print("\n❌ Still getting error in response")
            else:
                print("\n✅ Ranking command seems to work!")

if __name__ == "__main__":
    asyncio.run(test_ranking())
