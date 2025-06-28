"""AI Agent microservice for scalable AI processing."""

import asyncio
import logging
import os
from typing import Dict, Any, Optional
from contextlib import asynccontextmanager

import redis.asyncio as redis
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from pydantic_ai import Agent
import google.generativeai as genai

logger = logging.getLogger(__name__)


class AIRequest(BaseModel):
    """Request model for AI processing."""
    task_id: str
    task_type: str
    prompt: str
    context: Dict[str, Any]
    priority: int = 5


class AIResponse(BaseModel):
    """Response model for AI processing."""
    task_id: str
    result: str
    metadata: Dict[str, Any]


class AIAgentService:
    """Scalable AI agent service."""
    
    def __init__(self):
        self.redis_client = None
        self.agent = None
        self.processing = set()
        
    async def setup(self):
        """Setup connections and AI agent."""
        # Redis for task queue and caching
        self.redis_client = await redis.from_url(
            f"redis://{os.getenv('REDIS_HOST', 'localhost')}:6379"
        )
        
        # Setup AI agent
        genai.configure(api_key=os.getenv('GEMINI_API_KEY'))
        self.agent = Agent(
            'gemini-1.5-flash',
            system_prompt="Jesteś pomocnym asystentem Discord bota zaGadka."
        )
        
    async def cleanup(self):
        """Cleanup connections."""
        if self.redis_client:
            await self.redis_client.close()
    
    async def process_task(self, request: AIRequest) -> AIResponse:
        """Process AI task with caching."""
        # Check cache first
        cache_key = f"ai_result:{request.task_type}:{hash(request.prompt)}"
        cached = await self.redis_client.get(cache_key)
        if cached:
            logger.info(f"Cache hit for task {request.task_id}")
            return AIResponse(
                task_id=request.task_id,
                result=cached.decode(),
                metadata={"cached": True}
            )
        
        # Process with AI
        try:
            result = await self.agent.run(request.prompt)
            
            # Cache result
            await self.redis_client.setex(
                cache_key,
                3600,  # 1 hour TTL
                result.data
            )
            
            return AIResponse(
                task_id=request.task_id,
                result=result.data,
                metadata={"cached": False, "model": "gemini-1.5-flash"}
            )
            
        except Exception as e:
            logger.error(f"AI processing failed: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    async def get_queue_status(self) -> Dict[str, Any]:
        """Get queue and processing status."""
        queue_length = await self.redis_client.llen("ai_tasks")
        return {
            "queue_length": queue_length,
            "processing": len(self.processing),
            "healthy": True
        }


# FastAPI app
service = AIAgentService()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage service lifecycle."""
    await service.setup()
    yield
    await service.cleanup()


app = FastAPI(lifespan=lifespan)


@app.post("/process", response_model=AIResponse)
async def process_ai_task(request: AIRequest):
    """Process AI task endpoint."""
    return await service.process_task(request)


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    status = await service.get_queue_status()
    return {"status": "healthy", **status}


@app.get("/ready")
async def readiness_check():
    """Readiness check endpoint."""
    try:
        await service.redis_client.ping()
        return {"status": "ready"}
    except:
        raise HTTPException(status_code=503, detail="Not ready")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)