# OrmAI Quickstart Guide

This guide shows how to get started with OrmAI in common scenarios.

## Installation

```bash
# With uv (recommended)
uv add ormai

# Or with pip
pip install ormai
```

---

## 1. Basic SQLAlchemy Setup (5 minutes)

The fastest way to expose your SQLAlchemy models as safe agent tools.

```python
from sqlalchemy import create_engine, Column, Integer, String, ForeignKey
from sqlalchemy.orm import declarative_base, sessionmaker, relationship

from ormai.quickstart import mount_sqlalchemy
from ormai.utils import PolicyBuilder, DEFAULT_DEV

# Your existing models
Base = declarative_base()

class Customer(Base):
    __tablename__ = "customers"
    id = Column(Integer, primary_key=True)
    name = Column(String(100))
    email = Column(String(100))
    tenant_id = Column(String(50))  # For multi-tenancy

class Order(Base):
    __tablename__ = "orders"
    id = Column(Integer, primary_key=True)
    customer_id = Column(Integer, ForeignKey("customers.id"))
    total = Column(Integer)
    customer = relationship("Customer", backref="orders")

# Create engine and session
engine = create_engine("sqlite:///./app.db")
Session = sessionmaker(bind=engine)

# Mount with one line!
toolset = mount_sqlalchemy(
    engine=engine,
    session_factory=Session,
    policy=DEFAULT_DEV,
)

# Now you have tools: db.describe_schema, db.query, db.get, db.aggregate
print([t.name for t in toolset.tools.values()])
```

---

## 2. Production-Safe Policy

For production, you want tenant isolation and field restrictions.

```python
from ormai.utils import PolicyBuilder
from ormai.policy import FieldAction

policy = (
    PolicyBuilder()
    # Allow these models
    .allow_models(["Customer", "Order", "Product"])

    # Tenant isolation - all queries scoped by tenant_id
    .scope_by_tenant("tenant_id")

    # Restrict sensitive fields
    .deny_fields("Customer", ["ssn", "password_hash"])
    .mask_field("Customer", "email", strategy="partial")

    # Budget limits
    .max_rows(100)
    .max_complexity(500)

    # Build the policy
    .build()
)

toolset = mount_sqlalchemy(
    engine=engine,
    session_factory=Session,
    policy=policy,
)
```

---

## 3. Write Operations with Approval

Enable safe write operations with approval workflows.

```python
from ormai.utils import PolicyBuilder, CallbackApprovalGate

# Define approval callback
async def require_human_approval(request):
    # In production: send to Slack, email, or approval UI
    print(f"Approval needed: {request.operation} on {request.model}")
    return True  # Auto-approve for demo

policy = (
    PolicyBuilder()
    .allow_models(["Customer", "Order"])
    .scope_by_tenant("tenant_id")

    # Enable writes with restrictions
    .enable_writes()
    .allow_create("Order")  # Can create orders
    .allow_update("Order", max_affected=1)  # Update one at a time
    .require_reason("Order")  # Must provide reason for changes

    # Dangerous operations need approval
    .require_approval("Customer", operations=["update", "delete"])

    .build()
)

# Set up approval gate
approval_gate = CallbackApprovalGate(require_human_approval)

toolset = mount_sqlalchemy(
    engine=engine,
    session_factory=Session,
    policy=policy,
    approval_gate=approval_gate,
)
```

---

## 4. Claude Desktop Integration

Expose your database to Claude Desktop.

```python
from ormai.mcp import McpTemplates, install_claude_desktop

# Generate config for Claude Desktop
config = McpTemplates.readonly(
    database_url="postgresql://user:pass@localhost/mydb",
    name="my-app-db",
)

# Install to Claude Desktop
path = install_claude_desktop(config)
print(f"Config installed to: {path}")
# Restart Claude Desktop to use!
```

For development with writes enabled:

```python
config = McpTemplates.development(
    database_url="sqlite:///./dev.db",
)
install_claude_desktop(config)
```

---

## 5. Audit Logging

Track all agent operations for compliance.

