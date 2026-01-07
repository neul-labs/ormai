"""
OrmAI Control Plane.

Provides centralized policy distribution and audit log aggregation
for managing multiple OrmAI instances.
"""

from ormai.control_plane.aggregator import (
    AuditAggregator,
    FederatedAuditAggregator,
    InMemoryAuditAggregator,
)
from ormai.control_plane.client import (
    ControlPlaneClient,
    LocalControlPlaneClient,
    create_client,
)
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
from ormai.control_plane.registry import (
    InMemoryPolicyRegistry,
    JsonFilePolicyRegistry,
    PolicyRegistry,
)
from ormai.control_plane.server import ControlPlaneServer, create_server

__all__ = [
    # Models
    "PolicyVersion",
    "PolicyDeployment",
    "PolicyDiff",
    "Instance",
    "InstanceStatus",
    "InstanceHealth",
    "AuditQuery",
    "AuditQueryResult",
    "AuditStats",
    # Registry
    "PolicyRegistry",
    "InMemoryPolicyRegistry",
    "JsonFilePolicyRegistry",
    # Aggregator
    "AuditAggregator",
    "InMemoryAuditAggregator",
    "FederatedAuditAggregator",
    # Client
    "ControlPlaneClient",
    "LocalControlPlaneClient",
    "create_client",
    # Server
    "ControlPlaneServer",
    "create_server",
]
