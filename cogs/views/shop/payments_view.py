"""Payments view for navigating through payment history."""
import discord
from discord.ext.commands import Context

from datasources.queries import HandledPaymentQueries
from utils.message_sender import MessageSender


class PaymentsView(discord.ui.View):
    """View for navigating through payment history."""

    def __init__(self, ctx: Context, bot):
        super().__init__()
        self.ctx = ctx
        self.bot = bot
        self.current_offset = 0

    async def display_payments(self, interaction: discord.Interaction):
        """Display the payments."""
        self.current_offset = max(0, self.current_offset)
        async with self.bot.get_db() as session:
            payments = await HandledPaymentQueries.get_last_payments(
                session, offset=self.current_offset, limit=10
            )

        embed = MessageSender._create_embed(
            title="Wszystkie płatności", ctx=self.ctx.author
        )
        for payment in payments:
            name = f"ID płatności: {payment.id}"
            value = (
                f"ID członka: {payment.member_id}\n"
                f"Nazwa: {payment.name}\n"
                f"Kwota: {payment.amount}\n"
                f"Zapłacono: {discord.utils.format_dt(payment.paid_at, 'D')}\n"
                f"Typ płatności: {payment.payment_type}"
            )
            embed.add_field(name=name, value=value, inline=False)
        await interaction.response.edit_message(embed=embed)

    @discord.ui.button(label="Nowsze", style=discord.ButtonStyle.primary)
    async def newer_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        """Go to the newer payments."""
        self.current_offset -= 10
        await self.display_payments(interaction)

    @discord.ui.button(label="Starsze", style=discord.ButtonStyle.primary)
    async def older_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        """Go to the older payments."""
        self.current_offset += 10
        await self.display_payments(interaction)