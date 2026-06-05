# TypeScript Edition

OrmAI ships as a TypeScript/Node.js monorepo at [`ormai-ts/`](https://github.com/neul-labs/ormai/tree/main/ormai-ts) with first-class support for **Prisma**, **Drizzle**, and **TypeORM**.

## Packages

| Package | Description |
|---|---|
| `@ormai/core` | Core types, policy engine, adapter/tool/store interfaces, DSL schemas |
| `@ormai/prisma` | Prisma ORM adapter |
| `@ormai/drizzle` | Drizzle ORM adapter |
| `@ormai/typeorm` | TypeORM adapter |
| `@ormai/tools` | Generic database tools (query, get, aggregate, create, update, delete) |
| `@ormai/store` | Audit logging stores (in-memory, JSONL) and middleware |
| `@ormai/mcp` | Model Context Protocol server with auth |
| `@ormai/integrations` | Agent framework adapters (Vercel AI, LangChain, OpenAI, Anthropic, LlamaIndex, Mastra) |
| `@ormai/utils` | `PolicyBuilder`, defaults profiles, `quickSetup`, testing helpers |

## Installation

```bash
# Core is always required
npm install @ormai/core

# Pick an ORM adapter
npm install @ormai/prisma        # also: npm install @prisma/client
npm install @ormai/drizzle       # also: npm install drizzle-orm
npm install @ormai/typeorm       # also: npm install typeorm

# Optional
npm install @ormai/tools          # Generic database tools
npm install @ormai/store          # Audit logging
npm install @ormai/mcp            # MCP server
npm install @ormai/integrations   # Agent framework adapters
npm install @ormai/utils          # PolicyBuilder and helpers
```

## Quick Start with Prisma

```typescript
import { PrismaClient } from '@prisma/client';
import { PrismaAdapter } from '@ormai/prisma';
import { PolicyBuilder, createContext } from '@ormai/core';
import { createGenericTools } from '@ormai/tools';

const prisma = new PrismaClient();
const adapter = new PrismaAdapter({ prisma });
const schema = await adapter.introspect();

const policy = new PolicyBuilder('prod')
  .registerModels(['Customer', 'Order', 'Product'])
  .tenantScope('tenantId')
  .denyFields('*password*')
  .maskFields('*email*')
  .enableWrites(['Order'])
  .build();

const tools = createGenericTools({ adapter, policy, schema });

const ctx = createContext({
  tenantId: 'tenant-123',
  userId: 'user-456',
  db: prisma,
  roles: ['admin'],
});

const result = await tools[0].execute({
  model: 'Order',
  where: [{ field: 'status', op: 'eq', value: 'pending' }],
  take: 10,
}, ctx);
```

## Quick Start with Drizzle

```typescript
import { drizzle } from 'drizzle-orm/node-postgres';
import { DrizzleAdapter } from '@ormai/drizzle';
import { PolicyBuilder, createContext } from '@ormai/core';
import { createGenericTools } from '@ormai/tools';
import * as schema from './schema';

const db = drizzle(pool, { schema });
const adapter = new DrizzleAdapter({ db, schema });
const introspected = await adapter.introspect();

const policy = new PolicyBuilder('prod')
  .registerModels(['orders', 'customers'])
  .tenantScope('tenantId')
  .build();

const tools = createGenericTools({ adapter, policy, schema: introspected });
```

## Quick Start with TypeORM

```typescript
import { DataSource } from 'typeorm';
import { TypeOrmAdapter } from '@ormai/typeorm';
import { PolicyBuilder, createContext } from '@ormai/core';
import { createGenericTools } from '@ormai/tools';
import { User, Order } from './entities';

const dataSource = new DataSource({
  type: 'postgres',
  url: process.env.DATABASE_URL,
  entities: [User, Order],
});
await dataSource.initialize();

const adapter = new TypeOrmAdapter({ dataSource });
const schema = await adapter.introspect();

const policy = new PolicyBuilder('prod')
  .registerModels(['User', 'Order'])
  .tenantScope('tenantId')
  .build();

const tools = createGenericTools({ adapter, policy, schema });
```

## PolicyBuilder

`PolicyBuilder` from `@ormai/core` (re-exported by `@ormai/utils`) is the canonical way to declare policies in TypeScript.

```typescript
import { PolicyBuilder } from '@ormai/core';

const policy = new PolicyBuilder('prod')
  .registerModels(['Customer', 'Order', 'Product'])
  .tenantScope('tenantId')
  .denyFields('*password*', '*secret*', '*token*')
  .maskFields('*email*', '*phone*')
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

Profile presets ship in `@ormai/utils`: `DEFAULT_DEV` (permissive), `DEFAULT_INTERNAL` (moderate), `DEFAULT_PROD` (strict).

## Generic Tools

`createGenericTools` returns the standard tool set:

- `db.query` — filter, paginate, include relations
- `db.get` — fetch a single record by primary key
- `db.aggregate` — count / sum / avg / min / max with `groupBy`
- `db.describe_schema` — return the policy-filtered schema
- `db.create` / `db.update` / `db.delete` / `db.bulk_update` — gated by `enableWrites`

Each tool returns a structured result and never executes raw SQL.

## Agent Framework Integrations

`@ormai/integrations` adapts the tool registry to popular agent frameworks.

### Vercel AI SDK

```typescript
import { toVercelAITools } from '@ormai/integrations';
import { generateText } from 'ai';
import { openai } from '@ai-sdk/openai';

const agentTools = await toVercelAITools(registry.list(), ctx);

const result = await generateText({
  model: openai('gpt-4o'),
  tools: agentTools,
  prompt: 'Find all pending orders for the current tenant',
});
```

### Other adapters

The same package also exposes adapters for LangChain.js, OpenAI function-calling, Anthropic tool use, LlamaIndex.ts, and Mastra.

## Audit Logging

```typescript
import { JsonlAuditStore, withAudit } from '@ormai/store';

const store = new JsonlAuditStore('./audit.jsonl');
const auditedTools = tools.map(tool => withAudit(tool, store));
```

`@ormai/store` also ships an in-memory store for tests and middleware helpers for wrapping a registry.

## MCP Server

```typescript
import {
  createMcpServer,
  createJwtAuth,
  createContextFactory,
} from '@ormai/mcp';

const server = createMcpServer({
  name: 'my-db-server',
  version: '1.0.0',
  registry,
  createContext: createContextFactory({
    db: prisma,
    defaultRoles: ['user'],
  }),
  authMiddleware: createJwtAuth({
    secret: process.env.JWT_SECRET!,
  }),
});

await server.runStdio();
```

## Feature Comparison

| Feature | Python (`ormai`) | TypeScript (`@ormai/*`) |
|---|---|---|
| Query DSL | Yes | Yes |
| Policy engine | Yes | Yes |
| Tenant scoping | Yes | Yes |
| Write operations | Yes | Yes |
| Audit logging | Yes | Yes |
| MCP server | Yes | Yes |
| Vercel AI / LangChain.js | — | Yes |
| FastAPI integration | Yes | — |
| Codegen / eval harness | Yes | Partial |

## Next Steps

- [FastAPI Integration](fastapi.md) — Python web framework integration
- [LangGraph Integration](langgraph.md) — Multi-step agent integration
- [Multi-Tenant Setup](../guides/multi-tenant.md) — Tenant isolation patterns
