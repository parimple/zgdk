"""Shop cog for the Zagadka bot."""
import logging
from datetime import datetime, timezone

import discord
from discord.ext import commands
from discord.ext.commands import Context

from cogs.ui.shop_embeds import create_shop_embed
from cogs.views.shop_views import PaymentsView, RoleShopView
from datasources.queries import HandledPaymentQueries, MemberQueries, RoleQueries
from utils.permissions import is_admin, is_zagadka_owner
from utils.premium import PaymentData
from utils.services.shop_service import ShopService

logger = logging.getLogger(__name__)


class ShopCog(commands.Cog):
    """Shop cog for managing the purchase and assignment of roles."""

    def __init__(self, bot):
        """Initialize the shop cog."""
        self.bot = bot
        self.shop_service = ShopService(bot)

    @commands.hybrid_command(name="shop", description="Wyświetla sklep z rolami.")
    @is_admin()
    async def shop(self, ctx: Context, member: discord.Member = None):
        """Display the role shop."""
        viewer = ctx.author
        target_member = member or viewer
        
        # Use the service to get shop data
        shop_data = await self.shop_service.get_shop_data(viewer.id, target_member.id)
        
        # Create view and embed
        view = RoleShopView(
            ctx,
            self.bot,
            self.bot.config["premium_roles"],
            shop_data["balance"],
            page=1,
            viewer=viewer,
            member=target_member,
        )
        
        embed = await create_shop_embed(
            ctx,
            shop_data["balance"],
            view.role_price_map,
            shop_data["premium_roles"],
            page=1,
            viewer=viewer,
            member=target_member,
        )
        
        await ctx.reply(embed=embed, view=view, mention_author=False)

    @commands.command(name="add", description="Dodaje środki G.")
    @is_zagadka_owner()
    async def add_balance(self, ctx: Context, user: discord.User, amount: int):
        """Add balance to a user's wallet."""
        # Use the service for this operation
        success, message = await self.shop_service.add_balance(ctx.author, user, amount)
        
        if success:
            await ctx.reply(f"Dodano {amount} do portfela {user.mention}.")
        else:
            await ctx.reply(f"Błąd: {message}")

    @commands.command(name="assign_payment")
    @is_admin()
    async def assign_payment(self, ctx: Context, payment_id: int, user: discord.Member):
        """Assign a payment ID to a user."""
        # Use the service for this operation
        success, message = await self.shop_service.assign_payment(payment_id, user)
        
        if success:
            await ctx.reply(f"Płatność została przypisana do {user.mention}.")
            
            # Check if DM was sent
            if "Could not send DM" in message:
                await ctx.send(
                    f"Nie mogłem wysłać DM do {user.mention}. "
                    f"Proszę przekazać mu te informacje ręcznie."
                )
        else:
            await ctx.reply(f"Błąd: {message}")

    @commands.hybrid_command(name="payments", description="Wyświetla wszystkie płatności")
    @is_admin()
    async def all_payments(self, ctx: Context):
        """Fetch and display the initial set of payments."""
        # Use the service to get payments
        success, message, payments = await self.shop_service.get_recent_payments(limit=10)
        
        if not success:
            await ctx.reply(f"Błąd: {message}")
            return
        
        embed = discord.Embed(title="Wszystkie płatności")
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
        
        view = PaymentsView(ctx, self.bot)
        await ctx.send(embed=embed, view=view)

    @commands.command(
        name="set_role_expiry", description="Ustawia czas wygaśnięcia roli", aliases=["sr"]
    )
    @is_admin()
    async def set_role_expiry(self, ctx: Context, member: discord.Member, hours: int):
        """Set the expiration time for a role.
        
        Args:
            ctx: The command context
            member: The member whose role to set the expiry for
            hours: The number of hours until the role expires
        """
        # Use the service for this operation
        success, message, new_expiry = await self.shop_service.set_role_expiry(member, hours)
        
        if success:
            await ctx.reply(
                f"Zaktualizowano czas wygaśnięcia roli dla {member.display_name}.\n"
                f"Nowy czas wygaśnięcia: {discord.utils.format_dt(new_expiry, 'R')}"
            )
        else:
            await ctx.reply(f"Błąd: {message}")

    @commands.command(name="shop_force_check_roles")
    @commands.has_permissions(administrator=True)
    async def force_check_roles(self, ctx: Context):
        """Force check and remove expired premium roles.
        
        WARNING: This command only removes expired roles without refunding money.
        For voluntary role selling by users, use the "Sell role" button in the profile.
        """
        # Use the service for this operation
        success, message, count = await self.shop_service.check_expired_premium_roles(ctx.guild)
        
        await ctx.reply(f"Sprawdzono i usunięto {count} ról, które nie powinny być aktywne.")
        
        if not success:
            await ctx.send(f"Uwaga: Wystąpiły błędy podczas sprawdzania: {message}")


async def setup(bot: commands.Bot):
    """Setup function for ShopCog."""
    await bot.add_cog(ShopCog(bot))