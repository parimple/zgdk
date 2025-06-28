#!/bin/bash
# Script to run MCP tests for ZGDK bot

echo "🚀 Starting ZGDK MCP Test Environment..."

# Check if bot is running
if ! docker-compose ps | grep -q "app.*Up"; then
    echo "❌ Bot is not running. Starting bot first..."
    docker-compose up -d
    echo "⏳ Waiting for bot to start..."
    sleep 10
fi

# Enable MCP in bot
export ENABLE_MCP=true

# Run interactive MCP client
echo "📡 Starting MCP Client..."
echo "=====================================‌"
echo "Available commands:"
echo "  status          - Check bot status"
echo "  user <id>       - Get user info"
echo "  cmd <cmd> <uid> - Execute command"
echo "  balance <id> <n> - Modify balance"
echo "  decisions       - Analyze decisions"
echo "  perf            - Performance stats"
echo "  quit           - Exit"
echo "====================================="
echo ""

cd mcp && python mcp_client_example.py