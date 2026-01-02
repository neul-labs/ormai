# OrmAI

**ORM-native capability runtime for AI agents**

OrmAI transforms your existing SQLAlchemy, Tortoise, and Peewee database models into safe, typed, and auditable tool surfaces for AI agents. It provides a policy-compiled execution layer that sits on top of your existing database infrastructure.

## Why OrmAI?

AI agents need database access, but giving them raw ORM handles is dangerous. OrmAI solves this by:

- **Policy-First Access Control**: Define what models, fields, and operations agents can access
- **Automatic Tenant Isolation**: Prevent cross-tenant data leakage with scoping rules
- **Query Budget Enforcement**: Limit query complexity, row counts, and execution time
- **Complete Audit Trail**: Every operation is logged with sanitized inputs and outcomes
- **Type-Safe Tool Interfaces**: Agents interact with curated domain tools or a constrained query DSL

## Key Features

<div class="grid cards" markdown>

-   :material-shield-check:{ .lg .middle } **Policy Engine**

    ---

    Define granular access policies for models, fields, and operations with support for masking, hashing, and redaction.

-   :material-database:{ .lg .middle } **ORM Adapters**

    ---

    Native support for SQLAlchemy, Tortoise, Peewee, Django, and SQLModel with async capabilities.

-   :material-tools:{ .lg .middle } **Built-in Tools**

    ---

    Generic query, get, aggregate, create, update, and delete tools ready for agent consumption.

-   :material-clipboard-text:{ .lg .middle } **Audit Logging**

    ---

    Immutable audit records for every operation with multiple backend options.

</div>

## Quick Example

```python
from ormai.quickstart import mount_sqlalchemy
from ormai.core import Principal, RunContext

# Mount your SQLAlchemy models
toolset = mount_sqlalchemy(
    engine=engine,
    base=Base,
    policy=policy,
)

# Create execution context
ctx = RunContext(
    principal=Principal(tenant_id="acme", user_id="user-123"),
    db=session,
)

# Agents can now safely query your database
result = await toolset.query(
    ctx,
    model="Order",
    filters=[{"field": "status", "op": "eq", "value": "pending"}],
    limit=10,
)
```

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      AI Agent / LLM                         │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    OrmAI Tool Layer                         │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │
│  │ Query Tool  │  │ Write Tools │  │ Domain Tools        │  │
│  └─────────────┘  └─────────────┘  └─────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    Policy Engine                            │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌─────────────┐  │
│  │ Scoping  │  │ Redaction│  │ Budgets  │  │ Complexity  │  │
│  └──────────┘  └──────────┘  └──────────┘  └─────────────┘  │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    ORM Adapters                             │
│  ┌────────────┐  ┌──────────┐  ┌────────┐  ┌─────────────┐  │
│  │ SQLAlchemy │  │ Tortoise │  │ Peewee │  │ Django/etc  │  │
│  └────────────┘  └──────────┘  └────────┘  └─────────────┘  │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                      Database                               │
└─────────────────────────────────────────────────────────────┘
```

## Installation

```bash
pip install ormai
```

For specific ORM support:

```bash
pip install ormai[sqlalchemy]  # SQLAlchemy support
pip install ormai[tortoise]    # Tortoise ORM support
pip install ormai[peewee]      # Peewee support
```

## Next Steps

- [Quick Start Guide](getting-started/quickstart.md) - Get up and running in 5 minutes
- [Core Concepts](concepts/overview.md) - Understand how OrmAI works
- [API Reference](api-reference/core.md) - Detailed API documentation
