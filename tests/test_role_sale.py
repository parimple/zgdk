"""Tests for the role sale system."""
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import discord
import pytest

from utils.refund import calculate_refund
from utils.role_sale import RoleSaleManager


@pytest.fixture
def mock_bot():
    """Create a mock bot."""
    bot = MagicMock()
    bot.config = {
        "premium_roles": [
            {"name": "zG100", "price": 100},
            {"name": "zG500", "price": 500},
        ]
    }
    # Nie ustawiamy get_db tutaj - pozwolimy testom to kontrolować
    return bot


@pytest.fixture
def mock_member():
    """Create a mock Discord member."""
    member = MagicMock(spec=discord.Member)
    member.id = 123456789
    member.display_name = "TestUser"
    member.roles = []
    return member


@pytest.fixture
def mock_role():
    """Create a mock Discord role."""
    role = MagicMock(spec=discord.Role)
    role.id = 987654321
    role.name = "zG100"
    return role


@pytest.fixture
def mock_interaction():
    """Create a mock Discord interaction."""
    interaction = MagicMock(spec=discord.Interaction)
    return interaction


class TestRoleSaleManager:
    """Test cases for RoleSaleManager."""

    @pytest.mark.asyncio
    async def test_sell_role_success(self, mock_bot, mock_member, mock_role, mock_interaction):
        """Test successful role sale."""
        # Setup
        sale_manager = RoleSaleManager(mock_bot)

        # Mock member has the role
        mock_member.roles = [mock_role]

        # Mock database role
        mock_db_role = MagicMock()
        mock_db_role.expiration_date = datetime.now(timezone.utc) + timedelta(days=15)

        # Create a proper async context manager mock
        mock_session = AsyncMock()
        mock_context_manager = AsyncMock()
        mock_context_manager.__aenter__ = AsyncMock(return_value=mock_session)
        mock_context_manager.__aexit__ = AsyncMock(return_value=False)

        # Mock all the async operations
        with patch("utils.role_sale.RoleQueries") as mock_role_queries, patch(
            "utils.role_sale.MemberQueries"
        ) as mock_member_queries, patch("utils.role_sale.calculate_refund", return_value=50):
            # Setup the database mock - get_db powinno być funkcją zwracającą context manager
            mock_bot.get_db = MagicMock(return_value=mock_context_manager)

            # Mock async queries
            mock_role_queries.get_member_role = AsyncMock(return_value=mock_db_role)
            mock_member_queries.add_to_wallet_balance = AsyncMock()
            mock_member.remove_roles = AsyncMock()

            # Mock SQL execution - session.execute musi być AsyncMock
            mock_result = MagicMock()
            mock_result.rowcount = 1
            mock_session.execute = AsyncMock(return_value=mock_result)
            mock_session.commit = AsyncMock()
            mock_session.rollback = AsyncMock()

            # Mock _remove_premium_privileges
            sale_manager._remove_premium_privileges = AsyncMock()

            # Execute
            success, message, refund = await sale_manager.sell_role(mock_member, mock_role, mock_interaction)

            # Assert
            assert success is True
            assert "Sprzedano rolę zG100 za 50G" in message
            assert refund == 50

            # Verify calls
            mock_member.remove_roles.assert_called_once_with(mock_role)
            mock_member_queries.add_to_wallet_balance.assert_called_once_with(mock_session, mock_member.id, 50)
            mock_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_sell_role_user_doesnt_have_role(self, mock_bot, mock_member, mock_role, mock_interaction):
        """Test selling role when user doesn't have it."""
        sale_manager = RoleSaleManager(mock_bot)

        # Member doesn't have the role
        mock_member.roles = []

        success, message, refund = await sale_manager.sell_role(mock_member, mock_role, mock_interaction)

        assert success is False
        assert "Nie posiadasz tej roli na Discord" in message
        assert refund is None

    @pytest.mark.asyncio
    async def test_sell_role_not_in_database(self, mock_bot, mock_member, mock_role, mock_interaction):
        """Test selling role when it's not in database."""
        sale_manager = RoleSaleManager(mock_bot)

        # Member has the role on Discord
        mock_member.roles = [mock_role]

        # Create a proper async context manager mock
        mock_session = AsyncMock()
        mock_context_manager = AsyncMock()
        mock_context_manager.__aenter__ = AsyncMock(return_value=mock_session)
        mock_context_manager.__aexit__ = AsyncMock(return_value=False)

        with patch("utils.role_sale.RoleQueries") as mock_role_queries:
            # Setup the database mock - get_db powinno być funkcją zwracającą context manager
            mock_bot.get_db = MagicMock(return_value=mock_context_manager)

            # Role not in database - mock as AsyncMock
            mock_role_queries.get_member_role = AsyncMock(return_value=None)

            success, message, refund = await sale_manager.sell_role(mock_member, mock_role, mock_interaction)

            assert success is False
            assert "Nie posiadasz tej roli w bazie danych" in message
            assert refund is None

    @pytest.mark.asyncio
    async def test_sell_role_database_error_rollback(self, mock_bot, mock_member, mock_role, mock_interaction):
        """Test role sale with database error and rollback."""
        sale_manager = RoleSaleManager(mock_bot)

        # Member has the role
        mock_member.roles = [mock_role]

        # Mock database role
        mock_db_role = MagicMock()
        mock_db_role.expiration_date = datetime.now(timezone.utc) + timedelta(days=15)

        # Create a proper async context manager mock
        mock_session = AsyncMock()
        mock_context_manager = AsyncMock()
        mock_context_manager.__aenter__ = AsyncMock(return_value=mock_session)
        mock_context_manager.__aexit__ = AsyncMock(return_value=False)

        with patch("utils.role_sale.RoleQueries") as mock_role_queries, patch(
            "utils.role_sale.calculate_refund", return_value=50
        ):
            # Setup the database mock - get_db powinno być funkcją zwracającą context manager
            mock_bot.get_db = MagicMock(return_value=mock_context_manager)

            # Mock async queries
            mock_role_queries.get_member_role = AsyncMock(return_value=mock_db_role)
            mock_member.remove_roles = AsyncMock()
            mock_member.add_roles = AsyncMock()  # For rollback

            # Mock SQL execution failure - session.execute musi być AsyncMock
            mock_result = MagicMock()
            mock_result.rowcount = 0  # No rows deleted
            mock_session.execute = AsyncMock(return_value=mock_result)
            mock_session.commit = AsyncMock()
            mock_session.rollback = AsyncMock()

            success, message, refund = await sale_manager.sell_role(mock_member, mock_role, mock_interaction)

            assert success is False
            assert "Nie udało się usunąć roli z bazy danych" in message
            assert refund is None

            # Verify rollback
            mock_member.add_roles.assert_called_once_with(mock_role)

    @pytest.mark.asyncio
    async def test_sell_role_invalid_inputs(self, mock_bot, mock_interaction):
        """Test selling role with invalid inputs."""
        sale_manager = RoleSaleManager(mock_bot)

        # Test with None member
        success, message, refund = await sale_manager.sell_role(None, MagicMock(), mock_interaction)
        assert success is False
        assert "Nieprawidłowe dane wejściowe" in message

        # Test with None role
        success, message, refund = await sale_manager.sell_role(MagicMock(), None, mock_interaction)
        assert success is False
        assert "Nieprawidłowe dane wejściowe" in message

    @pytest.mark.asyncio
    async def test_sell_role_config_not_found(self, mock_bot, mock_member, mock_role, mock_interaction):
        """Test selling role when config is not found."""
        sale_manager = RoleSaleManager(mock_bot)

        # Member has the role
        mock_member.roles = [mock_role]

        # Role not in config
        mock_role.name = "UnknownRole"

        success, message, refund = await sale_manager.sell_role(mock_member, mock_role, mock_interaction)

        assert success is False
        assert "Nie można znaleźć konfiguracji roli" in message
        assert refund is None


