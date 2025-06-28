#!/usr/bin/env python3
"""Script to migrate currency imports from utils to core.services."""

import os
import re

def update_currency_imports(file_path):
    """Update currency imports in a single file."""
    with open(file_path, 'r') as f:
        content = f.read()
    
    # Replace direct imports
    old_import = "from utils.currency import"
    new_import = "from core.services.currency_service import CurrencyService"
    
    if old_import in content:
        # Check what's imported
        import_match = re.search(r'from utils\.currency import (.+)', content)
        if import_match:
            imports = import_match.group(1).strip()
            
            # Replace the import
            content = content.replace(import_match.group(0), new_import)
            
            # Add instantiation if needed
            if "CURRENCY_UNIT" in imports:
                # Add at the top of the file after imports
                lines = content.split('\n')
                import_index = -1
                for i, line in enumerate(lines):
                    if line.startswith('from ') or line.startswith('import '):
                        import_index = i
                
                # Insert CURRENCY_UNIT definition after imports
                if import_index >= 0:
                    # Find first non-import line
                    insert_index = import_index + 1
                    while insert_index < len(lines) and (lines[insert_index].startswith('from ') or 
                                                        lines[insert_index].startswith('import ') or 
                                                        lines[insert_index].strip() == ''):
                        insert_index += 1
                    
                    lines.insert(insert_index, '')
                    lines.insert(insert_index + 1, '# Currency constant')
                    lines.insert(insert_index + 2, 'CURRENCY_UNIT = CurrencyService.CURRENCY_UNIT')
                    content = '\n'.join(lines)
            
            # Replace g_to_pln calls
            content = re.sub(r'\bg_to_pln\(', 'CurrencyService().g_to_pln(', content)
        
        # Write back
        with open(file_path, 'w') as f:
            f.write(content)
        
        print(f"Updated: {file_path}")
        return True
    
    return False

# Files to update
files_to_update = [
    "/home/ubuntu/Projects/zgdk/cogs/commands/info/user/views.py",
    "/home/ubuntu/Projects/zgdk/cogs/commands/info/user/embed_builders.py",
    "/home/ubuntu/Projects/zgdk/cogs/commands/info/user_info_original.py",
    "/home/ubuntu/Projects/zgdk/cogs/events/on_task.py",
    "/home/ubuntu/Projects/zgdk/cogs/events/on_payment.py",
    "/home/ubuntu/Projects/zgdk/utils/role_sale.py"
]

print("Starting currency import migration...")
updated_count = 0

for file_path in files_to_update:
    if os.path.exists(file_path):
        if update_currency_imports(file_path):
            updated_count += 1
    else:
        print(f"File not found: {file_path}")

print(f"\nMigration complete. Updated {updated_count} files.")