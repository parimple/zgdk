#!/usr/bin/env python3
"""
Quick command tester for Discord bot commands via MCP.

Usage:
    python test_command.py <command> [args]

Examples:
    python test_command.py bump
    python test_command.py help
    python test_command.py profile
    python test_command.py shop
    python test_command.py userinfo 123456789
"""

import argparse
import json
import subprocess


def test_command(command: str, args: str = "") -> dict:
    """Test a single command via MCP."""

    # Create the test script
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

    except Exception as e:
        output = {{
            'success': False,
            'command': '{command}',
            'args': '{args}',
            'error': str(e)
        }}
        print(json.dumps(output))

asyncio.run(main())
"""

    # Execute in Docker
    cmd = ["docker", "exec", "-i", "zgdk-mcp-1", "python", "-c", script]

    print(f"🧪 Testing command: /{command} {args}")
    print("=" * 50)

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30, check=True)

        # Parse and display result
        if result.stdout:
            data = json.loads(result.stdout.strip())

            if data.get("success"):
                print("✅ Command executed successfully!")
            else:
                print("❌ Command failed!")
                if "error" in data:
                    print(f"Error: {data['error']}")

            print("\n📝 Responses:")
            for i, response in enumerate(data.get("responses", [])):
                print(f"\n--- Response {i+1} ---")
                if isinstance(response, dict):
                    print(f"Type: {response.get('type', 'unknown')}")
                    print(f"Text: {response.get('text', '')[:500]}")
                    if len(response.get("text", "")) > 500:
                        print("... (truncated)")
                else:
                    print(str(response)[:500])
                    if len(str(response)) > 500:
                        print("... (truncated)")

            return data

        else:
            print("❌ No output from command")
            return {"success": False, "error": "No output"}

    except subprocess.TimeoutExpired:
        print("❌ Command timed out (30s)")
        return {"success": False, "error": "Timeout"}

    except subprocess.CalledProcessError as e:
        print(f"❌ Docker execution failed: {e}")
        if e.stdout:
            print(f"Stdout: {e.stdout}")
        if e.stderr:
            print(f"Stderr: {e.stderr}")
        return {"success": False, "error": str(e)}

    except json.JSONDecodeError as e:
        print(f"❌ Failed to parse output: {e}")
        if "result" in locals() and result.stdout:
            print(f"Raw output: {result.stdout}")
        return {"success": False, "error": "JSON parse error"}

    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return {"success": False, "error": str(e)}


def check_recent_errors(lines: int = 20):
    """Check recent Docker logs for errors."""
    print("\n📋 Recent Docker errors:")
    print("-" * 50)

    cmd = ["docker-compose", "logs", "app", f"--tail={lines}"]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True)

        # Filter for errors
        error_count = 0
        for line in result.stdout.split("\n"):
            if any(word in line.lower() for word in ["error", "failed", "exception"]):
                print(line)
                error_count += 1

        if error_count == 0:
            print("No recent errors found")

    except Exception as e:
        print(f"Failed to check logs: {e}")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Test Discord bot commands via MCP",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python test_command.py bump
  python test_command.py help
  python test_command.py profile
  python test_command.py shop
  python test_command.py userinfo 123456789
  python test_command.py mute "@user" "10m" "spam"
        """,
    )

    parser.add_argument("command", help="The command to test (without prefix)")
    parser.add_argument("args", nargs="*", help="Command arguments")
    parser.add_argument("--check-logs", action="store_true", help="Check Docker logs for recent errors")

    args = parser.parse_args()

    # Join arguments
    command_args = " ".join(args.args) if args.args else ""

    # Test the command
    result = test_command(args.command, command_args)

    # Check logs if requested
    if args.check_logs:
        check_recent_errors()

    # Return appropriate exit code
    return 0 if result.get("success") else 1


if __name__ == "__main__":
    exit(main())
