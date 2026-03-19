"""
Control plane data models.

Defines the core data structures for policy versioning, instance management,
and audit aggregation.
"""

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from ormai.policy.models import Policy
from ormai.store.models import AuditRecord


class PolicyVersion(BaseModel):
    """
    A versioned policy with metadata.

    Policies are immutable once published - new versions create new records.
    """

    # Unique version identifier (e.g., "v1", "v2", "2024-01-15-001")
    version: str

    # Human-readable name for this policy
    name: str

    # The policy configuration
    policy: Policy

    # Publication timestamp
    published_at: datetime

    # User who published this version
    published_by: str

    # Optional description of changes
    description: str | None = None

    # Tags for organization (e.g., ["production", "support-team"])
    tags: list[str] = Field(default_factory=list)

    # Whether this is the active/default version
    is_active: bool = False

    # Hash of the policy for change detection
    policy_hash: str | None = None

    # Optional parent version for tracking lineage
    parent_version: str | None = None

    model_config = {"frozen": True}


class PolicyDeployment(BaseModel):
    """
    Record of a policy deployment to instances.
    """

    # Deployment identifier
    id: str

    # Policy version being deployed
    policy_version: str

    # Target instances (empty = all instances)
    target_instances: list[str] = Field(default_factory=list)

    # Target tags (instances matching these tags)
    target_tags: list[str] = Field(default_factory=list)

    # Deployment timing
    deployed_at: datetime
    deployed_by: str

    # Deployment status per instance
    instance_status: dict[str, str] = Field(default_factory=dict)

    # Whether deployment was successful
    success: bool = False

    # Error message if deployment failed
    error_message: str | None = None


class InstanceStatus(str, Enum):
    """Status of an OrmAI instance."""

    ONLINE = "online"
    OFFLINE = "offline"
    DEGRADED = "degraded"
    UNKNOWN = "unknown"


class InstanceHealth(BaseModel):
    """Health information for an instance."""

    # Current status
    status: InstanceStatus = InstanceStatus.UNKNOWN

    # Last heartbeat timestamp
    last_heartbeat: datetime | None = None

    # Current policy version
    current_policy_version: str | None = None

    # Error rate (last hour)
    error_rate: float = 0.0

    # Average latency (last hour) in ms
    avg_latency_ms: float = 0.0

    # Total tool calls (last hour)
    tool_calls_count: int = 0

    # Memory usage percentage
    memory_percent: float | None = None

    # Additional health metrics
    metrics: dict[str, Any] = Field(default_factory=dict)


class Instance(BaseModel):
    """
    An OrmAI instance registered with the control plane.
    """

    # Unique instance identifier
    id: str

    # Human-readable name
    name: str

    # Instance URL/endpoint
    endpoint: str

    # Tags for grouping (e.g., ["production", "us-west-2"])
    tags: list[str] = Field(default_factory=list)

    # Registration timestamp
    registered_at: datetime

    # Current health
    health: InstanceHealth = Field(default_factory=InstanceHealth)

    # Instance metadata
    metadata: dict[str, Any] = Field(default_factory=dict)

    # API key for this instance (hashed)
    api_key_hash: str | None = None

    # Whether instance is enabled
    enabled: bool = True


class AuditQuery(BaseModel):
    """
    Query parameters for audit log aggregation.
    """

    # Filter by tenant
    tenant_id: str | None = None

    # Filter by principal
    principal_id: str | None = None

    # Filter by tool
    tool_name: str | None = None

    # Filter by instance
    instance_id: str | None = None

    # Filter by instance tags
    instance_tags: list[str] | None = None

    # Time range
    start_time: datetime | None = None
    end_time: datetime | None = None

    # Only show errors
    errors_only: bool = False

    # Filter by model (for db.* tools)
    model: str | None = None

    # Pagination
    limit: int = Field(default=100, ge=1, le=1000)
    offset: int = Field(default=0, ge=0)

    # Sort order
    sort_by: str = "timestamp"
    sort_desc: bool = True


class AuditQueryResult(BaseModel):
    """
    Result of an audit query across instances.
    """

    # Matching records
    records: list[AuditRecord]

    # Total count (for pagination)
    total_count: int

    # Query parameters used
    query: AuditQuery

    # Instances queried
    instances_queried: list[str]

    # Any errors during aggregation
    errors: dict[str, str] = Field(default_factory=dict)


class AuditStats(BaseModel):
    """
    Aggregated audit statistics.
    """

    # Time window
    start_time: datetime
    end_time: datetime

    # Total calls
    total_calls: int = 0

    # Calls by tool
    calls_by_tool: dict[str, int] = Field(default_factory=dict)

    # Calls by model
    calls_by_model: dict[str, int] = Field(default_factory=dict)

    # Calls by instance
    calls_by_instance: dict[str, int] = Field(default_factory=dict)

    # Error counts
    total_errors: int = 0
    errors_by_type: dict[str, int] = Field(default_factory=dict)

    # Latency stats
    avg_latency_ms: float = 0.0
    p50_latency_ms: float = 0.0
    p95_latency_ms: float = 0.0
    p99_latency_ms: float = 0.0

    # Row counts
    total_rows_returned: int = 0
    avg_rows_per_query: float = 0.0


class PolicyDiff(BaseModel):
    """
    Differences between two policy versions.
    """

    from_version: str
    to_version: str

    # Added models
    added_models: list[str] = Field(default_factory=list)

    # Removed models
    removed_models: list[str] = Field(default_factory=list)

    # Modified models with changes
    modified_models: dict[str, dict[str, Any]] = Field(default_factory=dict)

    # Budget changes
    budget_changes: dict[str, Any] = Field(default_factory=dict)

    # Global policy changes
    global_changes: dict[str, Any] = Field(default_factory=dict)

    # Summary of changes
    summary: str = ""
