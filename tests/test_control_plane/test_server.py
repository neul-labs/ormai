"""Tests for Control Plane Server."""

from datetime import datetime
from uuid import uuid4

import pytest

from ormai.control_plane.models import (
    AuditQuery,
    InstanceHealth,
    InstanceStatus,
)
from ormai.control_plane.server import ControlPlaneServer, create_server
from ormai.policy.models import Budget, ModelPolicy, Policy
from ormai.store.models import AuditRecord, ErrorInfo


@pytest.fixture
def sample_policy() -> Policy:
    """Create a sample policy."""
    return Policy(
        models={"Customer": ModelPolicy(allowed=True)},
        default_budget=Budget(max_rows=100),
    )


@pytest.fixture
def server() -> ControlPlaneServer:
    """Create a server for testing."""
    return create_server()


def make_record(
    tool_name: str = "db.query",
    tenant_id: str = "tenant-1",
    principal_id: str = "user-1",
    duration_ms: float = 50.0,
    row_count: int = 10,
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
        row_count=row_count,
        error=error,
    )


class TestPolicyManagement:
    """Tests for policy management."""

    @pytest.mark.asyncio
    async def test_publish_policy(
        self, server: ControlPlaneServer, sample_policy: Policy
    ) -> None:
        """Publishing policy works."""
        pv = await server.publish_policy(
            policy=sample_policy,
            name="test-policy",
            published_by="admin",
            description="Initial version",
        )
        assert pv.version == "v1"
        assert pv.name == "test-policy"

    @pytest.mark.asyncio
    async def test_activate_policy(
        self, server: ControlPlaneServer, sample_policy: Policy
    ) -> None:
        """Activating policy works."""
        pv = await server.publish_policy(
            policy=sample_policy,
            name="test-policy",
            published_by="admin",
        )
        activated = await server.activate_policy(pv.version)
        assert activated.is_active is True

        active = await server.get_active_policy()
        assert active is not None
        assert active.version == pv.version

    @pytest.mark.asyncio
    async def test_list_policies(
        self, server: ControlPlaneServer, sample_policy: Policy
    ) -> None:
        """Listing policies works."""
        for i in range(3):
            await server.publish_policy(
                policy=sample_policy,
                name=f"policy-{i}",
                published_by="admin",
            )

        policies = await server.list_policies()
        assert len(policies) == 3

    @pytest.mark.asyncio
    async def test_delete_policy(
        self, server: ControlPlaneServer, sample_policy: Policy
    ) -> None:
        """Deleting policy works."""
        pv = await server.publish_policy(
            policy=sample_policy,
            name="test-policy",
            published_by="admin",
        )
        result = await server.delete_policy(pv.version)
        assert result is True

        deleted = await server.get_policy(pv.version)
        assert deleted is None

    @pytest.mark.asyncio
    async def test_diff_policies(
        self, server: ControlPlaneServer
    ) -> None:
        """Diffing policies works."""
        policy1 = Policy(
            models={"Customer": ModelPolicy(allowed=True)},
        )
        policy2 = Policy(
            models={
                "Customer": ModelPolicy(allowed=True),
                "Order": ModelPolicy(allowed=True),
            },
        )

        pv1 = await server.publish_policy(
            policy=policy1, name="test", published_by="admin"
        )
        pv2 = await server.publish_policy(
            policy=policy2, name="test", published_by="admin"
        )

        diff = await server.diff_policies(pv1.version, pv2.version)
        assert diff is not None
        assert "Order" in diff.added_models


