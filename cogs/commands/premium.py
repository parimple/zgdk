"""Premium commands cog for premium features like role colors and more."""

import io
import logging
from typing import Literal, Optional

import discord
from colour import Color
from discord import app_commands
from discord.ext import commands
import emoji
import emoji_data_python
from PIL import Image, ImageDraw, ImageFont
import httpx

from datasources.models import MemberRole
from datasources.models import Role as DBRole
from datasources.queries import MemberQueries
from utils.message_sender import MessageSender
from utils.permissions import is_zagadka_owner, is_admin
from utils.premium_checker import PremiumChecker

logger = logging.getLogger(__name__)


class PremiumCog(commands.Cog):
    """Commands related to premium features."""

    def __init__(self, bot):
        self.bot = bot
        self.message_sender = MessageSender()

        # Nazwa roli kolorowej z config
        self.color_role_name = self.bot.config.get("color", {}).get("role_name", "✎")
        # ID roli nad którą będą umieszczane role kolorowe
        self.base_role_id = self.bot.config.get("color", {}).get("base_role_id", 960665311772803184)

        # Konfiguracja teamów
        self.team_config = {
            "symbol": self.bot.config.get("team", {}).get("symbol", "☫"),
            "category_id": self.bot.config.get("team", {}).get("category_id", 1344105013357842522),
        }

        # Prefix z konfiguracji
        self.prefix = self.bot.config["prefix"]

    @commands.hybrid_command(aliases=["colour", "kolor"])
    @PremiumChecker.requires_premium_tier("color")
    @is_zagadka_owner()
    @app_commands.describe(color="Kolor roli (angielska nazwa, hex lub polska nazwa)")
    async def color(self, ctx, color: str):
        """Zmień kolor swojej roli."""
        # Logika zmiany koloru roli
        try:
            # Próba konwersji koloru na obiekt discord.Color
            discord_color = await self.parse_color(color)

            # Tworzenie/aktualizacja roli użytkownika
            await self.update_user_color_role(ctx.author, discord_color)

            # Tworzenie podstawowego opisu
            description = f"Zmieniono kolor twojej roli na `{color}`."

            # Dodanie informacji o planie premium
            # Sprawdzamy czy użytkownik jest na kanale głosowym
            channel = ctx.author.voice.channel if ctx.author.voice else None
            _, premium_text = self.message_sender._get_premium_text(ctx, channel)
            if premium_text:
                description = f"{description}\n{premium_text}"

            # Wysłanie potwierdzenia z kolorem wybranym przez użytkownika
            embed = self.message_sender._create_embed(
                description=description,
                color=discord_color,  # Używamy wybranego koloru zamiast "success"
                ctx=ctx,
            )
            await self.message_sender._send_embed(ctx, embed, reply=True)

        except ValueError as e:
            # Tworzenie opisu błędu - zamiana oryginalnego komunikatu błędu na wersję z backticks
            error_msg = str(e)
            if "Nieznany kolor:" in error_msg:
                # Wyciągamy nazwę koloru z komunikatu błędu
                color_start = error_msg.find("Nieznany kolor:") + len("Nieznany kolor:")
                color_end = error_msg.find(".", color_start)
                if color_end != -1:
                    color_name = error_msg[color_start:color_end].strip()
                    formatted_error = f"Nieznany kolor: `{color_name}`. Użyj nazwy angielskiej, polskiej lub kodu HEX (np. `#FF5733`)."
                    description = f"Błąd: {formatted_error}"
                else:
                    description = f"Błąd: {error_msg}"
            else:
                description = f"Błąd: {error_msg}"

            # Dodanie informacji o planie premium
            # Sprawdzamy czy użytkownik jest na kanale głosowym
            channel = ctx.author.voice.channel if ctx.author.voice else None
            _, premium_text = self.message_sender._get_premium_text(ctx, channel)
            if premium_text:
                description = f"{description}\n{premium_text}"

            embed = self.message_sender._create_embed(
                description=description, color="error", ctx=ctx
            )
            await self.message_sender._send_embed(ctx, embed, reply=True)

    async def parse_color(self, color_string: str) -> discord.Color:
        """Konwertuje string koloru na obiekt discord.Color."""
        # Polskie nazwy kolorów (nadal obsługujemy)
        polish_colors = {
            "czerwony": "red",
            "zielony": "green",
            "niebieski": "blue",
            "żółty": "yellow",
            "pomarańczowy": "orange",
            "fioletowy": "purple",
            "czarny": "black",
            "biały": "white",
            "różowy": "pink",
            "szary": "gray",
            "brązowy": "brown",
            "turkusowy": "cyan",
            "magenta": "magenta",
            "morski": "teal",
            "złoty": "gold",
        }

        # Sprawdź czy jest to polska nazwa koloru
        color_lower = color_string.lower()
        if color_lower in polish_colors:
            color_string = polish_colors[color_lower]

        # Próba konwersji przy użyciu biblioteki colour
        try:
            # Używamy biblioteki colour do parsowania nazwy/kodu koloru
            new_color = Color(color_string)
            hex_string = new_color.hex_l.replace("#", "")
            return discord.Color(int(hex_string, 16))
        except ValueError:
            # Jeśli to nie działa, spróbujmy jeszcze sprawdzić hex bez #
            try:
                if not color_string.startswith("#"):
                    # Próba interpretacji jako liczby szesnastkowej
                    hex_value = int(color_string, 16)
                    return discord.Color(hex_value)
            except ValueError:
                pass

            # Jeśli wszystkie próby zawiodły
            raise ValueError(
                f"Nieznany kolor: `{color_string}`. Użyj nazwy angielskiej, polskiej lub kodu HEX (np. `#FF5733`)."
            )

    async def update_user_color_role(self, member: discord.Member, color: discord.Color):
        """
        Creates or updates a user's color role.

        :param member: The member to update the role for
        :param color: The color to set for the role
        """
        # Use only the role name without adding the username
        role_name = self.color_role_name

        # Check if the user already has a color role
        existing_role = None
        for role in member.roles:
            if role.name == self.color_role_name:
                existing_role = role
                break

        if existing_role:
            # Update existing role
            await existing_role.edit(color=color)
        else:
            # Create a new role
            base_role = member.guild.get_role(self.base_role_id)
            if not base_role:
                raise ValueError(f"Base role with ID {self.base_role_id} not found")

            # Create the role
            new_role = await member.guild.create_role(
                name=role_name, color=color, reason=f"Color role for {member.display_name}"
            )

            # Move the role above the base role
            positions = {new_role: base_role.position + 1}
            await member.guild.edit_role_positions(positions=positions)

            # Assign the role to the user
            await member.add_roles(new_role)

    # Helper method for sending messages with premium plan information
    async def _send_premium_embed(self, ctx, title=None, description=None, color=None):
        """
        Creates and sends an embed with added premium plan information.

        :param ctx: Command context
        :param title: Embed title (optional)
        :param description: Embed description
        :param color: Embed color (optional)
        :return: Sent message
        """
        # Add premium plan information
        channel = ctx.author.voice.channel if ctx.author.voice else None
        mention, premium_text = self.message_sender._get_premium_text(ctx, channel)

        # Format description with bold text for important elements
        if description:
            # Add premium text to description if available
            if premium_text:
                full_description = f"{description}\n\n{premium_text}"
            else:
                full_description = description

            # Use MessageSender to send formatted message
            if color == 0xFF0000:  # Red color indicates error
                return await self.message_sender.send_error(ctx, full_description)
            else:
                return await self.message_sender.send_success(ctx, full_description)
        else:
            # In case there's no description but we need to send premium text
            if premium_text:
                return await self.message_sender.send_success(ctx, premium_text)
            return None

    @commands.group(invoke_without_command=True)
    @is_zagadka_owner()
    async def team(self, ctx):
        """Team (clan) management."""
        # Get the owner's team role
        team_role = await self._get_user_team_role(ctx.author)

        # Lista dostępnych komend
        available_commands = (
            f"**Dostępne komendy:**\n"
            f"• `{self.prefix}team create <nazwa>` - Utwórz nowy team\n"
            f"• `{self.prefix}team name <nazwa>` - Zmień nazwę swojego teamu\n"
            f"• `{self.prefix}team member add <@użytkownik>` - Dodaj członka do teamu\n"
            f"• `{self.prefix}team member remove <@użytkownik>` - Usuń członka z teamu\n"
            f"• `{self.prefix}team color <kolor>` - Ustaw kolor teamu (wymaga rangi zG500+)\n"
            f"• `{self.prefix}team emoji <emoji>` - Ustaw emoji teamu (wymaga rangi zG1000)"
        )

        if not team_role:
            # Create description
            description = (
                f"Nie masz teamu. Możesz go utworzyć za pomocą komendy:\n"
                f"`{self.prefix}team create <nazwa>`\n\n"
                f"Minimalne wymagania: posiadanie rangi **zG100**.\n\n"
                f"{available_commands}"
            )

            # Use the new method to send the message
            await self._send_premium_embed(ctx, description=description, color=0xFF0000)
            return

        # Get team information
        team_info = await self._get_team_info(team_role)

        # Prepare description with team info
        description = (
            f"**Team**: {self.team_config['symbol']} {team_role.name[2:]}\n\n"
            f"**Właściciel**: {team_info['owner'].mention}\n"
            f"**Liczba członków**: {len(team_info['members'])}/{team_info['max_members']}\n"
            f"**Kanał**: {team_info['channel'].mention}\n\n"
            f"**Członkowie**: {' '.join(m.mention for m in team_info['members'])}\n\n"
            f"{available_commands}"
        )

        # Use the new method to send the message
        await self._send_premium_embed(ctx, description=description)

    @team.command(name="create")
    @PremiumChecker.requires_specific_roles(["zG100", "zG500", "zG1000"])
    @app_commands.describe(
        name="Nazwa teamu (klanu)",
        color="Kolor teamu (opcjonalne, wymaga rangi zG500+)",
        emoji="Emoji teamu (opcjonalne, wymaga rangi zG1000)",
    )
    async def team_create(
        self, ctx, name: str, color: Optional[str] = None, emoji: Optional[str] = None
    ):
        """Create a new team (clan)."""
        # Check if the user already has a team
        existing_team = await self._get_user_team_role(ctx.author)
        if existing_team:
            return await self.message_sender.send_error(
                ctx, f"Masz już team `{existing_team.name}`. Musisz go najpierw usunąć."
            )

        # Check if the name is appropriate
        if len(name) < 3 or len(name) > 20:
            return await self.message_sender.send_error(
                ctx, "Nazwa teamu musi mieć od 3 do 20 znaków."
            )

        # Check if a team with this name already exists
        guild = ctx.guild
        team_symbol = self.team_config["symbol"]
        full_team_name = f"{team_symbol} {name}"

        existing_role = discord.utils.get(guild.roles, name=full_team_name)
        if existing_role:
            return await self.message_sender.send_error(
                ctx, f"Team o nazwie `{name}` już istnieje."
            )

        # Check color permissions (zG500 or zG1000)
        discord_color = None
        if color:
            has_color_permission = any(
                role.name in ["zG500", "zG1000"] for role in ctx.author.roles
            )
            if not has_color_permission:
                return await self.message_sender.send_error(
                    ctx, "Tylko użytkownicy z rangą zG500 lub wyższą mogą ustawić kolor teamu."
                )

            try:
                discord_color = await self.parse_color(color)
            except ValueError as e:
                return await self.message_sender.send_error(ctx, str(e))

        # Check emoji permissions (only zG1000)
        team_emoji = None
        if emoji:
            has_emoji_permission = any(role.name == "zG1000" for role in ctx.author.roles)
            if not has_emoji_permission:
                return await self.message_sender.send_error(
                    ctx, "Tylko użytkownicy z rangą zG1000 mogą ustawić emoji teamu."
                )

            # Check if it's a valid emoji
            if not emoji_validator(emoji):
                return await self.message_sender.send_error(
                    ctx, f"`{emoji}` nie jest poprawnym emoji."
                )

            team_emoji = emoji
            # Emoji will be added to the team name
            full_team_name = f"{team_symbol} {team_emoji} {name}"

        # Create team role
        try:
            # Create role
            team_role = await guild.create_role(
                name=full_team_name,
                color=discord_color or discord.Color.default(),
                mentionable=True,
                reason=f"Utworzenie teamu przez {ctx.author.display_name}",
            )

            # Assign role to user
            await ctx.author.add_roles(team_role)

            # Create text channel in appropriate category
            category = guild.get_channel(self.team_config["category_id"])
            if not category:
                logger.error(
                    f"Nie znaleziono kategorii teamów o ID {self.team_config['category_id']}"
                )
                category = None

            # Create channel permissions
            overwrites = {
                guild.default_role: discord.PermissionOverwrite(read_messages=False),
                team_role: discord.PermissionOverwrite(
                    read_messages=True,
                    send_messages=True,
                    embed_links=True,
                    attach_files=True,
                    read_message_history=True,
                ),
                ctx.author: discord.PermissionOverwrite(
                    read_messages=True,
                    send_messages=True,
                    manage_messages=True,
                    manage_channels=True,
                ),
            }

            # Create text channel
            channel_name = full_team_name.lower().replace(" ", "-")
            team_channel = await guild.create_text_channel(
                name=channel_name,
                category=category,
                topic=f"Team Channel for {full_team_name}. Owner: {ctx.author.id}",
                overwrites=overwrites,
                reason=f"Utworzenie kanału teamu przez {ctx.author.display_name}",
            )

            # Save team role to database
            await self._save_team_to_database(ctx.author.id, team_role.id)

            # Send success message
            description = (
                f"Utworzono team **{self.team_config['symbol']} {name}**!\n\n"
                f"• **Kanał**: {team_channel.mention}\n"
                f"• **Rola**: {team_role.mention}\n"
                f"• **Właściciel**: {ctx.author.mention}\n\n"
                f"Możesz zarządzać członkami teamu za pomocą komendy `{self.prefix}team member add/remove`."
            )

            # Use the new method to send the message
            await self._send_premium_embed(ctx, description=description)

        except Exception as e:
            logger.error(f"Błąd podczas tworzenia teamu: {str(e)}")
            await self.message_sender.send_error(
                ctx, f"Wystąpił błąd podczas tworzenia teamu: {str(e)}"
            )

    @team.command(name="name")
    @app_commands.describe(name="Nowa nazwa teamu")
    async def team_name(self, ctx, name: str):
        """Zmień nazwę swojego teamu."""
        # Sprawdź czy nazwa jest odpowiednia
        if len(name) < 3 or len(name) > 20:
            return await self.message_sender.send_error(
                ctx, "Nazwa teamu musi mieć od 3 do 20 znaków."
            )

        # Sprawdź czy użytkownik ma team
        team_role = await self._get_user_team_role(ctx.author)
        if not team_role:
            return await self.message_sender.send_error(
                ctx, "Nie masz żadnego teamu. Utwórz go najpierw za pomocą `,team create`."
            )

        # Sprawdź czy użytkownik jest właścicielem teamu
        is_owner = await self._is_team_owner(ctx.author.id, team_role.id)
        if not is_owner:
            return await self.message_sender.send_error(
                ctx, "Tylko właściciel teamu może zmienić nazwę teamu."
            )

        # Zachowanie emoji jeśli było wcześniej
        current_name_parts = team_role.name.split(" ")
        team_symbol = self.team_config["symbol"]
        team_emoji = None

        # Sprawdź czy team ma już emoji (format: ☫ 🔥 Nazwa)
        if len(current_name_parts) >= 3 and emoji_validator(current_name_parts[1]):
            team_emoji = current_name_parts[1]
            new_team_name = f"{team_symbol} {team_emoji} {name}"
        else:
            new_team_name = f"{team_symbol} {name}"

        # Sprawdź czy team o takiej nazwie już istnieje
        guild = ctx.guild
        existing_role = discord.utils.get(guild.roles, name=new_team_name)
        if existing_role and existing_role.id != team_role.id:
            return await self.message_sender.send_error(
                ctx, f"Team o nazwie `{name}` już istnieje."
            )

        try:
            # Aktualizuj rolę
            await team_role.edit(name=new_team_name)

            # Znajdź i zaktualizuj kanał
            team_channels = [c for c in ctx.guild.channels if isinstance(c, discord.TextChannel)]
            team_channel = None

            for channel in team_channels:
                if (
                    channel.topic
                    and str(ctx.author.id) in channel.topic
                    and "Team Channel" in channel.topic
                ):
                    team_channel = channel
                    break

            if team_channel:
                # Aktualizuj nazwę kanału
                channel_name = new_team_name.lower().replace(" ", "-")
                await team_channel.edit(name=channel_name)

                # Wyślij informację o sukcesie - bez dodawania symbolu ponownie
                description = f"Nazwa teamu została zmieniona na: **{new_team_name}**"

                # Użyj nowej metody do wysłania wiadomości
                await self._send_premium_embed(ctx, description=description)
            else:
                await self.message_sender.send_success(
                    ctx,
                    f"Zmieniono nazwę teamu na **{new_team_name}**, ale nie znaleziono kanału teamu.",
                )

        except Exception as e:
            logger.error(f"Błąd podczas zmiany nazwy teamu: {str(e)}")
            await self.message_sender.send_error(
                ctx, f"Wystąpił błąd podczas zmiany nazwy teamu: {str(e)}"
            )

    @team.group(name="member", invoke_without_command=True)
    async def team_member(self, ctx):
        """Zarządzaj członkami teamu."""
        if ctx.invoked_subcommand is None:
            description = (
                "**Dostępne komendy:**\n"
                f"`{self.prefix}team member add <@użytkownik>` - Dodaj członka do teamu\n"
                f"`{self.prefix}team member remove <@użytkownik>` - Usuń członka z teamu"
            )
            await self.message_sender.send_success(ctx, description)

    @team_member.command(name="add")
    @app_commands.describe(member="Użytkownik do dodania do teamu")
    async def team_member_add(self, ctx, member: discord.Member):
        """Dodaj członka do swojego teamu."""
        # Sprawdź czy użytkownik ma team
        team_role = await self._get_user_team_role(ctx.author)
        if not team_role:
            return await self.message_sender.send_error(
                ctx,
                f"Nie masz żadnego teamu. Utwórz go najpierw za pomocą `{self.prefix}team create`.",
            )

        # Sprawdź czy użytkownik jest właścicielem teamu
        is_owner = await self._is_team_owner(ctx.author.id, team_role.id)
        if not is_owner:
            return await self.message_sender.send_error(
                ctx, "Tylko właściciel teamu może dodawać członków."
            )

        # Sprawdź czy użytkownik nie próbuje dodać samego siebie
        if member.id == ctx.author.id:
            return await self.message_sender.send_error(
                ctx, "Nie możesz dodać siebie do teamu - jesteś już jego właścicielem."
            )

        # Sprawdź czy osoba już jest w teamie
        if team_role in member.roles:
            return await self.message_sender.send_error(
                ctx, f"{member.mention} już jest członkiem teamu **{team_role.name}**."
            )

        # Sprawdź czy osoba nie ma już innego teamu
        member_team = await self._get_user_team_role(member)
        if member_team:
            return await self.message_sender.send_error(
                ctx, f"{member.mention} jest już członkiem teamu **{member_team.name}**."
            )

        # Sprawdź limit członków na podstawie roli właściciela
        current_members = len([m for m in ctx.guild.members if team_role in m.roles])
        team_size_limit = 0

        # Znajdź najwyższą rangę premium użytkownika i jej limit
        for role_config in reversed(self.bot.config["premium_roles"]):
            if any(r.name == role_config["name"] for r in ctx.author.roles):
                team_size_limit = role_config.get(
                    "team_size", 10
                )  # Domyślnie 10 jeśli nie określono
                break

        if current_members >= team_size_limit:
            return await self.message_sender.send_error(
                ctx,
                f"Osiągnięto limit członków teamu ({current_members}/{team_size_limit}). "
                f"Aby zwiększyć limit, potrzebujesz wyższej rangi premium.",
            )

        try:
            # Dodaj rolę do użytkownika
            await member.add_roles(team_role)

            # Wyślij informację o sukcesie
            description = f"Dodano **{member.mention}** do teamu **{team_role.mention}**!"

            # Użyj nowej metody do wysłania wiadomości
            await self._send_premium_embed(ctx, description=description)

        except Exception as e:
            logger.error(f"Błąd podczas dodawania członka do teamu: {str(e)}")
            await self.message_sender.send_error(
                ctx, f"Wystąpił błąd podczas dodawania członka do teamu: {str(e)}"
            )

    @team_member.command(name="remove")
    @app_commands.describe(member="Użytkownik do usunięcia z teamu")
    async def team_member_remove(self, ctx, member: discord.Member):
        """Remove a member from your team."""
        # Check if the user has a team
        team_role = await self._get_user_team_role(ctx.author)
        if not team_role:
            return await self.message_sender.send_error(
                ctx, "Nie masz żadnego teamu. Utwórz go najpierw za pomocą `,team create`."
            )

        # Check if the user is the team owner
        is_owner = await self._is_team_owner(ctx.author.id, team_role.id)
        if not is_owner:
            return await self.message_sender.send_error(
                ctx, "Tylko właściciel teamu może usuwać członków."
            )

        # Check if the user is trying to remove themselves
        if member.id == ctx.author.id:
            return await self.message_sender.send_error(
                ctx,
                "Nie możesz usunąć siebie z teamu. Aby usunąć team, skontaktuj się z administracją.",
            )

        # Check if the person is in the team
        if team_role not in member.roles:
            return await self.message_sender.send_error(
                ctx, f"{member.mention} nie jest członkiem teamu **{team_role.name}**."
            )

        try:
            # Usuń rolę od użytkownika
            await member.remove_roles(team_role)

            # Wyślij informację o sukcesie
            description = f"Usunięto **{member.mention}** z teamu **{team_role.mention}**!"

            # Użyj nowej metody do wysłania wiadomości
            await self._send_premium_embed(ctx, description=description)

        except Exception as e:
            logger.error(f"Błąd podczas usuwania członka z teamu: {str(e)}")
            await self.message_sender.send_error(
                ctx, f"Wystąpił błąd podczas usuwania członka z teamu: {str(e)}"
            )

    @team.command(name="color")
    @app_commands.describe(color="Kolor teamu (angielska nazwa, hex lub polska nazwa)")
    async def team_color(self, ctx, color: str):
        """Change your team's color."""
        # Check color permissions (zG500 or zG1000)
        has_color_permission = any(role.name in ["zG500", "zG1000"] for role in ctx.author.roles)
        if not has_color_permission:
            # Użyj _send_premium_embed zamiast send_error, aby dodać informację o planach premium
            return await self._send_premium_embed(
                ctx,
                description="Tylko użytkownicy z rangą zG500 lub wyższą mogą ustawić kolor teamu.",
                color=0xFF0000,
            )

        # Check if the user has a team
        team_role = await self._get_user_team_role(ctx.author)
        if not team_role:
            # Użyj _send_premium_embed zamiast send_error, aby dodać informację o planach premium
            return await self._send_premium_embed(
                ctx,
                description="Nie masz żadnego teamu. Utwórz go najpierw za pomocą `,team create`.",
                color=0xFF0000,
            )

        # Check if the user is the team owner
        is_owner = await self._is_team_owner(ctx.author.id, team_role.id)
        if not is_owner:
            # Użyj _send_premium_embed zamiast send_error, aby dodać informację o planach premium
            return await self._send_premium_embed(
                ctx, description="Tylko właściciel teamu może zmienić jego kolor.", color=0xFF0000
            )

        try:
            # Próba konwersji koloru na obiekt discord.Color
            discord_color = await self.parse_color(color)

            # Aktualizuj kolor roli
            await team_role.edit(color=discord_color)

            # Wyślij informację o sukcesie
            description = f"Zmieniono kolor teamu **{team_role.mention}** na **`{color}`**."

            # Użyj nowej metody do wysłania wiadomości
            await self._send_premium_embed(ctx, description=description)

        except ValueError as e:
            # Użyj _send_premium_embed zamiast send_error, aby dodać informację o planach premium
            await self._send_premium_embed(ctx, description=str(e), color=0xFF0000)
        except Exception as e:
            logger.error(f"Błąd podczas zmiany koloru teamu: {str(e)}")
            # Użyj _send_premium_embed zamiast send_error, aby dodać informację o planach premium
            await self._send_premium_embed(
                ctx,
                description=f"Wystąpił błąd podczas zmiany koloru teamu: {str(e)}",
                color=0xFF0000,
            )

    @team.command(name="emoji")
    @app_commands.describe(emoji="Emoji teamu")
    async def team_emoji(self, ctx, emoji: str):
        """Set team emoji as role icon."""
        # Check if user has emoji permission (zG1000 only)
        has_emoji_permission = any(role.name == "zG1000" for role in ctx.author.roles)
        if not has_emoji_permission:
            return await self._send_premium_embed(
                ctx,
                description="Tylko użytkownicy z rangą zG1000 mogą ustawić emoji teamu.",
                color=0xFF0000,
            )

        # Check if it's a valid emoji
        if not emoji_validator(emoji):
            return await self._send_premium_embed(
                ctx, description=f"`{emoji}` nie jest poprawnym emoji.", color=0xFF0000
            )

        # Check if user has a team
        team_role = await self._get_user_team_role(ctx.author)
        if not team_role:
            return await self._send_premium_embed(
                ctx,
                description="Nie masz żadnego teamu. Utwórz go najpierw za pomocą `,team create`.",
                color=0xFF0000,
            )

        # Check if user is the team owner
        is_owner = await self._is_team_owner(ctx.author.id, team_role.id)
        if not is_owner:
            return await self._send_premium_embed(
                ctx, description="Tylko właściciel teamu może zmienić emoji teamu.", color=0xFF0000
            )
            
        # Check if server has the required boost level for role icons (Level 2)
        if ctx.guild.premium_tier < 2:
            return await self._send_premium_embed(
                ctx, 
                description="Serwer musi mieć minimum 7 boostów (Poziom 2), aby można było ustawić ikony ról.", 
                color=0xFF0000
            )

        try:
            # Get current name and team symbol
            current_name_parts = team_role.name.split(" ")
            team_symbol = self.team_config["symbol"]
            
            # Clean up current name if it has emoji in it
            if len(current_name_parts) >= 3 and emoji_validator(current_name_parts[1]):
                new_name = f"{team_symbol} {' '.join(current_name_parts[2:])}"
            else:
                new_name = team_role.name
                
            # Convert emoji to role icon format
            icon_bytes = await emoji_to_icon(emoji)
            
            # Update role with new icon and cleaned name
            await team_role.edit(name=new_name, display_icon=icon_bytes)

            # Update channel name if exists
            team_channels = [c for c in ctx.guild.channels if isinstance(c, discord.TextChannel)]
            team_channel = None

            for channel in team_channels:
                if (
                    channel.topic
                    and str(ctx.author.id) in channel.topic
                    and "Team Channel" in channel.topic
                ):
                    team_channel = channel
                    break

            if team_channel:
                # Update channel name but remove emoji from name
                channel_name = new_name.lower().replace(" ", "-")
                await team_channel.edit(name=channel_name)

            # Send success message
            description = f"Ustawiono emoji {emoji} jako ikonę teamu **{team_role.mention}**."
            await self._send_premium_embed(ctx, description=description)

        except discord.Forbidden:
            await self._send_premium_embed(
                ctx,
                description="Bot nie ma wystarczających uprawnień, aby zmienić ikonę roli.",
                color=0xFF0000,
            )
        except discord.HTTPException as e:
            logger.error(f"HTTP error during team emoji update: {str(e)}")
            await self._send_premium_embed(
                ctx,
                description=f"Wystąpił błąd podczas zmiany emoji teamu: {str(e)}",
                color=0xFF0000,
            )
        except Exception as e:
            logger.error(f"Error during team emoji update: {str(e)}")
            await self._send_premium_embed(
                ctx,
                description=f"Wystąpił błąd podczas zmiany emoji teamu: {str(e)}",
                color=0xFF0000,
            )

    async def _get_user_team_role(self, member: discord.Member):
        """
        Get the team role for a user.

        :param member: The member to find the team role for
        :return: The team role or None if not found
        """
        # Get team roles that follow the pattern "☫ <name>"
        team_symbol = self.team_config["symbol"]
        team_roles = [
            role
            for role in member.roles
            if role.name.startswith(team_symbol)
            and len(role.name) > len(team_symbol)
            and role.name[len(team_symbol)] == " "
        ]

        # Return the first team role found (there should only be one)
        return team_roles[0] if team_roles else None

    async def _is_team_owner(self, user_id: int, role_id: int):
        """
        Check if a user is the owner of a team.

        :param user_id: The user ID to check
        :param role_id: The team role ID
        :return: True if the user is the owner, False otherwise
        """
        async with self.bot.get_db() as session:
            role = await session.get(DBRole, role_id)
            return role and role.role_type == "team" and int(role.name) == user_id

    async def _save_team_to_database(self, owner_id: int, role_id: int):
        """
        Save team information to the database.

        :param owner_id: The ID of the team owner
        :param role_id: The ID of the team role
        """
        async with self.bot.get_db() as session:
            role = DBRole(
                id=role_id,
                name=str(owner_id),
                role_type="team",
            )
            session.add(role)
            await session.commit()

    async def _get_team_info(self, team_role: discord.Role):
        """
        Get information about a team.

        :param team_role: The team role to get information for
        :return: A dictionary containing team information
        """
        guild = team_role.guild

        # Find the team owner
        async with self.bot.get_db() as session:
            role = await session.get(DBRole, team_role.id)
            owner_id = int(role.name) if role and role.role_type == "team" else None

            # Get the member object
            owner = guild.get_member(owner_id) if owner_id else None

            # Find team members
            members = [member for member in guild.members if team_role in member.roles]

            # Find the team channel
            team_channel = None
            for channel in guild.channels:
                if (
                    isinstance(channel, discord.TextChannel)
                    and channel.topic
                    and str(owner_id) in channel.topic
                    and "Team Channel" in channel.topic
                ):
                    team_channel = channel
                    break

            # Get maximum team size based on owner's roles
            max_members = 10
            if owner:
                for role_config in reversed(self.bot.config["premium_roles"]):
                    if any(r.name == role_config["name"] for r in owner.roles):
                        max_members = role_config.get("team_size", 10)
                        break

            return {
                "owner": owner,
                "members": members,
                "channel": team_channel,
                "max_members": max_members,
            }


