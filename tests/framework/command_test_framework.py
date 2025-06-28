"""
Enhanced command testing framework for Discord bot commands.

This framework provides:
- Easy command execution via MCP
- Automatic response validation
- Mock data setup/teardown
- Performance metrics
- Error handling testing
- Permission testing
- Cooldown testing
"""

import asyncio
import json
import logging
import subprocess
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class CommandTestFramework:
    """Main framework for testing Discord commands."""

    def __init__(self, bot_container: str = "zgdk-mcp-1"):
        self.bot_container = bot_container
        self.test_results = []
        self.performance_metrics = {}

    async def execute_command(
        self,
        command: str,
        args: str = "",
        user_id: Optional[int] = None,
        channel_id: Optional[int] = None,
        guild_id: Optional[int] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Execute a command through MCP with timing and error handling."""
        start_time = datetime.now()

        # Build command execution string
        cmd_str = """
import asyncio
import json
from mcp_bot_server import call_tool

async def main():
    # Execute command with context
    context = {{
        'user_id': {user_id or 123456789},
        'channel_id': {channel_id or 987654321},
        'guild_id': {guild_id or 960665311701528596}
    }}

    result = await call_tool('execute_command', {{
        'command': '{command}',
        'args': '{args}',
        'context': context
    }})

    # Format response
    output = {{
        'success': True,
        'command': '{command}',
        'args': '{args}',
        'responses': []
    }}

    for r in result:
        if hasattr(r, 'type') and hasattr(r, 'text'):
            output['responses'].append({{
                'type': r.type,
                'text': r.text
            }})
        else:
            output['responses'].append(str(r))

    print(json.dumps(output))

asyncio.run(main())
"""

        # Execute via docker
        docker_cmd = [
            "docker", "exec", "-i", self.bot_container,
            "python", "-c", cmd_str
        ]

        try:
            result = subprocess.run(
                docker_cmd,
                capture_output=True,
                text=True,
                check=True,
                timeout=30
            )

            # Parse output
            output = json.loads(result.stdout.strip())

            # Add performance metrics
            end_time = datetime.now()
            execution_time = (end_time - start_time).total_seconds()

            output['execution_time'] = execution_time
            output['timestamp'] = start_time.isoformat()

            # Store metrics
            cmd_key = f"{command}_{args}".replace(" ", "_")
            if cmd_key not in self.performance_metrics:
                self.performance_metrics[cmd_key] = []
            self.performance_metrics[cmd_key].append(execution_time)

            return output

        except subprocess.TimeoutExpired:
            return {
                'success': False,
                'error': 'Command execution timeout',
                'command': command,
                'args': args
            }
        except subprocess.CalledProcessError as e:
            return {
                'success': False,
                'error': f'Command execution failed: {e.stderr}',
                'command': command,
                'args': args,
                'stdout': e.stdout,
                'stderr': e.stderr
            }
        except json.JSONDecodeError as e:
            return {
                'success': False,
                'error': f'Failed to parse command output: {e}',
                'command': command,
                'args': args,
                'raw_output': result.stdout if 'result' in locals() else None
            }
        except Exception as e:
            return {
                'success': False,
                'error': f'Unexpected error: {str(e)}',
                'command': command,
                'args': args
            }

    async def test_command_permissions(
        self,
        command: str,
        required_permissions: List[str],
        test_user_id: int = 123456789
    ) -> Dict[str, Any]:
        """Test command permission requirements."""
        results = {}

        # Test without permissions
        result_no_perms = await self.execute_command(
            command,
            user_id=test_user_id
        )
        results['no_permissions'] = result_no_perms

        # Test with each permission
        for perm in required_permissions:
            # Would need to mock user permissions here
            result_with_perm = await self.execute_command(
                command,
                user_id=test_user_id,
                mock_permissions=[perm]
            )
            results[f'with_{perm}'] = result_with_perm

        return results

    async def test_command_cooldown(
        self,
        command: str,
        cooldown_seconds: int,
        test_user_id: int = 123456789
    ) -> Dict[str, Any]:
        """Test command cooldown behavior."""
        results = {}

        # First execution
        result1 = await self.execute_command(command, user_id=test_user_id)
        results['first_execution'] = result1

        # Immediate second execution (should be on cooldown)
        result2 = await self.execute_command(command, user_id=test_user_id)
        results['during_cooldown'] = result2

        # Wait for cooldown
        await asyncio.sleep(cooldown_seconds + 1)

        # Third execution (cooldown should be over)
        result3 = await self.execute_command(command, user_id=test_user_id)
        results['after_cooldown'] = result3

        return results

    async def test_command_error_handling(
        self,
        command: str,
        invalid_args: List[str]
    ) -> Dict[str, Any]:
        """Test command error handling with invalid inputs."""
        results = {}

        for args in invalid_args:
            result = await self.execute_command(command, args=args)
            results[f'args_{args}'] = result

        return results

    def generate_test_report(self) -> str:
        """Generate a comprehensive test report."""
        report = []
        report.append("# Command Test Report")
        report.append(f"Generated at: {datetime.now().isoformat()}")
        report.append("")

        # Performance metrics
        report.append("## Performance Metrics")
        for cmd, times in self.performance_metrics.items():
            avg_time = sum(times) / len(times)
            min_time = min(times)
            max_time = max(times)
            report.append(f"- **{cmd}**: avg={avg_time:.3f}s, min={min_time:.3f}s, max={max_time:.3f}s")
        report.append("")

        # Test results
        report.append("## Test Results")
        for result in self.test_results:
            report.append(f"### {result['test_name']}")
            report.append(f"- Status: {'✅ PASSED' if result['passed'] else '❌ FAILED'}")
            report.append(f"- Duration: {result['duration']:.3f}s")
            if not result['passed']:
                report.append(f"- Error: {result['error']}")
            report.append("")

        return "\n".join(report)


class CommandTestCase:
    """Base class for command test cases."""

    def __init__(self, framework: CommandTestFramework):
        self.framework = framework
        self.setup_done = False
        self.teardown_done = False

    async def setup(self):
        """Set up test case (override in subclasses)."""
        self.setup_done = True

    async def teardown(self):
        """Tear down test case (override in subclasses)."""
        self.teardown_done = True

    async def assert_command_success(
        self,
        command: str,
        args: str = "",
        expected_response: Optional[str] = None,
        **kwargs
    ):
        """Assert that a command executes successfully."""
        result = await self.framework.execute_command(command, args, **kwargs)

        assert result['success'], f"Command failed: {result.get('error', 'Unknown error')}"

        if expected_response:
            responses = result.get('responses', [])
            assert responses, "No responses received"

            found = False
            for response in responses:
                if isinstance(response, dict):
                    if expected_response in response.get('text', ''):
                        found = True
                        break
                elif expected_response in str(response):
                    found = True
                    break

            assert found, f"Expected response '{expected_response}' not found"

        return result

    async def assert_command_fails(
        self,
        command: str,
        args: str = "",
        expected_error: Optional[str] = None,
        **kwargs
    ):
        """Assert that a command fails with expected error."""
        result = await self.framework.execute_command(command, args, **kwargs)

        # Command should either return success=False or have error in response
        if result['success']:
            # Check if response contains error message
            responses = result.get('responses', [])
            has_error = False
            for response in responses:
                if isinstance(response, dict):
                    text = response.get('text', '').lower()
                    if any(word in text for word in ['error', 'błąd', 'failed', 'nie można']):
                        has_error = True
                        break

            assert has_error, "Command succeeded when it should have failed"

        if expected_error:
            error_found = False
            error_text = result.get('error', '')

            # Check in responses too
            for response in result.get('responses', []):
                if isinstance(response, dict):
                    error_text += ' ' + response.get('text', '')

            error_found = expected_error.lower() in error_text.lower()
            assert error_found, f"Expected error '{expected_error}' not found"

        return result

    async def assert_cooldown_active(
        self,
        command: str,
        args: str = "",
        **kwargs
    ):
        """Assert that a command is on cooldown."""
        result = await self.framework.execute_command(command, args, **kwargs)

        # Check for cooldown indicators
        cooldown_found = False
        for response in result.get('responses', []):
            if isinstance(response, dict):
                text = response.get('text', '').lower()
                if any(word in text for word in ['cooldown', 'poczekaj', 'wait', 'oczekuj']):
                    cooldown_found = True
                    break

        assert cooldown_found, "Command did not indicate cooldown"
        return result


class BumpCommandTest(CommandTestCase):
    """Test case for bump commands."""

    async def test_bump_success(self):
        """Test successful bump execution."""
        result = await self.assert_command_success(
            "bump",
            expected_response="Status"
        )
        print("✅ Bump command executed successfully")

    async def test_bump_cooldown(self):
        """Test bump cooldown handling."""
        # First bump
        await self.assert_command_success("bump")

        # Second bump should show cooldown
        await self.assert_cooldown_active("bump")
        print("✅ Bump cooldown working correctly")


class ModCommandTest(CommandTestCase):
    """Test case for moderation commands."""

    async def test_mute_command(self):
        """Test mute command."""
        # Test without permissions
        await self.assert_command_fails(
            "mute",
            args="@user 10m test",
            expected_error="permissions"
        )
        print("✅ Mute permission check working")

    async def test_ban_command(self):
        """Test ban command."""
        # Test with invalid user
        await self.assert_command_fails(
            "ban",
            args="invaliduser",
            expected_error="user"
        )
        print("✅ Ban user validation working")


class ShopCommandTest(CommandTestCase):
    """Test case for shop commands."""

    async def test_shop_display(self):
        """Test shop display."""
        result = await self.assert_command_success(
            "shop",
            expected_response="Shop"
        )
        print("✅ Shop displays correctly")

    async def test_buy_item(self):
        """Test buying an item."""
        # Test buying without enough currency
        await self.assert_command_fails(
            "buy",
            args="1",
            expected_error="enough"
        )
        print("✅ Shop purchase validation working")


# Example usage function
async def run_command_tests():
    """Run all command tests."""
    framework = CommandTestFramework()

    test_cases = [
        BumpCommandTest(framework),
        ModCommandTest(framework),
        ShopCommandTest(framework),
    ]

    print("🧪 Starting command tests...")
    print("=" * 50)

    for test_case in test_cases:
        test_name = test_case.__class__.__name__
        print(f"\n📋 Running {test_name}")

        try:
            # Setup
            await test_case.setup()

            # Run all test methods
            for attr in dir(test_case):
                if attr.startswith('test_'):
                    method = getattr(test_case, attr)
                    if callable(method):
                        print(f"  ▶️ {attr}")
                        start = datetime.now()
                        try:
                            await method()
                            duration = (datetime.now() - start).total_seconds()
                            framework.test_results.append({
                                'test_name': f"{test_name}.{attr}",
                                'passed': True,
                                'duration': duration
                            })
                        except Exception as e:
                            duration = (datetime.now() - start).total_seconds()
                            framework.test_results.append({
                                'test_name': f"{test_name}.{attr}",
                                'passed': False,
                                'duration': duration,
                                'error': str(e)
                            })
                            print(f"    ❌ Failed: {e}")

            # Teardown
            await test_case.teardown()

        except Exception as e:
            print(f"  ❌ Test case failed: {e}")

    # Generate report
    print("\n" + "=" * 50)
    print(framework.generate_test_report())


if __name__ == "__main__":
    asyncio.run(run_command_tests())
