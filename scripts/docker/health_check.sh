#!/bin/bash
# Docker health check and bot monitoring

echo "🐳 Docker Health Check & Bot Monitoring"
echo "========================================"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Check Docker services
echo -e "${BLUE}📋 Docker Services Status${NC}"
if docker-compose ps | grep -q "Up"; then
    echo -e "${GREEN}✅ Docker Compose: Services running${NC}"
    docker-compose ps
else
    echo -e "${RED}❌ Docker Compose: Services not running${NC}"
    echo "Run: docker-compose up -d"
    exit 1
fi

echo ""
echo -e "${BLUE}🤖 Bot Health Check${NC}"

# Check bot logs for recent activity
echo "Checking recent bot activity..."
recent_logs=$(docker-compose logs app --tail=10 --since=1m)

if echo "$recent_logs" | grep -q "add_activity\|Command.*executed"; then
    echo -e "${GREEN}✅ Bot Activity: Active (processing commands/activity)${NC}"
else
    echo -e "${YELLOW}⚠️  Bot Activity: Low activity in last minute${NC}"
fi

# Check for errors
echo ""
echo "Checking for errors..."
error_count=$(docker-compose logs app --tail=100 | grep -c "ERROR\|Failed\|Exception")

if [ $error_count -eq 0 ]; then
    echo -e "${GREEN}✅ Error Status: No errors in recent logs${NC}"
elif [ $error_count -le 3 ]; then
    echo -e "${YELLOW}⚠️  Error Status: $error_count minor errors found${NC}"
else
    echo -e "${RED}❌ Error Status: $error_count errors found - needs attention${NC}"
fi

# Check database connectivity
echo ""
echo "Checking database connectivity..."
if docker-compose exec -T db psql -U postgres -d postgres -c "SELECT 1;" > /dev/null 2>&1; then
    echo -e "${GREEN}✅ Database: Connected and responding${NC}"
else
    echo -e "${RED}❌ Database: Connection issues${NC}"
fi

# Check Discord connectivity (look for gateway messages)
echo ""
echo "Checking Discord connectivity..."
if docker-compose logs app --tail=50 | grep -q "Gateway\|Shard.*connected"; then
    echo -e "${GREEN}✅ Discord: Connected to gateway${NC}"
else
    echo -e "${YELLOW}⚠️  Discord: No recent gateway messages${NC}"
fi

# Memory and CPU usage
echo ""
echo -e "${BLUE}📊 Resource Usage${NC}"
echo "Docker containers resource usage:"
docker stats --no-stream --format "table {{.Container}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.MemPerc}}"

# Quick action recommendations
echo ""
echo -e "${BLUE}🔧 Quick Actions${NC}"
echo "View live logs:     docker-compose logs app --follow"
echo "Restart services:   docker-compose down && docker-compose up --build -d"
echo "Check errors:       docker-compose logs app --tail=100 | grep -E '(ERROR|Failed)'"
echo "Test bot commands:  CLAUDE_BOT_TOKEN=xxx ./scripts/test/run_all_tests.sh"

# Exit with appropriate code
if [ $error_count -le 3 ]; then
    echo ""
    echo -e "${GREEN}🎉 Overall Health: GOOD${NC}"
    exit 0
else
    echo ""
    echo -e "${RED}⚠️  Overall Health: NEEDS ATTENTION${NC}"
    exit 1
fi