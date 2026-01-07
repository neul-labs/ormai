"""Tests for Control Plane Client."""

from datetime import datetime
from uuid import uuid4

import pytest

from ormai.control_plane.client import (
    ControlPlaneClient,
    LocalControlPlaneClient,
    create_client,
)
from ormai.policy.models import Budget, ModelPolicy, Policy
from ormai.store.jsonl import JsonlAuditStore
from ormai.store.models import AuditRecord, ErrorInfo


def make_record(
    tool_name: str = "db.query",
    tenant_id: str = "tenant-1",
    principal_id: str = "user-1",
    duration_ms: float = 50.0,
    error: ErrorInfo | None = None,
) -> AuditRecord:
    """Create a test audit record."""
    return AuditRecord(
        id=str(uuid4()),
        tool_name=tool_name,
        tenant_id=tenant_id,
        principal_id=principal_id,
        request_id=str(uuid4()),
        timestamp=datetime.utcnow(),
        duration_ms=duration_ms,
        inputs={},
        error=error,
    )


class TestControlPlaneClient:
    """Tests for control plane client."""

    @pytest.fixture
    def client(self) -> ControlPlaneClient:
        """Create a client for testing."""
        return ControlPlaneClient(
            instance_id="test-instance",
            instance_name="Test Instance",
            control_plane_url=None,  # Local mode
            sync_interval_seconds=60.0,
            heartbeat_interval_seconds=30.0,
        )

    def test_initialization(self, client: ControlPlaneClient) -> None:
        """Client initializes correctly."""
        assert client.instance_id == "test-instance"
        assert client.instance_name == "Test Instance"
        assert client.current_policy is None

    @pytest.mark.asyncio
    async def test_start_and_stop(self, client: ControlPlaneClient) -> None:
        """Client starts and stops correctly."""
        await client.start()
        assert client._running is True

        await client.stop()
        assert client._running is False

    @pytest.mark.asyncio
    async def test_record_tool_call(self, client: ControlPlaneClient) -> None:
        """Recording tool calls works."""
        record = make_record()
        await client.record_tool_call(record)

        assert len(client._audit_buffer) == 1

    @pytest.mark.asyncio
    async def test_record_updates_metrics(self, client: ControlPlaneClient) -> None:
        """Recording tool calls updates metrics."""
        # Normal call
        await client.record_tool_call(make_record(duration_ms=100))
        assert client._call_count == 1
        assert client._error_count == 0
        assert client._total_latency_ms == 100

        # Error call
        error = ErrorInfo(type="TestError", message="Test")
        await client.record_tool_call(make_record(error=error, duration_ms=50))
        assert client._call_count == 2
        assert client._error_count == 1
        assert client._total_latency_ms == 150

    @pytest.mark.asyncio
    async def test_get_health(self, client: ControlPlaneClient) -> None:
        """Getting health metrics works."""
        await client.record_tool_call(make_record(duration_ms=100))
        await client.record_tool_call(make_record(duration_ms=200))
        error = ErrorInfo(type="TestError", message="Test")
        await client.record_tool_call(make_record(error=error, duration_ms=300))

        health = client.get_health()
        assert health.tool_calls_count == 3
        assert health.error_rate == 1 / 3
        assert health.avg_latency_ms == 200.0

    @pytest.mark.asyncio
    async def test_reset_metrics(self, client: ControlPlaneClient) -> None:
        """Resetting metrics works."""
        await client.record_tool_call(make_record())
        await client.record_tool_call(make_record())

        client.reset_metrics()

        assert client._call_count == 0
        assert client._error_count == 0
        assert client._total_latency_ms == 0.0

    @pytest.mark.asyncio
    async def test_flush_to_local_store(
        self, client: ControlPlaneClient, tmp_path
    ) -> None:
        """Flushing to local store works."""
        store = JsonlAuditStore(str(tmp_path / "audit.jsonl"))
        client.set_local_audit_store(store)

        record = make_record()
        await client.record_tool_call(record)
        await client._flush_audit_buffer()

        # Verify record was stored
        stored = await store.get(record.id)
        assert stored is not None

    @pytest.mark.asyncio
    async def test_batch_flush(self, client: ControlPlaneClient, tmp_path) -> None:
        """Batch flushing works when buffer is full."""
        store = JsonlAuditStore(str(tmp_path / "audit.jsonl"))
        client.set_local_audit_store(store)
        client._audit_batch_size = 5

        # Add records up to batch size
        for _ in range(5):
            await client.record_tool_call(make_record())

        # Buffer should be flushed
        assert len(client._audit_buffer) == 0

        # Verify records were stored
        records = await store.query(limit=10)
        assert len(records) == 5


class TestLocalControlPlaneClient:
    """Tests for local-only control plane client."""

    @pytest.fixture
    def policy(self) -> Policy:
        """Create a sample policy."""
        return Policy(
            models={"Customer": ModelPolicy(allowed=True)},
            default_budget=Budget(max_rows=100),
        )

    def test_initialization_with_policy(self, policy: Policy) -> None:
        """Client initializes with policy."""
        client = LocalControlPlaneClient(
            instance_id="test",
            instance_name="Test",
            initial_policy=policy,
        )
        assert client.current_policy == policy
        assert client.current_policy_version == "local-v1"

    def test_set_policy(self, policy: Policy) -> None:
        """Setting policy works."""
        client = LocalControlPlaneClient(
            instance_id="test",
            instance_name="Test",
        )
        assert client.current_policy is None

        client.set_policy(policy, version="v1.0")
        assert client.current_policy == policy
        assert client.current_policy_version == "v1.0"

    @pytest.mark.asyncio
    async def test_start_minimal(self) -> None:
        """Start is minimal for local client."""
        client = LocalControlPlaneClient(
            instance_id="test",
            instance_name="Test",
        )
        await client.start()
        assert client._running is True
        # Only audit task should be running
        assert client._sync_task is None
        assert client._heartbeat_task is None
        assert client._audit_task is not None
        await client.stop()

    @pytest.mark.asyncio
    async def test_audit_to_local_store(self, tmp_path) -> None:
        """Audit records go to local store."""
        store = JsonlAuditStore(str(tmp_path / "audit.jsonl"))
        client = LocalControlPlaneClient(
            instance_id="test",
            instance_name="Test",
            audit_store=store,
        )

        record = make_record()
        await client.record_tool_call(record)
        await client._flush_audit_buffer()

        stored = await store.get(record.id)
        assert stored is not None


class TestCreateClient:
    """Tests for client factory function."""

    def test_creates_local_client_without_url(self) -> None:
        """Creates local client when no URL provided."""
        client = create_client(
            instance_id="test",
            instance_name="Test",
        )
        assert isinstance(client, LocalControlPlaneClient)

    def test_creates_remote_client_with_url(self) -> None:
        """Creates remote client when URL provided."""
        client = create_client(
            instance_id="test",
            instance_name="Test",
            control_plane_url="http://localhost:8000",
        )
        assert isinstance(client, ControlPlaneClient)
        assert not isinstance(client, LocalControlPlaneClient)

    def test_passes_initial_policy_to_local(self) -> None:
        """Passes initial policy to local client."""
        policy = Policy(models={})
        client = create_client(
            instance_id="test",
            instance_name="Test",
            initial_policy=policy,
        )
        assert client.current_policy == policy

    def test_sets_audit_store(self, tmp_path) -> None:
        """Sets audit store on client."""
        store = JsonlAuditStore(str(tmp_path / "audit.jsonl"))
        client = create_client(
            instance_id="test",
            instance_name="Test",
            audit_store=store,
        )
        assert client._local_audit_store == store
