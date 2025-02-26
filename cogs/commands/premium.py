"""Premium commands cog for premium features like role colors and more."""

import logging
import discord
from discord import app_commands
from discord.ext import commands
from typing import Optional, Literal
from colour import Color
import emoji

from datasources.models import Role as DBRole, MemberRole
from datasources.queries import MemberQueries
from utils.message_sender import MessageSender
from utils.premium_checker import PremiumChecker

logger = logging.getLogger(__name__)

class PremiumCog(commands.Cog):
    """Premium commands cog for various premium features."""

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
            "category_id": self.bot.config.get("team", {}).get("category_id", 1344105013357842522)
        }
        
    @commands.hybrid_command(aliases=["colour", "kolor"])
    @PremiumChecker.requires_premium_tier("color")
    @app_commands.describe(
        color="Kolor roli (angielska nazwa, hex lub polska nazwa)"
    )
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
                ctx=ctx
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
                description=description,
                color="error",
                ctx=ctx
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
            "złoty": "gold"
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
                if not color_string.startswith('#'):
                    # Próba interpretacji jako liczby szesnastkowej
                    hex_value = int(color_string, 16)
                    return discord.Color(hex_value)
            except ValueError:
                pass
            
            # Jeśli wszystkie próby zawiodły
            raise ValueError(f"Nieznany kolor: `{color_string}`. Użyj nazwy angielskiej, polskiej lub kodu HEX (np. `#FF5733`).")
        
    async def update_user_color_role(self, member: discord.Member, color: discord.Color):
        """Tworzy lub aktualizuje rolę kolorową użytkownika."""
        # Użyj samej nazwy roli bez dodawania nazwy użytkownika
        role_name = self.color_role_name
        
        # Sprawdź, czy użytkownik już ma rolę kolorową
        existing_role = None
        for role in member.roles:
            if role.name == self.color_role_name:
                existing_role = role
                break
        
        if existing_role:
            # Aktualizuj istniejącą rolę
            await existing_role.edit(color=color)
        else:
            # Stwórz nową rolę
            base_role = member.guild.get_role(self.base_role_id)
            if not base_role:
                raise ValueError(f"Nie znaleziono roli bazowej o ID {self.base_role_id}")
            
            # Tworzenie roli
            new_role = await member.guild.create_role(
                name=role_name,
                color=color,
                reason=f"Rola kolorowa dla {member.display_name}"
            )
            
            # Przeniesienie roli nad bazową
            positions = {
                new_role: base_role.position + 1
            }
            await member.guild.edit_role_positions(positions=positions)
            
            # Nadanie roli użytkownikowi
            await member.add_roles(new_role)

    # Grupa komend do zarządzania teamami (klanami)
    @commands.group(invoke_without_command=True)
    async def team(self, ctx):
        """Komendy do zarządzania teamem (klanem)."""
        if ctx.invoked_subcommand is None:
            # Sprawdź czy użytkownik ma team
            team_role = await self._get_user_team_role(ctx.author)
            
            if team_role:
                # Pobierz informacje o teamie
                team_info = await self._get_team_info(team_role)
                await self._send_team_info(ctx, team_role, team_info)
            else:
                # Wyślij informację o dostępnych podkomendach
                description = (
                    "**Dostępne komendy:**\n"
                    f"`,team create <nazwa>` - Utwórz nowy team\n"
                    f"`,team name <nazwa>` - Zmień nazwę swojego teamu\n"
                    f"`,team member add <@użytkownik>` - Dodaj członka do teamu\n"
                    f"`,team member remove <@użytkownik>` - Usuń członka z teamu\n"
                    f"`,team color <kolor>` - Ustaw kolor teamu (wymaga rangi zG500+)\n"
                    f"`,team emoji <emoji>` - Ustaw emoji teamu (wymaga rangi zG1000)"
                )
                await self.message_sender.send_success(ctx, description)
    
    @team.command(name="create")
    @PremiumChecker.requires_specific_roles(["zG100", "zG500", "zG1000"])
    @app_commands.describe(
        name="Nazwa teamu (klanu)",
        color="Kolor teamu (opcjonalne, wymaga rangi zG500+)",
        emoji="Emoji teamu (opcjonalne, wymaga rangi zG1000)"
    )
    async def team_create(self, ctx, name: str, color: Optional[str] = None, emoji: Optional[str] = None):
        """Utwórz nowy team (klan)."""
        # Sprawdź czy użytkownik już ma team
        existing_team = await self._get_user_team_role(ctx.author)
        if existing_team:
            return await self.message_sender.send_error(
                ctx, f"Masz już team `{existing_team.name}`. Musisz go najpierw usunąć."
            )
        
        # Sprawdź czy nazwa jest odpowiednia
        if len(name) < 3 or len(name) > 20:
            return await self.message_sender.send_error(
                ctx, "Nazwa teamu musi mieć od 3 do 20 znaków."
            )
        
        # Sprawdź czy team o takiej nazwie już istnieje
        guild = ctx.guild
        team_symbol = self.team_config["symbol"]
        full_team_name = f"{team_symbol} {name}"
        
        existing_role = discord.utils.get(guild.roles, name=full_team_name)
        if existing_role:
            return await self.message_sender.send_error(
                ctx, f"Team o nazwie `{name}` już istnieje."
            )
        
        # Sprawdź uprawnienia do koloru (zG500 lub zG1000)
        discord_color = None
        if color:
            has_color_permission = any(role.name in ["zG500", "zG1000"] for role in ctx.author.roles)
            if not has_color_permission:
                return await self.message_sender.send_error(
                    ctx, "Tylko użytkownicy z rangą zG500 lub wyższą mogą ustawić kolor teamu."
                )
            
            try:
                discord_color = await self.parse_color(color)
            except ValueError as e:
                return await self.message_sender.send_error(ctx, str(e))
        
        # Sprawdź uprawnienia do emoji (tylko zG1000)
        team_emoji = None
        if emoji:
            has_emoji_permission = any(role.name == "zG1000" for role in ctx.author.roles)
            if not has_emoji_permission:
                return await self.message_sender.send_error(
                    ctx, "Tylko użytkownicy z rangą zG1000 mogą ustawić emoji teamu."
                )
            
            # Sprawdź czy to jest poprawne emoji
            if not emoji_validator(emoji):
                return await self.message_sender.send_error(
                    ctx, f"`{emoji}` nie jest poprawnym emoji."
                )
            
            team_emoji = emoji
            # Emoji będzie dodane do nazwy teamu
            full_team_name = f"{team_symbol} {team_emoji} {name}"
        
        # Tworzenie roli teamu
        try:
            # Stwórz rolę
            team_role = await guild.create_role(
                name=full_team_name,
                color=discord_color or discord.Color.default(),
                mentionable=True,
                reason=f"Utworzenie teamu przez {ctx.author.display_name}"
            )
            
            # Dodaj rolę do użytkownika
            await ctx.author.add_roles(team_role)
            
            # Stwórz kanał tekstowy w odpowiedniej kategorii
            category = guild.get_channel(self.team_config["category_id"])
            if not category:
                logger.error(f"Nie znaleziono kategorii teamów o ID {self.team_config['category_id']}")
                category = None
            
            # Tworzenie uprawnień dla kanału
            overwrites = {
                guild.default_role: discord.PermissionOverwrite(read_messages=False),
                team_role: discord.PermissionOverwrite(
                    read_messages=True,
                    send_messages=True,
                    embed_links=True,
                    attach_files=True,
                    read_message_history=True
                ),
                ctx.author: discord.PermissionOverwrite(
                    read_messages=True,
                    send_messages=True,
                    manage_messages=True,
                    manage_channels=True
                )
            }
            
            # Stwórz kanał tekstowy
            channel_name = full_team_name.lower().replace(" ", "-")
            team_channel = await guild.create_text_channel(
                name=channel_name,
                category=category,
                topic=f"Team Channel for {full_team_name}. Owner: {ctx.author.id}",
                overwrites=overwrites,
                reason=f"Utworzenie kanału teamu przez {ctx.author.display_name}"
            )
            
            # Zapisz rolę teamu do bazy danych
            await self._save_team_to_database(ctx.author.id, team_role.id)
            
            # Wyślij informację o sukcesie
            description = f"Utworzono team **{full_team_name}**!\n\n"
            description += f"• **Kanał:** {team_channel.mention}\n"
            description += f"• **Rola:** {team_role.mention}\n"
            description += f"• **Właściciel:** {ctx.author.mention}\n\n"
            description += "Możesz zarządzać członkami teamu za pomocą komendy `,team member add/remove`."
            
            await self.message_sender.send_success(ctx, description)
            
        except Exception as e:
            logger.error(f"Błąd podczas tworzenia teamu: {str(e)}")
            await self.message_sender.send_error(
                ctx, f"Wystąpił błąd podczas tworzenia teamu: {str(e)}"
            )
    
    @team.command(name="name")
    @app_commands.describe(name="Nowa nazwa teamu")
    async def team_name(self, ctx, name: str):
        """Zmień nazwę swojego teamu."""
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
                ctx, "Tylko właściciel teamu może zmienić jego nazwę."
            )
        
        # Sprawdź czy nazwa jest odpowiednia
        if len(name) < 3 or len(name) > 20:
            return await self.message_sender.send_error(
                ctx, "Nazwa teamu musi mieć od 3 do 20 znaków."
            )
        
        # Zachowanie emoji jeśli było wcześniej
        current_name_parts = team_role.name.split(" ")
        team_symbol = self.team_config["symbol"]
        team_emoji = None
        
        # Sprawdź czy team ma już emoji (format: ☫ 🔥 Nazwa)
        if len(current_name_parts) >= 3 and emoji_validator(current_name_parts[1]):
            team_emoji = current_name_parts[1]
            new_name = f"{team_symbol} {team_emoji} {name}"
        else:
            new_name = f"{team_symbol} {name}"
        
        try:
            # Aktualizuj rolę
            await team_role.edit(name=new_name)
            
            # Znajdź i zaktualizuj kanał
            team_channels = [c for c in ctx.guild.channels if isinstance(c, discord.TextChannel)]
            team_channel = None
            
            for channel in team_channels:
                if channel.topic and str(ctx.author.id) in channel.topic and "Team Channel" in channel.topic:
                    team_channel = channel
                    break
            
            if team_channel:
                # Aktualizuj nazwę kanału
                channel_name = new_name.lower().replace(" ", "-")
                await team_channel.edit(name=channel_name)
                
                # Wyślij informację o sukcesie
                description = f"Zmieniono nazwę teamu na **{new_name}**!\n\n"
                description += f"• **Kanał:** {team_channel.mention}\n"
                description += f"• **Rola:** {team_role.mention}"
                
                await self.message_sender.send_success(ctx, description)
            else:
                await self.message_sender.send_success(
                    ctx, f"Zmieniono nazwę teamu na **{new_name}**, ale nie znaleziono kanału teamu."
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
                f"`,team member add <@użytkownik>` - Dodaj członka do teamu\n"
                f"`,team member remove <@użytkownik>` - Usuń członka z teamu"
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
                ctx, "Nie masz żadnego teamu. Utwórz go najpierw za pomocą `,team create`."
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
        
        try:
            # Dodaj rolę do użytkownika
            await member.add_roles(team_role)
            
            # Wyślij informację o sukcesie
            await self.message_sender.send_success(
                ctx, f"Dodano {member.mention} do teamu **{team_role.name}**!"
            )
            
        except Exception as e:
            logger.error(f"Błąd podczas dodawania członka do teamu: {str(e)}")
            await self.message_sender.send_error(
                ctx, f"Wystąpił błąd podczas dodawania członka do teamu: {str(e)}"
            )
    
    @team_member.command(name="remove")
    @app_commands.describe(member="Użytkownik do usunięcia z teamu")
    async def team_member_remove(self, ctx, member: discord.Member):
        """Usuń członka ze swojego teamu."""
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
                ctx, "Tylko właściciel teamu może usuwać członków."
            )
        
        # Sprawdź czy użytkownik nie próbuje usunąć samego siebie
        if member.id == ctx.author.id:
            return await self.message_sender.send_error(
                ctx, "Nie możesz usunąć siebie z teamu. Aby usunąć team, skontaktuj się z administracją."
            )
        
        # Sprawdź czy osoba jest w teamie
        if team_role not in member.roles:
            return await self.message_sender.send_error(
                ctx, f"{member.mention} nie jest członkiem teamu **{team_role.name}**."
            )
        
        try:
            # Usuń rolę od użytkownika
            await member.remove_roles(team_role)
            
            # Wyślij informację o sukcesie
            await self.message_sender.send_success(
                ctx, f"Usunięto {member.mention} z teamu **{team_role.name}**!"
            )
            
        except Exception as e:
            logger.error(f"Błąd podczas usuwania członka z teamu: {str(e)}")
            await self.message_sender.send_error(
                ctx, f"Wystąpił błąd podczas usuwania członka z teamu: {str(e)}"
            )
    
    @team.command(name="color")
    @app_commands.describe(color="Kolor teamu (angielska nazwa, hex lub polska nazwa)")
    async def team_color(self, ctx, color: str):
        """Zmień kolor swojego teamu."""
        # Sprawdź uprawnienia do koloru (zG500 lub zG1000)
        has_color_permission = any(role.name in ["zG500", "zG1000"] for role in ctx.author.roles)
        if not has_color_permission:
            return await self.message_sender.send_error(
                ctx, "Tylko użytkownicy z rangą zG500 lub wyższą mogą ustawić kolor teamu."
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
                ctx, "Tylko właściciel teamu może zmienić jego kolor."
            )
        
        try:
            # Próba konwersji koloru na obiekt discord.Color
            discord_color = await self.parse_color(color)
            
            # Aktualizuj kolor roli
            await team_role.edit(color=discord_color)
            
            # Wyślij informację o sukcesie
            await self.message_sender.send_success(
                ctx, f"Zmieniono kolor teamu **{team_role.name}** na `{color}`!"
            )
            
        except ValueError as e:
            await self.message_sender.send_error(ctx, str(e))
        except Exception as e:
            logger.error(f"Błąd podczas zmiany koloru teamu: {str(e)}")
            await self.message_sender.send_error(
                ctx, f"Wystąpił błąd podczas zmiany koloru teamu: {str(e)}"
            )
    
    @team.command(name="emoji")
    @app_commands.describe(emoji="Emoji teamu")
    async def team_emoji(self, ctx, emoji: str):
        """Zmień emoji swojego teamu."""
        # Sprawdź uprawnienia do emoji (tylko zG1000)
        has_emoji_permission = any(role.name == "zG1000" for role in ctx.author.roles)
        if not has_emoji_permission:
            return await self.message_sender.send_error(
                ctx, "Tylko użytkownicy z rangą zG1000 mogą ustawić emoji teamu."
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
                ctx, "Tylko właściciel teamu może zmienić jego emoji."
            )
        
        # Sprawdź czy to jest poprawne emoji
        if not emoji_validator(emoji):
            return await self.message_sender.send_error(
                ctx, f"`{emoji}` nie jest poprawnym emoji."
            )
        
        try:
            # Zaktualizuj nazwę roli z emoji
            current_name_parts = team_role.name.split(" ")
            team_symbol = self.team_config["symbol"]
            
            # Sprawdź czy team ma już emoji (format: ☫ 🔥 Nazwa) lub nie (format: ☫ Nazwa)
            if len(current_name_parts) >= 3 and emoji_validator(current_name_parts[1]):
                # Zastąp istniejące emoji
                team_name = " ".join(current_name_parts[2:])
                new_name = f"{team_symbol} {emoji} {team_name}"
            else:
                # Dodaj emoji do istniejącej nazwy
                team_name = " ".join(current_name_parts[1:])
                new_name = f"{team_symbol} {emoji} {team_name}"
            
            # Aktualizuj rolę
            await team_role.edit(name=new_name)
            
            # Znajdź i zaktualizuj kanał
            team_channels = [c for c in ctx.guild.channels if isinstance(c, discord.TextChannel)]
            team_channel = None
            
            for channel in team_channels:
                if channel.topic and str(ctx.author.id) in channel.topic and "Team Channel" in channel.topic:
                    team_channel = channel
                    break
            
            if team_channel:
                # Aktualizuj nazwę kanału
                channel_name = new_name.lower().replace(" ", "-")
                await team_channel.edit(name=channel_name)
            
            # Wyślij informację o sukcesie
            await self.message_sender.send_success(
                ctx, f"Zmieniono emoji teamu na {emoji}!"
            )
            
        except Exception as e:
            logger.error(f"Błąd podczas zmiany emoji teamu: {str(e)}")
            await self.message_sender.send_error(
                ctx, f"Wystąpił błąd podczas zmiany emoji teamu: {str(e)}"
            )
    
    async def _get_user_team_role(self, member: discord.Member):
        """Pobierz rolę teamu użytkownika."""
        team_symbol = self.team_config["symbol"]
        for role in member.roles:
            if role.name.startswith(team_symbol):
                return role
        return None
    
    async def _is_team_owner(self, user_id: int, role_id: int):
        """Sprawdź czy użytkownik jest właścicielem teamu."""
        async with self.bot.get_db() as session:
            role = await session.get(DBRole, role_id)
            if role and role.role_type == "team":
                return role.name == str(user_id)
        return False
    
    async def _save_team_to_database(self, owner_id: int, role_id: int):
        """Zapisz team do bazy danych."""
        async with self.bot.get_db() as session:
            # Sprawdź czy rola już istnieje w bazie
            role = await session.get(DBRole, role_id)
            if not role:
                # Utwórz nową rolę w bazie
                role = DBRole(
                    id=role_id,
                    name=str(owner_id),  # ID właściciela jako name
                    role_type="team"
                )
                session.add(role)
            
            # Przypisz rolę do właściciela (bez daty wygaśnięcia)
            member_role = MemberRole(
                member_id=owner_id,
                role_id=role_id,
                expiration_date=None
            )
            session.add(member_role)
            
            await session.commit()
    
    async def _get_team_info(self, team_role: discord.Role):
        """Pobierz informacje o teamie."""
        guild = team_role.guild
        
        # Znajdź właściciela teamu
        async with self.bot.get_db() as session:
            role = await session.get(DBRole, team_role.id)
            owner_id = int(role.name) if role and role.role_type == "team" else None
            
            # Pobierz obiekt członka
            owner = guild.get_member(owner_id) if owner_id else None
            
            # Znajdź członków teamu
            members = [member for member in guild.members if team_role in member.roles]
            
            # Znajdź kanał teamu
            team_channel = None
            for channel in guild.channels:
                if isinstance(channel, discord.TextChannel) and channel.topic and str(owner_id) in channel.topic and "Team Channel" in channel.topic:
                    team_channel = channel
                    break
            
            return {
                "owner": owner,
                "members": members,
                "channel": team_channel,
                "member_count": len(members)
            }
    
    async def _send_team_info(self, ctx, team_role, team_info):
        """Wyślij informacje o teamie."""
        owner = team_info["owner"]
        members = team_info["members"]
        channel = team_info["channel"]
        
        description = f"**Team:** {team_role.name}\n\n"
        
        if owner:
            description += f"**Właściciel:** {owner.mention}\n"
        else:
            description += "**Właściciel:** Nieznany\n"
        
        description += f"**Liczba członków:** {len(members)}\n"
        
        if channel:
            description += f"**Kanał:** {channel.mention}\n\n"
        
        if members:
            # Ogranicz wyświetlanie do maksymalnie 15 członków
            member_mentions = [member.mention for member in members[:15]]
            description += f"**Członkowie:** {', '.join(member_mentions)}"
            
            if len(members) > 15:
                description += f" i {len(members) - 15} więcej..."
        
        embed = self.message_sender._create_embed(
            title=f"Informacje o teamie",
            description=description,
            color=team_role.color,
            ctx=ctx
        )
        
        await self.message_sender._send_embed(ctx, embed, reply=True)


# Funkcje pomocnicze
def emoji_validator(emoji_str: str) -> bool:
    """Sprawdź czy string jest pojedynczym emoji."""
    if not emoji_str:
        return False
        
    # Używamy biblioteki emoji do walidacji
    return emoji.is_emoji(emoji_str)


async def setup(bot):
    """This function is called when the cog is loaded."""
    await bot.add_cog(PremiumCog(bot)) 