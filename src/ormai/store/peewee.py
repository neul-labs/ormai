"""
Peewee-based audit store.

SQL-backed audit storage using Peewee for synchronous database access.
"""

import asyncio
import json
from datetime import datetime
from typing import Any

from peewee import (
    CharField,
    DateTimeField,
    FloatField,
    IntegerField,
    Model,
    TextField,
)

from ormai.store.base import AuditStore
from ormai.store.models import AuditRecord, ErrorInfo

# Note: This is a base model. Users should create their own model
# that inherits from this and sets the database.


class BaseAuditRecordModel(Model):
    """
    Base Peewee model for audit records.

    To use this store, create a model that inherits from this
    and sets your database:

        from peewee import SqliteDatabase
        from ormai.store.peewee import BaseAuditRecordModel, PeeweeAuditStore

        db = SqliteDatabase("audit.db")

        class AuditRecordModel(BaseAuditRecordModel):
            class Meta:
                database = db

        db.create_tables([AuditRecordModel])
        store = PeeweeAuditStore(AuditRecordModel)

    Or use the provided factory function:

        store = PeeweeAuditStore.create(db)
    """

    id = CharField(primary_key=True, max_length=255)
    tool_name = CharField(max_length=255, index=True)
    principal_id = CharField(max_length=255, index=True)
    tenant_id = CharField(max_length=255, index=True)
    request_id = CharField(max_length=255, null=True)
    trace_id = CharField(max_length=255, null=True)
    timestamp = DateTimeField(index=True)
    inputs = TextField(default="{}")  # JSON
    outputs = TextField(null=True)  # JSON
    policy_decisions = TextField(default="[]")  # JSON
    row_count = IntegerField(null=True)
    duration_ms = FloatField(null=True)
    error = TextField(null=True)  # JSON
    before_snapshot = TextField(null=True)  # JSON
    after_snapshot = TextField(null=True)  # JSON
    reason = TextField(null=True)
    metadata = TextField(null=True)  # JSON

    class Meta:
        table_name = "audit_records"


def create_audit_model(db: Any) -> type[Model]:
    """
    Create an AuditRecordModel bound to a specific database.

    Args:
        db: Peewee database instance

    Returns:
        Model class ready for use
    """

    class AuditRecordModel(Model):
        """Audit record model bound to specific database."""

        id = CharField(primary_key=True, max_length=255)
        tool_name = CharField(max_length=255, index=True)
        principal_id = CharField(max_length=255, index=True)
        tenant_id = CharField(max_length=255, index=True)
        request_id = CharField(max_length=255, null=True)
        trace_id = CharField(max_length=255, null=True)
        timestamp = DateTimeField(index=True)
        inputs = TextField(default="{}")
        outputs = TextField(null=True)
        policy_decisions = TextField(default="[]")
        row_count = IntegerField(null=True)
        duration_ms = FloatField(null=True)
        error = TextField(null=True)
        before_snapshot = TextField(null=True)
        after_snapshot = TextField(null=True)
        reason = TextField(null=True)
        metadata = TextField(null=True)

        class Meta:
            database = db
            table_name = "audit_records"

    return AuditRecordModel


