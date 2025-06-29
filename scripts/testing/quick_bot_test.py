#!/usr/bin/env python3
"""Quick bot testing utility for development."""

import re
import subprocess
import time
from typing import Any, Dict, List, Optional


def test_bot_command(command: str, check_patterns: Optional[List[str]] = None) -> Dict[str, Any]:
    """
    Test a bot command by checking Docker logs.

    Args:
        command: Command name to check in logs (e.g., "profile", "shop")
        check_patterns: Optional patterns to search for in logs

    Returns:
        Dict with test results
    """
    print(f"\n🔍 Testing {command} command...")

    # Get Docker logs
    result = subprocess.run(["docker-compose", "logs", "app", "--tail=100"], capture_output=True, text=True)

    logs = result.stdout

    # Check if command was executed
    command_patterns = [f"User .* requested {command}", f"!{command}", f"/{command}", f"simulate {command}"]

    found_command = False
    for pattern in command_patterns:
        if re.search(pattern, logs, re.IGNORECASE):
            found_command = True
            break

    # Check for errors
    error_patterns = [
        r"ERROR.*" + command,
        r"Failed.*" + command,
        r"Traceback",
        r"AttributeError",
        r"TypeError",
        r"KeyError",
    ]

    errors_found = []
    for pattern in error_patterns:
        matches = re.findall(pattern, logs, re.IGNORECASE | re.MULTILINE)
        errors_found.extend(matches)

    # Check for specific patterns if provided
    patterns_found = []
    if check_patterns:
        for pattern in check_patterns:
            if re.search(pattern, logs, re.IGNORECASE):
                patterns_found.append(pattern)

    # Determine success
    success = found_command and len(errors_found) == 0

    result: Dict[str, Any] = {
        "command": command,
        "success": success,
        "found_command": found_command,
        "errors": errors_found,
        "patterns_found": patterns_found,
    }

    # Print summary
    print(f"✅ Command found: {found_command}")
    if errors_found:
        print(f"❌ Errors: {len(errors_found)}")
        for error in errors_found[:3]:  # Show first 3 errors
            print(f"   - {error}")
    else:
        print("✅ No errors found")

    if patterns_found:
        print(f"✅ Patterns found: {', '.join(patterns_found)}")

    return result


def check_bot_status() -> bool:
    """Check if bot is running properly."""
    print("🔍 Checking bot status...")

    # Check Docker container using docker-compose
    result = subprocess.run(["docker-compose", "ps"], capture_output=True, text=True)

    if "zgdk-app-1" in result.stdout and "Up" in result.stdout:
        print("✅ Container is running")

        # Check recent logs for connection
        logs_result = subprocess.run(["docker-compose", "logs", "app", "--tail=50"], capture_output=True, text=True)

        if "Logged in as" in logs_result.stdout:
            print("✅ Bot is connected to Discord")
            return True
        else:
            print("❌ Bot might not be connected to Discord")
            return False
    else:
        print("❌ Container not running")
        return False


def restart_bot() -> bool:
    """Restart the bot container."""
    print("🔄 Restarting bot...")

    result = subprocess.run(["docker-compose", "restart", "app"], capture_output=True, text=True)

    if result.returncode == 0:
        print("✅ Bot restarted successfully")
        time.sleep(5)  # Wait for bot to start
        return True
    else:
        print(f"❌ Failed to restart bot: {result.stderr}")
        return False


def quick_test_suite():
    """Run a quick test suite for common commands."""
    print("=" * 60)
    print("QUICK BOT TEST SUITE")
    print("=" * 60)

    # Check bot status
    if not check_bot_status():
        print("\n⚠️  Bot is not running properly!")
        if input("Restart bot? (y/n): ").lower() == "y":
            restart_bot()
        else:
            return

    # Test commands
    commands_to_test = [
        ("profile", ["Profil użytkownika", "Portfel", "Zaproszenia"]),
        ("shop", ["Sklep", "Premium", "Role"]),
        ("help", ["Komendy", "pomoc"]),
    ]

    results = []
    for cmd, patterns in commands_to_test:
        result = test_bot_command(cmd, patterns)
        results.append(result)
        time.sleep(1)

    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)

    passed = sum(1 for r in results if r["success"])
    failed = len(results) - passed

    print(f"\nTotal: {len(results)} tests")
    print(f"✅ Passed: {passed}")
    print(f"❌ Failed: {failed}")

    if failed > 0:
        print("\nFailed tests:")
        for r in results:
            if not r["success"]:
                print(f"  - {r['command']}: {r['errors'][:1] if r['errors'] else 'Command not found'}")


if __name__ == "__main__":
    quick_test_suite()
