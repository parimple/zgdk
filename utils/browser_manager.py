"""
Browser process management for Playwright.

This module provides proper cleanup for browser processes to prevent zombies.
"""

import asyncio
import logging
import os
import signal
from typing import Optional

try:
    from playwright.async_api import Browser, Page, async_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    Browser = None
    Page = None
    async_playwright = None

logger = logging.getLogger(__name__)


class BrowserManager:
    """Manages browser lifecycle with proper cleanup."""

    def __init__(self):
        self.browser: Optional[Browser] = None
        self._playwright = None

    async def __aenter__(self):
        """Start browser with proper settings."""
        if not PLAYWRIGHT_AVAILABLE:
            raise ImportError("Playwright is not installed. Browser automation is disabled.")
        self._playwright = await async_playwright().start()
        self.browser = await self._playwright.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
                "--disable-web-security",
                "--disable-features=VizDisplayCompositor",
                "--disable-extensions",
                "--disable-background-timer-throttling",
                "--disable-backgrounding-occluded-windows",
                "--disable-renderer-backgrounding",
                # Remove --single-process as it can cause issues
                "--disable-blink-features=AutomationControlled",
            ],
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Ensure proper cleanup of browser processes."""
        if self.browser:
            try:
                # Close all pages first
                if hasattr(self.browser, "pages"):
                    pages = self.browser.pages
                    for page in pages:
                        try:
                            await page.close()
                        except Exception as e:
                            logger.warning(f"Failed to close page: {e}")

                # Close browser
                await self.browser.close()

                # Give it a moment to clean up
                await asyncio.sleep(0.1)

            except Exception as e:
                logger.error(f"Error closing browser: {e}")
            finally:
                self.browser = None

        if self._playwright:
            try:
                await self._playwright.stop()
            except Exception as e:
                logger.error(f"Error stopping playwright: {e}")
            finally:
                self._playwright = None

    async def new_page(self) -> Page:
        """Create a new page with proper settings."""
        if not self.browser:
            raise RuntimeError("Browser not initialized")

        page = await self.browser.new_page()

        # Set reasonable timeout
        page.set_default_timeout(30000)  # 30 seconds

        return page


def cleanup_zombie_chromium():
    """Clean up any zombie chromium processes."""
    try:
        # Find all chromium-related processes
        import subprocess

        # Get list of chromium processes
        result = subprocess.run(["ps", "aux"], capture_output=True, text=True)

        if result.returncode == 0:
            for line in result.stdout.splitlines():
                if "headless_shell" in line or "chrome" in line:
                    parts = line.split()
                    if len(parts) > 1:
                        pid = int(parts[1])
                        try:
                            os.kill(pid, signal.SIGKILL)
                            logger.info(f"Killed zombie process {pid}")
                        except ProcessLookupError:
                            pass
                        except PermissionError:
                            pass

    except Exception as e:
        logger.warning(f"Failed to cleanup zombie processes: {e}")


# Run cleanup on module import
cleanup_zombie_chromium()
