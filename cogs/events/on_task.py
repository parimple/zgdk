from discord.ext import commands, tasks


class OnTaskEvent(commands.Cog):
    def __init__(self, bot):
        self.index = 0
        self.bot = bot
        self.printer.start()

    def cog_unload(self):
        self.printer.cancel()

    @tasks.loop(seconds=5.0)
    async def printer(self):
        # print(self.index)
        self.index += 1

    @printer.before_loop
    async def before_printer(self):
        print("waiting...")
        await self.bot.wait_until_ready()


async def setup(bot: commands.Bot):
    """Setup Function"""
    await bot.add_cog(OnTaskEvent(bot))
