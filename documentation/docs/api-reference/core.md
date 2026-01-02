# Core API Reference

The core module provides fundamental types for OrmAI operations.

## Principal

Represents the identity making a request.

```python
from ormai.core import Principal
```

### Constructor

```python
Principal(
    tenant_id: str,
    user_id: str,
    roles: list[str] = [],
    metadata: dict[str, Any] = {},
)
```

### Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `tenant_id` | `str` | Tenant/organization identifier |
| `user_id` | `str` | User identifier |
| `roles` | `list[str]` | User roles for authorization |
| `metadata` | `dict` | Additional context |

### Example

```python
principal = Principal(
    tenant_id="acme-corp",
    user_id="user-123",
    roles=["admin", "member"],
    metadata={"department": "engineering"},
)
```

---

## RunContext

Bundles execution context for a request.

```python
from ormai.core import RunContext
```

### Constructor

```python
RunContext(
    principal: Principal,
    db: Any,
    request_id: str | None = None,
    trace_id: str | None = None,
)
```

### Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `principal` | `Principal` | Identity context |
| `db` | `Any` | Database session (ORM-specific) |
| `request_id` | `str \| None` | Unique request identifier |
| `trace_id` | `str \| None` | Distributed tracing ID |

### Example

```python
ctx = RunContext(
    principal=principal,
    db=session,
    request_id=str(uuid.uuid4()),
    trace_id=request.headers.get("X-Trace-ID"),
)
```

---

## Query Request Types

### QueryRequest

Request for querying multiple records.

```python
from ormai.core import QueryRequest
```

```python
QueryRequest(
    model: str,
    filters: list[FilterClause] = [],
    select: list[str] | None = None,
    order: list[OrderClause] = [],
    include: list[IncludeClause] = [],
    limit: int = 50,
    cursor: str | None = None,
)
```

### GetRequest

Request for fetching a single record.

```python
from ormai.core import GetRequest
```

```python
GetRequest(
    model: str,
    id: Any,
    select: list[str] | None = None,
    include: list[IncludeClause] = [],
)
```

### AggregateRequest

Request for computing aggregations.

```python
from ormai.core import AggregateRequest
```

```python
AggregateRequest(
    model: str,
    filters: list[FilterClause] = [],
    aggregations: list[AggregationClause],
    group_by: list[str] = [],
)
```

---

## Filter Clauses

### FilterClause

Represents a filter condition.

```python
from ormai.core import FilterClause
```

```python
FilterClause(
    field: str,
    op: str,
    value: Any,
)
```

### Operators

| Operator | Description |
|----------|-------------|
| `eq` | Equal |
| `neq` | Not equal |
| `gt` | Greater than |
| `gte` | Greater than or equal |
| `lt` | Less than |
| `lte` | Less than or equal |
| `in` | In list |
| `not_in` | Not in list |
| `contains` | String contains |
| `starts_with` | String starts with |
| `ends_with` | String ends with |
| `is_null` | Is null (value: bool) |

### Examples

```python
# Simple equality
FilterClause(field="status", op="eq", value="active")

# Numeric comparison
FilterClause(field="price", op="gte", value=100)

# In list
FilterClause(field="status", op="in", value=["pending", "active"])

# String contains
FilterClause(field="name", op="contains", value="corp")

# Null check
FilterClause(field="deleted_at", op="is_null", value=True)
```

---

## Order Clauses

### OrderClause

Represents an ordering directive.

```python
from ormai.core import OrderClause
```

```python
OrderClause(
    field: str,
    direction: str = "asc",  # "asc" or "desc"
)
```

### Example

```python
order = [
    OrderClause(field="created_at", direction="desc"),
    OrderClause(field="id", direction="asc"),
]
```

---

## Include Clauses

### IncludeClause

Represents a relation to include.

```python
from ormai.core import IncludeClause
```

```python
IncludeClause(
    relation: str,
    select: list[str] | None = None,
    filters: list[FilterClause] = [],
    include: list[IncludeClause] = [],  # Nested includes
)
```

### Example

```python
include = [
    IncludeClause(
        relation="items",
        select=["id", "product_name", "quantity"],
        filters=[FilterClause(field="quantity", op="gt", value=0)],
        include=[
            IncludeClause(relation="product", select=["id", "name"]),
        ],
    ),
]
```

---

## Aggregation Clauses

### AggregationClause

Represents an aggregation operation.

```python
from ormai.core import AggregationClause
```

```python
AggregationClause(
    function: str,       # "count", "sum", "avg", "min", "max"
    field: str | None = None,  # Required for sum, avg, min, max
    alias: str,          # Output field name
)
```

### Example

```python
aggregations = [
    AggregationClause(function="count", alias="total_orders"),
    AggregationClause(function="sum", field="total", alias="revenue"),
    AggregationClause(function="avg", field="total", alias="avg_order"),
]
```

---

## Cursor Pagination

### CursorEncoder

Encode and decode pagination cursors.

```python
from ormai.core import CursorEncoder
```

```python
encoder = CursorEncoder(secret_key="your-secret")

# Encode cursor
cursor = encoder.encode({"id": 123, "created_at": "2024-01-15T10:00:00Z"})

# Decode cursor
data = encoder.decode(cursor)
```

---

## Schema Metadata

### SchemaMetadata

Container for all model metadata.

```python
from ormai.core import SchemaMetadata
```

```python
@dataclass
class SchemaMetadata:
    models: dict[str, ModelMetadata]
```

### ModelMetadata

Metadata for a single model.

```python
@dataclass
class ModelMetadata:
    name: str
    table_name: str
    primary_key: str | list[str]
    fields: dict[str, FieldMetadata]
    relations: dict[str, RelationMetadata]
```

### FieldMetadata

Metadata for a single field.

```python
@dataclass
class FieldMetadata:
    name: str
    column_name: str
    python_type: type
    nullable: bool
    default: Any | None
    primary_key: bool
    unique: bool
```

### RelationMetadata

Metadata for a relation.

```python
@dataclass
class RelationMetadata:
    name: str
    target_model: str
    relation_type: RelationType
    foreign_key: str | None
    back_populates: str | None
```

### RelationType

```python
class RelationType(Enum):
    ONE_TO_ONE = "one_to_one"
    ONE_TO_MANY = "one_to_many"
    MANY_TO_ONE = "many_to_one"
    MANY_TO_MANY = "many_to_many"
```

---

## Errors

### Base Error

```python
from ormai.core import OrmAIError

class OrmAIError(Exception):
    code: str
    message: str
    details: dict
```

### Specific Errors

| Error | Code | Description |
|-------|------|-------------|
| `ModelNotAllowedError` | `MODEL_NOT_ALLOWED` | Model not in policy allowlist |
| `FieldNotAllowedError` | `FIELD_NOT_ALLOWED` | Field not allowed by policy |
| `QueryBudgetExceededError` | `QUERY_BUDGET_EXCEEDED` | Query exceeds budget limits |
| `TenantScopeRequiredError` | `TENANT_SCOPE_REQUIRED` | Multi-tenant model missing scope |
| `WriteNotAllowedError` | `WRITE_NOT_ALLOWED` | Write operation not permitted |
| `RecordNotFoundError` | `RECORD_NOT_FOUND` | Record does not exist |
| `ValidationError` | `VALIDATION_ERROR` | Input validation failed |

### Example

```python
from ormai.core import ModelNotAllowedError

try:
    result = await toolset.query(ctx, model="SecretModel")
except ModelNotAllowedError as e:
    print(f"Code: {e.code}")
    print(f"Message: {e.message}")
    print(f"Details: {e.details}")
```
