"""
Control Plane Client SDK.

Allows OrmAI instances to connect to a control plane for:
- Policy synchronization
- Audit log forwarding
- Health reporting
"""

import asyncio
import hashlib
import time
from collections.abc import Awaitable, Callable
from datetime import datetime
from typing import Any

from ormai.control_plane.models import (
    Instance,
    InstanceHealth,
    InstanceStatus,
    PolicyVersion,
)
from ormai.policy.models import Policy
from ormai.store.base import AuditStore
from ormai.store.models import AuditRecord


class ControlPlaneClient:
    """
    Client for connecting an OrmAI instance to a control plane.

    Handles:
    - Policy synchronization (pull latest policy from control plane)
    - Audit log forwarding (push audit records to control plane)
    - Health heartbeats (report instance health to control plane)
    """

    def __init__(
        self,
        instance_id: str,
        instance_name: str,
        control_plane_url: str | None = None,
        api_key: str | None = None,
        tags: list[str] | None = None,
        sync_interval_seconds: float = 60.0,
        heartbeat_interval_seconds: float = 30.0,
        audit_batch_size: int = 100,
        audit_flush_interval_seconds: float = 5.0,
    ) -> None:
        """
        Initialize the control plane client.

        Args:
            instance_id: Unique identifier for this instance
            instance_name: Human-readable name
            control_plane_url: URL of the control plane server (None for local mode)
            api_key: API key for authentication
            tags: Tags for this instance (e.g., ["production", "us-west-2"])
            sync_interval_seconds: How often to check for policy updates
            heartbeat_interval_seconds: How often to send health heartbeats
            audit_batch_size: Batch size for audit log forwarding
            audit_flush_interval_seconds: How often to flush audit batches
        """
        self.instance_id = instance_id
        self.instance_name = instance_name
        self.control_plane_url = control_plane_url
        self.api_key = api_key
        self.tags = tags or []

        self._sync_interval = sync_interval_seconds
        self._heartbeat_interval = heartbeat_interval_seconds
        self._audit_batch_size = audit_batch_size
        self._audit_flush_interval = audit_flush_interval_seconds

        # Current state
        self._current_policy: Policy | None = None
        self._current_policy_version: str | None = None
        self._policy_hash: str | None = None

        # Audit buffer
        self._audit_buffer: list[AuditRecord] = []
        self._last_audit_flush = time.time()

        # Metrics for health reporting
        self._call_count = 0
        self._error_count = 0
        self._total_latency_ms = 0.0
        self._metrics_reset_time = time.time()

        # Callbacks
        self._on_policy_update: Callable[[Policy, str], Awaitable[None]] | None = None
        self._local_audit_store: AuditStore | None = None

        # Background tasks
        self._sync_task: asyncio.Task | None = None
        self._heartbeat_task: asyncio.Task | None = None
        self._audit_task: asyncio.Task | None = None
        self._running = False

    @property
    def current_policy(self) -> Policy | None:
        """Get the current active policy."""
        return self._current_policy

    @property
    def current_policy_version(self) -> str | None:
        """Get the current policy version."""
        return self._current_policy_version

    def set_policy_update_callback(
        self,
        callback: Callable[[Policy, str], Awaitable[None]],
    ) -> None:
        """
        Set callback for policy updates.

        Called when a new policy version is received from the control plane.
        """
        self._on_policy_update = callback

    def set_local_audit_store(self, store: AuditStore) -> None:
        """
        Set a local audit store for offline operation.

        Records will be stored locally if control plane is unreachable.
        """
        self._local_audit_store = store

    async def start(self) -> None:
        """
        Start the control plane client.

        Begins background tasks for:
        - Policy synchronization
        - Health heartbeats
        - Audit log forwarding
        """
        if self._running:
            return

        self._running = True

        # Initial policy sync
        await self._sync_policy()

        # Start background tasks
        self._sync_task = asyncio.create_task(self._sync_loop())
        self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())
        self._audit_task = asyncio.create_task(self._audit_loop())

    async def stop(self) -> None:
        """
        Stop the control plane client.

        Flushes pending audit records and cancels background tasks.
        """
        self._running = False

        # Flush remaining audit records
        await self._flush_audit_buffer()

        # Cancel background tasks
        if self._sync_task:
            self._sync_task.cancel()
            try:
                await self._sync_task
            except asyncio.CancelledError:
                pass

        if self._heartbeat_task:
            self._heartbeat_task.cancel()
            try:
                await self._heartbeat_task
            except asyncio.CancelledError:
                pass

        if self._audit_task:
            self._audit_task.cancel()
            try:
                await self._audit_task
            except asyncio.CancelledError:
                pass

    async def record_tool_call(
        self,
        record: AuditRecord,
    ) -> None:
        """
        Record a tool call for audit logging.

        Records are batched and sent to the control plane periodically.
        """
        self._audit_buffer.append(record)

        # Update metrics
        self._call_count += 1
        if record.error:
            self._error_count += 1
        if record.duration_ms:
            self._total_latency_ms += record.duration_ms

        # Flush if batch is full
        if len(self._audit_buffer) >= self._audit_batch_size:
            await self._flush_audit_buffer()

    async def force_sync(self) -> bool:
        """
        Force an immediate policy synchronization.

        Returns True if a new policy was received.
        """
        return await self._sync_policy()

    def get_health(self) -> InstanceHealth:
        """
        Get current instance health metrics.
        """
        now = time.time()
        elapsed = now - self._metrics_reset_time

        error_rate = (
            self._error_count / self._call_count
            if self._call_count > 0
            else 0.0
        )
        avg_latency = (
            self._total_latency_ms / self._call_count
            if self._call_count > 0
            else 0.0
        )

        return InstanceHealth(
            status=InstanceStatus.ONLINE if self._running else InstanceStatus.OFFLINE,
            last_heartbeat=datetime.utcnow(),
            current_policy_version=self._current_policy_version,
            error_rate=error_rate,
            avg_latency_ms=avg_latency,
            tool_calls_count=self._call_count,
            metrics={
                "elapsed_seconds": elapsed,
                "buffer_size": len(self._audit_buffer),
            },
        )

    def reset_metrics(self) -> None:
        """Reset health metrics."""
        self._call_count = 0
        self._error_count = 0
        self._total_latency_ms = 0.0
        self._metrics_reset_time = time.time()

    # Internal methods

    async def _sync_loop(self) -> None:
        """Background task for periodic policy synchronization."""
        while self._running:
            try:
                await asyncio.sleep(self._sync_interval)
                await self._sync_policy()
            except asyncio.CancelledError:
                break
            except Exception:
                # Log error but continue
                pass

    async def _heartbeat_loop(self) -> None:
        """Background task for periodic health heartbeats."""
        while self._running:
            try:
                await asyncio.sleep(self._heartbeat_interval)
                await self._send_heartbeat()
            except asyncio.CancelledError:
                break
            except Exception:
                # Log error but continue
                pass

    async def _audit_loop(self) -> None:
        """Background task for periodic audit log flushing."""
        while self._running:
            try:
                await asyncio.sleep(self._audit_flush_interval)
                if self._audit_buffer:
                    await self._flush_audit_buffer()
            except asyncio.CancelledError:
                break
            except Exception:
                # Log error but continue
                pass

    async def _sync_policy(self) -> bool:
        """
        Sync policy from control plane.

        Returns True if a new policy was received.
        """
        if not self.control_plane_url:
            # Local mode - no sync needed
            return False

        # In a real implementation, this would make an HTTP request
        # to the control plane API. For now, we just return False.
        # This is a placeholder for the actual implementation.
        return False

    async def _send_heartbeat(self) -> None:
        """Send health heartbeat to control plane."""
        if not self.control_plane_url:
            return

        # In a real implementation, this would make an HTTP request
        # to the control plane API. For now, this is a placeholder.
        pass

    async def _flush_audit_buffer(self) -> None:
        """Flush audit buffer to control plane or local store."""
        if not self._audit_buffer:
            return

        records = self._audit_buffer
        self._audit_buffer = []

        # Try to send to control plane
        if self.control_plane_url:
            try:
                await self._send_audit_records(records)
                return
            except Exception:
                # Fall back to local store
                pass

        # Store locally if available
        if self._local_audit_store:
            for record in records:
                await self._local_audit_store.store(record)

    async def _send_audit_records(self, records: list[AuditRecord]) -> None:
        """Send audit records to control plane."""
        # In a real implementation, this would make an HTTP request
        # to the control plane API. For now, this is a placeholder.
        pass