class TestInstanceManagement:
    """Tests for instance management."""

    @pytest.mark.asyncio
    async def test_register_instance(self, server: ControlPlaneServer) -> None:
        """Registering instance works."""
        instance, api_key = await server.register_instance(
            name="prod-server",
            endpoint="http://localhost:8000",
            tags=["production", "us-west-2"],
            metadata={"version": "1.0.0"},
        )
        assert instance.name == "prod-server"
        assert instance.endpoint == "http://localhost:8000"
        assert "production" in instance.tags
        assert api_key.startswith("ormai-")

    @pytest.mark.asyncio
    async def test_authenticate_instance(self, server: ControlPlaneServer) -> None:
        """Authenticating instance works."""
        instance, api_key = await server.register_instance(
            name="test-server",
            endpoint="http://localhost:8000",
        )

        authenticated = await server.authenticate_instance(api_key)
        assert authenticated is not None
        assert authenticated.id == instance.id

        # Invalid key returns None
        invalid = await server.authenticate_instance("invalid-key")
        assert invalid is None

    @pytest.mark.asyncio
    async def test_list_instances(self, server: ControlPlaneServer) -> None:
        """Listing instances works."""
        await server.register_instance(
            name="server-1",
            endpoint="http://localhost:8001",
            tags=["production"],
        )
        await server.register_instance(
            name="server-2",
            endpoint="http://localhost:8002",
            tags=["staging"],
        )

        # List all
        all_instances = await server.list_instances()
        assert len(all_instances) == 2

        # Filter by tags
        prod_instances = await server.list_instances(tags=["production"])
        assert len(prod_instances) == 1
        assert prod_instances[0].name == "server-1"

    @pytest.mark.asyncio
    async def test_unregister_instance(self, server: ControlPlaneServer) -> None:
        """Unregistering instance works."""
        instance, _ = await server.register_instance(
            name="test-server",
            endpoint="http://localhost:8000",
        )

        result = await server.unregister_instance(instance.id)
        assert result is True

        deleted = await server.get_instance(instance.id)
        assert deleted is None

    @pytest.mark.asyncio
    async def test_update_instance_health(self, server: ControlPlaneServer) -> None:
        """Updating instance health works."""
        instance, _ = await server.register_instance(
            name="test-server",
            endpoint="http://localhost:8000",
        )

        health = InstanceHealth(
            status=InstanceStatus.ONLINE,
            last_heartbeat=datetime.utcnow(),
            current_policy_version="v1",
            error_rate=0.01,
            avg_latency_ms=50.0,
            tool_calls_count=1000,
        )

        updated = await server.update_instance_health(instance.id, health)
        assert updated is not None
        assert updated.health.status == InstanceStatus.ONLINE
        assert updated.health.tool_calls_count == 1000


class TestAuditManagement:
    """Tests for audit management."""

    @pytest.mark.asyncio
    async def test_ingest_and_query(self, server: ControlPlaneServer) -> None:
        """Ingesting and querying audit records works."""
        instance, _ = await server.register_instance(
            name="test-server",
            endpoint="http://localhost:8000",
        )

        for _ in range(5):
            await server.ingest_audit_record(instance.id, make_record())

        result = await server.query_audit_logs(AuditQuery())
        assert result.total_count == 5

    @pytest.mark.asyncio
    async def test_get_audit_stats(self, server: ControlPlaneServer) -> None:
        """Getting audit stats works."""
        instance, _ = await server.register_instance(
            name="test-server",
            endpoint="http://localhost:8000",
        )

        error = ErrorInfo(type="TestError", message="Test")
        await server.ingest_audit_record(
            instance.id, make_record(duration_ms=100)
        )
        await server.ingest_audit_record(
            instance.id, make_record(error=error, duration_ms=200)
        )

        stats = await server.get_audit_stats()
        assert stats.total_calls == 2
        assert stats.total_errors == 1
        assert stats.avg_latency_ms == 150.0

    @pytest.mark.asyncio
    async def test_get_recent_audit_logs(self, server: ControlPlaneServer) -> None:
        """Getting recent audit logs works."""
        instance, _ = await server.register_instance(
            name="test-server",
            endpoint="http://localhost:8000",
        )

        for _ in range(10):
            await server.ingest_audit_record(instance.id, make_record())

        recent = await server.get_recent_audit_logs(limit=5)
        assert len(recent) == 5


