# @ormai/store

Audit logging stores (in-memory, JSONL) and middleware for recording all tool operations.

[![npm version](https://img.shields.io/npm/v/@ormai/store)](https://www.npmjs.com/package/@ormai/store) [![license](https://img.shields.io/npm/l/@ormai/store)](https://github.com/neul-labs/ormai/blob/main/ormai-ts/packages/store/LICENSE) [![CI](https://img.shields.io/github/actions/workflow/status/neul-labs/ormai/test.yml)](https://github.com/neul-labs/ormai/actions)

`@ormai/store` provides audit logging implementations that capture before/after snapshots of every tool operation. Use it to maintain a tamper-proof record of all database actions performed by AI agents.

## Installation

```bash
npm install @ormai/core @ormai/store
```

## Quick Start

```typescript
import { JsonlAuditStore, createJsonlAuditStore, withAudit } from '@ormai/store';
import { createGenericTools, createContext } from '@ormai/core';

const auditStore = createJsonlAuditStore('./audit.jsonl');

const tool = registry.get('db.query');
const auditedTool = withAudit(tool, auditStore, {
  includeInputs: true,
  includeOutputs: true,
  redactInputFields: ['password'],
});

const result = await auditedTool.execute(input, ctx);
```

## API Reference

- `InMemoryAuditStore`, `createInMemoryAuditStore()` -- In-memory store for testing
- `JsonlAuditStore`, `createJsonlAuditStore(path)` -- JSONL file store for production
- `withAudit(tool, store, options)` -- Wrap a tool with audit logging
- `createAuditedToolRegistry(registry, store, options)` -- Wrap all tools in a registry
- `AuditMiddlewareOptions` -- Configuration for redaction and inclusion

## Related Packages

- [@ormai/core](../core/) -- Audit record types and base store interface
- [@ormai/tools](../tools/) -- Generic database tools
- [@ormai/mcp](../mcp/) -- MCP server with auth middleware
- [@ormai/utils](../utils/) -- Testing helpers including `createMockAdapter`

## License

MIT