"""Support Agent implementation using CrewAI + PydanticAI."""

import logging
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

import google.generativeai as genai
import redis.asyncio as redis
from crewai import Agent as CrewAgent
from crewai import Crew, Process, Task
from pydantic import BaseModel, Field
from pydantic_ai import Agent
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

# Configure Gemini
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))


class UserQuery(BaseModel):
    """Model for user queries."""

    message_id: str
    content: str
    author_id: int
    channel_id: int
    timestamp: datetime
    query_type: Optional[str] = Field(None, description="FAQ, complaint, or unclear")


class AgentResponse(BaseModel):
    """Model for agent responses."""

    response: str
    confidence: float = Field(ge=0.0, le=1.0)
    requires_escalation: bool = False
    escalation_reason: Optional[str] = None
    response_time_ms: float


class SupportAgentCrew:
    """Main Support Agent crew orchestrator."""

    def __init__(self, redis_client: redis.Redis, db_session: AsyncSession):
        self.redis_client = redis_client
        self.db_session = db_session
        self.crew = self._initialize_crew()

    def _initialize_crew(self) -> Crew:
        """Initialize CrewAI agents."""

        # Intake Agent - klasyfikuje zapytania
        intake_agent = CrewAgent(
            role="Dispatcher",
            goal="Classify incoming queries and route them appropriately",
            backstory="Expert at understanding user intent in Polish Discord messages",
            verbose=True,
            allow_delegation=True,
            llm="gemini/gemini-1.5-flash",
        )

        # FAQ Agent - odpowiada na typowe pytania
        faq_agent = CrewAgent(
            role="Knowledge Expert",
            goal="Provide accurate answers to frequently asked questions",
            backstory="Discord server expert with deep knowledge of zaGadka rules and features",
            verbose=True,
            allow_delegation=False,
            llm="gemini/gemini-1.5-flash",
        )

        # Complaint Agent - obsługuje skargi
        complaint_agent = CrewAgent(
            role="Complaint Handler",
            goal="Handle user complaints with empathy and professionalism",
            backstory="Experienced in de-escalation and conflict resolution in Polish",
            verbose=True,
            allow_delegation=False,
            llm="gemini/gemini-1.5-flash",
        )

        # Escalation Agent - decyduje o eskalacji
        escalation_agent = CrewAgent(
            role="Escalation Manager",
            goal="Identify issues requiring human moderator intervention",
            backstory="Expert at recognizing serious violations and urgent matters",
            verbose=True,
            allow_delegation=False,
            llm="gemini/gemini-1.5-flash",
        )

        return Crew(
            agents=[intake_agent, faq_agent, complaint_agent, escalation_agent],
            process=Process.hierarchical,
            manager_llm="gemini/gemini-1.5-flash",
        )

    async def process_query(self, query: UserQuery) -> AgentResponse:
        """Process user query through the crew."""
        start_time = datetime.now()

        # Check cache first
        cache_key = f"faq:{hash(query.content)}"
        cached_response = await self.redis_client.get(cache_key)

        if cached_response:
            response_time = (datetime.now() - start_time).total_seconds() * 1000
            return AgentResponse(
                response=cached_response.decode("utf-8"),
                confidence=0.95,
                requires_escalation=False,
                response_time_ms=response_time,
            )

        # Define tasks for the crew
        classification_task = Task(
            description=f"Classify this Polish Discord message: '{query.content}'",
            expected_output="One of: FAQ, COMPLAINT, UNCLEAR",
            agent=self.crew.agents[0],  # intake_agent
        )

        # Execute crew
        try:
            result = self.crew.kickoff(inputs={"query": query.content})

            # Process result based on classification
            response_text = self._format_response(result)
            confidence = self._calculate_confidence(result)
            requires_escalation = self._check_escalation(query, result)

            # Cache if FAQ
            if query.query_type == "FAQ" and confidence > 0.8:
                await self.redis_client.setex(cache_key, 3600, response_text.encode("utf-8"))

            response_time = (datetime.now() - start_time).total_seconds() * 1000

            return AgentResponse(
                response=response_text,
                confidence=confidence,
                requires_escalation=requires_escalation,
                escalation_reason="High severity complaint" if requires_escalation else None,
                response_time_ms=response_time,
            )

        except Exception as e:
            logger.error(f"Crew processing error: {e}")
            return AgentResponse(
                response="Przepraszam, wystąpił błąd. Spróbuj ponownie za chwilę.",
                confidence=0.0,
                requires_escalation=True,
                escalation_reason=f"System error: {str(e)}",
                response_time_ms=(datetime.now() - start_time).total_seconds() * 1000,
            )

    def _format_response(self, crew_result: Any) -> str:
        """Format crew result into user-friendly response."""
        # Simplified for now
        return str(crew_result)

    def _calculate_confidence(self, crew_result: Any) -> float:
        """Calculate confidence score."""
        # Simplified - would analyze crew consensus
        return 0.85

    def _check_escalation(self, query: UserQuery, result: Any) -> bool:
        """Check if escalation is needed."""
        # Simplified - would check for keywords, sentiment, etc.
        escalation_keywords = ["ban", "skarga", "moderator", "admin", "zgłaszam"]
        return any(keyword in query.content.lower() for keyword in escalation_keywords)
