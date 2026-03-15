"""
Policy model definitions.

Policies control what data can be accessed, how it's filtered, and what operations
are allowed. They are evaluated at validation time, compile time (for query injection),
and post-execution (for redaction).
"""

from collections.abc import Callable
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class FieldAction(str, Enum):
    """Action to take for a field."""

    ALLOW = "allow"  # Field is visible
    DENY = "deny"  # Field is completely hidden
    MASK = "mask"  # Field is partially masked (e.g., "****1234")
    HASH = "hash"  # Field is hashed


class FieldPolicy(BaseModel):
    """
    Policy for a single field.

    Controls visibility and transformation of field values.
    """

    action: FieldAction = Field(default=FieldAction.ALLOW)
    mask_pattern: str | None = Field(
        default=None,
        description="Pattern for masking (e.g., '****{last4}' for credit cards)",
    )
    # Callable for custom redaction - takes value, returns redacted value
    # Note: This can't be serialized, so it's excluded from serialization
    custom_redactor: Callable[[Any], Any] | None = Field(default=None, exclude=True)

    model_config = {"frozen": True}


class RelationPolicy(BaseModel):
    """
    Policy for a relation/include.

    Controls which relations can be expanded and with what constraints.
    """

    allowed: bool = Field(default=True)
    max_depth: int = Field(default=1, ge=0, le=5)
    allowed_fields: list[str] | None = Field(
        default=None, description="If set, only these fields can be selected from the relation"
    )

    model_config = {"frozen": True}


class RowPolicy(BaseModel):
    """
    Row-level security policy.

    Defines how rows are filtered based on the execution context.
    """

    # Field used for tenant scoping (e.g., "tenant_id")
    tenant_scope_field: str | None = Field(default=None)

    # Field used for ownership scoping (e.g., "user_id", "owner_id")
    ownership_scope_field: str | None = Field(default=None)

    # Whether scoping is required (if True, queries without scope will fail)
    require_scope: bool = Field(default=True)

    # Soft delete field (e.g., "deleted_at", "is_deleted")
    soft_delete_field: str | None = Field(default=None)

    # Whether to include soft-deleted records
    include_soft_deleted: bool = Field(default=False)

    model_config = {"frozen": True}


class WritePolicy(BaseModel):
    """
    Policy for write operations.
    """

    # Whether writes are enabled at all
    enabled: bool = Field(default=False)

    # Whether create operations are allowed
    allow_create: bool = Field(default=False)

    # Whether update operations are allowed
    allow_update: bool = Field(default=False)

    # Whether delete operations are allowed
    allow_delete: bool = Field(default=False)

    # Whether bulk operations are allowed
    allow_bulk: bool = Field(default=False)

    # Whether updates require primary key
    require_primary_key: bool = Field(default=True)

    # Whether soft delete is the default delete behavior
    soft_delete: bool = Field(default=True)

    # Maximum rows that can be affected by a single operation
    max_affected_rows: int = Field(default=1, ge=1, le=1000)

    # Whether a reason is required for writes
    require_reason: bool = Field(default=True)

    # Whether human approval is required
    require_approval: bool = Field(default=False)

    # Fields that cannot be written to
    readonly_fields: list[str] = Field(default_factory=list)

    model_config = {"frozen": True}


class Budget(BaseModel):
    """
    Resource budget for queries.

    Limits query complexity to prevent runaway operations.
    """

    # Maximum rows to return
    max_rows: int = Field(default=100, ge=1, le=10000)

    # Maximum depth for relation includes
    max_includes_depth: int = Field(default=1, ge=0, le=5)

    # Maximum number of fields that can be selected
    max_select_fields: int = Field(default=40, ge=1, le=200)

    # Query timeout in milliseconds
    statement_timeout_ms: int = Field(default=2000, ge=100, le=30000)

    # Maximum complexity score (if scoring is enabled)
    max_complexity_score: int = Field(default=100, ge=1)

    # Whether to enable broad query guard (block unfiltered queries on large tables)
    broad_query_guard: bool = Field(default=True)

    # Minimum filters required to bypass broad query guard
    min_filters_for_broad_query: int = Field(default=1, ge=0)

    model_config = {"frozen": True}


