# Write Operations Guide

This guide covers enabling and securing create, update, and delete operations in OrmAI.

## Overview

Write operations in OrmAI are:

- **Opt-in** - Disabled by default
- **Policy-controlled** - Fine-grained permissions
- **Audited** - Complete change tracking
- **Approval-ready** - Optional human review

## Enabling Writes

### Basic Write Policy

```python
from ormai.policy import ModelPolicy, WritePolicy, WriteAction

ModelPolicy(
    allowed=True,
    fields={...},
    write_policy=WritePolicy(
        create=WriteAction.Allow,
        update=WriteAction.Allow,
        delete=WriteAction.Deny,  # Keep delete disabled
    ),
)
```

### Write Actions

| Action | Behavior |
|--------|----------|
| `Allow` | Operation proceeds immediately |
| `Deny` | Operation is rejected |
| `RequireApproval` | Operation waits for human approval |

## Create Operations

### Basic Create

```python
result = await toolset.create(
    ctx,
    model="Order",
    data={
        "status": "pending",
        "total": 5000,
        "items": [...],
    },
)

# Returns created record
print(result.data)
# {"id": 123, "status": "pending", "total": 5000, "tenant_id": "acme-corp", ...}
```

### Auto-Set Fields

Automatically populate fields:

```python
WritePolicy(
    create=WriteAction.Allow,
    auto_set={
        "tenant_id": "principal.tenant_id",
        "created_by": "principal.user_id",
        "created_at": "now()",
    },
)
```

### Required Fields

Enforce required fields:

```python
WritePolicy(
    create=WriteAction.Allow,
    required_fields=["name", "email", "status"],
)
```

Attempting to create without required fields:

```python
# This will fail
await toolset.create(ctx, model="User", data={"name": "Alice"})
# ValidationError: Missing required fields: email, status
```

## Update Operations

### Basic Update

```python
result = await toolset.update(
    ctx,
    model="Order",
    id=123,
    data={
        "status": "confirmed",
    },
)
```

### Immutable Fields

Protect fields from modification:

```python
WritePolicy(
    update=WriteAction.Allow,
    immutable_fields=["id", "tenant_id", "created_at", "created_by"],
)
```

Attempting to update immutable fields:

```python
# This will fail
await toolset.update(ctx, model="Order", id=123, data={"tenant_id": "other"})
# WriteNotAllowedError: Cannot modify immutable field: tenant_id
```

### Auto-Update Fields

```python
WritePolicy(
    update=WriteAction.Allow,
    auto_set={
        "updated_at": "now()",
        "updated_by": "principal.user_id",
    },
)
```

## Bulk Updates

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

print(result.data)
# {"updated_count": 42}
```

!!! warning "Bulk Update Safety"
    Bulk updates are powerful. Consider requiring approval for bulk operations.

## Delete Operations

### Soft Delete

Prefer soft deletes over hard deletes:

```python
# Instead of delete, use update
await toolset.update(
    ctx,
    model="Order",
    id=123,
    data={
        "deleted": True,
        "deleted_at": datetime.now().isoformat(),
    },
)
```

Configure policy to hide deleted records:

```python
ModelPolicy(
    row_policies=[
        RowPolicy(
            name="hide_deleted",
            condition="deleted = false OR deleted IS NULL",
        ),
    ],
)
```

### Hard Delete

If hard delete is needed:

```python
WritePolicy(
    delete=WriteAction.RequireApproval,  # Require approval
)
```

```python
result = await toolset.delete(
    ctx,
    model="Order",
    id=123,
)
```

## Approval Workflows

For sensitive operations, require human approval:

### Configure Approval

```python
WritePolicy(
    create=WriteAction.Allow,
    update=WriteAction.Allow,
    delete=WriteAction.RequireApproval,  # Deletes need approval
)
```

### Deferred Execution

```python
from ormai.tools import DeferredExecutor
from ormai.utils import InMemoryApprovalQueue

queue = InMemoryApprovalQueue()
executor = DeferredExecutor(approval_gate=queue)

