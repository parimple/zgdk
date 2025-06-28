#!/usr/bin/env python3
"""Fix common flake8 errors automatically."""

import os
import re
import subprocess
from pathlib import Path


def fix_trailing_whitespace():
    """Remove trailing whitespace from all Python files."""
    print("Fixing trailing whitespace...")
    subprocess.run(["find", ".", "-name", "*.py", "-type", "f", "-exec", "sed", "-i", "s/[[:space:]]*$//", "{}", "+"])


def fix_blank_lines_with_whitespace():
    """Remove whitespace from blank lines."""
    print("Fixing blank lines with whitespace...")
    for py_file in Path(".").rglob("*.py"):
        if ".venv" in str(py_file) or "__pycache__" in str(py_file):
            continue

        try:
            with open(py_file, "r") as f:
                lines = f.readlines()

            fixed_lines = []
            for line in lines:
                if line.strip() == "" and len(line) > 1:
                    fixed_lines.append("\n")
                else:
                    fixed_lines.append(line)

            with open(py_file, "w") as f:
                f.writelines(fixed_lines)
        except Exception as e:
            print(f"Error processing {py_file}: {e}")


def fix_missing_newline_at_eof():
    """Ensure all Python files end with a newline."""
    print("Fixing missing newlines at end of files...")
    for py_file in Path(".").rglob("*.py"):
        if ".venv" in str(py_file) or "__pycache__" in str(py_file):
            continue

        try:
            with open(py_file, "rb") as f:
                content = f.read()

            if content and content[-1] != ord("\n"):
                with open(py_file, "ab") as f:
                    f.write(b"\n")
        except Exception as e:
            print(f"Error processing {py_file}: {e}")


def fix_f_strings_without_placeholders():
    """Convert f-strings without placeholders to regular strings."""
    print("Fixing f-strings without placeholders...")
    for py_file in Path(".").rglob("*.py"):
        if ".venv" in str(py_file) or "__pycache__" in str(py_file):
            continue

        try:
            with open(py_file, "r") as f:
                content = f.read()

            # Find f-strings without any {} placeholders
            pattern = r'f(["\'])((?:(?!\1).)*?)\1'

            def replacer(match):
                quote = match.group(1)
                string_content = match.group(2)
                if "{" not in string_content:
                    return f"{quote}{string_content}{quote}"
                return match.group(0)

            new_content = re.sub(pattern, replacer, content)

            if new_content != content:
                with open(py_file, "w") as f:
                    f.write(new_content)
                print(f"Fixed f-strings in {py_file}")
        except Exception as e:
            print(f"Error processing {py_file}: {e}")


if __name__ == "__main__":
    os.chdir("/home/ubuntu/Projects/zgdk")
    fix_trailing_whitespace()
    fix_blank_lines_with_whitespace()
    fix_missing_newline_at_eof()
    fix_f_strings_without_placeholders()
    print("Done!")
