#!/usr/bin/env python3
"""
Test script for AI interpretability system.
Tests all AI modules and verifies logging/explanation functionality.
"""

import asyncio
import os
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from core.ai.duration_parser import DurationParser
from core.ai.color_parser import ColorParser
from core.ai.command_classifier import CommandIntentClassifier
from utils.ai.interpretability import get_explainer
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)

# Test cases
DURATION_TESTS = [
    "2 godziny",
    "tydzień",
    "pół dnia",
    "do jutra",
    "kwadrans",
    "3 dni i 4 godziny",
    "na weekend",
    "dwa tygodnie",
    "półtora miesiąca"
]

COLOR_TESTS = [
    "#FF0000",
    "czerwony",
    "ciemnoniebieski",
    "jasna zieleń",
    "kolor nieba",
    "rgb(255, 128, 0)",
    "fioletowy pastelowy",
    "kolor ferrari",
    "morski"
]

INTENT_TESTS = [
    ("chcę kupić rolę premium", None),
    ("ile kosztuje vip?", {"command_name": "shop"}),
    ("wycisz tego użytkownika", {"command_name": "mute"}),
    ("pokaż mi statystyki", {"command_name": "stats"}),
    ("jak używać bota?", None),
    ("dodaj mnie do drużyny", {"command_name": "team"}),
    ("sprawdź moje saldo", {"command_name": "balance"})
]


async def test_duration_parser():
    """Test duration parser with interpretability."""
    print("\n" + "="*50)
    print("TESTING DURATION PARSER")
    print("="*50)
    
    parser = DurationParser(use_ai=True)
    explainer = get_explainer()
    
    for test_input in DURATION_TESTS:
        try:
            print(f"\n📝 Input: '{test_input}'")
            result = await parser.parse(test_input)
            
            print(f"✅ Result: {result.seconds} seconds ({result.human_readable})")
            print(f"🎯 Confidence: {result.confidence:.0%}")
            print(f"💬 Interpretation: {result.interpretation}")
            
            # Get last decision for explanation
            decisions = explainer.logger.get_recent_decisions(1, "duration_parser")
            if decisions:
                decision = decisions[0]
                print(f"⚡ Execution time: {decision.execution_time_ms:.1f}ms")
                
                # Show key features
                print("🔍 Key features:")
                for key, value in list(decision.features_extracted.items())[:5]:
                    print(f"   - {key}: {value}")
                
        except Exception as e:
            print(f"❌ Error: {e}")


async def test_color_parser():
    """Test color parser with interpretability."""
    print("\n" + "="*50)
    print("TESTING COLOR PARSER")
    print("="*50)
    
    parser = ColorParser(use_ai=True)
    explainer = get_explainer()
    
    for test_input in COLOR_TESTS:
        try:
            print(f"\n🎨 Input: '{test_input}'")
            result = await parser.parse(test_input)
            
            print(f"✅ Result: {result.hex_color}")
            print(f"🌈 RGB: {result.rgb}")
            print(f"🎯 Confidence: {result.confidence:.0%}")
            print(f"💬 Interpretation: {result.interpretation}")
            if result.closest_named_color:
                print(f"🏷️ Closest named: {result.closest_named_color}")
            
            # Get last decision for explanation
            decisions = explainer.logger.get_recent_decisions(1, "color_parser")
            if decisions:
                decision = decisions[0]
                print(f"⚡ Execution time: {decision.execution_time_ms:.1f}ms")
                
                # Show key features
                print("🔍 Key features:")
                for key, value in list(decision.features_extracted.items())[:5]:
                    print(f"   - {key}: {value}")
                
        except Exception as e:
            print(f"❌ Error: {e}")


