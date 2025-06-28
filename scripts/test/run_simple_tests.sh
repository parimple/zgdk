#!/bin/bash
# Simple test runner without complex HTML reporting

echo "🧪 Simple Test Runner for zaGadka Discord Bot"
echo "=============================================="

# Set up environment
export PYTHONPATH="/home/ubuntu/Projects/zgdk:$PYTHONPATH"
cd /home/ubuntu/Projects/zgdk

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}📋 Running Unit Tests${NC}"
if cd tests && pytest unit/ -m unit -v --tb=short; then
    echo -e "${GREEN}✅ Unit Tests: PASSED${NC}"
    unit_result="PASS"
else
    echo -e "${RED}❌ Unit Tests: FAILED${NC}"
    unit_result="FAIL"
fi

echo ""
echo -e "${BLUE}📋 Running Integration Tests${NC}"
if cd ../tests && pytest integration/ -m integration -v --tb=short; then
    echo -e "${GREEN}✅ Integration Tests: PASSED${NC}"
    integration_result="PASS"
else
    echo -e "${RED}❌ Integration Tests: FAILED${NC}"
    integration_result="FAIL"
fi

echo ""
echo -e "${BLUE}📋 Running Health Check${NC}"
cd ..
if ./scripts/docker/health_check.sh > /dev/null 2>&1; then
    echo -e "${GREEN}✅ Docker Health: GOOD${NC}"
    health_result="PASS"
else
    echo -e "${RED}❌ Docker Health: ISSUES${NC}"
    health_result="FAIL"
fi

echo ""
echo "=============================================="
echo -e "${BLUE}📊 Test Summary${NC}"
echo "Unit Tests:        $unit_result"
echo "Integration Tests: $integration_result"  
echo "Docker Health:     $health_result"
echo ""

if [[ "$unit_result" == "PASS" && "$health_result" == "PASS" ]]; then
    echo -e "${GREEN}🎉 Core functionality is working!${NC}"
    echo "✅ Testing framework is operational"
    echo "✅ Bot is healthy and running"
    exit 0
else
    echo -e "${RED}⚠️  Some issues detected${NC}"
    echo "🔧 Check individual test results above"
    exit 1
fi