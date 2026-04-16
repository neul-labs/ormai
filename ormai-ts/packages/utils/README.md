# @ormai/utils

PolicyBuilder, defaults profiles (DEV/PROD/INTERNAL), quickSetup factory, and testing helpers.

[![npm version](https://img.shields.io/npm/v/@ormai/utils)](https://www.npmjs.com/package/@ormai/utils) [![license](https://img.shields.io/npm/l/@ormai/utils)](https://github.com/neul-labs/ormai/blob/main/ormai-ts/packages/utils/LICENSE) [![CI](https://img.shields.io/github/actions/workflow/status/neul-labs/ormai/test.yml)](https://github.com/neul-labs/ormai/actions)

`@ormai/utils` provides convenience utilities that reduce boilerplate when setting up OrmAI. It includes a fluent `PolicyBuilder`, preset profiles for common environments, a `quickSetup` factory, and testing helpers for writing assertions against policy-governed tools.

## Installation

```bash
npm install @ormai/core @ormai/utils
```

## Quick Start

```typescript
import { PolicyBuilder, quickSetup, DEV_DEFAULTS } from '@ormai/utils';
import { PrismaAdapter } from '@ormai/prisma';

const adapter = new PrismaAdapter({ prisma });
const schema = await adapter.introspect();

const policy = new PolicyBuilder('prod')
  .registerModels(['Customer', 'Order', 'Product'])
  .tenantScope('tenantId')
  .denyFields('*password*')
  .maskFields('*email*')
  .allowRelations('Order', ['customer', 'items'])
  .enableWrites(['Order'])
  .build();

const registry = quickSetup({ adapter, policy, schema });
```

### Defaults Profiles

```typescript
import { PROD_DEFAULTS, DEV_DEFAULTS, INTERNAL_DEFAULTS } from '@ormai/utils';

// PROD: strict budgets, writes disabled, redaction on
// DEV: relaxed budgets, writes enabled, no redaction
// INTERNAL: moderate budgets, writes enabled, partial redaction
```

### Testing Helpers

```typescript
import { createTestContext, createTestSchema, createTestPolicy, createMockAdapter } from '@ormai/utils';

const mockAdapter = createMockAdapter({
  models: { User: { fields: { id: 'string', name: 'string' } } },
});
const testCtx = createTestContext({ tenantId: 't1', roles: ['admin'] });
```

## API Reference

### PolicyBuilder

- `PolicyBuilder` -- Fluent policy construction with method chaining
- `createPolicyBuilder(profile)` -- Factory function

### Defaults Profiles

- `PROD_DEFAULTS`, `DEV_DEFAULTS`, `INTERNAL_DEFAULTS` -- Preset configurations
- `getDefaultsProfile(profile)` -- Look up a profile by name
- `budgetFromProfile(profile)` / `writePolicyFromProfile(profile)` -- Extract specific config

### Factory

- `createToolset(options)` -- Create a tool registry with all generic tools
- `quickSetup(options)` -- One-call setup for adapter + policy + tools
- `createRestrictedView(registry, options)` -- Create a filtered view of available tools

### Testing

- `createTestContext(options)` -- Create a test `RunContext`
- `createTestSchema(overrides)` -- Build a `SchemaMetadata` for tests
- `createTestPolicy(overrides)` -- Build a `Policy` for tests
- `createMockAdapter(overrides)` -- Create a mock `OrmAdapter`
- `assertThrows(fn, errorClass)` -- Assert a function throws a specific error

## Related Packages

- [@ormai/core](../core/) -- Core types, policy engine, DSL schemas
- [@ormai/tools](../tools/) -- Generic database tools
- [@ormai/prisma](../prisma/) -- Prisma adapter
- [@ormai/drizzle](../drizzle/) -- Drizzle adapter
- [@ormai/typeorm](../typeorm/) -- TypeORM adapter

## License

MIT