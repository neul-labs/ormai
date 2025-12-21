"""
Default profiles for OrmAI configuration.
"""

from dataclasses import dataclass
from typing import Literal

from ormai.policy.models import Budget, RowPolicy


@dataclass(frozen=True)
class DefaultsProfile:
    """
    Configuration profile with sensible defaults.

    Profiles control budget limits, security requirements, and feature toggles.
    """

    mode: Literal["prod", "internal", "dev"]

    # Budget limits
    max_rows: int = 100
    max_includes_depth: int = 1
    max_select_fields: int = 40
    statement_timeout_ms: int = 2000

    # Security
    require_tenant_scope: bool = True
    require_reason_for_writes: bool = True

    # Features
    writes_enabled: bool = False
    soft_delete: bool = True

    # Redaction
    redact_strategy: Literal["deny", "mask"] = "deny"

    # Generic tools
    allow_generic_query: bool = True
    allow_generic_mutations: bool = False

    # Complexity
    max_complexity_score: int = 100
    broad_query_guard: bool = True

    def to_budget(self) -> Budget:
        """Convert profile to Budget model."""
        return Budget(
            max_rows=self.max_rows,
            max_includes_depth=self.max_includes_depth,
            max_select_fields=self.max_select_fields,
            statement_timeout_ms=self.statement_timeout_ms,
            max_complexity_score=self.max_complexity_score,
            broad_query_guard=self.broad_query_guard,
        )

    def to_row_policy(self, tenant_field: str | None = None) -> RowPolicy:
        """Convert profile to RowPolicy model."""
        return RowPolicy(
            tenant_scope_field=tenant_field,
            require_scope=self.require_tenant_scope,
        )


# Built-in profiles

DEFAULT_PROD = DefaultsProfile(
    mode="prod",
    max_rows=100,
    max_includes_depth=1,
    max_select_fields=40,
    statement_timeout_ms=2000,
    require_tenant_scope=True,
    require_reason_for_writes=True,
    writes_enabled=False,
    soft_delete=True,
    redact_strategy="deny",
    allow_generic_query=True,
    allow_generic_mutations=False,
    max_complexity_score=100,
    broad_query_guard=True,
)

DEFAULT_INTERNAL = DefaultsProfile(
    mode="internal",
    max_rows=500,
    max_includes_depth=2,
    max_select_fields=80,
    statement_timeout_ms=5000,
    require_tenant_scope=True,
    require_reason_for_writes=True,
    writes_enabled=False,
    soft_delete=True,
    redact_strategy="mask",
    allow_generic_query=True,
    allow_generic_mutations=False,
    max_complexity_score=200,
    broad_query_guard=True,
)

DEFAULT_DEV = DefaultsProfile(
    mode="dev",
    max_rows=1000,
    max_includes_depth=3,
    max_select_fields=100,
    statement_timeout_ms=10000,
    require_tenant_scope=False,
    require_reason_for_writes=False,
    writes_enabled=True,
    soft_delete=True,
    redact_strategy="mask",
    allow_generic_query=True,
    allow_generic_mutations=True,
    max_complexity_score=500,
    broad_query_guard=False,
)
