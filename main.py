#!/usr/bin/env python
"""
Main file for Zagadka bot.
"""

import logging
import os
import subprocess
from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator, Optional

import discord
import yaml
from discord.ext import commands
from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from core.containers.service_container import ServiceContainer
from core.interfaces.messaging_interfaces import (
    IEmbedBuilder,
    IMessageFormatter,
    IMessageSender,
    INotificationService,
)
from core.interfaces.member_interfaces import (
    IActivityService,
    IInviteService,
    IMemberService,
    IModerationService,
)
from core.interfaces.premium_interfaces import (
    IPaymentProcessor,
    IPremiumService,
)
from core.interfaces.role_interfaces import IRoleService
from core.repositories.activity_repository import ActivityRepository
from core.repositories.invite_repository import InviteRepository
from core.repositories.member_repository import MemberRepository
from core.repositories.premium_repository import PaymentRepository, PremiumRepository
from core.repositories.role_repository import RoleRepository
from core.services.embed_builder_service import EmbedBuilderService
from core.services.member_service import (
    ActivityService,
    InviteService,
    MemberService,
    ModerationService,
)
from core.services.message_formatter_service import MessageFormatterService
from core.services.message_sender_service import MessageSenderService
from core.services.notification_service import NotificationService
from core.services.payment_processor_service import PaymentProcessorService
from core.services.premium_service import PremiumService
from core.services.role_service import RoleService
from datasources.models import Base
from utils.premium import PaymentData

intents = discord.Intents.all()


def load_config() -> dict[str, Any]:
    with open("config.yml", encoding="utf-8") as f:
        return yaml.safe_load(f)


def cleanup_zombie_processes() -> None:
    """Cleanup zombie processes from previous Playwright sessions"""
    try:
        # Kill all headless_shell processes
        subprocess.run(
            ["pkill", "-f", "headless_shell"], capture_output=True, timeout=5
        )

        # Kill orphaned Chrome processes
        subprocess.run(
            ["pkill", "-f", "chrome.*--headless"], capture_output=True, timeout=5
        )

        # Wait a moment for processes to terminate
        import time

        time.sleep(0.5)

        # Force kill if still running
        subprocess.run(
            ["pkill", "-9", "-f", "headless_shell"], capture_output=True, timeout=3
        )
        subprocess.run(
            ["pkill", "-9", "-f", "chrome.*--headless"], capture_output=True, timeout=3
        )

        logging.info("Cleaned up zombie browser processes")
    except subprocess.TimeoutExpired:
        logging.warning("Timeout during browser process cleanup")
    except FileNotFoundError:
        logging.debug("pkill command not found - skipping browser cleanup")
    except subprocess.SubprocessError as e:
        logging.warning(f"Subprocess error during zombie process cleanup: {e}")
    except Exception as e:
        logging.error(f"Unexpected error during zombie process cleanup: {e}")


