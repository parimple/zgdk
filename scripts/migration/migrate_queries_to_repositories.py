#!/usr/bin/env python3
"""
Script to help migrate from datasources.queries to core.repositories.
"""

import os
import re
from pathlib import Path


# Mapping of queries to repositories
QUERY_TO_REPO_MAP = {
    "ActivityQueries": "ActivityRepository",
    "AutoKickQueries": "AutoKickRepository",
    "ChannelQueries": "ChannelRepository",
    "InviteQueries": "InviteRepository",
    "MemberQueries": "MemberRepository",
    "MessageQueries": "MessageRepository",
    "ModerationQueries": "ModerationRepository",
    "NotificationQueries": "NotificationRepository",
    "PaymentQueries": "PaymentRepository",
    "RoleQueries": "RoleRepository",
}

# Files to skip
SKIP_FILES = {
    "backup_refactored",
    "__pycache__",
    ".venv",
    "scripts/migration",
}


def should_skip_file(file_path: Path) -> bool:
    """Check if file should be skipped."""
    path_str = str(file_path)
    for skip_pattern in SKIP_FILES:
        if skip_pattern in path_str:
            return True
    return False


def migrate_imports(content: str) -> tuple[str, list[str]]:
    """Migrate imports from queries to repositories."""
    changes = []
    
    # Pattern to match datasources.queries imports
    import_pattern = re.compile(
        r'from datasources\.queries import ([^;\n]+)'
    )
    
    for match in import_pattern.finditer(content):
        import_line = match.group(0)
        imports = match.group(1)
        
        # Split multiple imports
        query_imports = [i.strip() for i in imports.split(',')]
        
        # Separate queries that have repository equivalents
        repo_imports = []
        remaining_queries = []
        
        for query in query_imports:
            query_name = query.strip()
            if query_name in QUERY_TO_REPO_MAP:
                repo_imports.append(QUERY_TO_REPO_MAP[query_name])
            else:
                remaining_queries.append(query_name)
        
        # Build new import lines
        new_lines = []
        if repo_imports:
            new_lines.append(f"from core.repositories import {', '.join(repo_imports)}")
        if remaining_queries:
            new_lines.append(f"from datasources.queries import {', '.join(remaining_queries)}")
        
        if new_lines:
            new_import = '\n'.join(new_lines)
            content = content.replace(import_line, new_import)
            changes.append(f"Replaced: {import_line}")
            changes.append(f"With: {new_import}")
    
    return content, changes


def migrate_usage(content: str) -> tuple[str, list[str]]:
    """Migrate usage of queries to repositories."""
    changes = []
    
    # Pattern to match static method calls
    for query_name, repo_name in QUERY_TO_REPO_MAP.items():
        # Pattern for static method calls like QueryClass.method()
        static_pattern = re.compile(
            rf'\b{query_name}\.(\w+)\s*\('
        )
        
        matches = list(static_pattern.finditer(content))
        if matches:
            changes.append(f"Found {len(matches)} usages of {query_name}")
            
            # Note: Repository pattern requires instantiation
            # This is a complex migration that needs manual review
            for match in matches:
                line_start = content.rfind('\n', 0, match.start()) + 1
                line_end = content.find('\n', match.end())
                if line_end == -1:
                    line_end = len(content)
                line = content[line_start:line_end]
                changes.append(f"  Needs manual migration: {line.strip()}")
    
    return content, changes


def process_file(file_path: Path) -> list[str]:
    """Process a single file."""
    if should_skip_file(file_path):
        return []
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception as e:
        return [f"Error reading {file_path}: {e}"]
    
    # Check if file imports from datasources.queries
    if 'from datasources.queries import' not in content:
        return []
    
    changes = [f"\n=== Processing {file_path} ==="]
    
    # Migrate imports
    new_content, import_changes = migrate_imports(content)
    changes.extend(import_changes)
    
    # Check for usage that needs migration
    _, usage_changes = migrate_usage(content)
    changes.extend(usage_changes)
    
    # Write back if changes were made
    if import_changes:
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(new_content)
            changes.append("✓ File updated")
        except Exception as e:
            changes.append(f"✗ Error writing file: {e}")
    
    return changes


def main():
    """Main function."""
    print("Starting migration from datasources.queries to core.repositories...")
    
    # Find all Python files
    root_path = Path("/home/ubuntu/Projects/zgdk")
    py_files = list(root_path.rglob("*.py"))
    
    all_changes = []
    files_processed = 0
    
    for py_file in py_files:
        changes = process_file(py_file)
        if changes:
            all_changes.extend(changes)
            files_processed += 1
    
    # Print summary
    print(f"\nProcessed {files_processed} files")
    print("\nDetailed changes:")
    for change in all_changes:
        print(change)
    
    print("\n⚠️  IMPORTANT: This script only updates imports.")
    print("You need to manually update the usage patterns because:")
    print("- Queries use static methods: QueryClass.method(session, ...)")
    print("- Repositories need instantiation: repo = RepoClass(session); await repo.method(...)")
    print("\nSearch for 'Needs manual migration' above to find specific lines to update.")


if __name__ == "__main__":
    main()