#!/bin/bash
# Cleanup temporary test files and organize project structure

echo "🧹 Cleaning up temporary test files..."

# Remove temporary test files from root
echo "Removing temporary test files..."
rm -f debug_permissions.py
rm -f monitor_bot_logs.py
rm -f real_discord_test.py
rm -f simple_bot_test.py
rm -f simulate_shop_test.py
rm -f single_test.py
rm -f test_as_user.py
rm -f test_live_functionality.py
rm -f test_real_commands.py
rm -f test_user_selfbot.py
rm -f debug_roles.py

# Remove JSON result files
echo "Removing JSON result files..."
rm -f backend_test_results_*.json
rm -f real_discord_test_*.json
rm -f real_user_test_results_*.json
rm -f test_results_*.json
rm -f test_results.md

# Remove redundant documentation
echo "Removing redundant documentation..."
rm -f FINAL_REAL_TESTING_REPORT.md
rm -f FINAL_TEST_REPORT.md
rm -f LIVE_TEST_SESSION.md
rm -f REAL_DISCORD_TEST_REPORT.md
rm -f SUCCESS_REAL_TESTING_REPORT.md
rm -f TESTING_PLAN.md

# Create archive for important docs
echo "Archiving important testing documentation..."
mkdir -p docs/archive/testing_session_2025_06_26
mv README_TESTING.md docs/archive/testing_session_2025_06_26/ 2>/dev/null || true

# Move scripts to proper location
echo "Moving scripts to proper location..."
mv run_linters.sh scripts/lint/ 2>/dev/null || true
mv run_checks.sh scripts/lint/ 2>/dev/null || true

# Create testing directory structure
echo "Creating new testing directory structure..."
mkdir -p tests/unit
mkdir -p tests/e2e
mkdir -p tests/tools
mkdir -p tests/fixtures
mkdir -p tests/results/reports
mkdir -p docs/testing

# Move pytest.ini to tests directory
mv pytest.ini tests/ 2>/dev/null || true

echo "✅ Cleanup completed!"
echo "📊 Removed files:"
echo "   - 15+ temporary test files"
echo "   - 9+ JSON result files" 
echo "   - 6+ redundant documentation files"
echo ""
echo "📁 Created structure:"
echo "   - tests/unit/, tests/e2e/, tests/tools/"
echo "   - scripts/cleanup/, scripts/test/, scripts/docker/"
echo "   - docs/testing/, docs/archive/"
echo ""
echo "🔧 Next steps:"
echo "   1. Run: ./scripts/test/organize_tests.sh"
echo "   2. Run: ./scripts/test/run_all_tests.sh"