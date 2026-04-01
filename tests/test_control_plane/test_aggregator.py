"""Tests for Audit Aggregator."""

from datetime import datetime, timedelta
from uuid import uuid4

import pytest

from ormai.control_plane.aggregator import (
    FederatedAuditAggregator,
    InMemoryAuditAggregator,
)
from ormai.control_plane.models import AuditQuery
from ormai.store.jsonl import JsonlAuditStore
from ormai.store.models import AuditRecord, ErrorInfo


def make_record(
    tool_name: str = "db.query",
    tenant_id: str = "tenant-1",
    principal_id: str = "user-1",
    model: str | None = None,
    duration_ms: float = 50.0,
    row_count: int = 10,
    error: ErrorInfo | None = None,
    timestamp: datetime | None = None,
) -> AuditRecord:
    """Create a test audit record."""
    return AuditRecord(
        id=str(uuid4()),
        tool_name=tool_name,
        tenant_id=tenant_id,
        principal_id=principal_id,
        request_id=str(uuid4()),
        timestamp=timestamp or datetime.utcnow(),
        duration_ms=duration_ms,
        inputs={"model": model} if model else {},
        row_count=row_count,
        error=error,
    )


class TestInMemoryAuditAggregator:
    """Tests for in-memory audit aggregator."""

    @pytest.fixture
    def aggregator(self) -> InMemoryAuditAggregator:
        """Create an aggregator for testing."""
        return InMemoryAuditAggregator(max_records=1000, retention_hours=24)

    @pytest.mark.asyncio
    async def test_ingest_and_query(
        self, aggregator: InMemoryAuditAggregator
    ) -> None:
        """Ingesting and querying records works."""
        for _ in range(5):
            await aggregator.ingest("instance-1", make_record())

        result = await aggregator.query(AuditQuery())
        assert result.total_count == 5
        assert len(result.records) == 5

    @pytest.mark.asyncio
    async def test_query_filter_by_tenant(
        self, aggregator: InMemoryAuditAggregator
    ) -> None:
        """Query filters by tenant."""
        await aggregator.ingest("inst-1", make_record(tenant_id="tenant-a"))
        await aggregator.ingest("inst-1", make_record(tenant_id="tenant-b"))
        await aggregator.ingest("inst-1", make_record(tenant_id="tenant-a"))

        result = await aggregator.query(AuditQuery(tenant_id="tenant-a"))
        assert result.total_count == 2

    @pytest.mark.asyncio
    async def test_query_filter_by_tool(
        self, aggregator: InMemoryAuditAggregator
    ) -> None:
        """Query filters by tool name."""
        await aggregator.ingest("inst-1", make_record(tool_name="db.query"))
        await aggregator.ingest("inst-1", make_record(tool_name="db.get"))
        await aggregator.ingest("inst-1", make_record(tool_name="db.query"))

        result = await aggregator.query(AuditQuery(tool_name="db.query"))
        assert result.total_count == 2

    @pytest.mark.asyncio
    async def test_query_filter_by_instance(
        self, aggregator: InMemoryAuditAggregator
    ) -> None:
        """Query filters by instance ID."""
        await aggregator.ingest("inst-1", make_record())
        await aggregator.ingest("inst-2", make_record())
        await aggregator.ingest("inst-1", make_record())

        result = await aggregator.query(AuditQuery(instance_id="inst-1"))
        assert result.total_count == 2

    @pytest.mark.asyncio
    async def test_query_filter_by_time_range(
        self, aggregator: InMemoryAuditAggregator
    ) -> None:
        """Query filters by time range."""
        now = datetime.utcnow()
        old = now - timedelta(hours=2)
        very_old = now - timedelta(hours=5)

        await aggregator.ingest("inst-1", make_record(timestamp=very_old))
        await aggregator.ingest("inst-1", make_record(timestamp=old))
        await aggregator.ingest("inst-1", make_record(timestamp=now))

        result = await aggregator.query(
            AuditQuery(
                start_time=now - timedelta(hours=3),
                end_time=now + timedelta(minutes=1),
            )
        )
        assert result.total_count == 2

    @pytest.mark.asyncio
    async def test_query_errors_only(
        self, aggregator: InMemoryAuditAggregator
    ) -> None:
        """Query filters to errors only."""
        error = ErrorInfo(type="TestError", message="Test error")
        await aggregator.ingest("inst-1", make_record())
        await aggregator.ingest("inst-1", make_record(error=error))
        await aggregator.ingest("inst-1", make_record())

        result = await aggregator.query(AuditQuery(errors_only=True))
        assert result.total_count == 1

    @pytest.mark.asyncio
    async def test_query_filter_by_model(
        self, aggregator: InMemoryAuditAggregator
    ) -> None:
        """Query filters by model in inputs."""
        await aggregator.ingest("inst-1", make_record(model="Customer"))
        await aggregator.ingest("inst-1", make_record(model="Order"))
        await aggregator.ingest("inst-1", make_record(model="Customer"))

        result = await aggregator.query(AuditQuery(model="Customer"))
        assert result.total_count == 2

    @pytest.mark.asyncio
    async def test_query_pagination(
        self, aggregator: InMemoryAuditAggregator
    ) -> None:
        """Query supports pagination."""
        for _ in range(20):
            await aggregator.ingest("inst-1", make_record())

        result = await aggregator.query(AuditQuery(limit=5, offset=10))
        assert result.total_count == 20
        assert len(result.records) == 5

    @pytest.mark.asyncio
    async def test_query_sorting(
        self, aggregator: InMemoryAuditAggregator
    ) -> None:
        """Query supports sorting."""
        now = datetime.utcnow()
        for i in range(3):
            await aggregator.ingest(
                "inst-1",
                make_record(timestamp=now - timedelta(minutes=i)),
            )

        # Default: sort by timestamp desc
        result = await aggregator.query(AuditQuery())
        timestamps = [r.timestamp for r in result.records]
        assert timestamps == sorted(timestamps, reverse=True)

        # Sort by timestamp asc
        result = await aggregator.query(
            AuditQuery(sort_by="timestamp", sort_desc=False)
        )
        timestamps = [r.timestamp for r in result.records]
        assert timestamps == sorted(timestamps)

    @pytest.mark.asyncio
    async def test_get_stats(
        self, aggregator: InMemoryAuditAggregator
    ) -> None:
        """Getting stats works."""
        error = ErrorInfo(type="TestError", message="Test error")
        await aggregator.ingest(
            "inst-1", make_record(tool_name="db.query", model="Customer", duration_ms=100)
        )
        await aggregator.ingest(
            "inst-1", make_record(tool_name="db.get", model="Order", duration_ms=50)
        )
        await aggregator.ingest(
            "inst-2", make_record(tool_name="db.query", error=error, duration_ms=200)
        )

        stats = await aggregator.get_stats()

        assert stats.total_calls == 3
        assert stats.calls_by_tool["db.query"] == 2
        assert stats.calls_by_tool["db.get"] == 1
        assert stats.calls_by_model["Customer"] == 1
        assert stats.calls_by_instance["inst-1"] == 2
        assert stats.calls_by_instance["inst-2"] == 1
        assert stats.total_errors == 1
        assert stats.errors_by_type["TestError"] == 1
        assert stats.avg_latency_ms > 0

    @pytest.mark.asyncio
    async def test_get_stats_with_filter(
        self, aggregator: InMemoryAuditAggregator
    ) -> None:
        """Getting stats with instance filter works."""
        await aggregator.ingest("inst-1", make_record())
        await aggregator.ingest("inst-2", make_record())
        await aggregator.ingest("inst-1", make_record())

        stats = await aggregator.get_stats(instance_id="inst-1")
        assert stats.total_calls == 2

    @pytest.mark.asyncio
    async def test_get_recent(
        self, aggregator: InMemoryAuditAggregator
    ) -> None:
        """Getting recent records works."""
        now = datetime.utcnow()
        for i in range(10):
            await aggregator.ingest(
                "inst-1",
                make_record(timestamp=now - timedelta(minutes=i)),
            )

        recent = await aggregator.get_recent(limit=5)
        assert len(recent) == 5
        # Should be sorted by timestamp descending
        assert recent[0].timestamp >= recent[-1].timestamp

    @pytest.mark.asyncio
    async def test_max_records_enforcement(
        self, aggregator: InMemoryAuditAggregator
    ) -> None:
        """Aggregator enforces max records limit."""
        aggregator._max_records = 10

        for _ in range(20):
            await aggregator.ingest("inst-1", make_record())

        result = await aggregator.query(AuditQuery())
        assert result.total_count == 10


