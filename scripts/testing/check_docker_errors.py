#!/usr/bin/env python3
"""Docker error monitoring script for refactoring process."""

import json
import os
import subprocess
from datetime import datetime
from typing import Dict, List, Set

ERROR_LOG_FILE = "docker_errors.json"
FIXED_ERRORS_FILE = "fixed_errors.json"


def get_docker_logs(tail: int = 200) -> str:
    """Get recent Docker logs."""
    try:
        result = subprocess.run(
            ["docker-compose", "logs", "app", f"--tail={tail}"], capture_output=True, text=True, timeout=10
        )
        return result.stdout
    except Exception as e:
        print(f"Error getting Docker logs: {e}")
        return ""


def parse_errors(logs: str) -> List[Dict[str, str]]:  # type: ignore[type-arg]
    """Parse errors from logs."""
    errors = []
    lines = logs.split("\n")

    error_patterns = [
        "ERROR",
        "Failed",
        "Exception",
        "Traceback",
        "AttributeError",
        "ImportError",
        "KeyError",
        "TypeError",
        "NameError",
    ]

    # Skip known non-critical errors
    skip_patterns = [
        "add_activity",  # Activity logging
        "address already in use",  # API server
        "Event loop is closed",  # Shutdown errors
    ]

    for i, line in enumerate(lines):
        # Check if line contains error
        if any(pattern in line for pattern in error_patterns):
            # Skip if it's a known non-critical error
            if any(skip in line for skip in skip_patterns):
                continue

            # Extract error info
            error_info = {"line": line.strip(), "timestamp": datetime.now().isoformat(), "context": []}

            # Get context (2 lines before and after)
            start = max(0, i - 2)
            end = min(len(lines), i + 3)
            error_info["context"] = [lines[j].strip() for j in range(start, end) if lines[j].strip()]

            # Extract file and line number if available
            if ".py" in line:
                parts = line.split()
                for part in parts:
                    if ".py" in part:
                        error_info["file"] = part
                        break

            errors.append(error_info)

    return errors  # type: ignore[return-value]


def load_existing_errors() -> Dict[str, List[Dict]]:  # type: ignore[type-arg]
    """Load existing errors from file."""
    if os.path.exists(ERROR_LOG_FILE):
        try:
            with open(ERROR_LOG_FILE, "r") as f:
                return json.load(f)  # type: ignore[no-any-return]
        except Exception:
            return {}
    return {}


def load_fixed_errors() -> Set[str]:
    """Load fixed errors from file."""
    if os.path.exists(FIXED_ERRORS_FILE):
        try:
            with open(FIXED_ERRORS_FILE, "r") as f:
                data = json.load(f)
                return set(data.get("fixed_errors", []))
        except Exception:
            return set()
    return set()


def save_errors(errors: Dict[str, List[Dict]]) -> None:
    """Save errors to file."""
    with open(ERROR_LOG_FILE, "w") as f:
        json.dump(errors, f, indent=2)


def save_fixed_errors(fixed: Set[str]) -> None:
    """Save fixed errors to file."""
    with open(FIXED_ERRORS_FILE, "w") as f:
        json.dump({"fixed_errors": list(fixed)}, f, indent=2)


def get_error_key(error: Dict[str, str]) -> str:
    """Generate unique key for error."""
    # Use file and main error message as key
    key_parts = []
    if "file" in error:
        key_parts.append(error["file"])

    # Extract main error message
    line = error["line"]
    if "ERROR" in line:
        key_parts.append(line.split("ERROR", 1)[1].strip())
    else:
        key_parts.append(line)

    return "|".join(key_parts)


def check_and_log_errors() -> Dict[str, List[Dict]]:
    """Check Docker logs for errors and log them."""
    print("🔍 Checking Docker logs for errors...")

    # Get logs
    logs = get_docker_logs()

    # Parse errors
    current_errors = parse_errors(logs)

    # Load existing errors and fixed errors
    all_errors = load_existing_errors()
    fixed_errors = load_fixed_errors()

    # Process current errors
    new_errors = []
    recurring_errors = []

    for error in current_errors:
        error_key = get_error_key(error)

        # Skip if already fixed
        if error_key in fixed_errors:
            continue

        # Check if it's a new error
        is_new = True
        for category, error_list in all_errors.items():
            if any(get_error_key(e) == error_key for e in error_list):
                is_new = False
                recurring_errors.append(error)
                break

        if is_new:
            new_errors.append(error)

    # Update error log
    if new_errors:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        all_errors[f"session_{timestamp}"] = new_errors
        save_errors(all_errors)

    # Print summary
    print("\n📊 Error Summary:")
    print(f"   Total errors found: {len(current_errors)}")
    print(f"   New errors: {len(new_errors)}")
    print(f"   Recurring errors: {len(recurring_errors)}")
    print(f"   Fixed errors (skipped): {len(fixed_errors)}")

    if new_errors:
        print("\n❌ New Errors Found:")
        for i, error in enumerate(new_errors, 1):
            print(f"\n{i}. {error['line']}")
            if "file" in error:
                print(f"   File: {error['file']}")
            if error.get("context"):
                print("   Context:")
                for line in error["context"]:
                    print(f"      {line}")

    if recurring_errors:
        print("\n⚠️  Recurring Errors (need fixing):")
        for error in recurring_errors[:5]:  # Show first 5
            print(f"   - {error['line'][:100]}...")

    return all_errors


def mark_errors_as_fixed(error_keys: List[str]) -> None:
    """Mark specific errors as fixed."""
    fixed_errors = load_fixed_errors()
    fixed_errors.update(error_keys)
    save_fixed_errors(fixed_errors)
    print(f"✅ Marked {len(error_keys)} errors as fixed")


def clear_fixed_errors() -> None:
    """Clear the fixed errors list."""
    save_fixed_errors(set())
    print("🗑️  Cleared fixed errors list")


def main():
    """Main function."""
    import sys

    if len(sys.argv) > 1:
        command = sys.argv[1]

        if command == "check":
            check_and_log_errors()
        elif command == "fixed" and len(sys.argv) > 2:
            # Mark errors as fixed by providing error keys
            error_keys = sys.argv[2:]
            mark_errors_as_fixed(error_keys)
        elif command == "clear":
            clear_fixed_errors()
        elif command == "show":
            # Show current errors
            errors = load_existing_errors()
            fixed = load_fixed_errors()
            print(f"📋 Total error sessions: {len(errors)}")
            print(f"✅ Fixed errors: {len(fixed)}")

            for session, error_list in errors.items():
                print(f"\n{session}: {len(error_list)} errors")
                for error in error_list[:3]:
                    print(f"   - {error['line'][:80]}...")
        else:
            print("Usage: python check_docker_errors.py [check|fixed <keys>|clear|show]")
    else:
        # Default: check errors
        check_and_log_errors()


if __name__ == "__main__":
    main()
