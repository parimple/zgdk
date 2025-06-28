#!/bin/bash
# Uruchom interaktywny test sklepu z próbą kliknięcia buttonów

echo "🏪 Interactive Shop Testing"
echo "=========================="

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
    echo "1. Z .env: source .env && ./test_live_bot/run_interactive_shop_test.sh"
    echo "2. Bezpośrednio: CLAUDE_BOT_TOKEN=your_token ./test_live_bot/run_interactive_shop_test.sh"
    echo ""
    exit 1
fi

echo -e "${BLUE}🔑 Token found, proceeding with interactive shop tests...${NC}"
echo -e "${BLUE}🎯 Target Server: zaGadka (960665311701528596)${NC}"
echo -e "${BLUE}📱 Test Channel: cicd (1387864734002446407)${NC}"
echo ""

echo -e "${PURPLE}🏪 Interactive Test Scenarios:${NC}"
echo "   • 💰 Balance setup (3000 coins)"
echo "   • 🏪 Shop display with button analysis"
echo "   • 🔘 Button detection and structure analysis"
echo "   • 🖱️ Button click attempts (limited by Discord API)"
echo "   • 👤 Profile verification"
echo "   • 🔍 Error monitoring"
echo ""

echo -e "${YELLOW}📝 Important Notes:${NC}"
echo -e "${YELLOW}⚠️  User accounts cannot programmatically click Discord buttons${NC}"
echo -e "${YELLOW}⏱️  Using 8-second delays for better rate limiting${NC}"
echo -e "${YELLOW}🔘 Manual testing required for actual purchases${NC}"
echo ""

# Uruchom test
echo -e "${BLUE}🚀 Starting interactive shop tests...${NC}"
cd /home/ubuntu/Projects/zgdk
timeout 180 python test_live_bot/interactive_shop_test.py

# Sprawdź wynik
if [ $? -eq 0 ]; then
    echo ""
    echo -e "${GREEN}✅ Interactive shop tests completed!${NC}"
    echo -e "${GREEN}📊 Check the results above${NC}"
else
    echo ""
    echo -e "${RED}❌ Interactive shop tests encountered errors${NC}"
    echo -e "${RED}🔍 Check the error messages above${NC}"
fi

echo ""
echo -e "${BLUE}📄 Test results saved to: test_live_bot/results/interactive_shop_test_*.json${NC}"
echo ""
echo -e "${PURPLE}🔘 Next Steps - Manual Testing:${NC}"
echo "   1. Go to Discord server zaGadka"
echo "   2. Go to #cicd channel" 
echo "   3. Use ,shop command"
echo "   4. Click on role buttons (zG50, zG100, etc.)"
echo "   5. Complete purchase flow and verify with ,profile"
echo ""
echo -e "${BLUE}🔧 Additional verification:${NC}"
echo "   Check bot logs: docker-compose logs app --tail=20"
echo "   Check bot health: ./scripts/docker/health_check.sh"