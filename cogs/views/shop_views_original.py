"""Views for the shop cog."""
import logging
from datetime import datetime, timedelta, timezone

import discord
from discord.ext.commands import Context

from cogs.ui.shop_embeds import create_role_description_embed, create_shop_embed
from core.interfaces.premium_interfaces import IPremiumService
from datasources.queries import HandledPaymentQueries, MemberQueries, RoleQueries
from utils.message_sender import MessageSender
from utils.premium_logic import PremiumRoleManager
from utils.refund import calculate_refund

# Configuration constants
MONTHLY_DURATION = 30  # Base duration for monthly subscription
YEARLY_DURATION = 365  # Base duration for yearly subscription
YEARLY_MONTHS = 10  # Number of months to pay for yearly subscription (2 months free)

logger = logging.getLogger(__name__)


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
            payments = await HandledPaymentQueries.get_last_payments(session, offset=self.current_offset, limit=10)

        embed = MessageSender._create_embed(title="Wszystkie płatności", ctx=self.ctx.author)
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
    async def newer_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Go to the newer payments."""
        self.current_offset -= 10
        await self.display_payments(interaction)

    @discord.ui.button(label="Starsze", style=discord.ButtonStyle.primary)
    async def older_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Go to the older payments."""
        self.current_offset += 10
        await self.display_payments(interaction)


