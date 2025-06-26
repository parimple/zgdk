"""
On Payments Event Cog
"""

import asyncio
import logging
import os
import subprocess

import discord
from discord.ext import commands, tasks

from cogs.views.shop_views import BuyRoleButton
from datasources.queries import HandledPaymentQueries, MemberQueries
from utils.currency import CURRENCY_UNIT
from utils.premium import PremiumManager, TipplyDataProvider
from utils.premium_logic import PREMIUM_PRIORITY, PremiumRoleManager

logger = logging.getLogger(__name__)

TOKEN = os.environ.get("TIPO_API_TOKEN")

# Flaga do łatwego wyłączenia starego systemu po testach
LEGACY_SYSTEM_ENABLED = True

# Licznik do cleanup zombie procesów co 10 minut
cleanup_counter = 0


def cleanup_zombie_browser_processes():
    """Cleanup zombie browser processes"""
    try:
        subprocess.run(
            ["pkill", "-f", "headless_shell"], capture_output=True, timeout=5
        )
        subprocess.run(
            ["pkill", "-f", "chrome.*--headless"], capture_output=True, timeout=5
        )
        logger.debug("Cleaned up zombie browser processes")
    except Exception as e:
        logger.warning(f"Error during zombie browser cleanup: {e}")


class OnPaymentEvent(commands.Cog):
    """Class for the Tipo Payments Cog"""

    def __init__(self, bot):
        self.bot = bot
        self.guild = None
        self.premium_manager = PremiumManager(bot)
        self.data_provider = TipplyDataProvider(bot.get_db)
        self.role_manager = None
        self.check_payments.start()  # pylint: disable=no-member
        self.processing_locks = {}  # Lock per user ID
        self._guild_ready = asyncio.Event()

    async def cog_unload(self):
        """Cog Unload"""
        self.check_payments.cancel()  # pylint: disable=no-member

    @tasks.loop(minutes=1.0)
    async def check_payments(self):
        """Check Payments"""
        global cleanup_counter
        cleanup_counter += 1

        # Co 10 minut (10 iteracji po 1 minucie) czyść zombie procesy
        if cleanup_counter >= 10:
            cleanup_zombie_browser_processes()
            cleanup_counter = 0

        try:
            async with self.bot.get_db() as session:
                payments_data = await self.data_provider.get_data(session)
                if not payments_data:
                    return

                logger.info("Found %s new payments", len(payments_data))

                # First ensure all members exist in database
                for payment_data in payments_data:
                    try:
                        if not self.premium_manager:
                            logger.error("Premium manager not initialized")
                            continue
                        member = await self.premium_manager.get_member(
                            payment_data.name
                        )
                        if member:
                            await MemberQueries.get_or_add_member(session, member.id)
                            logger.info(
                                f"Ensured member {member.display_name} exists in database"
                            )
                    except Exception as e:
                        logger.error(f"Error ensuring member exists: {str(e)}")
                        continue

                # Commit member creation before processing payments
                await session.commit()

                # Now process all payments in a new transaction
                async with self.bot.get_db() as session:
                    for payment_data in payments_data:
                        try:
                            if not self.premium_manager:
                                logger.error("Premium manager not initialized for payment processing")
                                continue
                            # Process payment data first
                            await self.premium_manager.process_data(
                                session, payment_data
                            )
                            # Then handle the payment (roles, wallet updates etc.)
                            await self.handle_payment(session, payment_data)
                            # Commit after each successful payment
                            await session.commit()
                            logger.info(
                                "Successfully processed payment: %s", payment_data
                            )
                        except Exception as e:
                            logger.error(
                                "Error processing payment %s: %s", payment_data, str(e)
                            )
                            # Rollback the current transaction state
                            await session.rollback()
                            continue

                    logger.info("Finished processing all payments")
        except Exception as e:
            logger.error(f"Error in check_payments: {str(e)}")
            # Session will be rolled back automatically by context manager

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
                logger.info(
                    f"Waiting for guild to be set... (attempt {retry_count}/{max_retries})"
                )
                await asyncio.sleep(1)

        if not self.guild:
            logger.error(f"Failed to set guild after {max_retries} attempts")
            return

        # Initialize role manager
        self.role_manager = PremiumRoleManager(self.bot, self.guild)
        logger.info("Bot is ready and guild is set, starting payment checks")
        self._guild_ready.set()

    @commands.Cog.listener()
    async def on_ready(self):
        """Set guild when bot is ready"""
        self.guild = self.bot.get_guild(self.bot.guild_id)
        if not self.guild:
            logger.error("Cannot find guild with ID %d", self.bot.guild_id)
            return

        # Initialize role manager if not already initialized
        if not self.role_manager:
            self.role_manager = PremiumRoleManager(self.bot, self.guild)

        logger.info("Setting guild for PremiumManager in OnPaymentEvent")
        self.premium_manager.set_guild(self.guild)
        self._guild_ready.set()

    async def wait_for_guild(self, timeout: float = 5.0) -> bool:
        """Wait for guild to be ready with timeout"""
        try:
            await asyncio.wait_for(self._guild_ready.wait(), timeout=timeout)
            return True
        except asyncio.TimeoutError:
            return False

    async def handle_payment(self, session, payment_data):
        """Handle a single payment and send notification"""
        # Wait for guild to be ready before processing payment
        if not self._guild_ready.is_set():
            if not await self.wait_for_guild():
                logger.error("Timeout waiting for guild to be ready")
                return

        if not self.premium_manager:
            logger.error("Premium manager not initialized in handle_payment")
            return
        member = await self.premium_manager.get_member(payment_data.name)

        if member is None:
            logger.error("Member not found: %s", payment_data.name)
            # Try to find the payment record to get its ID for the admin command
            payment_record = await HandledPaymentQueries.get_payment_by_name_and_amount(
                session, payment_data.name, payment_data.amount
            )
            channel_id = self.bot.config["channels"]["donation"]
            channel = self.bot.get_channel(channel_id)
            if channel and payment_record:
                embed = discord.Embed(
                    title="❓ Nie znaleziono użytkownika dla wpłaty",
                    description=(
                        f"Otrzymano wpłatę od **{payment_data.name}** na kwotę **{payment_data.amount} {CURRENCY_UNIT}**, "
                        "ale nie udało się znaleźć pasującego użytkownika na serwerze."
                    ),
                    color=discord.Color.orange(),
                )
                embed.add_field(
                    name="⚙️ Akcja dla administratora",
                    value=(
                        "Aby ręcznie przypisać tę wpłatę do użytkownika, użyj komendy:\n"
                        f"`/przypisz_wplate uzytkownik:@nazwa_użytkownika id_wplaty:{payment_record.id}`"
                    ),
                    inline=False,
                )
                embed.set_footer(text=f"ID Wpłaty: {payment_record.id}")
                embed.timestamp = payment_data.paid_at
                await channel.send(embed=embed)
            return

        # Ensure member exists in database before proceeding
        try:
            await MemberQueries.get_or_add_member(session, member.id)
            await session.flush()
            logger.info(
                f"Ensured member {member.display_name} exists in database before payment processing"
            )
        except Exception as e:
            logger.error(f"Error ensuring member exists: {str(e)}")
            return

        # Użyj locka dla danego użytkownika
        if member.id not in self.processing_locks:
            self.processing_locks[member.id] = asyncio.Lock()

        async with self.processing_locks[member.id]:
            try:
                channel_id = self.bot.config["channels"]["donation"]
                channel = self.bot.get_channel(channel_id)

                if not channel:
                    logger.error("Donation channel not found: %s", channel_id)
                    return

                # Initialize owner variable at the start
                owner_id = self.bot.config.get("owner_id")
                owner = self.guild.get_member(owner_id)

                # Initialize variables
                original_amount = payment_data.amount
                final_amount = (
                    payment_data.converted_amount
                    if payment_data.converted_amount is not None
                    else original_amount
                )
                logger.info(
                    f"Processing payment for {member.display_name} - original: {original_amount}, final: {final_amount}"
                )

                # Get user's current highest premium role before processing
                highest_role_name = self.role_manager.get_user_highest_role_name(member)
                highest_role_priority = (
                    PREMIUM_PRIORITY.get(highest_role_name, 0)
                    if highest_role_name
                    else 0
                )

                # Check if the original amount (before legacy conversion) would result in a higher role
                # than what the user currently has - if so, add to wallet instead
                if highest_role_priority > 0:  # User has a premium role
                    target_role_for_original = None

                    # First check direct price match
                    for role_config in self.bot.config["premium_roles"]:
                        role_price = role_config["price"]
                        rounded_price = role_price + 1
                        if original_amount in [role_price, rounded_price]:
                            target_role_for_original = role_config["name"]
                            break

                    # If no direct match, check legacy mapping
                    if not target_role_for_original and self.bot.config.get(
                        "legacy_system", {}
                    ).get("enabled", False):
                        legacy_amounts = self.bot.config.get("legacy_system", {}).get(
                            "amounts", {}
                        )
                        if original_amount in legacy_amounts:
                            converted_amount = legacy_amounts[original_amount]
                            # Find role that matches the converted amount
                            for role_config in self.bot.config["premium_roles"]:
                                role_price = role_config["price"]
                                rounded_price = role_price + 1
                                if converted_amount in [role_price, rounded_price]:
                                    target_role_for_original = role_config["name"]
                                    break

                    if target_role_for_original:
                        target_role_priority = PREMIUM_PRIORITY.get(
                            target_role_for_original, 0
                        )

                        # If user has higher role, add to wallet
                        if highest_role_priority > target_role_priority:
                            # User has higher role than what they're trying to buy with original amount
                            # Add original amount to wallet and don't process legacy conversion
                            await MemberQueries.add_to_wallet_balance(
                                session, member.id, original_amount
                            )
                            await session.flush()

                            # Remove mute roles regardless
                            if self.role_manager:
                                await self.role_manager.remove_mute_roles(member)

                            embed = discord.Embed(
                                title="Doładowanie konta",
                                description=f"Posiadasz już wyższą rolę ({highest_role_name}). "
                                f"Kwota {original_amount}{CURRENCY_UNIT} została dodana do Twojego portfela.",
                                color=discord.Color.blue(),
                            )
                            embed.set_image(url=self.bot.config["gifs"]["donation"])

                            view = discord.ui.View()
                            view.add_item(
                                BuyRoleButton(
                                    bot=self.bot,
                                    member=member,
                                    role_name=highest_role_name,
                                    style=discord.ButtonStyle.success,
                                    label="Kup rangę",
                                    emoji=self.bot.config.get("emojis", {}).get(
                                        "mastercard", "💳"
                                    ),
                                )
                            )
                            view.add_item(
                                discord.ui.Button(
                                    label="Doładuj konto",
                                    style=discord.ButtonStyle.link,
                                    url=self.bot.config["donate_url"],
                                )
                            )

                            message = await channel.send(
                                content=f"{member.mention}", embed=embed, view=view
                            )
                            if owner:
                                await message.reply(f"{owner.mention}")
                            return

                        # If user has equal role, allow normal processing (role extension)
                        # This will handle cases like user with zG100 paying 25 -> legacy -> zG100 (should extend)
                        elif highest_role_priority == target_role_priority:
                            # Allow normal processing for same role extension
                            pass

                        # If user has lower role, check if this is a legacy conversion that shouldn't happen
                        elif highest_role_priority < target_role_priority:
                            # This is a potential upgrade, but check if it's through legacy conversion
                            # If original amount was converted by legacy system, it's not a real upgrade
                            if self.bot.config.get("legacy_system", {}).get(
                                "enabled", False
                            ):
                                legacy_amounts = self.bot.config.get(
                                    "legacy_system", {}
                                ).get("amounts", {})
                                if original_amount in legacy_amounts:
                                    # This is a legacy conversion - user didn't pay enough for real upgrade
                                    # Add original amount to wallet instead
                                    await MemberQueries.add_to_wallet_balance(
                                        session, member.id, original_amount
                                    )
                                    await session.flush()

                                    # Remove mute roles regardless
                                    if self.role_manager:
                                        await self.role_manager.remove_mute_roles(member)

                                    embed = discord.Embed(
                                        title="Doładowanie konta",
                                        description=f"Kwota {original_amount}{CURRENCY_UNIT} została dodana do Twojego portfela. "
                                        f"Aby kupić rolę {target_role_for_original}, potrzebujesz więcej środków.",
                                        color=discord.Color.blue(),
                                    )
                                    embed.set_image(
                                        url=self.bot.config["gifs"]["donation"]
                                    )

                                    view = discord.ui.View()
                                    view.add_item(
                                        BuyRoleButton(
                                            bot=self.bot,
                                            member=member,
                                            role_name=target_role_for_original,
                                            style=discord.ButtonStyle.success,
                                            label="Kup rangę",
                                            emoji=self.bot.config.get("emojis", {}).get(
                                                "mastercard", "💳"
                                            ),
                                        )
                                    )
                                    view.add_item(
                                        discord.ui.Button(
                                            label="Doładuj konto",
                                            style=discord.ButtonStyle.link,
                                            url=self.bot.config["donate_url"],
                                        )
                                    )

                                    message = await channel.send(
                                        content=f"{member.mention}",
                                        embed=embed,
                                        view=view,
                                    )
                                    if owner:
                                        await message.reply(f"{owner.mention}")
                                    return

                # Initialize embed variables
                embed = None
                role_name = None
                amount_to_add = (
                    final_amount  # Default to adding full amount if no role is found
                )

                # If amount >= 15, assign temporary roles based on original amount
                if original_amount >= 15:
                    await self.role_manager.assign_temporary_roles(
                        session, member, original_amount
                    )
                    await session.flush()

                # Try to find matching premium role
                for role_config in self.bot.config["premium_roles"]:
                    role_name = role_config["name"]
                    role_price = role_config["price"]
                    rounded_price = role_price + 1

                    if final_amount in [role_price, rounded_price]:
                        try:
                            # Use PremiumRoleManager to handle role assignment/extension
                            (
                                embed,
                                refund,
                                add_to_wallet,
                            ) = await self.role_manager.assign_or_extend_premium_role(
                                session=session,
                                member=member,
                                role_name=role_name,
                                amount=final_amount,
                                duration_days=30,
                                source="payment",
                            )
                            await session.flush()

                            # Remove mute roles regardless of the role assignment result
                            if self.role_manager:
                                await self.role_manager.remove_mute_roles(member)

                            # Handle wallet balance - only add if not explicitly set to False
                            if add_to_wallet is not False:
                                amount_to_add = final_amount
                                if (
                                    add_to_wallet is None
                                ):  # Default behavior - add remainder
                                    amount_to_add = final_amount - role_price

                                if amount_to_add > 0:
                                    await MemberQueries.add_to_wallet_balance(
                                        session, member.id, amount_to_add
                                    )
                                    await session.flush()
                            break
                        except Exception as e:
                            logger.error(
                                f"Error processing role assignment: {str(e)}",
                                exc_info=True,
                            )
                            raise

                # Jeśli nie znaleziono pasującej roli lub użytkownik ma wyższą rolę, dodaj całą kwotę do portfela
                if amount_to_add == final_amount:
                    try:
                        await MemberQueries.add_to_wallet_balance(
                            session, member.id, amount_to_add
                        )
                        await session.flush()
                        # Remove mute roles even if no role was purchased
                        if self.role_manager:
                            await self.role_manager.remove_mute_roles(member)
                    except Exception as e:
                        logger.error(f"Error adding balance to wallet: {str(e)}")
                        raise

                # If no premium role was found or processed
                if not embed:
                    embed = discord.Embed(
                        title="Gratulacje!",
                        description=f"Twoje konto zostało pomyślnie zasilone {amount_to_add}{CURRENCY_UNIT}!\nMożesz teraz kupić rangę w sklepie(unmute gratis!), klikając przycisk poniżej.",
                        color=discord.Color.green(),
                    )

                # Add image and send message
                embed.set_image(url=self.bot.config["gifs"]["donation"])

                view = discord.ui.View()
                view.add_item(
                    BuyRoleButton(
                        bot=self.bot,
                        member=member,
                        role_name=role_name,
                        style=discord.ButtonStyle.success,
                        label="Kup rangę",
                        emoji=self.bot.config.get("emojis", {}).get("mastercard", "💳"),
                    )
                )
                view.add_item(
                    discord.ui.Button(
                        label="Doładuj konto",
                        style=discord.ButtonStyle.link,
                        url=self.bot.config["donate_url"],
                    )
                )

                message = await channel.send(
                    content=f"{member.mention}", embed=embed, view=view
                )
                if owner:
                    await message.reply(f"{owner.mention}")

            except Exception as e:
                logger.error(f"Error in handle_payment: {str(e)}")
                raise


async def setup(bot: commands.Bot):
    """Setup function for the payment event cog"""
    await bot.add_cog(OnPaymentEvent(bot))