class ModelPolicy(BaseModel):
    """
    Complete policy for a single model.
    """

    # Whether the model is accessible at all
    allowed: bool = Field(default=True)

    # Whether read operations are allowed
    readable: bool = Field(default=True)

    # Whether write operations are allowed
    writable: bool = Field(default=False)

    # Field-level policies (field name -> policy)
    fields: dict[str, FieldPolicy] = Field(default_factory=dict)

    # Default field action for fields not in the fields dict
    default_field_action: FieldAction = Field(default=FieldAction.ALLOW)

    # Relation policies (relation name -> policy)
    relations: dict[str, RelationPolicy] = Field(default_factory=dict)

    # Row-level security policy
    row_policy: RowPolicy | None = Field(default=None)

    # Write policy
    write_policy: WritePolicy = Field(default_factory=WritePolicy)

    # Budget overrides for this model
    budget: Budget | None = Field(default=None)

    # Allowed operations for aggregations
    allowed_aggregations: list[str] = Field(
        default_factory=lambda: ["count", "sum", "avg", "min", "max"]
    )

    # Fields that can be aggregated
    aggregatable_fields: list[str] | None = Field(
        default=None, description="If set, only these fields can be aggregated"
    )

    model_config = {"frozen": True}

    def get_field_policy(self, field: str) -> FieldPolicy:
        """Get policy for a specific field, falling back to default."""
        if field in self.fields:
            return self.fields[field]
        return FieldPolicy(action=self.default_field_action)

    def is_field_allowed(self, field: str) -> bool:
        """Check if a field is allowed (not denied)."""
        policy = self.get_field_policy(field)
        return policy.action != FieldAction.DENY

    def get_allowed_fields(self, all_fields: list[str]) -> list[str]:
        """Get list of allowed fields from a list of all fields."""
        return [f for f in all_fields if self.is_field_allowed(f)]


class Policy(BaseModel):
    """
    Complete policy configuration.

    The root policy object that contains all model policies and defaults.
    """

    # Model-specific policies
    models: dict[str, ModelPolicy] = Field(default_factory=dict)

    # Default budget applied to all models unless overridden
    default_budget: Budget = Field(default_factory=Budget)

    # Default row policy applied to all models unless overridden
    default_row_policy: RowPolicy = Field(default_factory=RowPolicy)

    # Global field patterns to deny (e.g., "*password*", "*secret*")
    global_deny_patterns: list[str] = Field(default_factory=list)

    # Global field patterns to mask (e.g., "email", "phone")
    global_mask_patterns: list[str] = Field(default_factory=list)

    # Whether to require tenant scope by default
    require_tenant_scope: bool = Field(default=True)

    # Whether writes are enabled globally
    writes_enabled: bool = Field(default=False)

    model_config = {"frozen": True}

    def get_model_policy(self, model: str) -> ModelPolicy | None:
        """Get policy for a specific model."""
        return self.models.get(model)

    def get_budget(self, model: str) -> Budget:
        """Get budget for a model, falling back to default."""
        model_policy = self.models.get(model)
        if model_policy and model_policy.budget:
            return model_policy.budget
        return self.default_budget

    def get_row_policy(self, model: str) -> RowPolicy:
        """Get row policy for a model, falling back to default."""
        model_policy = self.models.get(model)
        if model_policy and model_policy.row_policy:
            return model_policy.row_policy
        return self.default_row_policy

    def is_model_allowed(self, model: str) -> bool:
        """Check if a model is allowed."""
        policy = self.models.get(model)
        return policy is not None and policy.allowed

    def list_allowed_models(self) -> list[str]:
        """List all allowed model names."""
        return [name for name, policy in self.models.items() if policy.allowed]