class Zagadka(commands.Bot):
    """Bot class."""

    def __init__(self, config: dict[str, Any], **kwargs: Any) -> None:
        load_dotenv()

        self.test: bool = kwargs.get("test", False)
        self.config: dict[str, Any] = config

        guild_id = config.get("guild_id")
        if guild_id is None:
            raise ValueError("guild_id is required in config")
        self.guild_id: int = guild_id
        
        self.donate_url: str = config.get("donate_url", "")
        self.channels: dict[str, int] = config.get("channels", {})

        self.guild: Optional[discord.Guild] = None
        self.invites: dict[str, discord.Invite] = {}

        database_url = self.get_database_url()

        self.engine = create_async_engine(
            database_url,
            pool_size=20,
            max_overflow=40,
            pool_timeout=30,
            pool_recycle=1800,
            pool_pre_ping=True,
        )
        self.SessionLocal = async_sessionmaker(
            self.engine, class_=AsyncSession, expire_on_commit=False
        )
        self.base = Base
        self.payment_data_class = PaymentData

        # Initialize service container
        self.service_container = ServiceContainer()
        self._setup_services()

        prefix = config.get("prefix")
        if prefix is None:
            raise ValueError("prefix is required in config")

        super().__init__(
            command_prefix=prefix,
            intents=intents,
            status=discord.Status.do_not_disturb,
            allowed_mentions=discord.AllowedMentions.all(),
            **kwargs,
        )

    def get_database_url(self) -> str:
        postgres_user: str = os.environ.get("POSTGRES_USER", "")
        postgres_password: str = os.environ.get("POSTGRES_PASSWORD", "")
        postgres_db: str = os.environ.get("POSTGRES_DB", "")
        postgres_port: str = os.environ.get("POSTGRES_PORT", "")

        return (
            f"postgresql+asyncpg://"
            f"{postgres_user}:"
            f"{postgres_password}@db:"
            f"{postgres_port}/"
            f"{postgres_db}"
        )

    @asynccontextmanager
    async def get_db(self) -> AsyncGenerator[AsyncSession, None]:
        async with self.SessionLocal() as session:
            try:
                yield session
                await session.commit()
            except Exception as e:
                await session.rollback()
                logging.error(f"Database session error: {e}")
                raise

    def _setup_services(self) -> None:
        """Setup dependency injection container with services."""

        # Register messaging services as singletons (stateless)
        embed_builder = EmbedBuilderService()
        message_formatter = MessageFormatterService()

        self.service_container.register_singleton(IEmbedBuilder, embed_builder)
        self.service_container.register_singleton(IMessageFormatter, message_formatter)

        # Note: Repository and service factories are handled in get_service method
        # since they require session and complex dependency injection

    async def get_service(
        self, service_type: type, session: Optional[AsyncSession] = None
    ) -> Any:
        """Get a service instance with optional database session."""

        # Services that don't need database session
        if service_type in [IEmbedBuilder, IMessageFormatter]:
            return self.service_container.get_service(service_type)

        # Services that need database session
        if session is None:
            raise ValueError(
                f"Service {service_type.__name__} requires a database session"
            )

        if service_type == IRoleService:
            # Create repository with session
            role_repository = RoleRepository(session)
            # Create unit of work
            unit_of_work = self.service_container.create_unit_of_work(session)
            # Create service with dependencies
            return RoleService(
                role_repository=role_repository, unit_of_work=unit_of_work
            )

        elif service_type == IMessageSender:
            # Create unit of work (needed for BaseService)
            unit_of_work = self.service_container.create_unit_of_work(session)
            return MessageSenderService(unit_of_work=unit_of_work)

        elif service_type == INotificationService:
            # Get dependencies
            embed_builder = self.service_container.get_service(IEmbedBuilder)
            unit_of_work = self.service_container.create_unit_of_work(session)
            message_sender = MessageSenderService(unit_of_work=unit_of_work)

            return NotificationService(
                embed_builder=embed_builder,
                message_sender=message_sender,
                unit_of_work=unit_of_work,
            )

        elif service_type == IPremiumService:
            # Create repositories
            premium_repository = PremiumRepository(session)
            payment_repository = PaymentRepository(session)
            unit_of_work = self.service_container.create_unit_of_work(session)

            # Create premium service
            premium_service = PremiumService(
                premium_repository=premium_repository,
                payment_repository=payment_repository,
                bot=self,
                unit_of_work=unit_of_work,
            )

            # Set guild if available
            if self.guild:
                premium_service.set_guild(self.guild)

            return premium_service

        elif service_type == IPaymentProcessor:
            # Create dependencies
            payment_repository = PaymentRepository(session)
            unit_of_work = self.service_container.create_unit_of_work(session)

            # Create payment processor
            payment_processor = PaymentProcessorService(
                payment_repository=payment_repository,
                unit_of_work=unit_of_work,
            )

            # Set premium service to avoid circular dependency
            premium_service = await self.get_service(IPremiumService, session)
            payment_processor.set_premium_service(premium_service)

            return payment_processor

        elif service_type == IMemberService:
            # Create repositories
            member_repository = MemberRepository(session)
            activity_repository = ActivityRepository(session)
            invite_repository = InviteRepository(session)
            unit_of_work = self.service_container.create_unit_of_work(session)

            return MemberService(
                member_repository=member_repository,
                activity_repository=activity_repository,
                invite_repository=invite_repository,
                unit_of_work=unit_of_work,
            )

        elif service_type == IActivityService:
            # Create repositories
            activity_repository = ActivityRepository(session)
            member_repository = MemberRepository(session)
            unit_of_work = self.service_container.create_unit_of_work(session)

            return ActivityService(
                activity_repository=activity_repository,
                member_repository=member_repository,
                unit_of_work=unit_of_work,
            )

        elif service_type == IModerationService:
            # Create repositories
            moderation_repository = ModerationRepository(session)
            member_repository = MemberRepository(session)
            unit_of_work = self.service_container.create_unit_of_work(session)

            return ModerationService(
                moderation_repository=moderation_repository,
                member_repository=member_repository,
                unit_of_work=unit_of_work,
            )

        elif service_type == IInviteService:
            # Create repositories
            invite_repository = InviteRepository(session)
            member_repository = MemberRepository(session)
            unit_of_work = self.service_container.create_unit_of_work(session)

            return InviteService(
                invite_repository=invite_repository,
                member_repository=member_repository,
                unit_of_work=unit_of_work,
            )

        # For other services, use the container
        return self.service_container.get_service(service_type)

    async def close(self) -> None:
        await self.engine.dispose()
        await super().close()

    async def load_cogs(self) -> None:
        """Load all cogs"""
        logging.info("Loading cogs...")
        for folder in ("cogs/commands", "cogs/events"):
            path = os.path.join(os.getcwd(), folder)
            for cog in os.listdir(path):
                if cog.endswith(".py") and cog != "__init__.py":
                    try:
                        await self.load_extension(
                            f"{folder.replace('/', '.')}.{cog[:-3]}"
                        )
                        logging.info("Loaded cog: %s", cog)
                    except commands.ExtensionAlreadyLoaded:
                        logging.warning("Cog %s is already loaded", cog)
                    except commands.ExtensionNotFound:
                        logging.error("Cog %s not found", cog)
                    except commands.NoEntryPointError:
                        logging.error("Cog %s has no setup function", cog)
                    except commands.ExtensionFailed as error:
                        logging.error("Failed to load cog %s: %s", cog, error)
                    except Exception as error:
                        logging.error("Unexpected error loading cog %s: %s", cog, error)

    async def setup_hook(self) -> None:
        """Setup hook."""
        if not self.test:
            await self.load_cogs()

    async def on_ready(self) -> None:
        """On ready event"""
        logging.info("Event on_ready started")

        async with self.engine.begin() as conn:
            table_names = self.base.metadata.tables.keys()
            logging.info("Creating tables: %s", ", ".join(table_names))
            # await conn.run_sync(self.base.metadata.drop_all)
            await conn.run_sync(self.base.metadata.create_all)

        logging.info("Database create_all completed")

        await self.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.playing, name="zaGadka bot"
            )
        )
        logging.info("Event change_presence completed")

        if self.guild is None:
            # Get the guild object and assign it to self.guild
            guild = self.get_guild(self.guild_id)
            if guild is None:
                logging.error("Cannot find a guild with the ID %d.", self.guild_id)
            else:
                logging.info("Found guild: %s", guild.name)
                self.guild = guild

        if not self.test:
            await self.tree.sync(guild=discord.Object(id=self.guild_id))
            logging.info("Slash commands synchronized")

        logging.info("Ready")

    def run(self) -> None:
        """Run the bot"""
        token = os.environ.get("ZAGADKA_TOKEN")
        if token is None:
            raise ValueError(
                "Missing bot token. Ensure that ZAGADKA_TOKEN is set in the environment variables."
            )
        super().run(token, reconnect=True)

    @property
    def force_channel_notifications(self):
        """Get global notification setting"""
        return self.config.get("force_channel_notifications", True)

    @force_channel_notifications.setter
    def force_channel_notifications(self, value: bool):
        """Set global notification setting"""
        self.config["force_channel_notifications"] = value


def setup_logging() -> None:
    """Setup logging"""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


if __name__ == "__main__":
    setup_logging()

    # Cleanup zombie processes before starting
    cleanup_zombie_processes()

    config = load_config()
    bot = Zagadka(config=config)
    bot.run()
