# @ormai/mcp

Model Context Protocol server with JWT/API key auth, multi-tenant header extraction, and dev auth middleware.

[![npm version](https://img.shields.io/npm/v/@ormai/mcp)](https://www.npmjs.com/package/@ormai/mcp) [![license](https://img.shields.io/npm/l/@ormai/mcp)](https://github.com/neul-labs/ormai/blob/main/ormai-ts/packages/mcp/LICENSE) [![CI](https://img.shields.io/github/actions/workflow/status/neul-labs/ormai/test.yml)](https://github.com/neul-labs/ormai/actions)

`@ormai/mcp` exposes OrmAI tools via the Model Context Protocol so that AI agents can discover and call database operations over stdio or HTTP transport. It includes authentication middleware for JWT, API key, and development-only scenarios.

## Installation

```bash
npm install @ormai/core @ormai/mcp
# and the MCP SDK peer dependency:
npm install @modelcontextprotocol/sdk
```

## Quick Start

```typescript
import { createPrismaAdapter } from '@ormai/prisma';
import { createToolset, createContext } from '@ormai/core';
import { createMcpServer, createJwtAuth, createContextFactory } from '@ormai/mcp';

const adapter = createPrismaAdapter({ prisma });
const registry = createToolset({ adapter, policy, schema });

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

## API Reference

### Auth

- `createJwtAuth(options)` -- JWT authentication middleware
- `createApiKeyAuth(options)` -- API key authentication middleware
- `createDevAuth(options)` -- Development-only auth (no verification)
- `createContextFactory(options)` -- Create a context factory for MCP requests
- `extractTenantFromHeaders(headers)` -- Multi-tenant header extraction
- `principalFromHeaders(headers)` -- Extract principal from request headers
- `combineAuthMiddlewares(...middlewares)` -- Compose multiple auth middlewares

### Server

- `McpServer` -- MCP server implementation
- `createMcpServer(config)` -- Create a configured MCP server
- `createSimpleMcpServer(config)` -- Create a server with minimal configuration

## Related Packages

- [@ormai/core](../core/) -- Core types, policy engine, tool registry
- [@ormai/tools](../tools/) -- Generic database tools
- [@ormai/prisma](../prisma/) -- Prisma adapter
- [@ormai/drizzle](../drizzle/) -- Drizzle adapter
- [@ormai/typeorm](../typeorm/) -- TypeORM adapter

## License

MIT