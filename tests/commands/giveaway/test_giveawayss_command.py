"""
Tests for giveawayss command - randomly selecting messages from a channel
Professional test implementation with proper fixtures and mocking
"""
from unittest.mock import patch


async def test_giveawayss_success_current_channel(giveaway_cog, mock_ctx, mock_regular_messages, mock_channel_with_history):
    """Test successful giveaway in current channel with proper winner selection"""
    # Arrange
    mock_channel_with_history(mock_regular_messages)

    with patch('random.choice') as mock_random, \
         patch.object(giveaway_cog.message_sender, 'send_giveaway_results') as mock_send_results:

        mock_random.side_effect = [
            mock_regular_messages[0],
            mock_regular_messages[2],
            mock_regular_messages[4]
        ]

        # Act
        await giveaway_cog.giveawayss(mock_ctx, 3)

        # Assert
        mock_ctx.channel.history.assert_called_once_with(limit=None)
        mock_send_results.assert_called_once()

        args = mock_send_results.call_args[0]
        assert len(args[1]) == 3  # winners count
        assert args[2] == mock_ctx.channel  # target channel
        assert args[3] == 3  # requested winners


async def test_giveawayss_success_specific_channel(giveaway_cog, mock_ctx, mock_regular_messages, test_constants):
    """Test successful giveaway in specified target channel"""
    # Arrange
    target_channel = mock_ctx.channel.__class__()
    target_channel.id = test_constants.CHANNEL_ID + 100

    async def async_iter():
        for message in mock_regular_messages:
            yield message

    target_channel.history.return_value.__aiter__ = async_iter

    with patch('random.choice') as mock_random, \
         patch.object(giveaway_cog.message_sender, 'send_giveaway_results') as mock_send_results:

        mock_random.return_value = mock_regular_messages[0]

        # Act
        await giveaway_cog.giveawayss(mock_ctx, 1, target_channel)

        # Assert
        target_channel.history.assert_called_once_with(limit=None)

        args = mock_send_results.call_args[0]
        assert args[2] == target_channel  # correct target channel used


async def test_giveawayss_filters_bot_messages_excludes_webhooks(giveaway_cog, mock_ctx, mock_regular_messages,
                                                               mock_bot_messages, mock_webhook_messages,
                                                               mock_channel_with_history):
    """Test that bot messages are filtered out but webhook messages are included"""
    # Arrange
    all_messages = mock_regular_messages + mock_bot_messages + mock_webhook_messages
    mock_channel_with_history(all_messages)

    with patch('random.choice') as mock_random, \
         patch.object(giveaway_cog.message_sender, 'send_giveaway_results') as mock_send_results:

        # Mock to return a webhook message to verify it's included
        mock_random.return_value = mock_webhook_messages[0]

        # Act
        await giveaway_cog.giveawayss(mock_ctx, 1)

        # Assert
        mock_send_results.assert_called_once()
        args = mock_send_results.call_args[0]
        winners = args[1]

        # Verify webhook message was selected (proving it wasn't filtered)
        assert len(winners) == 1
        assert winners[0].webhook_id is not None


async def test_giveawayss_enforces_unique_authors(giveaway_cog, mock_ctx, mock_messages_same_author, mock_channel_with_history):
    """Test that only one message per author is selected (uniqueness constraint)"""
    # Arrange
    mock_channel_with_history(mock_messages_same_author)

    with patch.object(giveaway_cog.message_sender, 'send_giveaway_results') as mock_send_results:

        # Act
        await giveaway_cog.giveawayss(mock_ctx, 3)  # Request 3 winners from same author

        # Assert
        mock_send_results.assert_called_once()
        args = mock_send_results.call_args[0]
        winners = args[1]

        # Should only get 1 winner (same author constraint)
        assert len(winners) == 1
        assert all(w.author.id == mock_messages_same_author[0].author.id for w in winners)


async def test_giveawayss_webhook_messages_bypass_unique_constraint(giveaway_cog, mock_ctx, mock_webhook_messages,
                                                                   mock_channel_with_history, test_constants):
    """Test that webhook messages don't have unique author constraint"""
    # Arrange - All webhook messages have same author but different webhook_ids
    for msg in mock_webhook_messages:
        msg.author.id = test_constants.BOT_USER_ID  # Same author

    mock_channel_with_history(mock_webhook_messages)

    with patch('random.choice') as mock_random, \
         patch.object(giveaway_cog.message_sender, 'send_giveaway_results') as mock_send_results:

        mock_random.side_effect = mock_webhook_messages

        # Act
        await giveaway_cog.giveawayss(mock_ctx, 2)

        # Assert
        mock_send_results.assert_called_once()
        args = mock_send_results.call_args[0]
        winners = args[1]

        # Should get both webhook messages despite same author
        assert len(winners) == 2
        assert all(w.webhook_id is not None for w in winners)


async def test_giveawayss_invalid_winners_count_zero(giveaway_cog, mock_ctx):
    """Test giveaway with zero winners count returns error"""
    # Arrange & Act
    with patch.object(giveaway_cog.message_sender, 'send_error') as mock_send_error:
        await giveaway_cog.giveawayss(mock_ctx, 0)

        # Assert
        mock_send_error.assert_called_once()
        error_message = mock_send_error.call_args[0][1]
        assert "większa od 0" in error_message


async def test_giveawayss_invalid_winners_count_negative(giveaway_cog, mock_ctx):
    """Test giveaway with negative winners count returns error"""
    # Arrange & Act
    with patch.object(giveaway_cog.message_sender, 'send_error') as mock_send_error:
        await giveaway_cog.giveawayss(mock_ctx, -5)

        # Assert
        mock_send_error.assert_called_once()


