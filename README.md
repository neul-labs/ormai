# OrmAI

[![PyPI Version](https://img.shields.io/pypi/v/ormai)](https://pypi.org/project/ormai/)
[![Python Versions](https://img.shields.io/pypi/pyversions/ormai)](https://pypi.org/project/ormai/)
[![MIT License](https://img.shields.io/pypi/l/ormai)](https://github.com/neul-labs/ormai/blob/main/LICENSE)
[![Tests](https://img.shields.io/github/actions/workflow/status/neul-labs/ormai/test.yml?label=tests)](https://github.com/neul-labs/ormai/actions)

OrmAI is an ORM-native capability runtime that turns existing SQLAlchemy, Tortoise, and Peewee models into a safe, typed, auditable tool surface for agents. It layers policy-compiled data access, tenant isolation, and audit logging on top of your current application without exposing direct ORM handles to the LLM.

## Table of Contents

- [Quick Start](#quick-start)
- [Installation](#installation)
- [Production Configuration](#production-configuration)
- [Core API Reference](#core-api-reference)
- [Policy Configuration](#policy-configuration)
- [Tool Reference](#tool-reference)
- [Architecture](#architecture)
- [Benchmark Demo](#benchmark-demo)
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

## Production Configuration

OrmAI includes production-ready features for secure deployment. Key configuration areas:

### Environment Detection

OrmAI uses the `ORMAI_ENV` environment variable to determine runtime behavior:

```bash
# Production (default) - requires authentication
export ORMAI_ENV=production

# Development - allows anonymous access with warnings
export ORMAI_ENV=development
```

### Security Checklist

Before deploying to production:

- [ ] Set `ORMAI_ENV=production` (enforces authentication)
- [ ] Configure authentication function for MCP server
- [ ] Use `DEFAULT_PROD` or stricter policy profile
- [ ] Enable HTTPS/TLS for all endpoints
- [ ] Configure audit log retention policy
- [ ] Set up structured logging for observability
- [ ] Enable rate limiting to prevent abuse

### Rate Limiting

```python
from ormai.middleware import RateLimiter, RateLimitConfig

limiter = RateLimiter(
    config=RateLimitConfig(
        requests_per_minute=60,
        requests_per_hour=1000,
        burst_limit=10,
    )
)
```

### Health Checks

```python
from ormai.health import HealthChecker, check_database, check_audit_store

checker = HealthChecker(version="0.2.0")
checker.add_check("database", lambda: check_database(adapter))
checker.add_check("audit", lambda: check_audit_store(store))

# Get health status
health = await checker.check_all()
```

### Structured Logging

```python
from ormai.logging import configure_logging, LogFormat, LogLevel

# Production: JSON logs for log aggregation
configure_logging(level=LogLevel.INFO, format=LogFormat.JSON)

# Development: Colorized text logs
configure_logging(level=LogLevel.DEBUG, format=LogFormat.TEXT)
```

### Audit Log Retention

```python
from ormai.store import RetentionPolicy, RetentionManager

policy = RetentionPolicy.days(90)  # Keep logs for 90 days
manager = RetentionManager(store=audit_store, policy=policy)

# Run cleanup once
await manager.run_cleanup()

# Or schedule periodic cleanup
await manager.start_scheduler()
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

## Benchmark Demo

OrmAI includes a benchmark demo comparing OrmAI's tool-based approach against raw text-to-SQL using the [Spider dataset](https://yale-lily.github.io/spider). The demo showcases OrmAI's safety advantages with a rich split-screen CLI.

### Why OrmAI vs Text-to-SQL?

| Aspect | OrmAI | Text-to-SQL |
|--------|-------|-------------|
| **SQL Injection** | Impossible (parameterized) | Possible |
| **Policy Enforcement** | Built-in | None |
| **Audit Trail** | Complete | None |
| **Unsafe Operations** | Blocked by policy | Executed |

### Running the Demo

```bash
# Install benchmark dependencies
uv add ormai[benchmark]

# Download Spider dataset (first-time setup)
uv run python examples/spider_demo.py download

# Run quick demo (20 questions) - great for presentations
uv run python examples/spider_demo.py run --limit 20

# Run full benchmark with both GPT-4 and Claude
uv run python examples/spider_demo.py run

# Run with single LLM
uv run python examples/spider_demo.py run --llm gpt-4
uv run python examples/spider_demo.py run --llm claude
```

### Demo Output

The demo displays a live split-screen comparison:

```
+--------------------------- Spider Benchmark ---------------------------+
|  Dataset: Spider (dev)  |  Questions: 1034  |  LLMs: GPT-4 + Claude    |
+------------------------------------------------------------------------+
|  +---------- OrmAI ----------+  +---------- Text-to-SQL ----------+    |
|  |  GPT-4      ======== 67%  |  |  GPT-4      ======== 67%       |    |
|  |  Correct: 523  Blocked: 8 |  |  Correct: 498  Unsafe: 23      |    |
|  |                           |  |                                 |    |
|  |  Claude     ======== 67%  |  |  Claude     ======== 67%       |    |
|  |  Correct: 531  Blocked: 6 |  |  Correct: 512  Unsafe: 19      |    |
|  +---------------------------+  +---------------------------------+    |
+------------------------------------------------------------------------+
```

**Requirements**: Set `OPENAI_API_KEY` and/or `ANTHROPIC_API_KEY` environment variables.

## Examples

Full working examples are available in the `examples/` directory:

- `examples/spider_demo.py` - Spider benchmark comparing OrmAI vs text-to-SQL
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
