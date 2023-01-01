import discord
from discord.ext import commands

class EventOnReady(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        print("Cog: on_ready.py Loaded")
    

async def setup(bot):
    await bot.add_cog(EventOnReady(bot))
