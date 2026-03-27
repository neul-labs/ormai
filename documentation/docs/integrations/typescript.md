# TypeScript Edition

OrmAI is available as a TypeScript/Node.js package with full feature parity to the Python version.

## Installation

```bash
npm install ormai
# or
yarn add ormai
# or
pnpm add ormai
```

## Supported ORMs

| ORM | Status | Package |
|-----|--------|---------|
| Prisma | Production | Built-in |
| Drizzle | Production | Built-in |
| TypeORM | Production | Built-in |

## Quick Start

### With Prisma

```typescript
import { PrismaClient } from '@prisma/client';
import { mountPrisma, Principal, RunContext } from 'ormai';

const prisma = new PrismaClient();

// Define policy
const policy = {
  models: {
    User: {
      allowed: true,
      fields: {
        id: { action: 'allow' },
        email: { action: 'mask' },
        name: { action: 'allow' },
      },
      scoping: { tenantId: 'principal.tenantId' },
    },
    Order: {
      allowed: true,
      fields: {
        id: { action: 'allow' },
        status: { action: 'allow' },
        total: { action: 'allow' },
      },
      scoping: { tenantId: 'principal.tenantId' },
    },
  },
};

// Mount toolset
const toolset = mountPrisma(prisma, policy);

// Create context
const ctx: RunContext = {
  principal: {
    tenantId: 'acme-corp',
    userId: 'user-123',
    roles: ['member'],
  },
};

// Query
const result = await toolset.query(ctx, {
  model: 'Order',
  filters: [{ field: 'status', op: 'eq', value: 'pending' }],
  limit: 10,
});

console.log(result.rows);
```

### With Drizzle

```typescript
import { drizzle } from 'drizzle-orm/node-postgres';
import { mountDrizzle } from 'ormai';
import * as schema from './schema';

const db = drizzle(pool, { schema });

const toolset = mountDrizzle(db, schema, policy);

const result = await toolset.query(ctx, {
  model: 'orders',
  filters: [{ field: 'status', op: 'eq', value: 'pending' }],
});
```

### With TypeORM

```typescript
import { DataSource } from 'typeorm';
import { mountTypeORM } from 'ormai';
import { User, Order } from './entities';

const dataSource = new DataSource({
  type: 'postgres',
  url: process.env.DATABASE_URL,
  entities: [User, Order],
});

await dataSource.initialize();

const toolset = mountTypeORM(dataSource, policy);
```

## Policy Configuration

### Zod Schema

Policies are validated with Zod:

```typescript
import { z } from 'zod';
import { PolicySchema, FieldAction, WriteAction } from 'ormai';

const policy = PolicySchema.parse({
  models: {
    User: {
      allowed: true,
      fields: {
        id: { action: FieldAction.Allow },
        email: { action: FieldAction.Mask },
        password: { action: FieldAction.Deny },
      },
      scoping: { tenantId: 'principal.tenantId' },
      writePolicy: {
        create: WriteAction.Allow,
        update: WriteAction.Allow,
        delete: WriteAction.Deny,
      },
    },
  },
  budget: {
    maxRows: 1000,
    maxIncludeDepth: 3,
  },
});
```

### Type Safety

Full TypeScript support:

```typescript
import type { Policy, ModelPolicy, FieldPolicy, Principal, RunContext } from 'ormai';

const modelPolicy: ModelPolicy = {
  allowed: true,
  fields: {
    id: { action: 'allow' },
  },
};

const policy: Policy = {
  models: {
    User: modelPolicy,
  },
};
```

## API Reference

### Query

```typescript
interface QueryOptions {
  model: string;
  filters?: FilterClause[];
  select?: string[];
  order?: OrderClause[];
  include?: IncludeClause[];
  limit?: number;
  cursor?: string;
}

const result = await toolset.query(ctx, {
  model: 'Order',
  filters: [
    { field: 'status', op: 'eq', value: 'pending' },
    { field: 'total', op: 'gte', value: 1000 },
  ],
  select: ['id', 'status', 'total'],
  order: [{ field: 'createdAt', direction: 'desc' }],
  include: [{ relation: 'user', select: ['id', 'name'] }],
  limit: 20,
});
```

### Get

```typescript
const result = await toolset.get(ctx, {
  model: 'Order',
  id: 123,
  include: [{ relation: 'items' }],
});
```

### Aggregate

```typescript
const result = await toolset.aggregate(ctx, {
  model: 'Order',
  filters: [{ field: 'status', op: 'eq', value: 'completed' }],
  aggregations: [
    { function: 'count', alias: 'totalOrders' },
    { function: 'sum', field: 'total', alias: 'revenue' },
    { function: 'avg', field: 'total', alias: 'avgOrder' },
  ],
  groupBy: ['status'],
});
```

### Create

```typescript
const result = await toolset.create(ctx, {
  model: 'Order',
  data: {
    status: 'pending',
    total: 5000,
    userId: 'user-123',
  },
});
```

### Update

```typescript
const result = await toolset.update(ctx, {
  model: 'Order',
  id: 123,
  data: {
    status: 'confirmed',
  },
});
```

### Delete

```typescript
const result = await toolset.delete(ctx, {
  model: 'Order',
  id: 123,
});
```

## Express Integration

