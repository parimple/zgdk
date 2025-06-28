#!/usr/bin/env python3
"""
MCP (Model Context Protocol) Server for ZGDK Discord Bot
Allows easy communication, testing, and monitoring of the bot.
"""

import asyncio
import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from mcp.server import Server, Tool
from mcp.server.stdio import stdio_transport
from pydantic import BaseModel, Field

# Import bot components
from core.interpretability import DecisionLogger
from datasources.queries import MemberQueries, RoleQueries

logger = logging.getLogger(__name__)


class BotStatus(BaseModel):
    """Bot status information."""
    online: bool
    guild_count: int
    member_count: int
    uptime_seconds: float
    last_error: Optional[str] = None
    active_features: List[str]


class CommandResult(BaseModel):
    """Result of command execution."""
    success: bool
    command: str
    user_id: str
    result: Optional[str] = None
    error: Optional[str] = None
    execution_time_ms: float
    decision_id: Optional[str] = None


class UserInfo(BaseModel):
    """User information from database."""
    user_id: str
    balance: int
    premium_roles: List[str]
    team_name: Optional[str] = None
    bypass_hours: float = 0
    activity_points: int = 0


class ZGDKMCPServer:
    """MCP Server for ZGDK Discord Bot."""
    
    def __init__(self, bot_instance=None):
        self.server = Server("zgdk-bot")
        self.bot = bot_instance
        self.start_time = datetime.utcnow()
        self._setup_tools()
    
    def _setup_tools(self):
        """Setup MCP tools for bot interaction."""
        
        @self.server.tool()
        async def bot_status() -> Dict[str, Any]:
            """Get current bot status and statistics."""
            if not self.bot:
                return {"error": "Bot not connected"}
            
            uptime = (datetime.utcnow() - self.start_time).total_seconds()
            
            return {
                "online": self.bot.is_ready(),
                "guild_count": len(self.bot.guilds),
                "member_count": sum(g.member_count for g in self.bot.guilds),
                "uptime_seconds": uptime,
                "latency_ms": self.bot.latency * 1000,
                "active_cogs": list(self.bot.cogs.keys()),
                "command_count": len(self.bot.commands)
            }
        
        @self.server.tool()
        async def execute_command(
            command: str = Field(description="Command to execute (without prefix)"),
            user_id: str = Field(description="Discord user ID"),
            args: str = Field(default="", description="Command arguments"),
            guild_id: Optional[str] = Field(default=None, description="Guild ID for context")
        ) -> Dict[str, Any]:
            """Execute a bot command as a specific user."""
            if not self.bot:
                return {"error": "Bot not connected"}
            
            start_time = asyncio.get_event_loop().time()
            
            try:
                # Create fake context for command execution
                from tests.utils.helpers import create_mock_context
                
                guild = self.bot.get_guild(int(guild_id)) if guild_id else self.bot.guilds[0]
                member = guild.get_member(int(user_id))
                
                if not member:
                    return {"error": f"Member {user_id} not found in guild"}
                
                ctx = create_mock_context(self.bot, member, guild)
                ctx.command = self.bot.get_command(command)
                
                if not ctx.command:
                    return {"error": f"Command '{command}' not found"}
                
                # Parse arguments
                if args:
                    ctx.args = args.split()
                
                # Execute command
                await ctx.command.invoke(ctx)
                
                execution_time = (asyncio.get_event_loop().time() - start_time) * 1000
                
                # Get decision if logged
                decision_id = None
                if hasattr(self.bot, 'decision_logger'):
                    decisions = self.bot.decision_logger.get_user_decisions(user_id, limit=1)
                    if decisions:
                        decision_id = decisions[0].decision_id
                
                return {
                    "success": True,
                    "command": command,
                    "user_id": user_id,
                    "result": "Command executed successfully",
                    "execution_time_ms": execution_time,
                    "decision_id": decision_id
                }
                
            except Exception as e:
                return {
                    "success": False,
                    "command": command,
                    "user_id": user_id,
                    "error": str(e),
                    "execution_time_ms": (asyncio.get_event_loop().time() - start_time) * 1000
                }
        
        @self.server.tool()
        async def get_user_info(
            user_id: str = Field(description="Discord user ID")
        ) -> Dict[str, Any]:
            """Get user information from database."""
            if not self.bot:
                return {"error": "Bot not connected"}
            
            try:
                async with self.bot.get_db() as session:
                    # Get member info
                    member = await MemberQueries.get_member(session, int(user_id))
                    if not member:
                        return {"error": f"User {user_id} not found in database"}
                    
                    # Get roles
                    roles = await RoleQueries.get_member_roles(session, int(user_id))
                    premium_roles = []
                    
                    for role in roles:
                        role_obj = self.bot.guild.get_role(role.role_id)
                        if role_obj:
                            premium_roles.append(role_obj.name)
                    
                    # Get team info
                    team_name = None
                    if member.team_id:
                        from datasources.queries import TeamQueries
                        team = await TeamQueries.get_team(session, member.team_id)
                        if team:
                            team_name = team.name
                    
                    return {
                        "user_id": user_id,
                        "balance": member.wallet_balance or 0,
                        "premium_roles": premium_roles,
                        "team_name": team_name,
                        "bypass_hours": member.bypass_hours or 0,
                        "activity_points": member.points or 0,
                        "join_date": member.joined_at.isoformat() if member.joined_at else None
                    }
                    
            except Exception as e:
                return {"error": f"Database error: {str(e)}"}
        
        @self.server.tool()
        async def analyze_decisions(
            user_id: Optional[str] = Field(default=None, description="Filter by user ID"),
            command: Optional[str] = Field(default=None, description="Filter by command"),
            limit: int = Field(default=10, description="Number of decisions to analyze")
        ) -> Dict[str, Any]:
            """Analyze bot decisions using interpretability system."""
            if not self.bot or not hasattr(self.bot, 'decision_logger'):
                return {"error": "Interpretability system not available"}
            
            try:
                if user_id:
                    decisions = self.bot.decision_logger.get_user_decisions(user_id, limit)
                elif command:
                    decisions = self.bot.decision_logger.get_command_decisions(command, limit)
                else:
                    decisions = self.bot.decision_logger.current_session[-limit:]
                
                # Analyze features if available
                feature_analysis = {}
                if hasattr(self.bot, 'feature_extractor'):
                    feature_counts = {}
                    for decision in decisions:
                        features = self.bot.feature_extractor.extract_features(decision)
                        for feature, strength in features:
                            if feature.name not in feature_counts:
                                feature_counts[feature.name] = 0
                            feature_counts[feature.name] += strength
                    
                    feature_analysis = {
                        "most_common_features": sorted(
                            feature_counts.items(), 
                            key=lambda x: x[1], 
                            reverse=True
                        )[:5]
                    }
                
                return {
                    "decisions_analyzed": len(decisions),
                    "decisions": [
                        {
                            "id": d.decision_id,
                            "type": d.decision_type.value,
                            "command": d.command,
                            "result": d.result,
                            "reason": d.reason,
                            "confidence": d.confidence,
                            "timestamp": d.timestamp.isoformat()
                        }
                        for d in decisions
                    ],
                    "feature_analysis": feature_analysis
                }
                
            except Exception as e:
                return {"error": f"Analysis error: {str(e)}"}
        
        @self.server.tool()
        async def modify_user_balance(
            user_id: str = Field(description="Discord user ID"),
            amount: int = Field(description="Amount to add (negative to subtract)"),
            reason: str = Field(default="MCP adjustment", description="Reason for change")
        ) -> Dict[str, Any]:
            """Modify user's balance for testing."""
            if not self.bot:
                return {"error": "Bot not connected"}
            
            try:
                async with self.bot.get_db() as session:
                    # Get current balance
                    member = await MemberQueries.get_or_add_member(session, int(user_id))
                    old_balance = member.wallet_balance or 0
                    
                    # Update balance
                    await MemberQueries.add_to_wallet_balance(session, int(user_id), amount)
                    await session.commit()
                    
                    new_balance = old_balance + amount
                    
                    # Log the change
                    logger.info(f"MCP: Balance modified for {user_id}: {old_balance} -> {new_balance} ({reason})")
                    
                    return {
                        "success": True,
                        "user_id": user_id,
                        "old_balance": old_balance,
                        "new_balance": new_balance,
                        "change": amount,
                        "reason": reason
                    }
                    
            except Exception as e:
                return {"error": f"Balance modification failed: {str(e)}"}
        
        @self.server.tool()
        async def simulate_message(
            content: str = Field(description="Message content"),
            user_id: str = Field(description="Discord user ID"),
            channel_id: str = Field(description="Channel ID"),
            guild_id: Optional[str] = Field(default=None, description="Guild ID")
        ) -> Dict[str, Any]:
            """Simulate a Discord message for testing."""
            if not self.bot:
                return {"error": "Bot not connected"}
            
            try:
                # Create fake message
                from tests.utils.helpers import create_mock_message
                
                guild = self.bot.get_guild(int(guild_id)) if guild_id else self.bot.guilds[0]
                channel = guild.get_channel(int(channel_id))
                member = guild.get_member(int(user_id))
                
                if not channel or not member:
                    return {"error": "Channel or member not found"}
                
                message = create_mock_message(content, member, channel)
                
                # Process message through bot
                await self.bot.on_message(message)
                
                return {
                    "success": True,
                    "message_content": content,
                    "user_id": user_id,
                    "channel_id": channel_id,
                    "processed": True
                }
                
            except Exception as e:
                return {"error": f"Message simulation failed: {str(e)}"}
        
        @self.server.tool()
        async def get_performance_stats(
            command: Optional[str] = Field(default=None, description="Specific command to analyze")
        ) -> Dict[str, Any]:
            """Get performance statistics."""
            if not self.bot or not hasattr(self.bot, 'tracer'):
                return {"error": "Performance tracking not available"}
            
            try:
                if command:
                    stats = self.bot.tracer.get_command_performance(command)
                else:
                    # Overall stats
                    recent_traces = self.bot.tracer.get_recent_traces(20)
                    
                    if not recent_traces:
                        return {"message": "No performance data available"}
                    
                    durations = [t['total_duration_ms'] for t in recent_traces]
                    
                    stats = {
                        "total_traces": len(recent_traces),
                        "avg_duration_ms": sum(durations) / len(durations),
                        "min_duration_ms": min(durations),
                        "max_duration_ms": max(durations),
                        "commands": {}
                    }
                    
                    # Group by command
                    for trace in recent_traces:
                        cmd = trace['command']
                        if cmd not in stats['commands']:
                            stats['commands'][cmd] = []
                        stats['commands'][cmd].append(trace['total_duration_ms'])
                    
                    # Calculate per-command stats
                    for cmd, times in stats['commands'].items():
                        stats['commands'][cmd] = {
                            "count": len(times),
                            "avg_ms": sum(times) / len(times)
                        }
                
                return stats
                
            except Exception as e:
                return {"error": f"Performance analysis failed: {str(e)}"}
    
    async def run(self):
        """Run the MCP server."""
        async with stdio_transport(self.server) as transport:
            logger.info("ZGDK MCP Server started")
            await transport.start()


def connect_to_bot(bot_instance):
    """Connect MCP server to bot instance."""
    global mcp_server
    mcp_server = ZGDKMCPServer(bot_instance)
    return mcp_server


if __name__ == "__main__":
    # For standalone testing
    logging.basicConfig(level=logging.INFO)
    server = ZGDKMCPServer()
    asyncio.run(server.run())