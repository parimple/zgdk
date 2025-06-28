#!/usr/bin/env python3
"""
Test the AI moderation assistant.
"""

import asyncio
import sys
from datetime import datetime, timedelta
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from core.ai.moderation_assistant import ModerationAssistant, ModerationType, ThreatLevel, UserContext, ViolationType

# Test cases for moderation
TEST_MESSAGES = [
    # Spam
    ("AAAAAAAAAAAAAAAAAAAAAAAAAAAAAA", "spam"),
    ("BUY NOW!!! CLICK HERE!!! BUY NOW!!!", "spam"),
    ("spam spam spam spam spam spam spam", "spam"),
    ("Check out my server: discord.gg/abc discord.gg/def discord.gg/xyz", "advertising"),
    # Toxicity
    ("You're such an idiot", "toxicity"),
    ("I hate all of you", "toxicity"),
    # Normal messages
    ("Hello everyone, how are you today?", "none"),
    ("Can someone help me with this quest?", "none"),
    ("Great game yesterday!", "none"),
    # Mixed violations
    ("IDIOT IDIOT IDIOT CHECK MY LINK discord.gg/spam", "multiple"),
    # Polish messages
    ("Jesteś głupkiem i debilem", "toxicity"),
    ("SPAMMMM SPAMMMM SPAMMMM", "spam"),
    ("Witam wszystkich, miłego dnia!", "none"),
]


async def test_pattern_detection():
    """Test pattern-based moderation."""
    print("\n" + "=" * 50)
    print("TESTING PATTERN-BASED MODERATION")
    print("=" * 50)

    assistant = ModerationAssistant(use_ai=False)

    # Create test user contexts
    new_user = UserContext(
        user_id="123",
        username="NewUser",
        join_date=datetime.utcnow() - timedelta(days=1),
        previous_violations=0,
        previous_warnings=0,
        previous_mutes=0,
        previous_bans=0,
        is_new_user=True,
        is_repeat_offender=False,
        roles=["Member"],
    )

    repeat_offender = UserContext(
        user_id="456",
        username="TroubleUser",
        join_date=datetime.utcnow() - timedelta(days=100),
        previous_violations=5,
        previous_warnings=3,
        previous_mutes=2,
        previous_bans=0,
        is_new_user=False,
        is_repeat_offender=True,
        roles=["Member"],
    )

    for message, expected in TEST_MESSAGES[:5]:  # Test first 5 with patterns
        print(f"\n📝 Message: '{message[:50]}...'")
        print(f"🎯 Expected: {expected}")

        # Test with new user
        result = await assistant.analyze_message(message, new_user)
        print(f"\n👤 New User Analysis:")
        print(f"  Threat Level: {result.threat_level.value}")
        print(f"  Violations: {[v.value for v in result.violations]}")
        print(f"  Action: {result.suggested_action.value}")
        print(f"  Confidence: {result.confidence:.0%}")
        print(f"  Reason: {result.reason}")

        # Test with repeat offender
        result_repeat = await assistant.analyze_message(message, repeat_offender)
        print(f"\n👤 Repeat Offender Analysis:")
        print(f"  Threat Level: {result_repeat.threat_level.value}")
        print(f"  Action: {result_repeat.suggested_action.value}")
        print(f"  Duration: {result_repeat.duration_text if result_repeat.suggested_duration else 'N/A'}")


async def test_ai_moderation():
    """Test AI-powered moderation."""
    print("\n" + "=" * 50)
    print("TESTING AI-POWERED MODERATION")
    print("=" * 50)

    assistant = ModerationAssistant(use_ai=True)

    # Create a typical user
    user = UserContext(
        user_id="789",
        username="RegularUser",
        join_date=datetime.utcnow() - timedelta(days=30),
        previous_violations=1,
        previous_warnings=1,
        previous_mutes=0,
        previous_bans=0,
        is_new_user=False,
        is_repeat_offender=False,
        roles=["Member", "Verified"],
    )

    # Test with AI
    for message, expected in TEST_MESSAGES:
        print(f"\n🤖 AI Analysis: '{message[:50]}...'")

        try:
            result = await assistant.analyze_message(
                message,
                user,
                server_rules=[
                    "Be respectful",
                    "No spam",
                    "No advertising without permission",
                    "English and Polish allowed",
                ],
            )

            print(f"✅ Success!")
            print(f"  Threat Level: {result.threat_level.value}")
            print(f"  Violations: {[v.value for v in result.violations]}")
            print(f"  Action: {result.suggested_action.value}")
            print(f"  Confidence: {result.confidence:.0%}")
            print(f"  Reason: {result.reason}")

            if result.evidence:
                print(f"  Evidence: {result.evidence[:2]}")

        except Exception as e:
            print(f"❌ Error: {str(e)}")


