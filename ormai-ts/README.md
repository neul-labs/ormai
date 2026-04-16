# OrmAI TypeScript

[![npm version](https://img.shields.io/npm/v/@ormai/core)](https://www.npmjs.com/package/@ormai/core) [![MIT License](https://img.shields.io/npm/l/@ormai/core)](https://github.com/neul-labs/ormai/blob/main/ormai-ts/packages/core/LICENSE) [![CI](https://img.shields.io/github/actions/workflow/status/neul-labs/ormai/test.yml?label=tests)](https://github.com/neul-labs/ormai/actions)

**Give your AI agents database access without the risk.**

OrmAI wraps your existing ORM models in a policy-enforced runtime. Your agents get typed tools for querying and writing data — while you keep control over what they can see and do.

## Packages

This is a monorepo containing the following packages:

| Package | Version | Description |
|---------|---------|-------------|
| [`@ormai/core`](./packages/core/) | [![npm](https://img.shields.io/npm/v/@ormai/core)](https://www.npmjs.com/package/@ormai/core) | Core types, policy engine, adapter/tool/store interfaces, DSL schemas |
| [`@ormai/prisma`](./packages/prisma/) | [![npm](https://img.shields.io/npm/v/@ormai/prisma)](https://www.npmjs.com/package/@ormai/prisma) | Prisma ORM adapter |
| [`@ormai/drizzle`](./packages/drizzle/) | [![npm](https://img.shields.io/npm/v/@ormai/drizzle)](https://www.npmjs.com/package/@ormai/drizzle) | Drizzle ORM adapter |
| [`@ormai/typeorm`](./packages/typeorm/) | [![npm](https://img.shields.io/npm/v/@ormai/typeorm)](https://www.npmjs.com/package/@ormai/typeorm) | TypeORM adapter |
| [`@ormai/tools`](./packages/tools/) | [![npm](https://img.shields.io/npm/v/@ormai/tools)](https://www.npmjs.com/package/@ormai/tools) | Generic database tools (query, get, aggregate, create, update, delete) |
| [`@ormai/store`](./packages/store/) | [![npm](https://img.shields.io/npm/v/@ormai/store)](https://www.npmjs.com/package/@ormai/store) | Audit logging stores (in-memory, JSONL) and middleware |
| [`@ormai/mcp`](./packages/mcp/) | [![npm](https://img.shields.io/npm/v/@ormai/mcp)](https://www.npmjs.com/package/@ormai/mcp) | Model Context Protocol server with auth |
| [`@ormai/integrations`](./packages/integrations/) | [![npm](https://img.shields.io/npm/v/@ormai/integrations)](https://www.npmjs.com/package/@ormai/integrations) | Agent framework integrations (Vercel AI, LangChain, OpenAI, Anthropic, LlamaIndex, Mastra) |
| [`@ormai/utils`](./packages/utils/) | [![npm](https://img.shields.io/npm/v/@ormai/utils)](https://www.npmjs.com/package/@ormai/utils) | PolicyBuilder, defaults profiles, quickSetup, testing helpers |

## Installation

```bash
# Core (required)
npm install @ormai/core

# Choose your ORM adapter
npm install @ormai/prisma        # + npm install @prisma/client
npm install @ormai/drizzle       # + npm install drizzle-orm
npm install @ormai/typeorm       # + npm install typeorm

# Optional packages
npm install @ormai/tools          # Generic database tools
npm install @ormai/store          # Audit logging
npm install @ormai/mcp            # MCP server (requires @modelcontextprotocol/sdk)
npm install @ormai/integrations   # Agent framework adapters
npm install @ormai/utils          # PolicyBuilder and testing helpers
```

## Quick Start

### With Prisma

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

// Use tools
const result = await tools[0].execute({
  model: 'Order',
  where: [{ field: 'status', op: 'eq', value: 'pending' }],
  take: 10,
}, ctx);
```

### With Vercel AI SDK

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

### MCP Server

```typescript
import { createMcpServer, createJwtAuth, createContextFactory } from '@ormai/mcp';

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

## Available Tools

| Tool | Description |
|------|-------------|
| `db.describe_schema` | List available models, fields, and relations |
| `db.query` | Query records with filters, ordering, pagination |
| `db.get` | Get a single record by primary key |
| `db.aggregate` | Perform aggregations (count, sum, avg, min, max) |
| `db.create` | Create a new record |
| `db.update` | Update a record by primary key |
| `db.delete` | Delete (soft or hard) a record |
| `db.bulk_update` | Update multiple records by IDs |

## Policy Configuration

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

## Agent Framework Integrations

| Framework | Package | Function |
|-----------|---------|----------|
| Vercel AI SDK | `@ormai/integrations` | `toVercelAITools()` |
| LangChain.js | `@ormai/integrations` | `toLangChainTools()` |
| OpenAI SDK | `@ormai/integrations` | `toOpenAITools()` |
| Anthropic SDK | `@ormai/integrations` | `toAnthropicTools()` |
| LlamaIndex.ts | `@ormai/integrations` | `toLlamaIndexTools()` |
| Mastra | `@ormai/integrations` | `toMastraTools()` |

## Audit Logging

```typescript
import { JsonlAuditStore, withAudit } from '@ormai/store';

const auditStore = new JsonlAuditStore('./audit.jsonl');

const auditedTool = withAudit(tool, auditStore, {
  includeInputs: true,
  includeOutputs: true,
  redactInputFields: ['password'],
});

const result = await auditedTool.execute(input, ctx);
```

## Error Handling

```typescript
import {
  ModelNotAllowedError,
  QueryBudgetExceededError,
} from '@ormai/core';

try {
  await tool.execute(input, ctx);
} catch (error) {
  if (error instanceof ModelNotAllowedError) {
    console.log('Allowed models:', error.allowedModels);
  }
  if (error instanceof QueryBudgetExceededError) {
    console.log('Retry hints:', error.retryHints);
  }
}
```

## Development

```bash
# Install dependencies
npm install

# Build all packages
npm run build

# Run tests
npm test

# Type check
npm run typecheck

# Lint
npm run lint
```

## License

MIT

## Related

- [OrmAI Python](https://github.com/neul-labs/ormai) - Python edition
- [Model Context Protocol](https://modelcontextprotocol.io/) - MCP specification