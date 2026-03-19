"""
SQLModel adapter implementation.

SQLModel is built on SQLAlchemy, so this adapter wraps the SQLAlchemy adapter
with SQLModel-specific conveniences.
"""

from typing import Any, Type

from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

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
            session_factory=lambda: Session(engine),
        )
    """

    def __init__(
        self,
        engine: Engine,
        session_factory: Any = None,
        models: list[Type] | None = None,
    ) -> None:
        """
        Initialize the SQLModel adapter.

        Args:
            engine: SQLAlchemy engine instance
            session_factory: Factory function or class to create sessions
            models: Optional list of SQLModel classes to include
        """
        if not HAS_SQLMODEL:
            raise ImportError(
                "SQLModel is not installed. Install with: pip install sqlmodel"
            )

        # Use SQLModel's metadata if no models specified
        if models:
            # Get metadata from model list
            metadata = models[0].metadata if models else None
        else:
            metadata = SQLModel.metadata if SQLModel else None

        super().__init__(
            engine=engine,
            session_factory=session_factory,
            metadata=metadata,
        )

        self._sqlmodel_classes = models or []

    async def introspect(self) -> SchemaMetadata:
        """Introspect SQLModel models."""
        return await super().introspect()

    @classmethod
    def from_models(
        cls,
        engine: Engine,
        *model_classes: Type,
    ) -> "SQLModelAdapter":
        """
        Create an adapter from SQLModel classes.

        Usage:
            adapter = SQLModelAdapter.from_models(
                engine,
                Customer,
                Order,
                Product,
            )
        """
        from sqlmodel import Session

        return cls(
            engine=engine,
            session_factory=lambda: Session(engine),
            models=list(model_classes),
        )
