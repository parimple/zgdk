"""Confirm view for role purchase confirmation."""
import discord


class ConfirmView(discord.ui.View):
    """View for confirming role purchases."""

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
