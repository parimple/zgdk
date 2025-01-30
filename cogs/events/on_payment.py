"""
On Payments Event Cog
"""

import asyncio
import logging
import os
from datetime import timedelta

import discord
from discord.ext import commands, tasks

from datasources.queries import RoleQueries
from utils.currency import CURRENCY_UNIT
from utils.premium import PremiumManager, TipplyDataProvider

logger = logging.getLogger(__name__)

TOKEN = os.environ.get("TIPO_API_TOKEN")


class OnPaymentEvent(commands.Cog):
    """Class for the Tipo Payments Cog"""

    def __init__(self, bot):
        self.bot = bot
        self.guild = bot.guild
        self.premium_manager = PremiumManager(bot)
        self.data_provider = TipplyDataProvider(bot.get_db)
        self.check_payments.start()  # pylint: disable=no-member

    async def cog_unload(self):
        """Cog Unload"""
        self.check_payments.cancel()  # pylint: disable=no-member

    @tasks.loop(minutes=1.0)
    async def check_payments(self):
        """Check Payments"""
        # logger.info("Checking for new payments")
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
        # finally:
        #     logger.info("Finished checking for payments")

    @check_payments.before_loop
    async def before_check_payments(self):
        """Before Check Payments"""
        await self.bot.wait_until_ready()
        if self.guild is None:
            logger.info("Guild is not set, fetching from bot")
            self.guild = self.bot.get_guild(self.bot.guild_id)

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

        logger.info(
            f"Handling payment for {member.display_name} with amount {payment_data.amount}G"
        )
        await self.assign_temporary_roles(session, member, payment_data.amount)
        await self.remove_mute_roles(member)

        owner_id = self.bot.config.get("owner_id")
        owner = self.guild.get_member(owner_id)

        embed = discord.Embed(
            title="Gratulacje!",
            description=f"Twoje konto zostało pomyślnie zasilone {payment_data.amount}{CURRENCY_UNIT}!",
            color=discord.Color.green(),
        )
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

    async def assign_temporary_roles(self, session, member, amount_g):
        """Assign all applicable temporary roles based on donation amount"""
        # Sprawdź i usuń nieaktualne role z bazy danych
        premium_roles = await RoleQueries.get_member_premium_roles(session, member.id)
        for member_role, role in premium_roles:
            if role.id not in [r.id for r in member.roles]:
                # Jeśli rola jest w bazie, ale nie ma jej na Discord, usuń z bazy
                await session.delete(member_role)
        await session.flush()

        # Create a set of role IDs the member currently has
        member_role_ids = {role.id for role in member.roles}

        # Log the member's roles before assignment for debugging
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

        delay_after_roles = ["$4", "$8"]
        last_assigned_role = None

        for amount, role_name in roles_tiers:
            logger.info("Checking if %d >= %d for role %s", amount_g, amount, role_name)
            if amount_g >= amount:
                role = discord.utils.get(self.guild.roles, name=role_name)
                if role:
                    logger.info("Found role %s for %s", role_name, member.display_name)
                    try:
                        await RoleQueries.add_or_update_role_to_member(
                            session, member.id, role.id, timedelta(days=30)
                        )
                        if role.id not in member_role_ids:
                            try:
                                await member.add_roles(role)
                                logger.info(
                                    "Assigned role %s to member %s", role_name, member.display_name
                                )
                            except Exception as e:
                                logger.error(
                                    f"Error adding role {role_name} to member {member.display_name}: {str(e)}"
                                )
                        else:
                            logger.info(
                                "Updated expiration for role %s of member %s",
                                role_name,
                                member.display_name,
                            )
                        last_assigned_role = role_name
                    except Exception as e:
                        logger.error(
                            f"Error assigning/updating role {role_name} to member {member.display_name}: {str(e)}"
                        )
                else:
                    logger.error("Role %s not found in the guild", role_name)
            else:
                logger.info("Amount %d is not enough for role %s", amount_g, role_name)

            if last_assigned_role in delay_after_roles:
                await self.delay_before_next_role()
                last_assigned_role = None

    async def delay_before_next_role(self):
        """Wait for 5 seconds before assigning the next roles."""
        logger.info("Waiting 5 seconds before assigning the next roles.")
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