class RoleShopView(discord.ui.View):
    """View for displaying and handling the purchase of roles in the shop."""

    def __init__(
        self,
        ctx: Context,
        bot,
        premium_roles=None,
        balance=0,
        page=1,
        viewer: discord.Member = None,
        member: discord.Member = None,
    ):
        super().__init__()
        self.ctx = ctx
        self.guild = bot.guild
        self.bot = bot
        self.balance = balance
        self.page = page
        self.viewer = viewer
        self.member = member
        self.premium_roles = premium_roles
        self.premium_manager = PremiumRoleManager(bot, self.guild)
        # Initialize MessageSender with bot instance for consistency
        self.message_sender = MessageSender(bot)

        # Tworzenie podstawowej mapy cen
        self.base_price_map = {role["name"]: role["price"] for role in premium_roles}
        # Tworzenie mapy cen z uwzględnieniem strony (miesięczne/roczne)
        self.role_price_map = self.get_price_map()

        self.role_ids = {
            role["name"]: discord.utils.get(self.guild.roles, name=role["name"]).id for role in premium_roles
        }

        # Przyciski dla każdej roli
        for role_name, price in self.role_price_map.items():
            price = price * 10 if self.page == 2 else price
            button = discord.ui.Button(
                label=role_name,
                style=discord.ButtonStyle.primary,
                disabled=self.balance < price,
            )
            button.callback = self.create_button_callback(role_name)
            self.add_item(button)

        # Przyciski nawigacji stron
        if page == 1:
            next_button = discord.ui.Button(label="Ceny roczne ➡️", style=discord.ButtonStyle.secondary)
            next_button.callback = self.next_page
            self.add_item(next_button)
        else:
            previous_button = discord.ui.Button(label="⬅️ Ceny miesięczne", style=discord.ButtonStyle.secondary)
            previous_button.callback = self.previous_page
            self.add_item(previous_button)

        # Przycisk opisu ról
        description_button = discord.ui.Button(label="Opis ról", style=discord.ButtonStyle.primary)
        description_button.callback = self.show_role_description
        self.add_item(description_button)

        # Przycisk "Moje ID"
        my_id_button = discord.ui.Button(label="Moje ID", style=discord.ButtonStyle.secondary, emoji="🆔")
        my_id_button.callback = self.show_my_id
        self.add_item(my_id_button)

        donate_url = self.bot.config.get("donate_url")
        if donate_url:
            self.add_item(
                discord.ui.Button(
                    label="Doładuj konto",
                    style=discord.ButtonStyle.link,
                    url=donate_url,
                )
            )

    async def create_view_for_user(self, interaction: discord.Interaction) -> tuple[discord.Embed, "RoleShopView"]:
        """Create a new view instance for a different user."""
        async with self.bot.get_db() as session:
            db_viewer = await MemberQueries.get_or_add_member(session, interaction.user.id)
            balance = db_viewer.wallet_balance
            premium_service = await self.bot.get_service(IPremiumService, session)
            premium_roles = await premium_service.get_member_premium_roles(interaction.user.id)
            await session.commit()

        new_view = RoleShopView(
            self.ctx,
            self.bot,
            self.premium_roles,
            balance,
            self.page,
            viewer=interaction.user,
            member=interaction.user,
        )
        embed = await create_shop_embed(
            self.ctx,
            balance,
            new_view.role_price_map,
            premium_roles,
            self.page,
            viewer=interaction.user,
            member=interaction.user,
        )
        return embed, new_view

    def get_price_map(self):
        """Get price map based on current page."""
        price_map = {}
        for role_name, base_price in self.base_price_map.items():
            if self.page == 2:  # Ceny roczne
                price_map[role_name] = base_price * YEARLY_MONTHS  # Płacisz za 10 miesięcy
            else:  # Ceny miesięczne
                price_map[role_name] = base_price
        return price_map

    def _add_premium_text_to_description(self, description: str) -> str:
        """Helper method to add premium text to description consistently."""
        _, premium_text = self.message_sender._get_premium_text(self.ctx)
        if premium_text:
            return f"{description}\n{premium_text}"
        return description

    def create_button_callback(self, role_name):
        """Create a button callback for the specified role name."""

        async def button_callback(interaction: discord.Interaction):
            if interaction.user.id != self.viewer.id:
                embed, view = await self.create_view_for_user(interaction)
                await interaction.response.send_message(
                    "Oto twój własny widok sklepu:",
                    embed=embed,
                    view=view,
                    ephemeral=True,
                )
                return

            duration_days = YEARLY_DURATION if self.page == 2 else MONTHLY_DURATION
            price = self.role_price_map[role_name]
            await self.handle_buy_role(interaction, role_name, self.member, duration_days, price)

        return button_callback

    async def handle_buy_role(
        self,
        interaction: discord.Interaction,
        role_name: str,
        member: discord.Member,
        duration_days: int,
        price: int,
    ) -> None:
        """Handle buying a role."""
        # Defer the response immediately to prevent interaction timeout
        await interaction.response.defer(thinking=True)

        async with self.bot.get_db() as session:
            try:
                logger.info(
                    f"[SHOP] Starting role purchase for {member.display_name}:"
                    f"\n - Role: {role_name}"
                    f"\n - Duration: {duration_days} days"
                    f"\n - Price: {price}G"
                )

                # Check if member has enough balance
                db_member = await MemberQueries.get_or_add_member(session, self.viewer.id)
                if db_member.wallet_balance < price:
                    # Get premium text
                    _, premium_text = self.message_sender._get_premium_text(self.ctx)
                    error_msg = (
                        f"Nie masz wystarczająco środków. Potrzebujesz {price}G, a masz {db_member.wallet_balance}G."
                    )
                    if premium_text:
                        error_msg = f"{error_msg}\n{premium_text}"

                    await interaction.followup.send(error_msg, ephemeral=True)
                    return

                # Get the role object
                role = discord.utils.get(self.bot.guild.roles, name=role_name)
                if not role:
                    await interaction.followup.send(f"Nie znaleziono roli {role_name}.", ephemeral=True)
                    return

                # Check for existing premium roles
                premium_service = await self.bot.get_service(IPremiumService, session)
                current_premium_roles = await premium_service.get_member_premium_roles(member.id)

                if current_premium_roles:
                    logger.info(
                        f"[SHOP] Found existing premium roles for {member.display_name}:"
                        f"\n - Current roles: {[r.get('role_name', 'Unknown') for r in current_premium_roles]}"
                    )

                    current_role_data = current_premium_roles[0]
                    # Create compatibility objects for old code
                    current_member_role = current_role_data.get("member_role")
                    current_role = current_role_data.get("role")

                    current_role_config = next(
                        (r for r in self.bot.config["premium_roles"] if r["name"] == current_role.name),
                        None,
                    )
                    new_role_config = next(
                        (r for r in self.bot.config["premium_roles"] if r["name"] == role_name),
                        None,
                    )

                    if current_role_config and new_role_config:
                        # Check if it's the same role first
                        if current_role.name == role_name:
                            # Same role - extend it directly
                            extend_days = MONTHLY_DURATION if duration_days == MONTHLY_DURATION else YEARLY_DURATION
                            old_expiry = current_member_role.expiration_date

                            logger.info(
                                f"[SHOP] Extending same role {role_name} for {member.display_name}:"
                                f"\n - Current expiry: {old_expiry}"
                                f"\n - Days to add: {extend_days}"
                                f"\n - New expiry: {old_expiry + timedelta(days=extend_days)}"
                            )

                            # Update expiration date
                            current_member_role.expiration_date = old_expiry + timedelta(days=extend_days)

                            # Remove mute roles and update balance
                            if self.premium_manager:
                                await self.premium_manager.remove_mute_roles(member)
                            await MemberQueries.add_to_wallet_balance(session, self.viewer.id, -price)

                            # Save changes
                            await session.flush()
                            await session.refresh(current_member_role)

                            # Send confirmation message using MessageSender
                            success_description = f"✅ Gratulacje! Przedłużyłeś rangę **{role_name}** o {extend_days} dni. Wszystkie blokady zostały usunięte – miłego korzystania!\nBóg zapłać!"
                            # Add premium text directly to description like MessageSender does
                            success_description = self._add_premium_text_to_description(success_description)

                            embed = MessageSender._create_embed(description=success_description, ctx=member)

                            await interaction.followup.send(embed=embed, ephemeral=False)

                            # Update the original shop embed with new expiration date
                            premium_service = await self.bot.get_service(IPremiumService, session)
                            premium_roles = await premium_service.get_member_premium_roles(member.id)
                            updated_embed = await create_shop_embed(
                                self.ctx,
                                self.balance - price,  # Update balance
                                self.role_price_map,
                                premium_roles,
                                self.page,
                                self.viewer,
                                self.member,
                            )
                            await interaction.message.edit(embed=updated_embed)
                            return

                        # Calculate refund for current role
                        refund_amount = calculate_refund(
                            current_member_role.expiration_date,
                            current_role_config["price"],
                        )

                        if current_role_config["price"] > new_role_config["price"]:
                            # Downgrade case
                            days_to_add = int(price / current_role_config["price"] * MONTHLY_DURATION)

                            logger.info(
                                f"[SHOP] Calculating extension for {member.display_name}:"
                                f"\n - Current role: {current_role.name}"
                                f"\n - Target role: {role_name}"
                                f"\n - Price paid: {price}G"
                                f"\n - Current role price: {current_role_config['price']}G"
                                f"\n - Price ratio: {price}/{current_role_config['price']}"
                                f"\n - Base days: {MONTHLY_DURATION}"
                                f"\n - Days to add: {days_to_add}"
                            )

                            description = (
                                "Dostępne opcje:\n"
                                f"1️⃣ **Przedłuż swoją rangę {current_role.name}** o {days_to_add} dni (usuwa wszystkie muty)\n"
                                f"2️⃣ **Kup nową rangę {role_name}** i otrzymaj **{refund_amount}G** zwrotu za obecną rolę\n"
                                "❌ **Anuluj operację**"
                            )
                        else:
                            # Upgrade case
                            days_to_add = 0  # No extension for upgrades
                            description = (
                                "Dostępne opcje:\n"
                                f"1️⃣ **Kup nową rangę {role_name}** i otrzymaj **{refund_amount}G** zwrotu za obecną rolę **{current_role.name}**\n"
                                "❌ **Anuluj operację**"
                            )

                        # Create embed with MessageSender for consistency
                        embed = MessageSender._create_embed(
                            description=description,
                            ctx=member,
                        )

                        # Show choice view
                        view = LowerRoleChoiceView(
                            self.bot,
                            member,
                            current_role.name,
                            role_name,
                            price,
                            days_to_add,
                            is_upgrade=current_role_config["price"] < new_role_config["price"],
                        )

                        # Send initial message with options as ephemeral
                        await interaction.followup.send(embed=embed, view=view, ephemeral=True)

                        try:
                            await view.wait()
                        except RuntimeError:
                            # Handle potential async generator issues
                            return

                        if view.value == "cancel" or view.value == "timeout":
                            await interaction.followup.send(
                                "Operacja została anulowana - nie dokonano wyboru w wyznaczonym czasie."
                                if view.value == "timeout"
                                else "Anulowałeś operację.",
                                ephemeral=True,
                            )
                            return

                        elif view.value == "extend":
                            # Extend the current role and remove mutes
                            expiration_date = current_member_role.expiration_date + timedelta(days=view.days_to_add)
                            logger.info(
                                f"[SHOP] Extending role {current_role.name} for {member.display_name}:"
                                f"\n - Current expiry: {current_member_role.expiration_date}"
                                f"\n - Days to add: {view.days_to_add}"
                                f"\n - New expiry: {expiration_date}"
                            )

                            current_member_role.expiration_date = expiration_date
                            await MemberQueries.add_to_wallet_balance(session, self.viewer.id, -price)

                            # Remove mute roles
                            if self.premium_manager:
                                await self.premium_manager.remove_mute_roles(member)

                            await session.commit()
                            await session.refresh(current_member_role)

                            logger.info(
                                f"[SHOP] After commit - role {current_role.name} expiry confirmed as: {current_member_role.expiration_date}"
                            )

                            # Send public confirmation
                            success_description = f"✅ Gratulacje! Przedłużyłeś rangę **{current_role.name}** o {view.days_to_add} dni. Wszystkie blokady zostały usunięte – miłego korzystania!\nBóg zapłać!"
                            # Add premium text directly to description like MessageSender does
                            success_description = self._add_premium_text_to_description(success_description)

                            embed = MessageSender._create_embed(description=success_description, ctx=member)

                            await interaction.followup.send(embed=embed, ephemeral=False)

                        elif view.value in ["buy_lower", "buy_higher"]:
                            # Calculate refund for the old role
                            refund = calculate_refund(
                                current_member_role.expiration_date,
                                current_role_config["price"],
                            )

                            # Remove old role
                            await member.remove_roles(current_role)
                            await RoleQueries.delete_member_role(session, member.id, current_role.id)

                            # Add refund to wallet
                            if refund > 0:
                                await MemberQueries.add_to_wallet_balance(session, member.id, refund)

                            # Remove mute roles before adding new role
                            if self.premium_manager:
                                await self.premium_manager.remove_mute_roles(member)

                            # Add new role - use MONTHLY_DURATION without bonus days for role changes
                            duration = timedelta(days=MONTHLY_DURATION)
                            await RoleQueries.add_role_to_member(session, member.id, role.id, duration)
                            await member.add_roles(role)

                            # Deduct price from wallet
                            await MemberQueries.add_to_wallet_balance(session, self.viewer.id, -price)
                            await session.commit()

                            # Send public confirmation
                            if view.value == "buy_lower":
                                success_description = f"🎉 Gratulacje! Zamieniłeś swoją rangę **{current_role.name}** na **{role_name}** i otrzymałeś **{refund}G** zwrotu. Dzięki, że wspierasz naszą społeczność!"
                            else:
                                success_description = f"🚀 Gratulacje! Ulepszyłeś rangę **{current_role.name}** do **{role_name}** i otrzymałeś **{refund}G** zwrotu. Świetny wybór!"

                            embed = MessageSender._create_embed(
                                description=success_description,
                                ctx=member,
                            )
                            # Add premium text directly to description like MessageSender does
                            embed.description = self._add_premium_text_to_description(embed.description)
                            await interaction.followup.send(embed=embed, ephemeral=False)

                        # Update the original shop embed with new expiration date
                        premium_service = await self.bot.get_service(IPremiumService, session)
                        premium_roles = await premium_service.get_member_premium_roles(member.id)
                        updated_embed = await create_shop_embed(
                            self.ctx,
                            self.balance - price,  # Update balance
                            self.role_price_map,
                            premium_roles,
                            self.page,
                            self.viewer,
                            self.member,
                        )
                        await interaction.message.edit(embed=updated_embed)
                        return

                    else:
                        # Same role or upgrade - handle directly
                        if current_role.name == role_name:
                            # Same role - extend it
                            extend_days = MONTHLY_DURATION if duration_days == MONTHLY_DURATION else YEARLY_DURATION
                            old_expiry = current_member_role.expiration_date

                            # Update expiration date
                            current_member_role.expiration_date = old_expiry + timedelta(days=extend_days)

                            # Remove mute roles and update balance
                            if self.premium_manager:
                                await self.premium_manager.remove_mute_roles(member)
                            await MemberQueries.add_to_wallet_balance(session, self.viewer.id, -price)

                            # Save changes
                            await session.flush()
                            await session.refresh(current_member_role)

                            logger.info(
                                f"[SHOP] Extended same role {role_name} for {member.display_name}:"
                                f"\n - Old expiry: {old_expiry}"
                                f"\n - Days added: {extend_days}"
                                f"\n - New expiry: {current_member_role.expiration_date}"
                            )

                            # Send confirmation message using MessageSender
                            success_description = f"✅ Gratulacje! Przedłużyłeś rangę **{current_role.name}** o {extend_days} dni. Wszystkie blokady zostały usunięte – miłego korzystania!\nBóg zapłać!"
                            # Add premium text directly to description like MessageSender does
                            success_description = self._add_premium_text_to_description(success_description)

                            embed = MessageSender._create_embed(description=success_description, ctx=member)

                            await interaction.followup.send(embed=embed, ephemeral=False)

                            # Update the original shop embed with new expiration date
                            premium_service = await self.bot.get_service(IPremiumService, session)
                            premium_roles = await premium_service.get_member_premium_roles(member.id)
                            updated_embed = await create_shop_embed(
                                self.ctx,
                                self.balance - price,  # Update balance
                                self.role_price_map,
                                premium_roles,
                                self.page,
                                self.viewer,
                                self.member,
                            )
                            await interaction.message.edit(embed=updated_embed)
                            return
                        else:
                            # Remove lower role when upgrading
                            await RoleQueries.delete_member_role(session, member.id, current_role.id)
                            await member.remove_roles(current_role)

                # Normal purchase flow
                if role in member.roles:
                    # Get current role expiration
                    member_role = await RoleQueries.get_member_role(session, member.id, role.id)
                    now = datetime.now(timezone.utc)

                    logger.info(
                        f"[SHOP] Checking role status for {member.display_name}:"
                        f"\n - Role: {role_name}"
                        "\n - Has role in Discord: True"
                        f"\n - Has role in DB: {member_role is not None}"
                        f"\n - Current time: {now}"
                        f"\n - Expiration date: {member_role.expiration_date if member_role else 'None'}"
                    )

                    if member_role:
                        # Calculate extension days
                        extend_days = MONTHLY_DURATION if duration_days == MONTHLY_DURATION else YEARLY_DURATION
                        old_expiry = member_role.expiration_date

                        # If role is expired or about to expire, start from now
                        if member_role.expiration_date <= now + timedelta(days=7):
                            logger.info(
                                f"[SHOP] Role {role_name} is expired or about to expire, starting new period from now:"
                                f"\n - Old expiry: {old_expiry}"
                                f"\n - New base: {now}"
                                f"\n - Days to add: {extend_days}"
                            )
                            member_role.expiration_date = now + timedelta(days=extend_days)
                        else:
                            logger.info(
                                f"[SHOP] Extending active role {role_name}:"
                                f"\n - Current expiry: {old_expiry}"
                                f"\n - Days to add: {extend_days}"
                            )
                            member_role.expiration_date = old_expiry + timedelta(days=extend_days)

                        # Verify the update
                        await session.flush()
                        await session.refresh(member_role)
                        logger.info(
                            f"[SHOP] After extension - role {role_name}:"
                            f"\n - Old expiry: {old_expiry}"
                            f"\n - New expiry: {member_role.expiration_date}"
                            f"\n - Difference in days: {(member_role.expiration_date - old_expiry).days}"
                        )

                        # Remove mute roles
                        if self.premium_manager:
                            await self.premium_manager.remove_mute_roles(member)

                        # Update wallet balance
                        await MemberQueries.add_to_wallet_balance(session, self.viewer.id, -price)
                        await session.commit()

                        # Send confirmation message using MessageSender
                        success_description = f"✅ Gratulacje! Przedłużyłeś rangę **{role_name}** o {extend_days} dni. Wszystkie blokady zostały usunięte – miłego korzystania!\nBóg zapłać!"
                        # Add premium text directly to description like MessageSender does
                        success_description = self._add_premium_text_to_description(success_description)

                        embed = MessageSender._create_embed(description=success_description, ctx=member)

                        await interaction.followup.send(embed=embed, ephemeral=False)

                        # Update the original shop embed with new expiration date
                        premium_service = await self.bot.get_service(IPremiumService, session)
                        premium_roles = await premium_service.get_member_premium_roles(member.id)
                        updated_embed = await create_shop_embed(
                            self.ctx,
                            self.balance - price,  # Update balance
                            self.role_price_map,
                            premium_roles,
                            self.page,
                            self.viewer,
                            self.member,
                        )
                        await interaction.message.edit(embed=updated_embed)
                        return
                    else:
                        logger.info(
                            f"[SHOP] Role {role_name} exists in Discord but not in database for {member.display_name} - treating as new purchase"
                        )

                # New purchase flow (when user doesn't have the role in database)
                logger.info(
                    f"[SHOP] Starting new purchase flow for {member.display_name}:"
                    f"\n - Role: {role_name}"
                    f"\n - Duration: {duration_days} days"
                )

                duration = timedelta(days=duration_days)
                await RoleQueries.add_role_to_member(session, member.id, role.id, duration)

                if role not in member.roles:
                    await member.add_roles(role)

                # Remove mute roles before updating balance
                if self.premium_manager:
                    await self.premium_manager.remove_mute_roles(member)

                await MemberQueries.add_to_wallet_balance(session, self.viewer.id, -price)
                await session.commit()

                # Verify the role assignment
                member_role = await RoleQueries.get_member_role(session, member.id, role.id)
                if member_role:
                    logger.info(
                        f"[SHOP] Purchase verification for {member.display_name}:"
                        f"\n - Role: {role_name}"
                        f"\n - Expiry: {member_role.expiration_date}"
                    )
                else:
                    logger.error(
                        f"[SHOP] Failed to verify role assignment for {member.display_name}:"
                        f"\n - Role: {role_name}"
                        f"\n - Role exists in Discord: {role in member.roles}"
                    )

                # Send confirmation message using MessageSender
                success_description = f"✅ Gratulacje! Zakupiłeś rangę **{role_name}** na 30 dni. Wszystkie blokady zostały usunięte – miłego korzystania!\nBóg zapłać!"
                # Add premium text directly to description like MessageSender does
                success_description = self._add_premium_text_to_description(success_description)

                embed = MessageSender._create_embed(description=success_description, ctx=member)

                await interaction.followup.send(embed=embed, ephemeral=False)

            except Exception as e:
                logger.error("Error while buying role: %s", e, exc_info=True)
                await session.rollback()
                await interaction.followup.send(
                    "Wystąpił błąd podczas zakupu roli. Proszę spróbować ponownie później.",
                    ephemeral=True,
                )

    async def next_page(self, interaction: discord.Interaction):
        """Go to the next page in the role shop."""
        if interaction.user.id != self.viewer.id:
            embed, view = await self.create_view_for_user(interaction)
            # Add premium text to the message
            base_text = self._add_premium_text_to_description("Oto twój własny widok sklepu:")
            await interaction.response.send_message(base_text, embed=embed, view=view, ephemeral=True)
            return

        self.page = 2
        self.role_price_map = self.get_price_map()

        async with self.bot.get_db() as session:
            db_member = await MemberQueries.get_or_add_member(session, self.viewer.id)
            balance = db_member.wallet_balance
            premium_service = await self.bot.get_service(IPremiumService, session)
            premium_roles = await premium_service.get_member_premium_roles(self.member.id)
            await session.commit()

        view = RoleShopView(
            self.ctx,
            self.bot,
            self.premium_roles,
            balance,
            self.page,
            self.viewer,
            self.member,
        )
        embed = await create_shop_embed(
            self.ctx,
            balance,
            view.role_price_map,
            premium_roles,
            self.page,
            self.viewer,
            self.member,
        )
        await interaction.response.edit_message(embed=embed, view=view)

    async def previous_page(self, interaction: discord.Interaction):
        """Go to the previous page in the role shop."""
        if interaction.user.id != self.viewer.id:
            embed, view = await self.create_view_for_user(interaction)
            # Add premium text to the message
            base_text = self._add_premium_text_to_description("Oto twój własny widok sklepu:")
            await interaction.response.send_message(base_text, embed=embed, view=view, ephemeral=True)
            return

        self.page = 1
        self.role_price_map = self.get_price_map()

        async with self.bot.get_db() as session:
            db_member = await MemberQueries.get_or_add_member(session, self.viewer.id)
            balance = db_member.wallet_balance
            premium_service = await self.bot.get_service(IPremiumService, session)
            premium_roles = await premium_service.get_member_premium_roles(self.member.id)
            await session.commit()

        view = RoleShopView(
            self.ctx,
            self.bot,
            self.premium_roles,
            balance,
            self.page,
            self.viewer,
            self.member,
        )
        embed = await create_shop_embed(
            self.ctx,
            balance,
            view.role_price_map,
            premium_roles,
            self.page,
            self.viewer,
            self.member,
        )
        await interaction.response.edit_message(embed=embed, view=view)

    async def show_role_description(self, interaction: discord.Interaction):
        """Show the description of the role."""
        if interaction.user.id != self.viewer.id:
            embed, view = await self.create_view_for_user(interaction)
            # Add premium text to the message
            base_text = self._add_premium_text_to_description("Oto twój własny widok sklepu:")
            await interaction.response.send_message(base_text, embed=embed, view=view, ephemeral=True)
            return

        async with self.bot.get_db() as session:
            db_member = await MemberQueries.get_or_add_member(session, self.viewer.id)
            balance = db_member.wallet_balance
            await session.commit()

        embed = await create_role_description_embed(
            self.ctx, self.page, self.premium_roles, balance, self.viewer, self.member
        )
        view = RoleDescriptionView(
            self.ctx,
            self.bot,
            self.page,
            self.premium_roles,
            balance,
            self.viewer,
            self.member,
        )
        await interaction.response.edit_message(embed=embed, view=view)

    async def generate_embed(self, session):
        """Generate the embed for the role shop."""
        db_member = await MemberQueries.get_or_add_member(session, self.viewer.id)
        balance = db_member.wallet_balance
        premium_service = await self.bot.get_service(IPremiumService, session)
        premium_roles = await premium_service.get_member_premium_roles(self.member.id)
        return await create_shop_embed(
            self.ctx,
            balance,
            self.role_price_map,
            premium_roles,
            self.page,
            self.viewer,
            self.member,
        )

    async def show_my_id(self, interaction: discord.Interaction):
        """Show the user's ID in a copyable format."""
        user_id = interaction.user.id
        message = f"🆔 **Twoje Discord ID:**\n```\n{user_id}\n```\n💡 *Kliknij w ramkę aby zaznaczyć i skopiować ID*"
        await interaction.response.send_message(message, ephemeral=True)


