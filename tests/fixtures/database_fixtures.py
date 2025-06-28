"""
Database fixtures for testing
"""
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from datasources.models import Activity, HandledPayment, Invite, Member, MemberRole, Role
from datasources.models.base import Base
from tests.data.test_constants import ROLE_ZG50_ID, ROLE_ZG100_ID, TEST_USER_1_ID, TEST_USER_2_ID, WALLET_BALANCES


@pytest.fixture
def database_url():
    """In-memory SQLite database URL for testing"""
    return "sqlite+aiosqlite:///:memory:"


@pytest.fixture
async def async_engine(database_url):
    """Create async engine for testing"""
    engine = create_async_engine(
        database_url,
        echo=False,  # Set to True for SQL debugging
        future=True
    )

    # Create all tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    # Cleanup
    await engine.dispose()


@pytest.fixture
async def async_session_factory(async_engine):
    """Create async session factory"""
    return sessionmaker(
        bind=async_engine,
        class_=AsyncSession,
        expire_on_commit=False
    )


@pytest.fixture
async def mock_empty_db_session(async_session_factory):
    """Create empty test database session"""
    session = async_session_factory()
    yield session
    await session.rollback()
    await session.close()


@pytest.fixture
async def mock_db_session_with_data(async_session_factory, default_database_items):
    """Create test database session with default data"""
    session = async_session_factory()

    # Add default items
    for item in default_database_items:
        session.add(item)

    await session.commit()

    yield session

    await session.rollback()
    await session.close()


@pytest.fixture
def default_database_items():
    """Default database items for testing"""
    now = datetime.now(timezone.utc)

    items = []

    # Create test members
    member1 = Member(
        id=TEST_USER_1_ID,
        wallet_balance=WALLET_BALANCES["medium"],
        first_inviter_id=None,
        current_inviter_id=None,
        joined_at=now
    )
    items.append(member1)

    member2 = Member(
        id=TEST_USER_2_ID,
        wallet_balance=WALLET_BALANCES["high"],
        first_inviter_id=TEST_USER_1_ID,
        current_inviter_id=TEST_USER_1_ID,
        joined_at=now
    )
    items.append(member2)

    # Create test roles
    role1 = Role(
        id=ROLE_ZG50_ID,
        name="zG50",
        role_type="premium"
    )
    items.append(role1)

    role2 = Role(
        id=ROLE_ZG100_ID,
        name="zG100",
        role_type="premium"
    )
    items.append(role2)

    # Create test member roles (premium assignments)
    member_role1 = MemberRole(
        member_id=TEST_USER_1_ID,
        role_id=ROLE_ZG50_ID,
        expiration_date=datetime(2025, 12, 31, tzinfo=timezone.utc)
    )
    items.append(member_role1)

    # Create test activities
    activity1 = Activity(
        member_id=TEST_USER_1_ID,
        date=now,
        activity_type="text",
        points=500
    )
    items.append(activity1)

    activity2 = Activity(
        member_id=TEST_USER_2_ID,
        date=now,
        activity_type="voice",
        points=800
    )
    items.append(activity2)

    # Create test payment
    payment1 = HandledPayment(
        member_id=TEST_USER_1_ID,
        name="Test Payment",
        amount=WALLET_BALANCES["zg50_price"],
        paid_at=now,
        payment_type="role_purchase"
    )
    items.append(payment1)

    # Create test invite
    invite1 = Invite(
        id="TEST123",
        creator_id=TEST_USER_1_ID,
        uses=5,
        created_at=now,
        last_used_at=None
    )
    items.append(invite1)

    return items


@pytest.fixture
def mock_async_session():
    """Mock async session for unit tests that don't need real database"""
    session = AsyncMock(spec=AsyncSession)
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.close = AsyncMock()
    session.add = MagicMock()
    session.delete = MagicMock()
    session.execute = AsyncMock()
    session.scalar = AsyncMock()
    session.scalars = AsyncMock()
    session.refresh = AsyncMock()
    session.merge = AsyncMock()
    return session


@pytest.fixture
def mock_database_context_manager(mock_async_session):
    """Mock database context manager for bot.get_db()"""
    context_manager = AsyncMock()
    context_manager.__aenter__ = AsyncMock(return_value=mock_async_session)
    context_manager.__aexit__ = AsyncMock(return_value=None)
    return context_manager


@pytest.fixture
def sample_member_data():
    """Sample member data for testing"""
    return {
        "id": TEST_USER_1_ID,
        "wallet_balance": WALLET_BALANCES["medium"],
        "first_inviter_id": None,
        "current_inviter_id": None
    }


@pytest.fixture
def sample_payment_data():
    """Sample payment data for testing"""
    return {
        "member_id": TEST_USER_1_ID,
        "name": "Test Payment",
        "amount": 500,
        "payment_type": "role_purchase",
        "paid_at": datetime.now(timezone.utc)
    }


@pytest.fixture
def sample_activity_data():
    """Sample activity data for testing"""
    from datetime import datetime, timezone
    return {
        "member_id": TEST_USER_1_ID,
        "date": datetime.now(timezone.utc),
        "activity_type": "text",
        "points": 100
    }


@pytest.fixture
def sample_premium_role_data():
    """Sample premium role assignment data"""
    return {
        "member_id": TEST_USER_1_ID,
        "role_id": ROLE_ZG50_ID,
        "expiration_date": datetime(2025, 12, 31, tzinfo=timezone.utc)
    }


# Database query fixtures for common operations
@pytest.fixture
def mock_member_queries():
    """Mock member database queries"""
    queries = MagicMock()

    # Mock get_member_by_discord_id
    member = MagicMock()
    member.discord_id = TEST_USER_1_ID
    member.wallet_balance = WALLET_BALANCES["medium"]
    member.total_activity_points = 1000
    queries.get_member_by_discord_id = AsyncMock(return_value=member)

    # Mock create_member
    queries.create_member = AsyncMock(return_value=member)

    # Mock update_member_balance
    queries.update_member_balance = AsyncMock()

    return queries


@pytest.fixture
def mock_payment_queries():
    """Mock payment database queries"""
    queries = MagicMock()

    # Mock get_payment_by_id
    payment = MagicMock()
    payment.id = 123
    payment.member_id = None
    payment.amount = 500
    queries.get_payment_by_id = AsyncMock(return_value=payment)

    # Mock add_payment
    queries.add_payment = AsyncMock()

    # Mock get_last_payments
    payments = [payment]
    queries.get_last_payments = AsyncMock(return_value=payments)

    return queries


@pytest.fixture
def mock_role_queries():
    """Mock role database queries"""
    queries = MagicMock()

    # Mock get_member_premium_roles
    role_data = {
        "role_id": ROLE_ZG50_ID,
        "role_name": "zG50",
        "expiration_date": datetime(2025, 12, 31, tzinfo=timezone.utc),
        "is_active": True
    }
    queries.get_member_premium_roles = AsyncMock(return_value=[role_data])

    # Mock assign_premium_role
    queries.assign_premium_role = AsyncMock()

    # Mock remove_premium_role
    queries.remove_premium_role = AsyncMock()

    return queries
