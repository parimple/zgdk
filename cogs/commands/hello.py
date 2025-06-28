"""Simple hello command for testing hot reload."""

import time

from discord.ext import commands


class HelloCog(commands.Cog):
    """Test cog for hot reload verification."""

    def __init__(self, bot):
        self.bot = bot
        self.created_at = time.time()

    @commands.hybrid_command(name="hello")
    async def hello(self, ctx):
        """Simple hello world command."""
        load_time = time.time() - self.created_at
        await ctx.send(f"Hello World! 🌍 (Loaded {load_time:.2f}s ago)")


async def setup(bot):
    """Setup the cog."""
    await bot.add_cog(HelloCog(bot))
