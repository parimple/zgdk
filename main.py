#!/usr/bin/env python
"""
Main file for Zagadka bot.
"""

import asyncio
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
from core.interfaces.activity_interfaces import IActivityTrackingService
from core.interfaces.currency_interfaces import ICurrencyService
from core.interfaces.member_interfaces import IActivityService, IInviteService, IMemberService, IModerationService
from core.interfaces.messaging_interfaces import IEmbedBuilder, IMessageFormatter, IMessageSender, INotificationService
from core.interfaces.permission_interfaces import IPermissionService
from core.interfaces.premium_interfaces import IPaymentProcessor, IPremiumService
from core.interfaces.role_interfaces import IRoleService
from core.interfaces.team_interfaces import ITeamManagementService
from core.interfaces.voice_interfaces import IVoiceChannelService, IAutoKickService
from core.repositories.activity_repository import ActivityRepository
from core.repositories.invite_repository import InviteRepository
from core.repositories.member_repository import MemberRepository
from core.repositories.moderation_repository import ModerationRepository
from core.repositories.premium_repository import PaymentRepository, PremiumRepository
from core.repositories.role_repository import RoleRepository
from core.repositories.channel_repository import ChannelRepository
from core.services.activity_tracking_service import ActivityTrackingService
from core.services.currency_service import CurrencyService
from core.services.embed_builder_service import EmbedBuilderService
from core.services.member_service import InviteService, MemberService, ModerationService
from core.services.message_formatter_service import MessageFormatterService
from core.services.message_sender_service import MessageSenderService
from core.services.notification_service import NotificationService
from core.services.payment_processor_service import PaymentProcessorService
from core.services.permission_service import PermissionService
from core.services.premium_service import PremiumService
from core.services.role_service import RoleService
from core.services.team_management_service import TeamManagementService
from core.services.voice_channel_service import VoiceChannelService
from core.services.autokick_service import AutoKickService
from datasources.models import Base
from utils.health_check import HealthCheckServer
from utils.premium import PaymentData

intents = discord.Intents.all()


def load_config() -> dict[str, Any]:
    with open("config.yml", encoding="utf-8") as f:
        return yaml.safe_load(f)