# Helper functions
def emoji_validator(emoji_str: str) -> bool:
    """
    Check if a string is a single emoji.

    :param emoji_str: The string to check
    :return: True if the string is a single emoji, False otherwise
    """
    if not emoji_str:
        return False

    # Check if it's a standard Unicode emoji using the emoji library
    if emoji.is_emoji(emoji_str):
        return True
    
    # Check for Discord custom emoji format: <:name:id> or <a:name:id>
    if emoji_str.startswith("<") and emoji_str.endswith(">"):
        parts = emoji_str.strip("<>").split(":")
        return len(parts) >= 2 and all(part for part in parts)
    
    return False


async def emoji_to_icon(emoji_str: str) -> bytes:
    """
    Convert an emoji to an image format suitable for Discord role icon.
    
    :param emoji_str: The emoji string to convert
    :return: Bytes representation of the image
    """
    # Check if it's a custom Discord emoji
    if emoji_str.startswith("<") and emoji_str.endswith(">"):
        # Custom emoji format: <:name:id> or <a:name:id>
        emoji_id = emoji_str.split(":")[-1].replace(">", "")
        is_animated = emoji_str.startswith("<a:")
        
        # Format the URL
        ext = "gif" if is_animated else "png"
        emoji_url = f"https://cdn.discordapp.com/emojis/{emoji_id}.{ext}"
        
        # Use httpx to get the emoji image
        async with httpx.AsyncClient() as client:
            response = await client.get(emoji_url)
            if response.status_code == 200:
                return response.content
    
    # For standard Unicode emojis, create an image
    try:
        # Find the emoji using emoji_data_python's built-in functions
        found_emoji = None
        
        # Try finding by exact match first
        for e in emoji_data_python.emoji_data:
            if e.char == emoji_str:
                found_emoji = e
                break
        
        # If no exact match, try using the emoji library
        if not found_emoji and emoji.is_emoji(emoji_str):
            emoji_str = emoji_str  # Use as is
        
        # Create a blank image with transparent background
        img = Image.new('RGBA', (128, 128), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        
        # Try to load a font that supports emoji
        try:
            # Try system fonts that might support emoji
            font = ImageFont.truetype("NotoColorEmoji.ttf", 109)
        except IOError:
            # Fallback to default font
            font = ImageFont.load_default()
        
        # Draw the emoji centered in the image
        draw.text((64, 64), emoji_str, font=font, fill=(0, 0, 0, 255), anchor="mm")
        
        # Save to bytes
        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        buffer.seek(0)
        return buffer.read()
    except Exception as e:
        # In case of error, return a default image
        logger.error(f"Error converting emoji to image: {str(e)}")
        img = Image.new('RGBA', (128, 128), (255, 0, 0, 255))  # Red square as fallback
        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        buffer.seek(0)
        return buffer.read()


async def setup(bot):
    """This function is called when the cog is loaded."""
    await bot.add_cog(PremiumCog(bot))
