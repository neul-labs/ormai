# OrmAI TypeScript Specification (ormai-ts)

OrmAI-TS is the TypeScript/Node.js edition of OrmAI, bringing the same policy-governed, auditable database capabilities to the JavaScript ecosystem. It targets Prisma, Drizzle, and TypeORM while maintaining full compatibility with the Python OrmAI DSL and MCP tool surface.

---

## 0. Summary

OrmAI-TS provides:

- Zod-based typed tool signatures and responses.
- Policy-compiled, adapter-specific query/mutation execution.
- Built-in tenant scoping, ACL enforcement, and field-level redaction.
- Automatic pagination, cost/budget controls, and query complexity guards.
- Immutable audit logging with tracing hooks.
- Optional approval workflows for write operations.
- MCP server/client mounting with consistent tool schemas across Python and TypeScript.

Adapters target Prisma (priority), Drizzle ORM, and TypeORM initially.

---

## 1. Goals vs. Non-goals

### Goals

1. **Feature parity** – Match Python OrmAI's safety guarantees and developer experience.
2. **Shared DSL** – Use identical JSON query/mutation schemas for cross-language compatibility.
3. **Drop-in integration** – Work with existing Prisma/Drizzle/TypeORM codebases without rewrites.
4. **Type safety** – Leverage TypeScript's type system and Zod for runtime validation.
5. **MCP compatibility** – Expose the same tool surface as Python OrmAI.
6. **Ecosystem fit** – Follow Node.js conventions (async-first, ESM, npm distribution).

### Non-goals

- Replacing agent frameworks – OrmAI-TS is a DB capability layer.
- Supporting non-TypeScript JavaScript – TypeScript-first with JS compatibility.
- Sync adapters – Node.js is async-native; no sync variants needed.

---

## 2. Key Concepts

### Capability, not ORM exposure

- Agents see curated **domain tools** and a **generic DSL toolset**, never Prisma clients or query builders directly.

### Policy-compiled execution

- Policies inject tenant filters, enforce field allowlists, and apply budgets at compile/execution time.
- Write policies govern approvals, affected row limits, and reason requirements.

### Views / Projection Models

- Responses are Zod-validated view objects, not ORM entities.
- Views stabilize schemas, simplify redaction, and decouple responses from ORM internals.

---

## 3. Architecture Overview

### Module layout

```
ormai-ts/
├── core/           # Runtime, execution context, DSL schemas (Zod), error taxonomy
├── adapters/       # PrismaAdapter, DrizzleAdapter, TypeORMAdapter
├── policy/         # Allowlists, scoping, budgets, write controls, redaction
├── store/          # Audit log storage (Prisma-based, file-based)
├── mcp/            # MCP server with auth/context injection
├── integrations/   # Agent framework adapters (Vercel AI, LangChain, etc.)
├── generators/     # Optional codegen for Zod views and domain tools
└── utils/          # Defaults, builders, factories, session helpers, testing
```

### Package distribution

- Published as `ormai-ts` on npm.
- ESM-first with CommonJS fallback.
- Full TypeScript declarations included.
- Zero runtime dependencies beyond Zod and adapter peer dependencies.

---

## 4. Target ORMs

### Prisma (Priority)

- Schema-first with excellent type inference.
- Largest Node.js ORM user base.
- Adapter leverages Prisma Client's generated types.
- Introspection via `prisma.dmmf` or schema parsing.

### Drizzle ORM

- SQL-like, lightweight, strong TypeScript support.
- Growing adoption, especially with edge runtimes.
- Adapter uses Drizzle's query builder with type inference.

### TypeORM

- Decorator-based, similar patterns to SQLAlchemy.
- Mature ecosystem with broad database support.
- Adapter handles entity metadata introspection.

---

## 5. Runtime & Context Model

### Execution context

Each tool call runs inside a `RunContext` carrying:

```typescript
interface RunContext {
  principal: {
    tenantId: string;
    userId: string;
    roles: string[];
  };
  requestId: string;
  traceId?: string;
  db: AdapterClient; // Prisma/Drizzle/TypeORM client
  now: Date;
}
```

