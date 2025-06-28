#!/usr/bin/env python3
"""Check bump cooldown status in database."""

import asyncio
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select
from datasources.models import NotificationLog

DATABASE_URL = "postgresql+asyncpg://postgres:postgres@localhost:5432/zagadka"

async def check_cooldowns():
    engine = create_async_engine(DATABASE_URL)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with async_session() as session:
        # Check all notification logs
        result = await session.execute(
            select(NotificationLog).order_by(NotificationLog.sent_at.desc()).limit(10)
        )
        logs = result.scalars().all()
        
        print("Recent notification logs:")
        print("-" * 80)
        for log in logs:
            print(f"Service: {log.service}")
            print(f"User ID: {log.user_id}")
            print(f"Sent at: {log.sent_at}")
            print(f"Time since: {datetime.now(timezone.utc) - log.sent_at}")
            print("-" * 80)
    
    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(check_cooldowns())