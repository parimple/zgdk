"""Server info commands cog."""

import logging
from datetime import datetime, timezone

import discord
from discord.ext import commands

logger = logging.getLogger(__name__)


class ServerInfoCog(commands.Cog):
    """Server info commands cog."""

    def __init__(self, bot):
        """Initialize server info cog."""
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        """Event listener which is called when the bot goes online."""
        logger.info("Cog: server_info.py Loaded")

    @commands.hybrid_command(name="ping", description="Sends Pong!")
    async def ping(self, ctx: commands.Context):
        """Ping command."""
        embed = discord.Embed(title="Pong!", color=discord.Color.green())
        embed.add_field(name="Latency", value=f"{round(self.bot.latency * 1000)}ms", inline=False)
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="serverinfo", aliases=["si"], description="Pokazuje informacje o serwerze.")
    async def guild_info(self, ctx: commands.Context):
        """Pokazuje informacje o serwerze."""
        guild = ctx.guild

        embed = discord.Embed(
            title=f"Informacje o serwerze: {guild.name}",
            color=discord.Color.blue(),
            timestamp=datetime.now(timezone.utc),
        )

        # Basic information
        embed.set_thumbnail(url=guild.icon.url if guild.icon else None)
        embed.add_field(name="ID", value=guild.id, inline=True)
        embed.add_field(name="Właściciel", value=guild.owner.mention, inline=True)
        embed.add_field(name="Utworzony", value=guild.created_at.strftime("%Y-%m-%d"), inline=True)

        # Member statistics
        total_members = guild.member_count
        bots = len([m for m in guild.members if m.bot])
        humans = total_members - bots

        embed.add_field(
            name="Członkowie",
            value=f"👥 Wszyscy: {total_members}\n" f"👤 Ludzie: {humans}\n" f"🤖 Boty: {bots}",
            inline=True,
        )

        # Channel statistics
        text_channels = len(guild.text_channels)
        voice_channels = len(guild.voice_channels)
        categories = len(guild.categories)

        embed.add_field(
            name="Kanały",
            value=f"💬 Tekstowe: {text_channels}\n" f"🔊 Głosowe: {voice_channels}\n" f"📁 Kategorie: {categories}",
            inline=True,
        )

        # Other statistics
        roles = len(guild.roles)
        emojis = len(guild.emojis)
        boosts = guild.premium_subscription_count
        boost_level = guild.premium_tier

        embed.add_field(
            name="Inne",
            value=f"🏷️ Role: {roles}\n" f"😀 Emoji: {emojis}\n" f"🚀 Boosty: {boosts} (Poziom {boost_level})",
            inline=True,
        )

        # Server features
        if guild.features:
            features = ", ".join([f.replace("_", " ").title() for f in guild.features])
            embed.add_field(name="Funkcje", value=features[:1024], inline=False)

        # Verification level
        verification_levels = {
            discord.VerificationLevel.none: "Brak",
            discord.VerificationLevel.low: "Niski",
            discord.VerificationLevel.medium: "Średni",
            discord.VerificationLevel.high: "Wysoki",
            discord.VerificationLevel.highest: "Najwyższy",
        }

        embed.add_field(
            name="Poziom weryfikacji", value=verification_levels.get(guild.verification_level, "Nieznany"), inline=True
        )

        # Content filter
        content_filters = {
            discord.ContentFilter.disabled: "Wyłączony",
            discord.ContentFilter.no_role: "Bez roli",
            discord.ContentFilter.all_members: "Wszyscy",
        }

        embed.add_field(
            name="Filtr treści", value=content_filters.get(guild.explicit_content_filter, "Nieznany"), inline=True
        )

        embed.set_footer(text=f"Żądane przez {ctx.author.display_name}", icon_url=ctx.author.display_avatar.url)

        await ctx.send(embed=embed)

    @commands.hybrid_command(name="roles", aliases=["allroles"], description="Wyświetla wszystkie role na serwerze.")
    async def all_roles(self, ctx: commands.Context):
        """Wyświetla wszystkie role na serwerze."""
        guild = ctx.guild

        # Get all roles except @everyone, sorted by position (highest first)
        roles = [role for role in guild.roles if role.name != "@everyone"]
        roles.sort(key=lambda r: r.position, reverse=True)

        # Create pages of roles (20 per page)
        pages = []
        for i in range(0, len(roles), 20):
            page_roles = roles[i : i + 20]

            embed = discord.Embed(
                title=f"Role na serwerze {guild.name}", color=discord.Color.blue(), timestamp=datetime.now(timezone.utc)
            )

            role_text = ""
            for role in page_roles:
                member_count = len(role.members)
                role_text += f"{role.mention} - {member_count} członków\n"

            embed.description = role_text
            embed.set_footer(text=f"Strona {i // 20 + 1}/{(len(roles) - 1) // 20 + 1} | " f"Łącznie ról: {len(roles)}")

            pages.append(embed)

        if not pages:
            embed = discord.Embed(
                title="Role na serwerze", description="Brak ról do wyświetlenia.", color=discord.Color.red()
            )
            await ctx.send(embed=embed)
            return

        # If only one page, send it directly
        if len(pages) == 1:
            await ctx.send(embed=pages[0])
            return

        # Create paginated view
        view = RolePaginationView(pages, ctx.author)
        await ctx.send(embed=pages[0], view=view)


class RolePaginationView(discord.ui.View):
    """View for paginating through roles."""

    def __init__(self, pages, author):
        super().__init__(timeout=180)
        self.pages = pages
        self.author = author
        self.current_page = 0

        # Update button states
        self.update_buttons()

    def update_buttons(self):
        """Update button states based on current page."""
        self.previous_button.disabled = self.current_page == 0
        self.next_button.disabled = self.current_page == len(self.pages) - 1

    @discord.ui.button(label="◀", style=discord.ButtonStyle.primary)
    async def previous_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Go to previous page."""
        self.current_page -= 1
        self.update_buttons()
        await interaction.response.edit_message(embed=self.pages[self.current_page], view=self)

    @discord.ui.button(label="▶", style=discord.ButtonStyle.primary)
    async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Go to next page."""
        self.current_page += 1
        self.update_buttons()
        await interaction.response.edit_message(embed=self.pages[self.current_page], view=self)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """Only allow the command author to interact."""
        if interaction.user != self.author:
            await interaction.response.send_message(
                "Tylko osoba, która użyła komendy może przewijać strony.", ephemeral=True
            )
            return False
        return True

    async def on_timeout(self):
        """Disable buttons on timeout."""
        for item in self.children:
            item.disabled = True


async def setup(bot: commands.Bot):
    """Setup function to add cog to bot."""
    await bot.add_cog(ServerInfoCog(bot))
