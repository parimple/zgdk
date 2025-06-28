"""Admin commands for managing and viewing invites."""

import logging
from typing import Literal, Optional

import discord
from discord import app_commands
from discord.ext import commands

from core.repositories import InviteRepository
from utils.permissions import is_admin

from .helpers import InviteInfo
from .views import InviteListView

logger = logging.getLogger(__name__)


class InviteCommands(commands.Cog):
    """Commands for managing server invites."""

    def __init__(self, bot):
        self.bot = bot

    @commands.hybrid_command(
        name="invites",
        description="Wyświetla listę zaproszeń z możliwością sortowania.",
    )
    @is_admin()
    @app_commands.describe(
        sort_by="Pole do sortowania (uses, created_at, last_used)",
        order="Kolejność sortowania (desc lub asc)",
        target="Użytkownik, którego zaproszenia chcesz wyświetlić",
    )
    async def list_invites(
        self,
        ctx: commands.Context,
        sort_by: Optional[Literal["uses", "created_at", "last_used"]] = "last_used",
        order: Optional[Literal["desc", "asc"]] = "desc",
        target: Optional[discord.Member] = None,
    ):
        """
        Wyświetla listę zaproszeń z możliwością sortowania.

        :param ctx: Kontekst komendy
        :param sort_by: Pole do sortowania (uses, created_at, last_used)
        :param order: Kolejność sortowania (desc lub asc)
        :param target: Opcjonalny użytkownik do filtrowania zaproszeń
        """
        logger.info(f"Admin {ctx.author} requested invite list (sort_by={sort_by}, order={order}, target={target})")

        async with self.bot.get_db() as session:
            # Pobierz wszystkie zaproszenia z bazy
            invite_repo = InviteRepository(session)
            all_invites = await invite_repo.get_all_invites()

            # Filtruj po użytkowniku jeśli podano
            if target:
                all_invites = [inv for inv in all_invites if inv.creator_id == target.id]

            # Stwórz listę InviteInfo
            invite_infos = []
            for inv in all_invites:
                creator = ctx.guild.get_member(inv.creator_id) if inv.creator_id else None
                invite_infos.append(InviteInfo(inv.__dict__, creator))

            # Utwórz widok
            view = InviteListView(ctx, invite_infos, sort_by, order)
            embed = view.create_embed()
            await ctx.send(embed=embed, view=view)
