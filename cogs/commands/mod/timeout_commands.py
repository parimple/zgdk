"""Timeout and other moderation commands."""

import logging
from datetime import datetime, timezone

import discord
from discord.ext import commands

from datasources.queries import ModerationLogQueries
from utils.permissions import is_mod_or_admin, is_owner_or_admin
from core.interfaces.member_interfaces import IModerationService
from .utils import parse_duration

logger = logging.getLogger(__name__)


class TimeoutCommands(commands.Cog):
    """Commands for timeouts and moderation utilities."""
    
    def __init__(self, bot):
        """Initialize timeout commands."""
        self.bot = bot
        self.parse_duration = parse_duration
    
    @commands.hybrid_command(
        name="timeout",
        description="Nadaje użytkownikowi timeout na określony czas."
    )
    @is_mod_or_admin()
    @discord.app_commands.describe(
        user="Użytkownik do wyciszenia",
        duration="Czas trwania (np. 1h, 30m, 1d)",
        reason="Powód timeout'u"
    )
    async def timeout(
        self,
        ctx: commands.Context,
        user: discord.Member,
        duration: str,
        *,
        reason: str = "Brak powodu"
    ):
        """Apply timeout to a user."""
        duration_seconds = self.parse_duration(duration)
        
        if not duration_seconds:
            await ctx.send("❌ Nieprawidłowy format czasu. Użyj np. 1h, 30m, 1d")
            return
        
        try:
            from datetime import timedelta
            timeout_until = discord.utils.utcnow() + timedelta(seconds=duration_seconds)
            
            await user.timeout(timeout_until, reason=f"{reason} (przez {ctx.author})")
            
            embed = discord.Embed(
                title="⏰ Timeout",
                description=f"{user.mention} otrzymał timeout",
                color=discord.Color.orange()
            )
            embed.add_field(name="Czas trwania", value=duration, inline=True)
            embed.add_field(name="Powód", value=reason, inline=True)
            embed.add_field(name="Moderator", value=ctx.author.mention, inline=True)
            
            await ctx.send(embed=embed)
            
        except discord.Forbidden:
            await ctx.send("❌ Nie mam uprawnień do nadania timeout'u temu użytkownikowi.")
        except Exception as e:
            logger.error(f"Error applying timeout: {e}")
            await ctx.send(f"❌ Wystąpił błąd: {str(e)}")
    
    @commands.hybrid_command(
        name="untimeout",
        description="Usuwa timeout użytkownika."
    )
    @is_mod_or_admin()
    @discord.app_commands.describe(
        user="Użytkownik do odwyciszenia",
        reason="Powód usunięcia timeout'u"
    )
    async def untimeout(
        self,
        ctx: commands.Context,
        user: discord.Member,
        *,
        reason: str = "Brak powodu"
    ):
        """Remove timeout from a user."""
        try:
            await user.timeout(None, reason=f"{reason} (przez {ctx.author})")
            
            embed = discord.Embed(
                title="✅ Timeout usunięty",
                description=f"Timeout został usunięty dla {user.mention}",
                color=discord.Color.green()
            )
            embed.add_field(name="Powód", value=reason, inline=True)
            embed.add_field(name="Moderator", value=ctx.author.mention, inline=True)
            
            await ctx.send(embed=embed)
            
        except discord.Forbidden:
            await ctx.send("❌ Nie mam uprawnień do usunięcia timeout'u temu użytkownikowi.")
        except Exception as e:
            logger.error(f"Error removing timeout: {e}")
            await ctx.send(f"❌ Wystąpił błąd: {str(e)}")
    
    @commands.command(
        name="userid", description="Wyświetla ID użytkownika o podanej nazwie"
    )
    @is_mod_or_admin()
    async def user_id(self, ctx: commands.Context, *, name: str):
        """Display user ID by name."""
        matching_members = []
        
        # Search for matching members
        for member in ctx.guild.members:
            if name.lower() in member.name.lower() or (
                member.nick and name.lower() in member.nick.lower()
            ):
                matching_members.append(member)
        
        if not matching_members:
            await ctx.send(f"Nie znaleziono użytkowników pasujących do nazwy '{name}'.")
            return
        
        # Display all matching IDs
        result = "Znaleziono następujących użytkowników:\n"
        for member in matching_members[:10]:  # Limit to 10 results
            result += f"- **{member.name}** (ID: `{member.id}`)\n"
        
        if len(matching_members) > 10:
            result += f"\nPokazano 10 z {len(matching_members)} pasujących użytkowników."
        
        await ctx.send(result)
    
    @commands.command(
        name="mutehistory", description="Wyświetla historię mute'ów użytkownika"
    )
    @is_mod_or_admin()
    async def mute_history(
        self, ctx: commands.Context, user: discord.Member, limit: int = 10
    ):
        """Display mute history for a user."""
        if limit > 50:
            limit = 50
        
        try:
            async with self.bot.get_db() as session:
                # Get mute history
                history = await ModerationLogQueries.get_user_mute_history(
                    session, user.id, limit
                )
                
                if not history:
                    embed = discord.Embed(
                        title="Historia mute'ów",
                        description=f"Użytkownik {user.mention} nie ma żadnych akcji moderatorskich w historii.",
                        color=discord.Color.green(),
                    )
                    await ctx.reply(embed=embed)
                    return
                
                # Create embed with history
                embed = discord.Embed(
                    title=f"Historia mute'ów - {user.display_name}",
                    description=f"Ostatnie {len(history)} akcji moderatorskich",
                    color=user.color or discord.Color.blue(),
                )
                embed.set_thumbnail(url=user.display_avatar.url)
                
                # Add history fields (max 25 fields per embed)
                for i, log in enumerate(history[:25]):
                    action_emoji = "🔇" if log.action_type == "mute" else "🔓"
                    
                    # Format duration
                    duration_text = "Permanentne"
                    if log.duration_seconds:
                        hours, remainder = divmod(log.duration_seconds, 3600)
                        minutes, seconds = divmod(remainder, 60)
                        if hours > 0:
                            duration_text = f"{hours}h {minutes}m"
                        elif minutes > 0:
                            duration_text = f"{minutes}m"
                        else:
                            duration_text = f"{seconds}s"
                    
                    # Format mute type
                    mute_type_text = log.mute_type.upper() if log.mute_type else "N/A"
                    
                    field_value = (
                        f"**Typ:** {mute_type_text}\n"
                        f"**Moderator:** <@{log.moderator_id}>\n"
                        f"**Czas:** {duration_text if log.action_type == 'mute' else 'N/A'}\n"
                        f"**Data:** {discord.utils.format_dt(log.created_at, 'f')}"
                    )
                    
                    embed.add_field(
                        name=f"{action_emoji} {log.action_type.upper()} #{len(history) - i}",
                        value=field_value,
                        inline=True,
                    )
                
                if len(history) > 25:
                    embed.add_field(
                        name="ℹ️ Informacja",
                        value=f"Pokazano 25 z {len(history)} akcji. Użyj mniejszego limitu dla nowszych akcji.",
                        inline=False,
                    )
                
                await ctx.reply(embed=embed)
                
        except Exception as e:
            logger.error(
                f"Error retrieving mute history for user {user.id}: {e}", exc_info=True
            )
            await ctx.send("Wystąpił błąd podczas pobierania historii mute'ów.")
    
    @commands.command(
        name="mutestats", description="Wyświetla statystyki mute'ów z serwera"
    )
    @is_mod_or_admin()
    async def mute_stats(self, ctx: commands.Context, days: int = 30):
        """Display server mute statistics."""
        if days > 365:
            days = 365
        
        try:
            async with self.bot.get_db() as session:
                stats = await ModerationLogQueries.get_mute_statistics(session, days)
                
                # Create embed with statistics
                embed = discord.Embed(
                    title="📊 Statystyki mute'ów",
                    description=f"Podsumowanie z ostatnich {days} dni",
                    color=discord.Color.orange(),
                    timestamp=datetime.now(timezone.utc),
                )
                
                # General statistics
                embed.add_field(
                    name="📋 Ogólne",
                    value=f"**Całkowite mute'y:** {stats['total_mutes']}",
                    inline=False,
                )
                
                # Statistics by mute type
                if stats["mute_types"]:
                    types_text = ""
                    for mute_type, count in stats["mute_types"].items():
                        types_text += f"**{mute_type.upper()}:** {count}\n"
                    
                    embed.add_field(
                        name="🏷️ Według typu",
                        value=types_text or "Brak danych",
                        inline=True,
                    )
                
                # Top muted users
                if stats["top_muted_users"]:
                    users_text = ""
                    for i, (user_id, count) in enumerate(
                        stats["top_muted_users"][:5], 1
                    ):
                        users_text += f"{i}. <@{user_id}> - {count} mute'ów\n"
                    
                    embed.add_field(
                        name="👤 Najczęściej mutowani",
                        value=users_text or "Brak danych",
                        inline=True,
                    )
                
                # Top moderators
                if stats["top_moderators"]:
                    mods_text = ""
                    for i, (mod_id, count) in enumerate(stats["top_moderators"][:5], 1):
                        mods_text += f"{i}. <@{mod_id}> - {count} akcji\n"
                    
                    embed.add_field(
                        name="👮 Najaktywniejszi moderatorzy",
                        value=mods_text or "Brak danych",
                        inline=True,
                    )
                
                await ctx.reply(embed=embed)
                
        except Exception as e:
            logger.error(
                f"Error retrieving mute statistics: {e}", exc_info=True
            )
            await ctx.send("Wystąpił błąd podczas pobierania statystyk.")
    
    @commands.command(name="voiceunmute", hidden=True)
    @is_owner_or_admin()
    async def voice_unmute(self, ctx: commands.Context, user: discord.Member):
        """Force unmute user in voice channel (owner/admin only)."""
        try:
            if user.voice and user.voice.channel:
                await user.edit(mute=False)
                await ctx.send(f"✅ Odciszono {user.mention} na kanale głosowym.")
            else:
                await ctx.send(f"❌ {user.mention} nie jest na kanale głosowym.")
        except discord.Forbidden:
            await ctx.send("❌ Nie mam uprawnień do odciszenia tego użytkownika.")
        except Exception as e:
            logger.error(f"Error in voice unmute: {e}")
            await ctx.send(f"❌ Wystąpił błąd: {str(e)}")
    
    @commands.command(name="voicemute", hidden=True)
    @is_owner_or_admin()
    async def voice_mute(self, ctx: commands.Context, user: discord.Member):
        """Force mute user in voice channel (owner/admin only)."""
        try:
            if user.voice and user.voice.channel:
                await user.edit(mute=True)
                await ctx.send(f"✅ Wyciszono {user.mention} na kanale głosowym.")
            else:
                await ctx.send(f"❌ {user.mention} nie jest na kanale głosowym.")
        except discord.Forbidden:
            await ctx.send("❌ Nie mam uprawnień do wyciszenia tego użytkownika.")
        except Exception as e:
            logger.error(f"Error in voice mute: {e}")
            await ctx.send(f"❌ Wystąpił błąd: {str(e)}")
    
    @commands.command(
        name="mutenick", description="Usuwa niewłaściwy nick użytkownika i nadaje karę."
    )
    @is_mod_or_admin()
    async def mutenick_prefix(self, ctx: commands.Context, user: discord.Member):
        """Usuwa niewłaściwy nick użytkownika i nadaje karę (wersja prefiksowa)."""
        try:
            logger.info(
                f"mutenick command started for user {user.id} ({user.display_name}) by {ctx.author.id}"
            )

            # Sprawdź aktualny nick przed rozpoczęciem
            default_nick = self.bot.config.get("default_mute_nickname", "random")
            original_nick = user.nick or user.name
            logger.info(
                f"User {user.id} original nick: '{original_nick}', target nick: '{default_nick}'"
            )

            # Wykonaj standardową logikę mutenick
            async with self.bot.get_db() as session:
                moderation_service = await self.bot.get_service(IModerationService, session)
                await moderation_service.mute_member(
                    target=user,
                    moderator=ctx.author,
                    mute_type="nick",
                    reason="Niewłaściwy nick",
                    channel_id=ctx.channel.id
                )
                await session.commit()

            # Dodatkowe sprawdzenie po 3 sekundach, czy nick został faktycznie ustawiony
            import asyncio
            await asyncio.sleep(3)

            # Pobierz świeży obiekt użytkownika
            updated_user = ctx.guild.get_member(user.id)
            if updated_user:
                current_nick = updated_user.nick or updated_user.name
                logger.info(f"After mutenick, user {user.id} nick is: '{current_nick}'")

                # Sprawdź czy nick to faktycznie "random"
                if current_nick != default_nick:
                    logger.warning(
                        f"Nick verification failed for user {user.id}: expected '{default_nick}', got '{current_nick}'. Attempting to fix..."
                    )
                    try:
                        await updated_user.edit(
                            nick=default_nick,
                            reason="Wymuszenie poprawnego nicku mutenick - weryfikacja",
                        )
                        logger.info(
                            f"Successfully enforced nick '{default_nick}' for user {user.id}"
                        )
                    except Exception as e:
                        logger.error(f"Failed to enforce nick for user {user.id}: {e}")

            # Użyj oryginalnej nazwy użytkownika w wiadomości
            await ctx.send(f"✅ Nadano karę mutenick dla **{original_nick}** ({user.name}#{user.discriminator})")

        except Exception as e:
            logger.error(f"Error in mutenick command: {e}")
            await ctx.send(f"❌ Wystąpił błąd podczas mutenick: {str(e)}")