```typescript
import express from 'express';
import { mountPrisma, Principal, RunContext } from 'ormai';

const app = express();
app.use(express.json());

const toolset = mountPrisma(prisma, policy);

// Middleware to extract context
function getContext(req: express.Request): RunContext {
  return {
    principal: {
      tenantId: req.headers['x-tenant-id'] as string,
      userId: req.headers['x-user-id'] as string,
      roles: (req.headers['x-roles'] as string)?.split(',') || [],
    },
  };
}

// Query endpoint
app.post('/api/query', async (req, res) => {
  try {
    const ctx = getContext(req);
    const result = await toolset.query(ctx, req.body);
    res.json(result);
  } catch (error) {
    res.status(400).json({ error: error.message });
  }
});

// Get endpoint
app.post('/api/get', async (req, res) => {
  try {
    const ctx = getContext(req);
    const result = await toolset.get(ctx, req.body);
    if (!result.success) {
      return res.status(404).json({ error: 'Not found' });
    }
    res.json(result.data);
  } catch (error) {
    res.status(400).json({ error: error.message });
  }
});

app.listen(3000);
```

## Next.js Integration

### API Routes

```typescript
// app/api/query/route.ts
import { NextRequest, NextResponse } from 'next/server';
import { toolset } from '@/lib/ormai';

export async function POST(request: NextRequest) {
  const body = await request.json();

  const ctx = {
    principal: {
      tenantId: request.headers.get('x-tenant-id')!,
      userId: request.headers.get('x-user-id')!,
    },
  };

  try {
    const result = await toolset.query(ctx, body);
    return NextResponse.json(result);
  } catch (error) {
    return NextResponse.json(
      { error: error.message },
      { status: 400 }
    );
  }
}
```

### Server Actions

```typescript
// app/actions.ts
'use server';

import { toolset } from '@/lib/ormai';
import { auth } from '@/lib/auth';

export async function queryOrders(filters: FilterClause[]) {
  const session = await auth();

  const ctx = {
    principal: {
      tenantId: session.user.orgId,
      userId: session.user.id,
    },
  };

  return toolset.query(ctx, {
    model: 'Order',
    filters,
    limit: 50,
  });
}
```

## Audit Logging

```typescript
import { JsonlAuditStore, AuditMiddleware } from 'ormai';

const store = new JsonlAuditStore('./audit.jsonl');
const middleware = new AuditMiddleware(store, {
  includeSnapshots: true,
});

const auditedToolset = middleware.wrap(toolset);
```

## Error Handling

```typescript
import {
  OrmAIError,
  ModelNotAllowedError,
  QueryBudgetExceededError,
} from 'ormai';

try {
  await toolset.query(ctx, { model: 'SecretModel' });
} catch (error) {
  if (error instanceof ModelNotAllowedError) {
    console.log('Model access denied');
  } else if (error instanceof QueryBudgetExceededError) {
    console.log('Query too expensive');
  } else if (error instanceof OrmAIError) {
    console.log(`OrmAI error: ${error.code}`);
  }
}
```

## Testing

```typescript
import { describe, it, expect, beforeEach } from 'vitest';
import { mountPrisma } from 'ormai';
import { prismaMock } from './mocks';

describe('OrmAI Integration', () => {
  const toolset = mountPrisma(prismaMock, policy);

  const ctx = {
    principal: {
      tenantId: 'test-tenant',
      userId: 'test-user',
    },
  };

  it('should query with tenant scope', async () => {
    const result = await toolset.query(ctx, {
      model: 'Order',
      limit: 10,
    });

    expect(result.success).toBe(true);
    // Verify tenant filter was applied
    expect(prismaMock.order.findMany).toHaveBeenCalledWith(
      expect.objectContaining({
        where: expect.objectContaining({
          tenantId: 'test-tenant',
        }),
      })
    );
  });

  it('should reject forbidden model', async () => {
    await expect(
      toolset.query(ctx, { model: 'SecretModel' })
    ).rejects.toThrow(ModelNotAllowedError);
  });
});
```

## Feature Comparison

| Feature | Python | TypeScript |
|---------|--------|------------|
| Query DSL | ✅ | ✅ |
| Policies | ✅ | ✅ |
| Field Actions | ✅ | ✅ |
| Scoping | ✅ | ✅ |
| Write Operations | ✅ | ✅ |
| Audit Logging | ✅ | ✅ |
| Deferred Execution | ✅ | ✅ |
| MCP Server | ✅ | ✅ |
| Code Generation | ✅ | ⚠️ Partial |
| Eval Framework | ✅ | ⚠️ Partial |

## Migration from Python

The TypeScript API mirrors Python closely:

```python
# Python
result = await toolset.query(
    ctx,
    model="Order",
    filters=[{"field": "status", "op": "eq", "value": "pending"}],
    limit=10,
)
```

```typescript
// TypeScript
const result = await toolset.query(ctx, {
  model: 'Order',
  filters: [{ field: 'status', op: 'eq', value: 'pending' }],
  limit: 10,
});
```

## Next Steps

- [FastAPI Integration](fastapi.md) - Python web integration
- [LangGraph Integration](langgraph.md) - AI agent integration
- [Multi-Tenant Setup](../guides/multi-tenant.md) - Tenant isolation
