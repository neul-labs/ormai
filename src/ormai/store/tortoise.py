"""
Tortoise ORM-based audit store.

SQL-backed audit storage using Tortoise ORM for async database access.
"""

from datetime import datetime
from typing import Any

from tortoise import fields
from tortoise.models import Model

from ormai.store.base import AuditStore
from ormai.store.models import AuditRecord, ErrorInfo


class AuditRecordModel(Model):
    """
    Tortoise ORM model for audit records.

    To use this store, create this table in your database:

    CREATE TABLE audit_records (
        id VARCHAR(255) PRIMARY KEY,
        tool_name VARCHAR(255) NOT NULL,
        principal_id VARCHAR(255) NOT NULL,
        tenant_id VARCHAR(255) NOT NULL,
        request_id VARCHAR(255),
        trace_id VARCHAR(255),
        timestamp TIMESTAMP NOT NULL,
        inputs JSON,
        outputs JSON,
        policy_decisions JSON,
        row_count INTEGER,
        duration_ms FLOAT,
        error JSON,
        before_snapshot JSON,
        after_snapshot JSON,
        reason TEXT,
        metadata JSON
    );

    CREATE INDEX idx_audit_tenant ON audit_records(tenant_id);
    CREATE INDEX idx_audit_principal ON audit_records(principal_id);
    CREATE INDEX idx_audit_tool ON audit_records(tool_name);
    CREATE INDEX idx_audit_timestamp ON audit_records(timestamp);
    """

    id = fields.CharField(max_length=255, pk=True)
    tool_name = fields.CharField(max_length=255)
    principal_id = fields.CharField(max_length=255)
    tenant_id = fields.CharField(max_length=255)
    request_id = fields.CharField(max_length=255, null=True)
    trace_id = fields.CharField(max_length=255, null=True)
    timestamp = fields.DatetimeField()
    inputs = fields.JSONField(default=dict)
    outputs = fields.JSONField(null=True)
    policy_decisions = fields.JSONField(default=list)
    row_count = fields.IntField(null=True)
    duration_ms = fields.FloatField(null=True)
    error = fields.JSONField(null=True)
    before_snapshot = fields.JSONField(null=True)
    after_snapshot = fields.JSONField(null=True)
    reason = fields.TextField(null=True)
    metadata = fields.JSONField(null=True)

    class Meta:
        table = "audit_records"


class TortoiseAuditStore(AuditStore):
    """
    Audit store using Tortoise ORM for async SQL database access.

    Supports any database that Tortoise ORM supports:
    - PostgreSQL
    - MySQL
    - SQLite
    - Microsoft SQL Server

    Usage:
        from ormai.store.tortoise import TortoiseAuditStore

        # Initialize Tortoise first
        await Tortoise.init(
            db_url="postgres://user:pass@localhost/db",
            modules={"models": ["ormai.store.tortoise"]},
        )
        await Tortoise.generate_schemas()

        store = TortoiseAuditStore()
        await store.store(record)
    """

    def __init__(self, connection_name: str = "default") -> None:
        """
        Initialize the Tortoise audit store.

        Args:
            connection_name: Tortoise connection name to use
        """
        self.connection_name = connection_name

    async def store(self, record: AuditRecord) -> None:
        """Store an audit record in the database."""
        await AuditRecordModel.create(
            id=record.id,
            tool_name=record.tool_name,
            principal_id=record.principal_id,
            tenant_id=record.tenant_id,
            request_id=record.request_id,
            trace_id=record.trace_id,
            timestamp=record.timestamp,
            inputs=record.inputs,
            outputs=record.outputs,
            policy_decisions=record.policy_decisions,
            row_count=record.row_count,
            duration_ms=record.duration_ms,
            error=record.error.model_dump() if record.error else None,
            before_snapshot=record.before_snapshot,
            after_snapshot=record.after_snapshot,
            reason=record.reason,
            metadata=record.metadata,
            using_db=self.connection_name,
        )

    async def get(self, record_id: str) -> AuditRecord | None:
        """Retrieve an audit record by ID."""
        model = await AuditRecordModel.filter(id=record_id).using_db(
            self.connection_name
        ).first()

        if model is None:
            return None

        return self._to_record(model)

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
        queryset = AuditRecordModel.all().using_db(self.connection_name)

        if tenant_id:
            queryset = queryset.filter(tenant_id=tenant_id)
        if principal_id:
            queryset = queryset.filter(principal_id=principal_id)
        if tool_name:
            queryset = queryset.filter(tool_name=tool_name)
        if start_time:
            queryset = queryset.filter(timestamp__gte=start_time)
        if end_time:
            queryset = queryset.filter(timestamp__lte=end_time)

        queryset = queryset.order_by("-timestamp").offset(offset).limit(limit)

        models = await queryset
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
        queryset = AuditRecordModel.all().using_db(self.connection_name)

        if tenant_id:
            queryset = queryset.filter(tenant_id=tenant_id)
        if principal_id:
            queryset = queryset.filter(principal_id=principal_id)
        if tool_name:
            queryset = queryset.filter(tool_name=tool_name)
        if start_time:
            queryset = queryset.filter(timestamp__gte=start_time)
        if end_time:
            queryset = queryset.filter(timestamp__lte=end_time)

        return await queryset.count()

    async def delete_before(self, before: datetime) -> int:
        """
        Delete audit records older than the given timestamp.

        Useful for implementing retention policies.

        Returns:
            Number of records deleted
        """
        deleted = await AuditRecordModel.filter(
            timestamp__lt=before
        ).using_db(self.connection_name).delete()
        return deleted

    def _to_record(self, model: AuditRecordModel) -> AuditRecord:
        """Convert a Tortoise model to an AuditRecord."""
        return AuditRecord(
            id=model.id,
            tool_name=model.tool_name,
            principal_id=model.principal_id,
            tenant_id=model.tenant_id,
            request_id=model.request_id,
            trace_id=model.trace_id,
            timestamp=model.timestamp,
            inputs=model.inputs,
            outputs=model.outputs,
            policy_decisions=model.policy_decisions,
            row_count=model.row_count,
            duration_ms=model.duration_ms,
            error=ErrorInfo.model_validate(model.error) if model.error else None,
            before_snapshot=model.before_snapshot,
            after_snapshot=model.after_snapshot,
            reason=model.reason,
            metadata=model.metadata,
        )
