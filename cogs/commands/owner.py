"""Owner commands cog for bot management."""

import logging
import os
import sys
from typing import Literal, Optional

import discord
from discord import app_commands
from discord.ext import commands

from utils.message_sender import MessageSender
from utils.permissions import is_zagadka_owner

logger = logging.getLogger(__name__)


class OwnerCog(commands.Cog):
    """Owner commands for bot management."""

    def __init__(self, bot):
        """
        Initialize the OwnerCog.

        :param bot: The bot instance
        :type bot: commands.Bot
        """
        self.bot = bot
        self.message_sender = MessageSender()

    @commands.hybrid_command(name="reboot", description="Restartuje całego bota.")
    @is_zagadka_owner()
    async def reboot(self, ctx: commands.Context):
        """
        Restartuje całego bota.

        :param ctx: Context komendy
        :type ctx: commands.Context
        :return: None
        """
        base_text = "🔄 Restartuję bota..."

        # Dodaj informację o planie premium
        channel = ctx.author.voice.channel if ctx.author.voice else None
        _, premium_text = self.message_sender._get_premium_text(ctx, channel)
        if premium_text:
            base_text = f"{base_text}\n{premium_text}"

        embed = self.message_sender._create_embed(description=base_text, ctx=ctx)
        await self.message_sender._send_embed(ctx, embed, reply=True)

        # Zamknij połączenie z bazą danych
        await self.bot.close()

        # Restartuj proces Pythona
        os.execv(sys.executable, ["python"] + sys.argv)

    @commands.hybrid_command(name="reload", description="Przeładuj wybrane lub wszystkie cogi.")
    @is_zagadka_owner()
    @app_commands.describe(
        cog_name="Nazwa coga do przeładowania (opcjonalne, bez .py)",
        folder="Folder z cogami (commands/events)",
    )
    async def reload(
        self,
        ctx: commands.Context,
        cog_name: Optional[str] = None,
        folder: Optional[Literal["commands", "events"]] = None,
    ):
        """
        Przeładuj wybrane lub wszystkie cogi.

        :param ctx: Context komendy
        :type ctx: commands.Context
        :param cog_name: Nazwa coga do przeładowania (bez .py)
        :type cog_name: Optional[str]
        :param folder: Folder z cogami (commands/events)
        :type folder: Optional[Literal["commands", "events"]]
        :return: None
        """

        async def reload_cog(cog_path: str) -> tuple[str, bool, str]:
            """
            Przeładuj pojedynczy cog i zwróć status.

            :param cog_path: Ścieżka do coga
            :type cog_path: str
            :return: Krotka (ścieżka, status, wiadomość)
            :rtype: tuple[str, bool, str]
            """
            try:
                await self.bot.reload_extension(cog_path)
                return cog_path, True, "Sukces"
            except Exception as e:
                return cog_path, False, str(e)

        # Wyślij wiadomość początkową
        message = await ctx.send("Rozpoczynam przeładowywanie cogów...")

        results = []

        if cog_name and folder:
            # Przeładuj konkretny cog
            cog_path = f"cogs.{folder}.{cog_name}"
            result = await reload_cog(cog_path)
            results.append(result)
        else:
            # Przeładuj wszystkie cogi
            for base_folder in ("commands", "events"):
                if folder and base_folder != folder:
                    continue

                path = os.path.join(os.getcwd(), "cogs", base_folder)
                for file in os.listdir(path):
                    if file.endswith(".py") and file != "__init__.py":
                        cog_path = f"cogs.{base_folder}.{file[:-3]}"
                        result = await reload_cog(cog_path)
                        results.append(result)

        # Przygotuj embed z wynikami
        embed = discord.Embed(
            title="Status przeładowania cogów",
            color=discord.Color.green() if all(r[1] for r in results) else discord.Color.red(),
        )

        # Dodaj pola dla sukcesu i błędów
        successful = [r for r in results if r[1]]
        failed = [r for r in results if not r[1]]

        if successful:
            embed.add_field(
                name="✅ Przeładowane pomyślnie",
                value="\n".join(f"`{r[0]}`" for r in successful),
                inline=False,
            )

        if failed:
            embed.add_field(
                name="❌ Błędy przeładowania",
                value="\n".join(f"`{r[0]}`: {r[2]}" for r in failed),
                inline=False,
            )

        # Aktualizuj wiadomość z wynikami
        await message.edit(content=None, embed=embed)


async def setup(bot: commands.Bot):
    """
    Setup function for OwnerCog.

    :param bot: The bot instance
    :type bot: commands.Bot
    :return: None
    """
    await bot.add_cog(OwnerCog(bot))