class BuyRoleButton(discord.ui.Button):
    """Button for buying a role."""

    def __init__(self, bot=None, member=None, role_name=None, **kwargs):
        """Initialize the button.

        Args:
            bot: The bot instance (optional)
            member: The member to buy role for (optional)
            role_name: The name of the role to buy (optional)
            **kwargs: Additional button parameters (style, label, etc.)
        """
        kwargs.setdefault("style", discord.ButtonStyle.primary)
        kwargs.setdefault("label", "Kup rolę")
        kwargs.setdefault("emoji", bot.config.get("emojis", {}).get("mastercard", "💳") if bot else "💳")
        super().__init__(**kwargs)
        self.bot = bot
        self.member = member
        self.role_name = role_name
        # Initialize MessageSender with bot instance if available, otherwise without
        self.message_sender = MessageSender(bot) if bot else MessageSender()

    async def callback(self, interaction: discord.Interaction):
        """Handle the button click."""
        # If bot and member were provided (from payment view), use them
        if self.bot and self.member:
            ctx = await self.bot.get_context(interaction.message)
            ctx.author = self.member
            if self.role_name:
                await ctx.invoke(self.bot.get_command("shop"), role_name=self.role_name)
            else:
                await ctx.invoke(self.bot.get_command("shop"))
        # Otherwise use the standard shop command (from shop view)
        else:
            if self.role_name:
                await interaction.client.get_command("shop")(interaction, role_name=self.role_name)
            else:
                await interaction.client.get_command("shop")(interaction)