async def test_user_behavior_analysis():
    """Test user behavior pattern analysis."""
    print("\n" + "=" * 50)
    print("TESTING USER BEHAVIOR ANALYSIS")
    print("=" * 50)

    assistant = ModerationAssistant(use_ai=True)

    # Test different user patterns
    users = [
        UserContext(
            user_id="001",
            username="GoodUser",
            join_date=datetime.utcnow() - timedelta(days=365),
            previous_violations=0,
            previous_warnings=0,
            previous_mutes=0,
            previous_bans=0,
            is_new_user=False,
            is_repeat_offender=False,
            roles=["Member", "Trusted", "1 Year"],
        ),
        UserContext(
            user_id="002",
            username="ProblematicUser",
            join_date=datetime.utcnow() - timedelta(days=60),
            previous_violations=8,
            previous_warnings=5,
            previous_mutes=3,
            previous_bans=0,
            is_new_user=False,
            is_repeat_offender=True,
            roles=["Member"],
        ),
        UserContext(
            user_id="003",
            username="ReformingUser",
            join_date=datetime.utcnow() - timedelta(days=180),
            previous_violations=3,
            previous_warnings=2,
            previous_mutes=1,
            previous_bans=0,
            is_new_user=False,
            is_repeat_offender=False,
            roles=["Member", "Verified"],
            recent_messages=["Thanks for the help!", "GG everyone", "Have a nice day"],
        ),
    ]

    for user in users:
        print(f"\n👤 Analyzing: {user.username}")
        print(f"  Join Date: {(datetime.utcnow() - user.join_date).days} days ago")
        print(f"  Violations: {user.previous_violations}")
        print(f"  Roles: {', '.join(user.roles)}")

        result = await assistant.analyze_user_behavior(user)

        print(f"\n📊 Behavior Analysis:")
        print(f"  Threat Level: {result.threat_level.value}")
        print(f"  Action: {result.suggested_action.value}")
        print(f"  Reason: {result.reason}")
        print(f"  Confidence: {result.confidence:.0%}")


async def test_edge_cases():
    """Test edge cases and special scenarios."""
    print("\n" + "=" * 50)
    print("TESTING EDGE CASES")
    print("=" * 50)

    assistant = ModerationAssistant(use_ai=True)

    # Premium user context
    premium_user = UserContext(
        user_id="999",
        username="PremiumUser",
        join_date=datetime.utcnow() - timedelta(days=200),
        previous_violations=2,
        previous_warnings=2,
        previous_mutes=0,
        previous_bans=0,
        is_new_user=False,
        is_repeat_offender=False,
        roles=["Member", "Premium", "Supporter"],
    )

    # Test cases
    edge_cases = [
        # Very long message
        ("A" * 1000, "Very long message"),
        # Unicode spam
        ("💩" * 50, "Emoji spam"),
        # Mixed languages
        ("This is spam これはスパムです to jest spam", "Mixed language spam"),
        # Subtle toxicity
        ("I really don't like people like you here", "Subtle harassment"),
        # Context-dependent
        ("kys", "Abbreviation that could be harmful"),
    ]

    for message, description in edge_cases:
        print(f"\n🧪 Edge Case: {description}")
        print(f"📝 Message: '{message[:50]}...'")

        try:
            result = await assistant.analyze_message(message, premium_user)

            print(f"  Threat Level: {result.threat_level.value}")
            print(f"  Action: {result.suggested_action.value}")
            print(f"  Confidence: {result.confidence:.0%}")

            # Note premium treatment
            if "Premium" in premium_user.roles:
                print(f"  💎 Premium user - may receive lighter punishment")

        except Exception as e:
            print(f"  ❌ Error: {str(e)}")


async def main():
    """Run all moderation tests."""
    print("🚀 Starting Moderation Assistant Tests")

    try:
        await test_pattern_detection()
        await test_ai_moderation()
        await test_user_behavior_analysis()
        await test_edge_cases()

        print("\n✅ All moderation tests completed!")

        # Show statistics
        from utils.ai.interpretability import get_explainer

        explainer = get_explainer()

        decisions = explainer.logger.get_recent_decisions(module="moderation_assistant")

        if decisions:
            print(f"\n📊 Moderation Statistics:")
            print(f"  Total decisions: {len(decisions)}")

            threat_counts = {}
            action_counts = {}

            for decision in decisions:
                output = decision.output
                if isinstance(output, dict):
                    threat = output.get("threat_level", "unknown")
                    action = output.get("suggested_action", "unknown")

                    threat_counts[threat] = threat_counts.get(threat, 0) + 1
                    action_counts[action] = action_counts.get(action, 0) + 1

            print(f"\n  Threat Levels:")
            for threat, count in threat_counts.items():
                print(f"    {threat}: {count}")

            print(f"\n  Suggested Actions:")
            for action, count in action_counts.items():
                print(f"    {action}: {count}")

    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())

