"""Voice commands cog."""

from discord.ext import commands


class VoiceCog(commands.Cog):
    """Voice commands cog."""

    def __init__(self, bot):
        self.bot = bot

    @commands.hybrid_command()
    async def join(self, ctx):
        """Join the voice channel the user is in."""
        if ctx.author.voice is None:
            await ctx.reply("Nie jesteś na żadnym kanale głosowym!")
            return

        voice_channel = ctx.author.voice.channel
        if ctx.voice_client is None:
            await voice_channel.connect()
        else:
            await ctx.voice_client.move_to(voice_channel)

    @commands.hybrid_command()
    async def leave(self, ctx):
        """Leave the voice channel."""
        if ctx.voice_client is not None:
            await ctx.voice_client.disconnect()
        else:
            await ctx.reply("Nie jestem na żadnym kanale głosowym!")

    @commands.hybrid_command()
    async def limit(self, ctx, max_members: int):
        """Change the maximum number of members that can join the current voice channel."""
        if ctx.author.voice is None:
            await ctx.reply("Nie jesteś na żadnym kanale głosowym!")
            return

        if max_members < 1 or max_members > 99:
            await ctx.reply("Podaj liczbę członków od 1 do 99.")
            return

        voice_channel = ctx.author.voice.channel
        await voice_channel.edit(user_limit=max_members)
        await ctx.reply(
            f"Limit członków na kanale {voice_channel} ustawiony na {max_members}."
        )


async def setup(bot):
    """This function is called when the cog is loaded."""
    await bot.add_cog(VoiceCog(bot))
