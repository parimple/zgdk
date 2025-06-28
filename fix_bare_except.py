#!/usr/bin/env python
"""Script to fix bare except clauses (E722)."""

import ast
import re
from pathlib import Path


def fix_bare_except(file_path):
    """Fix bare except clauses in a Python file."""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Fix bare except with simple regex
        # Match "except:" with optional whitespace and comment
        pattern = r"(\s*)except\s*:(.*)"

        def replacer(match):
            indent = match.group(1)
            rest = match.group(2)
            return f"{indent}except Exception:{rest}"

        new_content = re.sub(pattern, replacer, content)

        if new_content != content:
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(new_content)
            print(f"Fixed bare except in {file_path}")
            return True
    except Exception as e:
        print(f"Error processing {file_path}: {e}")
    return False


def main():
    """Main function."""
    files_with_bare_except = [
        "cogs/commands/dev.py",
        "cogs/commands/enhanced_moderation.py",
        "cogs/commands/mod/ai_mod_commands.py",
        "cogs/commands/premium/color_commands.py",
        "cogs/commands/team/member_management.py",
        "cogs/commands/team/team_management.py",
        "cogs/events/error_handler.py",
        "cogs/events/member_join/member_join_event.py",
        "core/ai/color_parser.py",
        "core/ai/duration_parser.py",
        "core/ai/moderation_assistant.py",
        "utils/message_senders/base.py",
        "utils/role_sale.py",
    ]

    fixed_count = 0
    for file_path in files_with_bare_except:
        if Path(file_path).exists():
            if fix_bare_except(file_path):
                fixed_count += 1

    print(f"\nFixed {fixed_count} files with bare except clauses")


if __name__ == "__main__":
    main()
