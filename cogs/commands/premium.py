"""Premium commands cog for premium features like role colors and more."""

import io
import logging
from datetime import datetime, timezone
from typing import Literal, Optional

import discord
import emoji
import emoji_data_python
import httpx
from colour import Color
from discord import app_commands
from discord.ext import commands
from PIL import Image, ImageDraw, ImageFont
from sqlalchemy import select

from datasources.models import MemberRole
from datasources.models import Role as DBRole
from datasources.queries import MemberQueries
from utils.message_sender import MessageSender
from utils.permissions import is_admin, is_zagadka_owner
from utils.premium_checker import PremiumChecker
from utils.team_manager import TeamManager

logger = logging.getLogger(__name__)


class PremiumCog(commands.Cog):
    """Commands related to premium features."""

    def __init__(self, bot):
        """Initialize the PremiumCog."""
        self.bot = bot
        self.prefix = self.bot.command_prefix[0] if self.bot.command_prefix else ","
        self.team_config = self.bot.config.get("team", {})
        # ID roli bazowej, nad którą będą umieszczane role teamów
        self.team_base_role_id = self.team_config.get(
            "base_role_id", 0
        )  # Domyślnie 0, jeśli nie skonfigurowano
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
        available_commands = f"**Dostępne komendy:**\n" f"{self._get_team_commands_description()}"

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
        """
        Create a new team (clan).
        """
        # 1. Sprawdź, czy użytkownik jest już właścicielem teamu w bazie danych
        is_already_owner = False
        existing_team = None
        existing_team_role = None
        existing_team_channel = None

        async with self.bot.get_db() as session:
            # Szukaj roli typu "team" z ID użytkownika jako właścicielem
            result = await session.execute(
                select(DBRole).where(
                    (DBRole.role_type == "team") & (DBRole.name == str(ctx.author.id))
                )
            )
            existing_team = result.scalar_one_or_none()
            if existing_team:
                is_already_owner = True
                existing_team_role = ctx.guild.get_role(existing_team.id)

        # Dodatkowe sprawdzenie kanałów - nawet jeśli nie ma roli w bazie, sprawdź czy są kanały
        if not is_already_owner:
            # Szukaj kanałów, które mogą należeć do teamu tego użytkownika
            for channel in ctx.guild.channels:
                if hasattr(channel, "topic") and channel.topic:
                    topic_parts = channel.topic.split()
                    # Sprawdź czy topic ma format id_właściciela id_roli
                    if len(topic_parts) >= 2 and topic_parts[0] == str(ctx.author.id):
                        is_already_owner = True
                        existing_team_channel = channel
                        role_id = (
                            int(topic_parts[1])
                            if len(topic_parts) > 1 and topic_parts[1].isdigit()
                            else None
                        )
                        if role_id:
                            existing_team_role = ctx.guild.get_role(role_id)
                        break
                    # Dla kompatybilności ze starym formatem
                    elif "Team Channel" in channel.topic and str(ctx.author.id) in channel.topic:
                        is_already_owner = True
                        existing_team_channel = channel
                        break

        # Jeśli już jest właścicielem, wyświetl błąd
        if is_already_owner:
            team_mention = "unknown team"
            if existing_team_role:
                team_mention = existing_team_role.mention
            elif existing_team:
                team_mention = f"ID: {existing_team.id}"
            elif existing_team_channel:
                team_mention = f"kanał {existing_team_channel.mention}"

            logger.warning(
                f"User {ctx.author.display_name} tried to create a team but already owns {team_mention}"
            )

            return await self._send_premium_embed(
                ctx,
                description=f"Jesteś już właścicielem teamu **{team_mention}**. Nie możesz stworzyć drugiego teamu.",
                color=0xFF0000,
            )

        # 2. Sprawdź, czy nazwa nie jest zajęta
        team_name = f"{self.team_config['symbol']} {name}"
        if discord.utils.get(ctx.guild.roles, name=team_name):
            return await self._send_premium_embed(
                ctx,
                description=f"Team o nazwie **{name}** już istnieje. Wybierz inną nazwę.",
                color=0xFF0000,
            )

        try:
            # 3. Tworzenie roli teamu
            team_role = await ctx.guild.create_role(name=team_name, mentionable=True)

            # 3.1. Pozycjonowanie roli teamu - nad rolą bazową, podobnie jak w update_user_color_role
            base_role = ctx.guild.get_role(self.team_base_role_id)
            if base_role:
                # Umieszczamy rolę teamu ponad rolą bazową
                positions = {team_role: base_role.position + 1}
                await ctx.guild.edit_role_positions(positions=positions)
                logger.info(
                    f"Team role {team_role.name} positioned above base role {base_role.name}"
                )
            else:
                # Jeśli nie znaleziono roli bazowej, spróbuj fallback do poprzedniej implementacji
                highest_assign_role = None
                for role in reversed(ctx.guild.roles):
                    if role.permissions.manage_roles and not role.managed:
                        highest_assign_role = role
                        break

                if highest_assign_role:
                    positions = {team_role: highest_assign_role.position - 1}
                    await ctx.guild.edit_role_positions(positions=positions)
                    logger.info(
                        f"Team role {team_role.name} positioned under {highest_assign_role.name} (fallback)"
                    )

            # 4. Zapisz informacje o teamie w bazie danych
            await self._save_team_to_database(ctx.author.id, team_role.id)

            # 5. Przydziel rolę właścicielowi
            await ctx.author.add_roles(team_role)

            # 6. Ustaw kolor jeśli został podany i użytkownik ma rangę zG500+
            if color:
                has_color_permission = any(
                    role.name in ["zG500", "zG1000"] for role in ctx.author.roles
                )
                if not has_color_permission:
                    await self._send_premium_embed(
                        ctx,
                        description="Kolor teamu dostępny tylko dla rang zG500+. Kolor nie został ustawiony.",
                        color=0xFF0000,
                    )
                else:
                    try:
                        discord_color = await self.parse_color(color)
                        await team_role.edit(color=discord_color)
                    except ValueError as e:
                        await self._send_premium_embed(ctx, description=str(e), color=0xFF0000)

            # 7. Ustaw emoji jeśli został podany i użytkownik ma rangę zG1000
            if emoji:
                has_emoji_permission = any(role.name == "zG1000" for role in ctx.author.roles)
                if not has_emoji_permission:
                    await self._send_premium_embed(
                        ctx,
                        description="Emoji teamu dostępny tylko dla rang zG1000. Emoji nie zostało ustawione.",
                        color=0xFF0000,
                    )
                else:
                    # Check if it's a valid emoji
                    if not emoji_validator(emoji):
                        await self._send_premium_embed(
                            ctx,
                            description=f"`{emoji}` nie jest poprawnym formatem emoji serwera. Aby użyć emoji z serwera, kliknij prawym przyciskiem myszy na emoji i wybierz 'Kopiuj odnośnik do emoji', a następnie wklej go w komendzie.",
                            color=0xFF0000,
                        )
                    else:
                        await team_role.edit(display_icon=await emoji_to_icon(emoji))

            # 8. Ustaw kanał teamu
            category = ctx.guild.get_channel(self.team_config["category_id"])
            if not category:
                logger.error(
                    f"Nie znaleziono kategorii teamów o ID {self.team_config['category_id']}"
                )
                category = None

            # Create channel permissions
            overwrites = {
                ctx.guild.default_role: discord.PermissionOverwrite(read_messages=False),
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
            channel_name = team_name.lower().replace(" ", "-")
            team_channel = await ctx.guild.create_text_channel(
                name=channel_name,
                category=category,
                topic=f"{ctx.author.id} {team_role.id}",
                overwrites=overwrites,
                reason=f"Utworzenie kanału teamu przez {ctx.author.display_name}",
            )

            # Informacja o przynależności do innego teamu
            user_team_role = await self._get_user_team_role(ctx.author)
            additional_info = ""
            if user_team_role and user_team_role.id != team_role.id:
                additional_info = (
                    f"\n\nJesteś obecnie również członkiem teamu {user_team_role.mention}."
                )

            # Send success message
            description = (
                f"Utworzono team **{self.team_config['symbol']} {name}**!\n\n"
                f"• **Kanał**: {team_channel.mention}\n"
                f"• **Rola**: {team_role.mention}\n"
                f"• **Właściciel**: {ctx.author.mention}\n\n"
                f"Możesz zarządzać członkami teamu za pomocą komendy `{self.prefix}team member <@użytkownik> [+/-]`."
                f"{additional_info}"
            )

            # Use the new method to send the message
            await self._send_premium_embed(ctx, description=description)

            # Wysyłanie i przypinanie wiadomości informacyjnej na kanale teamu
            team_info_embed = discord.Embed(
                title=f"Team **{self.team_config['symbol']} {name}**",
                description="Witaj w twoim nowym teamie! Oto informacje o nim:",
                color=team_role.color if team_role.color.value != 0 else discord.Color.blue(),
            )
            team_info_embed.add_field(name="Właściciel", value=ctx.author.mention, inline=True)
            team_info_embed.add_field(name="Rola", value=team_role.mention, inline=True)
            team_info_embed.add_field(
                name="Data utworzenia",
                value=discord.utils.format_dt(datetime.now(timezone.utc), style="f"),
                inline=True,
            )

            # Dodaj sekcję z komendami
            team_info_embed.add_field(
                name="Dostępne komendy", value=self._get_team_commands_description(), inline=False
            )

            # Dodaj informację o twojej roli
            user_premium_role = None
            for role in ctx.author.roles:
                if any(r["name"] == role.name for r in self.bot.config["premium_roles"]):
                    user_premium_role = role
                    break

            if user_premium_role:
                max_members = next(
                    (
                        r["team_size"]
                        for r in self.bot.config["premium_roles"]
                        if r["name"] == user_premium_role.name
                    ),
                    10,
                )
                team_info_embed.add_field(
                    name="Limity teamu",
                    value=f"• Maksymalna liczba członków: **{max_members}**",
                    inline=False,
                )

            # Wyślij i przypnij wiadomość
            team_info_message = await team_channel.send(embed=team_info_embed)
            await team_info_message.pin(reason="Informacje o teamie")

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

        # Użyj metody pomocniczej do sprawdzenia uprawnień
        has_perm, team_role, error_msg = await self._check_team_permissions(ctx, check_owner=True)
        if not has_perm:
            return await self.message_sender.send_error(ctx, error_msg)

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
                if channel.topic and str(ctx.author.id) in channel.topic:
                    # Sprawdź nowy format topicu: "id_właściciela id_roli"
                    topic_parts = channel.topic.split()
                    # Jeśli topic ma format id_właściciela id_roli
                    if len(topic_parts) >= 2 and topic_parts[0] == str(ctx.author.id) and topic_parts[1] == str(team_role.id):
                        team_channel = channel
                        break
                    # Dla kompatybilności ze starym formatem
                    elif "Team Channel" in channel.topic:
                        team_channel = channel
                        break

            if team_channel:
                # Aktualizuj nazwę kanału - usuń symbole specjalne i emoji, zachowaj tylko alfanumeryczne znaki
                # Najpierw usuń symbol teamu i emoji jeśli istnieje
                channel_parts = new_team_name.split()
                actual_name = channel_parts[-1] if len(channel_parts) >= 2 else new_team_name
                
                # Stwórz nazwę kanału zgodną z wymaganiami Discord (małe litery, cyfry, myślniki)
                import re
                channel_name = re.sub(r'[^a-zA-Z0-9 ]', '', actual_name)
                channel_name = channel_name.lower().strip().replace(" ", "-")
                
                # Dodaj prefix teamu dla lepszej organizacji
                channel_name = f"☫-{channel_name}"
                
                logger.info(f"Aktualizacja nazwy kanału teamu z {team_channel.name} na {channel_name}")
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

    @team.command(name="member")
    @app_commands.describe(
        target="Użytkownik do dodania/usunięcia z teamu",
        action="Dodaj (+) lub usuń (-) użytkownika z teamu. Bez parametru działa jak przełącznik."
    )
    async def team_member(
        self,
        ctx,
        target: discord.Member,
        action: Optional[Literal["+", "-"]] = None,
    ):
        """Dodaj lub usuń członka teamu. Bez parametru + lub - działa jak przełącznik."""
        # Użyj metody pomocniczej do sprawdzenia uprawnień
        has_perm, team_role, error_msg = await self._check_team_permissions(ctx, check_owner=True)
        if not has_perm:
            return await self.message_sender.send_error(ctx, error_msg)

        # Sprawdź czy użytkownik nie próbuje dodać/usunąć samego siebie
        if target.id == ctx.author.id:
            return await self.message_sender.send_error(
                ctx, "Nie możesz dodać/usunąć siebie z teamu - jesteś jego właścicielem."
            )

        # Sprawdź czy osoba jest już w teamie
        is_in_team = team_role in target.roles
        
        # Określ akcję na podstawie parametrów
        # Jeśli nie podano jawnej akcji, przełącz członkostwo
        if action is None:
            action = "-" if is_in_team else "+"
        
        # Obsługa dodawania do teamu
        if action == "+" and not is_in_team:
            # Sprawdź czy osoba nie ma już innego teamu
            member_team = await self._get_user_team_role(target)
            if member_team:
                return await self.message_sender.send_error(
                    ctx, f"{target.mention} jest już członkiem teamu **{member_team.name}**."
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
                await target.add_roles(team_role)
                
                # Wyślij informację o sukcesie
                description = f"Dodano **{target.mention}** do teamu **{team_role.mention}**!"
                await self._send_premium_embed(ctx, description=description)
            except Exception as e:
                logger.error(f"Błąd podczas dodawania członka do teamu: {str(e)}")
                await self.message_sender.send_error(
                    ctx, f"Wystąpił błąd podczas dodawania członka do teamu: {str(e)}"
                )
        
        # Obsługa usuwania z teamu
        elif action == "-" and is_in_team:
            try:
                # Usuń rolę od użytkownika
                await target.remove_roles(team_role)
                
                # Wyślij informację o sukcesie
                description = f"Usunięto **{target.mention}** z teamu **{team_role.mention}**!"
                await self._send_premium_embed(ctx, description=description)
            except Exception as e:
                logger.error(f"Błąd podczas usuwania członka z teamu: {str(e)}")
                await self.message_sender.send_error(
                    ctx, f"Wystąpił błąd podczas usuwania członka z teamu: {str(e)}"
                )
        
        # Jeśli akcja nie pasuje do obecnego stanu
        elif (action == "+" and is_in_team) or (action == "-" and not is_in_team):
            state = "już jest" if is_in_team else "nie jest"
            await self.message_sender.send_success(
                ctx, f"{target.mention} {state} członkiem teamu **{team_role.name}**."
            )

    @team.command(name="color")
    @app_commands.describe(color="Kolor teamu (angielska nazwa, hex lub polska nazwa)")
    async def team_color(self, ctx, color: str):
        """Change your team's color."""
        # Użyj metody pomocniczej do sprawdzenia uprawnień
        has_perm, team_role, error_msg = await self._check_team_permissions(
            ctx, required_role="zG500", check_owner=True
        )
        if not has_perm:
            return await self._send_premium_embed(ctx, description=error_msg, color=0xFF0000)

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
    @app_commands.describe(emoji="Emoji teamu (opcjonalne, bez podania usuwa ikonę)")
    async def team_emoji(self, ctx, emoji: Optional[str] = None):
        """Set team emoji as role icon or remove icon if no emoji provided."""
        # Dokładne logowanie, co otrzymaliśmy
        logger.info(
            f"team_emoji command with emoji string: '{emoji}', type: {type(emoji)}, length: {len(emoji) if emoji else 0}"
        )

        # Użyj metody pomocniczej do sprawdzenia uprawnień
        has_perm, team_role, error_msg = await self._check_team_permissions(
            ctx, required_role="zG1000"
        )
        if not has_perm:
            return await self._send_premium_embed(ctx, description=error_msg, color=0xFF0000)

        # Check if server has the required boost level for role icons (Level 2)
        if ctx.guild.premium_tier < 2:
            return await self._send_premium_embed(
                ctx,
                description="Serwer musi mieć minimum 7 boostów (Poziom 2), aby można było ustawić ikony ról.",
                color=0xFF0000,
            )

        # If no emoji provided, remove the role icon
        if emoji is None or emoji.strip() == "":
            try:
                logger.info(f"Removing icon from role {team_role.id}")
                await team_role.edit(display_icon=None)
                logger.info(f"Successfully removed role icon")

                # Send success message
                description = f"Usunięto ikonę teamu **{team_role.mention}**."
                return await self._send_premium_embed(ctx, description=description)

            except discord.Forbidden:
                logger.error("Forbidden error during team icon removal")
                return await self._send_premium_embed(
                    ctx,
                    description="Bot nie ma wystarczających uprawnień, aby zmienić ikonę roli.",
                    color=0xFF0000,
                )
            except discord.HTTPException as e:
                logger.error(f"HTTP error during team icon removal: {str(e)}")
                return await self._send_premium_embed(
                    ctx,
                    description=f"Wystąpił błąd podczas usuwania ikony teamu: {str(e)}",
                    color=0xFF0000,
                )
            except Exception as e:
                logger.error(f"Error during team icon removal: {str(e)}")
                return await self._send_premium_embed(
                    ctx,
                    description=f"Wystąpił błąd podczas usuwania ikony teamu: {str(e)}",
                    color=0xFF0000,
                )

        # Check if it's a custom emoji in wrong format (:name: instead of <:name:id>)
        if emoji.startswith(":") and emoji.endswith(":") and len(emoji) > 2:
            logger.info(f"User provided emoji in :name: format: {emoji}")
            # User provided serwerowe emoji w formacie :nazwa: zamiast <:nazwa:id>
            return await self._send_premium_embed(
                ctx,
                description=f"`{emoji}` nie jest poprawnym formatem emoji serwera. Aby użyć emoji z serwera, kliknij prawym przyciskiem myszy na emoji i wybierz 'Kopiuj odnośnik do emoji', a następnie wklej go w komendzie.",
                color=0xFF0000,
            )

        # Sprawdzenie, czy emoji serwerowe pochodzi z tego samego serwera
        if emoji.startswith("<") and emoji.endswith(">"):
            parts = emoji.strip("<>").split(":")
            if len(parts) >= 3:
                emoji_id = parts[-1]
                try:
                    # Próba znalezienia emoji na serwerze
                    emoji_id = int(emoji_id)
                    server_emoji = discord.utils.get(ctx.guild.emojis, id=emoji_id)
                    if not server_emoji:
                        logger.warning(f"User tried to use emoji from another server: {emoji}")
                        return await self._send_premium_embed(
                            ctx,
                            description=f"Możesz używać tylko emoji, które są dostępne na tym serwerze.",
                            color=0xFF0000,
                        )
                except (ValueError, TypeError):
                    return await self._send_premium_embed(
                        ctx,
                        description=f"`{emoji}` nie jest poprawnym emoji.",
                        color=0xFF0000,
                    )

        # Logujemy, czy emoji jest poprawne według walidatora
        is_valid = emoji_validator(emoji)
        logger.info(f"Emoji validation result for '{emoji}': {is_valid}")

        if not is_valid:
            # Jeśli to emoji serwerowe, sprawdź jeszcze raz z poprawioną logiką
            if emoji.startswith("<") and emoji.endswith(">"):
                parts = emoji.strip("<>").split(":")
                logger.info(f"Custom emoji parts: {parts}")

                # Sprawdź, czy to potencjalnie poprawne emoji serwerowe, którego nasz walidator nie przepuszcza
                if len(parts) >= 3 and parts[1]:
                    # Ostatnia część powinna być liczbą - ID emoji
                    try:
                        emoji_id = parts[-1]
                        int(emoji_id)  # Sprawdź, czy to liczba
                        logger.info(f"Emoji seems valid despite validator failure, ID: {emoji_id}")
                        # Jeśli dotarliśmy tutaj, to wygląda na poprawne emoji, kontynuuj mimo błędu walidacji
                    except (ValueError, IndexError):
                        return await self._send_premium_embed(
                            ctx, description=f"`{emoji}` nie jest poprawnym emoji.", color=0xFF0000
                        )
                else:
                    return await self._send_premium_embed(
                        ctx, description=f"`{emoji}` nie jest poprawnym emoji.", color=0xFF0000
                    )
            else:
                return await self._send_premium_embed(
                    ctx, description=f"`{emoji}` nie jest poprawnym emoji.", color=0xFF0000
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

            # Log before conversion attempt
            logger.info(f"Converting emoji '{emoji}' to role icon format")

            # Convert emoji to role icon format with better error handling
            try:
                icon_bytes = await emoji_to_icon(emoji)
                logger.info(f"Successfully converted emoji to icon, size: {len(icon_bytes)} bytes")
            except Exception as e:
                logger.error(f"Failed to convert emoji to icon: {str(e)}")
                return await self._send_premium_embed(
                    ctx,
                    description=f"Nie udało się przekonwertować emoji na format ikony roli: {str(e)}",
                    color=0xFF0000,
                )

            # Update role with new icon and cleaned name with better error handling
            try:
                logger.info(f"Updating role {team_role.id} with new icon")
                await team_role.edit(name=new_name, display_icon=icon_bytes)
                logger.info(f"Successfully updated role icon")
            except discord.Forbidden as e:
                logger.error(f"Forbidden error while updating role icon: {str(e)}")
                return await self._send_premium_embed(
                    ctx,
                    description="Bot nie ma wystarczających uprawnień, aby zmienić ikonę roli.",
                    color=0xFF0000,
                )
            except discord.HTTPException as e:
                logger.error(f"HTTP error while updating role icon: {str(e)}")
                return await self._send_premium_embed(
                    ctx,
                    description=f"Wystąpił błąd podczas zmiany emoji teamu: {str(e)}",
                    color=0xFF0000,
                )
            except Exception as e:
                logger.error(f"Unexpected error while updating role icon: {str(e)}")
                return await self._send_premium_embed(
                    ctx,
                    description=f"Wystąpił nieoczekiwany błąd podczas zmiany emoji teamu: {str(e)}",
                    color=0xFF0000,
                )

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
            logger.error("Forbidden error during team emoji update")
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

    @team.command(name="admin_delete")
    @is_admin()
    @app_commands.describe(user="Użytkownik, którego teamy mają zostać usunięte")
    async def team_admin_delete(self, ctx, user: discord.Member):
        """
        Usuń wszystkie teamy użytkownika (komenda administracyjna).
        Przydatne, gdy zostały zespoły, których użytkownik nie powinien mieć.
        """
        logger.info(
            f"Admin {ctx.author.display_name} zainicjował usunięcie teamów użytkownika {user.display_name}"
        )

        async with self.bot.get_db() as session:
            try:
                # Użyj bezpieczniejszej metody SQL do usuwania teamów
                deleted_teams = await TeamManager.delete_user_teams_by_sql(
                    session, self.bot, user.id
                )

                if deleted_teams > 0:
                    await self._send_premium_embed(
                        ctx,
                        description=f"Usunięto {deleted_teams} teamy użytkownika {user.mention}.",
                        color=0x00FF00,
                    )
                    logger.info(
                        f"Admin {ctx.author.display_name} usunął {deleted_teams} teamów użytkownika {user.display_name}"
                    )
                else:
                    await self._send_premium_embed(
                        ctx,
                        description=f"Nie znaleziono żadnych teamów użytkownika {user.mention}.",
                        color=0xFF9900,
                    )
            except Exception as e:
                logger.error(f"Błąd podczas usuwania teamów: {str(e)}")
                await self._send_premium_embed(
                    ctx,
                    description=f"Wystąpił błąd podczas usuwania teamów: {str(e)}",
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

        This method only checks ownership, not team membership.
        A user can be a member of multiple teams but can only own one team.

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

    async def _check_team_permissions(self, ctx, required_role=None, check_owner=True):
        """
        Helper method to check if user has required permissions for team operations.

        :param ctx: Command context
        :param required_role: Required role name (e.g. 'zG1000' for emoji) or list of role names
        :param check_owner: Whether to check if user is team owner
        :return: (has_permission, team_role, error_msg) tuple. If has_permission is False, error_msg contains the error message.
        """
        # Check if user has required role
        if required_role:
            if isinstance(required_role, str):
                required_roles = [required_role]
            else:
                required_roles = required_role

            # Hierarchia ról premium (od najniższej do najwyższej)
            premium_roles_hierarchy = ["zG50", "zG100", "zG500", "zG1000"]

            # Sprawdź rolę użytkownika w hierarchii
            user_highest_role = None
            for role in ctx.author.roles:
                if role.name in premium_roles_hierarchy:
                    role_index = premium_roles_hierarchy.index(role.name)
                    if user_highest_role is None or role_index > premium_roles_hierarchy.index(
                        user_highest_role
                    ):
                        user_highest_role = role.name

            # Sprawdź czy rola użytkownika jest wystarczająca
            has_sufficient_role = False
            min_required_role = None
            min_required_index = float("inf")

            for role_name in required_roles:
                if role_name in premium_roles_hierarchy:
                    role_index = premium_roles_hierarchy.index(role_name)
                    if role_index < min_required_index:
                        min_required_index = role_index
                        min_required_role = role_name

            if user_highest_role and min_required_role:
                user_role_index = premium_roles_hierarchy.index(user_highest_role)
                min_required_index = premium_roles_hierarchy.index(min_required_role)
                has_sufficient_role = user_role_index >= min_required_index
            else:
                # Jeśli nie możemy określić pozycji w hierarchii, użyj starej metody
                has_sufficient_role = any(role.name in required_roles for role in ctx.author.roles)

            if not has_sufficient_role:
                if len(required_roles) == 1:
                    return (
                        False,
                        None,
                        f"Tylko użytkownicy z rangą {required_roles[0]} lub wyższą mogą wykonać tę operację.",
                    )
                else:
                    min_role_name = min_required_role or " lub ".join(required_roles)
                    return (
                        False,
                        None,
                        f"Tylko użytkownicy z rangą {min_role_name} lub wyższą mogą wykonać tę operację.",
                    )

        # Check if user has a team
        team_role = await self._get_user_team_role(ctx.author)
        if not team_role:
            return (
                False,
                None,
                f"Nie masz żadnego teamu. Utwórz go najpierw za pomocą `{self.prefix}team create`.",
            )

        # Check if user is team owner
        if check_owner:
            is_owner = await self._is_team_owner(ctx.author.id, team_role.id)
            if not is_owner:
                return False, None, "Tylko właściciel teamu może wykonać tę operację."

        return True, team_role, None

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

            # Find the team channel - używamy nowego formatu topicu
            team_channel = None
            for channel in guild.channels:
                if (
                    isinstance(channel, discord.TextChannel)
                    and channel.topic
                    and len(channel.topic.split()) >= 2
                ):
                    topic_parts = channel.topic.split()
                    # Sprawdzamy czy topic zawiera dwa ID: właściciela i roli
                    if (
                        len(topic_parts) >= 2
                        and topic_parts[0] == str(owner_id)
                        and topic_parts[1] == str(team_role.id)
                    ):
                        team_channel = channel
                        break

                    # Dla kompatybilności ze starym formatem
                    elif "Team Channel" in channel.topic and str(owner_id) in channel.topic:
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

    def _get_team_commands_description(self):
        """
        Get a formatted description of available team commands.

        :return: Formatted string with team commands
        """
        return (
            f"• `{self.prefix}team create <nazwa>` - Utwórz nowy team\n"
            f"• `{self.prefix}team name <nazwa>` - Zmień nazwę swojego teamu\n"
            f"• `{self.prefix}team member <@użytkownik> [+/-]` - Dodaj/usuń członka do/z teamu\n"
            f"• `{self.prefix}team color <kolor>` - Ustaw kolor teamu (wymaga rangi zG500+)\n"
            f"• `{self.prefix}team emoji <emoji>` - Ustaw emoji teamu (wymaga rangi zG1000)"
        )


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

        # Dla emoji w formacie <:nazwa:id> mamy ['', 'nazwa', 'id>']
        # Dla emoji w formacie <a:nazwa:id> mamy ['a', 'nazwa', 'id']
        # Upewnijmy się, że mamy co najmniej 3 części i druga oraz trzecia nie są puste
        if len(parts) >= 3 and parts[1] and parts[2]:
            return True

        # Dla innych formatów sprawdź czy wszystkie części są niepuste
        return len(parts) >= 2 and all(part for part in parts)

    # Special case for when user inputs :name: format instead of <:name:id>
    if emoji_str.startswith(":") and emoji_str.endswith(":") and len(emoji_str) > 2:
        # Powiedz użytkownikowi, że nie możemy obsłużyć tego formatu
        return False

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
        parts = emoji_str.split(":")

        # For emoji in format <:nazwa:id> we get ['', 'name', 'id>']
        # For emoji in format <a:nazwa:id> we get ['<a', 'name', 'id']
        if len(parts) >= 3:
            # Extract the ID properly, removing the closing ">"
            emoji_id = parts[-1].replace(">", "")
            # Check if it's an animated emoji
            is_animated = emoji_str.startswith("<a:")

            # Format the URL
            ext = "gif" if is_animated else "png"
            emoji_url = f"https://cdn.discordapp.com/emojis/{emoji_id}.{ext}"

            logger.info(f"Fetching custom emoji from URL: {emoji_url}")

            # Use httpx to get the emoji image
            try:
                async with httpx.AsyncClient() as client:
                    response = await client.get(emoji_url)
                    if response.status_code == 200:
                        logger.info(f"Successfully downloaded custom emoji image from {emoji_url}")
                        return response.content
                    else:
                        logger.error(
                            f"Failed to download custom emoji image from {emoji_url}: HTTP {response.status_code}"
                        )
            except Exception as e:
                logger.error(f"Error getting custom emoji from URL: {emoji_url}, error: {str(e)}")

    # For standard Unicode emojis, use the Twemoji CDN to get the emoji image
    try:
        # Konwertuj emoji Unicode na kod dla Twemoji
        codepoints = []
        for char in emoji_str:
            # Dla każdego znaku emoji (które mogą składać się z kilku kodów Unicode)
            # pobierz kod szesnastkowy i dodaj go do listy
            if ord(char) < 0x10000:  # Podstawowe znaki Unicode
                codepoints.append(f"{ord(char):x}")
            else:  # Znaki spoza Basic Multilingual Plane
                codepoints.append(f"{ord(char):x}")

        # Tworzenie kodu emoji dla Twemoji - używa kresek dla złożonych emoji
        emoji_code = "-".join(codepoints).lower()
        logger.info(f"Unicode emoji '{emoji_str}' converted to code: {emoji_code}")

        # Pobieranie emoji z CDN Twemoji
        emoji_url = (
            f"https://cdn.jsdelivr.net/gh/twitter/twemoji@latest/assets/72x72/{emoji_code}.png"
        )
        logger.info(f"Fetching Twemoji from URL: {emoji_url}")

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(emoji_url)
                if response.status_code == 200:
                    # Twemoji successfully found
                    logger.info(f"Successfully downloaded Twemoji from {emoji_url}")
                    return response.content
                else:
                    logger.error(
                        f"Failed to download Twemoji from {emoji_url}: HTTP {response.status_code}"
                    )
                    # Spróbuj alternatywnego źródła Twemoji
                    alternate_url = f"https://twemoji.maxcdn.com/v/latest/72x72/{emoji_code}.png"
                    logger.info(f"Trying alternate Twemoji URL: {alternate_url}")
                    alt_response = await client.get(alternate_url)
                    if alt_response.status_code == 200:
                        logger.info(
                            f"Successfully downloaded Twemoji from alternate URL {alternate_url}"
                        )
                        return alt_response.content
                    else:
                        logger.error(
                            f"Failed to download Twemoji from alternate URL: HTTP {alt_response.status_code}"
                        )
        except Exception as e:
            logger.error(f"Error getting Twemoji from URL: {emoji_url}, error: {str(e)}")

        # Jeśli nie udało się pobrać z Twemoji, spróbujmy użyć biblioteki emoji_data_python
        logger.info("Fallback to rendering emoji with Pillow")

        # Find the emoji using emoji_data_python
        for e in emoji_data_python.emoji_data:
            if e.char == emoji_str:
                emoji_str = e.char
                break

        # Try to use system fonts
        img = Image.new("RGBA", (128, 128), (0, 0, 0, 0))  # Transparent background
        draw = ImageDraw.Draw(img)

        try:
            # Try common emoji font paths
            font_paths = [
                "/usr/share/fonts/truetype/noto/NotoColorEmoji.ttf",  # Linux
                "/System/Library/Fonts/Apple Color Emoji.ttc",  # macOS
                "C:\\Windows\\Fonts\\seguiemj.ttf",  # Windows
                "/usr/share/fonts/truetype/ancient-scripts/Symbola.ttf",  # Linux fallback
                "/usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc",  # Another Linux option
            ]

            font = None
            for font_path in font_paths:
                try:
                    font = ImageFont.truetype(font_path, 109)
                    break
                except (IOError, OSError):
                    continue

            if font is None:
                # If all font paths fail, try to use a system font
                font = ImageFont.load_default()

            # Draw the emoji centered with a more visible color (white)
            draw.text((64, 64), emoji_str, font=font, fill=(255, 255, 255, 255), anchor="mm")

            buffer = io.BytesIO()
            img.save(buffer, format="PNG")
            buffer.seek(0)
            return buffer.read()

        except Exception as e:
            logger.error(f"Error rendering emoji with Pillow: {str(e)}")
            # Continue to fallback

    except Exception as e:
        logger.error(f"Error processing emoji: {str(e)}")

    # Last resort: use a default image
    img = Image.new("RGBA", (128, 128), (0, 120, 215, 255))  # Discord blue as fallback
    draw = ImageDraw.Draw(img)
    # Draw a question mark
    try:
        font = ImageFont.load_default()
        draw.text((64, 64), "?", font=font, fill=(255, 255, 255, 255), anchor="mm")
    except:
        pass  # Just use the blue background if text fails

    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)
    return buffer.read()


async def setup(bot):
    """This function is called when the cog is loaded."""
    await bot.add_cog(PremiumCog(bot))
