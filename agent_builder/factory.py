"""Factory pattern for agent creation and management."""

import asyncio
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Type

from .core import AgentBuilder, AgentConfig
from .monitor import AgentMonitor
from .templates import AgentTemplate

logger = logging.getLogger(__name__)


class AgentFactory:
    """Factory for creating and managing AI agents."""

    _instance = None
    _agents: Dict[str, Any] = {}
    _configs: Dict[str, AgentConfig] = {}
    _monitors: Dict[str, AgentMonitor] = {}

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self.builder = AgentBuilder()
        self.template = AgentTemplate()
        self._initialized = True

    def register_agent(self, config: AgentConfig) -> str:
        """Register a new agent configuration."""
        agent_id = config.name.lower().replace(" ", "_")
        self._configs[agent_id] = config

        # Generate agent files
        files = self.builder.create_agent(config)

        logger.info(f"Agent '{config.name}' registered successfully")
        logger.info(f"Generated files: {list(files.keys())}")

        return agent_id

    async def create_agent(self, agent_id: str) -> Any:
        """Create an agent instance from registered configuration."""
        if agent_id not in self._configs:
            raise ValueError(f"Agent '{agent_id}' not registered")

        if agent_id in self._agents:
            return self._agents[agent_id]

        config = self._configs[agent_id]

        # Dynamically import and create agent
        try:
            module_name = f"agents.{agent_id}_agent"
            module = __import__(module_name, fromlist=[f"create_{agent_id}_agent"])
            create_func = getattr(module, f"create_{agent_id}_agent")

            agent = await create_func()
            self._agents[agent_id] = agent

            # Start monitoring
            monitor = AgentMonitor(agent_id, agent)
            await monitor.start()
            self._monitors[agent_id] = monitor

            logger.info(f"Agent '{agent_id}' created and started")
            return agent

        except Exception as e:
            logger.error(f"Failed to create agent '{agent_id}': {e}")
            raise

    async def get_agent(self, agent_id: str) -> Any:
        """Get an existing agent or create new one."""
        if agent_id not in self._agents:
            return await self.create_agent(agent_id)
        return self._agents[agent_id]

    def list_agents(self) -> List[Dict[str, Any]]:
        """List all registered agents with their status."""
        agents = []

        for agent_id, config in self._configs.items():
            status = "running" if agent_id in self._agents else "registered"

            agent_info = {
                "id": agent_id,
                "name": config.name,
                "purpose": config.purpose,
                "status": status,
                "created": agent_id in self._agents,
            }

            if agent_id in self._monitors:
                metrics = self._monitors[agent_id].get_metrics()
                agent_info["metrics"] = metrics

            agents.append(agent_info)

        return agents

    async def stop_agent(self, agent_id: str):
        """Stop and cleanup an agent."""
        if agent_id not in self._agents:
            return

        # Stop monitoring
        if agent_id in self._monitors:
            await self._monitors[agent_id].stop()
            del self._monitors[agent_id]

        # Cleanup agent
        agent = self._agents[agent_id]
        if hasattr(agent, "cleanup"):
            await agent.cleanup()

        del self._agents[agent_id]
        logger.info(f"Agent '{agent_id}' stopped")

    async def stop_all(self):
        """Stop all running agents."""
        agent_ids = list(self._agents.keys())

        for agent_id in agent_ids:
            await self.stop_agent(agent_id)

    # Quick creation methods using templates
    async def create_moderation_agent(self) -> Any:
        """Create a content moderation agent."""
        config = self.template.moderation_agent()
        agent_id = self.register_agent(config)
        return await self.create_agent(agent_id)

    async def create_analytics_agent(self) -> Any:
        """Create an analytics processor agent."""
        config = self.template.analytics_agent()
        agent_id = self.register_agent(config)
        return await self.create_agent(agent_id)

    async def create_test_runner_agent(self) -> Any:
        """Create a test runner agent."""
        config = self.template.test_runner_agent()
        agent_id = self.register_agent(config)
        return await self.create_agent(agent_id)

    async def create_optimizer_agent(self) -> Any:
        """Create a command optimizer agent."""
        config = self.template.command_optimizer_agent()
        agent_id = self.register_agent(config)
        return await self.create_agent(agent_id)

    def create_custom_agent_config(
        self, name: str, purpose: str, workflow: List[Dict[str, Any]], **kwargs
    ) -> AgentConfig:
        """Create a custom agent configuration."""
        config = self.template.custom_agent(name, purpose)

        # Override with custom values
        config.workflow = workflow

        for key, value in kwargs.items():
            if hasattr(config, key):
                setattr(config, key, value)

        return config
