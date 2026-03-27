# Policies

Policies are the core of OrmAI's security model. They define what agents can access and how data is protected.

## Policy Structure

A complete policy includes model policies, budgets, and optional defaults:

```python
from ormai.policy import (
    Policy,
    ModelPolicy,
    FieldPolicy,
    FieldAction,
    Budget,
    WritePolicy,
)

policy = Policy(
    models={
        "User": ModelPolicy(...),
        "Order": ModelPolicy(...),
    },
    budget=Budget(
        max_rows=1000,
        max_include_depth=3,
        statement_timeout_ms=5000,
    ),
    default_field_action=FieldAction.Deny,
)
```

## Model Policies

Model policies control access to specific database models:

```python
ModelPolicy(
    allowed=True,                    # Enable access to this model
    fields={...},                    # Field-level policies
    relations={...},                 # Relation policies
    scoping={"tenant_id": "principal.tenant_id"},  # Auto-scoping
    row_policies=[...],              # Row-level security
    write_policy=WritePolicy(...),   # Write operation rules
)
```

### Disabling a Model

```python
ModelPolicy(allowed=False)  # Blocks all access
```

## Field Policies

Field policies control access to individual fields:

```python
from ormai.policy import FieldPolicy, FieldAction

fields = {
    "id": FieldPolicy(action=FieldAction.Allow),
    "email": FieldPolicy(action=FieldAction.Mask),
    "ssn": FieldPolicy(action=FieldAction.Hash),
    "password_hash": FieldPolicy(action=FieldAction.Deny),
    "notes": FieldPolicy(action=FieldAction.Redact),
}
```

### Field Actions

| Action | Description | Output Example |
|--------|-------------|----------------|
| `Allow` | Field is returned as-is | `user@example.com` |
| `Deny` | Field is completely hidden | *(not in response)* |
| `Mask` | Partially obscured | `u***@***.com` |
| `Hash` | Deterministic hash | `a1b2c3d4...` |
| `Redact` | Replaced with placeholder | `[REDACTED]` |

### Custom Masking

```python
FieldPolicy(
    action=FieldAction.Mask,
    mask_pattern="***-**-{last4}",  # For SSN: ***-**-1234
)
```

## Scoping Rules

Scoping automatically filters queries to the current principal's context:

```python
ModelPolicy(
    scoping={
        "tenant_id": "principal.tenant_id",  # Tenant isolation
        "owner_id": "principal.user_id",     # User-level access
    }
)
```

### How Scoping Works

When a query is executed:

```python
# Original query
toolset.query(ctx, model="Order", filters=[...])

# After scope injection
SELECT * FROM orders
WHERE tenant_id = 'acme-corp'  -- Injected from principal
AND <user filters>
```

### Scoping Expressions

| Expression | Resolves To |
|------------|-------------|
| `principal.tenant_id` | `ctx.principal.tenant_id` |
| `principal.user_id` | `ctx.principal.user_id` |
| `principal.roles` | `ctx.principal.roles` |

## Row-Level Policies

For complex access control beyond simple scoping:

```python
from ormai.policy import RowPolicy

ModelPolicy(
    row_policies=[
        RowPolicy(
            name="draft_visibility",
            condition="status != 'draft' OR owner_id = principal.user_id",
            description="Users can only see their own drafts",
        ),
        RowPolicy(
            name="admin_access",
            condition="'admin' IN principal.roles",
            bypass=True,  # Admins bypass other row policies
        ),
    ]
)
```

## Relation Policies

Control access to related data:

```python
from ormai.policy import RelationPolicy

ModelPolicy(
    relations={
        "orders": RelationPolicy(
            allowed=True,
            max_depth=2,
            fields=["id", "status", "total"],  # Limit included fields
        ),
        "audit_logs": RelationPolicy(allowed=False),  # Block relation
    }
)
```

## Write Policies

Control create, update, and delete operations:

```python
from ormai.policy import WritePolicy, WriteAction

ModelPolicy(
    write_policy=WritePolicy(
        create=WriteAction.Allow,
        update=WriteAction.RequireApproval,  # Human approval needed
        delete=WriteAction.Deny,

        # Field-level write control
        immutable_fields=["id", "created_at", "tenant_id"],
        required_fields=["name", "email"],

        # Auto-populate fields
        auto_set={
            "tenant_id": "principal.tenant_id",
            "created_by": "principal.user_id",
        },
    )
)
```

### Write Actions

| Action | Description |
|--------|-------------|
| `Allow` | Operation is allowed |
| `Deny` | Operation is blocked |
| `RequireApproval` | Operation requires human approval |

## Budgets

Budgets prevent expensive operations:

```python
Budget(
    max_rows=1000,           # Maximum rows per query
    max_include_depth=3,     # Maximum relation nesting
    max_selected_fields=50,  # Maximum fields per query
    statement_timeout_ms=5000,  # Query timeout
    max_complexity_score=100,   # Computed query complexity
)
```

### Complexity Scoring

OrmAI computes a complexity score for each query:

```python
# Factors that increase complexity:
# - Number of filters
# - Include depth
# - Number of selected fields
# - Aggregations
# - Ordering

query = {
    "model": "Order",
    "filters": [...],      # +2 per filter
    "include": [           # +5 per include level
        {"relation": "items", "include": [...]},
    ],
    "order": [...],        # +1 per order clause
}
```

## Policy Builder

For fluent policy construction:

```python
from ormai.utils import PolicyBuilder

policy = (
    PolicyBuilder()
    .add_model("User")
        .allow_fields("id", "name", "email")
        .mask_field("email")
        .scope_by_tenant()
        .done()
    .add_model("Order")
        .allow_fields("id", "status", "total", "created_at")
        .allow_writes(create=True, update=True, delete=False)
        .scope_by_tenant()
        .done()
    .set_budget(max_rows=500, max_include_depth=2)
    .build()
)
```

## Default Profiles

Use preset profiles for common scenarios:

```python
from ormai.utils import DefaultsProfile

# Production: Strict defaults
policy = DefaultsProfile.DEFAULT_PROD.apply(base_policy)

# Internal tools: Relaxed defaults
policy = DefaultsProfile.DEFAULT_INTERNAL.apply(base_policy)

# Development: Permissive defaults
policy = DefaultsProfile.DEFAULT_DEV.apply(base_policy)
```

## Policy Validation

Validate policies at startup:

```python
from ormai.policy import validate_policy

errors = validate_policy(policy, schema_metadata)

for error in errors:
    print(f"Policy error: {error}")
```

Common validation errors:

- Unknown model in policy
- Unknown field in field policy
- Invalid scoping expression
- Circular relation policies

## Next Steps

- [Adapters](adapters.md) - How policies are applied by adapters
- [Tools](tools.md) - Tools that use policies
- [Audit Logging](audit-logging.md) - Policy decisions in audit logs
