"""
Adapter to bridge between old query classes and new repositories.

This allows gradual migration from queries to repositories without breaking existing code.
"""

import logging
from typing import Protocol, TypeVar, Type
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

T = TypeVar('T')


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
        # Add more as needed
        
        return QueryAdapter
    
    @staticmethod
    def _add_member_query_methods(adapter_class):
        """Add MemberQueries compatible methods."""
        
        @staticmethod
        async def get_or_add_member(session: AsyncSession, member_id: int):
            repo = MemberRepository(session)
            return await repo.get_or_create(member_id)
        
        @staticmethod
        async def get_member(session: AsyncSession, member_id: int):
            repo = MemberRepository(session)
            return await repo.get_by_id(member_id)
        
        @staticmethod
        async def add_member(session: AsyncSession, member_id: int):
            repo = MemberRepository(session)
            return await repo.create({"id": member_id})
        
        @staticmethod
        async def get_member_balance(session: AsyncSession, member_id: int):
            repo = MemberRepository(session)
            member = await repo.get_by_id(member_id)
            return member.balance if member else 0
        
        @staticmethod
        async def update_member_balance(session: AsyncSession, member_id: int, amount: int):
            repo = MemberRepository(session)
            return await repo.update_balance(member_id, amount)
        
        # Add methods to adapter class
        adapter_class.get_or_add_member = get_or_add_member
        adapter_class.get_member = get_member
        adapter_class.add_member = add_member
        adapter_class.get_member_balance = get_member_balance
        adapter_class.update_member_balance = update_member_balance
    
    @staticmethod
    def _add_role_query_methods(adapter_class):
        """Add RoleQueries compatible methods."""
        
        @staticmethod
        async def add_or_update_role_to_member(
            session: AsyncSession, 
            member_id: int, 
            role_id: int, 
            duration=None
        ):
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
        async def assign_payment_to_user(
            session: AsyncSession, 
            payment_id: str, 
            user_id: int
        ):
            repo = PaymentRepository(session)
            return await repo.assign_to_user(payment_id, user_id)
        
        @staticmethod
        async def get_last_payments(
            session: AsyncSession, 
            limit: int = 10, 
            offset: int = 0, 
            payment_type: str = None
        ):
            repo = PaymentRepository(session)
            return await repo.get_recent_payments(
                limit=limit, 
                offset=offset, 
                payment_type=payment_type
            )
        
        # Add methods to adapter class
        adapter_class.add_payment = add_payment
        adapter_class.get_payment_by_id = get_payment_by_id
        adapter_class.assign_payment_to_user = assign_payment_to_user
        adapter_class.get_last_payments = get_last_payments


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