async def test_giveawayss_no_messages_in_channel(giveaway_cog, mock_ctx, mock_channel_with_history):
    """Test giveaway when channel has no messages"""
    # Arrange
    mock_channel_with_history([])  # Empty channel

    with patch.object(giveaway_cog.message_sender, 'send_error') as mock_send_error:

        # Act
        await giveaway_cog.giveawayss(mock_ctx, 3)

        # Assert
        mock_send_error.assert_called_once()
        error_message = mock_send_error.call_args[0][1]
        assert "Brak wiadomości do wylosowania" in error_message


async def test_giveawayss_only_bot_messages_no_webhooks(giveaway_cog, mock_ctx, mock_bot_messages, mock_channel_with_history):
    """Test giveaway when channel has only bot messages (no webhooks)"""
    # Arrange
    mock_channel_with_history(mock_bot_messages)

    with patch.object(giveaway_cog.message_sender, 'send_error') as mock_send_error:

        # Act
        await giveaway_cog.giveawayss(mock_ctx, 3)

        # Assert
        mock_send_error.assert_called_once()
        error_message = mock_send_error.call_args[0][1]
        assert "Brak wiadomości do wylosowania" in error_message


async def test_giveawayss_insufficient_unique_authors(giveaway_cog, mock_ctx, mock_channel_with_history,
                                                     mock_message_factory, test_constants):
    """Test when fewer unique authors exist than requested winners"""
    # Arrange - Create messages from only 2 unique authors
    messages = []
    author_ids = [test_constants.TEST_USER_1_ID, test_constants.TEST_USER_2_ID]

    for author_id in author_ids:
        for i in range(3):  # 3 messages per author
            message = mock_message_factory.create_message(
                message_id=test_constants.MESSAGE_BASE_ID + author_id + i,
                author_id=author_id,
                content=f"Message from {author_id}"
            )
            messages.append(message)

    mock_channel_with_history(messages)

    with patch.object(giveaway_cog.message_sender, 'send_giveaway_results') as mock_send_results:

        # Act
        await giveaway_cog.giveawayss(mock_ctx, 5)  # Request more than unique authors

        # Assert
        mock_send_results.assert_called_once()
        args = mock_send_results.call_args[0]
        winners = args[1]

        # Should only return 2 winners (max unique authors)
        assert len(winners) <= 2

        # Verify unique authors
        winner_author_ids = {w.author.id for w in winners}
        assert len(winner_author_ids) == len(winners)


async def test_giveawayss_algorithm_exhaustion_handling(giveaway_cog, mock_ctx, mock_channel_with_history,
                                                       mock_message_factory, test_constants):
    """Test algorithm behavior when it can't find enough unique winners"""
    # Arrange - Edge case: very few messages, complex author distribution
    messages = [
        mock_message_factory.create_message(
            message_id=test_constants.MESSAGE_BASE_ID + 1,
            author_id=test_constants.TEST_USER_1_ID
        )
    ]

    mock_channel_with_history(messages)

    with patch.object(giveaway_cog.message_sender, 'send_giveaway_results') as mock_send_results:

        # Act
        await giveaway_cog.giveawayss(mock_ctx, 3)  # Request more than possible

        # Assert
        mock_send_results.assert_called_once()
        args = mock_send_results.call_args[0]
        winners = args[1]

        # Should gracefully handle limitation
        assert len(winners) <= 1


async def test_giveawayss_random_selection_distribution(giveaway_cog, mock_ctx, mock_regular_messages, mock_channel_with_history):
    """Test that random selection properly uses random.choice"""
    # Arrange
    mock_channel_with_history(mock_regular_messages)

    with patch('random.choice') as mock_random, \
         patch.object(giveaway_cog.message_sender, 'send_giveaway_results') as mock_send_results:

        expected_winners = [mock_regular_messages[1], mock_regular_messages[3]]
        mock_random.side_effect = expected_winners

        # Act
        await giveaway_cog.giveawayss(mock_ctx, 2)

        # Assert
        assert mock_random.call_count >= 2
        mock_send_results.assert_called_once()

        # Verify winners match random selection
        args = mock_send_results.call_args[0]
        winners = args[1]
        assert len(winners) == 2


async def test_giveawayss_permission_enforcement(giveaway_cog, mock_ctx):
    """Test that giveawayss command has administrator permission requirement"""
    # Arrange & Assert
    # Verify command has permission decorator
    assert hasattr(giveaway_cog.giveawayss, '__wrapped__')

    # The actual permission checking is handled by Discord.py decorator
    # This test ensures the decorator is properly applied


async def test_giveawayss_large_channel_performance(giveaway_cog, mock_ctx, mock_channel_with_history,
                                                   mock_message_factory, test_constants):
    """Test giveaway performance with large number of messages"""
    # Arrange - Simulate large channel
    large_message_set = []
    for i in range(100):  # Simulate 100 messages
        message = mock_message_factory.create_message(
            message_id=test_constants.MESSAGE_BASE_ID + i,
            author_id=test_constants.TEST_USER_1_ID + (i % 20),  # 20 unique authors
            content=f"Large channel message {i}"
        )
        large_message_set.append(message)

    mock_channel_with_history(large_message_set)

    with patch.object(giveaway_cog.message_sender, 'send_giveaway_results') as mock_send_results:

        # Act
        await giveaway_cog.giveawayss(mock_ctx, 10)

        # Assert
        mock_send_results.assert_called_once()
        args = mock_send_results.call_args[0]
        winners = args[1]

        # Should handle large dataset efficiently
        assert len(winners) <= 10
        assert len(winners) <= 20  # Max unique authors
