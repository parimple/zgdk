import discord
from discord.ext import commands

class CommandsClient(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
    
    @commands.Cog.listener()
    async def on_ready(self):
        print("Cog: client.py Loaded")

    # @commands.slash_command(name="ping", description="Sends Pong!")
    @commands.command(name="ping", description="Sends Pong!")
    async def ping(self, ctx):
        # Use `await ctx.send()` to send a message
        await ctx.send("pong")


async def setup(bot):
    await bot.add_cog(CommandsClient(bot))
