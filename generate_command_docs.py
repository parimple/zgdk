#!/usr/bin/env python3
"""
Generate documentation for all bot commands by analyzing cogs.

This helps identify what commands are available for testing.
"""

import re
from datetime import datetime
from pathlib import Path
from typing import Dict, List


class CommandDocGenerator:
    """Generate documentation for Discord bot commands."""

    def __init__(self, cogs_dir: str = "cogs/commands"):
        self.cogs_dir = Path(cogs_dir)
        self.commands: List[Dict[str, Any]] = []

    def extract_commands_from_file(self, filepath: Path) -> List[Dict]:
        """Extract command definitions from a Python file."""
        commands = []

        try:
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()

            # Find all @commands.hybrid_command decorators
            hybrid_pattern = r"@commands\.hybrid_command\s*\((.*?)\)"
            command_pattern = r"@commands\.command\s*\((.*?)\)"

            # Extract command definitions
            for pattern in [hybrid_pattern, command_pattern]:
                for match in re.finditer(pattern, content, re.DOTALL):
                    decorator_args = match.group(1)

                    # Extract command name
                    name_match = re.search(r'name\s*=\s*["\']([^"\']+)["\']', decorator_args)
                    if not name_match:
                        # Look for positional argument
                        name_match = re.search(r'^["\']([^"\']+)["\']', decorator_args.strip())

                    if name_match:
                        command_name = name_match.group(1)

                        # Extract aliases
                        aliases = []
                        aliases_match = re.search(r"aliases\s*=\s*\[(.*?)\]", decorator_args)
                        if aliases_match:
                            aliases_str = aliases_match.group(1)
                            aliases = [a.strip("\"'") for a in re.findall(r'["\']([^"\']+)["\']', aliases_str)]

                        # Extract description
                        desc_match = re.search(r'description\s*=\s*["\']([^"\']+)["\']', decorator_args)
                        description = desc_match.group(1) if desc_match else "No description"

                        # Find the function definition
                        func_pattern = r"def\s+(\w+)\s*\(.*?\):"
                        func_matches = list(re.finditer(func_pattern, content[match.end() :]))
                        if func_matches:
                            func_matches[0].group(1)

                            # Try to extract parameters
                            func_start = match.end() + func_matches[0].start()
                            func_def = content[func_start : content.find("\n", func_start)]

                            # Extract parameters (simplified)
                            params = []
                            param_match = re.search(r"\(self,\s*ctx[^,]*,?\s*(.*?)\)", func_def)
                            if param_match and param_match.group(1):
                                param_str = param_match.group(1)
                                # Simple parameter extraction
                                for param in param_str.split(","):
                                    param = param.strip()
                                    if param and not param.startswith("*"):
                                        param_name = param.split(":")[0].split("=")[0].strip()
                                        params.append(param_name)

                            commands.append(
                                {
                                    "name": command_name,
                                    "aliases": aliases,
                                    "description": description,
                                    "file": str(filepath.relative_to(Path.cwd())),
                                    "parameters": params,
                                    "cog": filepath.stem,
                                }
                            )

        except Exception as e:
            print(f"Error processing {filepath}: {e}")

        return commands

    def scan_all_cogs(self):
        """Scan all cog files for commands."""
        # Scan main commands directory
        for filepath in self.cogs_dir.rglob("*.py"):
            if filepath.name != "__init__.py":
                commands = self.extract_commands_from_file(filepath)
                self.commands.extend(commands)

        # Also scan other cog directories
        other_dirs = ["cogs/events", "cogs/views"]
        for dir_path in other_dirs:
            path = Path(dir_path)
            if path.exists():
                for filepath in path.rglob("*.py"):
                    if filepath.name != "__init__.py":
                        commands = self.extract_commands_from_file(filepath)
                        self.commands.extend(commands)

    def generate_markdown(self) -> str:
        """Generate markdown documentation."""
        doc = []
        doc.append("# Discord Bot Commands")
        doc.append(f"\nGenerated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        doc.append(f"\nTotal commands found: {len(self.commands)}")
        doc.append("\n---\n")

        # Group by cog
        cogs: Dict[str, List[Dict[str, Any]]] = {}
        for cmd in self.commands:
            cog = cmd["cog"]
            if cog not in cogs:
                cogs[cog] = []
            cogs[cog].append(cmd)

        # Generate documentation for each cog
        for cog_name, commands in sorted(cogs.items()):
            doc.append(f"## {cog_name.title().replace('_', ' ')}")
            doc.append(f"\nFile: `{commands[0]['file']}`")
            doc.append("\n### Commands:\n")

            for cmd in sorted(commands, key=lambda x: x["name"]):
                doc.append(f"#### /{cmd['name']}")

                if cmd["aliases"]:
                    doc.append(f"**Aliases:** {', '.join(f'/{a}' for a in cmd['aliases'])}")

                doc.append(f"\n**Description:** {cmd['description']}")

                if cmd["parameters"]:
                    doc.append(f"\n**Parameters:** {', '.join(cmd['parameters'])}")

                doc.append("\n")

        return "\n".join(doc)

    def generate_test_list(self) -> str:
        """Generate a list of commands for testing."""
        test_list = []
        test_list.append("# Command Test List")
        test_list.append("\nCommands to test:\n")

        for cmd in sorted(self.commands, key=lambda x: x["name"]):
            # Basic command
            test_list.append(f"python test_command.py {cmd['name']}")

            # With example parameters if any
            if cmd["parameters"]:
                example_args = []
                for param in cmd["parameters"]:
                    if "user" in param.lower() or "member" in param.lower():
                        example_args.append("@user")
                    elif "time" in param.lower() or "duration" in param.lower():
                        example_args.append("10m")
                    elif "reason" in param.lower():
                        example_args.append('"test reason"')
                    elif "amount" in param.lower() or "count" in param.lower():
                        example_args.append("10")
                    else:
                        example_args.append(f"<{param}>")

                test_list.append(f"python test_command.py {cmd['name']} {' '.join(example_args)}")

            # Test aliases too
            for alias in cmd["aliases"]:
                test_list.append(f"python test_command.py {alias}")

        return "\n".join(test_list)


def main():
    """Generate command documentation."""

    print("📚 Generating command documentation...")

    generator = CommandDocGenerator()
    generator.scan_all_cogs()

    # Generate markdown documentation
    markdown = generator.generate_markdown()
    with open("COMMANDS.md", "w") as f:
        f.write(markdown)
    print(f"✅ Generated COMMANDS.md with {len(generator.commands)} commands")

    # Generate test list
    test_list = generator.generate_test_list()
    with open("command_test_list.txt", "w") as f:
        f.write(test_list)
    print("✅ Generated command_test_list.txt")

    # Print summary
    print("\n📊 Summary:")
    print(f"  Total commands: {len(generator.commands)}")
    print(f"  Total cogs: {len(set(cmd['cog'] for cmd in generator.commands))}")

    # Print commands by cog
    print("\n📁 Commands by cog:")
    cogs = {}
    for cmd in generator.commands:
        if cmd["cog"] not in cogs:
            cogs[cmd["cog"]] = 0
        cogs[cmd["cog"]] += 1

    for cog, count in sorted(cogs.items()):
        print(f"  {cog}: {count} commands")


if __name__ == "__main__":
    main()
