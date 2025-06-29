#!/usr/bin/env python3
"""Automated error cleanup and maintenance script."""

import json
import os
import subprocess
from datetime import datetime, timedelta
from typing import Dict, List, Set

# File paths
ERROR_LOG_FILE = "/home/ubuntu/Projects/zgdk/docker_errors.json"
FIXED_ERRORS_FILE = "/home/ubuntu/Projects/zgdk/fixed_errors.json"
CLEANUP_LOG_FILE = "/home/ubuntu/Projects/zgdk/logs/error_cleanup.log"


def log_message(message: str) -> None:
    """Log message with timestamp."""
    os.makedirs(os.path.dirname(CLEANUP_LOG_FILE), exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    with open(CLEANUP_LOG_FILE, "a") as f:
        f.write(f"[{timestamp}] {message}\n")

    print(f"[{timestamp}] {message}")


def load_errors() -> Dict[str, List[Dict]]:  # type: ignore[type-arg]
    """Load error log."""
    if os.path.exists(ERROR_LOG_FILE):
        try:
            with open(ERROR_LOG_FILE, "r") as f:
                return json.load(f)  # type: ignore[no-any-return]
        except Exception:
            return {}
    return {}


def load_fixed_errors() -> Set[str]:
    """Load fixed errors."""
    if os.path.exists(FIXED_ERRORS_FILE):
        try:
            with open(FIXED_ERRORS_FILE, "r") as f:
                data = json.load(f)
                return set(data.get("fixed_errors", []))
        except Exception:
            return set()
    return set()


def save_errors(errors: Dict[str, List[Dict]]) -> None:
    """Save error log."""
    with open(ERROR_LOG_FILE, "w") as f:
        json.dump(errors, f, indent=2)


def parse_session_timestamp(session_key: str) -> datetime:
    """Parse timestamp from session key."""
    try:
        # Format: session_YYYYMMDD_HHMMSS
        timestamp_str = session_key.replace("session_", "")
        return datetime.strptime(timestamp_str, "%Y%m%d_%H%M%S")
    except Exception:
        return datetime.now()


def cleanup_old_sessions(days_to_keep: int = 7) -> int:
    """Remove error sessions older than specified days."""
    errors = load_errors()
    cutoff_date = datetime.now() - timedelta(days=days_to_keep)

    sessions_to_remove = []
    for session_key in errors.keys():
        session_date = parse_session_timestamp(session_key)
        if session_date < cutoff_date:
            sessions_to_remove.append(session_key)

    # Remove old sessions
    for session in sessions_to_remove:
        del errors[session]

    if sessions_to_remove:
        save_errors(errors)
        log_message(f"Cleaned up {len(sessions_to_remove)} old error sessions")

    return len(sessions_to_remove)


def verify_fixed_errors() -> Dict[str, bool]:
    """Verify if fixed errors are actually fixed."""
    fixed_errors = load_fixed_errors()

    # Get current Docker logs
    try:
        result = subprocess.run(
            ["docker-compose", "logs", "app", "--tail=100"], capture_output=True, text=True, timeout=10
        )
        current_logs = result.stdout
    except Exception:
        log_message("Failed to get Docker logs for verification")
        return {}

    verification_results = {}

    for error_key in fixed_errors:
        # Check if error pattern still exists in logs
        error_parts = error_key.split("|")
        still_exists = all(part in current_logs for part in error_parts if part)
        verification_results[error_key] = not still_exists

    return verification_results


def generate_error_report() -> str:
    """Generate error report."""
    errors = load_errors()
    fixed_errors = load_fixed_errors()

    report_lines = []
    report_lines.append("=" * 60)
    report_lines.append("ERROR TRACKING REPORT")
    report_lines.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    report_lines.append("=" * 60)

    # Count total errors
    total_errors = sum(len(session_errors) for session_errors in errors.values())

    report_lines.append("\n📊 SUMMARY:")
    report_lines.append(f"  Total error sessions: {len(errors)}")
    report_lines.append(f"  Total errors logged: {total_errors}")
    report_lines.append(f"  Fixed errors: {len(fixed_errors)}")

    # Recent errors
    if errors:
        recent_session = max(errors.keys(), key=lambda k: parse_session_timestamp(k))
        recent_errors = errors[recent_session]

        report_lines.append(f"\n🔴 RECENT ERRORS ({recent_session}):")
        for i, error in enumerate(recent_errors[:5], 1):
            report_lines.append(f"\n  {i}. {error['line'][:80]}...")
            if "file" in error:
                report_lines.append(f"     File: {error['file']}")

    # Fixed errors verification
    verification = verify_fixed_errors()
    if verification:
        report_lines.append("\n✅ FIXED ERRORS VERIFICATION:")
        for error_key, is_fixed in verification.items():
            status = "✓ Fixed" if is_fixed else "✗ Still occurring"
            report_lines.append(f"  {status}: {error_key[:60]}...")

    return "\n".join(report_lines)


def perform_maintenance() -> None:
    """Perform full error maintenance."""
    log_message("Starting error maintenance...")

    # 1. Clean up old sessions
    cleanup_old_sessions()

    # 2. Verify fixed errors
    verification = verify_fixed_errors()
    still_broken = [k for k, v in verification.items() if not v]

    if still_broken:
        log_message(f"Found {len(still_broken)} 'fixed' errors that are still occurring")

    # 3. Generate report
    report = generate_error_report()

    # 4. Save report
    report_file = f"/home/ubuntu/Projects/zgdk/logs/error_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    os.makedirs(os.path.dirname(report_file), exist_ok=True)

    with open(report_file, "w") as f:
        f.write(report)

    log_message(f"Error report saved to: {report_file}")

    # 5. Print summary
    print("\n" + report)

    log_message("Error maintenance completed")


def main():
    """Main function."""
    import sys

    if len(sys.argv) > 1:
        command = sys.argv[1]

        if command == "cleanup":
            # Clean up old sessions
            days = int(sys.argv[2]) if len(sys.argv) > 2 else 7
            removed = cleanup_old_sessions(days)
            print(f"Removed {removed} old error sessions")

        elif command == "verify":
            # Verify fixed errors
            verification = verify_fixed_errors()
            for error_key, is_fixed in verification.items():
                status = "✓" if is_fixed else "✗"
                print(f"{status} {error_key}")

        elif command == "report":
            # Generate report only
            report = generate_error_report()
            print(report)

        elif command == "auto":
            # Run automatic maintenance
            perform_maintenance()

        else:
            print("Usage: python error_cleanup.py [cleanup|verify|report|auto]")
    else:
        # Default: run maintenance
        perform_maintenance()


if __name__ == "__main__":
    main()
