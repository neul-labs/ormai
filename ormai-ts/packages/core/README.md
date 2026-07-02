# @ormai/core

Core types, policy engine, adapter/tool/store interfaces, DSL schemas, error taxonomy, and cursor encoding for OrmAI.

[![npm version](https://img.shields.io/npm/v/@ormai/core)](https://www.npmjs.com/package/@ormai/core) [![license](https://img.shields.io/npm/l/@ormai/core)](https://github.com/neul-labs/ormai/blob/main/ormai-ts/packages/core/LICENSE) [![CI](https://img.shields.io/github/actions/workflow/status/neul-labs/ormai/test.yml)](https://github.com/neul-labs/ormai/actions)

**[Website](https://ormai.neullabs.com)** · **[Documentation](https://docs.neullabs.com/ormai)** · **[GitHub](https://github.com/neul-labs/ormai)**

`@ormai/core` is the foundation for all OrmAI packages. It bundles five modules:

- **Core** -- execution context (`RunContext`), DSL schemas for queries/mutations, type definitions for models/fields/relations, cursor encoding, and a structured error taxonomy.
- **Policy** -- `PolicyEngine`, scoping, redaction, budget enforcement, and cost estimation.
- **Adapter Base** -- `OrmAdapter` interface, `BaseOrmAdapter`, compiled query/mutation types.
- **Tool Base** -- `BaseTool`, `ToolRegistry`, `ok`/`fail` result constructors.
- **Audit Base** -- `AuditStore` interface, `BaseAuditStore`, audit record models.

## Installation

```bash
npm install @ormai/core
```

## Quick Start

```typescript
import {
  PrismaAdapter,
  PolicyBuilder,
  createToolset,
  createContext,
} from '@ormai/core';

const adapter = new PrismaAdapter({ prisma });
const schema = await adapter.introspect();

const policy = new PolicyBuilder('prod')
  .registerModels(['Customer', 'Order', 'Product'])
  .tenantScope('tenantId')
  .denyFields('*password*')
  .maskFields('*email*')
  .enableWrites(['Order'])
  .build();

const registry = createToolset({ adapter, policy, schema });

const ctx = createContext({
  tenantId: 'tenant-123',
  userId: 'user-456',
  db: prisma,
  roles: ['admin'],
});

const result = await registry.get('db.query').execute({
  model: 'Order',
  where: [{ field: 'status', op: 'eq', value: 'pending' }],
  take: 10,
}, ctx);
```

## API Reference

### Core

`createContext`, `createContextWithPrincipal`, `createPrincipal`, `hasRole`, `isRunContext`, `isPrincipal`
`FilterOpSchema`, `QueryRequestSchema`, `CreateRequestSchema`, `UpdateRequestSchema`, `DeleteRequestSchema`, `BulkUpdateRequestSchema`, `AggregateRequestSchema`, and result schemas
`CursorEncoder`, `buildKeysetCondition`, `defaultEncoder`
`ModelNotAllowedError`, `FieldNotAllowedError`, `TenantScopeRequiredError`, `QueryBudgetExceededError`, `WriteDisabledError`, `NotFoundError`, `AdapterError`, `ValidationError`, and more

### Policy

`PolicyEngine`, `ScopeInjector`, `createScopeInjector`, `Redactor`, `createRedactor`, `maskEmail`, `maskPhone`, `ComplexityScorer`, `BudgetEnforcer`, `QueryCostEstimator`, `CostTracker`

### Adapter Base

`BaseOrmAdapter`, `OrmAdapter` (interface), `CompiledQuery`, `CompiledMutation`, `applyRedaction`

### Tool Base

`BaseTool`, `ToolRegistry`, `createToolRegistry`, `ok`, `fail`

### Audit Base

`BaseAuditStore`, `AuditStore` (interface), `AuditRecordSchema`, `createAuditRecord`

## Related Packages

- [@ormai/prisma](../prisma/) -- Prisma adapter
- [@ormai/drizzle](../drizzle/) -- Drizzle adapter
- [@ormai/typeorm](../typeorm/) -- TypeORM adapter
- [@ormai/tools](../tools/) -- Generic database tools
- [@ormai/store](../store/) -- Audit logging stores
- [@ormai/mcp](../mcp/) -- MCP server
- [@ormai/integrations](../integrations/) -- Agent framework integrations
- [@ormai/utils](../utils/) -- PolicyBuilder, factories, testing helpers

## License

MIT

## Part of the Neul Labs toolchain

Part of the [Neul Labs](https://www.neullabs.com) agent-infrastructure toolchain:

| Project | Description |
| --- | --- |
| [agentvfs](https://agentvfs.neullabs.com) | Workspace runtime and execution boundary for AI agents. |
| [memorg](https://memorg.neullabs.com) | Give your LLM a memory that actually works. |
| [mcp-pay](https://mcp-pay.neullabs.com) | Payment awareness layer for MCP (Model Context Protocol). |
| [closegate](https://closegate.neullabs.com) | The policy chokepoint for finance AI agents. |
| [regulus](https://regulus.neullabs.com) | The EU & UK compliance plane for Google ADK. |