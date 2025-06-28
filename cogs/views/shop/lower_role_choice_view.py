"""View for handling role extension vs buying new role choices."""
import discord

from datasources.queries import RoleQueries
from utils.premium_logic import PremiumRoleManager
from utils.refund import calculate_refund


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
                label=f"Przedłuż {current_role_name}",
                style=discord.ButtonStyle.primary,
                emoji="🔄",
                row=0,
            )
            extend_button.callback = self.extend_button_callback
            self.add_item(extend_button)

        buy_button = discord.ui.Button(
            label=f"{'Ulepsz do' if is_upgrade else 'Zmień na'} {new_role_name}",
            style=discord.ButtonStyle.success if is_upgrade else discord.ButtonStyle.secondary,
            emoji="⬆️" if is_upgrade else "🔀",
            row=0,
        )
        buy_button.callback = self.buy_button_callback
        self.add_item(buy_button)

        cancel_button = discord.ui.Button(label="Anuluj", style=discord.ButtonStyle.danger, emoji="❌", row=1)
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
