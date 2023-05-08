#!/usr/bin/env python
"""Main file for Zagadka bot"""

import logging
import os

import discord
import yaml
from discord.ext import commands
from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import declarative_base, sessionmaker

intents = discord.Intents.all()

with open("config.yml", encoding="utf-8") as f:
    config = yaml.safe_load(f)


class Zagadka(commands.Bot):
    """Main class for Zagadka bot"""

    def __init__(self, **kwargs):
        load_dotenv()

        self.test = kwargs.get("test", False)
        self.config = config

        postgres_user = os.environ.get("POSTGRES_USER")
        postgres_password = os.environ.get("POSTGRES_PASSWORD")
        postgres_db = os.environ.get("POSTGRES_DB")
        postgres_host = os.environ.get("POSTGRES_HOST")

        database_url = (
            f"postgresql+asyncpg://{postgres_user}:{postgres_password}"
            f"@{postgres_host}/{postgres_db}"
        )

        self.engine = create_async_engine(database_url)
        self.async_session = sessionmaker(self.engine, expire_on_commit=False, class_=AsyncSession)
        self.base = declarative_base()

        super().__init__(
            command_prefix=config["prefix"],
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
        logging.info("on_ready started")
        async with self.engine.begin() as conn:
            await conn.run_sync(self.base.metadata.create_all)
        logging.info("create_all completed")

        await self.change_presence(
            activity=discord.Activity(type=discord.ActivityType.playing, name="zaGadka bot")
        )
        logging.info("change_presence completed")

        if not self.test:
            await self.load_cogs()
        logging.info("Ready")

    def run(self):
        """Run the bot"""
        super().run(os.environ.get("ZAGADKA_TOKEN"), reconnect=True)


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
