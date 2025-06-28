"""Tests for refactored admin info module."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import discord
import pytest
from discord.ext import commands

from cogs.commands.info.admin.admin_info import AdminInfoCog
from cogs.commands.info.admin.helpers import InviteInfo, get_member_active_mutes
from cogs.commands.info.admin.views import InviteListView


class TestAdminHelpers:
    """Test admin helper functions."""

    def test_invite_info_creation(self):
        """Test InviteInfo class creation."""
        invite_data = {
            "code": "ABC123",
            "uses": 5,
            "created_at": datetime.now(timezone.utc),
            "last_used_at": datetime.now(timezone.utc),
            "creator_id": 123456789,
        }

        invite = InviteInfo(invite_data)

        assert invite.code == "ABC123"
        assert invite.uses == 5
        assert invite.creator_id == 123456789
        assert invite.created_at is not None
        assert invite.last_used_at is not None

    def test_get_member_active_mutes(self):
        """Test getting member's active mutes."""
        # Mock guild and member
        guild = MagicMock(spec=discord.Guild)
        member = MagicMock(spec=discord.Member)

        # Create mock mute roles
        mute_img_role = MagicMock(spec=discord.Role)
        mute_img_role.name = "mutedimg"

        mute_txt_role = MagicMock(spec=discord.Role)
        mute_txt_role.name = "mutedtxt"

        # Setup guild.get_role
        def get_role(name=None):
            if name == "mutedimg":
                return mute_img_role
            elif name == "mutedtxt":
                return mute_txt_role
            return None

        guild.roles = [mute_img_role, mute_txt_role]
        discord.utils.get = MagicMock(side_effect=lambda roles, name: get_role(name))

        # Member has mutedimg role
        member.roles = [mute_img_role]

        # Test
        active_mutes = get_member_active_mutes(guild, member)

        assert "mutedimg" in active_mutes
        assert "mutedtxt" not in active_mutes


class TestInviteListView:
    """Test invite list view."""

    @pytest.fixture
    def mock_ctx(self):
        """Create mock context."""
        ctx = MagicMock()
        ctx.author = MagicMock(spec=discord.Member)
        ctx.author.id = 123456
        return ctx

    @pytest.fixture
    def sample_invites(self):
        """Create sample invites."""
        invites = []
        for i in range(15):  # More than one page
            invite_data = {
                "code": f"CODE{i}",
                "uses": i * 10,
                "created_at": datetime.now(timezone.utc),
                "creator_id": 100 + i,
            }
            invites.append(InviteInfo(invite_data))
        return invites

    def test_invite_list_view_creation(self, mock_ctx, sample_invites):
        """Test creating invite list view."""
        view = InviteListView(mock_ctx, sample_invites)

        assert view.ctx == mock_ctx
        assert len(view.invites) == 15
        assert view.page == 0
        assert view.per_page == 10
        assert view.sort_by == "last_used"
        assert view.order == "desc"

    def test_invite_sorting(self, mock_ctx, sample_invites):
        """Test invite sorting."""
        view = InviteListView(mock_ctx, sample_invites, sort_by="uses", order="desc")

        sorted_invites = view._sort_invites()

        # Check that invites are sorted by uses in descending order
        for i in range(len(sorted_invites) - 1):
            assert sorted_invites[i].uses >= sorted_invites[i + 1].uses


class TestAdminInfoCog:
    """Test main admin info cog."""

    @pytest.fixture
    def mock_bot(self):
        """Create a mock bot."""
        bot = MagicMock(spec=commands.Bot)
        bot.get_db = AsyncMock()
        return bot

    @pytest.fixture
    def admin_cog(self, mock_bot):
        """Create admin info cog instance."""
        return AdminInfoCog(mock_bot)

    def test_cog_initialization(self, admin_cog, mock_bot):
        """Test that cog initializes correctly."""
        assert admin_cog.bot == mock_bot

        # Check that it has all command methods
        assert hasattr(admin_cog, "list_invites")
        assert hasattr(admin_cog, "sync")
        assert hasattr(admin_cog, "add_t")
        assert hasattr(admin_cog, "check_roles")
        assert hasattr(admin_cog, "check_status")
        assert hasattr(admin_cog, "force_check_user_premium_roles")

    @pytest.mark.asyncio
    async def test_sync_command(self, admin_cog, mock_bot):
        """Test sync command."""
        # Mock context
        ctx = MagicMock()
        ctx.bot = mock_bot
        ctx.send = AsyncMock()

        # Mock tree sync
        mock_bot.tree.sync = AsyncMock(return_value=[1, 2, 3])  # 3 commands

        # Run sync command
        await admin_cog.sync(ctx)

        # Check that sync was called and message was sent
        mock_bot.tree.sync.assert_called_once()
        ctx.send.assert_called_once_with("Synced 3 commands globally")

    @pytest.mark.asyncio
    async def test_add_t_command(self, admin_cog, mock_bot):
        """Test add bypass time command."""
        # Mock context and user
        ctx = MagicMock()
        ctx.send = AsyncMock()

        user = MagicMock(spec=discord.User)
        user.id = 123456
        user.mention = "<@123456>"

        # Mock database session
        mock_session = MagicMock()
        mock_session.commit = AsyncMock()
        mock_bot.get_db.return_value.__aenter__.return_value = mock_session

        # Mock member with bypass time
        mock_member = MagicMock()
        mock_member.voice_bypass_until = datetime.now(timezone.utc)

        with patch("cogs.commands.info.admin.user_commands.MemberQueries") as mock_queries:
            mock_queries.add_bypass_time = AsyncMock(return_value=mock_member)

            # Run command
            await admin_cog.add_t(ctx, user, 5)

            # Verify
            mock_queries.add_bypass_time.assert_called_once_with(mock_session, 123456, 5)
            mock_session.commit.assert_called_once()
            assert ctx.send.called