class PeeweeAuditStore(AuditStore):
    """
    Audit store using Peewee for synchronous SQL database access.

    Supports any database that Peewee supports:
    - PostgreSQL
    - MySQL
    - SQLite
    - CockroachDB

    Usage:
        from peewee import SqliteDatabase
        from ormai.store.peewee import PeeweeAuditStore

        db = SqliteDatabase("audit.db")
        store = PeeweeAuditStore.create(db)

        # Or with an existing model
        store = PeeweeAuditStore(MyAuditModel)
    """

    def __init__(self, model_class: type[Model]) -> None:
        """
        Initialize the Peewee audit store.

        Args:
            model_class: Peewee model class for audit records
        """
        self.model = model_class

    @classmethod
    def create(
        cls,
        database: Any,
        create_table: bool = True,
    ) -> "PeeweeAuditStore":
        """
        Create a PeeweeAuditStore with a new model bound to the database.

        Args:
            database: Peewee database instance
            create_table: Whether to create the table if it doesn't exist

        Returns:
            Configured PeeweeAuditStore
        """
        model_class = create_audit_model(database)
        if create_table:
            database.create_tables([model_class], safe=True)
        return cls(model_class)

    async def store(self, record: AuditRecord) -> None:
        """Store an audit record in the database."""
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self._store_sync, record)

    def _store_sync(self, record: AuditRecord) -> None:
        """Synchronous store implementation."""
        self.model.create(
            id=record.id,
            tool_name=record.tool_name,
            principal_id=record.principal_id,
            tenant_id=record.tenant_id,
            request_id=record.request_id,
            trace_id=record.trace_id,
            timestamp=record.timestamp,
            inputs=json.dumps(record.inputs),
            outputs=json.dumps(record.outputs) if record.outputs else None,
            policy_decisions=json.dumps(record.policy_decisions),
            row_count=record.row_count,
            duration_ms=record.duration_ms,
            error=json.dumps(record.error.model_dump()) if record.error else None,
            before_snapshot=json.dumps(record.before_snapshot) if record.before_snapshot else None,
            after_snapshot=json.dumps(record.after_snapshot) if record.after_snapshot else None,
            reason=record.reason,
            metadata=json.dumps(record.metadata) if record.metadata else None,
        )

    async def get(self, record_id: str) -> AuditRecord | None:
        """Retrieve an audit record by ID."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._get_sync, record_id)

    def _get_sync(self, record_id: str) -> AuditRecord | None:
        """Synchronous get implementation."""
        try:
            model = self.model.get_by_id(record_id)
            return self._to_record(model)
        except self.model.DoesNotExist:
            return None

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
        query = self.model.select()

        if tenant_id:
            query = query.where(self.model.tenant_id == tenant_id)
        if principal_id:
            query = query.where(self.model.principal_id == principal_id)
        if tool_name:
            query = query.where(self.model.tool_name == tool_name)
        if start_time:
            query = query.where(self.model.timestamp >= start_time)
        if end_time:
            query = query.where(self.model.timestamp <= end_time)

        query = query.order_by(self.model.timestamp.desc())
        query = query.offset(offset).limit(limit)

        return [self._to_record(m) for m in query]

    def count_sync(
        self,
        *,
        tenant_id: str | None = None,
        principal_id: str | None = None,
        tool_name: str | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
    ) -> int:
        """Count audit records matching filters (synchronous)."""
        query = self.model.select()

        if tenant_id:
            query = query.where(self.model.tenant_id == tenant_id)
        if principal_id:
            query = query.where(self.model.principal_id == principal_id)
        if tool_name:
            query = query.where(self.model.tool_name == tool_name)
        if start_time:
            query = query.where(self.model.timestamp >= start_time)
        if end_time:
            query = query.where(self.model.timestamp <= end_time)

        return query.count()

    def delete_before_sync(self, before: datetime) -> int:
        """
        Delete audit records older than the given timestamp (synchronous).

        Useful for implementing retention policies.

        Returns:
            Number of records deleted
        """
        query = self.model.delete().where(self.model.timestamp < before)
        return query.execute()

    def _to_record(self, model: Model) -> AuditRecord:
        """Convert a Peewee model to an AuditRecord."""
        return AuditRecord(
            id=model.id,
            tool_name=model.tool_name,
            principal_id=model.principal_id,
            tenant_id=model.tenant_id,
            request_id=model.request_id,
            trace_id=model.trace_id,
            timestamp=model.timestamp,
            inputs=json.loads(model.inputs) if model.inputs else {},
            outputs=json.loads(model.outputs) if model.outputs else None,
            policy_decisions=json.loads(model.policy_decisions) if model.policy_decisions else [],
            row_count=model.row_count,
            duration_ms=model.duration_ms,
            error=ErrorInfo.model_validate(json.loads(model.error)) if model.error else None,
            before_snapshot=json.loads(model.before_snapshot) if model.before_snapshot else None,
            after_snapshot=json.loads(model.after_snapshot) if model.after_snapshot else None,
            reason=model.reason,
            metadata=json.loads(model.metadata) if model.metadata else None,
        )
