"""
Django-based audit store.

SQL-backed audit storage using Django ORM for database access.
"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime
from typing import Any

from django.db import models, transaction

from ormai.store.base import AuditStore
from ormai.store.models import AuditRecord, ErrorInfo


class AuditRecordModel(models.Model):
    """
    Django model for audit records.

    To use this store, add this model to your Django project or create
    the table manually:

    CREATE TABLE ormai_auditrecord (
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
        metadata TEXT
    );

    CREATE INDEX idx_audit_tenant ON ormai_auditrecord(tenant_id);
    CREATE INDEX idx_audit_principal ON ormai_auditrecord(principal_id);
    CREATE INDEX idx_audit_tool ON ormai_auditrecord(tool_name);
    CREATE INDEX idx_audit_timestamp ON ormai_auditrecord(timestamp);
    """

    id = models.CharField(max_length=255, primary_key=True)
    tool_name = models.CharField(max_length=255, db_index=True)
    principal_id = models.CharField(max_length=255, db_index=True)
    tenant_id = models.CharField(max_length=255, db_index=True)
    request_id = models.CharField(max_length=255, null=True, blank=True)
    trace_id = models.CharField(max_length=255, null=True, blank=True)
    timestamp = models.DateTimeField(db_index=True)
    duration_ms = models.FloatField(null=True, blank=True)
    inputs = models.TextField(default="{}")
    outputs = models.TextField(null=True, blank=True)
    policy_decisions = models.TextField(default="[]")
    row_count = models.IntegerField(null=True, blank=True)
    error = models.TextField(null=True, blank=True)
    before_snapshot = models.TextField(null=True, blank=True)
    after_snapshot = models.TextField(null=True, blank=True)
    reason = models.TextField(null=True, blank=True)
    metadata = models.TextField(null=True, blank=True)

    class Meta:
        app_label = "ormai"
        db_table = "ormai_auditrecord"
        indexes = [
            models.Index(fields=["tenant_id", "timestamp"]),
            models.Index(fields=["principal_id", "timestamp"]),
        ]


class DjangoAuditStore(AuditStore):
    """
    Audit store using Django ORM for SQL database access.

    This store uses Django's synchronous ORM with async wrappers.
    Operations are executed in a thread pool for async compatibility.

    Usage:
        from ormai.store.django import DjangoAuditStore

        store = DjangoAuditStore()
        await store.store(record)

    Note: Ensure Django is configured and the model is migrated before use.
    You can either:
    1. Add 'ormai' to INSTALLED_APPS and run migrations
    2. Create the table manually using the SQL in AuditRecordModel docstring
    """

    def __init__(
        self,
        model_class: type[models.Model] | None = None,
        using: str | None = None,
    ) -> None:
        """
        Initialize the Django audit store.

        Args:
            model_class: Optional custom model class to use instead of AuditRecordModel
            using: Optional database alias to use (for multi-database setups)
        """
        self.model_class = model_class or AuditRecordModel
        self.using = using

    def _get_queryset(self) -> models.QuerySet[Any]:
        """Get the base queryset, optionally using a specific database."""
        qs = self.model_class.objects.all()
        if self.using:
            qs = qs.using(self.using)
        return qs

    async def store(self, record: AuditRecord) -> None:
        """Store an audit record in the database."""
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self._store_sync, record)

    def _store_sync(self, record: AuditRecord) -> None:
        """Synchronous store implementation."""
        model = self._to_model(record)
        if self.using:
            model.save(using=self.using)
        else:
            model.save()

    async def get(self, record_id: str) -> AuditRecord | None:
        """Retrieve an audit record by ID."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._get_sync, record_id)

    def _get_sync(self, record_id: str) -> AuditRecord | None:
        """Synchronous get implementation."""
        try:
            model = self._get_queryset().get(id=record_id)
            return self._to_record(model)
        except self.model_class.DoesNotExist:
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
        qs = self._get_queryset()
        qs = self._apply_filters(qs, tenant_id, principal_id, tool_name, start_time, end_time)
        qs = qs.order_by("-timestamp")
        qs = qs[offset : offset + limit]
        return [self._to_record(m) for m in qs]

    def _apply_filters(
        self,
        qs: models.QuerySet[Any],
        tenant_id: str | None,
        principal_id: str | None,
        tool_name: str | None,
        start_time: datetime | None,
        end_time: datetime | None,
    ) -> models.QuerySet[Any]:
        """Apply filters to a queryset."""
        if tenant_id:
            qs = qs.filter(tenant_id=tenant_id)
        if principal_id:
            qs = qs.filter(principal_id=principal_id)
        if tool_name:
            qs = qs.filter(tool_name=tool_name)
        if start_time:
            qs = qs.filter(timestamp__gte=start_time)
        if end_time:
            qs = qs.filter(timestamp__lte=end_time)
        return qs

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
        qs = self._get_queryset()
        qs = self._apply_filters(qs, tenant_id, principal_id, tool_name, start_time, end_time)
        return qs.count()

    async def delete_before(self, before: datetime) -> int:
        """Delete audit records older than the given timestamp."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._delete_before_sync, before)

    def _delete_before_sync(self, before: datetime) -> int:
        """Synchronous delete implementation."""
        with transaction.atomic(using=self.using):
            qs = self._get_queryset().filter(timestamp__lt=before)
            count, _ = qs.delete()
            return count

    async def bulk_store(self, records: list[AuditRecord]) -> int:
        """Store multiple audit records in a single operation."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._bulk_store_sync, records)

    def _bulk_store_sync(self, records: list[AuditRecord]) -> int:
        """Synchronous bulk store implementation."""
        models_list = [self._to_model(r) for r in records]
        if self.using:
            self.model_class.objects.using(self.using).bulk_create(models_list)
        else:
            self.model_class.objects.bulk_create(models_list)
        return len(records)

    def _to_model(self, record: AuditRecord) -> Any:
        """Convert an AuditRecord to a Django model instance."""
        return self.model_class(
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
            metadata=json.dumps(record.metadata) if record.metadata else None,
        )

    def _to_record(self, model: Any) -> AuditRecord:
        """Convert a Django model instance to an AuditRecord."""
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
            metadata=json.loads(model.metadata) if model.metadata else None,
        )