def cleanup_zombie_processes() -> None:
    """Cleanup zombie processes from previous Playwright sessions"""
    try:
        # Kill all headless_shell processes
        subprocess.run(["pkill", "-", "headless_shell"], capture_output=True, timeout=5)

        # Kill orphaned Chrome processes
        subprocess.run(["pkill", "-", "chrome.*--headless"], capture_output=True, timeout=5)

        # Wait a moment for processes to terminate
        import time

        time.sleep(0.5)

        # Force kill if still running
        subprocess.run(["pkill", "-9", "-", "headless_shell"], capture_output=True, timeout=3)
        subprocess.run(["pkill", "-9", "-", "chrome.*--headless"], capture_output=True, timeout=3)

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
        self.SessionLocal = async_sessionmaker(self.engine, class_=AsyncSession, expire_on_commit=False)
        self.base = Base
        self.payment_data_class = PaymentData

        # Initialize service container
        self.service_container = ServiceContainer()
        self._setup_services()

        # Create service manager interface for cogs
        self.service_manager = self

        # Initialize health check server
        self.health_server = HealthCheckServer(self)

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
        postgres_host: str = os.environ.get("POSTGRES_HOST", "db")
        postgres_port: str = os.environ.get("POSTGRES_PORT", "5432")

        return f"postgresql+asyncpg://{postgres_user}:{postgres_password}@{postgres_host}:{postgres_port}/{postgres_db}"

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

    @asynccontextmanager
    async def get_unit_of_work(self):
        """Get Unit of Work for comprehensive transaction management with service access."""
        async with self.get_db() as session:
            try:
                unit_of_work = self.service_container.create_unit_of_work(session)
                async with unit_of_work:
                    yield unit_of_work
                    await unit_of_work.commit()
            except Exception as e:
                logging.error(f"Unit of Work error: {e}")
                raise

    def _setup_services(self) -> None:
        """Setup dependency injection container with services."""

        # Register messaging services as singletons (stateless)
        embed_builder = EmbedBuilderService()
        message_formatter = MessageFormatterService()
        currency_service = CurrencyService()
        permission_service = PermissionService(bot=self)

        self.service_container.register_singleton(IEmbedBuilder, embed_builder)
        self.service_container.register_singleton(IMessageFormatter, message_formatter)
        self.service_container.register_singleton(ICurrencyService, currency_service)
        self.service_container.register_singleton(IPermissionService, permission_service)

        # Note: Repository and service factories are handled in get_service method
        # since they require session and complex dependency injection

    async def get_service(self, service_type: type, session: Optional[AsyncSession] = None) -> Any:
        """Get a service instance with optional database session."""

        # Services that don't need database session
        if service_type in [IEmbedBuilder, IMessageFormatter, ICurrencyService, IPermissionService]:
            return self.service_container.get_service(service_type)

        # Services that need database session
        if session is None:
            raise ValueError(f"Service {service_type.__name__} requires a database session")

        if service_type == IRoleService:
            # Create repository with session
            role_repository = RoleRepository(session)
            # Create unit of work
            unit_of_work = self.service_container.create_unit_of_work(session)
            # Create service with dependencies
            return RoleService(role_repository=role_repository, unit_of_work=unit_of_work)

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
                invite_repository=invite_repository,
                unit_of_work=unit_of_work,
            )

        elif service_type == IActivityService:
            # Create repositories
            activity_repository = ActivityRepository(session)
            member_repository = MemberRepository(session)
            unit_of_work = self.service_container.create_unit_of_work(session)

            return ActivityTrackingService(
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

        elif service_type == IActivityTrackingService:
            # Create unit of work
            unit_of_work = self.service_container.create_unit_of_work(session)
            # Create repositories
            activity_repository = ActivityRepository(session)
            member_repository = MemberRepository(session)
            # Create activity tracking service
            activity_service = ActivityTrackingService(
                activity_repository=activity_repository,
                member_repository=member_repository,
                guild=self.guild if hasattr(self, "guild") else None,
                unit_of_work=unit_of_work,
            )
            return activity_service

        elif service_type == ITeamManagementService:
            # Create unit of work
            unit_of_work = self.service_container.create_unit_of_work(session)
            # Create team management service
            team_service = TeamManagementService(bot=self, unit_of_work=unit_of_work)
            return team_service

        elif service_type == IVoiceChannelService:
            # Create repository with session
            channel_repository = ChannelRepository(session)
            # Create unit of work
            unit_of_work = self.service_container.create_unit_of_work(session)
            # Create service with dependencies
            return VoiceChannelService(
                channel_repository=channel_repository,
                bot=self,
                unit_of_work=unit_of_work
            )

        elif service_type == IAutoKickService:
            # Create repository with session
            channel_repository = ChannelRepository(session)
            # Create unit of work
            unit_of_work = self.service_container.create_unit_of_work(session)
            # Create service with dependencies
            return AutoKickService(
                channel_repository=channel_repository,
                unit_of_work=unit_of_work
            )

        # For other services, use the container
        return self.service_container.get_service(service_type)

    async def close(self) -> None:
        # Stop health check server
        try:
            await self.health_server.stop()
        except Exception as e:
            logging.error(f"Error stopping health check server: {e}")

        await self.engine.dispose()
        await super().close()

    async def load_cogs(self) -> None:
        """Load all cogs"""
        logging.info("Loading cogs...")
        for folder in ("cogs/commands", "cogs/events"):
            path = os.path.join(os.getcwd(), folder)
            for item in os.listdir(path):
                item_path = os.path.join(path, item)

                # Skip the old info.py file if the info module exists
                if item == "info.py" and os.path.isdir(os.path.join(path, "info")):
                    logging.info("Skipping info.py in favor of info module")
                    continue

                # Load .py files
                if item.endswith(".py") and item != "__init__.py":
                    try:
                        await self.load_extension(f"{folder.replace('/', '.')}.{item[:-3]}")
                        logging.info("Loaded cog: %s", item)
                    except commands.ExtensionAlreadyLoaded:
                        logging.warning("Cog %s is already loaded", item)
                    except commands.ExtensionNotFound:
                        logging.error("Cog %s not found", item)
                    except commands.NoEntryPointError:
                        logging.error("Cog %s has no setup function", item)
                    except commands.ExtensionFailed as error:
                        logging.error("Failed to load cog %s: %s", item, error)
                    except Exception as error:
                        logging.error("Unexpected error loading cog %s: %s", item, error)

                # Load modules (directories with __init__.py)
                elif os.path.isdir(item_path) and os.path.exists(os.path.join(item_path, "__init__.py")):
                    try:
                        await self.load_extension(f"{folder.replace('/', '.')}.{item}")
                        logging.info("Loaded cog module: %s", item)
                    except commands.ExtensionAlreadyLoaded:
                        logging.warning("Cog module %s is already loaded", item)
                    except commands.ExtensionNotFound:
                        logging.error("Cog module %s not found", item)
                    except commands.NoEntryPointError:
                        logging.error("Cog module %s has no setup function", item)
                    except commands.ExtensionFailed as error:
                        logging.error("Failed to load cog module %s: %s", item, error)
                    except Exception as error:
                        logging.error("Unexpected error loading cog module %s: %s", item, error)

    async def setup_hook(self) -> None:
        """Setup hook."""
        if not self.test:
            await self.load_cogs()

            # Start health check server
            try:
                await self.health_server.start()
            except Exception as e:
                logging.error(f"Failed to start health check server: {e}")

            # Setup hot reload in development
            if os.getenv("DEV_MODE", "false").lower() == "true":
                try:
                    from utils.hot_reload import setup_hot_reload

                    await setup_hot_reload(self)
                except Exception as e:
                    logging.error(f"Failed to setup hot reload: {e}")

    async def _run_mcp_server(self):
        """Run MCP server in background."""
        try:
            await self.mcp_server.run()
        except Exception as e:
            logging.error(f"MCP server error: {e}")

    async def on_ready(self) -> None:
        """On ready event"""
        logging.info("Event on_ready started")

        async with self.engine.begin() as conn:
            table_names = self.base.metadata.tables.keys()
            logging.info("Creating tables: %s", ", ".join(table_names))
            # await conn.run_sync(self.base.metadata.drop_all)
            await conn.run_sync(self.base.metadata.create_all)

        logging.info("Database create_all completed")

        await self.change_presence(activity=discord.Activity(type=discord.ActivityType.playing, name="zaGadka bot"))
        logging.info("Event change_presence completed")

        # Start MCP server if enabled
        if os.getenv("ENABLE_MCP", "false").lower() == "true":
            try:
                from mcp.zgdk_mcp_server import connect_to_bot

                self.mcp_server = connect_to_bot(self)
                asyncio.create_task(self._run_mcp_server())
                logging.info("MCP server started for bot communication")
            except Exception as e:
                logging.error(f"Failed to start MCP server: {e}")

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

        # Setup test category if configured
        if self.guild and self.config.get("test_category"):
            try:
                from utils.setup.test_category import TestCategorySetup
                setup = TestCategorySetup(self)
                await setup.setup_test_category(self.guild)
                logging.info("Test category setup completed")
                
                # Setup performance monitoring for 100k+ users
                from utils.monitoring.performance_monitor import PerformanceMonitor
                self.performance_monitor = PerformanceMonitor(self)
                # Set analytics channel if test channels were created
                if "test_channels" in self.config and "analytics" in self.config["test_channels"]:
                    self.performance_monitor.analytics_channel_id = self.config["test_channels"]["analytics"]
                await self.performance_monitor.start()
                logging.info("Performance monitoring started")
            except Exception as e:
                logging.error(f"Failed to setup test category: {e}", exc_info=True)

        logging.info("Ready")

    async def on_command_error(self, ctx, error):
        """Handle command errors with detailed logging."""
        from utils.error_logger import error_logger

        # Log the error with full context
        error_logger.log_command_error(error, ctx)

        # Also log to console for immediate visibility
        logging.error(f"An error occurred while executing command '{ctx.command}': {error}")

        # You can add user-friendly error responses here if needed
        # For now, let the default error handling continue

    def run(self) -> None:
        """Run the bot"""
        token = os.environ.get("ZAGADKA_TOKEN")
        if token is None:
            raise ValueError("Missing bot token. Ensure that ZAGADKA_TOKEN is set in the environment variables.")
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
