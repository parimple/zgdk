#!/bin/bash

# Setup script for ZGDK monitoring system

echo "Setting up ZGDK monitoring system..."

# Check if running as root
if [ "$EUID" -eq 0 ]; then 
   echo "Please run this script as a regular user, not root"
   exit 1
fi

# Create required directories
mkdir -p monitoring/logs

# Install Python dependencies
echo "Installing Python dependencies..."
if [ ! -d "venv" ]; then
    python3 -m venv venv
fi
source venv/bin/activate
pip install -q aiohttp pyyaml

# Create default config if not exists
if [ ! -f "monitoring/config.yml" ]; then
    echo "Creating default configuration..."
    python monitoring/monitor.py --generate-config
fi

# Setup systemd service (optional)
read -p "Install as systemd service? (requires sudo) [y/N] " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    sudo cp monitoring/zgdk-monitor.service /etc/systemd/system/
    sudo systemctl daemon-reload
    sudo systemctl enable zgdk-monitor.service
    echo "Systemd service installed. Start with: sudo systemctl start zgdk-monitor"
fi

# Create convenience scripts
cat > monitoring/view_status.sh << 'EOF'
#!/bin/bash
# Quick script to view monitoring status

if [ -f monitoring/status.json ]; then
    python -c "
import json
with open('monitoring/status.json', 'r') as f:
    data = json.load(f)

print('ZGDK System Status')
print('=' * 40)
print(f\"Last Updated: {data['timestamp']}\")
print(f\"Total Services: {data['summary']['total']}\")
print(f\"Healthy: {data['summary']['healthy']} ✓\")
print(f\"Degraded: {data['summary']['degraded']} ⚠\")
print(f\"Down: {data['summary']['down']} ✗\")
print()
print('Service Details:')
print('-' * 40)

for check in data['checks']:
    status_icon = '✓' if check['status'] == 'healthy' else '⚠' if check['status'] == 'degraded' else '✗'
    print(f\"{status_icon} {check['service']}: {check['message']}\")
"
else
    echo "No status data found. Run the monitor first."
fi
EOF

chmod +x monitoring/view_status.sh

echo ""
echo "Setup complete!"
echo ""
echo "Next steps:"
echo "1. Edit monitoring/config.yml with your settings"
echo "2. Set GITHUB_TOKEN environment variable for GitHub monitoring"
echo "3. Start monitoring with: ./monitoring/start_monitor.sh"
echo "4. View status with: ./monitoring/view_status.sh"
echo "5. Access web dashboard: python monitoring/status_server.py"
echo ""
echo "For automated notifications:"
echo "- Add webhook URL to config.yml"
echo "- Configure email settings if needed"