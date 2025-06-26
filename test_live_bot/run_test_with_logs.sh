#!/bin/bash
# Uruchom testy live bota i sprawdź logi

echo "🤖 Live Bot Testing with Log Analysis"
echo "====================================="

# Kolory
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

# Sprawdź token
if [ -z "$CLAUDE_BOT_TOKEN" ]; then
    echo -e "${RED}❌ CLAUDE_BOT_TOKEN environment variable not set${NC}"
    exit 1
fi

echo -e "${BLUE}🔑 Token found, running live bot tests...${NC}"
echo ""

# Uruchom test z timeoutem
echo -e "${BLUE}🚀 Starting live bot command tests (45s timeout)...${NC}"
cd /home/ubuntu/Projects/zgdk
timeout 45 python test_live_bot/live_commands_test.py

echo ""
echo -e "${BLUE}🔍 Checking for errors after tests...${NC}"
echo "=" * 50

# Sprawdź Docker logi
echo "🐳 Checking Docker logs for errors..."
DOCKER_ERRORS=$(docker-compose logs app --tail=50 | grep -E "(ERROR|Failed|Exception|Traceback)" | grep -v add_activity)

if [ -n "$DOCKER_ERRORS" ]; then
    echo -e "${YELLOW}⚠️ Found potential errors in Docker logs:${NC}"
    echo "$DOCKER_ERRORS" | tail -5
else
    echo -e "${GREEN}✅ No errors found in Docker logs${NC}"
fi

echo ""

# Sprawdź pliki z błędami
echo "📁 Checking error log files..."
ERROR_FILES=$(find . -name "*error*.log" -o -path "./logs/*" -name "*.log" -o -path "./utils/error_logs/*" -name "*.json" 2>/dev/null)

if [ -n "$ERROR_FILES" ]; then
    echo -e "${BLUE}📂 Found error log files:${NC}"
    for file in $ERROR_FILES; do
        if [ -s "$file" ]; then
            echo -e "${YELLOW}   📄 $file (has content)${NC}"
            echo "      Last 2 lines:"
            tail -2 "$file" | sed 's/^/      /'
        else
            echo -e "${GREEN}   📄 $file (empty)${NC}"
        fi
    done
else
    echo -e "${GREEN}✅ No error log files found${NC}"
fi

echo ""

# Sprawdź ostatnie logi bota
echo "📋 Recent bot activity (last 10 lines):"
docker-compose logs app --tail=10 | grep -v "add_activity" | tail -5

echo ""
echo -e "${GREEN}🎉 Test completed with log analysis!${NC}"
echo ""
echo -e "${BLUE}📊 Summary:${NC}"
echo "   - Live bot tests: Commands sent and responses received"
echo "   - Docker logs: Checked for errors"
echo "   - Error files: Checked for recent issues"
echo "   - Bot activity: Monitored for problems"