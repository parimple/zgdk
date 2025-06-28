"""Shop cog for the Zagadka bot."""
import logging
from datetime import datetime, timedelta, timezone

import discord
from discord.ext import commands
from discord.ext.commands import Context

from cogs.ui.shop_embeds import create_shop_embed
from cogs.views.shop_views import PaymentsView, RoleShopView
from core.interfaces.member_interfaces import IMemberService
from core.interfaces.premium_interfaces import IPremiumService
from datasources.queries import HandledPaymentQueries
from utils.permissions import is_admin, is_zagadka_owner
from utils.premium import PaymentData

logger = logging.getLogger(__name__)


class ShopCog(commands.Cog):
    """Shop cog for managing the purchase and assignment of roles."""

    def __init__(self, bot):
        self.bot = bot

    @commands.hybrid_command(name="shop", aliases=["sklep"], description="Wyświetla sklep z rolami.")
    @is_zagadka_owner()
    async def shop(self, ctx: Context, member: discord.Member = None):
        viewer = ctx.author
        target_member = member or viewer

        async with self.bot.get_db() as session:
            # Use new service architecture
            member_service = await self.bot.get_service(IMemberService, session)
            premium_service = await self.bot.get_service(IPremiumService, session)

            db_viewer = await member_service.get_or_create_member(viewer)
            balance = db_viewer.wallet_balance
            premium_roles = await premium_service.get_member_premium_roles(target_member.id)

        view = RoleShopView(
            ctx,
            self.bot,
            self.bot.config["premium_roles"],
            balance,
            page=1,
            viewer=viewer,
            member=target_member,
        )
        embed = await create_shop_embed(
            ctx,
            balance,
            view.role_price_map,
            premium_roles,
            page=1,
            viewer=viewer,
            member=target_member,
        )
        await ctx.reply(embed=embed, view=view, mention_author=False)

    @commands.hybrid_command(name="addbalance", description="Dodaje środki G.")
    @is_zagadka_owner()
    async def add_balance(self, ctx: Context, user: discord.User, amount: int):
        """Add balance to a user's wallet."""
        payment_data = PaymentData(
            name=ctx.author.display_name,
            amount=amount,
            paid_at=datetime.now(timezone.utc),
            payment_type="command",
        )

        async with self.bot.get_db() as session:
            # Use new service architecture
            member_service = await self.bot.get_service(IMemberService, session)

            await HandledPaymentQueries.add_payment(
                session,
                user.id,
                payment_data.name,
                payment_data.amount,
                payment_data.paid_at,
                payment_data.payment_type,
            )

            # Get or create member and update wallet balance
            db_member = await member_service.get_or_create_member(user)
            new_balance = db_member.wallet_balance + payment_data.amount
            await member_service.update_member_info(db_member, wallet_balance=new_balance)
            await session.commit()

        await ctx.reply(f"Dodano {amount} do portfela {user.mention}.")

    @commands.hybrid_command(name="assign_payment")
    @is_admin()
    async def assign_payment(self, ctx: Context, payment_id: int, user: discord.Member):
        """Assign a payment ID to a user."""
        async with self.bot.get_db() as session:
            # Use new service architecture
            member_service = await self.bot.get_service(IMemberService, session)

            payment = await HandledPaymentQueries.get_payment_by_id(session, payment_id)

            if payment:
                payment.member_id = user.id

                # Get or create member and update wallet balance
                db_member = await member_service.get_or_create_member(user)
                new_balance = db_member.wallet_balance + payment.amount
                await member_service.update_member_info(db_member, wallet_balance=new_balance)

                await session.commit()

                msg1 = "Proszę pamiętać o podawaniu swojego ID " "podczas dokonywania wpłat w przyszłości. Twoje ID to:"
                msg2 = f"Nie mogłem wysłać DM do {user.mention}. " "Proszę przekazać mu te informacje ręcznie."

                try:
                    await user.send(msg1)
                    await user.send(f"```{user.id}```")
                except discord.Forbidden:
                    await ctx.send(msg2)
            else:
                await ctx.send(f"Nie znaleziono płatności o ID: {payment_id}")

    @commands.hybrid_command(name="payments", description="Wyświetla wszystkie płatności")
    @is_admin()
    async def all_payments(self, ctx: Context):
        """Fetch and display the initial set of payments."""
        async with self.bot.get_db() as session:
            payments = await HandledPaymentQueries.get_last_payments(session, limit=10)

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
        name="set_role_expiry",
        description="Ustawia czas wygaśnięcia roli",
        aliases=["sr"],
    )
    @is_admin()
    async def set_role_expiry(self, ctx: Context, member: discord.Member, hours: int):
        """
        Ustawia czas wygaśnięcia roli dla użytkownika.

        Args:
            ctx: Kontekst komendy
            member: Użytkownik, którego rola ma być zmodyfikowana
            hours: Liczba godzin do wygaśnięcia roli
        """
        async with self.bot.get_db() as session:
            # Use new service architecture
            premium_service = await self.bot.get_service(IPremiumService, session)

            premium_roles = await premium_service.get_member_premium_roles(member.id)

            if not premium_roles:
                await ctx.reply("Ten użytkownik nie ma żadnej roli premium.")
                return

            # Get first premium role
            role_data = premium_roles[0]
            role_name = role_data.get("role_name", "Unknown")
            new_expiry = datetime.now(timezone.utc) + timedelta(hours=hours)

            # Extend the role (this will update the expiry time)
            result = await premium_service.extend_premium_role(
                member, role_name, 0, 0  # 0 days extension, just updating expiry
            )

            if result.success:
                await session.commit()
                await ctx.reply(
                    f"Zaktualizowano czas wygaśnięcia roli {role_name} dla {member.display_name}.\n"
                    f"Nowy czas wygaśnięcia: {discord.utils.format_dt(new_expiry, 'R')}"
                )
            else:
                await ctx.reply(f"Błąd aktualizacji roli: {result.message}")

    @commands.command(name="shop_force_check_roles")
    @commands.has_permissions(administrator=True)
    async def force_check_roles(self, ctx: Context):
        """
        Wymusza sprawdzenie i ewentualne usunięcie ról premium.

        UWAGA: Ta komenda tylko usuwa wygasłe role bez zwrotu pieniędzy.
        Do dobrowolnej sprzedaży ról przez użytkowników służy przycisk "Sprzedaj rangę" w profilu.
        """
        now = datetime.now(timezone.utc)
        count = 0

        # Pobierz konfigurację ról premium
        premium_role_names = {role["name"]: role for role in self.bot.config["premium_roles"]}

        # Znajdź role premium na serwerze
        premium_roles = [role for role in ctx.guild.roles if role.name in premium_role_names]

        # Dla każdej roli premium
        for role in premium_roles:
            # Sprawdź członków z tą rolą
            for member in role.members:
                async with self.bot.get_db() as session:
                    # Use new service architecture
                    premium_service = await self.bot.get_service(IPremiumService, session)

                    # Set guild context for premium service
                    premium_service.set_guild(ctx.guild)

                    # Check if member has valid premium role
                    has_valid_premium = await premium_service.has_premium_role(member)
                    premium_roles = await premium_service.get_member_premium_roles(member.id)

                    # Check if this specific role is expired
                    role_expired = True
                    for role_data in premium_roles:
                        if role_data.get("role_name") == role.name:
                            expiry = role_data.get("expiration_date")
                            if expiry and expiry > now:
                                role_expired = False
                                break

                    if not has_valid_premium or role_expired:
                        try:
                            await member.remove_roles(role)
                            count += 1
                            logger.info(f"Removed role {role.name} from {member.display_name} - no DB entry or expired")
                        except Exception as e:
                            logger.error(f"Error removing role {role.name} from {member.display_name}: {str(e)}")

        await ctx.reply(f"Sprawdzono i usunięto {count} ról, które nie powinny być aktywne.")


async def setup(bot: commands.Bot):
    """Setup function for ShopCog."""
    await bot.add_cog(ShopCog(bot))
