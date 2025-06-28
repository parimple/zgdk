#!/usr/bin/env python3
"""
Main test runner for Discord bot tests.
"""

import sys
import os
import unittest
import asyncio
import argparse
from typing import List, Optional

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tests.utils.client import TestClient
from tests.config import API_BASE_URL


def check_bot_connection() -> bool:
    """Check if bot is running and accessible."""
    async def check():
        client = TestClient()
        status = await client.check_status()
        await client.close()
        return "error" not in status
    
    loop = asyncio.new_event_loop()
    result = loop.run_until_complete(check())
    loop.close()
    
    return result


def discover_tests(test_modules: Optional[List[str]] = None) -> unittest.TestSuite:
    """Discover and load tests."""
    loader = unittest.TestLoader()
    
    if test_modules:
        # Load specific test modules
        suite = unittest.TestSuite()
        for module in test_modules:
            try:
                if not module.startswith("tests."):
                    module = f"tests.{module}"
                suite.addTests(loader.loadTestsFromName(module))
            except Exception as e:
                print(f"Error loading module {module}: {e}")
        return suite
    else:
        # Discover all tests
        start_dir = os.path.dirname(os.path.abspath(__file__))
        return loader.discover(start_dir, pattern="test_*.py")


def run_tests(verbosity: int = 2, failfast: bool = False, 
              test_modules: Optional[List[str]] = None) -> bool:
    """Run the test suite."""
    # Check bot connection first
    print("Checking bot connection...")
    if not check_bot_connection():
        print(f"❌ Cannot connect to bot at {API_BASE_URL}")
        print("Make sure the bot is running with command_tester cog loaded.")
        return False
    
    print("✅ Bot connection successful\n")
    
    # Discover tests
    suite = discover_tests(test_modules)
    
    # Run tests
    runner = unittest.TextTestRunner(
        verbosity=verbosity,
        failfast=failfast
    )
    
    result = runner.run(suite)
    
    # Print summary
    print("\n" + "="*70)
    print("TEST SUMMARY")
    print("="*70)
    print(f"Tests run: {result.testsRun}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    print(f"Skipped: {len(result.skipped)}")
    
    if result.wasSuccessful():
        print("\n✅ All tests passed!")
        return True
    else:
        print("\n❌ Some tests failed!")
        return False


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Run Discord bot tests")
    parser.add_argument("-v", "--verbose", action="store_true",
                       help="Increase verbosity")
    parser.add_argument("-q", "--quiet", action="store_true",
                       help="Decrease verbosity")
    parser.add_argument("-f", "--failfast", action="store_true",
                       help="Stop on first failure")
    parser.add_argument("modules", nargs="*",
                       help="Specific test modules to run (e.g., commands.test_mute_commands)")
    
    args = parser.parse_args()
    
    # Determine verbosity
    verbosity = 2
    if args.verbose:
        verbosity = 3
    elif args.quiet:
        verbosity = 1
    
    # Run tests
    success = run_tests(
        verbosity=verbosity,
        failfast=args.failfast,
        test_modules=args.modules if args.modules else None
    )
    
    # Exit with appropriate code
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()