### Dependency management

- `ContextBuilder` constructs request-scoped context from auth claims.
- Adapters manage transaction lifecycle, ensuring rollback on errors.

---

## 6. Policy Engine

### Policy objects

Policies mirror Python OrmAI semantics:

- **Model policies** – Access allowlists, read/write flags.
- **Field policies** – Allow, deny, mask, or hash fields.
- **Relation policies** – Allowed expansions and max depth.
- **Row policies** – Tenant/ownership scoping, soft-delete handling.
- **Budgets** – Row limits, include depth, field counts, query timeout, complexity thresholds.
- **Write policies** – Permissible operations, max affected rows, approval requirements.

### Scoping rules

- Automatic injection of tenant filters (e.g., `where: { tenantId: ctx.principal.tenantId }`).
- Enforced in the adapter compiler, not suggested to the LLM.

### Redaction

- Field-level redaction after query execution.
- Supports deny (remove), mask (partial), and hash strategies.

### Query budgeting

- Hard caps on `take`, include depth, selected fields, and query duration.
- Complexity scoring; requests exceeding thresholds are rejected with retry hints.

---

## 7. Tool Surface

### Generic DB tools

Identical to Python OrmAI:

- `db.describe_schema` – Returns allow-listed models, fields, relations.
- `db.query` – Structured DSL with select, where, orderBy, pagination, includes.
- `db.get` – Fetch by primary key with optional includes.
- `db.aggregate` – Controlled aggregations on whitelisted fields.
- `db.create`, `db.update`, `db.delete`, `db.bulk_update_by_ids` – Write interfaces with policy guardrails.

### Domain tools

- Developers register TypeScript functions with Zod input/output schemas.
- OrmAI-TS validates inputs, injects scoping, enforces policies, and handles auditing.

---

## 8. Structured Query DSL

### Shared JSON format

The DSL uses identical JSON schemas as Python OrmAI:

```typescript
interface QueryRequest {
  model: string;
  select?: string[];
  where?: FilterClause[];
  orderBy?: OrderClause[];
  take?: number;
  cursor?: string;
  include?: IncludeClause[];
}

interface FilterClause {
  field: string;
  op: 'eq' | 'ne' | 'in' | 'not_in' | 'lt' | 'lte' | 'gt' | 'gte' | 'is_null' | 'contains' | 'startswith' | 'endswith' | 'between';
  value: unknown;
}
```

### Pagination

- Cursor-based with deterministic ordering.
- Responses include `nextCursor` and `hasMore`.

### Includes/expansion

- `include` array references allow-listed relations.
- Max depth enforced globally or per relation.

---

## 9. Adapter Requirements

Adapters must implement:

```typescript
interface OrmAdapter {
  // Enumerate models, fields, types, PKs, relations
  introspect(): Promise<SchemaMetadata>;

  // Transform DSL to ORM-specific query
  compile(request: QueryRequest, context: RunContext, policy: Policy): CompiledQuery;

  // Execute query, map to views, apply redaction
  execute(compiled: CompiledQuery): Promise<QueryResult>;

  // Transaction management
  transaction<T>(fn: (tx: TransactionClient) => Promise<T>): Promise<T>;
}
```

### Backend considerations

- **Prisma**: Uses `prisma.model.findMany()` with generated types; introspects via DMMF.
- **Drizzle**: Uses query builder with `db.select().from()` patterns.
- **TypeORM**: Uses repository pattern with entity metadata.

---

## 10. Storage & Auditing

### Audit log record schema

```typescript
interface AuditRecord {
  id: string;
  toolName: string;
  principalId: string;
  tenantId: string;
  requestId: string;
  traceId?: string;
  timestamp: Date;
  inputs: Record<string, unknown>; // sanitized
  policyDecisions: string[];
  rowCount?: number;
  duration: number;
  error?: { code: string; message: string };
  beforeSnapshot?: unknown;
  afterSnapshot?: unknown;
}
```

### Storage backends

