"""Database engine and session management for RepoContinuum persistence."""

from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Generator
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


class Base(DeclarativeBase):
    """Base declarative class for all SQLAlchemy ORM models."""
    pass


class DatabaseManager:
    """Manages SQLAlchemy engine, schema creation, and session lifecycle."""

    def __init__(self, db_url: str | None = None):
        self.db_url = db_url or os.getenv("REPOCONTINUUM_DATABASE_URL", "sqlite:///repocontinuum.db")
        # For SQLite, enable check_same_thread=False for testing convenience
        connect_args = {}
        if self.db_url.startswith("sqlite"):
            connect_args = {"check_same_thread": False}

        self.engine = create_engine(self.db_url, connect_args=connect_args, echo=False)
        self.session_factory = sessionmaker(bind=self.engine, expire_on_commit=False)

    def create_tables(self) -> None:
        """Create all tables in the database schema."""
        Base.metadata.create_all(self.engine)

    def drop_tables(self) -> None:
        """Drop all tables in the database schema (useful for isolated tests)."""
        Base.metadata.drop_all(self.engine)

    @contextmanager
    def session_scope(self) -> Generator[Session, None, None]:
        """Provide a transactional scope around a series of database operations."""
        session: Session = self.session_factory()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()
