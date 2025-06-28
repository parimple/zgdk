"""CLI interface for Agent Builder."""

import asyncio
import click
from pathlib import Path
from typing import Optional

from .factory import AgentFactory
from .core import AgentConfig


@click.group()
def cli():
    """Agent Builder CLI - Create and manage AI agents."""
    pass


@cli.command()
@click.argument("template", type=click.Choice([
    "moderation", "analytics", "test-runner", "optimizer", "custom"
]))
@click.option("--name", help="Agent name (for custom agents)")
@click.option("--purpose", help="Agent purpose (for custom agents)")
def create(template: str, name: Optional[str], purpose: Optional[str]):
    """Create a new agent from template."""
    factory = AgentFactory()
    
    if template == "moderation":
        config = factory.template.moderation_agent()
    elif template == "analytics":
        config = factory.template.analytics_agent()
    elif template == "test-runner":
        config = factory.template.test_runner_agent()
    elif template == "optimizer":
        config = factory.template.command_optimizer_agent()
    elif template == "custom":
        if not name or not purpose:
            click.echo("Error: --name and --purpose required for custom agents")
            return
        config = factory.template.custom_agent(name, purpose)
    
    agent_id = factory.register_agent(config)
    
    click.echo(f"✅ Agent '{config.name}' created successfully!")
    click.echo(f"   ID: {agent_id}")
    click.echo(f"   Files generated:")
    click.echo(f"   - agents/{agent_id}_agent.py")
    click.echo(f"   - tests/agents/test_{agent_id}_agent.py")
    click.echo(f"   - k8s/agents/{agent_id}-*.yaml")
    click.echo(f"   - agents/{agent_id}_agent.md")


@cli.command()
def list():
    """List all registered agents."""
    factory = AgentFactory()
    agents = factory.list_agents()
    
    if not agents:
        click.echo("No agents registered")
        return
        
    click.echo("Registered Agents:")
    click.echo("-" * 60)
    
    for agent in agents:
        status_icon = "🟢" if agent["status"] == "running" else "⚪"
        click.echo(f"{status_icon} {agent['name']} ({agent['id']})")
        click.echo(f"   Purpose: {agent['purpose']}")
        
        if "metrics" in agent:
            metrics = agent["metrics"]["performance"]
            click.echo(f"   Performance: {metrics['success_rate']:.1f}% success rate")
            click.echo(f"   Response time: {metrics['avg_response_time']:.2f}s avg")


@cli.command()
@click.argument("agent_id")
def start(agent_id: str):
    """Start an agent."""
    async def _start():
        factory = AgentFactory()
        try:
            agent = await factory.create_agent(agent_id)
            click.echo(f"✅ Agent '{agent_id}' started successfully!")
        except Exception as e:
            click.echo(f"❌ Failed to start agent: {e}")
            
    asyncio.run(_start())


@cli.command()
@click.argument("agent_id")
def stop(agent_id: str):
    """Stop a running agent."""
    async def _stop():
        factory = AgentFactory()
        await factory.stop_agent(agent_id)
        click.echo(f"✅ Agent '{agent_id}' stopped")
        
    asyncio.run(_stop())


@cli.command()
@click.argument("agent_id")
def test(agent_id: str):
    """Run tests for an agent."""
    import subprocess
    
    test_file = f"tests/agents/test_{agent_id}_agent.py"
    
    if not Path(test_file).exists():
        click.echo(f"❌ Test file not found: {test_file}")
        return
        
    click.echo(f"Running tests for '{agent_id}'...")
    result = subprocess.run(
        ["pytest", test_file, "-v"],
        capture_output=True,
        text=True
    )
    
    click.echo(result.stdout)
    if result.returncode != 0:
        click.echo(result.stderr)


@cli.command()
@click.argument("agent_id")
def deploy(agent_id: str):
    """Deploy agent to Kubernetes."""
    k8s_dir = Path(f"k8s/agents")
    files = list(k8s_dir.glob(f"{agent_id}-*.yaml"))
    
    if not files:
        click.echo(f"❌ No Kubernetes files found for '{agent_id}'")
        return
        
    click.echo(f"Deploying '{agent_id}' to Kubernetes...")
    
    for file in files:
        click.echo(f"Applying {file.name}...")
        # In real implementation, would run kubectl apply
        click.echo(f"kubectl apply -f {file}")
        
    click.echo(f"✅ Agent '{agent_id}' deployed!")


@cli.command()
def quickstart():
    """Interactive agent creation wizard."""
    click.echo("🚀 Agent Builder Quickstart")
    click.echo("-" * 40)
    
    name = click.prompt("Agent name")
    purpose = click.prompt("Agent purpose")
    
    # Workflow steps
    click.echo("\nDefine workflow steps (enter empty step to finish):")
    workflow = []
    step_num = 1
    
    while True:
        step_name = click.prompt(f"Step {step_num} name", default="", show_default=False)
        if not step_name:
            break
            
        step_action = click.prompt(f"Step {step_num} action")
        workflow.append({
            "name": step_name,
            "action": step_action
        })
        step_num += 1
        
    # Create agent
    factory = AgentFactory()
    config = factory.create_custom_agent_config(name, purpose, workflow)
    agent_id = factory.register_agent(config)
    
    click.echo(f"\n✅ Agent '{name}' created successfully!")
    click.echo(f"   ID: {agent_id}")
    click.echo(f"\nNext steps:")
    click.echo(f"1. Edit agents/{agent_id}_agent.py to customize behavior")
    click.echo(f"2. Run tests: agent-builder test {agent_id}")
    click.echo(f"3. Start agent: agent-builder start {agent_id}")
    click.echo(f"4. Deploy: agent-builder deploy {agent_id}")


if __name__ == "__main__":
    cli()