"""
On Payments Event Cog
"""

import asyncio
import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Optional

import discord
from discord.ext import commands, tasks

from cogs.ui.shop_embeds import create_shop_embed
from cogs.views.shop_views import RoleShopView
from datasources.queries import MemberQueries, RoleQueries
from utils.currency import CURRENCY_UNIT
from utils.premium import PremiumManager, TipplyDataProvider

logger = logging.getLogger(__name__)

TOKEN = os.environ.get("TIPO_API_TOKEN")

# Flaga do łatwego wyłączenia starego systemu po testach
LEGACY_SYSTEM_ENABLED = True

# Mapowanie starych kwot na nowe
LEGACY_AMOUNTS = {15: 49, 25: 99, 45: 499, 85: 999}  # zG50  # zG100  # zG500  # zG1000

# Mapowanie kwot do dni przedłużenia dla poszczególnych ról premium
PARTIAL_EXTENSIONS = {
    "zG100": {
        49: int(49 / 99 * 30),  # ~15 dni (49/99 * 30)
        50: int(50 / 99 * 30),  # ~15 dni (50/99 * 30)
        99: 30,
        100: 30,
    },
    "zG500": {
        49: int(49 / 499 * 30),  # ~3 dni (49/499 * 30)
        50: int(50 / 499 * 30),  # ~3 dni (50/499 * 30)
        99: int(99 / 499 * 30),  # ~6 dni (99/499 * 30)
        100: int(100 / 499 * 30),  # ~6 dni (100/499 * 30)
        499: 30,
        500: 30,
    },
    "zG1000": {
        49: int(49 / 999 * 30),  # ~1 dzień (49/999 * 30)
        50: int(50 / 999 * 30),  # ~1 dzień (50/999 * 30)
        99: int(99 / 999 * 30),  # ~3 dni (99/999 * 30)
        100: int(100 / 999 * 30),  # ~3 dni (100/999 * 30)
        499: int(499 / 999 * 30),  # ~15 dni (499/999 * 30)
        500: int(500 / 999 * 30),  # ~15 dni (500/999 * 30)
        999: 30,
        1000: 30,
    },
}


