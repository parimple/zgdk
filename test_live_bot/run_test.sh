#!/bin/bash
# Uruchom testy live bota Discord

echo "🤖 Live Bot Discord Testing"
echo "==========================="

# Kolory
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

# Sprawdź token
if [ -z "$CLAUDE_BOT_TOKEN" ]; then
    echo -e "${RED}❌ CLAUDE_BOT_TOKEN environment variable not set${NC}"
    echo ""
    echo "Opcje uruchomienia:"
    echo "1. Z .env: source .env && ./test_live_bot/run_test.sh"
    echo "2. Bezpośrednio: CLAUDE_BOT_TOKEN=your_token ./test_live_bot/run_test.sh"
    echo ""
    exit 1
fi

echo -e "${BLUE}🔑 Token found, proceeding with live bot tests...${NC}"
echo -e "${BLUE}🎯 Target Server: zaGadka (960665311701528596)${NC}"
echo -e "${BLUE}📱 Test Channel: cicd (1387864734002446407)${NC}"
echo ""

echo -e "${YELLOW}⚠️  Note: This will send real commands to Discord bot${NC}"
echo -e "${YELLOW}⏱️  Commands will be spaced 3 seconds apart for rate limiting${NC}"
echo ""

# Uruchom test
echo -e "${BLUE}🚀 Starting live bot command tests...${NC}"
cd /home/ubuntu/Projects/zgdk
python test_live_bot/live_commands_test.py

# Sprawdź wynik
if [ $? -eq 0 ]; then
    echo ""
    echo -e "${GREEN}✅ Live bot tests completed successfully!${NC}"
    echo -e "${GREEN}📊 Check the results above for detailed test outcomes${NC}"
else
    echo ""
    echo -e "${RED}❌ Live bot tests encountered errors${NC}"
    echo -e "${RED}🔍 Check the error messages above${NC}"
fi

echo ""
echo -e "${BLUE}📄 Test results saved to: test_live_bot/results/live_test_*.json${NC}"
echo -e "${BLUE}🔧 Quick commands:${NC}"
echo "   Check bot health: ./scripts/docker/health_check.sh"
echo "   Check bot logs:   docker-compose logs app --tail=20"