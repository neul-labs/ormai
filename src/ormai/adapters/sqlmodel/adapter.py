"""
SQLModel adapter implementation.

SQLModel is built on SQLAlchemy, so this adapter wraps the SQLAlchemy adapter
with SQLModel-specific conveniences.
"""

from typing import Any

from sqlalchemy.engine import Engine

from ormai.adapters.sqlalchemy import SQLAlchemyAdapter
from ormai.core.types import SchemaMetadata

try:
    from sqlmodel import SQLModel

    HAS_SQLMODEL = True
except ImportError:
    HAS_SQLMODEL = False
    SQLModel = None  # type: ignore


class SQLModelAdapter(SQLAlchemyAdapter):
    """
    OrmAI adapter for SQLModel.

    SQLModel is built on SQLAlchemy, so this adapter inherits from
    SQLAlchemyAdapter with SQLModel-specific conveniences.

    Usage:
        from sqlmodel import SQLModel, Field, create_engine, Session
        from ormai.adapters.sqlmodel import SQLModelAdapter

        class Customer(SQLModel, table=True):
            id: int | None = Field(default=None, primary_key=True)
            name: str
            email: str

        engine = create_engine("sqlite:///./app.db")
        SQLModel.metadata.create_all(engine)

        adapter = SQLModelAdapter(
            engine=engine,
            models=[Customer, Order],
            policy=policy,
            session_factory=lambda: Session(engine),
        )
    """

    def __init__(
        self,
        engine: Engine,
        models: list[type] | None = None,
        policy: Any = None,
        session_factory: Any = None,
    ) -> None:
        """
        Initialize the SQLModel adapter.

        Args:
            engine: SQLAlchemy engine instance
            models: Optional list of SQLModel classes to include
            policy: Policy configuration (required by SQLAlchemyAdapter)
            session_factory: Factory function or class to create sessions
        """
        if not HAS_SQLMODEL:
            raise ImportError("SQLModel is not installed. Install with: pip install sqlmodel")

        if models is None:
            models = []

        super().__init__(
            engine=engine,
            models=models,
            policy=policy,
        )

        if session_factory is not None:
            self._session_manager = _SQLModelSessionManager(engine, session_factory)

        self._sqlmodel_classes = models

    async def introspect(self) -> SchemaMetadata:
        """Introspect SQLModel models."""
        return await super().introspect()

    @classmethod
    def from_models(
        cls,
        engine: Engine,
        *model_classes: type,
        policy: Any = None,
    ) -> "SQLModelAdapter":
        """
        Create an adapter from SQLModel classes.

        Usage:
            adapter = SQLModelAdapter.from_models(
                engine,
                Customer,
                Order,
                policy=policy,
            )
        """
        from sqlmodel import Session

        return cls(
            engine=engine,
            models=list(model_classes),
            policy=policy,
            session_factory=lambda: Session(engine),
        )


class _SQLModelSessionManager:
    """Simple session manager that wraps a session factory."""

    def __init__(self, engine: Engine, session_factory: Any) -> None:
        self._engine = engine
        self._session_factory = session_factory

    def session(self):
        return self._session_factory()
