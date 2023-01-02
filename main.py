import os
import yaml
from dotenv import load_dotenv

import discord
from discord.ext import commands

load_dotenv()

intents = discord.Intents.all()

with open("config.yml") as f:
    config = yaml.safe_load(f)

class Zagadka(commands.Bot):
    def __init__(self, **kwargs):
        super().__init__(
            command_prefix=config["prefix"],
            intents=intents,
            status=discord.Status.do_not_disturb,
            allowed_mentions=discord.AllowedMentions.all(),
            **kwargs,
        )
    
    async def load_cogs(self):
        for cog in os.listdir("cogs/commands"):
            if cog.endswith(".py"):
                await self.load_extension(f"cogs.commands.{cog[:-3]}")
        print("All commands loaded")

        for cog in os.listdir("cogs/events"):
            if cog.endswith(".py"):
                await self.load_extension(f"cogs.events.{cog[:-3]}")
        print("All events loaded")

    async def on_ready(self):
        print("Ready")
        await self.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.playing,
                name="discord.gg/zagadka"
            ))
        await self.load_cogs()

bot = Zagadka()
bot.run(os.environ.get("DISCORD_TOKEN"))
