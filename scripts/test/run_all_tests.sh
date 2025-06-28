#!/bin/bash
# Run all tests with proper organization and reporting

echo "🚀 Running comprehensive test suite..."

# Set up environment
export PYTHONPATH="/home/ubuntu/Projects/zgdk:$PYTHONPATH"
cd /home/ubuntu/Projects/zgdk

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Create results directory
mkdir -p tests/results/reports

echo -e "${BLUE}📋 Test Suite Configuration${NC}"
echo "Working Directory: $(pwd)"
echo "Python Path: $PYTHONPATH"
echo "Test Directory: tests/"
echo ""

# Function to run test category
run_test_category() {
    local category=$1
    local marker=$2
    local description=$3
    
    echo -e "${BLUE}🧪 Running $description...${NC}"
    
    if pytest tests/$category/ -m $marker -v --tb=short --html=tests/results/reports/${category}_report.html --self-contained-html; then
        echo -e "${GREEN}✅ $description: PASSED${NC}"
        return 0
    else
        echo -e "${RED}❌ $description: FAILED${NC}"
        return 1
    fi
}

# Test execution
total_tests=0
passed_tests=0

echo -e "${YELLOW}=== PHASE 1: UNIT TESTS ===${NC}"
if run_test_category "unit" "unit" "Unit Tests"; then
    ((passed_tests++))
fi
((total_tests++))

echo ""
echo -e "${YELLOW}=== PHASE 2: INTEGRATION TESTS ===${NC}"
if run_test_category "integration" "integration" "Integration Tests"; then
    ((passed_tests++))
fi
((total_tests++))

echo ""
echo -e "${YELLOW}=== PHASE 3: E2E TESTS (if token available) ===${NC}"
if [ -n "$CLAUDE_BOT_TOKEN" ]; then
    if run_test_category "e2e" "e2e" "End-to-End Tests"; then
        ((passed_tests++))
    fi
    ((total_tests++))
else
    echo -e "${YELLOW}⚠️  Skipping E2E tests: CLAUDE_BOT_TOKEN not set${NC}"
fi

echo ""
echo -e "${YELLOW}=== PHASE 4: CODE QUALITY ===${NC}"
echo -e "${BLUE}🔍 Running linters...${NC}"

# Run linters if available
if [ -f "scripts/lint/run_linters.sh" ]; then
    if bash scripts/lint/run_linters.sh; then
        echo -e "${GREEN}✅ Code Quality: PASSED${NC}"
        ((passed_tests++))
    else
        echo -e "${RED}❌ Code Quality: FAILED${NC}"
    fi
    ((total_tests++))
else
    echo -e "${YELLOW}⚠️  Linters not found, skipping${NC}"
fi

echo ""
echo -e "${YELLOW}=== PHASE 5: DOCKER HEALTH CHECK ===${NC}"
echo -e "${BLUE}🐳 Checking Docker status...${NC}"

if docker-compose ps | grep -q "Up"; then
    echo -e "${GREEN}✅ Docker Services: RUNNING${NC}"
    
    # Check bot logs for errors
    if docker-compose logs app --tail=50 | grep -qi error; then
        echo -e "${YELLOW}⚠️  Bot Logs: Errors detected${NC}"
    else
        echo -e "${GREEN}✅ Bot Logs: Clean${NC}"
        ((passed_tests++))
    fi
else
    echo -e "${RED}❌ Docker Services: NOT RUNNING${NC}"
fi
((total_tests++))

# Final report
echo ""
echo -e "${BLUE}=========================${NC}"
echo -e "${BLUE}📊 FINAL TEST REPORT${NC}"
echo -e "${BLUE}=========================${NC}"
echo "Test Categories: $total_tests"
echo "Passed: $passed_tests"
echo "Failed: $((total_tests - passed_tests))"

success_rate=$((passed_tests * 100 / total_tests))
echo "Success Rate: $success_rate%"

if [ $success_rate -ge 80 ]; then
    echo -e "${GREEN}🎉 Overall Status: EXCELLENT${NC}"
    exit_code=0
elif [ $success_rate -ge 60 ]; then
    echo -e "${YELLOW}👍 Overall Status: GOOD${NC}"
    exit_code=0
else
    echo -e "${RED}⚠️  Overall Status: NEEDS ATTENTION${NC}"
    exit_code=1
fi

echo ""
echo -e "${BLUE}📄 Reports generated:${NC}"
echo "   tests/results/reports/unit_report.html"
echo "   tests/results/reports/integration_report.html"
if [ -n "$CLAUDE_BOT_TOKEN" ]; then
    echo "   tests/results/reports/e2e_report.html"
fi

echo ""
echo -e "${BLUE}🔧 Quick commands:${NC}"
echo "   Unit tests only:        pytest tests/unit/ -m unit"
echo "   Integration tests only: pytest tests/integration/ -m integration"
echo "   E2E tests only:         CLAUDE_BOT_TOKEN=xxx pytest tests/e2e/ -m e2e"
echo "   Cleanup temp files:     ./scripts/cleanup/cleanup_temp_files.sh"

exit $exit_code