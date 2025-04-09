"""Moduł do zarządzania wyciszeniami użytkowników.

Moduł zawiera klasy i funkcje służące do zarządzania wyciszeniami użytkowników
na serwerze Discord.
"""

import asyncio
import logging
import re
from datetime import datetime, timedelta, timezone
from typing import Optional

import discord
from discord.ext import commands

from datasources.queries import MemberQueries, RoleQueries
from utils.message_sender import MessageSender
from utils.moderation.mute_type import MuteType

logger = logging.getLogger(__name__)


class MuteManager:
    """Zarządza wyciszeniami użytkowników.

    Klasa odpowiedzialna za logikę wyciszania i odciszania użytkowników,
    w tym zarządzanie rolami wyciszenia i bazą danych.
    """

    def __init__(self, bot):
        """Inicjalizuje menedżera wyciszeń.

        :param bot: Instancja bota Discord.
        :type bot: discord.ext.commands.Bot
        """
        self.bot = bot
        self.config = bot.config
        self.message_sender = MessageSender(bot)

    async def mute_user(self, ctx, user, mute_type_name, duration=None):
        """Wycisza użytkownika.

        :param ctx: Kontekst komendy.
        :type ctx: discord.ext.commands.Context
        :param user: Użytkownik do wyciszenia.
        :type user: discord.Member
        :param mute_type_name: Nazwa typu wyciszenia.
        :type mute_type_name: str
        :param duration: Czas trwania wyciszenia (opcjonalnie).
        :type duration: Optional[timedelta]
        """
        mute_type = MuteType.from_name(mute_type_name)
        await self._handle_mute_logic(ctx, user, mute_type, duration, unmute=False)

    async def unmute_user(self, ctx, user, mute_type_name):
        """Odcisza użytkownika.

        :param ctx: Kontekst komendy.
        :type ctx: discord.ext.commands.Context
        :param user: Użytkownik do odciszenia.
        :type user: discord.Member
        :param mute_type_name: Nazwa typu wyciszenia.
        :type mute_type_name: str
        """
        mute_type = MuteType.from_name(mute_type_name)
        await self._handle_mute_logic(ctx, user, mute_type, unmute=True)

    async def _handle_mute_logic(
        self,
        ctx: commands.Context,
        user: discord.Member,
        mute_type: MuteType,
        duration: Optional[timedelta] = None,
        unmute: bool = False,
    ):
        """Wspólna logika do obsługi różnych typów wyciszeń.

        :param ctx: Kontekst komendy.
        :type ctx: discord.ext.commands.Context
        :param user: Użytkownik do wyciszenia/odciszenia.
        :type user: discord.Member
        :param mute_type: Obiekt typu wyciszenia.
        :type mute_type: MuteType
        :param duration: Czas trwania wyciszenia (None dla permanentnego).
        :type duration: Optional[timedelta]
        :param unmute: Czy to jest operacja odciszenia.
        :type unmute: bool
        """
        try:
            # Check if target is a moderator or admin
            has_mod_role = discord.utils.get(user.roles, id=self.config["admin_roles"]["mod"])
            has_admin_role = discord.utils.get(user.roles, id=self.config["admin_roles"]["admin"])

            # Only admins can mute mods, and nobody can mute admins
            if has_admin_role:
                action = "zarządzać" if unmute else "zablokować"
                await ctx.send(f"Nie możesz {action} uprawnień administratora.")
                return

            if has_mod_role and not discord.utils.get(
                ctx.author.roles, id=self.config["admin_roles"]["admin"]
            ):
                action = "zarządzać" if unmute else "zablokować"
                await ctx.send(f"Tylko administrator może {action} uprawnienia moderatora.")
                return

            # Get role ID based on config
            role_index = mute_type.role_index
            mute_role_id = self.config["mute_roles"][role_index]["id"]
            mute_role = discord.Object(id=mute_role_id)

            if unmute:
                # Remove mute role
                await user.remove_roles(mute_role, reason=mute_type.reason_remove)

                # Remove role from database
                async with self.bot.get_db() as session:
                    # Upewnij się, że użytkownik istnieje w tabeli members
                    await MemberQueries.get_or_add_member(session, user.id)

                    await RoleQueries.delete_member_role(session, user.id, mute_role_id)
                    await session.commit()

                # Format success message
                message = mute_type.success_message_remove.format(
                    user_mention=user.mention,
                    action_name=mute_type.action_name,
                    premium_channel=self.config["channels"]["premium_info"],
                )
            else:
                # Apply mute

                # Remove color roles if present
                color_roles = [
                    discord.Object(id=role_id) for role_id in self.config["color_roles"].values()
                ]
                await user.remove_roles(*color_roles, reason=mute_type.reason_add)

                # Add mute role
                await user.add_roles(mute_role, reason=mute_type.reason_add)

                # Set default duration if not specified and the mute type supports it
                if duration is None and mute_type.supports_duration:
                    duration = mute_type.default_duration

                # Save punishment in database
                async with self.bot.get_db() as session:
                    # Upewnij się, że użytkownik istnieje w tabeli members
                    await MemberQueries.get_or_add_member(session, user.id)

                    # Check if there's an existing mute with longer duration
                    existing_role = await RoleQueries.get_member_role(
                        session, user.id, mute_role_id
                    )

                    if existing_role and existing_role.expiration_date and duration is not None:
                        time_left = existing_role.expiration_date - datetime.now(timezone.utc)
                        if time_left > duration:
                            # Keep the existing longer duration
                            message = f"Użytkownik {user.mention} posiada już dłuższą blokadę. Obecna kara wygaśnie za {time_left.days}d {time_left.seconds//3600}h {(time_left.seconds//60)%60}m."
                            await ctx.send(message)
                            return

                    await RoleQueries.add_or_update_role_to_member(
                        session, user.id, mute_role_id, duration=duration
                    )
                    await session.commit()

                # Format duration text
                if duration is None:
                    duration_text = "stałe"
                else:
                    # Format duration for user-friendly display
                    duration_text = ""
                    if duration.days > 0:
                        duration_text += f"{duration.days}d "
                    hours, remainder = divmod(duration.seconds, 3600)
                    minutes, seconds = divmod(remainder, 60)
                    if hours > 0:
                        duration_text += f"{hours}h "
                    if minutes > 0:
                        duration_text += f"{minutes}m "
                    if seconds > 0 or not duration_text:
                        duration_text += f"{seconds}s"

                # Format success message
                message = mute_type.success_message_add.format(
                    user_mention=user.mention,
                    duration_text=duration_text,
                    action_name=mute_type.action_name,
                    premium_channel=self.config["channels"]["premium_info"],
                )

                # Execute special actions for this mute type
                await self._execute_special_actions(ctx, user, mute_type)

            # Add premium info to message
            _, premium_text = MessageSender._get_premium_text(ctx)
            if premium_text:
                message = f"{message}\n{premium_text}"

            # Send response
            if mute_type.type_name == MuteType.NICK and not unmute:
                # For nick mute, use reply instead of embed
                await ctx.reply(message)
            else:
                # For other mutes, use embed
                embed = discord.Embed(description=message, color=ctx.author.color)
                await ctx.reply(embed=embed)

        except discord.Forbidden as e:
            action = "odblokowania" if unmute else "blokowania"
            logger.error(
                f"Permission error during {action} {mute_type.type_name} for user {user.id}: {e}",
                exc_info=True,
            )
            await ctx.send(f"Brak uprawnień do {action} użytkownika.")
        except discord.HTTPException as e:
            action = "odblokowania" if unmute else "blokowania"
            logger.error(
                f"Discord API error during {action} {mute_type.type_name} for user {user.id}: {e}",
                exc_info=True,
            )
            await ctx.send(f"Wystąpił błąd Discord API podczas {action}.")
        except Exception as e:
            action = "odblokowania" if unmute else "blokowania"
            logger.error(
                f"Error handling {action} {mute_type.type_name} for user {user.id}: {e}",
                exc_info=True,
            )
            await ctx.send(f"Wystąpił błąd podczas {action}.")

    async def _execute_special_actions(self, ctx, user, mute_type):
        """Wykonuje specjalne akcje dla danego typu wyciszenia.

        :param ctx: Kontekst komendy.
        :type ctx: discord.ext.commands.Context
        :param user: Użytkownik, na którym wykonywane są akcje.
        :type user: discord.Member
        :param mute_type: Obiekt typu wyciszenia.
        :type mute_type: MuteType
        """
        special_actions = mute_type.special_actions

        if "change_nickname" in special_actions:
            # Wait 5 seconds before changing nickname
            await asyncio.sleep(5)
            try:
                await user.edit(nick="random", reason="Niewłaściwy nick")
            except discord.Forbidden:
                await ctx.reply("Nie mogę zmienić nicku tego użytkownika.")
            except Exception as e:
                logger.error(f"Error changing nickname for user {user.id}: {e}")
                await ctx.reply("Wystąpił błąd podczas zmiany nicku.")

        # Check if user needs to be moved to AFK and back to force stream permission update
        if "move_to_afk_and_back" in special_actions and user.voice and user.voice.channel:
            try:
                # Get the AFK channel ID from config
                afk_channel_id = self.config["channels_voice"]["afk"]
                afk_channel = self.bot.get_channel(afk_channel_id)

                if afk_channel:
                    # Remember original channel
                    original_channel = user.voice.channel

                    # Move to AFK
                    await user.move_to(
                        afk_channel,
                        reason=f"Wymuszenie aktualizacji uprawnień {mute_type.action_name}",
                    )
                    logger.info(f"Moved user {user.id} to AFK channel for stream permission update")

                    # Wait a moment for Discord to register the move
                    await asyncio.sleep(1)

                    # Move back to original channel
                    await user.move_to(
                        original_channel,
                        reason=f"Powrót po aktualizacji uprawnień {mute_type.action_name}",
                    )
                    logger.info(
                        f"Moved user {user.id} back to original channel {original_channel.id}"
                    )
            except discord.Forbidden:
                logger.warning(f"No permission to move user {user.id} between voice channels")
            except Exception as e:
                logger.error(f"Error moving user {user.id} for stream permission update: {e}")

    def parse_duration(self, duration_str: str) -> Optional[timedelta]:
        """Parsuje ciąg znakowy reprezentujący czas trwania do obiektu timedelta.

        Obsługiwane formaty:
        - Pusty ciąg lub None - traktowany jako permanentny (zwraca None)
        - Sama liczba (np. "1") - traktowana jako godziny
        - Jednostki czasu (np. "1h", "30m", "1d")
        - Kombinacja (np. "1h30m")

        :param duration_str: String reprezentujący czas trwania.
        :type duration_str: str
        :returns: Obiekt timedelta lub None dla permanentnego.
        :rtype: Optional[timedelta]
        """
        if duration_str is None or duration_str.strip() == "":
            return None  # None indicates permanent mute

        # If it's just a number, treat as hours
        if duration_str.isdigit():
            return timedelta(hours=int(duration_str))

        # Try to parse complex duration
        total_seconds = 0
        pattern = r"(\d+)([dhms])"
        matches = re.findall(pattern, duration_str.lower())

        if not matches:
            # If no valid format found, default to 1 hour
            logger.warning(f"Invalid duration format: {duration_str}, using default 1 hour")
            return timedelta(hours=1)

        for value, unit in matches:
            if unit == "d":
                total_seconds += int(value) * 86400  # days to seconds
            elif unit == "h":
                total_seconds += int(value) * 3600  # hours to seconds
            elif unit == "m":
                total_seconds += int(value) * 60  # minutes to seconds
            elif unit == "s":
                total_seconds += int(value)  # seconds

        return timedelta(seconds=total_seconds)
