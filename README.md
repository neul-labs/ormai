# OrmAI

[![PyPI Version](https://img.shields.io/pypi/v/ormai)](https://pypi.org/project/ormai/)
[![npm version](https://img.shields.io/npm/v/@ormai/core)](https://www.npmjs.com/package/@ormai/core)
[![Python Versions](https://img.shields.io/pypi/pyversions/ormai)](https://pypi.org/project/ormai/)
[![MIT License](https://img.shields.io/pypi/l/ormai)](https://github.com/neul-labs/ormai/blob/main/LICENSE)
[![CI](https://img.shields.io/github/actions/workflow/status/neul-labs/ormai/ci.yml?label=tests)](https://github.com/neul-labs/ormai/actions)

**Give your AI agents database access without the risk.**

OrmAI wraps your existing ORM models in a policy-enforced runtime. Your agents get typed tools for querying and writing data — while you keep control over what they can see and do. No raw SQL. No prompt injection into your database. Just safe, auditable, tenant-scoped database tools.

**Available for Python and TypeScript/Node.js.**

**[Website](https://ormai.neullabs.com)** · **[Documentation](https://docs.neullabs.com/ormai)** · **[GitHub](https://github.com/neul-labs/ormai)**

---

## Why OrmAI?

Building AI agents that interact with your database? You have probably thought about:

- **"What if the agent reads sensitive data?"** → Field-level policies hide or mask PII automatically.
- **"What if it runs wild queries?"** → Query budgets and row limits prevent runaway costs.
- **"How do I audit what it did?"** → Every operation is logged with full context.
- **"What about multi-tenant isolation?"** → Tenant scoping is built-in, not bolted on.
- **"Which ORM do we use?"** → Works with SQLAlchemy, Prisma, Drizzle, TypeORM, Tortoise, Django, SQLModel, and Peewee.

OrmAI solves these at the ORM layer — not the prompt layer.

---

## Pick Your Stack

| | **Python** | **TypeScript / Node.js** |
|---|---|---|
| **Package** | `pip install ormai` | `npm install @ormai/core` |
| **ORMs** | SQLAlchemy, Tortoise, Django, SQLModel, Peewee | Prisma, Drizzle, TypeORM |
| **Integrations** | OpenAI, LangChain, LlamaIndex, MCP, FastAPI | Vercel AI SDK, LangChain.js, OpenAI, Anthropic, LlamaIndex.ts, Mastra, MCP |
| **Quickstart** | [`ormai.quickstart`](https://docs.neullabs.com/ormai) | [`@ormai/utils`](https://docs.neullabs.com/ormai) |
| **Docs** | [Python Guide](https://docs.neullabs.com/ormai/python) | [TS Guide](https://docs.neullabs.com/ormai/typescript) |

---

## Python Quick Start

```bash
# With your ORM of choice
pip install ormai[sqlalchemy]
# or
pip install ormai[prisma]
```

```python
from ormai.quickstart import mount_sqlalchemy
from ormai.utils import DEFAULT_DEV

# Your existing SQLAlchemy models + session
toolset = mount_sqlalchemy(
    engine=engine,
    session_factory=Session,
    policy=DEFAULT_DEV
)

# Done. Your agent now has: db.query, db.get, db.aggregate, db.describe_schema
```

## TypeScript Quick Start

```bash
# Core (required)
npm install @ormai/core

# Choose your ORM adapter
npm install @ormai/prisma
```

```typescript
import { PrismaClient } from '@prisma/client';
import { PrismaAdapter } from '@ormai/prisma';
import { PolicyBuilder, createContext } from '@ormai/core';
import { createGenericTools } from '@ormai/tools';

const prisma = new PrismaClient();
const adapter = new PrismaAdapter({ prisma });
const schema = await adapter.introspect();

const policy = new PolicyBuilder('prod')
  .registerModels(['Customer', 'Order'])
  .tenantScope('tenantId')
  .denyFields('*password*')
  .maskFields('*email*')
  .build();

const tools = createGenericTools({ adapter, policy, schema });

const ctx = createContext({
  tenantId: 'tenant-123',
  userId: 'user-456',
  db: prisma,
  roles: ['admin'],
});

// Your agent now has safe database tools
const result = await tools[0].execute({
  model: 'Order',
  where: [{ field: 'status', op: 'eq', value: 'pending' }],
  take: 10,
}, ctx);
```

---

## What You Get Out of the Box

| Feature | What It Does |
|---------|-------------|
| **Read-safe tools** | `db.query`, `db.get`, `db.aggregate`, `db.describe_schema` — no raw SQL |
| **Write-safe tools** | `db.create`, `db.update`, `db.delete`, `db.bulk_update` — gated by policy |
| **Field-level policies** | Hide passwords, mask emails, deny sensitive columns automatically |
| **Tenant scoping** | `.tenantScope('tenant_id')` auto-filters every query per user |
| **Query budgets** | Max rows, max includes depth, statement timeouts per model |
| **Audit logging** | Every call logged with principal, tenant, trace ID, input, output |
| **Human approval gates** | Require reason or approval for writes on sensitive models |
| **Schema introspection** | Auto-discovers models, fields, relations, primary keys |
| **Multi-framework** | LangChain, OpenAI, Vercel AI SDK, LlamaIndex, Mastra, FastAPI, MCP |

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        Your Agent                           │
└──────────────────────────┬──────────────────────────────────┘
                           │ calls tools
┌──────────────────────────▼──────────────────────────────────┐
│                    OrmAI Runtime                            │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐│
│  │   Policy    │  │   Audit     │  │    Tenant Scope     ││
│  │  Enforcer   │  │   Logger    │  │      Filter         ││
│  └─────────────┘  └─────────────┘  └─────────────────────┘│
└──────────────────────────┬──────────────────────────────────┘
                           │ parameterized queries only
┌──────────────────────────▼──────────────────────────────────┐
│          Your ORM (SQLAlchemy / Prisma / Drizzle / ...)   │
└─────────────────────────────────────────────────────────────┘
```

OrmAI sits between your agent and your ORM. It compiles agent requests into type-safe ORM queries, enforces policies, logs everything, and returns structured results. Your database never sees raw SQL from the agent.

---

## Documentation

**[docs.neullabs.com/ormai](https://docs.neullabs.com/ormai)** — Full guides, API reference, and examples.

- [Getting Started](https://docs.neullabs.com/ormai/getting-started)
- [Policy Configuration](https://docs.neullabs.com/ormai/policies)
- [Production Checklist](https://docs.neullabs.com/ormai/production)
- [API Reference](https://docs.neullabs.com/ormai/api)

---

## Installation

### Python

```bash
pip install ormai[sqlalchemy]
pip install ormai[tortoise]
pip install ormai[peewee]
pip install ormai[django]
pip install ormai[sqlmodel]

# Or all adapters
pip install ormai[all]
```

### TypeScript / Node.js

```bash
# Core (required)
npm install @ormai/core

# ORM adapters
npm install @ormai/prisma
npm install @ormai/drizzle
npm install @ormai/typeorm

# Optional packages
npm install @ormai/tools     # Generic database tools
npm install @ormai/store     # Audit logging
npm install @ormai/mcp       # MCP server
npm install @ormai/integrations  # Framework adapters
npm install @ormai/utils     # PolicyBuilder and helpers
```

---

## Policy Configuration

### Python

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

### TypeScript

```typescript
import { PolicyBuilder } from '@ormai/core';

const policy = new PolicyBuilder('prod')
  .registerModels(['Customer', 'Order', 'Product'])
  .tenantScope('tenantId')
  .denyFields('*password*')
  .maskFields('*email*')
  .allowRelations('Order', ['customer', 'items'])
  .enableWrites(['Order'], {
    allowCreate: true,
    allowUpdate: true,
    allowDelete: false,
    maxAffectedRows: 10,
  })
  .defaultBudgetConfig({
    maxRows: 100,
    maxIncludesDepth: 2,
    statementTimeoutMs: 5000,
  })
  .build();
```

**Presets:** `DEFAULT_DEV` (permissive), `DEFAULT_INTERNAL` (moderate), `DEFAULT_PROD` (strict)

---

## Agent Framework Integrations

| Framework | Python Package | TypeScript Package |
|-----------|---------------|-------------------|
| OpenAI | `ormai` | `@ormai/integrations` |
| LangChain | `ormai` | `@ormai/integrations` |
| Vercel AI SDK | — | `@ormai/integrations` |
| LlamaIndex | `ormai` | `@ormai/integrations` |
| Mastra | — | `@ormai/integrations` |
| Anthropic | — | `@ormai/integrations` |
| FastAPI | `ormai` | — |
| MCP | `ormai` | `@ormai/mcp` |

---

## Supported ORMs

| ORM | Python | TypeScript |
|-----|--------|------------|
| SQLAlchemy | ✅ | — |
| Prisma | — | ✅ |
| Drizzle | — | ✅ |
| TypeORM | — | ✅ |
| SQLModel | ✅ | — |
| Django ORM | ✅ | — |
| Tortoise ORM | ✅ | — |
| Peewee | ✅ | — |

---

## Benchmark: OrmAI vs Text-to-SQL

We benchmarked against the [Spider dataset](https://yale-lily.github.io/spider) — 1034 natural language queries:

| Metric | OrmAI | Text-to-SQL |
|--------|-------|-------------|
| SQL Injection possible | No | Yes |
| Unsafe ops executed | 0 | 23 |
| Full audit trail | Yes | No |

```bash
# Try it yourself
pip install ormai[benchmark]
python examples/spider_demo.py run --limit 20
```

---

## Examples

- [`examples/spider_demo.py`](./examples/spider_demo.py) — Benchmark demo
- [`examples/fastapi-sqlalchemy/`](./examples/fastapi-sqlalchemy/) — FastAPI + SQLAlchemy integration
- [`ormai-ts/`](./ormai-ts/) — TypeScript monorepo with Prisma, Drizzle, and TypeORM examples

More examples at [docs.neullabs.com/ormai/examples](https://docs.neullabs.com/ormai/examples).

---

## Contributing

```bash
git clone https://github.com/neul-labs/ormai.git
cd ormai

# Python
uv sync --dev
uv run pytest

# TypeScript
cd ormai-ts
npm install
npm run build
npm run test
```

See [contributing guide](https://docs.neullabs.com/ormai/contributing) for development setup and guidelines.

---

<div align="center">

**[Website](https://ormai.neullabs.com)** · **[Documentation](https://docs.neullabs.com/ormai)** · **[GitHub](https://github.com/neul-labs/ormai)** · **[PyPI](https://pypi.org/project/ormai/)** · **[npm](https://www.npmjs.com/package/@ormai/core)**

MIT License · Built by [Neul Labs](https://neullabs.com)

</div>

## Part of the Neul Labs toolchain

Part of the [Neul Labs](https://www.neullabs.com) agent-infrastructure toolchain:

| Project | Description |
| --- | --- |
| [agentvfs](https://agentvfs.neullabs.com) | Workspace runtime and execution boundary for AI agents. |
| [memorg](https://memorg.neullabs.com) | Give your LLM a memory that actually works. |
| [mcp-pay](https://mcp-pay.neullabs.com) | Payment awareness layer for MCP (Model Context Protocol). |
| [closegate](https://closegate.neullabs.com) | The policy chokepoint for finance AI agents. |
| [regulus](https://regulus.neullabs.com) | The EU & UK compliance plane for Google ADK. |
