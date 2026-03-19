"""
OrmAI Core Module.

Contains the runtime context, DSL schemas, error taxonomy, and shared types.
"""

from ormai.core.context import Principal, RunContext
from ormai.core.cursor import (
    CursorData,
    CursorEncoder,
    CursorType,
    build_keyset_condition,
    default_encoder,
)
from ormai.core.dsl import (
    AggregateRequest,
    FilterClause,
    FilterOp,
    GetRequest,
    IncludeClause,
    OrderClause,
    OrderDirection,
    QueryRequest,
)
from ormai.core.errors import (
    FieldNotAllowedError,
    MaxAffectedRowsExceededError,
    ModelNotAllowedError,
    OrmAccessDeniedError,
    OrmAIError,
    QueryBudgetExceededError,
    QueryTooBroadError,
    RelationNotAllowedError,
    TenantScopeRequiredError,
    ValidationError,
    WriteApprovalRequiredError,
    WriteDisabledError,
)
from ormai.core.types import (
    AggregateOp,
    FieldMetadata,
    FieldType,
    ModelMetadata,
    RelationMetadata,
    SchemaMetadata,
)

__all__ = [
    # Context
    "Principal",
    "RunContext",
    # Cursor
    "CursorEncoder",
    "CursorData",
    "CursorType",
    "build_keyset_condition",
    "default_encoder",
    # DSL
    "QueryRequest",
    "GetRequest",
    "AggregateRequest",
    "FilterClause",
    "FilterOp",
    "OrderClause",
    "OrderDirection",
    "IncludeClause",
    # Errors
    "OrmAIError",
    "OrmAccessDeniedError",
    "ModelNotAllowedError",
    "FieldNotAllowedError",
    "RelationNotAllowedError",
    "TenantScopeRequiredError",
    "QueryTooBroadError",
    "QueryBudgetExceededError",
    "WriteDisabledError",
    "WriteApprovalRequiredError",
    "MaxAffectedRowsExceededError",
    "ValidationError",
    # Types
    "AggregateOp",
    "FieldType",
    "ModelMetadata",
    "FieldMetadata",
    "RelationMetadata",
    "SchemaMetadata",
]