class OnPaymentEvent(commands.Cog):
    """Class for the Tipo Payments Cog"""

    def __init__(self, bot):
        self.bot = bot
        self.guild = None
        self.premium_manager = PremiumManager(bot)
        self.data_provider = TipplyDataProvider(bot.get_db)
        self.check_payments.start()  # pylint: disable=no-member

    async def cog_unload(self):
        """Cog Unload"""
        self.check_payments.cancel()  # pylint: disable=no-member

    @tasks.loop(minutes=1.0)
    async def check_payments(self):
        """Check Payments"""
        try:
            async with self.bot.get_db() as session:
                payments_data = await self.data_provider.get_data(session)
                if payments_data:
                    logger.info("Found %s new payments", len(payments_data))
                for payment_data in payments_data:
                    try:
                        await self.premium_manager.process_data(session, payment_data)
                        await self.handle_payment(session, payment_data)
                        logger.info("Processed payment: %s", payment_data)
                        await session.commit()
                    except Exception as err:
                        logger.error("Error while processing payment %s: %s", payment_data, err)
                        await session.rollback()
        except Exception as e:
            logger.error(f"Error in check_payments: {str(e)}")

    @check_payments.before_loop
    async def before_check_payments(self):
        """Wait for bot to be ready and guild to be set before starting payments check"""
        logger.info("Waiting for bot to be ready...")
        await self.bot.wait_until_ready()

        # Wait for guild to be set with timeout
        retry_count = 0
        max_retries = 30
        while not self.guild and retry_count < max_retries:
            self.guild = self.bot.get_guild(self.bot.guild_id)
            if not self.guild:
                retry_count += 1
                logger.info(f"Waiting for guild to be set... (attempt {retry_count}/{max_retries})")
                await asyncio.sleep(1)

        if not self.guild:
            logger.error(f"Failed to set guild after {max_retries} attempts")
            return

        logger.info("Bot is ready and guild is set, starting payment checks")

    @commands.Cog.listener()
    async def on_ready(self):
        """Set guild when bot is ready"""
        self.guild = self.bot.get_guild(self.bot.guild_id)
        if not self.guild:
            logger.error("Cannot find guild with ID %d", self.bot.guild_id)
            return

        logger.info("Setting guild for PremiumManager in OnPaymentEvent")
        self.premium_manager.set_guild(self.guild)

    async def extend_existing_role_partially(
        self, session, member: discord.Member, final_amount: int
    ) -> Optional[discord.Embed]:
        """
        Używane WYŁĄCZNIE, gdy użytkownik już ma zG100 / zG1000 (albo inne z PARTIAL_EXTENSIONS).
        Jeśli final_amount pasuje do PARTIAL_EXTENSIONS[rola], to przedłużamy dokładnie o days_to_add.
        W przeciwnym razie zwracamy None.
        """
        await self.remove_mute_roles(member)
        logger.info(
            f"Checking partial extension for {member.display_name} with amount {final_amount}"
        )

        # Przejrzyj wszystkie role premium, które obsługujemy w PARTIAL_EXTENSIONS
        for role_name, amounts_map in PARTIAL_EXTENSIONS.items():
            role_obj = discord.utils.get(self.guild.roles, name=role_name)
            if not role_obj:
                logger.error(f"Role {role_name} not found in the guild")
                continue

            # Jeśli user ma tę rolę
            if role_obj in member.roles:
                # Pobierz liczbę dni z amounts_map (domyślnie 0, jeśli brak)
                days_to_add = amounts_map.get(final_amount, 0)
                if days_to_add > 0:
                    # Znajdź w bazie, czy user ma MemberRole
                    current_member_role = await RoleQueries.get_member_role(
                        session, member.id, role_obj.id
                    )
                    if current_member_role:
                        # Przedłuż
                        await RoleQueries.update_role_expiration_date(
                            session, member.id, role_obj.id, timedelta(days=days_to_add)
                        )
                        logger.info(
                            f"Extended role {role_name} for {member.display_name} by {days_to_add} days (partial extension)"
                        )

                        # Przygotuj embed z informacją
                        embed = discord.Embed(
                            title="Gratulacje!",
                            description=f"Przedłużyłeś rolę {role_name} o {days_to_add} dni i zdjęto ci muta!",
                            color=discord.Color.green(),
                        )
                        return embed
                    else:
                        logger.warning(
                            f"No DB entry found for {role_name} - user {member.display_name} has the role on Discord, but not in DB"
                        )

        # Jeśli doszliśmy tutaj, to znaczy że nie było przedłużenia
        return None

    async def handle_payment(self, session, payment_data):
        """Handle a single payment and send notification"""
        channel_id = self.bot.config["channels"]["donation"]
        channel = self.bot.get_channel(channel_id)

        if not channel:
            logger.error("Donation channel not found: %s", channel_id)
            return

        member = await self.premium_manager.get_member(payment_data.name)
        if member is None:
            logger.error("Member not found: %s", payment_data.name)
            return

        # Initialize variables
        original_amount = payment_data.amount
        final_amount = (
            payment_data.converted_amount
            if payment_data.converted_amount is not None
            else original_amount
        )
        premium_role = None
        logger.info(
            f"Processing payment for {member.display_name} - original: {original_amount}, final: {final_amount}"
        )

        # Initialize owner and embed variables
        owner_id = self.bot.config.get("owner_id")
        owner = self.guild.get_member(owner_id)
        embed = None

        # Najpierw dodaj do portfela
        await MemberQueries.add_to_wallet_balance(session, member.id, final_amount)

        # Define premium role priority
        premium_priority = {"zG50": 1, "zG100": 2, "zG500": 3, "zG1000": 4}

        # Check user's highest premium role
        user_highest_priority = 0
        for role_name, priority in premium_priority.items():
            role_obj = discord.utils.get(member.guild.roles, name=role_name)
            if role_obj and role_obj in member.roles:
                user_highest_priority = max(user_highest_priority, priority)

        logger.info(f"User's highest premium role priority: {user_highest_priority}")

        # Jeśli kwota >= 15, nadaj odpowiednie role tymczasowe (zawsze, niezależnie od premium)
        if final_amount >= 15:
            await self.assign_temporary_roles(session, member, original_amount)
            await self.remove_mute_roles(member)  # Zawsze zdejmuj muty po nadaniu ról $

        # Try partial extension first
        embed_partial = await self.extend_existing_role_partially(session, member, final_amount)
        if embed_partial:
            logger.info("Using partial extension")
            embed = embed_partial
        else:
            # Then try to find matching premium role
            for role_config in self.bot.config["premium_roles"]:
                if final_amount in [role_config["price"], role_config["price"] + 1]:
                    # Check if user already has higher role
                    role_priority = premium_priority.get(role_config["name"], 0)
                    if role_priority < user_highest_priority:
                        logger.info(
                            f"User already has higher role (priority {user_highest_priority}), ignoring new role {role_config['name']} (priority {role_priority})"
                        )
                        continue
                    premium_role = role_config
                    break

            if premium_role:
                logger.info(f"Found matching premium role: {premium_role['name']}")
                role = discord.utils.get(self.guild.roles, name=premium_role["name"])
                if not role:
                    logger.error(f"Role {premium_role['name']} not found")
                    embed = discord.Embed(
                        title="Błąd",
                        description="Wystąpił błąd podczas przydzielania roli premium. Skontaktuj się z administracją.",
                        color=discord.Color.red(),
                    )
                else:
                    current_premium_role = await RoleQueries.get_member_role(
                        session, member.id, role.id
                    )

                    # Sprawdź czy to przedłużenie tej samej roli
                    if current_premium_role and role in member.roles:
                        logger.info(
                            f"Found existing premium role {role.name} for member {member.display_name}"
                        )
                        days_left = (
                            current_premium_role.expiration_date - datetime.now(timezone.utc)
                        ).days
                        logger.info(f"Current premium role {role.name} has {days_left} days left")

                        # Sprawdź czy to kwota upgradu i czy rola kwalifikuje się do upgradu
                        can_upgrade = False
                        if role.name == "zG50" and final_amount == 50 and 29 <= days_left <= 33:
                            # Próba upgradu do zG100
                            upgrade_role = discord.utils.get(self.guild.roles, name="zG100")
                            if upgrade_role:
                                await member.remove_roles(role)
                                await RoleQueries.delete_member_role(session, member.id, role.id)
                                await member.add_roles(upgrade_role)
                                await RoleQueries.add_role_to_member(
                                    session, member.id, upgrade_role.id, timedelta(days=days_left)
                                )
                                await session.commit()
                                embed = discord.Embed(
                                    title="Gratulacje!",
                                    description=f"Ulepszono twoją rolę z {role.name} na zG100!",
                                    color=discord.Color.green(),
                                )
                                can_upgrade = True
                        elif role.name == "zG100" and final_amount == 400 and 29 <= days_left <= 33:
                            # Próba upgradu do zG500 (bo 99 + 400 = 499)
                            upgrade_role = discord.utils.get(self.guild.roles, name="zG500")
                            if upgrade_role:
                                await member.remove_roles(role)
                                await RoleQueries.delete_member_role(session, member.id, role.id)
                                await member.add_roles(upgrade_role)
                                await RoleQueries.add_role_to_member(
                                    session, member.id, upgrade_role.id, timedelta(days=days_left)
                                )
                                await session.commit()
                                embed = discord.Embed(
                                    title="Gratulacje!",
                                    description=f"Ulepszono twoją rolę z {role.name} na zG500!",
                                    color=discord.Color.green(),
                                )
                                can_upgrade = True
                        elif role.name == "zG500" and final_amount == 500 and 29 <= days_left <= 33:
                            # Próba upgradu do zG1000 (bo 499 + 500 = 999)
                            upgrade_role = discord.utils.get(self.guild.roles, name="zG1000")
                            if upgrade_role:
                                await member.remove_roles(role)
                                await RoleQueries.delete_member_role(session, member.id, role.id)
                                await member.add_roles(upgrade_role)
                                await RoleQueries.add_role_to_member(
                                    session, member.id, upgrade_role.id, timedelta(days=days_left)
                                )
                                await session.commit()
                                embed = discord.Embed(
                                    title="Gratulacje!",
                                    description=f"Ulepszono twoją rolę z {role.name} na zG1000!",
                                    color=discord.Color.green(),
                                )
                                can_upgrade = True

                        # Jeśli nie można zrobić upgradu, sprawdź czy to przedłużenie
                        if not can_upgrade:
                            # Sprawdź czy kwota odpowiada przedłużeniu aktualnej roli
                            role_extension_amounts = {
                                "zG50": [49, 50],  # 50 przedłuża jeśli nie można zrobić upgradu
                                "zG100": [99, 100],  # 100 przedłuża i daje +1G
                                "zG500": [499, 500],  # 500 przedłuża i daje +1G
                                "zG1000": [999, 1000],  # 1000 przedłuża i daje +1G
                            }

                            if final_amount in role_extension_amounts.get(role.name, []):
                                logger.info(
                                    f"Amount {final_amount} matches extension amount for role {role.name}"
                                )
                                logger.info(
                                    f"Checking extension days for role {role.name}. Current days_left: {days_left}"
                                )
                                extension_days = 33 if days_left < 1 or days_left >= 29 else 30
                                logger.info(
                                    f"Decided to extend role {role.name} by {extension_days} days (days_left < 1: {days_left < 1}, days_left > 29: {days_left > 29})"
                                )

                                await RoleQueries.update_role_expiration_date(
                                    session, member.id, role.id, timedelta(days=extension_days)
                                )

                                # Dodaj 1G jeśli zapłacił więcej
                                bonus_msg = ""
                                if final_amount > premium_role["price"]:
                                    await MemberQueries.add_to_wallet_balance(session, member.id, 1)
                                    bonus_msg = f" Dodatkowo otrzymujesz 1{CURRENCY_UNIT}."

                                await session.commit()

                                bonus_time_msg = (
                                    " (10% czasu gratis!)" if extension_days == 33 else ""
                                )
                                embed = discord.Embed(
                                    title="Gratulacje!",
                                    description=f"Przedłużyłeś rolę {role.name} o {extension_days} dni{bonus_time_msg}!{bonus_msg}",
                                    color=discord.Color.green(),
                                )

                    # Standardowe nadanie roli jeśli nie ma żadnej
                    elif role not in member.roles:
                        await RoleQueries.add_role_to_member(
                            session, member.id, role.id, timedelta(days=30)
                        )

                        # Dodaj 1G tylko jeśli zapłacił więcej niż cena roli
                        bonus_msg = ""
                        if final_amount > premium_role["price"]:
                            await MemberQueries.add_to_wallet_balance(session, member.id, 1)
                            bonus_msg = f" Dodatkowo otrzymujesz 1{CURRENCY_UNIT}."

                        await member.add_roles(role)
                        await session.commit()

                        embed = discord.Embed(
                            title="Gratulacje!",
                            description=f"Zakupiłeś rolę {role.name}!{bonus_msg}",
                            color=discord.Color.green(),
                        )

                    await self.remove_mute_roles(member)
            else:
                # Użyj przekonwertowanej kwoty w wiadomości
                amount_to_display = final_amount
                logger.info(
                    f"Handling payment for {member.display_name} with amount {amount_to_display}G"
                )
                embed = discord.Embed(
                    title="Gratulacje!",
                    description=f"Twoje konto zostało pomyślnie zasilone {amount_to_display}{CURRENCY_UNIT}!\nMożesz teraz kupić rangę w sklepie(unmute gratis!), klikając przycisk poniżej.",
                    color=discord.Color.green(),
                )

        # Add image and send message
        embed.set_image(url=self.bot.config["gifs"]["donation"])

        view = discord.ui.View()
        view.add_item(
            BuyRoleButton(
                bot=self.bot,
                member=member,
                label="Kup rangę",
                style=discord.ButtonStyle.success,
            )
        )
        view.add_item(
            discord.ui.Button(
                label="Doładuj konto",
                style=discord.ButtonStyle.link,
                url=self.bot.config["donate_url"],
            )
        )

        message = await channel.send(content=f"{member.mention}", embed=embed, view=view)
        if owner:
            await message.reply(f"{owner.mention}")

    async def assign_temporary_roles(self, session, member, amount):
        """
        Assign all applicable temporary roles based on donation amount.
        After $4 and $8 roles, wait 5 seconds.
        After all roles are assigned, wait additional 5 seconds.
        """
        logger.info(
            f"Member {member.display_name} roles before assignment: {[r.name for r in member.roles]}"
        )

        roles_tiers = [
            (15, "$2"),
            (25, "$4"),
            (45, "$8"),
            (85, "$16"),
            (160, "$32"),
            (320, "$64"),
            (640, "$128"),
        ]

        for amount_required, role_name in roles_tiers:
            logger.info(f"Checking if {amount} >= {amount_required} for role {role_name}")
            if amount >= amount_required:
                role = discord.utils.get(self.guild.roles, name=role_name)
                if role:
                    logger.info(f"Found role {role_name} for {member.display_name}")
                    try:
                        # Sprawdź czy rola już istnieje i ile dni zostało
                        current_role = await RoleQueries.get_member_role(
                            session, member.id, role.id
                        )
                        days_to_add = 30

                        if current_role and role in member.roles:
                            days_left = (
                                current_role.expiration_date - datetime.now(timezone.utc)
                            ).days
                            if days_left < 1 or days_left >= 29:
                                days_to_add = 33
                                logger.info(
                                    f"Role {role_name} has {days_left} days left, extending by {days_to_add} days"
                                )

                        await RoleQueries.add_or_update_role_to_member(
                            session, member.id, role.id, timedelta(days=days_to_add)
                        )

                        if role not in member.roles:
                            await member.add_roles(role)
                            logger.info(
                                f"Assigned role {role_name} to member {member.display_name}"
                            )
                        else:
                            logger.info(
                                f"Updated expiration for role {role_name} of member {member.display_name} to {days_to_add} days"
                            )

                        # Po $4 i $8 odczekaj 5 sek
                        if role_name in ["$4", "$8"]:
                            logger.info("Waiting 5 seconds after assigning role %s.", role_name)
                            await asyncio.sleep(5)

                    except Exception as e:
                        logger.error(
                            f"Error assigning/updating role {role_name} to member {member.display_name}: {str(e)}"
                        )
                else:
                    logger.error(f"Role {role_name} not found in the guild")
            else:
                logger.info(f"Amount {amount} is not enough for role {role_name}")

        # Po zakończeniu nadawania wszystkich ról czekamy dodatkowe 5 sekund
        logger.info("Finished assigning $ roles. Waiting 5 seconds before next steps.")
        await asyncio.sleep(5)

    async def remove_mute_roles(self, member):
        """Remove mute roles from a member if they have any temporary roles assigned"""
        mute_roles_names = [role["name"] for role in self.bot.config["mute_roles"]]
        roles_to_remove = [role for role in member.roles if role.name in mute_roles_names]

        if roles_to_remove:
            await member.remove_roles(*roles_to_remove)
            logger.info("Removed mute roles from %s", member.display_name)


class BuyRoleButton(discord.ui.Button):
    """Button to buy a role."""

    def __init__(self, bot, member, **kwargs):
        super().__init__(**kwargs)
        self.bot = bot
        self.member = member

    async def callback(self, interaction: discord.Interaction):
        ctx = await self.bot.get_context(interaction.message)
        ctx.author = interaction.user
        await ctx.invoke(self.bot.get_command("shop"), member=self.member)


async def setup(bot: commands.Bot):
    """Setup function for the payment event cog"""
    await bot.add_cog(OnPaymentEvent(bot))
