# Policy API Reference

The policy module provides access control and data protection primitives.

## Policy

Top-level policy container.

```python
from ormai.policy import Policy
```

### Constructor

```python
Policy(
    models: dict[str, ModelPolicy],
    budget: Budget | None = None,
    default_field_action: FieldAction = FieldAction.Deny,
)
```

### Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `models` | `dict[str, ModelPolicy]` | Per-model policies |
| `budget` | `Budget \| None` | Global query budget |
| `default_field_action` | `FieldAction` | Default for unlisted fields |

---

## ModelPolicy

Policy for a single model.

```python
from ormai.policy import ModelPolicy
```

### Constructor

```python
ModelPolicy(
    allowed: bool = True,
    fields: dict[str, FieldPolicy] = {},
    relations: dict[str, RelationPolicy] = {},
    scoping: dict[str, str] = {},
    row_policies: list[RowPolicy] = [],
    write_policy: WritePolicy | None = None,
)
```

### Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `allowed` | `bool` | Whether model is accessible |
| `fields` | `dict[str, FieldPolicy]` | Field-level policies |
| `relations` | `dict[str, RelationPolicy]` | Relation policies |
| `scoping` | `dict[str, str]` | Auto-scoping rules |
| `row_policies` | `list[RowPolicy]` | Row-level security |
| `write_policy` | `WritePolicy \| None` | Write operation rules |

### Example

```python
ModelPolicy(
    allowed=True,
    fields={
        "id": FieldPolicy(action=FieldAction.Allow),
        "email": FieldPolicy(action=FieldAction.Mask),
        "password_hash": FieldPolicy(action=FieldAction.Deny),
    },
    scoping={"tenant_id": "principal.tenant_id"},
    write_policy=WritePolicy(
        create=WriteAction.Allow,
        update=WriteAction.Allow,
        delete=WriteAction.Deny,
    ),
)
```

---

## FieldPolicy

Policy for a single field.

```python
from ormai.policy import FieldPolicy, FieldAction
```

### Constructor

```python
FieldPolicy(
    action: FieldAction,
    mask_pattern: str | None = None,
)
```

### FieldAction Enum

```python
class FieldAction(Enum):
    Allow = "allow"       # Return as-is
    Deny = "deny"         # Exclude from response
    Mask = "mask"         # Partially obscure
    Hash = "hash"         # Deterministic hash
    Redact = "redact"     # Replace with placeholder
```

### Examples

```python
# Allow field
FieldPolicy(action=FieldAction.Allow)

# Mask with default pattern
FieldPolicy(action=FieldAction.Mask)

# Custom mask pattern
FieldPolicy(
    action=FieldAction.Mask,
    mask_pattern="***-**-{last4}",  # SSN format
)

# Hash for consistent anonymization
FieldPolicy(action=FieldAction.Hash)

# Complete redaction
FieldPolicy(action=FieldAction.Redact)
```

---

## RelationPolicy

Policy for a relation.

```python
from ormai.policy import RelationPolicy
```

### Constructor

```python
RelationPolicy(
    allowed: bool = True,
    max_depth: int = 3,
    fields: list[str] | None = None,
)
```

### Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `allowed` | `bool` | Whether relation can be included |
| `max_depth` | `int` | Maximum nesting depth |
| `fields` | `list[str] \| None` | Allowed fields (None = all) |

---

## RowPolicy

Row-level security policy.

```python
from ormai.policy import RowPolicy
```

### Constructor

```python
RowPolicy(
    name: str,
    condition: str,
    description: str | None = None,
    bypass: bool = False,
)
```

### Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `name` | `str` | Policy identifier |
| `condition` | `str` | Filter expression |
| `description` | `str \| None` | Human-readable description |
| `bypass` | `bool` | If true, bypasses other row policies |

### Example

```python
RowPolicy(
    name="own_drafts_only",
    condition="status != 'draft' OR owner_id = principal.user_id",
    description="Users can only see their own draft records",
)
```

---

## WritePolicy

Policy for write operations.

```python
from ormai.policy import WritePolicy, WriteAction
```

### Constructor

```python
WritePolicy(
    create: WriteAction = WriteAction.Deny,
    update: WriteAction = WriteAction.Deny,
    delete: WriteAction = WriteAction.Deny,
    immutable_fields: list[str] = [],
    required_fields: list[str] = [],
    auto_set: dict[str, str] = {},
)
```

### WriteAction Enum

```python
class WriteAction(Enum):
    Allow = "allow"
    Deny = "deny"
    RequireApproval = "require_approval"
```

### Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `create` | `WriteAction` | Create permission |
| `update` | `WriteAction` | Update permission |
| `delete` | `WriteAction` | Delete permission |
| `immutable_fields` | `list[str]` | Fields that cannot be updated |
| `required_fields` | `list[str]` | Required fields for create |
| `auto_set` | `dict[str, str]` | Auto-populated fields |

### Example

```python
WritePolicy(
    create=WriteAction.Allow,
    update=WriteAction.Allow,
    delete=WriteAction.RequireApproval,
    immutable_fields=["id", "created_at", "tenant_id"],
    required_fields=["name", "status"],
    auto_set={
        "tenant_id": "principal.tenant_id",
        "created_by": "principal.user_id",
    },
)
```

---

## Budget

Query budget constraints.

```python
from ormai.policy import Budget
```

### Constructor

```python
Budget(
    max_rows: int = 1000,
    max_include_depth: int = 3,
    max_selected_fields: int = 100,
    statement_timeout_ms: int = 5000,
    max_complexity_score: int = 100,
)
```

### Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `max_rows` | `int` | Maximum rows per query |
| `max_include_depth` | `int` | Maximum relation nesting |
| `max_selected_fields` | `int` | Maximum fields per query |
| `statement_timeout_ms` | `int` | Query timeout in milliseconds |
| `max_complexity_score` | `int` | Maximum complexity score |

---

## PolicyEngine

Evaluates policies against requests.

```python
from ormai.policy import PolicyEngine
```

### Constructor

```python
PolicyEngine(
    policy: Policy,
    schema: SchemaMetadata,
)
```

### Methods

#### validate_query

```python
def validate_query(
    self,
    request: QueryRequest,
    principal: Principal,
) -> list[PolicyViolation]:
```

#### get_allowed_fields

```python
def get_allowed_fields(
    self,
    model: str,
    principal: Principal,
) -> list[str]:
```

#### apply_scoping

```python
def apply_scoping(
    self,
    model: str,
    principal: Principal,
) -> list[FilterClause]:
```

---

## Redactor

Applies field redaction to results.

```python
from ormai.policy import Redactor
```

### Methods

#### redact

```python
def redact(
    self,
    model: str,
    data: dict,
    policy: ModelPolicy,
) -> dict:
```

### Example

```python
redactor = Redactor()

data = {"id": "123", "email": "user@example.com", "ssn": "123-45-6789"}
redacted = redactor.redact("User", data, model_policy)
# {"id": "123", "email": "u***@***.com", "ssn": "***-**-6789"}
```

---

## PolicyBuilder

Fluent API for building policies.

```python
from ormai.utils import PolicyBuilder
```

### Methods

```python
builder = PolicyBuilder()

# Add model
builder.add_model("User")

# Configure fields
builder.allow_fields("id", "name", "email")
builder.deny_fields("password_hash")
builder.mask_field("email")
builder.hash_field("ssn")

# Configure scoping
builder.scope_by_tenant()
builder.scope_by_user()

# Configure writes
builder.allow_writes(create=True, update=True, delete=False)

# Finish model
builder.done()

# Set budget
builder.set_budget(max_rows=500, max_include_depth=2)

# Build policy
policy = builder.build()
```

### Complete Example

```python
policy = (
    PolicyBuilder()
    .add_model("User")
        .allow_fields("id", "name", "email", "created_at")
        .mask_field("email")
        .scope_by_tenant()
        .done()
    .add_model("Order")
        .allow_fields("id", "status", "total", "items")
        .scope_by_tenant()
        .allow_writes(create=True, update=True, delete=False)
        .done()
    .set_budget(max_rows=1000, max_include_depth=3)
    .build()
)
```

---

## ComplexityScorer

Computes query complexity scores.

```python
from ormai.policy import ComplexityScorer
```

### Methods

```python
scorer = ComplexityScorer()

score = scorer.score(request)
# Returns integer complexity score
```

### Scoring Factors

| Factor | Points |
|--------|--------|
| Base query | 1 |
| Per filter | 2 |
| Per include level | 5 |
| Per aggregation | 3 |
| Per order clause | 1 |
| High limit (>100) | 2 |

---

## BudgetEnforcer

Enforces budget constraints.

```python
from ormai.policy import BudgetEnforcer
```

### Methods

```python
enforcer = BudgetEnforcer(budget)

# Check before execution
violations = enforcer.check(request)

# Apply limits
modified_request = enforcer.apply_limits(request)
```
