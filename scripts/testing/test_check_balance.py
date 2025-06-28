"""Check user balance after addbalance command."""

import asyncio
import json

import aiohttp


async def check_balance():
    """Check user balance by running shop command."""
    base_url = "http://localhost:8089"

    async with aiohttp.ClientSession() as session:
        # Run shop command as the user to see their balance
        print("Checking balance for user 489328381972971520...")
        try:
            command_data = {"command": "shop", "channel_id": "960665315426226216", "author_id": "489328381972971520"}

            async with session.post(
                f"{base_url}/execute", json=command_data, timeout=aiohttp.ClientTimeout(total=10)
            ) as response:
                data = await response.json()
                print(f"Response: {json.dumps(data, indent=2)}")

                # Try to get actual responses
                if data.get("success"):
                    # Get the responses that were sent
                    async with session.get(
                        f"{base_url}/responses", timeout=aiohttp.ClientTimeout(total=5)
                    ) as resp_response:
                        responses = await resp_response.json()
                        print(f"\nCaptured responses: {json.dumps(responses, indent=2)}")

                        # Look for balance in embeds
                        for response in responses.get("responses", []):
                            if isinstance(response, dict):
                                embeds = response.get("embeds", [])
                                for embed in embeds:
                                    footer = embed.get("footer", {})
                                    if "Portfel" in footer.get("text", ""):
                                        print(f"\n✅ Found balance: {footer['text']}")
                                        return

                        print("\n⚠️ Could not find balance in responses")
                else:
                    print(f"❌ Shop command failed: {data.get('error')}")
        except Exception as e:
            print(f"❌ Error: {e}")


if __name__ == "__main__":
    asyncio.run(check_balance())
