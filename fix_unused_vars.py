#!/usr/bin/env python
"""Script to fix unused variable assignments by prefixing with underscore."""

import re
from pathlib import Path


def fix_unused_variable(file_path, line_num, var_name):
    """Fix an unused variable in a specific file and line."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            
        if 0 <= line_num - 1 < len(lines):
            line = lines[line_num - 1]
            # Replace variable assignment with underscore prefix
            # Handle various assignment patterns
            patterns = [
                (rf'\b{var_name}\s*=', f'_{var_name} ='),
                (rf'for\s+{var_name}\s+in', f'for _{var_name} in'),
                (rf'except\s+.*\s+as\s+{var_name}:', f'except Exception:'),  # For except clauses
            ]
            
            new_line = line
            for pattern, replacement in patterns:
                if re.search(pattern, line):
                    new_line = re.sub(pattern, replacement, line)
                    break
                    
            if new_line != line:
                lines[line_num - 1] = new_line
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.writelines(lines)
                return True
    except Exception as e:
        print(f"Error processing {file_path}:{line_num} - {var_name}: {e}")
    return False


def main():
    """Main function to fix specific unused variables."""
    # List of unused variables from flake8 output
    unused_vars = [
        ("agent_builder/cli.py", 82, "agent"),
        ("agent_builder/factory.py", 56, "config"),
        ("agents/health_server.py", 96, "crew"),
        ("agents/support_agent.py", 117, "classification_task"),
        ("cogs/commands/developer_api.py", 213, "responses"),
        ("cogs/commands/enhanced_moderation.py", 53, "timeout_req"),
        ("cogs/commands/info/admin/role_commands.py", 85, "premium_manager"),
        ("cogs/commands/info/user/profile_helpers.py", 24, "member_service"),
        ("cogs/commands/info/user_info_original.py", 48, "member_service"),
        ("cogs/commands/mod/ai_mod_commands.py", 67, "session"),
        ("cogs/commands/mod/ai_mod_commands.py", 287, "e"),
        ("cogs/commands/ranking.py", 165, "color"),
        ("cogs/events/bump/handlers.py", 66, "guild_id"),
        ("cogs/events/bump/handlers.py", 257, "member"),
        ("cogs/events/bump/handlers.py", 310, "member"),
        ("cogs/events/bump/handlers.py", 368, "member"),
        ("cogs/events/member_join/member_join_event.py", 125, "db_member"),
        ("cogs/events/member_join/member_join_event.py", 132, "role_repo"),
        ("cogs/events/member_join/member_join_event.py", 139, "mute_role_ids"),
        ("cogs/events/member_join/role_restorer.py", 35, "db_member"),
        ("cogs/events/on_payment.py", 491, "updated_member"),
        ("cogs/events/on_task.py", 316, "recent_notifications"),
        ("core/ai/error_handler.py", 157, "error_info"),
        ("utils/message_sender_original.py", 561, "channel"),
        ("utils/message_sender_original.py", 568, "channel"),
        ("utils/message_sender_original.py", 743, "channel"),
        ("utils/moderation/message_cleaner.py", 514, "e"),
        ("utils/premium_logic.py", 294, "db_role"),
        ("utils/premium_logic.py", 362, "upgrade_cost"),
        # Test files
        ("tests/mcp/premium/test_complete_premium_cycle.py", 47, "test_color_green"),
        ("tests/mcp/premium/test_complete_premium_cycle.py", 58, "msg_deletion_confirm"),
        ("tests/mcp/premium/test_complete_premium_cycle.py", 59, "msg_color_removed"),
        ("tests/mcp/premium/test_complete_premium_cycle.py", 60, "msg_shop_opened"),
        ("tests/mcp/premium/test_debug_premium.py", 13, "owner_id"),
        ("tests/mcp/premium/test_premium_with_logging.py", 16, "color"),
        ("tests/mcp/utils/mcp_client.py", 29, "request_json"),
        ("tests/models/test_shop_business_logic.py", 121, "payment_id"),
        ("tests/models/test_shop_business_logic.py", 122, "user_id"),
        ("tests/models/test_shop_data_models.py", 125, "premium_role_data"),
    ]
    
    fixed_count = 0
    for file_path, line_num, var_name in unused_vars:
        if Path(file_path).exists():
            if fix_unused_variable(file_path, line_num, var_name):
                print(f"Fixed unused variable '{var_name}' in {file_path}:{line_num}")
                fixed_count += 1
                
    print(f"\nFixed {fixed_count} unused variables")


if __name__ == "__main__":
    main()