- `PrismaAuditStore` – Uses a Prisma model for audit records.
- `JsonlAuditStore` – Appends to JSONL file (development).
- `ConsoleAuditStore` – Logs to stdout (debugging).

---

## 11. MCP Integration

- MCP server exposes all tools with JSON schemas derived from Zod models.
- Auth middleware builds principals from JWTs or API keys.
- Tool schemas are identical to Python OrmAI, enabling polyglot agent setups.

```typescript
import { createMcpServer } from 'ormai-ts/mcp';

const server = createMcpServer({
  toolset,
  auth: jwtAuth({ secret: process.env.JWT_SECRET }),
  contextBuilder: defaultContextBuilder,
});
```

---

## 12. Agent Framework Integrations

OrmAI-TS provides first-class adapters for popular TypeScript agent frameworks, enabling seamless integration without manual tool wiring.

### Target Frameworks

| Framework | Priority | Package | Notes |
|-----------|----------|---------|-------|
| **Vercel AI SDK** | P0 | `ormai-ts/integrations/vercel-ai` | Largest TS AI user base, Next.js dominance |
| **LangChain.js** | P0 | `ormai-ts/integrations/langchain` | Cross-ecosystem familiarity, enterprise adoption |
| **LlamaIndex.ts** | P1 | `ormai-ts/integrations/llamaindex` | RAG-heavy use cases |
| **Mastra** | P1 | `ormai-ts/integrations/mastra` | TypeScript-native, growing community |
| **OpenAI SDK** | P1 | `ormai-ts/integrations/openai` | Direct function calling |
| **Anthropic SDK** | P1 | `ormai-ts/integrations/anthropic` | Claude tool use |

### Vercel AI SDK Integration

```typescript
import { createOrmAI } from 'ormai-ts';
import { toVercelAITools } from 'ormai-ts/integrations/vercel-ai';
import { generateText } from 'ai';
import { openai } from '@ai-sdk/openai';

const ormai = createOrmAI({ /* config */ });
const tools = toVercelAITools(ormai.toolset);

const result = await generateText({
  model: openai('gpt-4o'),
  tools,
  prompt: 'Find all orders for customer 123',
});
```

### LangChain.js Integration

```typescript
import { createOrmAI } from 'ormai-ts';
import { toLangChainTools } from 'ormai-ts/integrations/langchain';
import { ChatOpenAI } from '@langchain/openai';
import { AgentExecutor, createToolCallingAgent } from 'langchain/agents';

const ormai = createOrmAI({ /* config */ });
const tools = toLangChainTools(ormai.toolset);

const agent = createToolCallingAgent({
  llm: new ChatOpenAI({ model: 'gpt-4o' }),
  tools,
  prompt: hubPrompt,
});

const executor = new AgentExecutor({ agent, tools });
```

### LlamaIndex.ts Integration

```typescript
import { createOrmAI } from 'ormai-ts';
import { toLlamaIndexTools } from 'ormai-ts/integrations/llamaindex';
import { OpenAIAgent } from 'llamaindex';

const ormai = createOrmAI({ /* config */ });
const tools = toLlamaIndexTools(ormai.toolset);

const agent = new OpenAIAgent({ tools });
const response = await agent.chat({ message: 'Get subscription details for user 456' });
```

### Mastra Integration

```typescript
import { createOrmAI } from 'ormai-ts';
import { toMastraTools } from 'ormai-ts/integrations/mastra';
import { Agent } from '@mastra/core';

const ormai = createOrmAI({ /* config */ });
const tools = toMastraTools(ormai.toolset);

const agent = new Agent({
  name: 'db-agent',
  tools,
  model: { provider: 'openai', name: 'gpt-4o' },
});
```

### Direct Provider SDK Integration

For OpenAI, Anthropic, and other provider SDKs, export raw JSON Schema tool definitions:

