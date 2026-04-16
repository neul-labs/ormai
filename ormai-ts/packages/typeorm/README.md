# @ormai/typeorm

TypeORM adapter with full introspection, query compilation, and CRUD support for OrmAI.

[![npm version](https://img.shields.io/npm/v/@ormai/typeorm)](https://www.npmjs.com/package/@ormai/typeorm) [![license](https://img.shields.io/npm/l/@ormai/typeorm)](https://github.com/neul-labs/ormai/blob/main/ormai-ts/packages/typeorm/LICENSE) [![CI](https://img.shields.io/github/actions/workflow/status/neul-labs/ormai/test.yml)](https://github.com/neul-labs/ormai/actions)

`@ormai/typeorm` provides a TypeORM adapter that implements the `OrmAdapter` interface from `@ormai/core`. It introspects your TypeORM entities, compiles OrmAI DSL queries into QueryBuilder calls, and supports full CRUD operations.

## Installation

```bash
npm install @ormai/core @ormai/typeorm
# and the TypeORM peer dependency:
npm install typeorm
```

## Quick Start

```typescript
import { DataSource } from 'typeorm';
import { TypeORMAdapter } from '@ormai/typeorm';
import { PolicyBuilder, createToolset, createContext } from '@ormai/core';

const dataSource = new DataSource({ /* ... */ });
await dataSource.initialize();

const adapter = new TypeORMAdapter({ dataSource });
const schema = await adapter.introspect();

const policy = new PolicyBuilder('prod')
  .registerModels(['User', 'Order', 'Product'])
  .tenantScope('tenantId')
  .denyFields('*password*')
  .build();

const registry = createToolset({ adapter, policy, schema });
```

## API Reference

- `TypeORMAdapter` -- Full `OrmAdapter` implementation for TypeORM
- `createTypeORMAdapter(config)` -- Factory function
- `TypeORMAdapterConfig`, `TypeORMAdapterDataSource` -- Configuration types
- `TypeORMIntrospector`, `createTypeORMIntrospector()` -- Schema introspection from TypeORM metadata
- `TypeORMCompiler`, `createTypeORMCompiler()` -- Compiles OrmAI DSL to TypeORM queries
- `TypeORMEntityMetadata`, `TypeORMColumnMetadata`, `TypeORMRelationMetadata` -- Introspection types

## Related Packages

- [@ormai/core](../core/) -- Core types and policy engine
- [@ormai/prisma](../prisma/) -- Prisma adapter
- [@ormai/drizzle](../drizzle/) -- Drizzle adapter
- [@ormai/tools](../tools/) -- Generic database tools
- [@ormai/utils](../utils/) -- PolicyBuilder and factories

## License

MIT