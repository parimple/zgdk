"""Health check server for Kubernetes probes."""

import logging
from typing import Optional

from aiohttp import web

logger = logging.getLogger(__name__)


class HealthCheckServer:
    """Simple HTTP server for health checks."""

    def __init__(self, bot, port: int = 8091):
        """Initialize health check server."""
        self.bot = bot
        self.port = port
        self.app = web.Application()
        self.runner: Optional[web.AppRunner] = None
        self._setup_routes()

    def _setup_routes(self):
        """Setup health check routes."""
        self.app.router.add_get("/health", self.health_check)
        self.app.router.add_get("/ready", self.readiness_check)
        self.app.router.add_get("/startup", self.startup_check)

    async def health_check(self, request):
        """Liveness probe - checks if bot process is alive."""
        try:
            # Basic check - bot object exists
            if self.bot:
                return web.Response(text="OK", status=200)
            else:
                return web.Response(text="Bot not initialized", status=503)
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return web.Response(text=str(e), status=503)

    async def readiness_check(self, request):
        """Readiness probe - checks if bot is ready to serve traffic."""
        try:
            # Check if bot is connected to Discord
            if not self.bot.is_ready():
                return web.Response(text="Bot not ready", status=503)

            # Check if we have guilds
            if len(self.bot.guilds) == 0:
                return web.Response(text="No guilds connected", status=503)

            # Check database connection
            try:
                from sqlalchemy import text

                async with self.bot.get_db() as session:
                    await session.execute(text("SELECT 1"))
            except Exception as e:
                return web.Response(text=f"Database error: {e}", status=503)

            return web.Response(text="Ready", status=200)

        except Exception as e:
            logger.error(f"Readiness check failed: {e}")
            return web.Response(text=str(e), status=503)

    async def startup_check(self, request):
        """Startup probe - checks if bot is starting up properly."""
        try:
            # More lenient check for startup
            if self.bot and hasattr(self.bot, "loop"):
                return web.Response(text="Starting", status=200)
            else:
                return web.Response(text="Bot initialization failed", status=503)
        except Exception as e:
            logger.error(f"Startup check failed: {e}")
            return web.Response(text=str(e), status=503)

    async def start(self):
        """Start the health check server."""
        try:
            self.runner = web.AppRunner(self.app)
            await self.runner.setup()
            site = web.TCPSite(self.runner, "0.0.0.0", self.port)
            await site.start()
            logger.info(f"Health check server started on port {self.port}")
        except Exception as e:
            logger.error(f"Failed to start health check server: {e}")
            raise

    async def stop(self):
        """Stop the health check server."""
        if self.runner:
            await self.runner.cleanup()
            logger.info("Health check server stopped")