class TestFederatedAuditAggregator:
    """Tests for federated audit aggregator."""

    @pytest.fixture
    def aggregator(self) -> FederatedAuditAggregator:
        """Create an aggregator for testing."""
        return FederatedAuditAggregator(timeout_seconds=5.0)

    @pytest.mark.asyncio
    async def test_register_and_query_stores(
        self, aggregator: FederatedAuditAggregator, tmp_path
    ) -> None:
        """Registering stores and querying works."""
        # Create two stores
        store1 = JsonlAuditStore(str(tmp_path / "store1.jsonl"))
        store2 = JsonlAuditStore(str(tmp_path / "store2.jsonl"))

        await aggregator.register_store("inst-1", store1)
        await aggregator.register_store("inst-2", store2)

        # Add records to each store
        await store1.store(make_record(tool_name="db.query"))
        await store1.store(make_record(tool_name="db.get"))
        await store2.store(make_record(tool_name="db.query"))

        # Query across stores
        result = await aggregator.query(AuditQuery())
        assert result.total_count == 3
        assert set(result.instances_queried) == {"inst-1", "inst-2"}

    @pytest.mark.asyncio
    async def test_query_single_instance(
        self, aggregator: FederatedAuditAggregator, tmp_path
    ) -> None:
        """Querying a single instance works."""
        store1 = JsonlAuditStore(str(tmp_path / "store1.jsonl"))
        store2 = JsonlAuditStore(str(tmp_path / "store2.jsonl"))

        await aggregator.register_store("inst-1", store1)
        await aggregator.register_store("inst-2", store2)

        await store1.store(make_record())
        await store1.store(make_record())
        await store2.store(make_record())

        result = await aggregator.query(AuditQuery(instance_id="inst-1"))
        assert result.total_count == 2

    @pytest.mark.asyncio
    async def test_ingest_to_store(
        self, aggregator: FederatedAuditAggregator, tmp_path
    ) -> None:
        """Ingesting stores to registered store."""
        store = JsonlAuditStore(str(tmp_path / "store.jsonl"))
        await aggregator.register_store("inst-1", store)

        record = make_record()
        await aggregator.ingest("inst-1", record)

        # Verify record was stored
        stored = await store.get(record.id)
        assert stored is not None
        assert stored.id == record.id

    @pytest.mark.asyncio
    async def test_unregister_store(
        self, aggregator: FederatedAuditAggregator, tmp_path
    ) -> None:
        """Unregistering store works."""
        store = JsonlAuditStore(str(tmp_path / "store.jsonl"))
        await aggregator.register_store("inst-1", store)
        await store.store(make_record())

        await aggregator.unregister_store("inst-1")

        result = await aggregator.query(AuditQuery())
        assert result.total_count == 0

    @pytest.mark.asyncio
    async def test_get_stats_federated(
        self, aggregator: FederatedAuditAggregator, tmp_path
    ) -> None:
        """Getting stats from federated stores works."""
        store1 = JsonlAuditStore(str(tmp_path / "store1.jsonl"))
        store2 = JsonlAuditStore(str(tmp_path / "store2.jsonl"))

        await aggregator.register_store("inst-1", store1)
        await aggregator.register_store("inst-2", store2)

        await store1.store(make_record(duration_ms=100, row_count=10))
        await store2.store(make_record(duration_ms=200, row_count=20))

        stats = await aggregator.get_stats()
        assert stats.total_calls == 2
        assert stats.avg_latency_ms == 150.0
        assert stats.total_rows_returned == 30

    @pytest.mark.asyncio
    async def test_get_recent_federated(
        self, aggregator: FederatedAuditAggregator, tmp_path
    ) -> None:
        """Getting recent records from federated stores works."""
        store1 = JsonlAuditStore(str(tmp_path / "store1.jsonl"))
        store2 = JsonlAuditStore(str(tmp_path / "store2.jsonl"))

        await aggregator.register_store("inst-1", store1)
        await aggregator.register_store("inst-2", store2)

        now = datetime.utcnow()
        await store1.store(make_record(timestamp=now - timedelta(minutes=2)))
        await store2.store(make_record(timestamp=now - timedelta(minutes=1)))
        await store1.store(make_record(timestamp=now))

        recent = await aggregator.get_recent(limit=2)
        assert len(recent) == 2
        assert recent[0].timestamp >= recent[1].timestamp
