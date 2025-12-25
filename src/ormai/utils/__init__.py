"""
OrmAI Utilities Pack.

Provides defaults, builders, and helpers for quick integration.
"""

from ormai.utils.approval import (
    ApprovalDecision,
    ApprovalGate,
    ApprovalRequest,
    ApprovalStatus,
    AutoApproveGate,
    CallbackApprovalGate,
    InMemoryApprovalQueue,
)
from ormai.utils.builder import PolicyBuilder
from ormai.utils.cache import PersistentSchemaCache, SchemaCache, compute_migration_hash
from ormai.utils.defaults import DEFAULT_DEV, DEFAULT_INTERNAL, DEFAULT_PROD, DefaultsProfile
from ormai.utils.factory import ToolsetFactory
from ormai.utils.plugins import (
    ErrorContext,
    ErrorPlugin,
    LocalizedErrorPlugin,
    LoggingPlugin,
    MetricsPlugin,
    PluginChain,
    TerseErrorPlugin,
    TransformedError,
    VerboseErrorPlugin,
)
from ormai.utils.transaction import (
    RETRY_FAST,
    RETRY_NONE,
    RETRY_PERSISTENT,
    RETRY_STANDARD,
    RetryConfig,
    RetryStrategy,
    TransactionManager,
    retry_async,
    retry_sync,
    with_retry,
    with_retry_sync,
)

__all__ = [
    # Defaults
    "DefaultsProfile",
    "DEFAULT_PROD",
    "DEFAULT_INTERNAL",
    "DEFAULT_DEV",
    # Builder
    "PolicyBuilder",
    # Factory
    "ToolsetFactory",
    # Cache
    "SchemaCache",
    "PersistentSchemaCache",
    "compute_migration_hash",
    # Plugins
    "ErrorPlugin",
    "ErrorContext",
    "TransformedError",
    "PluginChain",
    "LocalizedErrorPlugin",
    "VerboseErrorPlugin",
    "TerseErrorPlugin",
    "MetricsPlugin",
    "LoggingPlugin",
    # Approval
    "ApprovalGate",
    "ApprovalRequest",
    "ApprovalDecision",
    "ApprovalStatus",
    "AutoApproveGate",
    "CallbackApprovalGate",
    "InMemoryApprovalQueue",
    # Transaction / Retry
    "RetryConfig",
    "RetryStrategy",
    "RETRY_NONE",
    "RETRY_FAST",
    "RETRY_STANDARD",
    "RETRY_PERSISTENT",
    "retry_async",
    "retry_sync",
    "with_retry",
    "with_retry_sync",
    "TransactionManager",
]
