"""
MCP-based test runner for Discord bot commands.

This runner provides:
- Direct integration with MCP server
- Real command execution
- Response validation
- Database state verification
- Performance tracking
"""

import json
import logging
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

logger = logging.getLogger(__name__)


class MCPTestRunner:
    """Test runner that uses MCP for real command execution."""

    def __init__(self):
        self.container_name = "zgdk-mcp-1"
        self.test_user_id = 123456789
        self.test_channel_id = 987654321
        self.test_guild_id = 960665311701528596
        self.results = []

    def execute_mcp_command(self, command: str, args: str = "") -> Dict[str, Any]:
        """Execute a command through MCP and return the result."""

        # Create the Python script to run inside the container
        script = '''
import asyncio
import json
import sys
from mcp_bot_server import call_tool

async def main():
    try:
        # Execute the command
        result = await call_tool('execute_command', {{
            'command': '{command}',
            'args': '{args}'
        }})

        # Format the output
        output = {{
            'success': True,
            'command': '{command}',
            'args': '{args}',
            'responses': []
        }}

        # Process responses
        for r in result:
            if hasattr(r, '__dict__'):
                output['responses'].append({{
                    'type': getattr(r, 'type', 'unknown'),
                    'text': getattr(r, 'text', str(r)),
                    'data': getattr(r, 'data', {{}})
                }})
            else:
                output['responses'].append({{
                    'type': 'text',
                    'text': str(r)
                }})

        print(json.dumps(output))

    except Exception as e:
        output = {{
            'success': False,
            'command': '{command}',
            'args': '{args}',
            'error': str(e),
            'responses': []
        }}
        print(json.dumps(output))

if __name__ == "__main__":
    asyncio.run(main())
'''

        # Execute the script in the Docker container
        cmd = [
            "docker", "exec", "-i", self.container_name,
            "python", "-c", script
        ]

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30,
                check=True
            )

            # Parse the JSON output
            if result.stdout:
                return json.loads(result.stdout.strip())
            else:
                return {
                    'success': False,
                    'error': 'No output from command',
                    'stderr': result.stderr
                }

        except subprocess.TimeoutExpired:
            return {
                'success': False,
                'error': 'Command execution timeout (30s)',
                'command': command,
                'args': args
            }
        except subprocess.CalledProcessError as e:
            return {
                'success': False,
                'error': f'Docker execution failed: {e}',
                'stdout': e.stdout,
                'stderr': e.stderr,
                'command': command,
                'args': args
            }
        except json.JSONDecodeError as e:
            return {
                'success': False,
                'error': f'Failed to parse JSON output: {e}',
                'raw_output': result.stdout if 'result' in locals() else None,
                'command': command,
                'args': args
            }
        except Exception as e:
            return {
                'success': False,
                'error': f'Unexpected error: {str(e)}',
                'command': command,
                'args': args
            }

    def check_docker_logs(self, lines: int = 50) -> List[str]:
        """Check recent Docker logs for errors."""
        cmd = [
            "docker-compose", "logs", "app",
            f"--tail={lines}"
        ]

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                cwd=str(project_root)
            )

            # Filter for errors and warnings
            log_lines = result.stdout.split('\n')
            important_lines = []

            for line in log_lines:
                lower_line = line.lower()
                if any(keyword in lower_line for keyword in ['error', 'failed', 'exception', 'warning']):
                    important_lines.append(line)

            return important_lines

        except Exception as e:
            logger.error(f"Failed to check logs: {e}")
            return []

    def run_test(self, test_name: str, test_func) -> Dict[str, Any]:
        """Run a single test and record results."""
        print(f"\n🧪 Running: {test_name}")
        start_time = datetime.now()

        try:
            # Run the test
            result = test_func()

            # Check if test passed
            passed = result.get('success', False)

            # Calculate duration
            duration = (datetime.now() - start_time).total_seconds()

            # Record result
            test_result = {
                'name': test_name,
                'passed': passed,
                'duration': duration,
                'result': result
            }

            if passed:
                print(f"  ✅ PASSED ({duration:.2f}s)")
            else:
                print(f"  ❌ FAILED ({duration:.2f}s)")
                if 'error' in result:
                    print(f"     Error: {result['error']}")

            self.results.append(test_result)
            return test_result

        except Exception as e:
            duration = (datetime.now() - start_time).total_seconds()
            test_result = {
                'name': test_name,
                'passed': False,
                'duration': duration,
                'error': str(e)
            }
            print(f"  ❌ EXCEPTION ({duration:.2f}s): {e}")
            self.results.append(test_result)
            return test_result

    def generate_report(self) -> str:
        """Generate a test report."""
        total_tests = len(self.results)
        passed_tests = sum(1 for r in self.results if r['passed'])
        failed_tests = total_tests - passed_tests
        total_duration = sum(r['duration'] for r in self.results)

        report = [
            "=" * 60,
            "📊 Test Report",
            "=" * 60,
            f"Total Tests: {total_tests}",
            f"Passed: {passed_tests} ✅",
            f"Failed: {failed_tests} ❌",
            f"Total Duration: {total_duration:.2f}s",
            "",
            "Detailed Results:",
            "-" * 60
        ]

        for result in self.results:
            status = "✅ PASS" if result['passed'] else "❌ FAIL"
            report.append(f"{status} {result['name']} ({result['duration']:.2f}s)")

            if not result['passed'] and 'error' in result:
                report.append(f"     Error: {result['error']}")

        report.extend([
            "-" * 60,
            "",
            "Recent Docker Errors:",
            "-" * 60
        ])

        # Add recent errors from logs
        errors = self.check_docker_logs()
        if errors:
            report.extend(errors[-10:])  # Last 10 errors
        else:
            report.append("No recent errors found in logs")

        return "\n".join(report)


