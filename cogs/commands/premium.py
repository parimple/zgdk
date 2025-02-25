"""Premium commands cog for premium features like role colors and more."""

import logging
import discord
from discord import app_commands
from discord.ext import commands
from typing import Optional
from colour import Color

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

    # Tutaj można dodać kolejne komendy premium w przyszłości
    # Na przykład:
    # @commands.hybrid_command()
    # @PremiumChecker.requires_premium_tier("badge")
    # async def badge(self, ctx, ...):
    #    """Komenda do zarządzania odznakami dla użytkowników premium."""
    #    pass


async def setup(bot):
    """This function is called when the cog is loaded."""
    await bot.add_cog(PremiumCog(bot)) 