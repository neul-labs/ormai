"""Tests for SQL-based audit stores."""

import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from peewee import SqliteDatabase

from ormai.store.models import AuditRecord, ErrorInfo
from ormai.store.peewee import PeeweeAuditStore


@pytest.fixture
def peewee_db(tmp_path):
    """Create a file-based SQLite database for testing."""
    db_path = tmp_path / "test_audit.db"
    db = SqliteDatabase(str(db_path))
    db.connect()
    yield db
    db.close()


@pytest.fixture
def peewee_store(peewee_db):
    """Create a PeeweeAuditStore."""
    store = PeeweeAuditStore.create(peewee_db, create_table=True)
    return store


@pytest.fixture
def sample_record():
    """Create a sample audit record."""
    return AuditRecord(
        id="test-123",
        tool_name="db.query",
        principal_id="user-1",
        tenant_id="tenant-1",
        request_id="req-456",
        timestamp=datetime.now(timezone.utc),
        inputs={"model": "Customer", "take": 10},
        outputs={"data": [{"id": 1, "name": "Alice"}]},
        policy_decisions=["tenant_scope_applied"],
        row_count=1,
        duration_ms=15.5,
    )


class TestPeeweeAuditStore:
    """Tests for PeeweeAuditStore."""

    @pytest.mark.asyncio
    async def test_store_and_get(self, peewee_store, sample_record):
        """Test storing and retrieving a record."""
        await peewee_store.store(sample_record)

        retrieved = await peewee_store.get(sample_record.id)

        assert retrieved is not None
        assert retrieved.id == sample_record.id
        assert retrieved.tool_name == sample_record.tool_name
        assert retrieved.principal_id == sample_record.principal_id
        assert retrieved.tenant_id == sample_record.tenant_id
        assert retrieved.inputs == sample_record.inputs
        assert retrieved.outputs == sample_record.outputs
        assert retrieved.row_count == sample_record.row_count

    @pytest.mark.asyncio
    async def test_get_nonexistent(self, peewee_store):
        """Test getting a non-existent record."""
        result = await peewee_store.get("nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_store_with_error(self, peewee_store):
        """Test storing a record with an error."""
        record = AuditRecord(
            id="error-123",
            tool_name="db.query",
            principal_id="user-1",
            tenant_id="tenant-1",
            timestamp=datetime.now(timezone.utc),
            inputs={"model": "Customer"},
            error=ErrorInfo(
                type="PolicyError",
                message="Access denied",
                code="ACCESS_DENIED",
            ),
            duration_ms=5.0,
        )

        await peewee_store.store(record)
        retrieved = await peewee_store.get(record.id)

        assert retrieved is not None
        assert retrieved.error is not None
        assert retrieved.error.type == "PolicyError"
        assert retrieved.error.message == "Access denied"

    @pytest.mark.asyncio
    async def test_store_with_snapshots(self, peewee_store):
        """Test storing a record with before/after snapshots."""
        record = AuditRecord(
            id="mutation-123",
            tool_name="db.update",
            principal_id="user-1",
            tenant_id="tenant-1",
            timestamp=datetime.now(timezone.utc),
            inputs={"model": "Customer", "id": 1, "data": {"name": "Bob"}},
            before_snapshot={"id": 1, "name": "Alice"},
            after_snapshot={"id": 1, "name": "Bob"},
            reason="Customer requested name change",
            duration_ms=25.0,
        )

        await peewee_store.store(record)
        retrieved = await peewee_store.get(record.id)

        assert retrieved is not None
        assert retrieved.before_snapshot == {"id": 1, "name": "Alice"}
        assert retrieved.after_snapshot == {"id": 1, "name": "Bob"}
        assert retrieved.reason == "Customer requested name change"

    @pytest.mark.asyncio
    async def test_query_by_tenant(self, peewee_store):
        """Test querying by tenant."""
        now = datetime.now(timezone.utc)

        # Create records for different tenants
        for i in range(3):
            await peewee_store.store(AuditRecord(
                id=f"t1-{i}",
                tool_name="db.query",
                principal_id="user-1",
                tenant_id="tenant-1",
                timestamp=now,
                inputs={},
            ))

        for i in range(2):
            await peewee_store.store(AuditRecord(
                id=f"t2-{i}",
                tool_name="db.query",
                principal_id="user-1",
                tenant_id="tenant-2",
                timestamp=now,
                inputs={},
            ))

        results = await peewee_store.query(tenant_id="tenant-1")
        assert len(results) == 3

        results = await peewee_store.query(tenant_id="tenant-2")
        assert len(results) == 2

    @pytest.mark.asyncio
    async def test_query_by_principal(self, peewee_store):
        """Test querying by principal."""
        now = datetime.now(timezone.utc)

        await peewee_store.store(AuditRecord(
            id="u1-1",
            tool_name="db.query",
            principal_id="user-1",
            tenant_id="tenant-1",
            timestamp=now,
            inputs={},
        ))

        await peewee_store.store(AuditRecord(
            id="u2-1",
            tool_name="db.query",
            principal_id="user-2",
            tenant_id="tenant-1",
            timestamp=now,
            inputs={},
        ))

        results = await peewee_store.query(principal_id="user-1")
        assert len(results) == 1
        assert results[0].principal_id == "user-1"

    @pytest.mark.asyncio
    async def test_query_by_tool(self, peewee_store):
        """Test querying by tool name."""
        now = datetime.now(timezone.utc)

        await peewee_store.store(AuditRecord(
            id="query-1",
            tool_name="db.query",
            principal_id="user-1",
            tenant_id="tenant-1",
            timestamp=now,
            inputs={},
        ))

        await peewee_store.store(AuditRecord(
            id="get-1",
            tool_name="db.get",
            principal_id="user-1",
            tenant_id="tenant-1",
            timestamp=now,
            inputs={},
        ))

        results = await peewee_store.query(tool_name="db.query")
        assert len(results) == 1
        assert results[0].tool_name == "db.query"

    @pytest.mark.asyncio
    async def test_query_by_time_range(self, peewee_store):
        """Test querying by time range."""
        now = datetime.now(timezone.utc)
        yesterday = now - timedelta(days=1)
        tomorrow = now + timedelta(days=1)

        await peewee_store.store(AuditRecord(
            id="old-1",
            tool_name="db.query",
            principal_id="user-1",
            tenant_id="tenant-1",
            timestamp=yesterday,
            inputs={},
        ))

        await peewee_store.store(AuditRecord(
            id="new-1",
            tool_name="db.query",
            principal_id="user-1",
            tenant_id="tenant-1",
            timestamp=now,
            inputs={},
        ))

        # Query for today onwards
        results = await peewee_store.query(
            start_time=now - timedelta(hours=1),
            end_time=tomorrow,
        )
        assert len(results) == 1
        assert results[0].id == "new-1"

    @pytest.mark.asyncio
    async def test_query_with_limit_offset(self, peewee_store):
        """Test query pagination."""
        now = datetime.now(timezone.utc)

        for i in range(10):
            await peewee_store.store(AuditRecord(
                id=f"rec-{i:02d}",
                tool_name="db.query",
                principal_id="user-1",
                tenant_id="tenant-1",
                timestamp=now - timedelta(seconds=i),  # Different times for ordering
                inputs={},
            ))

        # Get first page
        results = await peewee_store.query(limit=3, offset=0)
        assert len(results) == 3

        # Get second page
        results = await peewee_store.query(limit=3, offset=3)
        assert len(results) == 3

    def test_count_sync(self, peewee_store):
        """Test synchronous count."""
        now = datetime.now(timezone.utc)

        for i in range(5):
            peewee_store._store_sync(AuditRecord(
                id=f"count-{i}",
                tool_name="db.query",
                principal_id="user-1",
                tenant_id="tenant-1",
                timestamp=now,
                inputs={},
            ))

        count = peewee_store.count_sync(tenant_id="tenant-1")
        assert count == 5

    def test_delete_before_sync(self, peewee_store):
        """Test synchronous delete before date."""
        now = datetime.now(timezone.utc)
        old = now - timedelta(days=30)

        # Create old and new records
        peewee_store._store_sync(AuditRecord(
            id="old-1",
            tool_name="db.query",
            principal_id="user-1",
            tenant_id="tenant-1",
            timestamp=old,
            inputs={},
        ))

        peewee_store._store_sync(AuditRecord(
            id="new-1",
            tool_name="db.query",
            principal_id="user-1",
            tenant_id="tenant-1",
            timestamp=now,
            inputs={},
        ))

        # Delete old records
        deleted = peewee_store.delete_before_sync(now - timedelta(days=7))
        assert deleted == 1

        # Verify only new record remains
        assert peewee_store.count_sync() == 1