```typescript
import { createOrmAI } from 'ormai-ts';
import { toOpenAIFunctions } from 'ormai-ts/integrations/openai';
import { toAnthropicTools } from 'ormai-ts/integrations/anthropic';
import OpenAI from 'openai';
import Anthropic from '@anthropic-ai/sdk';

const ormai = createOrmAI({ /* config */ });

// OpenAI function calling
const openai = new OpenAI();
const functions = toOpenAIFunctions(ormai.toolset);
const response = await openai.chat.completions.create({
  model: 'gpt-4o',
  messages: [{ role: 'user', content: 'List recent orders' }],
  functions,
});

// Anthropic tool use
const anthropic = new Anthropic();
const tools = toAnthropicTools(ormai.toolset);
const message = await anthropic.messages.create({
  model: 'claude-sonnet-4-20250514',
  max_tokens: 1024,
  tools,
  messages: [{ role: 'user', content: 'List recent orders' }],
});
```

### Universal JSON Schema Export

For any framework not explicitly supported:

```typescript
import { createOrmAI } from 'ormai-ts';

const ormai = createOrmAI({ /* config */ });

// Export as JSON Schema (works with any tool-calling system)
const schemas = ormai.toolset.toJSONSchema();
// Returns: { db_query: { name, description, parameters }, ... }

// Execute tool calls
const result = await ormai.toolset.execute('db_query', {
  model: 'Order',
  where: [{ field: 'status', op: 'eq', value: 'pending' }],
  take: 10,
});
```

### Integration Design Principles

1. **Zero runtime overhead** – Adapters are thin wrappers that translate tool formats.
2. **Type preservation** – Full TypeScript types flow through to framework tools.
3. **Context injection** – All integrations support passing `RunContext` for tenant scoping.
4. **Streaming support** – Vercel AI SDK adapter supports streaming responses where applicable.
5. **Error mapping** – OrmAI errors are translated to framework-appropriate formats.

---

## 13. Developer Experience

### Quickstart

```typescript
import { createOrmAI } from 'ormai-ts';
import { PrismaClient } from '@prisma/client';

const prisma = new PrismaClient();

const ormai = createOrmAI({
  adapter: 'prisma',
  client: prisma,
  profile: 'prod',
  policy: {
    models: ['Customer', 'Order', 'Subscription'],
    denyFields: ['*password*', '*token*', '*secret*'],
    maskFields: ['email', 'phone'],
    tenantScope: { field: 'tenantId' },
  },
});

// ormai.toolset - ready-to-use tools
// ormai.mcpServer - optional MCP server
// ormai.views - generated Zod schemas
```

### Policy configuration

```typescript
import { PolicyBuilder, DEFAULT_PROD } from 'ormai-ts/utils';

const policy = new PolicyBuilder(DEFAULT_PROD)
  .registerModels(['Customer', 'Order', 'Subscription'])
  .denyFields('*password*')
  .maskFields(['email', 'phone'])
  .allowRelations({ Order: ['customer', 'items'] })
  .tenantScope('tenantId')
  .build();
```

### View generation

```typescript
import { ViewFactory } from 'ormai-ts/utils';

const views = ViewFactory.fromPolicy(policy, adapter);
// views.Customer - Zod schema for Customer
// views.Order - Zod schema for Order
```

---

## 13. Utilities Pack

### DefaultsProfile

```typescript
interface DefaultsProfile {
  mode: 'prod' | 'internal' | 'dev';
  maxRows: number;              // default: 100
  maxIncludesDepth: number;     // default: 1
  maxSelectFields: number;      // default: 40
  statementTimeoutMs: number;   // default: 2000
  requireTenantScope: boolean;  // default: true
  requireReasonForWrites: boolean;
  writesEnabled: boolean;       // default: false
  softDelete: boolean;          // default: true
  redactStrategy: 'deny' | 'mask';
  allowGenericQuery: boolean;
  allowGenericMutations: boolean;
}
```

Built-in profiles: `DEFAULT_PROD`, `DEFAULT_INTERNAL`, `DEFAULT_DEV`.

### Components

- `PolicyBuilder` – Fluent policy construction with glob patterns.
- `ViewFactory` – Generates Zod schemas from policy + adapter metadata.
- `ToolsetFactory` – Produces toolset from policy with retry hints.
- `AuditMiddleware` – Wraps tools to guarantee audit entries.
- `SchemaCache` – Memoizes adapter introspection with TTL.

