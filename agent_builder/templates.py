"""Pre-defined agent templates for common use cases."""

from typing import Any, Dict

from .core import AgentConfig


class AgentTemplate:
    """Collection of pre-defined agent templates."""

    @staticmethod
    def moderation_agent() -> AgentConfig:
        """Template for content moderation agent."""
        return AgentConfig(
            name="Content Moderator",
            purpose="Analyze and moderate Discord messages for inappropriate content",
            workflow=[
                {
                    "name": "Extract Content",
                    "action": "Extract message content and metadata",
                    "inputs": {"message": "Discord message object"},
                    "outputs": ["text", "author_id", "channel_id"],
                },
                {
                    "name": "Check Cache",
                    "action": "Check Redis cache for similar content",
                    "inputs": {"text_hash": "Hash of message content"},
                    "outputs": ["cached_result"],
                },
                {
                    "name": "AI Analysis",
                    "action": "Analyze content with Gemini AI for violations",
                    "inputs": {"text": "Message text", "context": "Channel context"},
                    "outputs": ["severity", "categories", "confidence"],
                },
                {
                    "name": "Take Action",
                    "action": "Execute moderation action based on severity",
                    "inputs": {"severity": "Violation severity", "message_id": "Message ID"},
                    "outputs": ["action_taken", "reason"],
                },
            ],
            inputs={"message_id": "str", "content": "str", "author_id": "int", "channel_id": "int", "guild_id": "int"},
            outputs={
                "is_violation": "bool",
                "severity": "Optional[str]",
                "categories": "List[str]",
                "action_taken": "Optional[str]",
                "confidence": "float",
            },
            metrics=[
                "total_processed",
                "total_errors",
                "avg_duration",
                "last_success",
                "violations_found",
                "false_positives",
            ],
            k8s_config={"replicas": 3, "minReplicas": 2, "maxReplicas": 10},
            resources={"requests": {"memory": "512Mi", "cpu": "200m"}, "limits": {"memory": "1Gi", "cpu": "1000m"}},
        )

    @staticmethod
    def analytics_agent() -> AgentConfig:
        """Template for server analytics agent."""
        return AgentConfig(
            name="Analytics Processor",
            purpose="Analyze server activity and generate insights",
            workflow=[
                {
                    "name": "Collect Data",
                    "action": "Gather activity data from database",
                    "inputs": {"time_range": "Time period", "metrics": "List of metrics"},
                    "outputs": ["raw_data"],
                },
                {
                    "name": "Process Data",
                    "action": "Process and aggregate data",
                    "inputs": {"raw_data": "Activity data"},
                    "outputs": ["aggregated_data", "trends"],
                },
                {
                    "name": "Generate Insights",
                    "action": "Use AI to generate insights from data",
                    "inputs": {"aggregated_data": "Processed data", "trends": "Identified trends"},
                    "outputs": ["insights", "recommendations"],
                },
                {
                    "name": "Create Report",
                    "action": "Format insights into readable report",
                    "inputs": {"insights": "AI insights", "data": "Supporting data"},
                    "outputs": ["report", "visualizations"],
                },
            ],
            inputs={"guild_id": "int", "time_range": "str", "metrics": "List[str]", "format": "str"},
            outputs={
                "report": "str",
                "insights": "List[Dict[str, Any]]",
                "trends": "Dict[str, Any]",
                "recommendations": "List[str]",
            },
            metrics=["total_processed", "total_errors", "avg_duration", "last_success", "reports_generated"],
            k8s_config={"replicas": 2, "minReplicas": 1, "maxReplicas": 5},
        )

    @staticmethod
    def test_runner_agent() -> AgentConfig:
        """Template for automated test runner agent."""
        return AgentConfig(
            name="Test Runner",
            purpose="Automatically run and analyze tests for bot commands",
            workflow=[
                {
                    "name": "Identify Changes",
                    "action": "Detect code changes in commands",
                    "inputs": {"commit_hash": "Git commit", "files": "Changed files"},
                    "outputs": ["affected_commands", "test_files"],
                },
                {
                    "name": "Generate Tests",
                    "action": "AI generates test cases for changes",
                    "inputs": {"commands": "Affected commands", "changes": "Code changes"},
                    "outputs": ["test_cases"],
                },
                {
                    "name": "Execute Tests",
                    "action": "Run generated and existing tests",
                    "inputs": {"test_cases": "Test specifications"},
                    "outputs": ["test_results", "coverage"],
                },
                {
                    "name": "Analyze Results",
                    "action": "Analyze test results and suggest fixes",
                    "inputs": {"results": "Test results", "failures": "Failed tests"},
                    "outputs": ["analysis", "suggestions", "fix_code"],
                },
            ],
            inputs={"trigger": "str", "target": "Optional[str]", "commit_hash": "Optional[str]", "branch": "str"},
            outputs={
                "success": "bool",
                "passed": "int",
                "failed": "int",
                "coverage": "float",
                "failures": "List[Dict[str, Any]]",
                "suggestions": "List[str]",
                "fix_code": "Optional[str]",
            },
            metrics=[
                "total_processed",
                "total_errors",
                "avg_duration",
                "last_success",
                "tests_generated",
                "fixes_suggested",
            ],
            k8s_config={"replicas": 1, "minReplicas": 1, "maxReplicas": 3},
        )

    @staticmethod
    def command_optimizer_agent() -> AgentConfig:
        """Template for command performance optimizer."""
        return AgentConfig(
            name="Command Optimizer",
            purpose="Analyze and optimize bot command performance",
            workflow=[
                {
                    "name": "Monitor Performance",
                    "action": "Collect command execution metrics",
                    "inputs": {"command": "Command name", "timeframe": "Analysis period"},
                    "outputs": ["metrics", "bottlenecks"],
                },
                {
                    "name": "Analyze Code",
                    "action": "AI analyzes code for optimization opportunities",
                    "inputs": {"code": "Command code", "metrics": "Performance metrics"},
                    "outputs": ["issues", "opportunities"],
                },
                {
                    "name": "Generate Optimizations",
                    "action": "Generate optimized code versions",
                    "inputs": {"issues": "Identified issues", "code": "Original code"},
                    "outputs": ["optimized_code", "improvements"],
                },
                {
                    "name": "Validate Changes",
                    "action": "Test optimized code for correctness",
                    "inputs": {"original": "Original code", "optimized": "Optimized code"},
                    "outputs": ["is_valid", "performance_gain"],
                },
            ],
            inputs={"command_name": "str", "threshold_ms": "float", "auto_apply": "bool"},
            outputs={
                "optimized": "bool",
                "performance_gain": "float",
                "changes": "List[Dict[str, Any]]",
                "new_code": "Optional[str]",
            },
            metrics=[
                "total_processed",
                "total_errors",
                "avg_duration",
                "last_success",
                "optimizations_found",
                "performance_improved",
            ],
            k8s_config={"replicas": 1, "minReplicas": 1, "maxReplicas": 2},
        )

    @staticmethod
    def custom_agent(name: str, purpose: str) -> AgentConfig:
        """Create a custom agent with basic structure."""
        return AgentConfig(
            name=name,
            purpose=purpose,
            workflow=[
                {
                    "name": "Input Processing",
                    "action": "Process and validate input data",
                    "inputs": {"data": "Input data"},
                    "outputs": ["processed_data"],
                },
                {
                    "name": "AI Processing",
                    "action": "Process data with AI model",
                    "inputs": {"data": "Processed data"},
                    "outputs": ["result"],
                },
                {
                    "name": "Output Formatting",
                    "action": "Format result for output",
                    "inputs": {"result": "AI result"},
                    "outputs": ["formatted_output"],
                },
            ],
            inputs={"data": "Dict[str, Any]"},
            outputs={"result": "Any", "metadata": "Dict[str, Any]"},
            metrics=["total_processed", "total_errors", "avg_duration", "last_success"],
            k8s_config={"replicas": 2, "minReplicas": 1, "maxReplicas": 5},
        )
