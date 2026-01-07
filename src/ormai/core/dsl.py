"""
Query DSL schemas for OrmAI.

These Pydantic models define the structured query language that agents use
to interact with the database. The DSL is designed to be safe, expressive,
and easily validated.
"""

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, field_validator


class FilterOp(str, Enum):
    """Supported filter operators."""

    EQ = "eq"
    NE = "ne"
    LT = "lt"
    LTE = "lte"
    GT = "gt"
    GTE = "gte"
    IN = "in"
    NOT_IN = "not_in"
    IS_NULL = "is_null"
    CONTAINS = "contains"
    STARTSWITH = "startswith"
    ENDSWITH = "endswith"
    BETWEEN = "between"


class OrderDirection(str, Enum):
    """Sort order direction."""

    ASC = "asc"
    DESC = "desc"


class FilterClause(BaseModel):
    """
    A single filter condition.

    Examples:
        {"field": "status", "op": "eq", "value": "active"}
        {"field": "created_at", "op": "gte", "value": "2024-01-01"}
        {"field": "id", "op": "in", "value": [1, 2, 3]}
    """

    field: str = Field(..., description="The field name to filter on")
    op: FilterOp = Field(..., description="The filter operator")
    value: Any = Field(..., description="The value to compare against")

    model_config = {"frozen": True}

    @field_validator("field")
    @classmethod
    def validate_field_name(cls, v: str) -> str:
        """Ensure field name is not empty and doesn't contain SQL injection attempts."""
        if not v or not v.strip():
            raise ValueError("Field name cannot be empty")
        # Basic protection against SQL injection in field names
        if any(char in v for char in [";", "--", "/*", "*/", "'", '"']):
            raise ValueError("Invalid characters in field name")
        return v.strip()


class OrderClause(BaseModel):
    """
    A single order/sort clause.

    Example:
        {"field": "created_at", "direction": "desc"}
    """

    field: str = Field(..., description="The field name to order by")
    direction: OrderDirection = Field(
        default=OrderDirection.ASC, description="Sort direction"
    )

    model_config = {"frozen": True}


class IncludeClause(BaseModel):
    """
    Specifies a relation to include in the query results.

    Example:
        {"relation": "orders", "select": ["id", "total", "status"]}
    """

    relation: str = Field(..., description="The relation name to include")
    select: list[str] | None = Field(
        default=None, description="Fields to select from the relation"
    )
    where: list[FilterClause] | None = Field(
        default=None, description="Filters to apply to the relation"
    )
    take: int | None = Field(
        default=None, ge=1, description="Max items to include from relation (limited by budget)"
    )

    model_config = {"frozen": True}


class QueryRequest(BaseModel):
    """
    A structured query request.

    This is the primary DSL for querying data through OrmAI. It supports:
    - Field selection
    - Filtering with various operators
    - Ordering
    - Cursor-based pagination
    - Relation includes

    Example:
        {
            "model": "Order",
            "select": ["id", "total", "status", "created_at"],
            "where": [
                {"field": "status", "op": "eq", "value": "pending"},
                {"field": "created_at", "op": "gte", "value": "2024-01-01"}
            ],
            "order_by": [{"field": "created_at", "direction": "desc"}],
            "take": 25,
            "include": [{"relation": "customer", "select": ["id", "name"]}]
        }
    """

    model: str = Field(..., description="The model/table name to query")
    select: list[str] | None = Field(
        default=None, description="Fields to select (None means all allowed fields)"
    )
    where: list[FilterClause] | None = Field(
        default=None, description="Filter conditions (AND-ed together)"
    )
    order_by: list[OrderClause] | None = Field(
        default=None, description="Sort order"
    )
    take: int = Field(
        default=25, ge=1, description="Maximum number of rows to return (limited by budget)"
    )
    cursor: str | None = Field(
        default=None, description="Pagination cursor from previous response"
    )
    include: list[IncludeClause] | None = Field(
        default=None, description="Relations to include"
    )

    model_config = {"frozen": True}


class GetRequest(BaseModel):
    """
    A request to get a single record by primary key.

    Example:
        {
            "model": "Order",
            "id": 123,
            "select": ["id", "total", "status"],
            "include": [{"relation": "items"}]
        }
    """

    model: str = Field(..., description="The model/table name")
    id: Any = Field(..., description="The primary key value")
    select: list[str] | None = Field(
        default=None, description="Fields to select"
    )
    include: list[IncludeClause] | None = Field(
        default=None, description="Relations to include"
    )

    model_config = {"frozen": True}


class AggregateRequest(BaseModel):
    """
    A request to perform an aggregation.

    Example:
        {
            "model": "Order",
            "operation": "sum",
            "field": "total",
            "where": [{"field": "status", "op": "eq", "value": "completed"}]
        }
    """

    model: str = Field(..., description="The model/table name")
    operation: str = Field(..., description="Aggregation operation: count, sum, avg, min, max")
    field: str | None = Field(
        default=None, description="Field to aggregate (required for sum/avg/min/max)"
    )
    where: list[FilterClause] | None = Field(
        default=None, description="Filter conditions"
    )

    model_config = {"frozen": True}

    @field_validator("operation")
    @classmethod
    def validate_operation(cls, v: str) -> str:
        """Validate aggregation operation."""
        allowed = {"count", "sum", "avg", "min", "max"}
        if v.lower() not in allowed:
            raise ValueError(f"Operation must be one of: {', '.join(allowed)}")
        return v.lower()