class LocalControlPlaneClient(ControlPlaneClient):
    """
    Local-only control plane client for standalone operation.

    Provides the same interface as ControlPlaneClient but operates
    entirely locally without network communication.
    """

    def __init__(
        self,
        instance_id: str,
        instance_name: str,
        initial_policy: Policy | None = None,
        audit_store: AuditStore | None = None,
        tags: list[str] | None = None,
    ) -> None:
        super().__init__(
            instance_id=instance_id,
            instance_name=instance_name,
            control_plane_url=None,
            tags=tags,
        )

        if initial_policy:
            self._current_policy = initial_policy
            self._current_policy_version = "local-v1"
            self._policy_hash = self._compute_policy_hash(initial_policy)

        if audit_store:
            self._local_audit_store = audit_store

    def set_policy(self, policy: Policy, version: str | None = None) -> None:
        """
        Set the current policy directly.

        For local operation without a control plane.
        """
        self._current_policy = policy
        self._current_policy_version = version or f"local-{int(time.time())}"
        self._policy_hash = self._compute_policy_hash(policy)

    def _compute_policy_hash(self, policy: Policy) -> str:
        """Compute hash of policy for change detection."""
        policy_json = policy.model_dump_json(exclude_none=True)
        return hashlib.sha256(policy_json.encode()).hexdigest()[:16]

    async def start(self) -> None:
        """Start the client (minimal for local operation)."""
        self._running = True
        # Start audit flush task only
        self._audit_task = asyncio.create_task(self._audit_loop())

    async def _sync_policy(self) -> bool:
        """No sync needed for local operation."""
        return False

    async def _send_heartbeat(self) -> None:
        """No heartbeat needed for local operation."""
        pass

    async def _send_audit_records(self, records: list[AuditRecord]) -> None:
        """Store records locally."""
        if self._local_audit_store:
            for record in records:
                await self._local_audit_store.store(record)


def create_client(
    instance_id: str,
    instance_name: str,
    control_plane_url: str | None = None,
    api_key: str | None = None,
    initial_policy: Policy | None = None,
    audit_store: AuditStore | None = None,
    tags: list[str] | None = None,
) -> ControlPlaneClient:
    """
    Create a control plane client.

    If control_plane_url is provided, creates a remote client.
    Otherwise, creates a local client for standalone operation.
    """
    if control_plane_url:
        client = ControlPlaneClient(
            instance_id=instance_id,
            instance_name=instance_name,
            control_plane_url=control_plane_url,
            api_key=api_key,
            tags=tags,
        )
        if audit_store:
            client.set_local_audit_store(audit_store)
        return client
    else:
        return LocalControlPlaneClient(
            instance_id=instance_id,
            instance_name=instance_name,
            initial_policy=initial_policy,
            audit_store=audit_store,
            tags=tags,
        )
