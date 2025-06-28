"""Help and documentation commands cog."""

import logging
from collections import Counter

import discord
from discord.ext import commands

from utils.permissions import is_admin

logger = logging.getLogger(__name__)


class HelpInfoCog(commands.Cog):
    """Help and documentation commands cog."""

    def __init__(self, bot):
        """Initialize help info cog."""
        self.bot = bot
        # Remove default help command
        self.bot.remove_command("help")

    @commands.Cog.listener()
    async def on_ready(self):
        """Event listener which is called when the bot goes online."""
        logger.info("Cog: help_info.py Loaded")

    @commands.hybrid_command(name="pomoc", aliases=["help"], description="Wyświetla listę komend.")
    @is_admin()
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def help_command(self, ctx: commands.Context):
        """Display help menu with available commands."""
        embed = discord.Embed(
            title="📖 **Menu Pomocy**",
            description="Lista dostępnych komend:",
            color=discord.Color.blue(),
        )

        # Voice commands
        voice_commands = (
            "**Komendy Głosowe:**\n"
            "`/speak` - Zezwól użytkownikowi na mówienie\n"
            "`/connect [nazwa]` - Utwórz kanał głosowy\n"
            "`/view [add/remove] @user` - Zarządzaj widocznością kanału\n"
            "`/text` - Przełącz kanał tekstowy\n"
            "`/live` - Przełącz transmisję na żywo\n"
            "`/mod [add/remove] @user` - Zarządzaj moderatorami\n"
            "`/limit [liczba]` - Ustaw limit użytkowników\n"
            "`/voicechat [rename/claim/transfer]` - Zarządzaj kanałem\n"
            "`/reset` - Zresetuj ustawienia kanału\n"
            "`/autokick` - Zarządzaj automatycznym wyrzucaniem"
        )

        # Info commands
        info_commands = (
            "**Komendy Informacyjne:**\n"
            "`/profile [@user]` - Wyświetl profil użytkownika\n"
            "`/shop` - Otwórz sklep\n"
            "`/games` - Zobacz aktywne gry na serwerze\n"
            "`/bump` - Podbij serwer"
        )

        embed.add_field(name="\u200b", value=voice_commands, inline=False)
        embed.add_field(name="\u200b", value=info_commands, inline=False)

        embed.set_footer(text=f"Prefix: {self.bot.command_prefix} | Wspierane są również komendy slash (/)")

        await ctx.send(embed=embed)

    @commands.hybrid_command(name="games", aliases=["gry"], description="Pokazuje aktywne gry na serwerze.")
    async def games(self, ctx: commands.Context):
        """Show what games people are playing on the server."""
        # Send initial loading message
        loading_embed = discord.Embed(
            title="🎮 Aktywne Gry", description="⏳ Ładowanie danych...", color=discord.Color.blue()
        )
        message = await ctx.send(embed=loading_embed)

        # Collect game data
        games_counter = Counter()
        total_playing = 0

        for member in ctx.guild.members:
            if member.bot:
                continue

            for activity in member.activities:
                if isinstance(activity, discord.Game) or (
                    isinstance(activity, discord.Activity) and activity.type == discord.ActivityType.playing
                ):
                    game_name = activity.name
                    games_counter[game_name] += 1
                    total_playing += 1

        if not games_counter:
            no_games_embed = discord.Embed(
                title="🎮 Aktywne Gry", description="Obecnie nikt nie gra w żadne gry.", color=discord.Color.orange()
            )
            await message.edit(embed=no_games_embed)
            return

        # Sort games by player count
        sorted_games = sorted(games_counter.items(), key=lambda x: x[1], reverse=True)

        # Create pages (10 games per page)
        pages = []
        games_per_page = 10

        for i in range(0, len(sorted_games), games_per_page):
            page_games = sorted_games[i : i + games_per_page]

            embed = discord.Embed(title="🎮 Aktywne Gry na Serwerze", color=discord.Color.green())

            description = ""
            for rank, (game, count) in enumerate(page_games, start=i + 1):
                percentage = (count / total_playing) * 100
                emoji = self._get_rank_emoji(rank)
                description += f"{emoji} **{game}**\n"
                description += f"   👥 {count} {'gracz' if count == 1 else 'graczy'} ({percentage:.1f}%)\n\n"

            embed.description = description
            embed.set_footer(
                text=f"Strona {i // games_per_page + 1}/{(len(sorted_games) - 1) // games_per_page + 1} | "
                f"Łącznie graczy: {total_playing} | Różnych gier: {len(games_counter)}"
            )

            pages.append(embed)

        # If only one page, just edit the message
        if len(pages) == 1:
            await message.edit(embed=pages[0])
            return

        # Create paginated view
        view = GamesPaginator(pages)
        await message.edit(embed=pages[0], view=view)

    def _get_rank_emoji(self, rank: int) -> str:
        """Get emoji for ranking position."""
        if rank == 1:
            return "🥇"
        elif rank == 2:
            return "🥈"
        elif rank == 3:
            return "🥉"
        elif rank <= 10:
            return f"#{rank}"
        else:
            return "▫️"


class GamesPaginator(discord.ui.View):
    """Pagination view for games list."""

    def __init__(self, pages):
        super().__init__(timeout=180)
        self.pages = pages
        self.current_page = 0
        self.update_buttons()

    def update_buttons(self):
        """Update button states based on current page."""
        self.previous_page.disabled = self.current_page == 0
        self.next_page.disabled = self.current_page >= len(self.pages) - 1

    @discord.ui.button(label="◀", style=discord.ButtonStyle.primary)
    async def previous_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Go to previous page."""
        self.current_page -= 1
        self.update_buttons()
        await interaction.response.edit_message(embed=self.pages[self.current_page], view=self)

    @discord.ui.button(label="▶", style=discord.ButtonStyle.primary)
    async def next_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Go to next page."""
        self.current_page += 1
        self.update_buttons()
        await interaction.response.edit_message(embed=self.pages[self.current_page], view=self)

    async def on_timeout(self):
        """Disable all buttons on timeout."""
        for item in self.children:
            item.disabled = True


async def setup(bot: commands.Bot):
    """Setup function to add cog to bot."""
    await bot.add_cog(HelpInfoCog(bot))
