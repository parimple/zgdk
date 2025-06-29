#!/usr/bin/env python3
"""
Test script for Gemini API integration in ZGDK bot.
"""

import asyncio
import os

from dotenv import load_dotenv

# Load environment variables
load_dotenv()

from core.ai.color_parser import ColorParser  # noqa: E402
from core.ai.command_classifier import CommandIntentClassifier  # noqa: E402

# Import AI modules
from core.ai.duration_parser import DurationParser  # noqa: E402


async def test_duration_parser():
    """Test duration parsing with Gemini."""
    print("\n=== Testing Duration Parser ===")
    parser = DurationParser(use_ai=True)

    test_cases = ["1 dzień", "2 godziny i 30 minut", "do jutra", "na weekend", "kwadrans", "pół godziny"]

    for test in test_cases:
        try:
            result = await parser.parse(test)
            print(f"✓ '{test}' -> {result.seconds}s ({result.human_readable})")
            print(f"  Interpretation: {result.interpretation}")
        except Exception as e:
            print(f"✗ '{test}' -> Error: {e}")


async def test_color_parser():
    """Test color parsing with Gemini."""
    print("\n=== Testing Color Parser ===")
    parser = ColorParser(use_ai=True)

    test_cases = ["czerwony", "ciemny niebieski", "kolor discorda", "jasny fioletowy", "morski", "#FF0000"]

    for test in test_cases:
        try:
            result = await parser.parse(test)
            print(f"✓ '{test}' -> {result.hex_color}")
            print(f"  Interpretation: {result.interpretation}")
            if result.closest_named_color:
                print(f"  Closest named: {result.closest_named_color}")
        except Exception as e:
            print(f"✗ '{test}' -> Error: {e}")


async def test_command_classifier():
    """Test command classification with Gemini."""
    print("\n=== Testing Command Classifier ===")
    classifier = CommandIntentClassifier(use_ai=True)

    test_cases = [
        "jak kupić premium?",
        "wycisz tego użytkownika",
        "pokaż mi mój profil",
        "stwórz kanał głosowy",
        "sprawdź saldo",
    ]

    for test in test_cases:
        try:
            result = await classifier.classify(test)
            print(f"✓ '{test}'")
            print(f"  Category: {result.category.value} (confidence: {result.confidence:.2f})")
            if result.suggested_command:
                print(f"  Suggested: /{result.suggested_command}")
            print(f"  Interpretation: {result.interpretation}")
        except Exception as e:
            print(f"✗ '{test}' -> Error: {e}")


async def main():
    """Main test function."""
    print("=== ZGDK Gemini Integration Test ===")

    # Check for API keys
    gemini_key = os.getenv("GEMINI_API_KEY")
    openai_key = os.getenv("OPENAI_API_KEY")

    if gemini_key:
        print("✓ Gemini API key found (using Gemini)")
    elif openai_key:
        print("✓ OpenAI API key found (fallback to OpenAI)")
    else:
        print("✗ No API keys found! Set GEMINI_API_KEY or OPENAI_API_KEY")
        return

    # Run tests
    await test_duration_parser()
    await test_color_parser()
    await test_command_classifier()

    print("\n=== Test Complete ===")


if __name__ == "__main__":
    asyncio.run(main())
