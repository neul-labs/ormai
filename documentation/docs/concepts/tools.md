# Tools

Tools are the interface AI agents use to interact with your database. OrmAI provides built-in generic tools and supports custom domain tools.

## Built-in Tools

### Read Tools

| Tool | Description | Use Case |
|------|-------------|----------|
| `DescribeSchemaTool` | List available models and fields | Schema discovery |
| `QueryTool` | Query records with filters | List and search |
| `GetTool` | Fetch single record by ID | Detail views |
| `AggregateTool` | Compute aggregations | Analytics |

### Write Tools

| Tool | Description | Use Case |
|------|-------------|----------|
| `CreateTool` | Create new records | Data entry |
| `UpdateTool` | Update existing records | Modifications |
| `DeleteTool` | Delete records | Removal |
| `BulkUpdateTool` | Update multiple records | Batch operations |

## Using Tools

### DescribeSchemaTool

Discover available models and their fields:

```python
result = await toolset.describe_schema(ctx)

# Returns schema information respecting policy
{
    "models": {
        "Order": {
            "fields": ["id", "status", "total", "created_at"],
            "relations": ["user", "items"],
            "writable": true
        },
        "User": {
            "fields": ["id", "name", "email"],
            "relations": ["orders"],
            "writable": false
        }
    }
}
```

### QueryTool

Query records with filters, ordering, and pagination:

```python
result = await toolset.query(
    ctx,
    model="Order",
    filters=[
        {"field": "status", "op": "eq", "value": "pending"},
        {"field": "total", "op": "gte", "value": 1000},
    ],
    select=["id", "status", "total", "created_at"],
    order=[
        {"field": "created_at", "direction": "desc"}
    ],
    include=[
        {"relation": "user", "select": ["id", "name"]}
    ],
    limit=20,
    cursor=None,  # For pagination
)
```

#### Response

```python
{
    "rows": [
        {
            "id": 123,
            "status": "pending",
            "total": 5000,
            "created_at": "2024-01-15T10:30:00Z",
            "user": {"id": "u-1", "name": "Alice"}
        },
        ...
    ],
    "total": 45,
    "has_more": True,
    "next_cursor": "eyJpZCI6MTIzfQ=="
}
```

### GetTool

Fetch a single record by ID:

```python
result = await toolset.get(
    ctx,
    model="Order",
    id=123,
    select=["id", "status", "total", "items"],
    include=[
        {"relation": "items", "select": ["id", "product_name", "quantity"]}
    ],
)
```

### AggregateTool

Compute aggregations:

```python
result = await toolset.aggregate(
    ctx,
    model="Order",
    filters=[
        {"field": "status", "op": "eq", "value": "completed"}
    ],
    aggregations=[
        {"function": "count", "alias": "total_orders"},
        {"function": "sum", "field": "total", "alias": "revenue"},
        {"function": "avg", "field": "total", "alias": "avg_order"},
        {"function": "min", "field": "total", "alias": "min_order"},
        {"function": "max", "field": "total", "alias": "max_order"},
    ],
    group_by=["status"],
)
```

#### Aggregation Functions

| Function | Description | Requires Field |
|----------|-------------|----------------|
| `count` | Count rows | No |
| `sum` | Sum values | Yes |
| `avg` | Average values | Yes |
| `min` | Minimum value | Yes |
| `max` | Maximum value | Yes |

### CreateTool

Create new records:

```python
result = await toolset.create(
    ctx,
    model="Order",
    data={
        "status": "pending",
        "total": 2500,
        "user_id": "u-123",
    },
)

# Returns created record
{
    "id": 456,
    "status": "pending",
    "total": 2500,
    "user_id": "u-123",
    "tenant_id": "acme-corp",  # Auto-set from principal
    "created_at": "2024-01-15T10:30:00Z"
}
```

### UpdateTool

Update existing records:

```python
result = await toolset.update(
    ctx,
    model="Order",
    id=456,
    data={
        "status": "confirmed",
    },
)
```

### DeleteTool

Delete records:

```python
result = await toolset.delete(
    ctx,
    model="Order",
    id=456,
)
```