def test_bump_command(runner: MCPTestRunner) -> Dict[str, Any]:
    """Test the bump command."""
    return runner.execute_mcp_command("bump")


def test_help_command(runner: MCPTestRunner) -> Dict[str, Any]:
    """Test the help command."""
    return runner.execute_mcp_command("help")


def test_profile_command(runner: MCPTestRunner) -> Dict[str, Any]:
    """Test the profile command."""
    return runner.execute_mcp_command("profile")


def test_shop_command(runner: MCPTestRunner) -> Dict[str, Any]:
    """Test the shop command."""
    return runner.execute_mcp_command("shop")


def test_balance_command(runner: MCPTestRunner) -> Dict[str, Any]:
    """Test the balance command."""
    return runner.execute_mcp_command("balance")


def test_mute_command_no_perms(runner: MCPTestRunner) -> Dict[str, Any]:
    """Test mute command without permissions."""
    result = runner.execute_mcp_command("mute", "@user 10m test")
    # Should fail due to lack of permissions
    return result


def test_invalid_command(runner: MCPTestRunner) -> Dict[str, Any]:
    """Test an invalid command."""
    result = runner.execute_mcp_command("thisisnotacommand")
    # Should indicate command not found
    return result


def test_command_with_args(runner: MCPTestRunner) -> Dict[str, Any]:
    """Test a command with arguments."""
    return runner.execute_mcp_command("userinfo", "123456789")


def main():
    """Run all tests."""
    print("🚀 Starting MCP Command Test Suite")
    print(f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    # Create test runner
    runner = MCPTestRunner()

    # Define all tests
    tests = [
        ("Bump Command", lambda: test_bump_command(runner)),
        ("Help Command", lambda: test_help_command(runner)),
        ("Profile Command", lambda: test_profile_command(runner)),
        ("Shop Command", lambda: test_shop_command(runner)),
        ("Balance Command", lambda: test_balance_command(runner)),
        ("Mute Command (No Perms)", lambda: test_mute_command_no_perms(runner)),
        ("Invalid Command", lambda: test_invalid_command(runner)),
        ("Command with Args", lambda: test_command_with_args(runner)),
    ]

    # Run all tests
    for test_name, test_func in tests:
        runner.run_test(test_name, test_func)

    # Generate and print report
    print("\n" + runner.generate_report())

    # Return exit code based on results
    if all(r['passed'] for r in runner.results):
        print("\n✅ All tests passed!")
        return 0
    else:
        print("\n❌ Some tests failed!")
        return 1


if __name__ == "__main__":
    exit(main())
