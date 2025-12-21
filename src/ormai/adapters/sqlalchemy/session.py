"""
SQLAlchemy session management.

Provides session lifecycle management for both sync and async operations.
"""

from collections.abc import AsyncGenerator, Callable, Generator
from contextlib import asynccontextmanager, contextmanager
from typing import Any, TypeVar

from sqlalchemy import Engine
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import Session, sessionmaker

T = TypeVar("T")


class SessionManager:
    """
    Manages SQLAlchemy sessions for OrmAI operations.

    Supports both sync and async engines/sessions.
    """

    def __init__(
        self,
        engine: Engine | AsyncEngine,
        session_factory: sessionmaker | async_sessionmaker | None = None,
    ) -> None:
        """
        Initialize the session manager.

        Args:
            engine: SQLAlchemy engine (sync or async)
            session_factory: Optional pre-configured session factory
        """
        self.engine = engine
        self.is_async = isinstance(engine, AsyncEngine)

        if session_factory:
            self._session_factory = session_factory
        elif self.is_async:
            self._session_factory = async_sessionmaker(
                engine,  # type: ignore
                class_=AsyncSession,
                expire_on_commit=False,
            )
        else:
            self._session_factory = sessionmaker(
                engine,  # type: ignore
                expire_on_commit=False,
            )

    @contextmanager
    def session(self) -> Generator[Session, None, None]:
        """
        Context manager for sync sessions.

        Automatically commits on success and rolls back on error.
        """
        if self.is_async:
            raise RuntimeError("Use async_session() for async engines")

        session: Session = self._session_factory()  # type: ignore
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    @asynccontextmanager
    async def async_session(self) -> AsyncGenerator[AsyncSession, None]:
        """
        Async context manager for async sessions.

        Automatically commits on success and rolls back on error.
        """
        if not self.is_async:
            raise RuntimeError("Use session() for sync engines")

        session: AsyncSession = self._session_factory()  # type: ignore
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

    def run_in_transaction(
        self,
        fn: Callable[[Session], T],
    ) -> T:
        """
        Execute a function within a sync transaction.
        """
        with self.session() as session:
            return fn(session)

    async def async_run_in_transaction(
        self,
        fn: Callable[[AsyncSession], Any],
    ) -> Any:
        """
        Execute an async function within an async transaction.
        """
        async with self.async_session() as session:
            return await fn(session)

    def get_session(self) -> Session:
        """
        Get a new session (caller is responsible for lifecycle).

        Prefer using session() context manager when possible.
        """
        if self.is_async:
            raise RuntimeError("Use get_async_session() for async engines")
        return self._session_factory()  # type: ignore

    async def get_async_session(self) -> AsyncSession:
        """
        Get a new async session (caller is responsible for lifecycle).

        Prefer using async_session() context manager when possible.
        """
        if not self.is_async:
            raise RuntimeError("Use get_session() for sync engines")
        return self._session_factory()  # type: ignore
