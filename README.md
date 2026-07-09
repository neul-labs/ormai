# OrmAI

[![PyPI Version](https://img.shields.io/pypi/v/ormai)](https://pypi.org/project/ormai/)
[![Python Versions](https://img.shields.io/pypi/pyversions/ormai)](https://pypi.org/project/ormai/)
[![MIT License](https://img.shields.io/pypi/l/ormai)](https://github.com/neul-labs/ormai/blob/main/LICENSE)
[![Tests](https://img.shields.io/github/actions/workflow/status/neul-labs/ormai/test.yml?label=tests)](https://github.com/neul-labs/ormai/actions)

**Give your AI agents database access without the risk.**

OrmAI wraps your existing ORM models in a policy-enforced runtime. Your agents get typed tools for querying and writing data—while you keep control over what they can see and do.

## Why OrmAI?

Building AI agents that interact with your database? You've probably thought about:

- **"What if the agent reads sensitive data?"** → Field-level policies hide or mask PII automatically
- **"What if it runs wild queries?"** → Query budgets and row limits prevent runaway costs
- **"How do I audit what it did?"** → Every operation is logged with full context
- **"What about multi-tenant isolation?"** → Tenant scoping is built-in, not bolted on

OrmAI solves these at the ORM layer—not the prompt layer. No SQL injection. No prompt hacks. Just safe, typed database tools.

## 30-Second Setup

```bash
uv add ormai[sqlalchemy]
```

```python
from ormai.quickstart import mount_sqlalchemy
from ormai.utils import DEFAULT_DEV

# Your existing SQLAlchemy models + session
toolset = mount_sqlalchemy(engine=engine, session_factory=Session, policy=DEFAULT_DEV)

# Done. Your agent now has: db.query, db.get, db.aggregate, db.describe_schema
```

That's it. Pass `toolset.tools` to your agent framework of choice.

## Quick Wins

| What you want | How OrmAI helps |
|---------------|-----------------|
| **Agent can query, not drop tables** | Tools expose read/write ops, never raw SQL |
| **Hide passwords, tokens, secrets** | `.deny_fields("*password*", "*token*")` |
| **Mask PII in responses** | `.mask_fields(["email", "phone"])` |
| **Scope queries to current tenant** | `.tenant_scope("tenant_id")` auto-filters everything |
| **Know what the agent did** | Every call logged with principal, tenant, trace ID |
| **Human approval for writes** | `.require_approval(["Order"])` gates mutations |

## Supported ORMs

Works with your existing models—no schema changes required:

- **SQLAlchemy** (sync & async)
- **Tortoise ORM**
- **Peewee**
- **Django** (coming soon)

## Documentation

**[docs.neullabs.com/ormai](https://docs.neullabs.com/ormai)** — Full guides, API reference, and examples

- [Getting Started](https://docs.neullabs.com/ormai/getting-started) — Install, configure, integrate
- [Policy Configuration](https://docs.neullabs.com/ormai/policies) — Field rules, tenant scoping, write controls
- [Production Checklist](https://docs.neullabs.com/ormai/production) — Security, rate limiting, observability
- [API Reference](https://docs.neullabs.com/ormai/api) — Full tool and builder reference

---

## Table of Contents

- [Quick Start](#quick-start)
- [Installation](#installation)
- [Policy Configuration](#policy-configuration)
- [Architecture](#architecture)
- [Benchmark Demo](#benchmark-demo)
- [Contributing](#contributing)

## Quick Start

```python
from sqlalchemy import create_engine, Column, Integer, String, ForeignKey
from sqlalchemy.orm import declarative_base, sessionmaker, relationship
from ormai.quickstart import mount_sqlalchemy
from ormai.utils import DEFAULT_DEV

# Your existing models (unchanged)
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

# Mount with one line
engine = create_engine("sqlite:///./app.db")
Session = sessionmaker(bind=engine)

toolset = mount_sqlalchemy(engine=engine, session_factory=Session, policy=DEFAULT_DEV)

# Your agent now has safe database tools
print([t.name for t in toolset.tools.values()])
# ['db.describe_schema', 'db.query', 'db.get', 'db.aggregate']
```

## Installation

```bash
# With your ORM of choice
uv add ormai[sqlalchemy]
uv add ormai[tortoise]
uv add ormai[peewee]

# Or all adapters
uv add ormai[all]
```

See [installation guide](https://docs.neullabs.com/ormai/getting-started#installation) for pip, development setup, and framework integrations.

## Policy Configuration

Start with a preset, customize as needed:

```python
from ormai.utils import PolicyBuilder, DEFAULT_PROD

policy = (
    PolicyBuilder(DEFAULT_PROD)
    .register_models([Customer, Order])
    .deny_fields("*password*", "*secret*", "*token*")
    .mask_fields(["email", "phone"])
    .tenant_scope("tenant_id")
    .enable_writes(models=["Order"], require_reason=True)
    .build()
)
```

**Presets:** `DEFAULT_DEV` (permissive), `DEFAULT_INTERNAL` (moderate), `DEFAULT_PROD` (strict)

See [policy documentation](https://docs.neullabs.com/ormai/policies) for field rules, row limits, approval gates, and advanced patterns.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        Your Agent                           │
└──────────────────────────┬──────────────────────────────────┘
                           │ calls tools
┌──────────────────────────▼──────────────────────────────────┐
│                    OrmAI Runtime                            │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │
│  │   Policy    │  │   Audit     │  │    Tenant Scope     │  │
│  │  Enforcer   │  │   Logger    │  │      Filter         │  │
│  └─────────────┘  └─────────────┘  └─────────────────────┘  │
└──────────────────────────┬──────────────────────────────────┘
                           │ parameterized queries only
┌──────────────────────────▼──────────────────────────────────┐
│               Your ORM (SQLAlchemy / Tortoise / Peewee)     │
└─────────────────────────────────────────────────────────────┘
```

See [architecture guide](https://docs.neullabs.com/ormai/architecture) for module details and extension points.

## Benchmark: OrmAI vs Text-to-SQL

We benchmarked against the [Spider dataset](https://yale-lily.github.io/spider)—1034 natural language queries:

| Metric | OrmAI | Text-to-SQL |
|--------|-------|-------------|
| SQL Injection possible | No | Yes |
| Unsafe ops executed | 0 | 23 |
| Full audit trail | Yes | No |

```bash
# Try it yourself
uv add ormai[benchmark]
uv run python examples/spider_demo.py run --limit 20
```

## Examples

- [`examples/spider_demo.py`](./examples/spider_demo.py) — Benchmark demo
- [`examples/fastapi-sqlalchemy/`](./examples/fastapi-sqlalchemy/) — FastAPI integration

More examples at [docs.neullabs.com/ormai/examples](https://docs.neullabs.com/ormai/examples)

## Contributing

```bash
git clone https://github.com/neul-labs/ormai.git
cd ormai
uv sync --dev
uv run pytest
```

See [contributing guide](https://docs.neullabs.com/ormai/contributing) for development setup and guidelines.

---

<div align="center">

**[Documentation](https://docs.neullabs.com/ormai)** · **[GitHub](https://github.com/neul-labs/ormai)** · **[PyPI](https://pypi.org/project/ormai/)**

MIT License · Built by [Neul Labs](https://neullabs.com)

</div>
