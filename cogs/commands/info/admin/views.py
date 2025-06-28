"""Discord UI views for admin info commands."""

from datetime import datetime, timezone

import discord


class InviteListView(discord.ui.View):
    """View for displaying and sorting invite lists."""

    def __init__(self, ctx, invites, sort_by="last_used", order="desc"):
        super().__init__(timeout=300)
        self.ctx = ctx
        self.invites = invites
        self.sort_by = sort_by
        self.order = order
        self.page = 0
        self.per_page = 10

    def create_embed(self):
        """Create embed with current sorting and pagination."""
        # Sort invites
        sorted_invites = self._sort_invites()

        # Paginate
        start_idx = self.page * self.per_page
        end_idx = start_idx + self.per_page
        page_invites = sorted_invites[start_idx:end_idx]

        embed = discord.Embed(title="Lista Zaproszeń", color=discord.Color.blue(), timestamp=datetime.now(timezone.utc))

        embed.set_footer(
            text=f"Strona {self.page + 1}/{(len(sorted_invites) - 1) // self.per_page + 1} | "
            f"Sortowanie: {self.sort_by} ({self.order})"
        )

        if not page_invites:
            embed.description = "Brak zaproszeń do wyświetlenia."
            return embed

        for inv in page_invites:
            creator_name = inv.creator.display_name if inv.creator else f"ID: {inv.creator_id or 'Unknown'}"
            created_date = inv.created_at.strftime("%Y-%m-%d %H:%M") if inv.created_at else "Unknown"
            last_used = inv.last_used_at.strftime("%Y-%m-%d %H:%M") if inv.last_used_at else "Nigdy"

            embed.add_field(
                name=f"Kod: {inv.code}",
                value=f"Użycia: {inv.uses}\n"
                f"Stworzony: {created_date}\n"
                f"Ostatnio: {last_used}\n"
                f"Twórca: {creator_name}",
                inline=True,
            )

        return embed

    def _sort_invites(self):
        """Sort invites based on current settings."""
        invites = self.invites.copy()

        if self.sort_by == "uses":
            invites.sort(key=lambda x: x.uses, reverse=(self.order == "desc"))
        elif self.sort_by == "created_at":
            invites.sort(
                key=lambda x: x.created_at if x.created_at else datetime.min.replace(tzinfo=timezone.utc),
                reverse=(self.order == "desc"),
            )
        elif self.sort_by == "last_used":
            invites.sort(
                key=lambda x: x.last_used_at if x.last_used_at else datetime.min.replace(tzinfo=timezone.utc),
                reverse=(self.order == "desc"),
            )

        return invites

    @discord.ui.button(label="◀", style=discord.ButtonStyle.primary, row=0)
    async def previous_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Go to previous page."""
        if self.page > 0:
            self.page -= 1
            embed = self.create_embed()
            await interaction.response.edit_message(embed=embed, view=self)
        else:
            await interaction.response.defer()

    @discord.ui.button(label="▶", style=discord.ButtonStyle.primary, row=0)
    async def next_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Go to next page."""
        max_page = (len(self.invites) - 1) // self.per_page
        if self.page < max_page:
            self.page += 1
            embed = self.create_embed()
            await interaction.response.edit_message(embed=embed, view=self)
        else:
            await interaction.response.defer()

    @discord.ui.select(
        placeholder="Sortuj według...",
        options=[
            discord.SelectOption(label="Użycia", value="uses"),
            discord.SelectOption(label="Data utworzenia", value="created_at"),
            discord.SelectOption(label="Ostatnie użycie", value="last_used"),
        ],
        row=1,
    )
    async def sort_select(self, interaction: discord.Interaction, select: discord.ui.Select):
        """Change sorting field."""
        self.sort_by = select.values[0]
        self.page = 0  # Reset to first page
        embed = self.create_embed()
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="Odwróć kolejność", style=discord.ButtonStyle.secondary, row=2)
    async def toggle_order(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Toggle sort order."""
        self.order = "asc" if self.order == "desc" else "desc"
        self.page = 0  # Reset to first page
        embed = self.create_embed()
        await interaction.response.edit_message(embed=embed, view=self)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """Check if user can interact with this view."""
        return interaction.user == self.ctx.author
