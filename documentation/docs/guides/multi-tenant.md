# Multi-Tenant Setup Guide

This guide covers setting up OrmAI for multi-tenant applications where data must be strictly isolated between tenants.

## Overview

Multi-tenancy in OrmAI is handled through:

1. **Principals** - Carrying tenant context
2. **Scoping Rules** - Automatic query filtering
3. **Policy Enforcement** - Preventing cross-tenant access

## Basic Setup

### 1. Define Tenant-Aware Models

Ensure your models have a `tenant_id` column:

```python
from sqlalchemy import Column, String, ForeignKey
from sqlalchemy.orm import declarative_base

Base = declarative_base()

class Tenant(Base):
    __tablename__ = "tenants"
    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)

class User(Base):
    __tablename__ = "users"
    id = Column(String, primary_key=True)
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False)
    email = Column(String, nullable=False)

class Order(Base):
    __tablename__ = "orders"
    id = Column(Integer, primary_key=True)
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    status = Column(String)
```

### 2. Configure Tenant Scoping

Add scoping rules to your policy:

```python
from ormai.policy import Policy, ModelPolicy, FieldPolicy, FieldAction

policy = Policy(
    models={
        "User": ModelPolicy(
            allowed=True,
            fields={
                "id": FieldPolicy(action=FieldAction.Allow),
                "tenant_id": FieldPolicy(action=FieldAction.Allow),
                "email": FieldPolicy(action=FieldAction.Allow),
            },
            scoping={"tenant_id": "principal.tenant_id"},
        ),
        "Order": ModelPolicy(
            allowed=True,
            fields={
                "id": FieldPolicy(action=FieldAction.Allow),
                "tenant_id": FieldPolicy(action=FieldAction.Allow),
                "user_id": FieldPolicy(action=FieldAction.Allow),
                "status": FieldPolicy(action=FieldAction.Allow),
            },
            scoping={"tenant_id": "principal.tenant_id"},
        ),
    },
)
```

### 3. Pass Tenant in Principal

Extract tenant from your authentication:

```python
from ormai.core import Principal, RunContext

def get_context(request, db):
    # Extract from JWT, header, or session
    tenant_id = request.headers.get("X-Tenant-ID")
    user_id = request.user.id

    return RunContext(
        principal=Principal(
            tenant_id=tenant_id,
            user_id=user_id,
        ),
        db=db,
    )
```

## How Scoping Works

When a query is executed:

```python
# User's query
result = await toolset.query(
    ctx,
    model="Order",
    filters=[{"field": "status", "op": "eq", "value": "pending"}],
)

# OrmAI automatically adds tenant filter
# Resulting SQL:
# SELECT * FROM orders
# WHERE tenant_id = 'acme-corp'  <-- Injected
# AND status = 'pending'         <-- User filter
```

Users cannot override or bypass the tenant scope.

## Multiple Scoping Fields

Scope by multiple fields:

```python
ModelPolicy(
    scoping={
        "tenant_id": "principal.tenant_id",
        "organization_id": "principal.metadata.org_id",
    }
)
```

## User-Level Scoping

For user-specific data access:

```python
ModelPolicy(
    scoping={
        "tenant_id": "principal.tenant_id",
        "owner_id": "principal.user_id",
    }
)
```

This restricts users to their own data within the tenant.

## Hierarchical Tenancy

For parent-child tenant relationships:

```python
# Principal with hierarchy
principal = Principal(
    tenant_id="child-tenant",
    metadata={
        "parent_tenant_id": "parent-tenant",
        "tenant_hierarchy": ["root", "parent-tenant", "child-tenant"],
    },
)

# Policy with hierarchical access
ModelPolicy(
    scoping={"tenant_id": "principal.tenant_id"},
    row_policies=[
        RowPolicy(
            name="parent_access",
            condition="tenant_id IN principal.metadata.tenant_hierarchy",
            description="Access data from parent tenants",
        ),
    ],
)
```

## Cross-Tenant Access (Admin)

For admin operations across tenants:

