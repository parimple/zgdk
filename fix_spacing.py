#!/usr/bin/env python
"""Script to fix spacing issues (E302, E306, E402, E128)."""

from pathlib import Path


def fix_e302(file_path, line_num):
    """Fix E302: expected 2 blank lines, found 1."""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            lines = f.readlines()

        if 0 <= line_num - 1 < len(lines):
            # Insert an extra blank line before the current line
            lines.insert(line_num - 1, "\n")

            with open(file_path, "w", encoding="utf-8") as f:
                f.writelines(lines)
            return True
    except Exception as e:
        print(f"Error fixing E302 in {file_path}:{line_num}: {e}")
    return False


def fix_e306(file_path, line_num):
    """Fix E306: expected 1 blank line before a nested definition, found 0."""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            lines = f.readlines()

        if 0 <= line_num - 1 < len(lines):
            # Insert a blank line before the current line
            lines.insert(line_num - 1, "\n")

            with open(file_path, "w", encoding="utf-8") as f:
                f.writelines(lines)
            return True
    except Exception as e:
        print(f"Error fixing E306 in {file_path}:{line_num}: {e}")
    return False


def main():
    """Main function."""
    # List of E302 errors
    e302_errors = [
        ("tests/mcp/commands/test_commands.py", 41),
        ("tests/mcp/commands/test_commands_detailed.py", 47),
        ("tests/mcp/commands/test_misc_commands.py", 44),
        ("tests/mcp/commands/test_mod_commands.py", 42),
        ("tests/mcp/commands/test_voice_commands.py", 44),
        ("tests/mcp/utils/test_commands_mcp.py", 43),
        ("tests/mcp/utils/test_voice_commands_mcp.py", 13),
        ("tests/mcp/utils/test_voice_commands_mcp.py", 68),
    ]

    # Fix E302 errors
    fixed_count = 0
    for file_path, line_num in e302_errors:
        if Path(file_path).exists():
            if fix_e302(file_path, line_num):
                print(f"Fixed E302 in {file_path}:{line_num}")
                fixed_count += 1

    # Fix E306 error
    if Path("tests/utils/commands_stub.py").exists():
        if fix_e306("tests/utils/commands_stub.py", 96):
            print("Fixed E306 in tests/utils/commands_stub.py:96")
            fixed_count += 1

    print(f"\nFixed {fixed_count} spacing issues")


if __name__ == "__main__":
    main()
