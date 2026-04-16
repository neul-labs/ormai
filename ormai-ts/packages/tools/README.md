# @ormai/tools

Generic database tools (query, get, aggregate, create, update, delete, bulk update, describe schema) for AI agents.

[![npm version](https://img.shields.io/npm/v/@ormai/tools)](https://www.npmjs.com/package/@ormai/tools) [![license](https://img.shields.io/npm/l/@ormai/tools)](https://github.com/neul-labs/ormai/blob/main/ormai-ts/packages/tools/LICENSE) [![CI](https://img.shields.io/github/actions/workflow/status/neul-labs/ormai/test.yml)](https://github.com/neul-labs/ormai/actions)

`@ormai/tools` provides eight generic database tools that implement the `BaseTool` interface from `@ormai/core`. Each tool is policy-aware and uses an `OrmAdapter` for query execution.

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

## Installation

```bash
npm install @ormai/core @ormai/tools
# Plus an adapter, e.g.:
npm install @ormai/prisma @prisma/client
```

## Quick Start

```typescript
import { PrismaClient } from '@prisma/client';
import { PrismaAdapter } from '@ormai/prisma';
import { createToolset, createContext } from '@ormai/core';
import { createGenericTools } from '@ormai/tools';

const prisma = new PrismaClient();
const adapter = new PrismaAdapter({ prisma });
const schema = await adapter.introspect();
const policy = createPolicyBuilder('dev').build();

const tools = createGenericTools({ adapter, policy, schema });
const ctx = createContext({ tenantId: 't1', userId: 'u1', db: prisma });

const result = await tools.get('db.query').execute({
  model: 'Order',
  where: [{ field: 'status', op: 'eq', value: 'pending' }],
  take: 10,
}, ctx);
```

## API Reference

- `DescribeSchemaTool` -- Schema introspection tool
- `QueryTool` -- Filtered, paginated query tool
- `GetTool` -- Single record fetch by PK
- `AggregateTool` -- Aggregation tool (count, sum, avg, min, max)
- `CreateTool` -- Record creation tool
- `UpdateTool` -- Record update tool
- `DeleteTool` -- Record deletion tool (soft or hard)
- `BulkUpdateTool` -- Bulk update by IDs
- `createGenericTools(options)` -- Create and register all 8 tools
- `GenericToolsOptions` -- Configuration type

## Related Packages

- [@ormai/core](../core/) -- Core types, policy engine, tool registry
- [@ormai/prisma](../prisma/) -- Prisma adapter
- [@ormai/drizzle](../drizzle/) -- Drizzle adapter
- [@ormai/typeorm](../typeorm/) -- TypeORM adapter
- [@ormai/store](../store/) -- Audit logging stores
- [@ormai/integrations](../integrations/) -- Agent framework integrations

## License

MIT