#!/bin/bash
"""Main file for Zagadka bot"""

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
        print(os.getcwd())
        for cog in os.listdir(os.path.join(os.getcwd(), "cogs/commands")):
            print(cog)
            if cog.endswith(".py") and cog != "__init__.py":
                await self.load_extension(f"cogs.commands.{cog[:-3]}")
        print("All commands loaded")

        for cog in os.path.join(os.getcwd(), "cogs/events"):
            if cog.endswith(".py") and cog != "__init__.py":
                await self.load_extension(f"cogs.events.{cog[:-3]}")
        print("All events loaded")

    async def on_ready(self):
        """On ready event"""
        print("Ready")
        await self.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.playing, name="discord.gg/zagadka"
            )
        )
        if not self.test:
            await self.load_cogs()

    def run(self):
        """Run the bot"""
        super().run(os.environ.get("ZAGADKA_TOKEN"), reconnect=True)


if __name__ == "__main__":
    bot = Zagadka()
    bot.run()