---

## 14. Error Taxonomy

Shared error codes with Python OrmAI:

- `ORM_ACCESS_DENIED`
- `MODEL_NOT_ALLOWED`
- `FIELD_NOT_ALLOWED`
- `RELATION_NOT_ALLOWED`
- `TENANT_SCOPE_REQUIRED`
- `QUERY_TOO_BROAD`
- `QUERY_BUDGET_EXCEEDED`
- `WRITE_DISABLED`
- `WRITE_APPROVAL_REQUIRED`
- `MAX_AFFECTED_ROWS_EXCEEDED`
- `VALIDATION_ERROR`

All errors include structured retry hints for LLM self-correction.

---

## 15. Testing Utilities

- In-memory SQLite adapters for unit tests.
- Seed helpers for multi-tenant datasets.
- Eval harness for recording/replaying tool calls.
- Budget assertion helpers.
- Cross-tenant leakage detection.

---

## 16. Security Model

Identical guarantees to Python OrmAI:

- Enforced cross-tenant isolation through injected scoping.
- PII protection via field-level redaction/masking.
- Runaway query prevention with budgets/timeouts.
- Mass write prevention through ID requirements and affected-row caps.
- Full auditability for compliance.

---

## 17. Cross-Language Compatibility

### Shared specifications

| Component | Format | Shared? |
|-----------|--------|---------|
| Query DSL | JSON Schema | Yes |
| MCP tool schemas | JSON Schema | Yes |
| Error codes | String enums | Yes |
| Audit record schema | JSON Schema | Yes |
| Policy semantics | Documentation | Yes |

### Polyglot agent scenarios

- Python backend + TypeScript backend can expose identical MCP tools.
- Agents can interact with either implementation transparently.
- Audit logs are compatible across implementations.

---

## 18. Delivery Plan

### Phase 4.1 – Read-Only MVP

- Core runtime with Zod validation and error taxonomy.
- Prisma adapter with introspection, compile, execute.
- Policy engine with scoping, allowlists, budgets, redaction.
- Read-only tools: `describe_schema`, `get`, `query`, `aggregate`.
- Audit logging (Prisma store + JSONL fallback).
- Basic MCP server.
- **Vercel AI SDK integration** (P0 framework).
- **LangChain.js integration** (P0 framework).
- Universal JSON Schema export for any provider SDK.

### Phase 4.2 – Additional Adapters + Writes

- Drizzle and TypeORM adapters.
- Write tools with approval gates and before/after auditing.
- Utilities pack: `PolicyBuilder`, `ViewFactory`, `ToolsetFactory`.
- **LlamaIndex.ts integration** (P1 framework).
- **Mastra integration** (P1 framework).
- OpenAI and Anthropic SDK direct integrations.

### Phase 4.3 – DX & Ecosystem

- Quickstart functions for Express, Fastify, Next.js.
- Generator CLI for views and domain tools.
- Testing utilities and eval harness.
- Published documentation and examples.
- Integration guides for each supported agent framework.
- Example agents demonstrating end-to-end flows with each framework.

---

## 19. Dependencies

### Runtime

- `zod` – Schema validation (peer dependency).
- Adapter peer dependencies: `@prisma/client`, `drizzle-orm`, `typeorm`.

### Development

- `vitest` – Testing.
- `tsup` – Bundling.
- `typescript` – Type checking.

---

## 20. Repository Structure

```
ormai-ts/
├── packages/
│   ├── core/           # Shared runtime, DSL, errors
│   ├── adapter-prisma/
│   ├── adapter-drizzle/
│   ├── adapter-typeorm/
│   ├── policy/
│   ├── store/
│   ├── mcp/
│   ├── utils/
│   └── generators/
├── examples/
│   ├── express-prisma/
│   ├── fastify-drizzle/
│   └── nextjs-prisma/
├── docs/
└── package.json        # Monorepo root
```

Monorepo managed with pnpm workspaces or turborepo.
