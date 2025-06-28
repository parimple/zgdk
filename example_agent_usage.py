"""Example: Creating a Jay-Agent with Agent Builder."""

import asyncio

from agent_builder import AgentConfig, AgentFactory


async def main():
    """Demonstrate Agent Builder usage."""

    # Initialize factory
    factory = AgentFactory()

    # Example 1: Quick creation from template
    print("1. Creating Moderation Agent from template...")
    moderation_agent = await factory.create_moderation_agent()
    print(f"   ✅ Moderation agent ready!")

    # Example 2: Custom agent for sentiment analysis
    print("\n2. Creating custom Sentiment Analyzer...")

    sentiment_config = factory.create_custom_agent_config(
        name="Sentiment Analyzer",
        purpose="Analyze sentiment in Discord messages and provide emotional insights",
        workflow=[
            {
                "name": "Extract Message",
                "action": "Extract message content and context",
                "inputs": {"message": "Discord message"},
                "outputs": ["text", "author", "context"],
            },
            {
                "name": "Analyze Sentiment",
                "action": "Use Gemini AI to analyze emotional tone",
                "inputs": {"text": "Message text"},
                "outputs": ["sentiment", "confidence", "emotions"],
            },
            {
                "name": "Generate Insights",
                "action": "Create actionable insights from sentiment",
                "inputs": {"sentiment": "Analysis results"},
                "outputs": ["insights", "suggestions"],
            },
        ],
        inputs={"message_id": "str", "content": "str", "author_id": "int"},
        outputs={"sentiment": "str", "confidence": "float", "emotions": "List[str]", "insights": "str"},
        metrics=["total_processed", "avg_confidence", "sentiment_distribution"],
    )

    # Register and create the agent
    sentiment_id = factory.register_agent(sentiment_config)
    sentiment_agent = await factory.create_agent(sentiment_id)
    print(f"   ✅ Sentiment analyzer ready! ID: {sentiment_id}")

    # Example 3: List all agents
    print("\n3. All registered agents:")
    agents = factory.list_agents()
    for agent in agents:
        print(f"   - {agent['name']} ({agent['id']}): {agent['status']}")

    # Example 4: Using an agent
    print("\n4. Testing sentiment analysis...")

    # This would normally come from Discord
    from agents.sentiment_analyzer_agent import SentimentAnalyzerInput

    test_input = SentimentAnalyzerInput(
        message_id="123456", content="I'm so excited about this new feature! Can't wait to try it out!", author_id=789
    )

    try:
        result = await sentiment_agent.process(test_input)
        print(f"   Sentiment: {result.sentiment}")
        print(f"   Confidence: {result.confidence:.2%}")
        print(f"   Emotions: {', '.join(result.emotions)}")
        print(f"   Insights: {result.insights}")
    except Exception as e:
        print(f"   Error: {e}")

    # Example 5: Get metrics
    print("\n5. Agent metrics:")
    metrics = await sentiment_agent.get_metrics()
    for key, value in metrics.items():
        print(f"   {key}: {value}")

    # Cleanup
    await factory.stop_all()
    print("\n✅ All agents stopped")


# Quick one-liner to create and start an agent
async def quick_create():
    """One-liner agent creation."""
    factory = AgentFactory()

    # Create a test runner in one line
    test_runner = await factory.create_test_runner_agent()
    print("Test runner created and ready!")

    return test_runner


if __name__ == "__main__":
    print("🚀 Agent Builder Demo\n")
    asyncio.run(main())

    print("\n" + "=" * 50)
    print("Quick creation example:")
    asyncio.run(quick_create())
