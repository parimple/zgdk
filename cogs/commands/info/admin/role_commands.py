"""Admin commands for managing roles and premium roles."""

import logging
from datetime import datetime, timezone

import discord
from discord.ext import commands

from datasources.queries import RoleQueries
from utils.message_sender import MessageSender
from utils.permissions import is_admin
from utils.premium import PremiumManager

from .helpers import remove_premium_role_mod_permissions

logger = logging.getLogger(__name__)


class RoleCommands(commands.Cog):
    """Commands for managing roles."""

    def __init__(self, bot):
        self.bot = bot

    @commands.command(
        name="checkroles", description="Sprawdza role użytkownika w logach."
    )
    @is_admin()
    async def check_roles(self, ctx: commands.Context, user: discord.Member):
        """Sprawdza role użytkownika w logach."""
        async with self.bot.get_db() as session:
            # Pobierz wszystkie role użytkownika z bazy
            db_roles = await RoleQueries.get_member_roles(session, user.id)

            embed = discord.Embed(
                title=f"Role użytkownika {user.display_name}",
                color=discord.Color.blue(),
            )

            # Role w bazie danych
            if db_roles:
                db_text = "\n".join(
                    [
                        f"- Role ID: {role.role_id}, Expires: {role.expiration_date if role.expiration_date else 'Never'}"
                        for role in db_roles
                    ]
                )
                embed.add_field(
                    name="Role w bazie danych", value=db_text[:1024], inline=False
                )
            else:
                embed.add_field(
                    name="Role w bazie danych", value="Brak ról w bazie", inline=False
                )

            # Role na serwerze
            server_roles = [role.name for role in user.roles if role.name != "@everyone"]
            if server_roles:
                embed.add_field(
                    name="Role na serwerze",
                    value=", ".join(server_roles)[:1024],
                    inline=False,
                )
            else:
                embed.add_field(
                    name="Role na serwerze", value="Brak ról", inline=False
                )

            await ctx.send(embed=embed)

    @commands.command(name="force_check_user_premium_roles", aliases=["fcpr"])
    @is_admin()
    async def force_check_user_premium_roles(
        self, ctx: commands.Context, user: discord.Member, mode: str = "check"
    ):
        """
        Ręcznie sprawdza i opcjonalnie usuwa wygasłe role premium użytkownika.

        Parametry:
        - user: Użytkownik do sprawdzenia
        - mode: 'check' (tylko sprawdza) lub 'remove' (sprawdza i usuwa wygasłe)
        """
        logger.info(
            f"Admin {ctx.author} is force checking premium roles for {user} (mode: {mode})"
        )

        if mode not in ["check", "remove"]:
            await ctx.send("Mode musi być 'check' lub 'remove'")
            return

        embed = discord.Embed(
            title=f"Sprawdzanie ról premium: {user.display_name}",
            color=discord.Color.blue(),
            timestamp=datetime.now(timezone.utc),
        )

        premium_manager = PremiumManager(self.bot)
        async with self.bot.get_db() as session:
            # Pobierz role premium użytkownika z bazy
            premium_roles = await RoleQueries.get_member_premium_roles(
                session, user.id
            )

            if not premium_roles:
                embed.description = "Użytkownik nie ma żadnych ról premium w bazie danych."
                embed.color = discord.Color.orange()
                await ctx.send(embed=embed)
                return

            roles_to_remove = []
            roles_info = []

            for role_data in premium_roles:
                role_name = role_data["role_name"]
                expiration = role_data["expiration_date"]
                discord_role = discord.utils.get(ctx.guild.roles, name=role_name)

                status = "✅ Aktywna"
                should_remove = False

                # Sprawdź czy rola wygasła
                if expiration and expiration < datetime.now(timezone.utc):
                    status = "❌ Wygasła"
                    should_remove = True
                    if discord_role and mode == "remove":
                        roles_to_remove.append((discord_role, role_data))

                # Sprawdź czy użytkownik ma rolę na Discordzie
                has_on_discord = discord_role in user.roles if discord_role else False

                roles_info.append(
                    f"**{role_name}**\n"
                    f"└ Status: {status}\n"
                    f"└ Wygasa: {expiration.strftime('%Y-%m-%d %H:%M') if expiration else 'Nigdy'}\n"
                    f"└ Na Discordzie: {'✅ Tak' if has_on_discord else '❌ Nie'}\n"
                    f"└ Do usunięcia: {'🗑️ Tak' if should_remove else '➖ Nie'}"
                )

            embed.add_field(
                name="Role premium w bazie", value="\n\n".join(roles_info), inline=False
            )

            # Jeśli mode = remove, usuń wygasłe role
            if mode == "remove" and roles_to_remove:
                removed_roles = []
                for discord_role, role_data in roles_to_remove:
                    try:
                        # Usuń rolę z Discorda
                        if discord_role in user.roles:
                            await user.remove_roles(
                                discord_role, reason="Wygasła rola premium"
                            )

                        # Usuń z bazy danych
                        await RoleQueries.delete_member_role(
                            session, user.id, role_data["role_id"]
                        )

                        # Usuń uprawnienia związane z rolą premium
                        await remove_premium_role_mod_permissions(
                            session, self.bot, user.id
                        )

                        removed_roles.append(role_data["role_name"])
                        logger.info(
                            f"Removed expired premium role {role_data['role_name']} from user {user.id}"
                        )

                    except Exception as e:
                        logger.error(
                            f"Error removing role {role_data['role_name']} from user {user.id}: {e}"
                        )

                await session.commit()

                if removed_roles:
                    embed.add_field(
                        name="Usunięte role",
                        value=", ".join(removed_roles),
                        inline=False,
                    )
                    embed.color = discord.Color.green()

                    # Wyślij powiadomienie do użytkownika
                    await MessageSender.send_premium_expired_notification(
                        self.bot, user, removed_roles
                    )
                else:
                    embed.add_field(
                        name="Wynik",
                        value="Nie usunięto żadnych ról",
                        inline=False,
                    )

            # Sprawdź role na Discordzie, których nie ma w bazie
            discord_premium_roles = ["zG50", "zG100", "zG500", "zG1000"]
            orphaned_roles = []
            
            for role_name in discord_premium_roles:
                discord_role = discord.utils.get(ctx.guild.roles, name=role_name)
                if discord_role and discord_role in user.roles:
                    # Sprawdź czy jest w bazie
                    has_in_db = any(
                        role_data["role_name"] == role_name for role_data in premium_roles
                    )
                    if not has_in_db:
                        orphaned_roles.append(role_name)

            if orphaned_roles:
                embed.add_field(
                    name="⚠️ Role bez wpisu w bazie",
                    value=", ".join(orphaned_roles),
                    inline=False,
                )

        embed.set_footer(
            text=f"Wykonane przez {ctx.author.display_name}",
            icon_url=ctx.author.display_avatar.url,
        )
        await ctx.send(embed=embed)