class RoleDescriptionView(discord.ui.View):
    """Role description view for displaying and handling role purchases."""

    def __init__(
        self,
        ctx: Context,
        bot,
        page=1,
        premium_roles=None,
        balance=0,
        viewer: discord.Member = None,
        member: discord.Member = None,
    ):
        super().__init__()
        self.ctx = ctx
        self.bot = bot
        self.page = page
        self.premium_roles = premium_roles or []
        self.balance = balance
        self.viewer = viewer
        self.member = member
        # Initialize MessageSender with bot instance for consistency
        self.message_sender = MessageSender(bot)

        # Add buttons
        previous_button = discord.ui.Button(label="⬅️", style=discord.ButtonStyle.secondary)
        previous_button.callback = self.previous_page
        self.add_item(previous_button)

        buy_button = discord.ui.Button(
            label="Kup rangę",
            style=discord.ButtonStyle.primary,
            disabled=premium_roles[page - 1]["price"] > balance,
            emoji=self.bot.config.get("emojis", {}).get("mastercard", "💳"),
        )
        buy_button.callback = self.buy_role
        self.add_item(buy_button)

        go_to_shop_button = discord.ui.Button(label="Do sklepu", style=discord.ButtonStyle.primary)
        go_to_shop_button.callback = self.go_to_shop
        self.add_item(go_to_shop_button)

        self.add_item(
            discord.ui.Button(
                label="Doładuj konto",
                style=discord.ButtonStyle.link,
                url=self.bot.config["donate_url"],
            )
        )

        next_button = discord.ui.Button(label="➡️", style=discord.ButtonStyle.secondary)
        next_button.callback = self.next_page
        self.add_item(next_button)

    def _add_premium_text_to_description(self, description: str) -> str:
        """Helper method to add premium text to description consistently."""
        _, premium_text = self.message_sender._get_premium_text(self.ctx)
        if premium_text:
            return f"{description}\n{premium_text}"
        return description

    async def create_view_for_user(
        self, interaction: discord.Interaction
    ) -> tuple[discord.Embed, "RoleDescriptionView"]:
        """Create a new view instance for a different user."""
        async with self.bot.get_db() as session:
            db_viewer = await MemberQueries.get_or_add_member(session, interaction.user.id)
            balance = db_viewer.wallet_balance
            await session.commit()

        new_view = RoleDescriptionView(
            self.ctx,
            self.bot,
            self.page,
            self.premium_roles,
            balance,
            viewer=interaction.user,
            member=interaction.user,
        )
        embed = await create_role_description_embed(
            self.ctx,
            self.page,
            self.premium_roles,
            balance,
            viewer=interaction.user,
            member=interaction.user,
        )
        return embed, new_view

    async def next_page(self, interaction: discord.Interaction):
        """Go to the next page in the role shop view."""
        if interaction.user.id != self.viewer.id:
            embed, view = await self.create_view_for_user(interaction)
            # Add premium text to the message
            base_text = self._add_premium_text_to_description("Oto twój własny widok opisu ról:")
            await interaction.response.send_message(base_text, embed=embed, view=view, ephemeral=True)
            return

        self.page = (self.page % len(self.premium_roles)) + 1
        embed = await create_role_description_embed(
            self.ctx,
            self.page,
            self.premium_roles,
            self.balance,
            self.viewer,
            self.member,
        )
        view = RoleDescriptionView(
            self.ctx,
            self.bot,
            self.page,
            self.premium_roles,
            self.balance,
            self.viewer,
            self.member,
        )
        await interaction.response.edit_message(embed=embed, view=view)

    async def previous_page(self, interaction: discord.Interaction):
        """Go to the previous page in the role description view."""
        if interaction.user.id != self.viewer.id:
            embed, view = await self.create_view_for_user(interaction)
            # Add premium text to the message
            base_text = self._add_premium_text_to_description("Oto twój własny widok opisu ról:")
            await interaction.response.send_message(base_text, embed=embed, view=view, ephemeral=True)
            return

        self.page = (self.page - 2) % len(self.premium_roles) + 1
        embed = await create_role_description_embed(
            self.ctx,
            self.page,
            self.premium_roles,
            self.balance,
            self.viewer,
            self.member,
        )
        view = RoleDescriptionView(
            self.ctx,
            self.bot,
            self.page,
            self.premium_roles,
            self.balance,
            self.viewer,
            self.member,
        )
        await interaction.response.edit_message(embed=embed, view=view)

    async def buy_role(self, interaction: discord.Interaction):
        """Buy a role from description."""
        if interaction.user.id != self.viewer.id:
            embed, view = await self.create_view_for_user(interaction)
            # Add premium text to the message
            base_text = self._add_premium_text_to_description("Oto twój własny widok opisu ról:")
            await interaction.response.send_message(base_text, embed=embed, view=view, ephemeral=True)
            return

        role_name = self.premium_roles[self.page - 1]["name"]
        role_price = self.premium_roles[self.page - 1]["price"]
        role_shop_view = RoleShopView(
            self.ctx,
            self.bot,
            self.premium_roles,
            self.balance,
            self.page,
            self.viewer,
            self.member,
        )
        await role_shop_view.handle_buy_role(interaction, role_name, self.member, duration_days=30, price=role_price)

    async def go_to_shop(self, interaction: discord.Interaction):
        """Go to the role shop view."""
        if interaction.user.id != self.viewer.id:
            embed, view = await self.create_view_for_user(interaction)
            # Add premium text to the message
            base_text = self._add_premium_text_to_description("Oto twój własny widok opisu ról:")
            await interaction.response.send_message(base_text, embed=embed, view=view, ephemeral=True)
            return

        async with self.bot.get_db() as session:
            premium_service = await self.bot.get_service(IPremiumService, session)
            premium_roles = await premium_service.get_member_premium_roles(self.member.id)

        view = RoleShopView(
            self.ctx,
            self.bot,
            self.premium_roles,
            self.balance,
            page=1,
            viewer=self.viewer,
            member=self.member,
        )
        embed = await create_shop_embed(
            self.ctx,
            self.balance,
            view.role_price_map,
            premium_roles,
            page=1,
            viewer=self.viewer,
            member=self.member,
        )
        await interaction.response.edit_message(embed=embed, view=view)


