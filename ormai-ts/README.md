# OrmAI TypeScript Edition

A policy-governed, auditable database capability layer for TypeScript/Node.js applications. OrmAI-TS enables AI agents to safely interact with databases through structured tools while enforcing security policies, tenant isolation, and comprehensive audit logging.

## Features

- **Policy-Governed Access** - Field-level allowlists, tenant scoping, and budget controls
- **Multi-ORM Support** - Prisma, Drizzle, and TypeORM adapters
- **Full CRUD Operations** - Query, get, aggregate, create, update, delete, bulk update
- **Agent Framework Integrations** - Vercel AI SDK, LangChain.js, LlamaIndex, Mastra, OpenAI, Anthropic
- **MCP Server** - Model Context Protocol server with authentication
- **Audit Logging** - Comprehensive logging with before/after snapshots
- **Type Safety** - Full TypeScript support with Zod validation

## Installation

```bash
npm install ormai-ts
```

## Quick Start

### With Prisma

```typescript
import { PrismaClient } from '@prisma/client';
import {
  PrismaAdapter,
  PolicyBuilder,
  createToolset,
  createContext,
} from 'ormai-ts';

const prisma = new PrismaClient();

// Create adapter
const adapter = new PrismaAdapter({ prisma });

// Introspect schema
const schema = await adapter.introspect();

// Build policy
const policy = new PolicyBuilder('prod')
  .registerModels(['Customer', 'Order', 'Product'])
  .tenantScope('tenantId')
  .denyFields('*password*')
  .maskFields('*email*')
  .allowRelations('Order', ['customer', 'items'])
  .enableWrites(['Order'])
  .build();

// Create toolset
const registry = createToolset({ adapter, policy, schema });

// Create execution context
const ctx = createContext({
  tenantId: 'tenant-123',
  userId: 'user-456',
  db: prisma,
  roles: ['admin'],
});

// Use tools
const queryTool = registry.get('db.query');
const result = await queryTool.execute({
  model: 'Order',
  where: [{ field: 'status', op: 'eq', value: 'pending' }],
  take: 10,
}, ctx);
```

### With Vercel AI SDK

```typescript
import { toVercelAITools } from 'ormai-ts';
import { generateText } from 'ai';
import { openai } from '@ai-sdk/openai';

const tools = await toVercelAITools(registry.list(), ctx);

const result = await generateText({
  model: openai('gpt-4o'),
  tools,
  prompt: 'Find all pending orders for the current tenant',
});
```

### With LangChain.js

```typescript
import { toLangChainTools } from 'ormai-ts';
import { ChatOpenAI } from '@langchain/openai';
import { AgentExecutor, createToolCallingAgent } from 'langchain/agents';

const tools = await toLangChainTools(registry.list(), ctx);

const agent = createToolCallingAgent({
  llm: new ChatOpenAI({ model: 'gpt-4o' }),
  tools,
  prompt: hubPrompt,
});
```

### MCP Server

```typescript
import { createMcpServer, createJwtAuth, createContextFactory } from 'ormai-ts';

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

// Start stdio server for Claude Desktop
await server.runStdio();
```

## Module Structure

```
ormai-ts/
├── core/           # Context, DSL schemas, errors, types
├── policy/         # Policy engine, scoping, redaction, budgets
├── adapters/       # Prisma, Drizzle, TypeORM adapters
├── tools/          # Generic database tools
├── store/          # Audit logging (in-memory, JSONL)
├── mcp/            # MCP server with auth middleware
├── integrations/   # Agent framework adapters
└── utils/          # PolicyBuilder, factories, testing helpers
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
const policy = new PolicyBuilder('prod')
  // Register models
  .registerModels(['Customer', 'Order', 'Product'])

  // Tenant isolation
  .tenantScope('tenantId')

  // Field security
  .denyFields('*password*')
  .denyFields('*secret*')
  .maskFields('*email*')

  // Relations
  .allowRelations('Order', ['customer', 'items'])

  // Write permissions
  .enableWrites(['Order'], {
    allowCreate: true,
    allowUpdate: true,
    allowDelete: false,
    maxAffectedRows: 10,
  })

  // Budget controls
  .defaultBudgetConfig({
    maxRows: 100,
    maxIncludesDepth: 2,
    statementTimeoutMs: 5000,
  })

  .build();
```

## Agent Framework Integrations

| Framework | Function | Description |
|-----------|----------|-------------|
| Vercel AI SDK | `toVercelAITools()` | Returns tools for `generateText`/`streamText` |
| LangChain.js | `toLangChainTools()` | Returns `DynamicStructuredTool[]` |
| LlamaIndex.ts | `toLlamaIndexTools()` | Returns `FunctionTool[]` |
| Mastra | `toMastraTools()` | Returns Mastra-compatible tools |
| OpenAI SDK | `toOpenAITools()` | Returns OpenAI function definitions |
| Anthropic SDK | `toAnthropicTools()` | Returns Claude tool definitions |
| Generic | `toJsonSchemas()` | Returns JSON Schema definitions |

## Audit Logging

```typescript
import { JsonlAuditStore, withAudit } from 'ormai-ts';

// Create audit store
const auditStore = new JsonlAuditStore('./audit.jsonl');

// Wrap tools with audit logging
const auditedTool = withAudit(tool, auditStore, {
  includeInputs: true,
  includeOutputs: true,
  redactInputFields: ['password'],
});

// Execute with automatic audit logging
const result = await auditedTool.execute(input, ctx);
```

## Error Handling

OrmAI-TS provides structured errors with retry hints:

```typescript
import {
  ModelNotAllowedError,
  FieldNotAllowedError,
  TenantScopeRequiredError,
  QueryBudgetExceededError,
  WriteDisabledError,
} from 'ormai-ts';

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

## API Reference

### Core Exports

- `createContext()` - Create execution context
- `createPrincipal()` - Create principal (identity)
- `PolicyEngine` - Validate requests against policies
- `PolicyBuilder` - Fluent policy construction

### Adapters

- `PrismaAdapter` - Prisma ORM adapter
- `DrizzleAdapter` - Drizzle ORM adapter
- `TypeORMAdapter` - TypeORM adapter

### Tools

- `ToolRegistry` - Register and manage tools
- `createGenericTools()` - Create all 8 database tools
- `BaseTool` - Base class for custom tools

### MCP

- `McpServer` - MCP server implementation
- `createMcpServer()` - Create configured MCP server
- `createJwtAuth()` - JWT authentication middleware
- `createApiKeyAuth()` - API key authentication

## License

MIT

## Related

- [OrmAI Python](https://github.com/anthropics/ormai) - Python edition
- [Model Context Protocol](https://modelcontextprotocol.io/) - MCP specification
