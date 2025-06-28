#!/usr/bin/env python3
"""
Test AI interpretability commands in the bot.
"""

import asyncio
import os
import sys
from pathlib import Path

import discord
from discord.ext import commands

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))


async def test_ai_commands():
    """Test AI commands by simulating bot interactions."""

    # Create a minimal bot instance
    intents = discord.Intents.default()
    intents.message_content = True
    bot = commands.Bot(command_prefix="/", intents=intents)

    # Mock configuration
    bot.config = {"gemini_api_key": os.getenv("GEMINI_API_KEY")}

    # Load the cog
    from cogs.commands.developer_ai import DeveloperAI

    await bot.add_cog(DeveloperAI(bot))

    print("✅ DeveloperAI cog loaded successfully!")

    # List available commands
    print("\n📋 Available AI commands:")
    for command in bot.commands:
        if command.name == "ai" or command.name.startswith("ai_"):
            print(f"  - /{command.name}: {command.description or 'No description'}")
            if hasattr(command, "commands"):  # Group command
                for subcommand in command.commands:
                    print(f"    - /{command.name} {subcommand.name}: {subcommand.description or 'No description'}")

    # Test parsing some inputs to generate decision logs
    print("\n🧪 Generating test data...")
    from core.ai.color_parser import ColorParser
    from core.ai.command_classifier import CommandIntentClassifier
    from core.ai.duration_parser import DurationParser

    # Test duration parsing
    duration_parser = DurationParser(use_ai=True)
    test_durations = ["5 minut", "dwa dni", "na tydzień"]
    for test in test_durations:
        try:
            result = await duration_parser.parse(test)
            print(f"  ✅ Duration '{test}' -> {result.seconds}s")
        except Exception as e:
            print(f"  ❌ Duration '{test}' failed: {e}")

    # Test color parsing
    color_parser = ColorParser(use_ai=True)
    test_colors = ["niebieski", "#00FF00", "ciemna czerwień"]
    for test in test_colors:
        try:
            result = await color_parser.parse(test)
            print(f"  ✅ Color '{test}' -> {result.hex_color}")
        except Exception as e:
            print(f"  ❌ Color '{test}' failed: {e}")

    # Test intent classification
    intent_classifier = CommandIntentClassifier(use_ai=True)
    test_intents = ["pomóż mi", "kup rolę", "wycisz go"]
    for test in test_intents:
        try:
            result = await intent_classifier.classify(test)
            print(f"  ✅ Intent '{test}' -> {result.category.value}")
        except Exception as e:
            print(f"  ❌ Intent '{test}' failed: {e}")

    print("\n✅ All command tests completed!")
    print("\n💡 To test commands in Discord:")
    print("  1. Use /ai explain - to see the last AI decision")
    print("  2. Use /ai features duration_parser - to see feature importance")
    print("  3. Use /ai trace - to see recent decisions")
    print("  4. Use /ai stats - to see overall statistics")
    print('  5. Use /ai test duration "3 godziny" - to test parsing')

    # Clean up
    await bot.close()


async def main():
    """Run the test."""
    try:
        await test_ai_commands()
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
