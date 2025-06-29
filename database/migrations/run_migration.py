#!/usr/bin/env python3
"""
Database Migration Runner for ZGDK Discord Bot
Safely applies performance indexes and database optimizations.
"""

import asyncio
import logging
import os
import sys
from pathlib import Path
from typing import List

import asyncpg

# Add project root to path for imports
sys.path.append(str(Path(__file__).parent.parent.parent))

logger = logging.getLogger(__name__)


class MigrationRunner:
    """Handles database migrations safely and efficiently."""

    def __init__(self, database_url: str):
        self.database_url = database_url
        self.migrations_dir = Path(__file__).parent

    async def connect(self) -> asyncpg.Connection:
        """Create database connection."""
        try:
            conn = await asyncpg.connect(self.database_url)
            logger.info("Connected to database successfully")
            return conn
        except Exception as e:
            logger.error(f"Failed to connect to database: {e}")
            raise

    async def create_migrations_table(self, conn: asyncpg.Connection) -> None:
        """Create migrations tracking table if it doesn't exist."""
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS migrations (
                id SERIAL PRIMARY KEY,
                filename VARCHAR(255) NOT NULL UNIQUE,
                applied_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                success BOOLEAN NOT NULL DEFAULT TRUE
            )
        """
        )
        logger.info("Migrations table ready")

    async def get_applied_migrations(self, conn: asyncpg.Connection) -> List[str]:
        """Get list of already applied migrations."""
        result = await conn.fetch("SELECT filename FROM migrations WHERE success = TRUE")
        return [row["filename"] for row in result]

    def get_migration_files(self) -> List[Path]:
        """Get sorted list of migration files."""
        migration_files = list(self.migrations_dir.glob("*.sql"))
        migration_files.sort()  # Sort by filename for proper order
        return migration_files

    async def apply_migration(self, conn: asyncpg.Connection, migration_file: Path) -> bool:
        """Apply a single migration file."""
        filename = migration_file.name

        logger.info(f"Applying migration: {filename}")

        try:
            # Read migration content
            content = migration_file.read_text(encoding="utf-8")

            # Check if migration contains CONCURRENTLY (can't be in transaction)
            has_concurrent = "CONCURRENTLY" in content.upper()

            if has_concurrent:
                # Execute each statement separately for CONCURRENT operations
                statements = [stmt.strip() for stmt in content.split(";") if stmt.strip()]

                for statement in statements:
                    if statement.strip():
                        # Skip comments and empty lines
                        if statement.strip().startswith("--") or not statement.strip():
                            continue
                        try:
                            logger.info(f"Executing: {statement[:100]}...")
                            await conn.execute(statement)
                            logger.info("Statement executed successfully")
                        except Exception as e:
                            logger.warning(f"Statement failed (continuing): {e}")
                            # Continue with other statements for index creation

                # Record successful migration (no transaction for CONCURRENT)
                await conn.execute("INSERT INTO migrations (filename, success) VALUES ($1, $2)", filename, True)
            else:
                # Use transaction for regular migrations
                async with conn.transaction():
                    # Execute migration
                    await conn.execute(content)

                    # Record successful migration
                    await conn.execute("INSERT INTO migrations (filename, success) VALUES ($1, $2)", filename, True)

            logger.info(f"Successfully applied migration: {filename}")
            return True

        except Exception as e:
            logger.error(f"Failed to apply migration {filename}: {e}")

            # Record failed migration
            try:
                await conn.execute("INSERT INTO migrations (filename, success) VALUES ($1, $2)", filename, False)
            except:
                pass  # Don't fail if we can't record the failure

            return False

    async def run_migrations(self) -> bool:
        """Run all pending migrations."""
        conn = None
        try:
            conn = await self.connect()

            # Setup migrations tracking
            await self.create_migrations_table(conn)

            # Get applied migrations
            applied = await self.get_applied_migrations(conn)
            logger.info(f"Found {len(applied)} already applied migrations")

            # Get migration files
            migration_files = self.get_migration_files()
            logger.info(f"Found {len(migration_files)} migration files")

            # Apply pending migrations
            pending = [f for f in migration_files if f.name not in applied]

            if not pending:
                logger.info("No pending migrations")
                return True

            logger.info(f"Applying {len(pending)} pending migrations")

            success_count = 0
            for migration_file in pending:
                if await self.apply_migration(conn, migration_file):
                    success_count += 1
                else:
                    logger.error(f"Migration failed, stopping: {migration_file.name}")
                    break

            logger.info(f"Applied {success_count}/{len(pending)} migrations successfully")
            return success_count == len(pending)

        except Exception as e:
            logger.error(f"Migration runner failed: {e}")
            return False
        finally:
            if conn:
                await conn.close()


async def main():
    """Main entry point."""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

    # Get database URL from environment
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        # Try to build from components
        db_host = os.getenv("DB_HOST", "localhost")
        db_port = os.getenv("DB_PORT", "5432")
        db_name = os.getenv("DB_NAME", "zgdk")
        db_user = os.getenv("DB_USER", "postgres")
        db_password = os.getenv("DB_PASSWORD", "postgres")

        database_url = f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"

    logger.info("Starting database migrations...")
    logger.info(
        f"Database URL: {database_url.replace(db_password, '****') if 'db_password' in locals() else 'from environment'}"
    )

    runner = MigrationRunner(database_url)
    success = await runner.run_migrations()

    if success:
        logger.info("All migrations completed successfully!")
        return 0
    else:
        logger.error("Some migrations failed!")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
