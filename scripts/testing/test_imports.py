#!/usr/bin/env python3
"""Test script to check import structure and identify circular dependencies."""

import sys
import traceback
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def test_import(module_name):
    """Test importing a module and return success status."""
    try:
        print(f"\n{'='*60}")
        print(f"Testing import: {module_name}")
        print('='*60)
        
        # Clear any previously imported modules to test fresh imports
        if module_name in sys.modules:
            del sys.modules[module_name]
        
        # Try to import the module
        module = __import__(module_name, fromlist=[''])
        print(f"✓ Successfully imported: {module_name}")
        
        # List what's in the module
        if hasattr(module, '__all__'):
            print(f"  Exports: {', '.join(module.__all__)}")
        
        return True, None
        
    except Exception as e:
        print(f"✗ Failed to import: {module_name}")
        print(f"  Error: {type(e).__name__}: {str(e)}")
        print("\nTraceback:")
        traceback.print_exc()
        return False, str(e)

def main():
    """Run import tests for all core modules."""
    print("Discord Bot Import Structure Test")
    print("=" * 80)
    
    # Test modules in dependency order
    test_modules = [
        # Core infrastructure
        "core.unit_of_work",
        "core.exceptions",
        "core.error_handler",
        
        # Base protocols and interfaces
        "core.interfaces",
        
        # Container
        "core.containers.service_container",
        
        # Repositories (data layer)
        "core.repositories",
        "core.repositories.base_repository",
        "core.repositories.member_repository",
        "core.repositories.role_repository",
        "core.repositories.premium_repository",
        "core.repositories.message_repository",
        "core.repositories.moderation_repository",
        "core.repositories.payment_repository",
        "core.repositories.activity_repository",
        "core.repositories.invite_repository",
        
        # Services (business logic layer)
        "core.services",
        "core.services.base_service",
        "core.services.member_service",
        "core.services.role_service",
        "core.services.premium_service",
        "core.services.moderation_service",
        "core.services.consolidated_premium_service",
        "core.services.embed_builder_service",
        "core.services.message_formatter_service",
        "core.services.message_sender_service",
        "core.services.notification_service",
        "core.services.payment_processor_service",
        "core.services.activity_tracking_service",
        "core.services.currency_service",
        "core.services.permission_service",
        "core.services.team_management_service",
        
        # Main entry point
        "main",
        
        # Utilities
        "utils.moderation.mute_manager",
        "utils.premium",
        "utils.role_manager",
        
        # Commands
        "cogs.commands.info",
        "cogs.commands.mod",
        "cogs.commands.premium",
        "cogs.commands.voice",
        "cogs.commands.team",
        
        # Events
        "cogs.events.on_message",
        "cogs.events.on_command",
        "cogs.events.on_task",
        "cogs.events.on_voice_state_update",
        "cogs.events.bump",
        "cogs.events.member_join",
        
        # Views
        "cogs.views.shop_views",
        "cogs.ui.shop_embeds",
    ]
    
    results = []
    failed_modules = []
    
    for module in test_modules:
        success, error = test_import(module)
        results.append((module, success, error))
        if not success:
            failed_modules.append((module, error))
    
    # Summary
    print("\n" + "=" * 80)
    print("IMPORT TEST SUMMARY")
    print("=" * 80)
    
    successful = sum(1 for _, success, _ in results if success)
    failed = len(results) - successful
    
    print(f"\nTotal modules tested: {len(results)}")
    print(f"✓ Successful imports: {successful}")
    print(f"✗ Failed imports: {failed}")
    
    if failed_modules:
        print("\nFailed Modules:")
        for module, error in failed_modules:
            print(f"  - {module}: {error.split(':')[0] if ':' in error else error}")
    
    # Check for circular dependencies by analyzing import errors
    print("\n" + "=" * 80)
    print("CIRCULAR DEPENDENCY ANALYSIS")
    print("=" * 80)
    
    circular_suspects = []
    for module, error in failed_modules:
        if "circular import" in error.lower() or "cannot import name" in error.lower():
            circular_suspects.append(module)
    
    if circular_suspects:
        print(f"\nPotential circular dependencies detected in:")
        for module in circular_suspects:
            print(f"  - {module}")
    else:
        print("\nNo obvious circular dependencies detected.")
    
    # Test specific import chains that might be problematic
    print("\n" + "=" * 80)
    print("TESTING SPECIFIC IMPORT CHAINS")
    print("=" * 80)
    
    # Test service container import chain
    print("\nTesting ServiceContainer import chain:")
    try:
        from core.containers.service_container import ServiceContainer
        print("✓ ServiceContainer imports successfully")
    except Exception as e:
        print(f"✗ ServiceContainer import failed: {e}")
    
    # Test unit of work import chain
    print("\nTesting UnitOfWork import chain:")
    try:
        from core.unit_of_work import UnitOfWork
        print("✓ UnitOfWork imports successfully")
    except Exception as e:
        print(f"✗ UnitOfWork import failed: {e}")
    
    # Test main bot class
    print("\nTesting main Zagadka class:")
    try:
        from main import Zagadka
        print("✓ Zagadka class imports successfully")
    except Exception as e:
        print(f"✗ Zagadka class import failed: {e}")
    
    return failed == 0

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)