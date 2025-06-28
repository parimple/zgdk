#!/bin/bash
# Uruchom proste testy sklepu Discord bot

echo "🏪 Simple Shop Testing"
echo "====================="

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
    echo "1. Z .env: source .env && ./test_live_bot/run_simple_shop_test.sh"
    echo "2. Bezpośrednio: CLAUDE_BOT_TOKEN=your_token ./test_live_bot/run_simple_shop_test.sh"
    echo ""
    exit 1
fi

echo -e "${BLUE}🔑 Token found, proceeding with simple shop tests...${NC}"
echo -e "${BLUE}🎯 Target Server: zaGadka (960665311701528596)${NC}"
echo -e "${BLUE}📱 Test Channel: cicd (1387864734002446407)${NC}"
echo ""

echo -e "${PURPLE}🏪 Shop Test Scenarios:${NC}"
echo "   • 💰 Balance management"
echo "   • 👤 Profile verification"
echo "   • 🏪 Shop display with buttons"
echo "   • 🔘 Interactive UI detection"
echo "   • 🔍 Error monitoring"
echo ""

echo -e "${YELLOW}📝 Note: This test verifies shop is accessible${NC}"
echo -e "${YELLOW}🔘 Manual button testing needed for actual purchases${NC}"
echo ""

# Uruchom test
echo -e "${BLUE}🚀 Starting simple shop tests...${NC}"
cd /home/ubuntu/Projects/zgdk
timeout 120 python test_live_bot/simple_shop_test.py

# Sprawdź wynik
if [ $? -eq 0 ]; then
    echo ""
    echo -e "${GREEN}✅ Simple shop tests completed!${NC}"
    echo -e "${GREEN}📊 Check the results above${NC}"
else
    echo ""
    echo -e "${RED}❌ Simple shop tests encountered errors${NC}"
    echo -e "${RED}🔍 Check the error messages above${NC}"
fi

echo ""
echo -e "${BLUE}📄 Test results saved to: test_live_bot/results/simple_shop_test_*.json${NC}"
echo ""
echo -e "${PURPLE}🔘 Manual Testing Instructions:${NC}"
echo "   1. Go to Discord server zaGadka"
echo "   2. Go to #cicd channel"
echo "   3. Use ,shop command"
echo "   4. Click on role buttons (zG50, zG100, etc.)"
echo "   5. Test purchase/extend/upgrade flow"
echo "   6. Test sell functionality if available"