"""Role purchase handling logic for shop views."""
import logging
from datetime import datetime, timedelta, timezone

import discord
from discord.ext.commands import Context

from datasources.queries import MemberQueries, RoleQueries
from utils.message_sender import MessageSender
from utils.premium_logic import PremiumRoleManager

from .constants import MONTHLY_DURATION
from .embed_helpers import (
    create_cancel_embed,
    create_downgrade_embed,
    create_error_embed,
    create_extension_embed,
    create_purchase_embed,
    create_upgrade_embed,
)
from .lower_role_choice_view import LowerRoleChoiceView
from .role_shop_helpers import RoleShopPricing, RoleValidation

logger = logging.getLogger(__name__)


class RolePurchaseHandler:
    """Handles the complex logic of role purchases."""

    def __init__(self, bot, guild: discord.Guild, premium_manager: PremiumRoleManager):
        self.bot = bot
        self.guild = guild
        self.premium_manager = premium_manager
        self.message_sender = MessageSender(bot)

    async def handle_buy_role(
        self,
        interaction: discord.Interaction,
        ctx: Context,
        member: discord.Member,
        role_name: str,
        page: int,
        balance: int,
        premium_roles: list,
    ) -> None:
        """Handle the purchase of a role with all the complex logic."""
        # Get role and price information
        role_config = next((r for r in premium_roles if r["name"] == role_name), None)
        if not role_config:
            await interaction.response.send_message("Nie znaleziono konfiguracji roli.", ephemeral=True)
            return

        price_map = RoleShopPricing.get_price_map(premium_roles, page)
        price = price_map.get(role_name, 0)

        # Check balance
        if balance < price:
            await interaction.response.send_message(
                f"Nie masz wystarczająco środków. Potrzebujesz {price} zł.", ephemeral=True
            )
            return

        # Calculate subscription duration
        days_to_add = RoleShopPricing.calculate_subscription_days(page)

        # Check for existing premium roles from database
        current_highest_role = None
        async with self.bot.get_db() as session:
            from datasources.queries import RoleQueries

            member_roles = await RoleQueries.get_member_roles(session, member.id)

            # Find highest active premium role
            active_roles = []
            now = datetime.now(timezone.utc)
            for member_role in member_roles:
                if member_role.expiration_date and member_role.expiration_date > now:
                    # Get role name
                    for role_config in premium_roles:
                        discord_role = discord.utils.get(self.guild.roles, name=role_config["name"])
                        if discord_role and discord_role.id == member_role.role_id:
                            active_roles.append(role_config["name"])
                            break

            # Get highest role (iterate in reverse order since config is lowest to highest)
            for role_config in reversed(premium_roles):
                if role_config["name"] in active_roles:
                    current_highest_role = role_config["name"]
                    break

        if current_highest_role:
            # Handle role upgrade/downgrade/extension logic
            is_upgrade = RoleValidation.is_role_upgrade(current_highest_role, role_name, premium_roles)
            is_downgrade = RoleValidation.is_role_downgrade(current_highest_role, role_name, premium_roles)

            if is_upgrade:
                await self._handle_role_upgrade(
                    interaction, ctx, member, current_highest_role, role_name, price, days_to_add
                )
            elif is_downgrade:
                # For downgrades, automatically apply partial extension
                await self._handle_partial_extension(interaction, ctx, member, current_highest_role, role_name, price)
            else:
                # Same role - extend
                await self._handle_role_extension(interaction, ctx, member, role_name, price, days_to_add)
        else:
            # First time purchase
            await self._handle_first_purchase(interaction, ctx, member, role_name, price, days_to_add)

    async def _handle_role_upgrade(
        self,
        interaction: discord.Interaction,
        ctx: Context,
        member: discord.Member,
        current_role: str,
        new_role: str,
        price: int,
        days_to_add: int,
    ) -> None:
        """Handle upgrading to a higher tier role."""
        # Show upgrade choice view
        choice_view = LowerRoleChoiceView(self.bot, member, current_role, new_role, price, days_to_add, is_upgrade=True)

        # Calculate refund
        async with self.bot.get_db() as session:
            refund_amount = await choice_view.get_refund_info(session)

        member_color = member.color if member.color.value != 0 else discord.Color.blurple()
        embed = create_upgrade_embed(current_role, new_role, price, refund_amount, member_color)

        await interaction.response.send_message(embed=embed, view=choice_view, ephemeral=True)

        await choice_view.wait()

        if choice_view.value == "buy_higher":
            await self._process_role_upgrade(ctx, member, current_role, new_role, price, days_to_add, refund_amount)
        elif choice_view.value == "cancel":
            await interaction.followup.send("Anulowano zakup.", ephemeral=True)

    async def _handle_role_downgrade(
        self,
        interaction: discord.Interaction,
        ctx: Context,
        member: discord.Member,
        current_role: str,
        new_role: str,
        price: int,
        days_to_add: int,
    ) -> None:
        """Handle downgrading to a lower tier role."""
        choice_view = LowerRoleChoiceView(
            self.bot, member, current_role, new_role, price, days_to_add, is_upgrade=False
        )

        member_color = member.color if member.color.value != 0 else discord.Color.blurple()
        embed = create_downgrade_embed(current_role, new_role, price, days_to_add, member_color)

        await interaction.response.send_message(embed=embed, view=choice_view, ephemeral=True)

        await choice_view.wait()

        if choice_view.value == "extend":
            # Extend current role instead
            async with self.bot.get_db() as session:
                success = await self._process_role_purchase(
                    session, member, current_role, price, days_to_add, is_extension=True
                )

                if success:
                    member_color = member.color if member.color.value != 0 else discord.Color.blurple()
                    embed = create_extension_embed(current_role, days_to_add, member_color)
                    await interaction.followup.send(embed=embed)
                else:
                    member_color = member.color if member.color.value != 0 else discord.Color.blurple()
                    embed = create_error_embed("Nie udało się przedłużyć rangi", member_color)
                    await interaction.followup.send(embed=embed)
        elif choice_view.value == "buy_lower":
            # Buy the lower role (will be handled separately)
            embed = discord.Embed(
                title="💡 Jak zmienić rangę?",
                description=(
                    "Aby kupić niższą rangę:\n"
                    "1. Użyj komendy `/profile`\n"
                    "2. Kliknij **Sprzedaj Rolę**\n"
                    "3. Kup nową rangę"
                ),
                color=discord.Color.orange(),
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
        elif choice_view.value == "cancel":
            member_color = member.color if member.color.value != 0 else discord.Color.blurple()
            embed = create_cancel_embed(member_color)
            await interaction.followup.send(embed=embed, ephemeral=True)

    async def _handle_partial_extension(
        self,
        interaction: discord.Interaction,
        ctx: Context,
        member: discord.Member,
        current_role: str,
        new_role: str,
        price: int,
    ) -> None:
        """Handle partial extension when buying a lower tier role."""
        # Calculate partial extension days based on price difference
        current_role_price = self.premium_manager.get_role_price(current_role)
        if current_role_price == 0:
            await interaction.response.send_message("Nie można obliczyć częściowego przedłużenia.", ephemeral=True)
            return

        # Calculate days based on what they're paying vs their current role price
        partial_days = int(price / current_role_price * MONTHLY_DURATION)

        async with self.bot.get_db() as session:
            # Process the partial extension
            success = await self._process_role_purchase(
                session, member, current_role, price, partial_days, is_extension=True
            )

            if success:
                # Check if member has mute roles before removing
                had_mute_roles = self.premium_manager.has_mute_roles(member)
                if had_mute_roles:
                    await self.premium_manager.remove_mute_roles(member)

                member_color = member.color if member.color.value != 0 else discord.Color.blurple()
                description = (
                    f"✅ Ranga `{current_role}` przedłużona o `{partial_days} dni`\n(za zakup {new_role} - {price} G)"
                )
                if had_mute_roles:
                    description += "\n🔊 Usunięto wszystkie wyciszenia"

                embed = discord.Embed(description=description, color=member_color)
                await interaction.response.send_message(embed=embed)
            else:
                member_color = member.color if member.color.value != 0 else discord.Color.blurple()
                embed = create_error_embed("Nie udało się przedłużyć rangi", member_color)
                await interaction.response.send_message(embed=embed, ephemeral=True)

    async def _handle_role_extension(
        self,
        interaction: discord.Interaction,
        ctx: Context,
        member: discord.Member,
        role_name: str,
        price: int,
        days_to_add: int,
    ) -> None:
        """Handle extending an existing role."""
        async with self.bot.get_db() as session:
            # Process the extension
            success = await self._process_role_purchase(
                session, member, role_name, price, days_to_add, is_extension=True
            )

            if success:
                member_color = member.color if member.color.value != 0 else discord.Color.blurple()
                embed = create_extension_embed(role_name, days_to_add, member_color)
                await interaction.response.send_message(embed=embed)
            else:
                member_color = member.color if member.color.value != 0 else discord.Color.blurple()
                embed = create_error_embed("Nie udało się przedłużyć rangi", member_color)
                await interaction.response.send_message(embed=embed, ephemeral=True)

    async def _handle_first_purchase(
        self,
        interaction: discord.Interaction,
        ctx: Context,
        member: discord.Member,
        role_name: str,
        price: int,
        days_to_add: int,
    ) -> None:
        """Handle first time role purchase."""
        async with self.bot.get_db() as session:
            success = await self._process_role_purchase(
                session, member, role_name, price, days_to_add, is_extension=False
            )

            if success:
                member_color = member.color if member.color.value != 0 else discord.Color.blurple()
                embed = create_purchase_embed(role_name, days_to_add, member_color)
                await interaction.response.send_message(embed=embed)
            else:
                member_color = member.color if member.color.value != 0 else discord.Color.blurple()
                embed = create_error_embed("Nie udało się zakupić rangi", member_color)
                await interaction.response.send_message(embed=embed, ephemeral=True)

    async def _process_role_purchase(
        self, session, member: discord.Member, role_name: str, price: int, days_to_add: int, is_extension: bool
    ) -> bool:
        """Process the actual role purchase in the database."""
        try:
            # Deduct balance
            await MemberQueries.add_to_wallet_balance(session, member.id, -price)

            # Get or create role
            discord_role = discord.utils.get(self.guild.roles, name=role_name)
            if not discord_role:
                logger.error(f"Role {role_name} not found in guild")
                return False

            # Add/extend role
            if is_extension:
                await RoleQueries.extend_member_role(session, member.id, discord_role.id, days_to_add)
            else:
                expiration_date = datetime.now(timezone.utc) + timedelta(days=days_to_add)
                await RoleQueries.add_member_role(session, member.id, discord_role.id, expiration_date)
                # Add Discord role
                await member.add_roles(discord_role)

            # Premium service logic handled by role assignment above

            await session.commit()
            return True

        except Exception as e:
            logger.error(f"Error processing role purchase: {e}")
            await session.rollback()
            return False

    async def _process_role_upgrade(
        self,
        ctx: Context,
        member: discord.Member,
        current_role: str,
        new_role: str,
        price: int,
        days_to_add: int,
        refund_amount: int,
    ) -> None:
        """Process role upgrade with refund."""
        async with self.bot.get_db() as session:
            try:
                # Remove old role
                old_discord_role = discord.utils.get(self.guild.roles, name=current_role)
                if old_discord_role:
                    await member.remove_roles(old_discord_role)
                    await RoleQueries.delete_member_role(session, member.id, old_discord_role.id)

                # Calculate actual cost
                actual_cost = max(0, price - refund_amount)

                # Process new role purchase
                success = await self._process_role_purchase(session, member, new_role, actual_cost, days_to_add, False)

                if success:
                    member_color = member.color if member.color.value != 0 else discord.Color.blurple()
                    embed = discord.Embed(
                        description=(
                            f"✅ Ulepszono rangę: `{current_role}` → `{new_role}`\n"
                            f"💸 Zwrot: `{refund_amount} G` • Zapłacono: `{actual_cost} G`"
                        ),
                        color=member_color,
                    )
                    await ctx.send(embed=embed)

            except Exception as e:
                logger.error(f"Error processing role upgrade: {e}")
                await ctx.send("❌ Wystąpił błąd podczas ulepszania rangi.")
