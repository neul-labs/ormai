# @ormai/drizzle

Drizzle ORM adapter with full introspection, query compilation, and CRUD support for OrmAI.

[![npm version](https://img.shields.io/npm/v/@ormai/drizzle)](https://www.npmjs.com/package/@ormai/drizzle) [![license](https://img.shields.io/npm/l/@ormai/drizzle)](https://github.com/neul-labs/ormai/blob/main/ormai-ts/packages/drizzle/LICENSE) [![CI](https://img.shields.io/github/actions/workflow/status/neul-labs/ormai/test.yml)](https://github.com/neul-labs/ormai/actions)

`@ormai/drizzle` provides a Drizzle ORM adapter that implements the `OrmAdapter` interface from `@ormai/core`. It introspects your Drizzle schema, compiles OrmAI DSL queries into Drizzle query builders, and supports full CRUD operations.

## Installation

```bash
npm install @ormai/core @ormai/drizzle
# and the Drizzle peer dependency:
npm install drizzle-orm
```

## Quick Start

```typescript
import { drizzle } from 'drizzle-orm/node-postgres';
import * as schema from './schema';
import { DrizzleAdapter } from '@ormai/drizzle';
import { PolicyBuilder, createToolset, createContext } from '@ormai/core';

const db = drizzle(client, { schema });
const adapter = new DrizzleAdapter({ db, schema });

const introspection = await adapter.introspect();

const policy = new PolicyBuilder('prod')
  .registerModels(['users', 'orders', 'products'])
  .tenantScope('tenantId')
  .denyFields('*password*')
  .build();

const registry = createToolset({ adapter, policy, schema: introspection });
```

## API Reference

- `DrizzleAdapter` -- Full `OrmAdapter` implementation for Drizzle
- `createDrizzleAdapter(config)` -- Factory function
- `DrizzleAdapterConfig`, `DrizzleDB` -- Configuration types
- `DrizzleIntrospector`, `createDrizzleIntrospector()` -- Schema introspection from Drizzle tables
- `DrizzleCompiler`, `createDrizzleCompiler()` -- Compiles OrmAI DSL to Drizzle queries
- `DrizzleTable`, `DrizzleColumn`, `DrizzleRelation`, `DrizzleSchema` -- Introspection types

## Related Packages

- [@ormai/core](../core/) -- Core types and policy engine
- [@ormai/prisma](../prisma/) -- Prisma adapter
- [@ormai/typeorm](../typeorm/) -- TypeORM adapter
- [@ormai/tools](../tools/) -- Generic database tools
- [@ormai/utils](../utils/) -- PolicyBuilder and factories

## License

MIT