"""Alembic environment: schema comes from mediqueue.db.metadata."""
from alembic import context
from sqlalchemy import create_engine

from mediqueue.config import get_settings
from mediqueue.db import metadata

target_metadata = metadata


def run_migrations_online() -> None:
    engine = create_engine(get_settings().database_url, future=True)
    with engine.connect() as conn:
        context.configure(connection=conn, target_metadata=target_metadata, render_as_batch=True)
        with context.begin_transaction():
            context.run_migrations()


run_migrations_online()
