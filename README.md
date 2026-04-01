# OrmAI

[![PyPI Version](https://img.shields.io/pypi/v/ormai)](https://pypi.org/project/ormai/)
[![Python Versions](https://img.shields.io/pypi/pyversions/ormai)](https://pypi.org/project/ormai/)
[![MIT License](https://img.shields.io/pypi/l/ormai)](https://github.com/neul-labs/ormai/blob/main/LICENSE)
[![Tests](https://img.shields.io/github/actions/workflow/status/neul-labs/ormai/test.yml?label=tests)](https://github.com/neul-labs/ormai/actions)

OrmAI is an ORM-native capability runtime that turns existing SQLAlchemy, Tortoise, and Peewee models into a safe, typed, auditable tool surface for agents. It layers policy-compiled data access, tenant isolation, and audit logging on top of your current application without exposing direct ORM handles to the LLM.

## Table of Contents

- [Quick Start](#quick-start)
- [Installation](#installation)
- [Core API Reference](#core-api-reference)
- [Policy Configuration](#policy-configuration)
- [Tool Reference](#tool-reference)
- [Architecture](#architecture)
- [Examples](#examples)
- [Contributing](#contributing)
- [Resources](#resources)

## Quick Start

```python
from sqlalchemy import create_engine, Column, Integer, String, ForeignKey
from sqlalchemy.orm import declarative_base, sessionmaker, relationship

from ormai.quickstart import mount_sqlalchemy
from ormai.utils import DEFAULT_DEV

# Your existing models
Base = declarative_base()

class Customer(Base):
    __tablename__ = "customers"
    id = Column(Integer, primary_key=True)
    name = Column(String(100))
    email = Column(String(100))

class Order(Base):
    __tablename__ = "orders"
    id = Column(Integer, primary_key=True)
    customer_id = Column(Integer, ForeignKey("customers.id"))
    total = Column(Integer)
    customer = relationship("Customer", backref="orders")

# Create engine and session
engine = create_engine("sqlite:///./app.db")
Session = sessionmaker(bind=engine)

# Mount with one line - get safe tools for agents!
toolset = mount_sqlalchemy(
    engine=engine,
    session_factory=Session,
    policy=DEFAULT_DEV,
)

# Available tools: db.describe_schema, db.query, db.get, db.aggregate
print([t.name for t in toolset.tools.values()])
# ['db.describe_schema', 'db.query', 'db.get', 'db.aggregate']
```

## Installation

OrmAI uses [uv](https://docs.astral.sh/uv/) as its package manager.

```bash
# Install uv if you haven't already
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install OrmAI
uv add ormai

# With specific adapter extras
uv add ormai[sqlalchemy]    # SQLAlchemy support
uv add ormai[tortoise]      # Tortoise ORM support
uv add ormai[peewee]        # Peewee support
uv add ormai[all]           # All adapters
```

For development:

```bash
git clone https://github.com/neul-labs/ormai.git
cd ormai
uv sync --dev
```

## Core API Reference

### mount_sqlalchemy / mount_tortoise / mount_peewee

```python
from ormai.quickstart import mount_sqlalchemy, mount_tortoise, mount_peewee

toolset = mount_sqlalchemy(
    engine: Engine,
    session_factory: SessionFactory,
    policy: Policy,
    schema: SchemaMetadata | None = None,
    audit_store: AuditStore | None = None,
    approval_gate: ApprovalGate | None = None,
    plugins: list[ErrorPlugin] | None = None,
)
```

One-line setup returning a `ToolRegistry` with all configured tools.

### ToolsetFactory

```python
from ormai.utils import ToolsetFactory

# Create toolset from policy
toolset = ToolsetFactory.from_policy(
    policy: Policy,
    adapter: OrmAdapter,
    schema: SchemaMetadata | None = None,
    plugins: list[ErrorPlugin] | None = None,
) -> ToolRegistry
```

Factory for creating tool registries from policy configuration.

### RunContext & Principal

```python
from ormai.core.context import RunContext, Principal

# Agent context for queries
context = RunContext(
    principal=Principal(id="agent-1", roles=["admin"]),
    tenant_id="acme-corp",
    trace_id="req-123",
)

# All tool calls automatically scoped
result = toolset.execute("db.query", {...}, context=context)
```

## Policy Configuration

### PolicyBuilder

Fluent builder for constructing policies with sensible defaults.

```python
from ormai.utils import PolicyBuilder, DEFAULT_PROD

policy = (
    PolicyBuilder(DEFAULT_PROD)
    .register_models([Customer, Order])
    .deny_fields("*password*", "*secret*", "*token*")
    .mask_fields(["email", "phone"])
    .allow_relations({"Order": ["customer"]})
    .tenant_scope("tenant_id")
    .enable_writes(
        models=["Order"],
        allow_create=True,
        allow_update=True,
        require_reason=True,
    )
    .build()
)
```

### Key Builder Methods

| Method | Description |
|--------|-------------|
| `.register_models(models)` | Register accessible models |
| `.deny_fields(*patterns)` | Hide fields completely (glob patterns) |
| `.mask_fields(fields)` | Partially redact sensitive fields |
| `.tenant_scope(field)` | Auto-filter all queries by tenant |
| `.allow_relations(relations)` | Configure allowed relations |
| `.enable_writes(...)` | Enable create/update/delete with restrictions |
| `.require_approval(models)` | Require human approval for writes |

### Defaults Profiles

```python
from ormai.utils import DEFAULT_DEV, DEFAULT_INTERNAL, DEFAULT_PROD

# DEV - permissive, for development
DEFAULT_DEV

# INTERNAL - moderate restrictions, for internal tools
DEFAULT_INTERNAL

# PROD - strict security, for production
DEFAULT_PROD
```

## Tool Reference

### Generic Tools (auto-generated)

| Tool | Description |
|------|-------------|
| `db.describe_schema` | Return allowlisted schema metadata |
| `db.query` | Structured queries with select/where/order/pagination |
| `db.get` | Fetch single record by ID |
| `db.aggregate` | Safe aggregations (count/sum/min/max) |
| `db.create` | Create new records (requires writes enabled) |
| `db.update` | Update records by ID (requires writes enabled) |
| `db.delete` | Delete records (requires writes enabled) |
| `db.bulk_update_by_ids` | Bulk updates (requires writes enabled) |

### Error Types

```python
from ormai import (
    OrmAIError,
    ModelNotAllowedError,
    FieldNotAllowedError,
    TenantScopeRequiredError,
    QueryTooBroadError,
    QueryBudgetExceededError,
    ValidationError,
)
```

## Architecture

| Module | Responsibility |
|--------|----------------|
| `ormai.core` | Tool runtime, execution context, DSL schemas, errors |
| `ormai.adapters` | SQLAlchemy, Tortoise, Peewee backends |
| `ormai.policy` | Resource/field/row policies, budgeting, redaction |
| `ormai.store` | Audit log storage, sanitization |
| `ormai.mcp` | MCP server glue, auth/context translation |
| `ormai.utils` | Builders, factories, plugins, testing utilities |

## Examples

Full working examples are available in the `examples/` directory:

- `examples/fastapi-sqlalchemy/` - FastAPI with SQLAlchemy and agent integration

See [docs/quickstart.md](./docs/quickstart.md) for detailed guides on:
- Production-safe policy configuration
- Write operations with approval workflows
- Claude Desktop integration
- Audit logging
- Query cost estimation

## Contributing

```bash
# Set up development environment
git clone https://github.com/neul-labs/ormai.git
cd ormai
uv sync --dev

# Run tests
uv run pytest

# Run type checking
uv run mypy src/

# Run linting
uv run ruff check src/
```

### Development Notes

- Python 3.10+ required
- All adapters tested with SQLite for CI
- Run `uv run pytest` before submitting PRs
- Follow existing code patterns and docstring styles

## Resources

- [Quickstart Guide](./docs/quickstart.md) - Getting started examples
- [Specification](./docs/specification.md) - Full API details
- [Utilities Pack](./docs/utilities-pack.md) - Helper functions reference
- [Roadmap](./docs/roadmap.md) - Upcoming features
- [TypeScript Edition Spec](./docs/ormai-ts-specification.md) - Node.js roadmap

---

<div align="center">

**OrmAI: Safe, typed, auditable database access for AI agents**

</div>
