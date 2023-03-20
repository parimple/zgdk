#!/usr/bin/env python
"""Main file for Zagadka bot"""

import logging
import os

import discord
import yaml
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()

intents = discord.Intents.all()

with open("config.yml", encoding="utf-8") as f:
    config = yaml.safe_load(f)


class Zagadka(commands.Bot):
    """Main class for Zagadka bot"""

    def __init__(self, **kwargs):
        self.test = kwargs.get("test", False)
        self.config = config

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
                        await self.load_extension(
                            f"{folder.replace('/', '.')}.{cog[:-3]}"
                        )
                        logging.info("Loaded cog: %s", cog)
                    except (commands.ExtensionError, commands.CommandError) as error:
                        logging.error("Failed to load cog: %s, error: %s", cog, error)

    async def on_ready(self):
        """On ready event"""
        logging.info("Ready")
        await self.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.playing, name="zaGadka bot"
            )
        )
        if not self.test:
            await self.load_cogs()

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
