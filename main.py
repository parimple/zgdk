import os
import yaml
from dotenv import load_dotenv

import asyncio
import discord
from discord.ext import commands

load_dotenv()

with open('config.yml') as f:
    config = yaml.safe_load(f)

intents = discord.Intents.all()

bot = commands.Bot(
    command_prefix=commands.when_mentioned_or("/", config["prefix"]), 
    intents=intents
)
bot.config = config

async def load_cogs():
    # Load commands
    for cog in os.listdir("./cogs/commands"):
        if cog.endswith(".py"):
            print(cog)
            try:
                await bot.load_extension(f"cogs.commands.{cog[:-3]}")
            except Exception as e:
                print(f"Failed to load cog {cog}: {e}")
    # Load events
    for cog in os.listdir("./cogs/events"):
        if cog.endswith(".py"):
            try:
                await bot.load_extension(f"cogs.events.{cog[:-3]}")
            except Exception as e:
                print(f"Failed to load cog {cog}: {e}")

    # Run the bot
    await bot.start(os.environ['DISCORD_TOKEN'])

if __name__ == "__main__":
    asyncio.run(load_cogs())
    bot.run(os.environ['DISCORD_TOKEN'])