```python
from ormai.store import PeeweeAuditStore
from peewee import SqliteDatabase

# Create audit store
audit_db = SqliteDatabase("audit.db")
audit_store = PeeweeAuditStore.create(audit_db)

toolset = mount_sqlalchemy(
    engine=engine,
    session_factory=Session,
    policy=policy,
    audit_store=audit_store,
)

# Every query/mutation is now logged!
# Query audit records:
records = audit_store.query_sync(
    tenant_id="acme-corp",
    tool_name="db.query",
    limit=10,
)
for r in records:
    print(f"{r.timestamp}: {r.tool_name} by {r.principal_id}")
```

---

## 6. Query Cost Estimation

Prevent expensive queries before they run.

```python
from ormai.policy import QueryCostEstimator, TableStats, CostBudget

# Define table statistics
stats = {
    "Customer": TableStats(
        table_name="Customer",
        estimated_row_count=100_000,
        indexed_columns=["id", "email", "tenant_id"],
    ),
    "Order": TableStats(
        table_name="Order",
        estimated_row_count=1_000_000,
        indexed_columns=["id", "customer_id", "created_at"],
    ),
}

# Create estimator
estimator = QueryCostEstimator(table_stats=stats)

# Estimate a query
from ormai.core.dsl import QueryRequest, FilterClause

request = QueryRequest(
    model="Order",
    select=["id", "total", "created_at"],
    where=[FilterClause(field="customer_id", op="eq", value=123)],
    take=100,
)

breakdown = estimator.estimate(request)
print(f"Estimated cost: {breakdown.total}")
print(f"  Scan: {breakdown.scan_cost}")
print(f"  Filter: {breakdown.filter_cost}")

# Set cost budget
budget = CostBudget(
    max_total_cost=500,
    max_join_cost=100,
)
exceeded = budget.check(breakdown)
if exceeded:
    print(f"Query too expensive: {exceeded}")
```

---

## 7. Custom Error Messages

Localize and customize error messages for your users.

```python
from ormai.utils import (
    ToolsetFactory,
    LocalizedErrorPlugin,
    MetricsPlugin,
)

# Custom error messages
messages = {
    "MODEL_NOT_ALLOWED": "You cannot access {model} data",
    "FIELD_NOT_ALLOWED": "The {field} field is restricted",
    "QUERY_BUDGET_EXCEEDED": "Your query is too large. Please add filters.",
}

# Create plugins
localized = LocalizedErrorPlugin(messages=messages)
metrics = MetricsPlugin()

# Use in factory
factory = ToolsetFactory(
    adapter=adapter,
    policy=policy,
    schema=schema,
    plugins=[localized, metrics],
)

toolset = factory.create()

# Later: check error metrics
print(metrics.get_counts())
# {'MODEL_NOT_ALLOWED': 5, 'FIELD_NOT_ALLOWED': 2}
```

---

## 8. Testing Your Setup

OrmAI provides testing utilities for verifying your policies.

```python
import pytest
from ormai.utils.testing import (
    create_test_harness,
    make_context,
    assert_no_leaks,
)

def test_tenant_isolation():
    """Verify tenant data is isolated."""
    harness = create_test_harness(
        adapter=adapter,
        policy=policy,
    )

    # Create context for tenant A
    ctx_a = make_context(tenant_id="tenant-a", user_id="user-1")

    # Query should only return tenant-a data
    result = harness.query(
        model="Customer",
        ctx=ctx_a,
    )

    # Verify no data leaked from other tenants
    assert_no_leaks(result, tenant_id="tenant-a")

def test_field_redaction():
    """Verify sensitive fields are redacted."""
    harness = create_test_harness(
        adapter=adapter,
        policy=policy,
    )

    ctx = make_context(tenant_id="test", user_id="user")
    result = harness.query(model="Customer", ctx=ctx)

    # SSN should be redacted
    for row in result.data:
        assert "ssn" not in row or row["ssn"] == "[REDACTED]"
```

---

## Next Steps

- Read the [Specification](./specification.md) for full API details
- Check [Utilities Pack](./utilities-pack.md) for helper functions
- See the [Roadmap](./roadmap.md) for upcoming features

## Examples

Full working examples are available in the `examples/` directory:

- `examples/fastapi-sqlalchemy/` - FastAPI with SQLAlchemy
- More examples coming soon!
