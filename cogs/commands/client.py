"""This is a simple example of a cog."""

from discord.ext import commands


class CommandsClient(commands.Cog):
    """This is a simple example of a cog."""

    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        """Event listener which is called when the bot goes online."""
        print("Cog: client.py Loaded")

    @commands.command(name="ping", description="Sends Pong!")
    async def ping(self, ctx: commands.Context):
        """Sends Pong! when ping is used as a command."""
        await ctx.send("pong")


async def setup(bot):
    """This function is called when the cog is loaded."""
    await bot.add_cog(CommandsClient(bot))
