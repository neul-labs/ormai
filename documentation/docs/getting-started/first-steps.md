# First Steps

Now that you have OrmAI installed, let's explore the core concepts you'll work with daily.

## Understanding the Principal

The `Principal` represents the identity making the request. It carries context used for scoping and authorization:

```python
from ormai.core import Principal

principal = Principal(
    tenant_id="acme-corp",      # Tenant/organization identifier
    user_id="user-123",         # User identifier
    roles=["admin", "member"],  # User roles for authorization
)
```

### Why Principals Matter

Principals enable automatic scoping. When you configure a model with:

```python
ModelPolicy(
    scoping={"tenant_id": "principal.tenant_id"}
)
```

Every query automatically includes a `WHERE tenant_id = 'acme-corp'` filter, preventing cross-tenant data access.

## The Run Context

`RunContext` bundles everything needed for a request:

```python
from ormai.core import RunContext
import uuid

ctx = RunContext(
    principal=principal,
    db=session,                           # Database session
    request_id=str(uuid.uuid4()),         # Unique request identifier
    trace_id="trace-abc",                 # Distributed tracing ID
)
```

### Context Properties

| Property | Description |
|----------|-------------|
| `principal` | Identity and authorization context |
| `db` | Database session (ORM-specific) |
| `request_id` | Unique identifier for this request |
| `trace_id` | Distributed tracing correlation ID |

## Query DSL Basics

OrmAI uses a structured query DSL instead of raw SQL:

### Basic Query

```python
result = await toolset.query(
    ctx,
    model="Order",
    filters=[
        {"field": "status", "op": "eq", "value": "pending"},
        {"field": "total", "op": "gte", "value": 1000},
    ],
    select=["id", "status", "total", "created_at"],
    order=[{"field": "created_at", "direction": "desc"}],
    limit=20,
)
```

### Filter Operators

| Operator | Description | Example |
|----------|-------------|---------|
| `eq` | Equal | `{"field": "status", "op": "eq", "value": "active"}` |
| `neq` | Not equal | `{"field": "status", "op": "neq", "value": "deleted"}` |
| `gt` | Greater than | `{"field": "price", "op": "gt", "value": 100}` |
| `gte` | Greater than or equal | `{"field": "price", "op": "gte", "value": 100}` |
| `lt` | Less than | `{"field": "quantity", "op": "lt", "value": 10}` |
| `lte` | Less than or equal | `{"field": "quantity", "op": "lte", "value": 10}` |
| `in` | In list | `{"field": "status", "op": "in", "value": ["a", "b"]}` |
| `contains` | String contains | `{"field": "name", "op": "contains", "value": "corp"}` |
| `is_null` | Is null | `{"field": "deleted_at", "op": "is_null", "value": true}` |

### Getting a Single Record

```python
result = await toolset.get(
    ctx,
    model="Order",
    id=123,
    select=["id", "status", "total"],
)
```

### Aggregations

```python
result = await toolset.aggregate(
    ctx,
    model="Order",
    filters=[{"field": "status", "op": "eq", "value": "completed"}],
    aggregations=[
        {"function": "count", "alias": "order_count"},
        {"function": "sum", "field": "total", "alias": "total_revenue"},
        {"function": "avg", "field": "total", "alias": "avg_order_value"},
    ],
    group_by=["status"],
)
```

## Including Relations

Fetch related data in a single query:

```python
result = await toolset.query(
    ctx,
    model="Order",
    filters=[{"field": "status", "op": "eq", "value": "pending"}],
    include=[
        {"relation": "user", "select": ["id", "name", "email"]},
        {"relation": "items", "select": ["id", "product_name", "quantity"]},
    ],
)
```

!!! note "Include Depth Limits"
    Policies can limit include depth to prevent expensive nested queries. The default maximum depth is configurable in your policy's budget settings.

## Handling Results

Query results include metadata:

```python
result = await toolset.query(ctx, model="Order", limit=10)

# Access the data
for order in result.rows:
    print(f"Order {order['id']}: {order['status']}")

# Pagination info
print(f"Total rows: {result.total}")
print(f"Has more: {result.has_more}")
print(f"Next cursor: {result.next_cursor}")
```

### Cursor-Based Pagination

For stable pagination under concurrent writes:

```python
# First page
page1 = await toolset.query(ctx, model="Order", limit=10)

# Next page using cursor
page2 = await toolset.query(
    ctx,
    model="Order",
    limit=10,
    cursor=page1.next_cursor,
)
```

## Error Handling

OrmAI raises specific exceptions:

```python
from ormai.core import (
    ModelNotAllowedError,
    FieldNotAllowedError,
    QueryBudgetExceededError,
    TenantScopeRequiredError,
)

try:
    result = await toolset.query(ctx, model="SecretModel")
except ModelNotAllowedError as e:
    print(f"Model access denied: {e}")
except QueryBudgetExceededError as e:
    print(f"Query too expensive: {e}")
except TenantScopeRequiredError as e:
    print(f"Tenant scoping required: {e}")
```

## Next Steps

- [Policies](../concepts/policies.md) - Configure access control
- [Tools](../concepts/tools.md) - Explore all available tools
- [Write Operations](../guides/write-operations.md) - Enable mutations
