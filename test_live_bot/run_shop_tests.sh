#!/bin/bash
# Uruchom kompleksowe testy sklepu Discord bot

echo "🏪 Comprehensive Shop Testing"
echo "============================"

# Kolory
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
PURPLE='\033[0;35m'
NC='\033[0m'

# Sprawdź token
if [ -z "$CLAUDE_BOT_TOKEN" ]; then
    echo -e "${RED}❌ CLAUDE_BOT_TOKEN environment variable not set${NC}"
    echo ""
    echo "Opcje uruchomienia:"
    echo "1. Z .env: source .env && ./test_live_bot/run_shop_tests.sh"
    echo "2. Bezpośrednio: CLAUDE_BOT_TOKEN=your_token ./test_live_bot/run_shop_tests.sh"
    echo ""
    exit 1
fi

echo -e "${BLUE}🔑 Token found, proceeding with comprehensive shop tests...${NC}"
echo -e "${BLUE}🎯 Target Server: zaGadka (960665311701528596)${NC}"
echo -e "${BLUE}📱 Test Channel: cicd (1387864734002446407)${NC}"
echo ""

echo -e "${PURPLE}🏪 Shop Test Scenarios:${NC}"
echo "   • 💰 Balance management (add 5000 coins)"
echo "   • 🛒 Purchase zG50 role (30 days)"
echo "   • ⏰ Extend zG50 role (15 days)"
echo "   • ⬆️ Upgrade to zG100 (30 days)"
echo "   • ⏰ Extend zG100 role (15 days)"
echo "   • 💳 Wallet verification"
echo "   • 🔍 Error monitoring"
echo ""

echo -e "${YELLOW}⚠️  Note: This will test real shop functionality${NC}"
echo -e "${YELLOW}⏱️  Commands will be spaced 4 seconds apart${NC}"
echo -e "${YELLOW}💸 Test will spend virtual currency for role testing${NC}"
echo ""

# Uruchom test
echo -e "${BLUE}🚀 Starting comprehensive shop tests...${NC}"
cd /home/ubuntu/Projects/zgdk
timeout 300 python test_live_bot/comprehensive_shop_test.py

# Sprawdź wynik
if [ $? -eq 0 ]; then
    echo ""
    echo -e "${GREEN}✅ Shop tests completed successfully!${NC}"
    echo -e "${GREEN}📊 Check the results above for detailed shop test outcomes${NC}"
else
    echo ""
    echo -e "${RED}❌ Shop tests encountered errors or timed out${NC}"
    echo -e "${RED}🔍 Check the error messages above${NC}"
fi

echo ""
echo -e "${BLUE}📄 Test results saved to: test_live_bot/results/comprehensive_shop_test_*.json${NC}"
echo ""
echo -e "${BLUE}🔧 Quick verification commands:${NC}"
echo "   Check bot health: ./scripts/docker/health_check.sh"
echo "   Check bot logs:   docker-compose logs app --tail=30"
echo "   View test results: ls -la test_live_bot/results/"
echo ""
echo -e "${PURPLE}🎯 Test completed! Check Discord #cicd channel for real interactions.${NC}"