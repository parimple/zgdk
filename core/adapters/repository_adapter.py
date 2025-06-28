"""
Adapter to bridge between old query classes and new repositories.

This allows gradual migration from queries to repositories without breaking existing code.
"""

import logging
from typing import TypeVar

from sqlalchemy.ext.asyncio import AsyncSession

from core.repositories import (
    ActivityRepository,
    AutoKickRepository,
    ChannelRepository,
    InviteRepository,
    MemberRepository,
    MessageRepository,
    ModerationRepository,
    NotificationRepository,
    PaymentRepository,
    RoleRepository,
)

logger = logging.getLogger(__name__)

T = TypeVar("T")


class RepositoryAdapter:
    """Adapter to provide query-like interface using repositories."""

    # Mapping of query classes to repository classes
    QUERY_TO_REPO_MAP = {
        "ActivityQueries": ActivityRepository,
        "AutoKickQueries": AutoKickRepository,
        "ChannelPermissionQueries": ChannelRepository,
        "InviteQueries": InviteRepository,
        "MemberQueries": MemberRepository,
        "MessageQueries": MessageRepository,
        "ModerationQueries": ModerationRepository,
        "NotificationLogQueries": NotificationRepository,
        "PaymentQueries": PaymentRepository,
        "HandledPaymentQueries": PaymentRepository,
        "RoleQueries": RoleRepository,
    }

    @classmethod
    def get_repository(cls, query_class_name: str, session: AsyncSession):
        """Get repository instance for a query class.

        Args:
            query_class_name: Name of the query class (e.g., "MemberQueries")
            session: Database session

        Returns:
            Repository instance

        Raises:
            ValueError: If query class not mapped to a repository
        """
        repo_class = cls.QUERY_TO_REPO_MAP.get(query_class_name)
        if not repo_class:
            raise ValueError(f"No repository mapped for {query_class_name}")

        return repo_class(session)

    @classmethod
    def create_query_adapter(cls, query_class_name: str):
        """Create a query-like adapter class that uses repositories internally.

        This creates a class with static methods that match the query interface
        but use repositories under the hood.

        Args:
            query_class_name: Name of the query class to adapt

        Returns:
            Adapter class with static methods
        """
        repo_class = cls.QUERY_TO_REPO_MAP.get(query_class_name)
        if not repo_class:
            raise ValueError(f"No repository mapped for {query_class_name}")

        class QueryAdapter:
            """Adapter providing query-like static methods using repositories."""

            @staticmethod
            async def _get_repo(session: AsyncSession):
                """Get repository instance."""
                return repo_class(session)

        # Add specific adapters based on query class
        if query_class_name == "MemberQueries":
            cls._add_member_query_methods(QueryAdapter)
        elif query_class_name == "RoleQueries":
            cls._add_role_query_methods(QueryAdapter)
        elif query_class_name == "PaymentQueries":
            cls._add_payment_query_methods(QueryAdapter)
        elif query_class_name == "HandledPaymentQueries":
            cls._add_handled_payment_query_methods(QueryAdapter)
        elif query_class_name == "MessageQueries":
            cls._add_message_query_methods(QueryAdapter)
        # Add more as needed

        return QueryAdapter

    @staticmethod
    def _add_member_query_methods(adapter_class):
        """Add MemberQueries compatible methods."""

        @staticmethod
        async def get_or_add_member(session: AsyncSession, member_id: int, **kwargs):
            repo = MemberRepository(session)
            return await repo.get_or_add_member(member_id, **kwargs)

        @staticmethod
        async def get_member(session: AsyncSession, member_id: int):
            repo = MemberRepository(session)
            return await repo.get_member(member_id)

        @staticmethod
        async def add_member(session: AsyncSession, member_id: int):
            repo = MemberRepository(session)
            return await repo.create_member(discord_id=member_id)

        @staticmethod
        async def add_to_wallet_balance(session: AsyncSession, member_id: int, amount: int):
            repo = MemberRepository(session)
            return await repo.add_to_wallet_balance(member_id, amount)

        @staticmethod
        async def get_voice_bypass_status(session: AsyncSession, member_id: int):
            repo = MemberRepository(session)
            return await repo.get_voice_bypass_status(member_id)

        @staticmethod
        async def add_bypass_time(session: AsyncSession, member_id: int, hours: int):
            repo = MemberRepository(session)
            return await repo.add_bypass_time(member_id, hours)

        @staticmethod
        async def extend_voice_bypass(session: AsyncSession, member_id: int, duration):
            repo = MemberRepository(session)
            return await repo.extend_voice_bypass(member_id, duration)

        @staticmethod
        async def clear_voice_bypass(session: AsyncSession, member_id: int):
            repo = MemberRepository(session)
            return await repo.clear_voice_bypass(member_id)

        @staticmethod
        async def get_all_members(session: AsyncSession):
            repo = MemberRepository(session)
            return await repo.get_all_members()

        # Add methods to adapter class
        adapter_class.get_or_add_member = get_or_add_member
        adapter_class.get_member = get_member
        adapter_class.add_member = add_member
        adapter_class.add_to_wallet_balance = add_to_wallet_balance
        adapter_class.get_voice_bypass_status = get_voice_bypass_status
        adapter_class.add_bypass_time = add_bypass_time
        adapter_class.extend_voice_bypass = extend_voice_bypass
        adapter_class.clear_voice_bypass = clear_voice_bypass
        adapter_class.get_all_members = get_all_members

    @staticmethod
    def _add_role_query_methods(adapter_class):
        """Add RoleQueries compatible methods."""

        @staticmethod
        async def add_or_update_role_to_member(session: AsyncSession, member_id: int, role_id: int, duration=None):
            repo = RoleRepository(session)
            return await repo.add_role_to_member(member_id, role_id, duration)

        @staticmethod
        async def get_member_roles(session: AsyncSession, member_id: int):
            repo = RoleRepository(session)
            return await repo.get_member_roles(member_id)

        @staticmethod
        async def delete_member_role(session: AsyncSession, member_id: int, role_id: int):
            repo = RoleRepository(session)
            return await repo.remove_role_from_member(member_id, role_id)

        # Add methods to adapter class
        adapter_class.add_or_update_role_to_member = add_or_update_role_to_member
        adapter_class.get_member_roles = get_member_roles
        adapter_class.delete_member_role = delete_member_role

    @staticmethod
    def _add_payment_query_methods(adapter_class):
        """Add PaymentQueries compatible methods."""

        @staticmethod
        async def add_payment(session: AsyncSession, **kwargs):
            repo = PaymentRepository(session)
            return await repo.create_payment(**kwargs)

        @staticmethod
        async def get_payment_by_id(session: AsyncSession, payment_id: str):
            repo = PaymentRepository(session)
            return await repo.get_by_id(payment_id)

        @staticmethod
        async def assign_payment_to_user(session: AsyncSession, payment_id: str, user_id: int):
            repo = PaymentRepository(session)
            return await repo.assign_to_user(payment_id, user_id)

        @staticmethod
        async def get_last_payments(session: AsyncSession, limit: int = 10, offset: int = 0, payment_type: str = None):
            repo = PaymentRepository(session)
            return await repo.get_recent_payments(limit=limit, offset=offset, payment_type=payment_type)

        # Add methods to adapter class
        adapter_class.add_payment = add_payment
        adapter_class.get_payment_by_id = get_payment_by_id
        adapter_class.assign_payment_to_user = assign_payment_to_user
        adapter_class.get_last_payments = get_last_payments

    @staticmethod
    def _add_message_query_methods(adapter_class):
        """Add MessageQueries compatible methods."""

        @staticmethod
        async def save_message(
            session: AsyncSession,
            message_id: int,
            author_id: int,
            content: str,
            timestamp,
            channel_id: int,
            reply_to_message_id=None,
        ):
            repo = MessageRepository(session)
            return await repo.save_message(
                message_id=message_id,
                author_id=author_id,
                content=content,
                timestamp=timestamp,
                channel_id=channel_id,
                reply_to_message_id=reply_to_message_id,
            )

        # Add methods to adapter class
        adapter_class.save_message = save_message

    @staticmethod
    def _add_handled_payment_query_methods(adapter_class):
        """Add HandledPaymentQueries compatible methods."""

        @staticmethod
        async def add_payment(
            session: AsyncSession,
            member_id,
            name: str,
            amount: int,
            paid_at,
            payment_type: str,
        ):
            repo = PaymentRepository(session)
            return await repo.add_payment(
                member_id=member_id, name=name, amount=amount, paid_at=paid_at, payment_type=payment_type
            )

        @staticmethod
        async def get_last_payments(
            session: AsyncSession,
            offset: int = 0,
            limit: int = 10,
            payment_type=None,
        ):
            repo = PaymentRepository(session)
            return await repo.get_last_payments(offset=offset, limit=limit, payment_type=payment_type)

        @staticmethod
        async def add_member_id_to_payment(session: AsyncSession, payment_id: int, member_id: int):
            repo = PaymentRepository(session)
            return await repo.add_member_id_to_payment(payment_id, member_id)

        @staticmethod
        async def get_payment_by_id(session: AsyncSession, payment_id: int):
            repo = PaymentRepository(session)
            return await repo.get_payment_by_id(payment_id)

        @staticmethod
        async def get_payment_by_name_and_amount(session: AsyncSession, name: str, amount: int):
            repo = PaymentRepository(session)
            return await repo.get_payment_by_name_and_amount(name, amount)

        # Add methods to adapter class
        adapter_class.add_payment = add_payment
        adapter_class.get_last_payments = get_last_payments
        adapter_class.add_member_id_to_payment = add_member_id_to_payment
        adapter_class.get_payment_by_id = get_payment_by_id
        adapter_class.get_payment_by_name_and_amount = get_payment_by_name_and_amount


# Example usage in migration:
# Instead of:
#   from datasources.queries import MemberQueries
#   member = await MemberQueries.get_member(session, member_id)
#
# Use:
#   from core.adapters.repository_adapter import RepositoryAdapter
#   MemberQueries = RepositoryAdapter.create_query_adapter("MemberQueries")
#   member = await MemberQueries.get_member(session, member_id)
#
# Or directly use repository:
#   from core.repositories import MemberRepository
#   repo = MemberRepository(session)
#   member = await repo.get_by_id(member_id)
