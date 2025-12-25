"""
Control Plane Server.

Provides the management API and backend for:
- Policy registry (versioning, distribution)
- Instance registration and health monitoring
- Audit log aggregation and querying
"""

import hashlib
import secrets
from datetime import datetime, timedelta
from typing import Any

from ormai.control_plane.aggregator import AuditAggregator, InMemoryAuditAggregator
from ormai.control_plane.models import (
    AuditQuery,
    AuditQueryResult,
    AuditStats,
    Instance,
    InstanceHealth,
    InstanceStatus,
    PolicyDeployment,
    PolicyDiff,
    PolicyVersion,
)
from ormai.control_plane.registry import InMemoryPolicyRegistry, PolicyRegistry
from ormai.policy.models import Policy
from ormai.store.models import AuditRecord


class ControlPlaneServer:
    """
    Control plane server that manages policies and instances.

    Provides APIs for:
    - Policy management (publish, activate, list, diff)
    - Instance registration and health monitoring
    - Audit log aggregation and querying
    - Deployment tracking
    """

    def __init__(
        self,
        policy_registry: PolicyRegistry | None = None,
        audit_aggregator: AuditAggregator | None = None,
        instance_timeout_seconds: float = 120.0,
    ) -> None:
        """
        Initialize the control plane server.

        Args:
            policy_registry: Registry for policy versions
            audit_aggregator: Aggregator for audit logs
            instance_timeout_seconds: Seconds before an instance is considered offline
        """
        self._registry = policy_registry or InMemoryPolicyRegistry()
        self._aggregator = audit_aggregator or InMemoryAuditAggregator()
        self._instance_timeout = instance_timeout_seconds

        # Instance registry
        self._instances: dict[str, Instance] = {}

        # API keys (hash -> instance_id)
        self._api_keys: dict[str, str] = {}

        # Deployment history
        self._deployments: list[PolicyDeployment] = []

    # Policy Management

    async def publish_policy(
        self,
        policy: Policy,
        name: str,
        published_by: str,
        description: str | None = None,
        tags: list[str] | None = None,
        activate: bool = False,
    ) -> PolicyVersion:
        """
        Publish a new policy version.
        """
        return await self._registry.publish(
            policy=policy,
            name=name,
            published_by=published_by,
            description=description,
            tags=tags,
            activate=activate,
        )

    async def activate_policy(self, version: str) -> PolicyVersion:
        """
        Activate a policy version.
        """
        return await self._registry.activate(version)

    async def deactivate_policy(self, version: str) -> PolicyVersion:
        """
        Deactivate a policy version.
        """
        return await self._registry.deactivate(version)

    async def get_policy(self, version: str) -> PolicyVersion | None:
        """
        Get a specific policy version.
        """
        return await self._registry.get(version)

    async def get_active_policy(self) -> PolicyVersion | None:
        """
        Get the currently active policy version.
        """
        return await self._registry.get_active()

    async def list_policies(
        self,
        name: str | None = None,
        tags: list[str] | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[PolicyVersion]:
        """
        List policy versions with optional filters.
        """
        return await self._registry.list_versions(
            name=name,
            tags=tags,
            limit=limit,
            offset=offset,
        )

    async def delete_policy(self, version: str) -> bool:
        """
        Delete a policy version.
        """
        return await self._registry.delete(version)

    async def diff_policies(
        self,
        from_version: str,
        to_version: str,
    ) -> PolicyDiff | None:
        """
        Get differences between two policy versions.
        """
        return await self._registry.diff(from_version, to_version)

    # Instance Management

    async def register_instance(
        self,
        name: str,
        endpoint: str,
        tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> tuple[Instance, str]:
        """
        Register a new OrmAI instance.

        Returns the instance and its API key.
        """
        instance_id = f"inst-{secrets.token_hex(8)}"
        api_key = f"ormai-{secrets.token_urlsafe(32)}"
        api_key_hash = hashlib.sha256(api_key.encode()).hexdigest()

        instance = Instance(
            id=instance_id,
            name=name,
            endpoint=endpoint,
            tags=tags or [],
            registered_at=datetime.utcnow(),
            metadata=metadata or {},
            api_key_hash=api_key_hash,
        )

        self._instances[instance_id] = instance
        self._api_keys[api_key_hash] = instance_id

        return instance, api_key

    async def unregister_instance(self, instance_id: str) -> bool:
        """
        Unregister an instance.
        """
        if instance_id not in self._instances:
            return False

        instance = self._instances[instance_id]
        if instance.api_key_hash:
            self._api_keys.pop(instance.api_key_hash, None)

        del self._instances[instance_id]
        await self._aggregator.unregister_store(instance_id)
        return True

    async def get_instance(self, instance_id: str) -> Instance | None:
        """
        Get instance by ID.
        """
        return self._instances.get(instance_id)

    async def list_instances(
        self,
        tags: list[str] | None = None,
        status: InstanceStatus | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Instance]:
        """
        List registered instances with optional filters.
        """
        instances = list(self._instances.values())

        # Update status based on heartbeat
        now = datetime.utcnow()
        for inst in instances:
            if inst.health.last_heartbeat:
                elapsed = (now - inst.health.last_heartbeat).total_seconds()
                if elapsed > self._instance_timeout:
                    inst.health.status = InstanceStatus.OFFLINE
                else:
                    inst.health.status = InstanceStatus.ONLINE

        # Filter by tags
        if tags:
            instances = [i for i in instances if any(t in i.tags for t in tags)]

        # Filter by status
        if status:
            instances = [i for i in instances if i.health.status == status]

        # Sort by name
        instances.sort(key=lambda i: i.name)

        return instances[offset : offset + limit]

    async def update_instance_health(
        self,
        instance_id: str,
        health: InstanceHealth,
    ) -> Instance | None:
        """
        Update instance health from heartbeat.
        """
        instance = self._instances.get(instance_id)
        if not instance:
            return None

        # Create updated instance with new health
        updated = Instance(
            id=instance.id,
            name=instance.name,
            endpoint=instance.endpoint,
            tags=instance.tags,
            registered_at=instance.registered_at,
            health=health,
            metadata=instance.metadata,
            api_key_hash=instance.api_key_hash,
            enabled=instance.enabled,
        )

        self._instances[instance_id] = updated
        return updated

    async def authenticate_instance(self, api_key: str) -> Instance | None:
        """
        Authenticate an instance by API key.
        """
        api_key_hash = hashlib.sha256(api_key.encode()).hexdigest()
        instance_id = self._api_keys.get(api_key_hash)
        if instance_id:
            return self._instances.get(instance_id)
        return None

    # Audit Management

    async def ingest_audit_record(
        self,
        instance_id: str,
        record: AuditRecord,
    ) -> None:
        """
        Ingest an audit record from an instance.
        """
        await self._aggregator.ingest(instance_id, record)

    async def query_audit_logs(
        self,
        query: AuditQuery,
    ) -> AuditQueryResult:
        """
        Query audit logs across instances.
        """
        return await self._aggregator.query(query)

    async def get_audit_stats(
        self,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        instance_id: str | None = None,
    ) -> AuditStats:
        """
        Get aggregated audit statistics.
        """
        return await self._aggregator.get_stats(
            start_time=start_time,
            end_time=end_time,
            instance_id=instance_id,
        )

    async def get_recent_audit_logs(
        self,
        limit: int = 50,
        instance_id: str | None = None,
    ) -> list[AuditRecord]:
        """
        Get recent audit logs.
        """
        return await self._aggregator.get_recent(
            limit=limit,
            instance_id=instance_id,
        )

    # Deployment Management

    async def deploy_policy(
        self,
        policy_version: str,
        deployed_by: str,
        target_instances: list[str] | None = None,
        target_tags: list[str] | None = None,
    ) -> PolicyDeployment:
        """
        Deploy a policy version to instances.

        Args:
            policy_version: Version to deploy
            deployed_by: User deploying
            target_instances: Specific instance IDs (empty = all)
            target_tags: Target instances with these tags
        """
        deployment_id = f"deploy-{secrets.token_hex(8)}"

        # Determine target instances
        targets: list[Instance] = []
        if target_instances:
            targets = [
                self._instances[iid]
                for iid in target_instances
                if iid in self._instances
            ]
        elif target_tags:
            targets = [
                inst
                for inst in self._instances.values()
                if any(t in inst.tags for t in target_tags)
            ]
        else:
            targets = list(self._instances.values())

        # Create deployment record
        deployment = PolicyDeployment(
            id=deployment_id,
            policy_version=policy_version,
            target_instances=[i.id for i in targets],
            target_tags=target_tags or [],
            deployed_at=datetime.utcnow(),
            deployed_by=deployed_by,
            instance_status={i.id: "pending" for i in targets},
            success=False,
        )

        self._deployments.append(deployment)

        # In a real implementation, this would push the policy to instances
        # For now, we just mark them as deployed
        deployment.instance_status = {i.id: "deployed" for i in targets}
        deployment.success = True

        return deployment

    async def list_deployments(
        self,
        policy_version: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[PolicyDeployment]:
        """
        List deployment history.
        """
        deployments = self._deployments

        if policy_version:
            deployments = [
                d for d in deployments if d.policy_version == policy_version
            ]

        # Sort by deployed_at descending
        deployments.sort(key=lambda d: d.deployed_at, reverse=True)

        return deployments[offset : offset + limit]

    async def get_deployment(self, deployment_id: str) -> PolicyDeployment | None:
        """
        Get deployment by ID.
        """
        for d in self._deployments:
            if d.id == deployment_id:
                return d
        return None

    # Dashboard/Summary

    async def get_dashboard_summary(self) -> dict[str, Any]:
        """
        Get a summary for dashboard display.
        """
        now = datetime.utcnow()
        hour_ago = now - timedelta(hours=1)

        # Get instance stats
        instances = await self.list_instances()
        online_count = sum(
            1 for i in instances if i.health.status == InstanceStatus.ONLINE
        )

        # Get policy stats
        active_policy = await self.get_active_policy()
        all_policies = await self.list_policies()

        # Get audit stats
        audit_stats = await self.get_audit_stats(start_time=hour_ago)

        return {
            "instances": {
                "total": len(instances),
                "online": online_count,
                "offline": len(instances) - online_count,
            },
            "policies": {
                "total": len(all_policies),
                "active_version": active_policy.version if active_policy else None,
            },
            "audit": {
                "calls_last_hour": audit_stats.total_calls,
                "errors_last_hour": audit_stats.total_errors,
                "error_rate": (
                    audit_stats.total_errors / audit_stats.total_calls
                    if audit_stats.total_calls > 0
                    else 0.0
                ),
                "avg_latency_ms": audit_stats.avg_latency_ms,
            },
            "deployments": {
                "recent": len([d for d in self._deployments[-10:] if d.success]),
                "failed": len([d for d in self._deployments[-10:] if not d.success]),
            },
        }


def create_server(
    policy_registry: PolicyRegistry | None = None,
    audit_aggregator: AuditAggregator | None = None,
) -> ControlPlaneServer:
    """
    Create a control plane server with default components.
    """
    return ControlPlaneServer(
        policy_registry=policy_registry,
        audit_aggregator=audit_aggregator,
    )
