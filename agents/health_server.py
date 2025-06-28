"""Health check server for Support Agents."""

import asyncio
import logging
from aiohttp import web
from datetime import datetime
import os

logger = logging.getLogger(__name__)


class HealthServer:
    """Simple health/ready endpoints for Kubernetes probes."""
    
    def __init__(self, agent_type: str, port: int = 8080):
        self.agent_type = agent_type
        self.port = port
        self.app = web.Application()
        self.startup_time = datetime.now()
        self.ready = False
        self.healthy = True
        self._setup_routes()
        
    def _setup_routes(self):
        self.app.router.add_get('/health', self.health_check)
        self.app.router.add_get('/ready', self.readiness_check)
        self.app.router.add_get('/metrics', self.metrics)
        
    async def health_check(self, request):
        """Liveness probe - is the agent running?"""
        if self.healthy:
            return web.json_response({
                'status': 'healthy',
                'agent': self.agent_type,
                'uptime': str(datetime.now() - self.startup_time)
            })
        return web.json_response({'status': 'unhealthy'}, status=503)
        
    async def readiness_check(self, request):
        """Readiness probe - is the agent ready to handle requests?"""
        if self.ready:
            return web.json_response({
                'status': 'ready',
                'agent': self.agent_type
            })
        return web.json_response({'status': 'not ready'}, status=503)
        
    async def metrics(self, request):
        """Basic metrics endpoint."""
        return web.json_response({
            'agent_type': self.agent_type,
            'uptime_seconds': (datetime.now() - self.startup_time).total_seconds(),
            'ready': self.ready,
            'healthy': self.healthy
        })
        
    def set_ready(self, ready: bool = True):
        """Set readiness state."""
        self.ready = ready
        logger.info(f"{self.agent_type} agent ready: {ready}")
        
    def set_healthy(self, healthy: bool = True):
        """Set health state."""
        self.healthy = healthy
        
    async def start(self):
        """Start health server."""
        runner = web.AppRunner(self.app)
        await runner.setup()
        site = web.TCPSite(runner, '0.0.0.0', self.port)
        await site.start()
        logger.info(f"Health server started on port {self.port}")


# Agent entry point
async def main():
    """Main entry point for Support Agent."""
    import sys
    from support_agent import SupportAgentCrew
    import redis.asyncio as redis
    
    # Get agent type from environment
    agent_type = os.getenv('AGENT_TYPE', 'unknown')
    logger.info(f"Starting {agent_type} agent...")
    
    # Start health server
    health = HealthServer(agent_type)
    await health.start()
    
    try:
        # Initialize connections
        redis_client = await redis.from_url(
            f"redis://{os.getenv('REDIS_HOST', 'localhost')}:6379"
        )
        
        # For now, mock the DB session
        db_session = None  # Would be AsyncSession in production
        
        # Create agent crew
        crew = SupportAgentCrew(redis_client, db_session)
        
        # Mark as ready
        health.set_ready(True)
        
        # Keep running
        while True:
            await asyncio.sleep(60)
            # Here would be the main agent loop
            
    except Exception as e:
        logger.error(f"Agent error: {e}")
        health.set_healthy(False)
        raise


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())