"""Tests for JSONL audit store."""

from datetime import datetime, timezone

import pytest

from ormai.store.jsonl import JsonlAuditStore
from ormai.store.models import AuditRecord


def make_record(**kwargs):
    defaults = dict(
        id="rec-001",
        tenant_id="tenant-1",
        principal_id="user-1",
        tool_name="query",
        timestamp=datetime.now(timezone.utc),
    )
    defaults.update(kwargs)
    return AuditRecord(**defaults)


@pytest.fixture
def store(tmp_path):
    path = tmp_path / "audit.jsonl"
    return JsonlAuditStore(path)


@pytest.fixture
def sample_record():
    return make_record()


@pytest.fixture
def sample_record_2():
    return make_record(
        id="rec-002",
        tenant_id="tenant-2",
        principal_id="user-2",
        tool_name="create",
    )


class TestJsonlAuditStore:
    @pytest.mark.asyncio
    async def test_store_creates_file(self, store, sample_record):
        await store.store(sample_record)
        assert store.path.exists()

    @pytest.mark.asyncio
    async def test_store_and_get(self, store, sample_record):
        await store.store(sample_record)
        result = await store.get("rec-001")
        assert result is not None
        assert result.id == "rec-001"
        assert result.tenant_id == "tenant-1"

    @pytest.mark.asyncio
    async def test_get_nonexistent_id(self, store, sample_record):
        await store.store(sample_record)
        result = await store.get("nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_missing_file(self, tmp_path):
        store = JsonlAuditStore(tmp_path / "nonexistent.jsonl")
        result = await store.get("any-id")
        assert result is None

    @pytest.mark.asyncio
    async def test_store_multiple_and_get(self, store, sample_record, sample_record_2):
        await store.store(sample_record)
        await store.store(sample_record_2)
        result1 = await store.get("rec-001")
        result2 = await store.get("rec-002")
        assert result1.id == "rec-001"
        assert result2.id == "rec-002"

    @pytest.mark.asyncio
    async def test_query_no_filters(self, store, sample_record):
        await store.store(sample_record)
        results = await store.query()
        assert len(results) == 1

    @pytest.mark.asyncio
    async def test_query_by_tenant(self, store, sample_record, sample_record_2):
        await store.store(sample_record)
        await store.store(sample_record_2)
        results = await store.query(tenant_id="tenant-1")
        assert len(results) == 1
        assert results[0].tenant_id == "tenant-1"

    @pytest.mark.asyncio
    async def test_query_by_principal(self, store, sample_record, sample_record_2):
        await store.store(sample_record)
        await store.store(sample_record_2)
        results = await store.query(principal_id="user-2")
        assert len(results) == 1
        assert results[0].principal_id == "user-2"

    @pytest.mark.asyncio
    async def test_query_by_tool_name(self, store, sample_record, sample_record_2):
        await store.store(sample_record)
        await store.store(sample_record_2)
        results = await store.query(tool_name="create")
        assert len(results) == 1
        assert results[0].tool_name == "create"

    @pytest.mark.asyncio
    async def test_query_with_limit(self, store):
        for i in range(5):
            record = make_record(id=f"rec-{i}")
            await store.store(record)

        results = await store.query(limit=3)
        assert len(results) == 3

    @pytest.mark.asyncio
    async def test_query_with_offset(self, store):
        for i in range(5):
            record = make_record(id=f"rec-{i}")
            await store.store(record)

        results = await store.query(offset=2)
        assert len(results) == 3

    @pytest.mark.asyncio
    async def test_query_missing_file(self, tmp_path):
        store = JsonlAuditStore(tmp_path / "nonexistent.jsonl")
        results = await store.query()
        assert results == []

    @pytest.mark.asyncio
    async def test_count(self, store, sample_record, sample_record_2):
        await store.store(sample_record)
        await store.store(sample_record_2)
        total = await store.count()
        assert total == 2

    @pytest.mark.asyncio
    async def test_count_with_filter(self, store, sample_record, sample_record_2):
        await store.store(sample_record)
        await store.store(sample_record_2)
        count = await store.count(tenant_id="tenant-1")
        assert count == 1

    @pytest.mark.asyncio
    async def test_count_missing_file(self, tmp_path):
        store = JsonlAuditStore(tmp_path / "nonexistent.jsonl")
        count = await store.count()
        assert count == 0

    @pytest.mark.asyncio
    async def test_delete_before(self, store):
        old_time = datetime(2024, 1, 1, tzinfo=timezone.utc)
        new_time = datetime(2025, 6, 1, tzinfo=timezone.utc)

        old_record = make_record(id="old", timestamp=old_time)
        new_record = make_record(id="new", timestamp=new_time)
        await store.store(old_record)
        await store.store(new_record)

        deleted = await store.delete_before(datetime(2025, 1, 1, tzinfo=timezone.utc))
        assert deleted == 1

        results = await store.query()
        assert len(results) == 1
        assert results[0].id == "new"

    @pytest.mark.asyncio
    async def test_delete_before_no_match(self, store, sample_record):
        await store.store(sample_record)
        deleted = await store.delete_before(datetime(2020, 1, 1, tzinfo=timezone.utc))
        assert deleted == 0

    @pytest.mark.asyncio
    async def test_delete_before_missing_file(self, tmp_path):
        store = JsonlAuditStore(tmp_path / "nonexistent.jsonl")
        deleted = await store.delete_before(datetime.now(timezone.utc))
        assert deleted == 0

    def test_clear(self, store, sample_record):
        import asyncio

        asyncio.run(store.store(sample_record))
        assert store.path.exists()
        store.clear()
        assert not store.path.exists()

    def test_clear_missing_file(self, tmp_path):
        store = JsonlAuditStore(tmp_path / "nonexistent.jsonl")
        store.clear()

    @pytest.mark.asyncio
    async def test_serialization_roundtrip(self, store):
        record = make_record(
            id="roundtrip-test",
            timestamp=datetime(2024, 6, 15, 12, 30, 45, tzinfo=timezone.utc),
            policy_decisions=["allowed"],
        )
        await store.store(record)
        result = await store.get("roundtrip-test")
        assert result is not None
        assert result.id == "roundtrip-test"
        assert result.tenant_id == "tenant-1"
        assert result.tool_name == "query"