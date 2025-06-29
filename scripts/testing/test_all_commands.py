#!/usr/bin/env python3
"""
Test all Discord bot commands systematically.

This script tests all available commands and generates a comprehensive report.
"""

import json
import subprocess
import time
from datetime import datetime
from typing import Dict, List


class CommandTester:
    """Comprehensive command tester."""

    def __init__(self):
        self.container = "zgdk-mcp-1"
        self.results = []
        self.start_time = datetime.now()

        # Define all commands to test
        self.commands = [
            # Info commands
            ("help", "", "Display help menu"),
            ("profile", "", "Show user profile"),
            ("balance", "", "Check balance"),
            ("userinfo", "123456789", "Get user information"),
            ("serverinfo", "", "Get server information"),
            ("roleinfo", "@Member", "Get role information"),
            ("avatar", "", "Show avatar"),
            # Shop commands
            ("shop", "", "Display shop"),
            ("buy", "1", "Buy item (should fail - no funds)"),
            # Bump commands
            ("bump", "", "Check bump status"),
            ("bumptop", "", "Show bump leaderboard"),
            # Team commands
            ("team", "list", "List teams"),
            ("teamtop", "", "Team leaderboard"),
            # Voice commands
            ("voice", "lock", "Lock voice channel"),
            ("voice", "unlock", "Unlock voice channel"),
            # Premium commands
            ("premium", "", "Check premium status"),
            # Ranking commands
            ("rank", "", "Show rank"),
            ("top", "", "Show leaderboard"),
            ("topusers", "", "Show user leaderboard"),
            # Moderation commands (should fail without perms)
            ("mute", "@user 10m test", "Mute user (no perms)"),
            ("unmute", "@user", "Unmute user (no perms)"),
            ("ban", "@user test", "Ban user (no perms)"),
            ("kick", "@user test", "Kick user (no perms)"),
            ("warn", "@user test", "Warn user (no perms)"),
            ("clear", "10", "Clear messages (no perms)"),
        ]

    def execute_command(self, command: str, args: str = "") -> Dict:  # type: ignore[type-arg]
        """Execute a single command via MCP."""
        script = """
import asyncio
import json
from mcp_bot_server import call_tool

async def main():
    try:
        result = await call_tool('execute_command', {{
            'command': '{command}',
            'args': '{args}'
        }})

        output = {{
            'success': True,
            'responses': []
        }}

        for r in result:
            if hasattr(r, 'type') and hasattr(r, 'text'):
                output['responses'].append({{
                    'type': r.type,
                    'text': r.text[:200]  # Truncate for readability
                }})
            else:
                output['responses'].append(str(r)[:200])

        print(json.dumps(output))

    except Exception as e:
        print(json.dumps({{'success': False, 'error': str(e)}}))

asyncio.run(main())
"""

        cmd = ["docker", "exec", "-i", self.container, "python", "-c", script]

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10, check=True)

            if result.stdout:
                return json.loads(result.stdout.strip())  # type: ignore[no-any-return]
            return {"success": False, "error": "No output"}

        except subprocess.TimeoutExpired:
            return {"success": False, "error": "Timeout"}
        except subprocess.CalledProcessError as e:
            return {"success": False, "error": f"Docker error: {e}"}
        except json.JSONDecodeError:
            return {"success": False, "error": "Invalid JSON response"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def test_command(self, command: str, args: str, description: str) -> Dict:
        """Test a command and record results."""
        print(f"  Testing: /{command} {args}... ", end="", flush=True)

        start = time.time()
        result = self.execute_command(command, args)
        duration = time.time() - start

        # Determine status
        if result.get("success"):
            # Check if it's an expected permission error
            responses_text = " ".join(str(r) for r in result.get("responses", []))
            if "permissions" in responses_text.lower() or "uprawnie" in responses_text.lower():
                status = "EXPECTED_FAIL"
                print("⚠️  (permission denied - expected)")
            else:
                status = "PASS"
                print("✅")
        else:
            status = "FAIL"
            print(f"❌ ({result.get('error', 'Unknown error')})")

        # Record result
        test_result = {
            "command": command,
            "args": args,
            "description": description,
            "status": status,
            "duration": duration,
            "result": result,
        }

        self.results.append(test_result)
        return test_result

    def run_all_tests(self):
        """Run all command tests."""
        print(f"\n🚀 Testing {len(self.commands)} commands...")
        print("=" * 70)

        for command, args, description in self.commands:
            self.test_command(command, args, description)
            # Small delay to avoid overwhelming the bot
            time.sleep(0.1)

    def check_docker_status(self) -> bool:
        """Check if Docker container is running."""
        cmd = ["docker", "ps", "--format", "{{.Names}}"]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True)
            return self.container in result.stdout
        except Exception:
            return False

    def get_error_logs(self, lines: int = 30) -> List[str]:
        """Get recent error logs from Docker."""
        cmd = ["docker-compose", "logs", "app", f"--tail={lines}", "--no-log-prefix"]

        try:
            result = subprocess.run(cmd, capture_output=True, text=True)
            errors = []

            for line in result.stdout.split("\n"):
                if any(word in line.lower() for word in ["error", "failed", "exception"]):
                    errors.append(line.strip())

            return errors[-10:]  # Last 10 errors
        except Exception:
            return []

    def generate_report(self) -> str:
        """Generate a comprehensive test report."""
        total_duration = (datetime.now() - self.start_time).total_seconds()

        # Count results
        passed = sum(1 for r in self.results if r["status"] == "PASS")
        failed = sum(1 for r in self.results if r["status"] == "FAIL")
        expected_fail = sum(1 for r in self.results if r["status"] == "EXPECTED_FAIL")

        report = []
        report.append("=" * 70)
        report.append("📊 DISCORD BOT COMMAND TEST REPORT")
        report.append("=" * 70)
        report.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report.append(f"Total Duration: {total_duration:.2f}s")
        report.append("")

        # Summary
        report.append("SUMMARY:")
        report.append(f"  Total Commands: {len(self.results)}")
        report.append(f"  ✅ Passed: {passed}")
        report.append(f"  ❌ Failed: {failed}")
        report.append(f"  ⚠️  Expected Failures: {expected_fail}")
        report.append(f"  Success Rate: {(passed / len(self.results) * 100):.1f}%")
        report.append("")

        # Failed commands
        if failed > 0:
            report.append("FAILED COMMANDS:")
            for r in self.results:
                if r["status"] == "FAIL":
                    report.append(f"  ❌ /{r['command']} {r['args']}")
                    report.append(f"     Error: {r['result'].get('error', 'Unknown')}")
            report.append("")

        # Detailed results
        report.append("DETAILED RESULTS:")
        report.append("-" * 70)
        report.append(f"{'Command':<20} {'Args':<20} {'Status':<15} {'Duration':<10}")
        report.append("-" * 70)

        for r in self.results:
            status_emoji = {"PASS": "✅ PASS", "FAIL": "❌ FAIL", "EXPECTED_FAIL": "⚠️  EXPECTED"}.get(
                r["status"], r["status"]
            )

            report.append(
                f"{r['command']:<20} "
                f"{r['args'][:17]+'...' if len(r['args']) > 20 else r['args']:<20} "
                f"{status_emoji:<15} "
                f"{r['duration']:.3f}s"
            )

        # Recent errors
        report.append("")
        report.append("RECENT DOCKER ERRORS:")
        report.append("-" * 70)

        errors = self.get_error_logs()
        if errors:
            for error in errors:
                report.append(f"  {error[:67]}...")
        else:
            report.append("  No recent errors found")

        report.append("=" * 70)

        return "\n".join(report)

    def save_report(self, filename: str = "command_test_report.txt"):
        """Save the test report to a file."""
        report = self.generate_report()
        with open(filename, "w") as f:
            f.write(report)
        print(f"\n📄 Report saved to: {filename}")


def main():
    """Run all tests and generate report."""
    print("🤖 Discord Bot Command Test Suite")
    print("=" * 70)

    # Create tester
    tester = CommandTester()

    # Check Docker status
    print("🐳 Checking Docker status... ", end="", flush=True)
    if tester.check_docker_status():
        print("✅ Container running")
    else:
        print("❌ Container not found!")
        print(f"Please ensure {tester.container} is running")
        return 1

    # Run tests
    tester.run_all_tests()

    # Generate and display report
    print("\n" + tester.generate_report())

    # Save report
    tester.save_report()

    # Return exit code
    failed = sum(1 for r in tester.results if r["status"] == "FAIL")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    exit(main())
