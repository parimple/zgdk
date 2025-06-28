#!/usr/bin/env python3
"""
ZGDK Automated Monitoring System
Monitors CI/CD pipelines, Docker containers, and ArgoCD deployments
"""

import asyncio
import json
import logging
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import aiohttp
import yaml
from dataclasses import dataclass, asdict
from enum import Enum


class ServiceStatus(Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    DOWN = "down"
    UNKNOWN = "unknown"


@dataclass
class HealthCheck:
    service: str
    status: ServiceStatus
    message: str
    timestamp: datetime
    details: Optional[Dict] = None


class ZGDKMonitor:
    def __init__(self, config_path: str = "monitoring/config.yml"):
        self.config = self._load_config(config_path)
        self.logger = self._setup_logging()
        self.health_checks: List[HealthCheck] = []
        
    def _load_config(self, config_path: str) -> dict:
        """Load monitoring configuration"""
        config_file = Path(config_path)
        if not config_file.exists():
            # Create default config if it doesn't exist
            default_config = {
                "monitoring": {
                    "interval_seconds": 300,
                    "timeout_seconds": 30,
                    "retry_attempts": 3
                },
                "github": {
                    "owner": "your-github-username",
                    "repo": "zgdk",
                    "workflows": ["ci", "docker-build"]
                },
                "docker": {
                    "containers": ["zgdk_app", "zgdk_db", "zgdk_redis"],
                    "compose_file": "docker-compose.yml"
                },
                "argocd": {
                    "enabled": False,
                    "server": "argocd.example.com",
                    "app_name": "zgdk"
                },
                "notifications": {
                    "webhook_url": "",
                    "email": {
                        "enabled": False,
                        "smtp_server": "",
                        "smtp_port": 587,
                        "from_email": "",
                        "to_emails": []
                    }
                },
                "status_page": {
                    "output_path": "monitoring/status.html",
                    "update_interval": 60
                }
            }
            
            os.makedirs(os.path.dirname(config_path), exist_ok=True)
            with open(config_path, 'w') as f:
                yaml.dump(default_config, f, default_flow_style=False)
            
            return default_config
        
        with open(config_path, 'r') as f:
            return yaml.safe_load(f)
    
    def _setup_logging(self) -> logging.Logger:
        """Setup logging configuration"""
        logger = logging.getLogger("zgdk_monitor")
        logger.setLevel(logging.INFO)
        
        # Console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        
        # File handler
        os.makedirs("monitoring/logs", exist_ok=True)
        file_handler = logging.FileHandler("monitoring/logs/monitor.log")
        file_handler.setLevel(logging.DEBUG)
        
        # Formatter
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        console_handler.setFormatter(formatter)
        file_handler.setFormatter(formatter)
        
        logger.addHandler(console_handler)
        logger.addHandler(file_handler)
        
        return logger
    
    async def check_github_actions(self, session: aiohttp.ClientSession) -> List[HealthCheck]:
        """Check GitHub Actions workflow status"""
        checks = []
        
        if not os.getenv("GITHUB_TOKEN"):
            self.logger.warning("GITHUB_TOKEN not set, skipping GitHub Actions check")
            return checks
        
        headers = {
            "Authorization": f"token {os.getenv('GITHUB_TOKEN')}",
            "Accept": "application/vnd.github.v3+json"
        }
        
        owner = self.config["github"]["owner"]
        repo = self.config["github"]["repo"]
        
        for workflow in self.config["github"]["workflows"]:
            try:
                url = f"https://api.github.com/repos/{owner}/{repo}/actions/workflows/{workflow}.yml/runs"
                
                async with session.get(url, headers=headers) as response:
                    if response.status == 200:
                        data = await response.json()
                        
                        if data["workflow_runs"]:
                            latest_run = data["workflow_runs"][0]
                            status = ServiceStatus.HEALTHY if latest_run["status"] == "completed" and latest_run["conclusion"] == "success" else ServiceStatus.DOWN
                            
                            checks.append(HealthCheck(
                                service=f"github_workflow_{workflow}",
                                status=status,
                                message=f"Latest run: {latest_run['conclusion']}",
                                timestamp=datetime.now(),
                                details={
                                    "run_id": latest_run["id"],
                                    "run_number": latest_run["run_number"],
                                    "conclusion": latest_run["conclusion"],
                                    "html_url": latest_run["html_url"]
                                }
                            ))
                        else:
                            checks.append(HealthCheck(
                                service=f"github_workflow_{workflow}",
                                status=ServiceStatus.UNKNOWN,
                                message="No workflow runs found",
                                timestamp=datetime.now()
                            ))
                    else:
                        checks.append(HealthCheck(
                            service=f"github_workflow_{workflow}",
                            status=ServiceStatus.DOWN,
                            message=f"API request failed: {response.status}",
                            timestamp=datetime.now()
                        ))
                        
            except Exception as e:
                self.logger.error(f"Error checking GitHub workflow {workflow}: {e}")
                checks.append(HealthCheck(
                    service=f"github_workflow_{workflow}",
                    status=ServiceStatus.DOWN,
                    message=f"Error: {str(e)}",
                    timestamp=datetime.now()
                ))
        
        return checks
    
    def check_docker_containers(self) -> List[HealthCheck]:
        """Check Docker container health"""
        checks = []
        
        for container in self.config["docker"]["containers"]:
            try:
                # Check if container is running
                result = subprocess.run(
                    ["docker", "inspect", "--format='{{.State.Status}}'", container],
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                
                if result.returncode == 0:
                    status_str = result.stdout.strip().strip("'")
                    if status_str == "running":
                        # Check container health if available
                        health_result = subprocess.run(
                            ["docker", "inspect", "--format='{{.State.Health.Status}}'", container],
                            capture_output=True,
                            text=True,
                            timeout=10
                        )
                        
                        if health_result.returncode == 0 and health_result.stdout.strip().strip("'") != "<no value>":
                            health_status = health_result.stdout.strip().strip("'")
                            status = ServiceStatus.HEALTHY if health_status == "healthy" else ServiceStatus.DEGRADED
                            message = f"Container running, health: {health_status}"
                        else:
                            status = ServiceStatus.HEALTHY
                            message = "Container running"
                    else:
                        status = ServiceStatus.DOWN
                        message = f"Container status: {status_str}"
                else:
                    status = ServiceStatus.DOWN
                    message = "Container not found"
                
                checks.append(HealthCheck(
                    service=f"docker_{container}",
                    status=status,
                    message=message,
                    timestamp=datetime.now()
                ))
                
            except subprocess.TimeoutExpired:
                checks.append(HealthCheck(
                    service=f"docker_{container}",
                    status=ServiceStatus.UNKNOWN,
                    message="Check timed out",
                    timestamp=datetime.now()
                ))
            except Exception as e:
                self.logger.error(f"Error checking Docker container {container}: {e}")
                checks.append(HealthCheck(
                    service=f"docker_{container}",
                    status=ServiceStatus.DOWN,
                    message=f"Error: {str(e)}",
                    timestamp=datetime.now()
                ))
        
        return checks
    
    async def check_argocd(self, session: aiohttp.ClientSession) -> List[HealthCheck]:
        """Check ArgoCD application status"""
        checks = []
        
        if not self.config["argocd"]["enabled"]:
            return checks
        
        # This is a placeholder - you'll need to configure ArgoCD authentication
        # For now, we'll return a mock check
        checks.append(HealthCheck(
            service="argocd_zgdk",
            status=ServiceStatus.UNKNOWN,
            message="ArgoCD check not implemented",
            timestamp=datetime.now()
        ))
        
        return checks
    
    async def send_notifications(self, failed_checks: List[HealthCheck]):
        """Send notifications for failed health checks"""
        if not failed_checks:
            return
        
        # Webhook notification
        webhook_url = self.config["notifications"]["webhook_url"]
        if webhook_url:
            try:
                async with aiohttp.ClientSession() as session:
                    payload = {
                        "text": f"ZGDK Monitoring Alert: {len(failed_checks)} services are unhealthy",
                        "attachments": [
                            {
                                "color": "danger",
                                "fields": [
                                    {
                                        "title": check.service,
                                        "value": f"{check.status.value}: {check.message}",
                                        "short": False
                                    }
                                    for check in failed_checks
                                ]
                            }
                        ]
                    }
                    
                    async with session.post(webhook_url, json=payload) as response:
                        if response.status != 200:
                            self.logger.error(f"Failed to send webhook notification: {response.status}")
                            
            except Exception as e:
                self.logger.error(f"Error sending webhook notification: {e}")
    
    def generate_status_page(self):
        """Generate HTML status page"""
        html_template = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ZGDK Status Dashboard</title>
    <meta http-equiv="refresh" content="60">
    <style>
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            margin: 0;
            padding: 20px;
            background-color: #f5f5f5;
        }
        .container {
            max-width: 1200px;
            margin: 0 auto;
        }
        h1 {
            color: #333;
            text-align: center;
        }
        .status-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 20px;
            margin-top: 30px;
        }
        .status-card {
            background: white;
            border-radius: 8px;
            padding: 20px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        .status-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 10px;
        }
        .service-name {
            font-weight: bold;
            font-size: 18px;
        }
        .status-indicator {
            width: 12px;
            height: 12px;
            border-radius: 50%;
            display: inline-block;
        }
        .status-healthy { background-color: #4caf50; }
        .status-degraded { background-color: #ff9800; }
        .status-down { background-color: #f44336; }
        .status-unknown { background-color: #9e9e9e; }
        .status-message {
            color: #666;
            margin-top: 5px;
        }
        .last-updated {
            text-align: center;
            color: #999;
            margin-top: 30px;
        }
        .summary {
            background: white;
            border-radius: 8px;
            padding: 20px;
            margin-bottom: 30px;
            text-align: center;
        }
        .summary-stats {
            display: flex;
            justify-content: center;
            gap: 40px;
            margin-top: 15px;
        }
        .stat {
            text-align: center;
        }
        .stat-value {
            font-size: 32px;
            font-weight: bold;
        }
        .stat-label {
            color: #666;
            font-size: 14px;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>ZGDK Status Dashboard</h1>
        
        <div class="summary">
            <h2>System Overview</h2>
            <div class="summary-stats">
                <div class="stat">
                    <div class="stat-value" style="color: #4caf50;">{healthy_count}</div>
                    <div class="stat-label">Healthy</div>
                </div>
                <div class="stat">
                    <div class="stat-value" style="color: #ff9800;">{degraded_count}</div>
                    <div class="stat-label">Degraded</div>
                </div>
                <div class="stat">
                    <div class="stat-value" style="color: #f44336;">{down_count}</div>
                    <div class="stat-label">Down</div>
                </div>
            </div>
        </div>
        
        <div class="status-grid">
            {status_cards}
        </div>
        
        <div class="last-updated">
            Last updated: {last_updated}
        </div>
    </div>
</body>
</html>"""
        
        # Count statuses
        healthy_count = sum(1 for check in self.health_checks if check.status == ServiceStatus.HEALTHY)
        degraded_count = sum(1 for check in self.health_checks if check.status == ServiceStatus.DEGRADED)
        down_count = sum(1 for check in self.health_checks if check.status == ServiceStatus.DOWN)
        
        # Generate status cards
        status_cards = []
        for check in self.health_checks:
            card = f"""
            <div class="status-card">
                <div class="status-header">
                    <span class="service-name">{check.service.replace('_', ' ').title()}</span>
                    <span class="status-indicator status-{check.status.value}"></span>
                </div>
                <div class="status-message">{check.message}</div>
            </div>"""
            status_cards.append(card)
        
        # Fill template
        html = html_template.format(
            healthy_count=healthy_count,
            degraded_count=degraded_count,
            down_count=down_count,
            status_cards=''.join(status_cards),
            last_updated=datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC")
        )
        
        # Write to file
        output_path = Path(self.config["status_page"]["output_path"])
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(html)
        
        self.logger.info(f"Status page updated: {output_path}")
    
    def save_status_json(self):
        """Save status data as JSON for API consumption"""
        status_data = {
            "timestamp": datetime.now().isoformat(),
            "checks": [
                {
                    "service": check.service,
                    "status": check.status.value,
                    "message": check.message,
                    "timestamp": check.timestamp.isoformat(),
                    "details": check.details
                }
                for check in self.health_checks
            ],
            "summary": {
                "total": len(self.health_checks),
                "healthy": sum(1 for check in self.health_checks if check.status == ServiceStatus.HEALTHY),
                "degraded": sum(1 for check in self.health_checks if check.status == ServiceStatus.DEGRADED),
                "down": sum(1 for check in self.health_checks if check.status == ServiceStatus.DOWN),
                "unknown": sum(1 for check in self.health_checks if check.status == ServiceStatus.UNKNOWN)
            }
        }
        
        output_path = Path("monitoring/status.json")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, 'w') as f:
            json.dump(status_data, f, indent=2)
    
    async def run_health_checks(self):
        """Run all health checks"""
        self.health_checks.clear()
        
        async with aiohttp.ClientSession() as session:
            # Run GitHub Actions checks
            github_checks = await self.check_github_actions(session)
            self.health_checks.extend(github_checks)
            
            # Run Docker checks
            docker_checks = self.check_docker_containers()
            self.health_checks.extend(docker_checks)
            
            # Run ArgoCD checks
            argocd_checks = await self.check_argocd(session)
            self.health_checks.extend(argocd_checks)
        
        # Log results
        failed_checks = [check for check in self.health_checks if check.status not in [ServiceStatus.HEALTHY, ServiceStatus.UNKNOWN]]
        
        if failed_checks:
            self.logger.warning(f"Found {len(failed_checks)} unhealthy services")
            for check in failed_checks:
                self.logger.warning(f"{check.service}: {check.status.value} - {check.message}")
        else:
            self.logger.info("All services are healthy")
        
        # Send notifications for failures
        await self.send_notifications(failed_checks)
        
        # Generate status page
        self.generate_status_page()
        
        # Save JSON status
        self.save_status_json()
    
    async def run(self):
        """Main monitoring loop"""
        self.logger.info("Starting ZGDK monitoring system")
        
        while True:
            try:
                await self.run_health_checks()
                
                # Wait for next check
                await asyncio.sleep(self.config["monitoring"]["interval_seconds"])
                
            except KeyboardInterrupt:
                self.logger.info("Monitoring stopped by user")
                break
            except Exception as e:
                self.logger.error(f"Unexpected error in monitoring loop: {e}")
                await asyncio.sleep(60)  # Wait a minute before retrying


async def main():
    """Main entry point"""
    monitor = ZGDKMonitor()
    await monitor.run()


if __name__ == "__main__":
    asyncio.run(main())