### BulkUpdateTool

Update multiple records:

```python
result = await toolset.bulk_update(
    ctx,
    model="Order",
    filters=[
        {"field": "status", "op": "eq", "value": "pending"},
        {"field": "created_at", "op": "lt", "value": "2024-01-01"},
    ],
    data={
        "status": "expired",
    },
)

# Returns count of updated rows
{"updated_count": 15}
```

## Tool Registry

Tools are organized in a registry:

```python
from ormai.tools import ToolRegistry

registry = ToolRegistry()

# Register built-in tools
registry.register(QueryTool(adapter, policy))
registry.register(GetTool(adapter, policy))
registry.register(CreateTool(adapter, policy))

# Get tool by name
tool = registry.get("query")

# List all tools
for name, tool in registry.items():
    print(f"{name}: {tool.description}")
```

## Tool Results

All tools return a `ToolResult`:

```python
@dataclass
class ToolResult:
    success: bool
    data: Any
    error: str | None
    metadata: dict  # Execution metadata
```

### Metadata

```python
result = await toolset.query(ctx, model="Order", ...)

print(result.metadata)
# {
#     "execution_time_ms": 45,
#     "row_count": 20,
#     "policy_applied": ["tenant_scope", "field_mask"],
#     "cache_hit": False,
# }
```

## Domain Tools

Create custom tools for domain-specific operations:

```python
from ormai.tools import Tool, ToolResult

class CancelOrderTool(Tool):
    name = "cancel_order"
    description = "Cancel an order and refund payment"

    async def execute(
        self,
        ctx: RunContext,
        order_id: int,
        reason: str,
    ) -> ToolResult:
        # Get the order
        order = await self.toolset.get(ctx, model="Order", id=order_id)

        if order.data["status"] == "shipped":
            return ToolResult(
                success=False,
                error="Cannot cancel shipped orders",
            )

        # Update order status
        await self.toolset.update(
            ctx,
            model="Order",
            id=order_id,
            data={"status": "cancelled", "cancel_reason": reason},
        )

        # Process refund
        await self.process_refund(order.data)

        return ToolResult(success=True, data={"cancelled": True})
```

### Registering Domain Tools

```python
registry.register(CancelOrderTool(adapter, policy))
```

## Deferred Execution

For operations requiring approval:

```python
from ormai.tools import DeferredExecutor

executor = DeferredExecutor(
    approval_gate=my_approval_gate,
    timeout_seconds=3600,  # 1 hour
)

# Create a deferred operation
deferred = await executor.defer(
    tool=delete_tool,
    ctx=ctx,
    model="Order",
    id=123,
)

print(deferred.id)  # "defer-abc123"
print(deferred.status)  # "pending_approval"

# Later, after approval
result = await executor.execute(deferred.id)
```

### Approval Gates

```python
from ormai.utils import ApprovalGate, AutoApproveGate, CallbackApprovalGate

# Auto-approve (for testing)
gate = AutoApproveGate()

# Callback-based approval
async def check_approval(operation):
    # Check with human or external system
    return await my_approval_service.check(operation)

gate = CallbackApprovalGate(callback=check_approval)

# In-memory queue (for development)
from ormai.utils import InMemoryApprovalQueue
gate = InMemoryApprovalQueue()
```

## Tool Schemas for LLMs

Export tool schemas for LLM function calling:

```python
schemas = registry.to_openai_functions()
# Returns OpenAI function calling format

schemas = registry.to_anthropic_tools()
# Returns Anthropic tool use format
```

Example output:

```json
{
    "name": "query",
    "description": "Query records from a database model",
    "parameters": {
        "type": "object",
        "properties": {
            "model": {"type": "string", "description": "Model name"},
            "filters": {"type": "array", "items": {...}},
            "select": {"type": "array", "items": {"type": "string"}},
            "limit": {"type": "integer", "default": 50}
        },
        "required": ["model"]
    }
}
```

## Next Steps

- [Audit Logging](audit-logging.md) - Logging tool operations
- [Write Operations](../guides/write-operations.md) - Write tool details
- [Custom Tools](../guides/custom-tools.md) - Building domain tools
