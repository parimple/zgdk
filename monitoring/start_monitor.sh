#!/bin/bash

# Start ZGDK Monitoring System

# Change to project directory
cd "$(dirname "$0")/.."

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
source venv/bin/activate

# Install required dependencies
pip install -q aiohttp pyyaml

# Export GitHub token if available
if [ -f ".env" ]; then
    export $(grep -v '^#' .env | xargs)
fi

# Create monitoring directories
mkdir -p monitoring/logs

# Start monitor with nohup for background execution
echo "Starting ZGDK monitoring system..."
nohup python monitoring/monitor.py > monitoring/logs/monitor_startup.log 2>&1 &

# Save PID for later management
echo $! > monitoring/monitor.pid

echo "Monitor started with PID: $(cat monitoring/monitor.pid)"
echo "Logs: monitoring/logs/monitor.log"
echo "Status page: monitoring/status.html"
echo ""
echo "To stop monitoring: kill $(cat monitoring/monitor.pid)"