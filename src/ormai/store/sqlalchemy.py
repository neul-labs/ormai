"""
SQLAlchemy-based audit store.

SQL-backed audit storage using SQLAlchemy for database access.
Supports both sync and async engines.
"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime
from typing import Any

from sqlalchemy import (
    Column,
    DateTime,
    Float,
    Index,
    Integer,
    String,
    Text,
    delete,
    func,
    select,
)
from sqlalchemy.engine import Engine
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from ormai.store.base import AuditStore
from ormai.store.models import AuditRecord, ErrorInfo


class Base(DeclarativeBase):
    """Base class for SQLAlchemy models."""

    pass


class AuditRecordModel(Base):
    """
    SQLAlchemy model for audit records.

    To use this store, create this table in your database:

    CREATE TABLE audit_records (
        id VARCHAR(255) PRIMARY KEY,
        tool_name VARCHAR(255) NOT NULL,
        principal_id VARCHAR(255) NOT NULL,
        tenant_id VARCHAR(255) NOT NULL,
        request_id VARCHAR(255),
        trace_id VARCHAR(255),
        timestamp TIMESTAMP NOT NULL,
        duration_ms FLOAT,
        inputs TEXT NOT NULL,
        outputs TEXT,
        policy_decisions TEXT,
        row_count INTEGER,
        error TEXT,
        before_snapshot TEXT,
        after_snapshot TEXT,
        reason TEXT,
        metadata_ TEXT
    );

    CREATE INDEX idx_audit_tenant ON audit_records(tenant_id);
    CREATE INDEX idx_audit_principal ON audit_records(principal_id);
    CREATE INDEX idx_audit_tool ON audit_records(tool_name);
    CREATE INDEX idx_audit_timestamp ON audit_records(timestamp);
    CREATE INDEX idx_audit_tenant_time ON audit_records(tenant_id, timestamp);
    CREATE INDEX idx_audit_principal_time ON audit_records(principal_id, timestamp);
    """

    __tablename__ = "audit_records"

    id = Column(String(255), primary_key=True)
    tool_name = Column(String(255), nullable=False, index=True)
    principal_id = Column(String(255), nullable=False, index=True)
    tenant_id = Column(String(255), nullable=False, index=True)
    request_id = Column(String(255), nullable=True)
    trace_id = Column(String(255), nullable=True)
    timestamp = Column(DateTime, nullable=False, index=True)
    duration_ms = Column(Float, nullable=True)
    inputs = Column(Text, nullable=False, default="{}")
    outputs = Column(Text, nullable=True)
    policy_decisions = Column(Text, default="[]")
    row_count = Column(Integer, nullable=True)
    error = Column(Text, nullable=True)
    before_snapshot = Column(Text, nullable=True)
    after_snapshot = Column(Text, nullable=True)
    reason = Column(Text, nullable=True)
    metadata_ = Column("metadata", Text, nullable=True)

    # Composite indexes for common query patterns
    __table_args__ = (
        Index("idx_audit_tenant_time", "tenant_id", "timestamp"),
        Index("idx_audit_principal_time", "principal_id", "timestamp"),
    )


class SQLAlchemyAuditStore(AuditStore):
    """
    Audit store using SQLAlchemy for SQL database access.

    Supports both synchronous and asynchronous engines:
    - PostgreSQL (sync and async with asyncpg)
    - MySQL (sync and async with aiomysql)
    - SQLite (sync and async with aiosqlite)

    Usage with sync engine:
        from sqlalchemy import create_engine
        from ormai.store.sqlalchemy import SQLAlchemyAuditStore

        engine = create_engine("sqlite:///audit.db")
        store = SQLAlchemyAuditStore(engine, create_tables=True)
        await store.store(record)

    Usage with async engine:
        from sqlalchemy.ext.asyncio import create_async_engine

        engine = create_async_engine("sqlite+aiosqlite:///audit.db")
        store = SQLAlchemyAuditStore(engine, create_tables=True)
        await store.store(record)
    """

    def __init__(
        self,
        engine: Engine | AsyncEngine,
        create_tables: bool = False,
    ) -> None:
        """
        Initialize the SQLAlchemy audit store.

        Args:
            engine: SQLAlchemy engine (sync or async)
            create_tables: Whether to create tables if they don't exist
        """
        self.engine = engine
        self.is_async = isinstance(engine, AsyncEngine)

        if self.is_async:
            self._async_session_factory = async_sessionmaker(
                engine,  # type: ignore
                class_=AsyncSession,
                expire_on_commit=False,
            )
            self._sync_session_factory = None
        else:
            self._sync_session_factory = sessionmaker(
                engine,  # type: ignore
                expire_on_commit=False,
            )
            self._async_session_factory = None

        if create_tables:
            self._create_tables()

    def _create_tables(self) -> None:
        """Create the audit_records table if it doesn't exist."""
        if self.is_async:
            # For async engines, we need to run sync to create tables
            # This is typically only done once at startup
            async def _create():
                async with self.engine.begin() as conn:  # type: ignore
                    await conn.run_sync(Base.metadata.create_all)

            try:
                asyncio.get_running_loop()
                asyncio.create_task(_create())
            except RuntimeError:
                asyncio.run(_create())
        else:
            Base.metadata.create_all(self.engine)  # type: ignore

    async def store(self, record: AuditRecord) -> None:
        """Store an audit record in the database."""
        if self.is_async:
            await self._store_async(record)
        else:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, self._store_sync, record)

    def _store_sync(self, record: AuditRecord) -> None:
        """Synchronous store implementation."""
        with self._sync_session_factory() as session:  # type: ignore
            model = self._to_model(record)
            session.add(model)
            session.commit()

    async def _store_async(self, record: AuditRecord) -> None:
        """Asynchronous store implementation."""
        async with self._async_session_factory() as session:  # type: ignore
            model = self._to_model(record)
            session.add(model)
            await session.commit()

    async def get(self, record_id: str) -> AuditRecord | None:
        """Retrieve an audit record by ID."""
        if self.is_async:
            return await self._get_async(record_id)
        else:
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(None, self._get_sync, record_id)

    def _get_sync(self, record_id: str) -> AuditRecord | None:
        """Synchronous get implementation."""
        with self._sync_session_factory() as session:  # type: ignore
            stmt = select(AuditRecordModel).where(AuditRecordModel.id == record_id)
            result = session.execute(stmt)
            model = result.scalars().first()
            return self._to_record(model) if model else None

    async def _get_async(self, record_id: str) -> AuditRecord | None:
        """Asynchronous get implementation."""
        async with self._async_session_factory() as session:  # type: ignore
            stmt = select(AuditRecordModel).where(AuditRecordModel.id == record_id)
            result = await session.execute(stmt)
            model = result.scalars().first()
            return self._to_record(model) if model else None

    async def query(
        self,
        *,
        tenant_id: str | None = None,
        principal_id: str | None = None,
        tool_name: str | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[AuditRecord]:
        """Query audit records with filters."""
        if self.is_async:
            return await self._query_async(
                tenant_id, principal_id, tool_name, start_time, end_time, limit, offset
            )
        else:
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(
                None,
                self._query_sync,
                tenant_id,
                principal_id,
                tool_name,
                start_time,
                end_time,
                limit,
                offset,
            )

    def _build_query_filters(
        self,
        stmt: Any,
        tenant_id: str | None,
        principal_id: str | None,
        tool_name: str | None,
        start_time: datetime | None,
        end_time: datetime | None,
    ) -> Any:
        """Apply filters to a query statement."""
        if tenant_id:
            stmt = stmt.where(AuditRecordModel.tenant_id == tenant_id)
        if principal_id:
            stmt = stmt.where(AuditRecordModel.principal_id == principal_id)
        if tool_name:
            stmt = stmt.where(AuditRecordModel.tool_name == tool_name)
        if start_time:
            stmt = stmt.where(AuditRecordModel.timestamp >= start_time)
        if end_time:
            stmt = stmt.where(AuditRecordModel.timestamp <= end_time)
        return stmt

    def _query_sync(
        self,
        tenant_id: str | None,
        principal_id: str | None,
        tool_name: str | None,
        start_time: datetime | None,
        end_time: datetime | None,
        limit: int,
        offset: int,
    ) -> list[AuditRecord]:
        """Synchronous query implementation."""
        with self._sync_session_factory() as session:  # type: ignore
            stmt = select(AuditRecordModel)
            stmt = self._build_query_filters(
                stmt, tenant_id, principal_id, tool_name, start_time, end_time
            )
            stmt = stmt.order_by(AuditRecordModel.timestamp.desc())
            stmt = stmt.offset(offset).limit(limit)

            result = session.execute(stmt)
            models = result.scalars().all()
            return [self._to_record(m) for m in models]

    async def _query_async(
        self,
        tenant_id: str | None,
        principal_id: str | None,
        tool_name: str | None,
        start_time: datetime | None,
        end_time: datetime | None,
        limit: int,
        offset: int,
    ) -> list[AuditRecord]:
        """Asynchronous query implementation."""
        async with self._async_session_factory() as session:  # type: ignore
            stmt = select(AuditRecordModel)
            stmt = self._build_query_filters(
                stmt, tenant_id, principal_id, tool_name, start_time, end_time
            )
            stmt = stmt.order_by(AuditRecordModel.timestamp.desc())
            stmt = stmt.offset(offset).limit(limit)

            result = await session.execute(stmt)
            models = result.scalars().all()
            return [self._to_record(m) for m in models]

    async def count(
        self,
        *,
        tenant_id: str | None = None,
        principal_id: str | None = None,
        tool_name: str | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
    ) -> int:
        """Count audit records matching filters."""
        if self.is_async:
            return await self._count_async(
                tenant_id, principal_id, tool_name, start_time, end_time
            )
        else:
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(
                None,
                self._count_sync,
                tenant_id,
                principal_id,
                tool_name,
                start_time,
                end_time,
            )

    def _count_sync(
        self,
        tenant_id: str | None,
        principal_id: str | None,
        tool_name: str | None,
        start_time: datetime | None,
        end_time: datetime | None,
    ) -> int:
        """Synchronous count implementation."""
        with self._sync_session_factory() as session:  # type: ignore
            stmt = select(func.count()).select_from(AuditRecordModel)
            stmt = self._build_query_filters(
                stmt, tenant_id, principal_id, tool_name, start_time, end_time
            )
            result = session.execute(stmt)
            return result.scalar() or 0

    async def _count_async(
        self,
        tenant_id: str | None,
        principal_id: str | None,
        tool_name: str | None,
        start_time: datetime | None,
        end_time: datetime | None,
    ) -> int:
        """Asynchronous count implementation."""
        async with self._async_session_factory() as session:  # type: ignore
            stmt = select(func.count()).select_from(AuditRecordModel)
            stmt = self._build_query_filters(
                stmt, tenant_id, principal_id, tool_name, start_time, end_time
            )
            result = await session.execute(stmt)
            return result.scalar() or 0

    async def delete_before(self, before: datetime) -> int:
        """Delete audit records older than the given timestamp."""
        if self.is_async:
            return await self._delete_before_async(before)
        else:
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(None, self._delete_before_sync, before)

    def _delete_before_sync(self, before: datetime) -> int:
        """Synchronous delete implementation."""
        with self._sync_session_factory() as session:  # type: ignore
            stmt = delete(AuditRecordModel).where(AuditRecordModel.timestamp < before)
            result = session.execute(stmt)
            session.commit()
            return result.rowcount

    async def _delete_before_async(self, before: datetime) -> int:
        """Asynchronous delete implementation."""
        async with self._async_session_factory() as session:  # type: ignore
            stmt = delete(AuditRecordModel).where(AuditRecordModel.timestamp < before)
            result = await session.execute(stmt)
            await session.commit()
            return result.rowcount

    async def bulk_store(self, records: list[AuditRecord]) -> int:
        """Store multiple audit records in a single operation."""
        if self.is_async:
            return await self._bulk_store_async(records)
        else:
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(None, self._bulk_store_sync, records)

    def _bulk_store_sync(self, records: list[AuditRecord]) -> int:
        """Synchronous bulk store implementation."""
        with self._sync_session_factory() as session:  # type: ignore
            models = [self._to_model(r) for r in records]
            session.add_all(models)
            session.commit()
            return len(records)

    async def _bulk_store_async(self, records: list[AuditRecord]) -> int:
        """Asynchronous bulk store implementation."""
        async with self._async_session_factory() as session:  # type: ignore
            models = [self._to_model(r) for r in records]
            session.add_all(models)
            await session.commit()
            return len(records)

    def _to_model(self, record: AuditRecord) -> AuditRecordModel:
        """Convert an AuditRecord to a SQLAlchemy model."""
        return AuditRecordModel(
            id=record.id,
            tool_name=record.tool_name,
            principal_id=record.principal_id,
            tenant_id=record.tenant_id,
            request_id=record.request_id,
            trace_id=record.trace_id,
            timestamp=record.timestamp,
            duration_ms=record.duration_ms,
            inputs=json.dumps(record.inputs),
            outputs=json.dumps(record.outputs) if record.outputs else None,
            policy_decisions=json.dumps(record.policy_decisions),
            row_count=record.row_count,
            error=json.dumps(record.error.model_dump()) if record.error else None,
            before_snapshot=json.dumps(record.before_snapshot) if record.before_snapshot else None,
            after_snapshot=json.dumps(record.after_snapshot) if record.after_snapshot else None,
            reason=record.reason,
            metadata_=json.dumps(record.metadata) if record.metadata else None,
        )

    def _to_record(self, model: AuditRecordModel) -> AuditRecord:
        """Convert a SQLAlchemy model to an AuditRecord."""
        return AuditRecord(
            id=model.id,
            tool_name=model.tool_name,
            principal_id=model.principal_id,
            tenant_id=model.tenant_id,
            request_id=model.request_id,
            trace_id=model.trace_id,
            timestamp=model.timestamp,
            duration_ms=model.duration_ms,
            inputs=json.loads(model.inputs) if model.inputs else {},
            outputs=json.loads(model.outputs) if model.outputs else None,
            policy_decisions=json.loads(model.policy_decisions) if model.policy_decisions else [],
            row_count=model.row_count,
            error=ErrorInfo.model_validate(json.loads(model.error)) if model.error else None,
            before_snapshot=json.loads(model.before_snapshot) if model.before_snapshot else None,
            after_snapshot=json.loads(model.after_snapshot) if model.after_snapshot else None,
            reason=model.reason,
            metadata=json.loads(model.metadata_) if model.metadata_ else None,
        )