class TestRefundCalculation:
    """Test cases for refund calculation."""

    def test_calculate_refund_full_time_remaining(self):
        """Test refund calculation with full time remaining."""
        # Use exactly 30 days to ensure precise calculation
        expiration_date = datetime.now(timezone.utc) + timedelta(days=30, hours=12)
        role_price = 100

        refund = calculate_refund(expiration_date, role_price)

        # Should be 50% of price for full month (30 days = 50, 29 days = 48)
        assert refund >= 48  # Allow for small timing differences

    def test_calculate_refund_half_time_remaining(self):
        """Test refund calculation with half time remaining."""
        # Use exactly 15 days to ensure precise calculation
        expiration_date = datetime.now(timezone.utc) + timedelta(days=15, hours=12)
        role_price = 100

        refund = calculate_refund(expiration_date, role_price)

        # Should be 25% of price for half month (15 days = 25, 14 days = 23)
        assert refund >= 23  # Allow for small timing differences

    def test_calculate_refund_expired_role(self):
        """Test refund calculation for expired role."""
        expiration_date = datetime.now(timezone.utc) - timedelta(days=1)
        role_price = 100

        refund = calculate_refund(expiration_date, role_price)

        # Should be 0 for expired role
        assert refund == 0

    def test_calculate_refund_zero_price(self):
        """Test refund calculation with zero price."""
        expiration_date = datetime.now(timezone.utc) + timedelta(days=30)
        role_price = 0

        refund = calculate_refund(expiration_date, role_price)

        assert refund == 0
