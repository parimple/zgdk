"""Voice commands cog."""

import discord
from discord.ext import commands
from discord.voice_client import VoiceClient


class VoiceCog(commands.Cog):
    """Voice commands cog."""

    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="join", help="Dołaczę do kanalu głosowego")
    async def join(self, ctx):
        """Join the voice channel the user is in."""

        if ctx.author.voice is None:
            await ctx.send("Nie jesteś na żadnym kanale głosowym!")
            return

        voice_channel = ctx.author.voice.channel
        if ctx.voice_client is None:
            await voice_channel.connect()
        else:
            await ctx.voice_client.move_to(voice_channel)

    @commands.command(name="leave", help="Opuszczę kanał głosowy")
    async def leave(self, ctx):
        """Leave the voice channel."""
        if ctx.voice_client is not None:
            await ctx.voice_client.disconnect()
        else:
            await ctx.send("Nie jestem na żadnym kanale głosowym!")


async def setup(bot):
    """This function is called when the cog is loaded."""
    await bot.add_cog(VoiceCog(bot))