class TestDeploymentManagement:
    """Tests for deployment management."""

    @pytest.mark.asyncio
    async def test_deploy_policy(
        self, server: ControlPlaneServer, sample_policy: Policy
    ) -> None:
        """Deploying policy works."""
        # Register instances
        inst1, _ = await server.register_instance(
            name="server-1",
            endpoint="http://localhost:8001",
            tags=["production"],
        )
        inst2, _ = await server.register_instance(
            name="server-2",
            endpoint="http://localhost:8002",
            tags=["staging"],
        )

        # Publish policy
        pv = await server.publish_policy(
            policy=sample_policy,
            name="test",
            published_by="admin",
        )

        # Deploy to all instances
        deployment = await server.deploy_policy(
            policy_version=pv.version,
            deployed_by="admin",
        )
        assert deployment.success is True
        assert len(deployment.target_instances) == 2

    @pytest.mark.asyncio
    async def test_deploy_to_tagged_instances(
        self, server: ControlPlaneServer, sample_policy: Policy
    ) -> None:
        """Deploying to tagged instances works."""
        await server.register_instance(
            name="server-1",
            endpoint="http://localhost:8001",
            tags=["production"],
        )
        await server.register_instance(
            name="server-2",
            endpoint="http://localhost:8002",
            tags=["staging"],
        )

        pv = await server.publish_policy(
            policy=sample_policy,
            name="test",
            published_by="admin",
        )

        deployment = await server.deploy_policy(
            policy_version=pv.version,
            deployed_by="admin",
            target_tags=["production"],
        )
        assert len(deployment.target_instances) == 1

    @pytest.mark.asyncio
    async def test_list_deployments(
        self, server: ControlPlaneServer, sample_policy: Policy
    ) -> None:
        """Listing deployments works."""
        await server.register_instance(
            name="server",
            endpoint="http://localhost:8000",
        )

        pv = await server.publish_policy(
            policy=sample_policy,
            name="test",
            published_by="admin",
        )

        for _ in range(3):
            await server.deploy_policy(
                policy_version=pv.version,
                deployed_by="admin",
            )

        deployments = await server.list_deployments()
        assert len(deployments) == 3

    @pytest.mark.asyncio
    async def test_get_deployment(
        self, server: ControlPlaneServer, sample_policy: Policy
    ) -> None:
        """Getting deployment by ID works."""
        await server.register_instance(
            name="server",
            endpoint="http://localhost:8000",
        )

        pv = await server.publish_policy(
            policy=sample_policy,
            name="test",
            published_by="admin",
        )

        deployment = await server.deploy_policy(
            policy_version=pv.version,
            deployed_by="admin",
        )

        retrieved = await server.get_deployment(deployment.id)
        assert retrieved is not None
        assert retrieved.id == deployment.id


class TestDashboard:
    """Tests for dashboard summary."""

    @pytest.mark.asyncio
    async def test_get_dashboard_summary(
        self, server: ControlPlaneServer, sample_policy: Policy
    ) -> None:
        """Getting dashboard summary works."""
        # Register instances
        inst, _ = await server.register_instance(
            name="server",
            endpoint="http://localhost:8000",
        )

        # Update health to online
        health = InstanceHealth(
            status=InstanceStatus.ONLINE,
            last_heartbeat=datetime.utcnow(),
        )
        await server.update_instance_health(inst.id, health)

        # Publish policy
        await server.publish_policy(
            policy=sample_policy,
            name="test",
            published_by="admin",
            activate=True,
        )

        # Add some audit records
        error = ErrorInfo(type="TestError", message="Test")
        await server.ingest_audit_record(inst.id, make_record())
        await server.ingest_audit_record(inst.id, make_record(error=error))

        summary = await server.get_dashboard_summary()

        assert summary["instances"]["total"] == 1
        assert summary["instances"]["online"] == 1
        assert summary["policies"]["total"] == 1
        assert summary["policies"]["active_version"] == "v1"
        assert summary["audit"]["calls_last_hour"] == 2
        assert summary["audit"]["errors_last_hour"] == 1
