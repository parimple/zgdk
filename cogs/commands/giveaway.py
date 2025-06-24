"""Giveaway commands for randomly selecting messages from a channel."""

import logging
import random
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

from utils.message_sender import MessageSender

logger = logging.getLogger(__name__)


class GiveawayCog(commands.Cog):
    """Cog for giveaway-related commands."""

    def __init__(self, bot):
        self.bot = bot
        self.message_sender = MessageSender()

    @commands.hybrid_command(aliases=["gws"])
    @commands.has_permissions(administrator=True)
    @discord.app_commands.describe(
        winners_count="Liczba wygranych do wylosowania",
        channel="Kanał z którego losować wiadomości (opcjonalnie)",
    )
    async def giveawayss(
        self,
        ctx,
        winners_count: int,
        channel: Optional[discord.TextChannel] = None,
    ):
        """Losuj określoną liczbę wiadomości z kanału."""
        if winners_count < 1:
            await self.message_sender.send_error(
                ctx, "Liczba wygranych musi być większa od 0!"
            )
            return

        # Użyj bieżącego kanału jeśli nie podano innego
        target_channel = channel or ctx.channel

        # Zbierz wszystkie wiadomości z kanału
        messages = []
        async for message in target_channel.history(limit=None):
            if (
                message.author.bot and not message.webhook_id
            ):  # Pomijamy boty, ale nie webhooki
                continue
            messages.append(message)

        if not messages:
            await self.message_sender.send_error(ctx, "Brak wiadomości do wylosowania!")
            return

        # Losuj wiadomości
        winners = []
        used_authors = set()  # Zbiór ID autorów, którzy już zostali wylosowani
        remaining_messages = messages.copy()

        while len(winners) < winners_count and remaining_messages:
            message = random.choice(remaining_messages)
            remaining_messages.remove(message)

            # Dla wiadomości od webhooków nie sprawdzamy unikalności autora
            if not message.webhook_id:
                # Jeśli autor już wygrał, pomiń tę wiadomość
                if message.author.id in used_authors:
                    continue
                used_authors.add(message.author.id)

            winners.append(message)

            # Jeśli nie ma już wystarczającej liczby wiadomości, przerwij
            if len(remaining_messages) < (winners_count - len(winners)):
                break

        # Przygotuj i wyślij wyniki
        if not winners:
            await self.message_sender.send_error(
                ctx, "Nie udało się wylosować żadnej wiadomości!"
            )
            return

        # Wyślij wyniki
        await self.message_sender.send_giveaway_results(
            ctx, winners, target_channel, winners_count
        )

    @commands.hybrid_command(
        name="giveawayr", description="Losuje użytkownika z wybranych ról."
    )
    @commands.has_role("✪")
    @discord.app_commands.describe(
        role1="Pierwsza rola do losowania (wymagana)",
        role2="Druga rola do losowania (opcjonalna)",
        role3="Trzecia rola do losowania (opcjonalna)",
        mode="Tryb sprawdzania ról: 'or' (dowolna z ról) lub 'and' (wszystkie role)",
    )
    async def giveawayr(
        self,
        ctx: commands.Context,
        role1: str,
        role2: str = None,
        role3: str = None,
        mode: str = "and",
    ):
        """Losuje użytkownika z wybranych ról.

        Przykład użycia:
        ,giveawayr "Nazwa Roli 1" "Nazwa Roli 2" "Nazwa Roli 3" or  # Losuje użytkownika z dowolną z tych ról
        ,giveawayr "Nazwa Roli 1" "Nazwa Roli 2"                    # Losuje użytkownika z obiema rolami (domyślnie and)
        """
        # Sprawdź czy użytkownik ma rolę administratora
        if not discord.utils.get(
            ctx.author.roles, id=self.bot.config["admin_roles"]["admin"]
        ):
            await ctx.send("Ta komenda jest dostępna tylko dla administratorów.")
            return

        # Konwertuj nazwy ról na obiekty ról
        roles = []
        for role_name in [role1, role2, role3]:
            if role_name:
                # Dla slash command, role_name będzie już obiektem Role
                if isinstance(role_name, discord.Role):
                    roles.append(role_name)
                else:
                    # Dla wersji z prefixem, szukamy roli po nazwie
                    role = discord.utils.get(ctx.guild.roles, name=role_name)
                    if role:
                        roles.append(role)
                    else:
                        await ctx.send(f"Nie znaleziono roli o nazwie: {role_name}")
                        return

        # Sprawdź poprawność trybu
        mode = mode.lower()
        if mode not in ["or", "and"]:
            mode = "and"  # Domyślnie używamy AND jeśli podano nieprawidłowy tryb

        # Zbierz wszystkich członków serwera
        eligible_members = []
        for member in ctx.guild.members:
            if not member.bot:  # Pomijamy boty
                if mode == "or":
                    # Tryb OR - wystarczy mieć jedną z ról
                    if any(role in member.roles for role in roles):
                        eligible_members.append(member)
                else:
                    # Tryb AND - musi mieć wszystkie role
                    if all(role in member.roles for role in roles):
                        eligible_members.append(member)

        if not eligible_members:
            role_names = ", ".join(f"'{role.name}'" for role in roles)
            await ctx.send(
                f"Nie znaleziono żadnych użytkowników z wymaganymi rolami ({role_names}) "
                f"w trybie {mode.upper()}."
            )
            return

        # Wylosuj zwycięzcę
        winner = random.choice(eligible_members)

        # Przygotuj wiadomość z informacją o rolach (bez pingowania)
        role_info = " ".join(f"'{role.name}'" for role in roles)
        mode_info = "dowolnej z" if mode == "or" else "wszystkich"

        await ctx.send(
            f"🎉 Wylosowano zwycięzcę spośród użytkowników z {mode_info} ról: {role_info}\n"
            f"Zwycięzca: {winner.mention}\n"
            f"Liczba uprawnionych użytkowników: {len(eligible_members)}"
        )

    # Osobna wersja dla slash command
    @giveawayr.app_command.error
    async def giveawayr_app_command_error(
        self, interaction: discord.Interaction, error: app_commands.CommandInvokeError
    ):
        # Konwertuj parametry z discord.Role na str dla wersji z prefixem
        if isinstance(error.original, commands.CommandInvokeError):
            ctx = await self.bot.get_context(interaction)
            roles = []
            for param in interaction.namespace:
                if isinstance(param, discord.Role):
                    roles.append(param.name)
                else:
                    roles.append(param)
            await self.giveawayr(ctx, *roles)


async def setup(bot):
    """Add the cog to the bot."""
    await bot.add_cog(GiveawayCog(bot))
