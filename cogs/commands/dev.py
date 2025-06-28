"""Developer commands for rapid development and testing."""

import io
import logging
import textwrap
import traceback
from contextlib import redirect_stdout

import discord
from discord.ext import commands

from utils.permissions import is_zagadka_owner
from utils.quick_test import quick_test

logger = logging.getLogger(__name__)


class DevCog(commands.Cog, name="Developer"):
    """Developer tools for rapid development."""

    def __init__(self, bot):
        self.bot = bot
        self._last_result = None

    # Removed reload command - already exists in owner.py
    # @commands.hybrid_command(name="reload", aliases=["rl"])
    # @is_zagadka_owner()
    # async def reload(self, ctx, module: Optional[str] = None):
    #     """Reload a cog or all cogs instantly."""
    #     if module:
    #         try:
    #             await self.bot.reload_extension(f"cogs.{module}")
    #             await ctx.send(f"✅ Reloaded: `{module}`")
    #         except Exception as e:
    #             await ctx.send(f"❌ Failed: `{e}`")
    #     else:
    #         # Reload all
    #         success = 0
    #         failed = 0
    #         for extension in list(self.bot.extensions):
    #             try:
    #                 await self.bot.reload_extension(extension)
    #                 success += 1
    #             except Exception:
    #                 failed += 1
    #         await ctx.send(f"✅ Reloaded {success} cogs, {failed} failed")

    @commands.hybrid_command(name="test")
    @is_zagadka_owner()
    async def test_command(self, ctx, command_name: str, *, args: str = ""):
        """Quick test a command without execution."""
        # Parse args
        import shlex

        try:
            parsed_args = shlex.split(args) if args else []
        except Exception:
            parsed_args = args.split() if args else []

        # Run quick test
        result = await quick_test(self.bot, command_name, *parsed_args)

        if result["success"]:
            embed = discord.Embed(title=f"✅ Test: {command_name}", color=discord.Color.green())
            for i, resp in enumerate(result.get("responses", [])):
                embed.add_field(name=f"Response {i+1}", value=resp.get("content", "Embed sent"), inline=False)
        else:
            embed = discord.Embed(
                title=f"❌ Test Failed: {command_name}",
                description=f"```{result['error']}```",
                color=discord.Color.red(),
            )

        await ctx.send(embed=embed)

    @commands.hybrid_command(name="eval")
    @is_zagadka_owner()
    async def _eval(self, ctx, *, code: str):
        """Evaluate Python code for quick testing."""
        env = {
            "bot": self.bot,
            "ctx": ctx,
            "channel": ctx.channel,
            "author": ctx.author,
            "guild": ctx.guild,
            "message": ctx.message,
            "_": self._last_result,
            "discord": discord,
            "commands": commands,
        }

        env.update(globals())

        # Clean code
        code = code.strip("` ")
        if code.startswith("python"):
            code = code[6:]

        stdout = io.StringIO()

        to_compile = f'async def func():\n{textwrap.indent(code, "  ")}'

        try:
            exec(to_compile, env)
        except Exception as e:
            return await ctx.send(f"```py\n{e.__class__.__name__}: {e}\n```")

        func = env["func"]
        try:
            with redirect_stdout(stdout):
                ret = await func()
        except Exception:
            value = stdout.getvalue()
            await ctx.send(f"```py\n{value}{traceback.format_exc()}\n```")
        else:
            value = stdout.getvalue()

            if ret is None:
                if value:
                    await ctx.send(f"```py\n{value}\n```")
            else:
                self._last_result = ret
                await ctx.send(f"```py\n{value}{ret}\n```")

    @commands.hybrid_command(name="sql")
    @is_zagadka_owner()
    async def sql_query(self, ctx, *, query: str):
        """Execute SQL query for quick database checks."""
        try:
            async with self.bot.db_session() as session:
                from sqlalchemy import text

                result = await session.execute(text(query))

                if query.strip().upper().startswith("SELECT"):
                    rows = result.fetchall()
                    if not rows:
                        await ctx.send("No results found.")
                        return

                    # Format as table
                    headers = list(result.keys())
                    table = "```\n"
                    table += " | ".join(headers) + "\n"
                    table += "-" * (len(" | ".join(headers))) + "\n"

                    for row in rows[:10]:  # Limit to 10 rows
                        table += " | ".join(str(v) for v in row) + "\n"

                    if len(rows) > 10:
                        table += f"\n... and {len(rows) - 10} more rows"

                    table += "```"
                    await ctx.send(table)
                else:
                    await session.commit()
                    await ctx.send(f"✅ Query executed: {result.rowcount} rows affected")

        except Exception as e:
            await ctx.send(f"❌ Error: ```{e}```")


async def setup(bot):
    """Setup the cog."""
    await bot.add_cog(DevCog(bot))
