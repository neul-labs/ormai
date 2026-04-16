# @ormai/prisma

Prisma ORM adapter with full introspection, query compilation, and CRUD support for OrmAI.

[![npm version](https://img.shields.io/npm/v/@ormai/prisma)](https://www.npmjs.com/package/@ormai/prisma) [![license](https://img.shields.io/npm/l/@ormai/prisma)](https://github.com/neul-labs/ormai/blob/main/ormai-ts/packages/prisma/LICENSE) [![CI](https://img.shields.io/github/actions/workflow/status/neul-labs/ormai/test.yml)](https://github.com/neul-labs/ormai/actions)

`@ormai/prisma` provides a Prisma adapter that implements the `OrmAdapter` interface from `@ormai/core`. It introspects your Prisma schema, compiles OrmAI DSL queries into Prisma client calls, and supports full CRUD operations.

## Installation

```bash
npm install @ormai/core @ormai/prisma
# and the Prisma peer dependency:
npm install @prisma/client
```

## Quick Start

```typescript
import { PrismaClient } from '@prisma/client';
import { PrismaAdapter } from '@ormai/prisma';
import { PolicyBuilder, createToolset, createContext } from '@ormai/core';

const prisma = new PrismaClient();
const adapter = new PrismaAdapter({ prisma });

const schema = await adapter.introspect();

const policy = new PolicyBuilder('prod')
  .registerModels(['Customer', 'Order', 'Product'])
  .tenantScope('tenantId')
  .denyFields('*password*')
  .build();

const registry = createToolset({ adapter, policy, schema });
```

## API Reference

- `PrismaAdapter` -- Full `OrmAdapter` implementation for Prisma
- `createPrismaAdapter(options)` -- Factory function
- `PrismaAdapterOptions`, `PrismaClientLike` -- Configuration types
- `introspectFromDMMF(dmmf)` -- Introspect from a Prisma DMMF document
- `introspectPrismaClient(client)` -- Introspect from a live Prisma client
- `getDMMF(schemaPath)` -- Load DMMF from a Prisma schema file
- `PrismaCompiler` -- Compiles OrmAI DSL to Prisma query args
- `defaultCompiler` -- Default compiler instance

## Related Packages

- [@ormai/core](../core/) -- Core types and policy engine
- [@ormai/drizzle](../drizzle/) -- Drizzle adapter
- [@ormai/typeorm](../typeorm/) -- TypeORM adapter
- [@ormai/tools](../tools/) -- Generic database tools
- [@ormai/utils](../utils/) -- PolicyBuilder and factories

## License

MIT