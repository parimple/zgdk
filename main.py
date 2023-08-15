#!/usr/bin/env python
"""Main file for Zagadka bot"""

import asyncio
import logging
import os
from typing import Optional

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

from datasources.models import Base

intents = discord.Intents.all()

with open("config.yml", encoding="utf-8") as f:
    config = yaml.safe_load(f)


# pylint: disable=too-many-instance-attributes
class Zagadka(commands.Bot):
    """Main class for Zagadka bot"""

    def __init__(self, **kwargs):
        load_dotenv()

        self.test: bool = kwargs.get("test", False)
        self.config: dict = config
        self.guild_id: int = config.get("guild_id")
        self.guild: Optional[discord.Guild] = None
        self.donate_url: str = config.get("donate_url", "")

        postgres_user: str = os.environ.get("POSTGRES_USER", "")
        postgres_password: str = os.environ.get("POSTGRES_PASSWORD", "")
        postgres_db: str = os.environ.get("POSTGRES_DB", "")
        postgres_port: str = os.environ.get("POSTGRES_PORT", "")

        database_url = (
            f"postgresql+asyncpg://"
            f"{postgres_user}:"
            f"{postgres_password}@db:"
            f"{postgres_port}/"
            f"{postgres_db}"
        )

        self.engine = create_async_engine(database_url)
        self.session = async_scoped_session(
            async_sessionmaker(self.engine, expire_on_commit=False, class_=AsyncSession),
            scopefunc=asyncio.current_task,
        )
        self.base = Base

        super().__init__(
            command_prefix=config.get("prefix"),
            intents=intents,
            status=discord.Status.do_not_disturb,
            allowed_mentions=discord.AllowedMentions.all(),
            **kwargs,
        )

    async def load_cogs(self):
        """Load all cogs"""
        logging.info("Loading cogs...")
        for folder in ("cogs/commands", "cogs/events"):
            path = os.path.join(os.getcwd(), folder)
            for cog in os.listdir(path):
                if cog.endswith(".py") and cog != "__init__.py":
                    try:
                        await self.load_extension(f"{folder.replace('/', '.')}.{cog[:-3]}")
                        logging.info("Loaded cog: %s", cog)
                    except (commands.ExtensionError, commands.CommandError) as error:
                        logging.error("Failed to load cog: %s, error: %s", cog, error)

    async def on_ready(self):
        """On ready event"""
        logging.info("Event on_ready started")

        async with self.engine.begin() as conn:
            table_names = self.base.metadata.tables.keys()
            logging.info("Dropping tables: %s", ", ".join(table_names))
            await conn.run_sync(self.base.metadata.drop_all)
            await conn.run_sync(self.base.metadata.create_all)

        logging.info("Database create_all completed")

        await self.change_presence(
            activity=discord.Activity(type=discord.ActivityType.playing, name="zaGadka bot")
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
            await self.load_cogs()
        # await self.tree.sync(guild=guild)
        # await self.tree.sync()
        # await self.app_commands.sync(guild=self.guild_id)
        logging.info("Ready")

    def run(self):
        """Run the bot"""
        token = os.environ.get("ZAGADKA_TOKEN")
        if token is None:
            raise ValueError(
                "Missing bot token. Ensure that ZAGADKA_TOKEN is set in the environment variables."
            )
        super().run(token, reconnect=True)


def setup_logging():
    """Setup logging"""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


if __name__ == "__main__":
    setup_logging()
    bot = Zagadka()
    bot.run()
