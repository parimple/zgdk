#!/usr/bin/env python
"""
Main file for Zagadka bot.
"""

import asyncio
import logging
import os
from contextlib import asynccontextmanager
from typing import Any, Optional

import discord
import yaml
from discord.ext import commands
from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_scoped_session,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import sessionmaker

from datasources.models import Base
from utils.premium import PaymentData

intents = discord.Intents.all()


def load_config():
    with open("config.yml", encoding="utf-8") as f:
        return yaml.safe_load(f)


class Zagadka(commands.Bot):
    """Bot class."""

    def __init__(self, config, **kwargs):
        load_dotenv()

        self.test: bool = kwargs.get("test", False)
        self.config: dict[str, Any] = config

        self.guild_id: int = config.get("guild_id")
        self.donate_url: str = config.get("donate_url", "")
        self.channels: dict[str, int] = config.get("channels", {})

        self.guild: Optional[discord.Guild] = None
        self.invites: dict[str, discord.Invite] = {}

        database_url = self.get_database_url()

        self.engine = create_async_engine(
            database_url,
            pool_size=20,
            max_overflow=40,
            pool_timeout=30,
            pool_recycle=1800,
            pool_pre_ping=True,
        )
        self.SessionLocal = sessionmaker(
            self.engine, class_=AsyncSession, expire_on_commit=False
        )
        self.base = Base
        self.payment_data_class = PaymentData

        super().__init__(
            command_prefix=config.get("prefix"),
            intents=intents,
            status=discord.Status.do_not_disturb,
            allowed_mentions=discord.AllowedMentions.all(),
            **kwargs,
        )

    def get_database_url(self):
        postgres_user: str = os.environ.get("POSTGRES_USER", "")
        postgres_password: str = os.environ.get("POSTGRES_PASSWORD", "")
        postgres_db: str = os.environ.get("POSTGRES_DB", "")
        postgres_port: str = os.environ.get("POSTGRES_PORT", "")

        return (
            f"postgresql+asyncpg://"
            f"{postgres_user}:"
            f"{postgres_password}@db:"
            f"{postgres_port}/"
            f"{postgres_db}"
        )

    @asynccontextmanager
    async def get_db(self):
        async with self.SessionLocal() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    async def close(self):
        await self.engine.dispose()
        await super().close()

    async def load_cogs(self):
        """Load all cogs"""
        logging.info("Loading cogs...")
        for folder in ("cogs/commands", "cogs/events"):
            path = os.path.join(os.getcwd(), folder)
            for cog in os.listdir(path):
                if cog.endswith(".py") and cog != "__init__.py":
                    try:
                        await self.load_extension(
                            f"{folder.replace('/', '.')}.{cog[:-3]}"
                        )
                        logging.info("Loaded cog: %s", cog)
                    except (commands.ExtensionError, commands.CommandError) as error:
                        logging.error("Failed to load cog: %s, error: %s", cog, error)

    async def setup_hook(self):
        """Setup hook."""
        if not self.test:
            await self.load_cogs()

    async def on_ready(self):
        """On ready event"""
        logging.info("Event on_ready started")

        async with self.engine.begin() as conn:
            table_names = self.base.metadata.tables.keys()
            logging.info("Creating tables: %s", ", ".join(table_names))
            # await conn.run_sync(self.base.metadata.drop_all)
            await conn.run_sync(self.base.metadata.create_all)

        logging.info("Database create_all completed")

        await self.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.playing, name="zaGadka bot"
            )
        )
        logging.info("Event change_presence completed")

        if self.guild is None:
            # Get the guild object and assign it to self.guild
            guild = self.get_guild(self.guild_id)
            if guild is None:
                logging.error("Cannot find a guild with the ID %d.", self.guild_id)
            else:
                logging.info("Found guild: %s", guild.name)
                self.guild = guild

        if not self.test:
            await self.tree.sync(guild=discord.Object(id=self.guild_id))
            logging.info("Slash commands synchronized")

        logging.info("Ready")

    def run(self):
        """Run the bot"""
        token = os.environ.get("ZAGADKA_TOKEN")
        if token is None:
            raise ValueError(
                "Missing bot token. Ensure that ZAGADKA_TOKEN is set in the environment variables."
            )
        super().run(token, reconnect=True)

    @property
    def force_channel_notifications(self):
        """Get global notification setting"""
        return self.config.get("force_channel_notifications", True)

    @force_channel_notifications.setter
    def force_channel_notifications(self, value: bool):
        """Set global notification setting"""
        self.config["force_channel_notifications"] = value


def setup_logging():
    """Setup logging"""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


if __name__ == "__main__":
    setup_logging()
    config = load_config()
    bot = Zagadka(config=config)
    bot.run()