```python
# Admin principal
admin_principal = Principal(
    tenant_id="system",
    user_id="admin-001",
    roles=["super_admin"],
)

# Policy with admin bypass
ModelPolicy(
    scoping={"tenant_id": "principal.tenant_id"},
    row_policies=[
        RowPolicy(
            name="admin_bypass",
            condition="'super_admin' IN principal.roles",
            bypass=True,  # Bypasses scoping for admins
        ),
    ],
)
```

!!! warning "Security Note"
    Use admin bypass carefully. Ensure proper authentication and audit logging for admin operations.

## Preventing Tenant Leakage

### Write Operations

Automatically set tenant on create:

```python
from ormai.policy import WritePolicy, WriteAction

ModelPolicy(
    write_policy=WritePolicy(
        create=WriteAction.Allow,
        auto_set={
            "tenant_id": "principal.tenant_id",
        },
        immutable_fields=["tenant_id"],  # Cannot be updated
    ),
)
```

### Validation

Add row policies to catch edge cases:

```python
RowPolicy(
    name="tenant_required",
    condition="tenant_id IS NOT NULL",
    description="Ensure tenant_id is always set",
)
```

## Testing Multi-Tenancy

### Unit Tests

```python
async def test_tenant_isolation():
    # Create contexts for different tenants
    ctx_tenant_a = RunContext(
        principal=Principal(tenant_id="tenant-a", user_id="user-1"),
        db=session,
    )
    ctx_tenant_b = RunContext(
        principal=Principal(tenant_id="tenant-b", user_id="user-2"),
        db=session,
    )

    # Create order in tenant A
    await toolset.create(
        ctx_tenant_a,
        model="Order",
        data={"status": "pending"},
    )

    # Query from tenant B - should not see tenant A's order
    result = await toolset.query(ctx_tenant_b, model="Order")
    assert len(result.rows) == 0
```

### Invariant Testing

Use the eval harness:

```python
from ormai.eval import EvalHarness, no_cross_tenant_data

harness = EvalHarness(toolset, policy)

# Run with invariant checks
result = await harness.run(
    ctx,
    tool="query",
    kwargs={"model": "Order"},
    invariants=[no_cross_tenant_data],
)
```

## Audit Trail

Tenant information is included in audit logs:

```python
{
    "id": "aud-123",
    "tenant_id": "acme-corp",
    "user_id": "user-123",
    "tool_name": "query",
    "model": "Order",
    "scopes_injected": ["tenant_id = 'acme-corp'"],
    ...
}
```

Query audit logs by tenant:

```python
records = await audit_store.query(
    filters={"tenant_id": "acme-corp"},
)
```

## Best Practices

1. **Always scope sensitive models** - Any model with user data should have tenant scoping

2. **Use immutable tenant_id** - Prevent updates to tenant_id after creation

3. **Auto-set tenant on create** - Use `auto_set` to ensure tenant is always set correctly

4. **Audit cross-tenant access** - Log and monitor any admin/system access

5. **Test isolation thoroughly** - Include tenant isolation in your test suite

6. **Use row policies for complex rules** - When simple scoping isn't enough

## Common Patterns

### Shared Resources

For resources shared across tenants:

```python
ModelPolicy(
    scoping={},  # No tenant scoping
    row_policies=[
        RowPolicy(
            name="public_or_owned",
            condition="is_public = true OR tenant_id = principal.tenant_id",
        ),
    ],
)
```

### Tenant Metadata Access

Allow read-only access to own tenant info:

```python
"Tenant": ModelPolicy(
    allowed=True,
    fields={
        "id": FieldPolicy(action=FieldAction.Allow),
        "name": FieldPolicy(action=FieldAction.Allow),
    },
    scoping={"id": "principal.tenant_id"},  # Can only see own tenant
    write_policy=WritePolicy(
        create=WriteAction.Deny,
        update=WriteAction.Deny,
        delete=WriteAction.Deny,
    ),
)
```

## Next Steps

- [Write Operations](write-operations.md) - Secure write handling
- [Evaluation & Testing](evaluation.md) - Testing tenant isolation
- [Audit Logging](../concepts/audit-logging.md) - Monitoring access
