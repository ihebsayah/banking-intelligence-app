"""Alembic environment configuration.

Uses raw SQL migrations (no ORM models). The target_metadata is None.
Database URL is read from alembic.ini which uses the DATABASE_URL env var.
"""
import os
import sys
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool, create_engine

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = None


def run_migrations_offline() -> None:
    url = os.path.expandvars(config.get_main_option("sqlalchemy.url"))
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    # alembic.ini uses ${DATABASE_URL}; alembic's Config does not expand env
    # vars, so expand them here (and in offline mode below via expandvars).
    url = os.path.expandvars(config.get_main_option("sqlalchemy.url"))
    if not url:
        raise ValueError("sqlalchemy.url is not set in alembic.ini or environment")
    connectable = create_engine(url, poolclass=pool.NullPool)
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
