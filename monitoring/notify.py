#!/usr/bin/env python3
"""
Notification handler for ZGDK monitoring system
Supports multiple notification channels
"""

import asyncio
import json
import os
import smtplib
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import Dict, List, Optional

import aiohttp
import yaml


class NotificationHandler:
    def __init__(self, config_path: str = "monitoring/config.yml"):
        with open(config_path, "r") as f:
            self.config = yaml.safe_load(f)["notifications"]

    async def send_webhook(self, message: str, details: Optional[Dict] = None):
        """Send notification via webhook (Slack/Discord compatible)"""
        webhook_url = self.config.get("webhook_url", "")
        if not webhook_url:
            return

        # Format for Slack/Discord
        payload = {"text": message, "username": "ZGDK Monitor", "icon_emoji": ":warning:"}

        if details:
            # Add rich formatting for Slack
            if "slack" in webhook_url.lower():
                payload["attachments"] = [
                    {
                        "color": "danger",
                        "fields": [
                            {"title": k.replace("_", " ").title(), "value": str(v), "short": True}
                            for k, v in details.items()
                        ],
                        "footer": "ZGDK Monitoring System",
                        "ts": int(datetime.now().timestamp()),
                    }
                ]
            # Format for Discord
            elif "discord" in webhook_url.lower():
                payload["embeds"] = [
                    {
                        "title": "System Alert",
                        "description": message,
                        "color": 15158332,  # Red
                        "fields": [
                            {"name": k.replace("_", " ").title(), "value": str(v), "inline": True}
                            for k, v in details.items()
                        ],
                        "footer": {"text": "ZGDK Monitoring System"},
                        "timestamp": datetime.now().isoformat(),
                    }
                ]

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(webhook_url, json=payload) as response:
                    if response.status != 200:
                        print(f"Webhook notification failed: {response.status}")
        except Exception as e:
            print(f"Error sending webhook: {e}")

    def send_email(self, subject: str, body: str, html_body: Optional[str] = None):
        """Send email notification"""
        email_config = self.config.get("email", {})
        if not email_config.get("enabled", False):
            return

        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = f"[ZGDK Monitor] {subject}"
            msg["From"] = email_config["from_email"]
            msg["To"] = ", ".join(email_config["to_emails"])

            # Add plain text part
            msg.attach(MIMEText(body, "plain"))

            # Add HTML part if provided
            if html_body:
                msg.attach(MIMEText(html_body, "html"))

            # Send email
            with smtplib.SMTP(email_config["smtp_server"], email_config["smtp_port"]) as server:
                server.starttls()
                if os.getenv("SMTP_PASSWORD"):
                    server.login(email_config["from_email"], os.getenv("SMTP_PASSWORD"))
                server.send_message(msg)

        except Exception as e:
            print(f"Error sending email: {e}")

    async def notify_failure(self, service: str, status: str, message: str):
        """Send failure notification"""
        notification_message = f"⚠️ ZGDK Alert: {service} is {status}\n\n{message}"

        # Send webhook notification
        await self.send_webhook(
            notification_message,
            {"service": service, "status": status, "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC")},
        )

        # Send email notification
        html_body = f"""
        <html>
            <body style="font-family: Arial, sans-serif;">
                <h2 style="color: #d32f2f;">ZGDK System Alert</h2>
                <table style="border-collapse: collapse; width: 100%;">
                    <tr>
                        <td style="padding: 8px; border: 1px solid #ddd;"><strong>Service:</strong></td>
                        <td style="padding: 8px; border: 1px solid #ddd;">{service}</td>
                    </tr>
                    <tr>
                        <td style="padding: 8px; border: 1px solid #ddd;"><strong>Status:</strong></td>
                        <td style="padding: 8px; border: 1px solid #ddd; color: #d32f2f;">{status}</td>
                    </tr>
                    <tr>
                        <td style="padding: 8px; border: 1px solid #ddd;"><strong>Message:</strong></td>
                        <td style="padding: 8px; border: 1px solid #ddd;">{message}</td>
                    </tr>
                    <tr>
                        <td style="padding: 8px; border: 1px solid #ddd;"><strong>Time:</strong></td>
                        <td style="padding: 8px; border: 1px solid #ddd;">{datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC")}</td>
                    </tr>
                </table>
                <p style="margin-top: 20px; color: #666;">
                    <a href="http://localhost:8888/status">View Status Dashboard</a>
                </p>
            </body>
        </html>
        """

        self.send_email(f"Service Alert: {service} is {status}", notification_message, html_body)

    async def notify_recovery(self, service: str):
        """Send recovery notification"""
        notification_message = f"✅ ZGDK Recovery: {service} is now healthy"

        await self.send_webhook(
            notification_message,
            {"service": service, "status": "healthy", "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC")},
        )


async def test_notifications():
    """Test notification system"""
    handler = NotificationHandler()

    print("Testing notifications...")
    await handler.notify_failure("docker_zgdk_app", "down", "Container is not running")

    await asyncio.sleep(2)

    await handler.notify_recovery("docker_zgdk_app")

    print("Notification test completed")


if __name__ == "__main__":
    asyncio.run(test_notifications())
