"""Core Agent Builder functionality."""

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import google.generativeai as genai
import yaml
from pydantic import BaseModel, Field


@dataclass
class AgentConfig:
    """Configuration for an AI agent."""

    name: str
    purpose: str
    model: str = "gemini-1.5-flash"
    workflow: List[Dict[str, Any]] = field(default_factory=list)
    inputs: Dict[str, str] = field(default_factory=dict)
    outputs: Dict[str, str] = field(default_factory=dict)
    dependencies: List[str] = field(default_factory=list)
    resources: Dict[str, Any] = field(default_factory=dict)
    metrics: List[str] = field(default_factory=list)
    k8s_config: Dict[str, Any] = field(default_factory=dict)


class WorkflowStep(BaseModel):
    """Single step in agent workflow."""

    name: str
    action: str
    inputs: Dict[str, Any] = Field(default_factory=dict)
    outputs: List[str] = Field(default_factory=list)
    error_handling: Optional[str] = None


class AgentBuilder:
    """Main builder for creating AI agents."""

    def __init__(self, project_root: Path = None):
        self.project_root = project_root or Path.cwd()
        self.agents_dir = self.project_root / "agents"
        self.tests_dir = self.project_root / "tests" / "agents"
        self.k8s_dir = self.project_root / "k8s" / "agents"

        # Create directories
        self.agents_dir.mkdir(parents=True, exist_ok=True)
        self.tests_dir.mkdir(parents=True, exist_ok=True)
        self.k8s_dir.mkdir(parents=True, exist_ok=True)

        # Load Gemini API
        self._setup_gemini()

    def _setup_gemini(self):
        """Setup Gemini API from environment."""
        api_key = os.getenv("GEMINI_API_KEY")
        if api_key:
            genai.configure(api_key=api_key)

    def create_agent(self, config: AgentConfig) -> Dict[str, Path]:
        """Create a new agent with all necessary files."""
        agent_name = config.name.lower().replace(" ", "_")

        # Generate agent code
        agent_file = self._generate_agent_code(agent_name, config)

        # Generate tests
        test_file = self._generate_tests(agent_name, config)

        # Generate K8s configs
        k8s_files = self._generate_k8s_configs(agent_name, config)

        # Generate documentation
        doc_file = self._generate_documentation(agent_name, config)

        return {"agent": agent_file, "test": test_file, "k8s": k8s_files, "docs": doc_file}

    def _generate_agent_code(self, name: str, config: AgentConfig) -> Path:
        """Generate Python code for the agent."""
        template = '''"""
{config.name} Agent
Purpose: {config.purpose}
Generated: {datetime.now().isoformat()}
"""

import asyncio
import logging
from typing import Dict, Any, Optional
from datetime import datetime

import redis.asyncio as redis
from pydantic import BaseModel, Field
from pydantic_ai import Agent
import google.generativeai as genai

from core.interfaces.base import IService
from core.services.base_service import BaseService

logger = logging.getLogger(__name__)


class {name.title().replace("_", "")}Input(BaseModel):
    """Input model for {config.name}."""
{self._generate_pydantic_fields(config.inputs)}


class {name.title().replace("_", "")}Output(BaseModel):
    """Output model for {config.name}."""
{self._generate_pydantic_fields(config.outputs)}


class {name.title().replace("_", "")}Agent(BaseService):
    """
    {config.purpose}

    Workflow:
{self._format_workflow(config.workflow)}
    """

    def __init__(self):
        super().__init__()
        self.name = "{config.name}"
        self.agent = None
        self.redis_client = None
        self.metrics = {{
{self._generate_metrics_dict(config.metrics)}
        }}

    async def initialize(self):
        """Initialize the agent."""
        # Setup Redis
        self.redis_client = await redis.from_url(
            "redis://redis-service:6379"
        )

        # Setup AI agent
        genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
        self.agent = Agent(
            "{config.model}",
            system_prompt="{config.purpose}"
        )

        logger.info(f"{{self.name}} initialized")

    async def process(self, input_data: {name.title().replace("_", "")}Input) -> {name.title().replace("_", "")}Output:
        """Process input through the agent workflow."""
        start_time = datetime.now()

        try:
{self._generate_workflow_code(config.workflow)}

            # Update metrics
            self.metrics["total_processed"] += 1
            self.metrics["last_success"] = datetime.now()

            return output

        except Exception as e:
            self.metrics["total_errors"] += 1
            logger.error(f"Error in {{self.name}}: {{e}}")
            raise
        finally:
            duration = (datetime.now() - start_time).total_seconds()
            self.metrics["avg_duration"] = (
                (self.metrics["avg_duration"] * (self.metrics["total_processed"] - 1) + duration)
                / self.metrics["total_processed"]
            )

    async def get_metrics(self) -> Dict[str, Any]:
        """Get agent metrics."""
        return self.metrics.copy()

    async def cleanup(self):
        """Cleanup resources."""
        if self.redis_client:
            await self.redis_client.close()


# Factory function for dependency injection
async def create_{name}_agent() -> {name.title().replace("_", "")}Agent:
    """Create and initialize the agent."""
    agent = {name.title().replace("_", "")}Agent()
    await agent.initialize()
    return agent
'''

        file_path = self.agents_dir / f"{name}_agent.py"
        file_path.write_text(template)
        return file_path

    def _generate_tests(self, name: str, config: AgentConfig) -> Path:
        """Generate test code for the agent."""
        template = '''"""Tests for {config.name} Agent."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

from agents.{name}_agent import (
    {name.title().replace("_", "")}Agent,
    {name.title().replace("_", "")}Input,
    {name.title().replace("_", "")}Output
)


@pytest.fixture
async def agent():
    """Create test agent."""
    with patch("redis.asyncio.from_url") as mock_redis:
        mock_redis.return_value = AsyncMock()

        agent = {name.title().replace("_", "")}Agent()
        await agent.initialize()
        yield agent
        await agent.cleanup()


@pytest.mark.asyncio
async def test_{name}_initialization(agent):
    """Test agent initialization."""
    assert agent.name == "{config.name}"
    assert agent.redis_client is not None
    assert agent.agent is not None


@pytest.mark.asyncio
async def test_{name}_process_success(agent):
    """Test successful processing."""
    # Mock AI response
    agent.agent.run = AsyncMock(return_value=MagicMock(data="test result"))

    input_data = {name.title().replace("_", "")}Input(
{self._generate_test_input(config.inputs)}
    )

    output = await agent.process(input_data)

    assert isinstance(output, {name.title().replace("_", "")}Output)
    assert agent.metrics["total_processed"] == 1
    assert agent.metrics["total_errors"] == 0


@pytest.mark.asyncio
async def test_{name}_process_error(agent):
    """Test error handling."""
    agent.agent.run = AsyncMock(side_effect=Exception("Test error"))

    input_data = {name.title().replace("_", "")}Input(
{self._generate_test_input(config.inputs)}
    )

    with pytest.raises(Exception):
        await agent.process(input_data)

    assert agent.metrics["total_errors"] == 1


@pytest.mark.asyncio
async def test_{name}_metrics(agent):
    """Test metrics collection."""
    metrics = await agent.get_metrics()

    assert "total_processed" in metrics
    assert "total_errors" in metrics
    assert "avg_duration" in metrics
    assert "last_success" in metrics
'''

        file_path = self.tests_dir / f"test_{name}_agent.py"
        file_path.write_text(template)
        return file_path

    def _generate_k8s_configs(self, name: str, config: AgentConfig) -> Dict[str, Path]:
        """Generate Kubernetes configurations."""
        # Deployment
        deployment = {
            "apiVersion": "apps/v1",
            "kind": "Deployment",
            "metadata": {"name": f"{name}-agent", "labels": {"app": f"{name}-agent", "component": "ai-agent"}},
            "spec": {
                "replicas": config.k8s_config.get("replicas", 2),
                "selector": {"matchLabels": {"app": f"{name}-agent"}},
                "template": {
                    "metadata": {"labels": {"app": f"{name}-agent"}},
                    "spec": {
                        "containers": [
                            {
                                "name": "agent",
                                "image": f"zgdk/{name}-agent:latest",
                                "ports": [{"containerPort": 8080}],
                                "env": [
                                    {"name": "AGENT_NAME", "value": config.name},
                                    {"name": "REDIS_HOST", "value": "redis-service"},
                                ],
                                "envFrom": [{"secretRef": {"name": "ai-secrets"}}],
                                "resources": {
                                    "requests": config.resources.get("requests", {"memory": "256Mi", "cpu": "100m"}),
                                    "limits": config.resources.get("limits", {"memory": "512Mi", "cpu": "500m"}),
                                },
                            }
                        ]
                    },
                },
            },
        }

        # Service
        service = {
            "apiVersion": "v1",
            "kind": "Service",
            "metadata": {"name": f"{name}-agent-service"},
            "spec": {"selector": {"app": f"{name}-agent"}, "ports": [{"port": 8080, "targetPort": 8080}]},
        }

        # HPA
        hpa = {
            "apiVersion": "autoscaling/v2",
            "kind": "HorizontalPodAutoscaler",
            "metadata": {"name": f"{name}-agent-hpa"},
            "spec": {
                "scaleTargetRef": {"apiVersion": "apps/v1", "kind": "Deployment", "name": f"{name}-agent"},
                "minReplicas": config.k8s_config.get("minReplicas", 1),
                "maxReplicas": config.k8s_config.get("maxReplicas", 5),
                "metrics": [
                    {
                        "type": "Resource",
                        "resource": {"name": "cpu", "target": {"type": "Utilization", "averageUtilization": 70}},
                    }
                ],
            },
        }

        files = {}

        # Save deployment
        deployment_path = self.k8s_dir / f"{name}-deployment.yaml"
        with open(deployment_path, "w") as f:
            yaml.dump(deployment, f)
        files["deployment"] = deployment_path

        # Save service
        service_path = self.k8s_dir / f"{name}-service.yaml"
        with open(service_path, "w") as f:
            yaml.dump(service, f)
        files["service"] = service_path

        # Save HPA
        hpa_path = self.k8s_dir / f"{name}-hpa.yaml"
        with open(hpa_path, "w") as f:
            yaml.dump(hpa, f)
        files["hpa"] = hpa_path

        return files

    def _generate_documentation(self, name: str, config: AgentConfig) -> Path:
        """Generate documentation for the agent."""
        doc = """# {config.name} Agent

## Purpose
{config.purpose}

## Workflow
{self._format_workflow_markdown(config.workflow)}

## Inputs
{self._format_io_markdown(config.inputs)}

## Outputs
{self._format_io_markdown(config.outputs)}

## Usage

### Python
```python
from agents.{name}_agent import create_{name}_agent

# Create and initialize agent
agent = await create_{name}_agent()

# Process input
input_data = {name.title().replace("_", "")}Input(
{self._generate_example_input(config.inputs)}
)

output = await agent.process(input_data)
print(output)
```

### Kubernetes Deployment
```bash
# Deploy the agent
kubectl apply -f k8s/agents/{name}-deployment.yaml
kubectl apply -f k8s/agents/{name}-service.yaml
kubectl apply -f k8s/agents/{name}-hpa.yaml

# Check status
kubectl get pods -l app={name}-agent
kubectl logs -l app={name}-agent

# Scale manually
kubectl scale deployment {name}-agent --replicas=5
```

## Metrics
- `total_processed`: Total number of processed requests
- `total_errors`: Total number of errors
- `avg_duration`: Average processing duration
- `last_success`: Timestamp of last successful processing

## Configuration
Environment variables:
- `GEMINI_API_KEY`: API key for Google Gemini
- `REDIS_HOST`: Redis server hostname (default: redis-service)

## Testing
```bash
pytest tests/agents/test_{name}_agent.py -v
```
"""

        doc_path = self.agents_dir / f"{name}_agent.md"
        doc_path.write_text(doc)
        return doc_path

    # Helper methods
    def _generate_pydantic_fields(self, fields: Dict[str, str]) -> str:
        """Generate Pydantic field definitions."""
        if not fields:
            return "    pass"

        lines = []
        for name, type_hint in fields.items():
            lines.append(f'    {name}: {type_hint} = Field(description="{name}")')
        return "\n".join(lines)

    def _format_workflow(self, workflow: List[Dict[str, Any]]) -> str:
        """Format workflow for docstring."""
        lines = []
        for i, step in enumerate(workflow, 1):
            lines.append(f'    {i}. {step.get("name", "Step")}: {step.get("action", "")}')
        return "\n".join(lines)

    def _format_workflow_markdown(self, workflow: List[Dict[str, Any]]) -> str:
        """Format workflow for markdown."""
        lines = []
        for i, step in enumerate(workflow, 1):
            lines.append(f'{i}. **{step.get("name", "Step")}**: {step.get("action", "")}')
            if "inputs" in step:
                lines.append(f'   - Inputs: {", ".join(step["inputs"].keys())}')
            if "outputs" in step:
                lines.append(f'   - Outputs: {", ".join(step["outputs"])}')
        return "\n".join(lines)

    def _format_io_markdown(self, io_dict: Dict[str, str]) -> str:
        """Format input/output for markdown."""
        if not io_dict:
            return "None"

        lines = []
        for name, type_hint in io_dict.items():
            lines.append(f"- `{name}`: {type_hint}")
        return "\n".join(lines)

    def _generate_workflow_code(self, workflow: List[Dict[str, Any]]) -> str:
        """Generate workflow implementation code."""
        code_lines = []

        for i, step in enumerate(workflow):
            code_lines.append(f'            # Step {i+1}: {step.get("name", "Step")}')

            # Add step implementation based on action type
            action = step.get("action", "").lower()

            if "ai" in action or "llm" in action:
                code_lines.append("            result = await self.agent.run(input_data.dict())")
            elif "cache" in action:
                code_lines.append('            cached = await self.redis_client.get(f"cache:{input_data}")')
            elif "validate" in action:
                code_lines.append("            # Validation logic here")
            else:
                code_lines.append("            # Custom logic here")

            code_lines.append("")

        # Add output creation
        code_lines.append("            # Create output")
        code_lines.append(f'            output = {workflow[0].get("name", "").title().replace("_", "")}Output(')
        code_lines.append("                # Set output fields")
        code_lines.append("            )")

        return "\n".join(code_lines)

    def _generate_metrics_dict(self, metrics: List[str]) -> str:
        """Generate metrics dictionary initialization."""
        lines = []
        for metric in metrics:
            if metric == "total_processed":
                lines.append('            "total_processed": 0,')
            elif metric == "total_errors":
                lines.append('            "total_errors": 0,')
            elif metric == "avg_duration":
                lines.append('            "avg_duration": 0.0,')
            elif metric == "last_success":
                lines.append('            "last_success": None,')
            else:
                lines.append(f'            "{metric}": 0,')
        return "\n".join(lines)

    def _generate_test_input(self, inputs: Dict[str, str]) -> str:
        """Generate test input data."""
        lines = []
        for name, type_hint in inputs.items():
            if "str" in type_hint:
                lines.append(f'        {name}="test_{name}",')
            elif "int" in type_hint:
                lines.append(f"        {name}=123,")
            elif "float" in type_hint:
                lines.append(f"        {name}=1.23,")
            elif "bool" in type_hint:
                lines.append(f"        {name}=True,")
            else:
                lines.append(f"        {name}=None,  # TODO: Set appropriate test value")
        return "\n".join(lines)

    def _generate_example_input(self, inputs: Dict[str, str]) -> str:
        """Generate example input for documentation."""
        lines = []
        for name, type_hint in inputs.items():
            if "str" in type_hint:
                lines.append(f'    {name}="example {name}",')
            elif "int" in type_hint:
                lines.append(f"    {name}=42,")
            elif "float" in type_hint:
                lines.append(f"    {name}=3.14,")
            elif "bool" in type_hint:
                lines.append(f"    {name}=True,")
            else:
                lines.append(f"    {name}=...,  # Set appropriate value")
        return "\n".join(lines)
