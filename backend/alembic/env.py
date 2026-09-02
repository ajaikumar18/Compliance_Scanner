"""
Alembic environment configuration – uses async SQLAlchemy engine.

Key behaviours:
- Reads DATABASE_URL from .env (via app.core.config)
- Converts postgresql:// → postgresql+asyncpg:// for async migrations
- Imports all models so autogenerate can detect schema changes
"""

import asyncio
import os
import sys
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import create_async_engine

# ── Make sure the backend/ package is importable ──────────────────────────────
# env.py lives at backend/alembic/env.py, so we add backend/ to sys.path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

# ── Load application settings (reads .env) ────────────────────────────────────
from app.core.config import settings  # noqa: E402

# ── Import the shared Base and ALL models so autogenerate works ───────────────
from app.core.database import Base  # noqa: E402
import app.models  # noqa: E402, F401  – side-effect: registers all mappers

# ── Alembic Config ────────────────────────────────────────────────────────────
config = context.config

# Build the raw asyncpg URL (used to create the engine directly)
_db_url = settings.DATABASE_URL
if _db_url.startswith("postgresql://"):
    _db_url = _db_url.replace("postgresql://", "postgresql+asyncpg://", 1)
elif _db_url.startswith("postgres://"):
    _db_url = _db_url.replace("postgres://", "postgresql+asyncpg://", 1)

# Also set it in the config (with % escaped for configparser) so offline mode works
config.set_main_option("sqlalchemy.url", _db_url.replace("%", "%%"))

# Interpret the alembic.ini logging section
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


# ── Offline migrations ────────────────────────────────────────────────────────
def run_migrations_offline() -> None:
    """Run migrations without a live DB connection (generates SQL script)."""
    context.configure(
        url=_db_url,          # raw URL – no configparser interpolation issues
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


# ── Online migrations (async) ─────────────────────────────────────────────────
def do_run_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    # Build the engine directly from the raw URL – bypasses configparser % issues
    connectable = create_async_engine(
        _db_url,
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


# ── Entry point ───────────────────────────────────────────────────────────────
if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