# Operation is deferred
deferred = await executor.defer(
    tool=delete_tool,
    ctx=ctx,
    model="Order",
    id=123,
)

print(deferred.status)  # "pending_approval"
print(deferred.id)      # "defer-abc123"
```

### Approval Interface

```python
# In admin interface
pending = await queue.get_pending()

for op in pending:
    print(f"Operation: {op.tool_name} on {op.model}")
    print(f"Requested by: {op.principal.user_id}")
    print(f"Data: {op.data}")

    # Approve or reject
    if should_approve(op):
        await queue.approve(op.id)
    else:
        await queue.reject(op.id, reason="Not authorized")
```

### Execute Approved

```python
# After approval
result = await executor.execute(deferred.id)
```

## Transaction Handling

### Basic Transaction

```python
from ormai.utils import TransactionManager

manager = TransactionManager(adapter)

async with manager.begin(ctx):
    await toolset.create(ctx, model="Order", data={...})
    await toolset.create(ctx, model="OrderItem", data={...})
    await toolset.update(ctx, model="Inventory", id=..., data={...})
    # Commits on success
```

### Savepoints

```python
async with manager.begin(ctx) as tx:
    await toolset.create(ctx, model="Order", data={...})

    async with tx.savepoint("items"):
        try:
            await toolset.create(ctx, model="OrderItem", data={...})
        except ValidationError:
            # Savepoint rolls back, main transaction continues
            pass

    # This still commits
```

### Retry Logic

```python
from ormai.utils import RetryConfig, retry_async

config = RetryConfig(
    max_attempts=3,
    retryable_exceptions=(DeadlockError, TimeoutError),
)

@retry_async(config)
async def create_order_with_retry(ctx, data):
    return await toolset.create(ctx, model="Order", data=data)
```

## Audit Logging

Write operations are fully audited:

```python
# Enable snapshots for before/after tracking
middleware = AuditMiddleware(
    store=audit_store,
    include_snapshots=True,
)

audited_toolset = middleware.wrap(toolset)
```

Audit record for update:

```json
{
    "id": "aud-456",
    "tool_name": "update",
    "model": "Order",
    "action": "update",
    "inputs": {"id": 123, "data": {"status": "confirmed"}},
    "before_snapshot": {"id": 123, "status": "pending"},
    "after_snapshot": {"id": 123, "status": "confirmed"},
    "success": true
}
```

## Validation

### Field Validation

Use write policies for basic validation:

```python
WritePolicy(
    required_fields=["email", "name"],
    immutable_fields=["id", "tenant_id"],
)
```

### Custom Validation

Add validation in domain tools:

```python
class CreateOrderTool(Tool):
    async def execute(self, ctx, data):
        # Validate
        if data.get("total", 0) < 0:
            return ToolResult(
                success=False,
                error="Total cannot be negative",
            )

        if not self.validate_items(data.get("items", [])):
            return ToolResult(
                success=False,
                error="Invalid order items",
            )

        # Proceed with create
        return await self.toolset.create(ctx, model="Order", data=data)
```

## Error Handling

```python
from ormai.core import WriteNotAllowedError, ValidationError, RecordNotFoundError

try:
    await toolset.update(ctx, model="Order", id=123, data={...})
except WriteNotAllowedError as e:
    print(f"Write denied: {e.message}")
except ValidationError as e:
    print(f"Validation failed: {e.details}")
except RecordNotFoundError as e:
    print(f"Record not found: {e.message}")
```

## Best Practices

1. **Default to deny** - Only enable writes where needed

2. **Use immutable fields** - Protect IDs, tenant_id, timestamps

3. **Auto-set tenant** - Prevent tenant spoofing

4. **Prefer soft delete** - Keep data for audit/recovery

5. **Require approval for destructive ops** - Deletes, bulk updates

6. **Enable audit snapshots** - Track before/after for writes

7. **Use transactions** - Group related operations

8. **Validate early** - Check data before attempting writes

## Next Steps

- [Custom Tools](custom-tools.md) - Build domain-specific write tools
- [Audit Logging](../concepts/audit-logging.md) - Track all changes
- [Evaluation](evaluation.md) - Test write operations