async def test_intent_classifier():
    """Test intent classifier with interpretability."""
    print("\n" + "="*50)
    print("TESTING INTENT CLASSIFIER")
    print("="*50)
    
    classifier = CommandIntentClassifier(use_ai=True)
    explainer = get_explainer()
    
    for test_input, context in INTENT_TESTS:
        try:
            print(f"\n💭 Input: '{test_input}'")
            if context:
                print(f"📌 Context: {context}")
            
            result = await classifier.classify(test_input, context)
            
            print(f"✅ Category: {result.category.value}")
            print(f"🎯 Confidence: {result.confidence:.0%}")
            print(f"💬 Interpretation: {result.interpretation}")
            if result.suggested_command:
                print(f"💡 Suggested command: {result.suggested_command}")
            if result.alternative_categories:
                print(f"🔄 Alternatives: {[c.value for c in result.alternative_categories]}")
            
            # Get last decision for explanation
            decisions = explainer.logger.get_recent_decisions(1, "intent_classifier")
            if decisions:
                decision = decisions[0]
                print(f"⚡ Execution time: {decision.execution_time_ms:.1f}ms")
                
                # Show key features
                print("🔍 Key features:")
                for key, value in list(decision.features_extracted.items())[:5]:
                    if isinstance(value, dict):
                        print(f"   - {key}:")
                        for k, v in value.items():
                            print(f"     • {k}: {v}")
                    else:
                        print(f"   - {key}: {value}")
                
        except Exception as e:
            print(f"❌ Error: {e}")


async def test_explanations():
    """Test the explanation generation."""
    print("\n" + "="*50)
    print("TESTING EXPLANATIONS")
    print("="*50)
    
    explainer = get_explainer()
    
    # Test duration explanation
    parser = DurationParser(use_ai=True)
    await parser.parse("trzy dni")
    
    decisions = explainer.logger.get_recent_decisions(1, "duration_parser")
    if decisions:
        decision = decisions[0]
        explanation = await explainer.explain_decision(
            module=decision.module,
            input_text="trzy dni",
            decision=decision.final_decision,
            features=decision.features_extracted,
            confidence=decision.confidence
        )
        print(f"\n📖 Duration Explanation:\n{explanation}")
    
    # Test feature importance report
    print("\n📊 Feature Importance Reports:")
    for module in ["duration_parser", "color_parser", "intent_classifier"]:
        report = await explainer.generate_feature_report(module)
        print(f"\n{report}")


async def test_statistics():
    """Show overall statistics after tests."""
    print("\n" + "="*50)
    print("OVERALL STATISTICS")
    print("="*50)
    
    explainer = get_explainer()
    all_decisions = explainer.logger.current_session
    
    if not all_decisions:
        print("No decisions logged.")
        return
    
    # Calculate stats by module
    module_stats = {}
    for decision in all_decisions:
        module = decision.module
        if module not in module_stats:
            module_stats[module] = {
                'count': 0,
                'total_time': 0,
                'success_count': 0,
                'total_confidence': 0
            }
        
        stats = module_stats[module]
        stats['count'] += 1
        stats['total_time'] += decision.execution_time_ms
        if decision.final_decision is not None:
            stats['success_count'] += 1
        stats['total_confidence'] += decision.confidence
    
    print(f"\n📈 Total decisions processed: {len(all_decisions)}")
    
    for module, stats in module_stats.items():
        print(f"\n📦 {module}:")
        print(f"   - Decisions: {stats['count']}")
        print(f"   - Success rate: {stats['success_count']/stats['count']:.0%}")
        print(f"   - Avg confidence: {stats['total_confidence']/stats['count']:.0%}")
        print(f"   - Avg time: {stats['total_time']/stats['count']:.1f}ms")
        print(f"   - Total time: {stats['total_time']:.0f}ms")


async def main():
    """Run all tests."""
    print("🚀 Starting AI Interpretability Tests")
    print(f"📁 Log directory: logs/ai_decisions/")
    
    # Set API key if available
    gemini_key = os.getenv('GEMINI_API_KEY')
    if gemini_key:
        print("✅ Using Gemini API for enhanced explanations")
    else:
        print("⚠️ No Gemini API key found, using rule-based explanations")
    
    try:
        await test_duration_parser()
        await test_color_parser()
        await test_intent_classifier()
        await test_explanations()
        await test_statistics()
        
        print("\n✅ All tests completed successfully!")
        
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())