class QueryResult(BaseModel):
    """
    Result of a query operation.
    """

    data: list[dict[str, Any]] = Field(default_factory=list)
    next_cursor: str | None = Field(default=None)
    has_more: bool = Field(default=False)
    total_count: int | None = Field(default=None)

    model_config = {"frozen": True}


class GetResult(BaseModel):
    """
    Result of a get operation.
    """

    data: dict[str, Any] | None = Field(default=None)
    found: bool = Field(default=False)

    model_config = {"frozen": True}


class AggregateResult(BaseModel):
    """
    Result of an aggregation operation.
    """

    value: Any = Field(default=None)
    operation: str
    field: str | None = None
    row_count: int = Field(default=0)

    model_config = {"frozen": True}


# =============================================================================
# MUTATION DSL (Phase 2)
# =============================================================================


class CreateRequest(BaseModel):
    """
    A request to create a new record.

    Example:
        {
            "model": "Order",
            "data": {
                "customer_id": 123,
                "total": 99.99,
                "status": "pending"
            },
            "reason": "Customer placed order via checkout flow"
        }
    """

    model: str = Field(..., description="The model/table name")
    data: dict[str, Any] = Field(..., description="Field values for the new record")
    reason: str | None = Field(
        default=None,
        description="Reason for the mutation (required by some policies)",
    )
    return_fields: list[str] | None = Field(
        default=None,
        description="Fields to return after creation (None means all allowed)",
    )

    model_config = {"frozen": True}


class UpdateRequest(BaseModel):
    """
    A request to update a record by primary key.

    Example:
        {
            "model": "Order",
            "id": 123,
            "data": {"status": "shipped"},
            "reason": "Order shipped by warehouse"
        }
    """

    model: str = Field(..., description="The model/table name")
    id: Any = Field(..., description="The primary key of the record to update")
    data: dict[str, Any] = Field(..., description="Fields to update")
    reason: str | None = Field(
        default=None,
        description="Reason for the mutation",
    )
    return_fields: list[str] | None = Field(
        default=None,
        description="Fields to return after update",
    )

    model_config = {"frozen": True}


class DeleteRequest(BaseModel):
    """
    A request to delete a record by primary key.

    By default, this performs a soft delete if the model has a soft delete field.
    Hard deletes require explicit policy permission.

    Example:
        {
            "model": "Order",
            "id": 123,
            "reason": "Customer requested cancellation",
            "hard": false
        }
    """

    model: str = Field(..., description="The model/table name")
    id: Any = Field(..., description="The primary key of the record to delete")
    reason: str | None = Field(
        default=None,
        description="Reason for the deletion",
    )
    hard: bool = Field(
        default=False,
        description="If True, perform hard delete instead of soft delete",
    )

    model_config = {"frozen": True}


class BulkUpdateRequest(BaseModel):
    """
    A request to update multiple records by their primary keys.

    This is safer than a filter-based bulk update because it requires
    explicit identification of each record to update.

    Example:
        {
            "model": "Order",
            "ids": [123, 124, 125],
            "data": {"status": "cancelled"},
            "reason": "Batch cancellation due to supplier issue"
        }
    """

    model: str = Field(..., description="The model/table name")
    ids: list[Any] = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Primary keys of records to update",
    )
    data: dict[str, Any] = Field(..., description="Fields to update on all records")
    reason: str | None = Field(
        default=None,
        description="Reason for the mutation",
    )

    model_config = {"frozen": True}


class CreateResult(BaseModel):
    """
    Result of a create operation.
    """

    data: dict[str, Any] = Field(default_factory=dict)
    id: Any = Field(default=None, description="Primary key of created record")
    success: bool = Field(default=True)

    model_config = {"frozen": True}


class UpdateResult(BaseModel):
    """
    Result of an update operation.
    """

    data: dict[str, Any] | None = Field(default=None)
    success: bool = Field(default=True)
    found: bool = Field(default=True)

    model_config = {"frozen": True}


class DeleteResult(BaseModel):
    """
    Result of a delete operation.
    """

    success: bool = Field(default=True)
    found: bool = Field(default=True)
    soft_deleted: bool = Field(default=True, description="True if soft delete was used")

    model_config = {"frozen": True}


class BulkUpdateResult(BaseModel):
    """
    Result of a bulk update operation.
    """

    updated_count: int = Field(default=0)
    success: bool = Field(default=True)
    failed_ids: list[Any] = Field(
        default_factory=list,
        description="IDs that failed to update (if any)",
    )

    model_config = {"frozen": True}
