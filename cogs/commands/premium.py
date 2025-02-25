"""Premium commands cog for premium features like role colors and more."""

import logging
import discord
from discord import app_commands
from discord.ext import commands
from typing import Optional

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
        
    @commands.hybrid_command(aliases=["c"])
    @PremiumChecker.requires_voice_access("color")
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
            
            # Wysłanie potwierdzenia
            embed = self.message_sender._create_embed(
                description=f"Zmieniono kolor twojej roli na {color}.",
                color="success",
                ctx=ctx
            )
            await self.message_sender._send_embed(ctx, embed, reply=True)
            
        except ValueError as e:
            embed = self.message_sender._create_embed(
                description=f"Błąd: {str(e)}",
                color="error",
                ctx=ctx
            )
            await self.message_sender._send_embed(ctx, embed, reply=True)
            
    async def parse_color(self, color_string: str) -> discord.Color:
        """Konwertuje string koloru na obiekt discord.Color."""
        # Jeśli to hex
        if color_string.startswith("#"):
            try:
                return discord.Color.from_str(color_string)
            except ValueError:
                raise ValueError(f"Niepoprawny format koloru HEX: {color_string}")
        
        # Angielskie nazwy kolorów
        english_colors = {
            "red": discord.Color.red(),
            "green": discord.Color.green(),
            "blue": discord.Color.blue(),
            "yellow": discord.Color.yellow(),
            "orange": discord.Color.orange(),
            "purple": discord.Color.purple(),
            "black": discord.Color.default(),
            "white": discord.Color.from_rgb(255, 255, 255),
            "pink": discord.Color.from_rgb(255, 105, 180),
            "gray": discord.Color.from_rgb(128, 128, 128),
            "brown": discord.Color.from_rgb(165, 42, 42),
            "cyan": discord.Color.from_rgb(0, 255, 255),
            "magenta": discord.Color.from_rgb(255, 0, 255),
            "teal": discord.Color.teal(),
            "gold": discord.Color.gold()
        }
        
        # Polskie nazwy kolorów
        polish_colors = {
            "czerwony": discord.Color.red(),
            "zielony": discord.Color.green(),
            "niebieski": discord.Color.blue(),
            "żółty": discord.Color.yellow(),
            "pomarańczowy": discord.Color.orange(),
            "fioletowy": discord.Color.purple(),
            "czarny": discord.Color.default(),
            "biały": discord.Color.from_rgb(255, 255, 255),
            "różowy": discord.Color.from_rgb(255, 105, 180),
            "szary": discord.Color.from_rgb(128, 128, 128),
            "brązowy": discord.Color.from_rgb(165, 42, 42),
            "turkusowy": discord.Color.from_rgb(0, 255, 255),
            "magenta": discord.Color.from_rgb(255, 0, 255),
            "morski": discord.Color.teal(),
            "złoty": discord.Color.gold()
        }
        
        # Sprawdź czy kolor jest w słownikach
        color_lower = color_string.lower()
        if color_lower in english_colors:
            return english_colors[color_lower]
        if color_lower in polish_colors:
            return polish_colors[color_lower]
        
        # Jeśli to liczba hex bez #
        try:
            hex_value = int(color_string, 16)
            return discord.Color(hex_value)
        except ValueError:
            pass
        
        # Jeśli nic nie pasuje
        raise ValueError(f"Nieznany kolor: {color_string}. Użyj nazwy angielskiej, polskiej lub kodu HEX (np. #FF5733).")
        
    async def update_user_color_role(self, member: discord.Member, color: discord.Color):
        """Tworzy lub aktualizuje rolę kolorową użytkownika."""
        role_name = f"{self.color_role_name} {member.display_name}"
        
        # Sprawdź, czy użytkownik już ma rolę kolorową
        existing_role = None
        for role in member.roles:
            if role.name.startswith(self.color_role_name):
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
    # @PremiumChecker.requires_voice_access("badge")
    # async def badge(self, ctx, ...):
    #    """Komenda do zarządzania odznakami dla użytkowników premium."""
    #    pass


async def setup(bot):
    """This function is called when the cog is loaded."""
    await bot.add_cog(PremiumCog(bot)) 