class ConfirmView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=60.0)  # 60 seconds timeout
        self.value = None

    @discord.ui.button(label="Potwierdź", style=discord.ButtonStyle.green)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.value = True
        await interaction.response.send_message("Potwierdzono zakup.", ephemeral=True)
        self.stop()

    @discord.ui.button(label="Anuluj", style=discord.ButtonStyle.red)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.value = False
        await interaction.response.send_message("Anulowano zakup.", ephemeral=True)
        self.stop()

    async def on_timeout(self):
        self.value = False
        self.stop()


class LowerRoleChoiceView(discord.ui.View):
    """View for handling the choice between extending current role or buying a lower/higher one."""

    def __init__(
        self,
        bot,
        member: discord.Member,
        current_role_name: str,
        new_role_name: str,
        price: int,
        days_to_add: int,
        is_upgrade: bool = False,
    ):
        super().__init__(timeout=120.0)  # 2 minutes timeout
        self.bot = bot
        self.member = member
        self.current_role_name = current_role_name
        self.new_role_name = new_role_name
        self.price = price
        self.days_to_add = days_to_add
        self.is_upgrade = is_upgrade
        self.value = None
        self.premium_manager = PremiumRoleManager(bot, bot.guild)

        # Add buttons based on whether this is an upgrade or not
        if not is_upgrade:
            extend_button = discord.ui.Button(
                label="Przedłuż obecną rangę (usuwa muty)",
                style=discord.ButtonStyle.primary,
                row=0,
            )
            extend_button.callback = self.extend_button_callback
            self.add_item(extend_button)

        buy_button = discord.ui.Button(
            label=f"Kup nową rangę {new_role_name}" + (" (usuwa muty)" if is_upgrade else ""),
            style=discord.ButtonStyle.primary if is_upgrade else discord.ButtonStyle.secondary,
            row=0,
        )
        buy_button.callback = self.buy_button_callback
        self.add_item(buy_button)

        cancel_button = discord.ui.Button(label="Anuluj", style=discord.ButtonStyle.danger, row=1)
        cancel_button.callback = self.cancel_button_callback
        self.add_item(cancel_button)

    async def on_timeout(self):
        """Handle timeout by setting the value to timeout"""
        self.value = "timeout"
        self.stop()

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """Check if the interaction is from the correct user"""
        if interaction.user.id != self.member.id:
            await interaction.response.send_message("Tylko osoba kupująca może wybrać tę opcję.", ephemeral=True)
            return False
        return True

    async def extend_button_callback(self, interaction: discord.Interaction):
        """Handle extend button click"""
        self.value = "extend"
        await interaction.response.defer()
        self.stop()

    async def buy_button_callback(self, interaction: discord.Interaction):
        """Handle buy button click"""
        self.value = "buy_lower" if not self.is_upgrade else "buy_higher"
        await interaction.response.defer()
        self.stop()

    async def cancel_button_callback(self, interaction: discord.Interaction):
        """Handle cancel button click"""
        self.value = "cancel"
        await interaction.response.defer()
        self.stop()

    async def get_refund_info(self, session) -> int:
        """Calculate refund amount for current role."""
        role_config = next(
            (r for r in self.bot.config["premium_roles"] if r["name"] == self.current_role_name),
            None,
        )
        if not role_config:
            return 0

        current_role = await RoleQueries.get_member_role(
            session,
            self.member.id,
            discord.utils.get(self.bot.guild.roles, name=self.current_role_name).id,
        )
        if not current_role:
            return 0

        return calculate_refund(current_role.expiration_date, role_config["price"])
