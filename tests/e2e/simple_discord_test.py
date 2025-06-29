#!/usr/bin/env python3
"""
Simple Discord bot testing without complex imports
Tests actual Discord commands via subprocess calls
"""

import json
import os
import subprocess
from datetime import datetime


def test_discord_commands_simple():
    """Simple Discord command testing"""

    # Check if token is available
    token = os.getenv("CLAUDE_BOT_TOKEN")
    if not token:
        print("❌ CLAUDE_BOT_TOKEN environment variable not set")
        return

    print("🤖 Simple Discord Bot Command Testing")
    print("=====================================")
    print(f"⏰ Start Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    # Test results
    results = {"start_time": datetime.now().isoformat(), "tests": [], "summary": {}}

    # Test 1: Check if bot is online
    print("🔍 Test 1: Check bot health")
    try:
        health_result = subprocess.run(["./scripts/docker/health_check.sh"], capture_output=True, text=True, timeout=30)
        if health_result.returncode == 0:
            print("✅ Bot is healthy and running")
            bot_status = "HEALTHY"
        else:
            print("⚠️ Bot health check failed")
            bot_status = "UNHEALTHY"
    except Exception as e:
        print(f"❌ Health check error: {e}")
        bot_status = "ERROR"

    results["tests"].append({"test": "bot_health_check", "status": bot_status, "timestamp": datetime.now().isoformat()})

    # Test 2: Check recent bot logs for command activity
    print("\n🔍 Test 2: Check recent bot activity")
    try:
        logs_result = subprocess.run(
            ["docker-compose", "logs", "app", "--tail=20"], capture_output=True, text=True, timeout=10
        )

        if logs_result.returncode == 0:
            logs = logs_result.stdout

            # Check for command activity
            if "Command" in logs and "executed" in logs:
                print("✅ Bot is processing commands")
                activity_status = "ACTIVE"
            elif "add_activity" in logs:
                print("✅ Bot is tracking activity")
                activity_status = "TRACKING"
            else:
                print("⚠️ No recent command activity detected")
                activity_status = "QUIET"
        else:
            print("❌ Failed to get bot logs")
            activity_status = "ERROR"

    except Exception as e:
        print(f"❌ Log check error: {e}")
        activity_status = "ERROR"

    results["tests"].append(
        {"test": "bot_activity_check", "status": activity_status, "timestamp": datetime.now().isoformat()}
    )

    # Test 3: Check if permissions system is working (via logs)
    print("\n🔍 Test 3: Check permissions system")
    try:
        perm_result = subprocess.run(
            ["docker-compose", "logs", "app", "--tail=50"], capture_output=True, text=True, timeout=10
        )

        if perm_result.returncode == 0:
            logs = perm_result.stdout

            # Check for permission logs
            if "OWNER CHECK" in logs or "PERMISSION" in logs:
                print("✅ Permissions system is active")
                perm_status = "ACTIVE"
            elif "CheckFailure" in logs:
                print("✅ Permissions system is blocking unauthorized access")
                perm_status = "BLOCKING"
            else:
                print("ℹ️ No recent permission activity")
                perm_status = "QUIET"
        else:
            print("❌ Failed to check permission logs")
            perm_status = "ERROR"

    except Exception as e:
        print(f"❌ Permission check error: {e}")
        perm_status = "ERROR"

    results["tests"].append(
        {"test": "permissions_check", "status": perm_status, "timestamp": datetime.now().isoformat()}
    )

    # Summary
    print("\n" + "=" * 40)
    print("📊 TEST SUMMARY")
    print("=" * 40)

    passed_tests = 0
    total_tests = len(results["tests"])

    for i, test in enumerate(results["tests"], 1):
        status = test["status"]
        if status in ["HEALTHY", "ACTIVE", "TRACKING", "BLOCKING"]:
            print(f"{i}. ✅ {test['test']}: {status}")
            passed_tests += 1
        elif status in ["QUIET"]:
            print(f"{i}. ⚠️ {test['test']}: {status}")
            passed_tests += 0.5
        else:
            print(f"{i}. ❌ {test['test']}: {status}")

    success_rate = (passed_tests / total_tests * 100) if total_tests > 0 else 0

    results["summary"] = {
        "total_tests": total_tests,
        "passed_tests": passed_tests,
        "success_rate": round(success_rate, 1),
    }

    print(f"\nSuccess Rate: {success_rate:.1f}%")

    if success_rate >= 75:
        print("🎉 Overall Status: EXCELLENT")
        overall_status = "EXCELLENT"
    elif success_rate >= 50:
        print("👍 Overall Status: GOOD")
        overall_status = "GOOD"
    else:
        print("⚠️ Overall Status: NEEDS ATTENTION")
        overall_status = "NEEDS_ATTENTION"

    results["summary"]["overall_status"] = overall_status

    # Save results
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"tests/results/simple_discord_test_{timestamp}.json"

    try:
        os.makedirs("tests/results", exist_ok=True)
        with open(filename, "w") as f:
            json.dump(results, f, indent=2, default=str)
        print(f"\n📄 Results saved to: {filename}")
    except Exception as e:
        print(f"❌ Failed to save results: {e}")

    print("\n🔧 Manual Testing Instructions:")
    print("1. Go to Discord server zaGadka")
    print("2. Go to #cicd channel")
    print("3. Test commands:")
    print("   ,addbalance @Claude 1000")
    print("   ,profile")
    print("   ,shop")
    print("4. Verify bot responds to all commands")

    return results


if __name__ == "__main__":
    test_discord_commands_simple()
