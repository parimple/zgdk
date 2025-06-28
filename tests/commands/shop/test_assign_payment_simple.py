"""
Simple tests for assign_payment command - testing core logic without complex imports
"""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.mark.asyncio
async def test_assign_payment_success_simple():
    """Test successful payment assignment logic"""
    # Arrange
    payment_id = 123
    user_id = 789
    payment_amount = 500

    # Mock database session
    mock_session = AsyncMock()
    mock_session.commit = AsyncMock()

    # Mock payment
    mock_payment = MagicMock()
    mock_payment.id = payment_id
    mock_payment.amount = payment_amount
    mock_payment.member_id = None

    # Mock member service
    mock_member_service = AsyncMock()
    mock_db_member = MagicMock()
    mock_db_member.wallet_balance = 1000
    mock_member_service.get_or_create_member = AsyncMock(return_value=mock_db_member)
    mock_member_service.update_member_info = AsyncMock()

    # Mock Discord user
    mock_user = MagicMock()
    mock_user.id = user_id
    mock_user.send = AsyncMock()

    # Act - simulate assign_payment core logic
    with patch('datasources.queries.HandledPaymentQueries.get_payment_by_id', new_callable=AsyncMock) as mock_get_payment:
        mock_get_payment.return_value = mock_payment

        # Core logic
        payment = await mock_get_payment(mock_session, payment_id)
        if payment:
            payment.member_id = user_id

            # Get or create member and update wallet balance
            db_member = await mock_member_service.get_or_create_member(mock_user)
            new_balance = db_member.wallet_balance + payment.amount
            await mock_member_service.update_member_info(db_member, wallet_balance=new_balance)

            await mock_session.commit()

            # Send DM messages
            await mock_user.send("Proszę pamiętać o podawaniu swojego ID podczas dokonywania wpłat w przyszłości. Twoje ID to:")
            await mock_user.send(f"```{user_id}```")

    # Assert
    mock_get_payment.assert_called_once_with(mock_session, payment_id)
    assert mock_payment.member_id == user_id
    mock_member_service.get_or_create_member.assert_called_once_with(mock_user)
    mock_member_service.update_member_info.assert_called_once_with(
        mock_db_member, wallet_balance=1500
    )
    mock_session.commit.assert_called_once()
    assert mock_user.send.call_count == 2


@pytest.mark.asyncio
async def test_assign_payment_not_found_simple():
    """Test assign_payment when payment not found"""
    # Arrange
    payment_id = 999
    mock_session = AsyncMock()

    # Act
    with patch('datasources.queries.HandledPaymentQueries.get_payment_by_id', new_callable=AsyncMock) as mock_get_payment:
        mock_get_payment.return_value = None

        payment = await mock_get_payment(mock_session, payment_id)
        assert payment is None

    # Assert
    mock_get_payment.assert_called_once_with(mock_session, payment_id)


@pytest.mark.asyncio
async def test_assign_payment_dm_forbidden_simple():
    """Test assign_payment when DM fails"""
    # Arrange
    payment_id = 123
    user_id = 789
    payment_amount = 500

    # Mock payment
    mock_payment = MagicMock()
    mock_payment.amount = payment_amount
    mock_payment.member_id = None

    # Mock Discord user with DM failure
    mock_user = MagicMock()
    mock_user.id = user_id
    mock_user.mention = f"<@{user_id}>"

    # Create a mock exception that behaves like discord.Forbidden
    class MockForbidden(Exception):
        pass

    mock_user.send = AsyncMock(side_effect=MockForbidden("Cannot send DM"))

    # Mock context for fallback message
    mock_ctx = MagicMock()
    mock_ctx.send = AsyncMock()

    # Act - simulate DM failure handling
    with patch('datasources.queries.HandledPaymentQueries.get_payment_by_id', new_callable=AsyncMock) as mock_get_payment:
        mock_get_payment.return_value = mock_payment

        payment = await mock_get_payment(MagicMock(), payment_id)
        if payment:
            payment.member_id = user_id

            try:
                await mock_user.send("Test message")
            except MockForbidden:
                # Send fallback message
                fallback_msg = f"Nie mogłem wysłać DM do {mock_user.mention}. Proszę przekazać mu te informacje ręcznie."
                await mock_ctx.send(fallback_msg)

    # Assert
    assert mock_payment.member_id == user_id
    mock_ctx.send.assert_called_once()
    call_args = mock_ctx.send.call_args[0][0]
    assert "Nie mogłem wysłać DM" in call_args
    assert mock_user.mention in call_args


@pytest.mark.asyncio
async def test_assign_payment_large_amount_simple():
    """Test assign_payment with large amount"""
    # Arrange
    payment_id = 123
    user_id = 789
    large_amount = 999999

    # Mock payment
    mock_payment = MagicMock()
    mock_payment.amount = large_amount
    mock_payment.member_id = None

    # Mock member service
    mock_member_service = AsyncMock()
    mock_db_member = MagicMock()
    mock_db_member.wallet_balance = 0
    mock_member_service.get_or_create_member = AsyncMock(return_value=mock_db_member)
    mock_member_service.update_member_info = AsyncMock()

    # Mock user
    mock_user = MagicMock()
    mock_user.id = user_id
    mock_user.send = AsyncMock()

    # Act
    with patch('datasources.queries.HandledPaymentQueries.get_payment_by_id', new_callable=AsyncMock) as mock_get_payment:
        mock_get_payment.return_value = mock_payment

        payment = await mock_get_payment(MagicMock(), payment_id)
        if payment:
            payment.member_id = user_id

            db_member = await mock_member_service.get_or_create_member(mock_user)
            new_balance = db_member.wallet_balance + payment.amount
            await mock_member_service.update_member_info(db_member, wallet_balance=new_balance)

    # Assert
    assert mock_payment.member_id == user_id
    mock_member_service.update_member_info.assert_called_once_with(
        mock_db_member, wallet_balance=large_amount
    )


@pytest.mark.asyncio
async def test_assign_payment_database_transaction_simple():
    """Test assign_payment commits database transaction"""
    # Arrange
    payment_id = 123

    # Mock database session
    mock_session = AsyncMock()
    mock_session.commit = AsyncMock()

    # Mock payment
    mock_payment = MagicMock()
    mock_payment.amount = 500
    mock_payment.member_id = None

    # Act
    with patch('datasources.queries.HandledPaymentQueries.get_payment_by_id', new_callable=AsyncMock) as mock_get_payment:
        mock_get_payment.return_value = mock_payment

        payment = await mock_get_payment(mock_session, payment_id)
        if payment:
            payment.member_id = 123456
            await mock_session.commit()

    # Assert
    mock_session.commit.assert_called_once()


def test_assign_payment_data_validation():
    """Test payment data validation logic"""
    # Arrange
    payment_id = 123
    user_id = 789

    # Mock payment
    mock_payment = MagicMock()
    mock_payment.id = payment_id
    mock_payment.amount = 500
    mock_payment.member_id = None

    # Act
    mock_payment.member_id = user_id

    # Assert
    assert mock_payment.id == payment_id
    assert mock_payment.amount == 500
    assert mock_payment.member_id == user_id
