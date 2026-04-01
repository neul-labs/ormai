/**
 * Tests for tools/generic.ts
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import {
  DescribeSchemaTool,
  QueryTool,
  GetTool,
  AggregateTool,
  CreateTool,
  UpdateTool,
  DeleteTool,
  BulkUpdateTool,
  createGenericTools,
} from '../../src/tools/generic.js';
import { PolicySchema, type Policy } from '../../src/policy/models.js';
import type { SchemaMetadata } from '../../src/core/types.js';
import { createContext, type RunContext } from '../../src/core/context.js';
import type { OrmAdapter, CompiledQuery, CompiledGet, CompiledAggregate, CompiledCreate, CompiledUpdate, CompiledDelete, CompiledBulkUpdate } from '../../src/adapters/base.js';

// Test fixtures
const testSchema: SchemaMetadata = {
  models: {
    Customer: {
      name: 'Customer',
      tableName: 'customers',
      fields: {
        id: { name: 'id', fieldType: 'string', nullable: false, primaryKey: true },
        tenantId: { name: 'tenantId', fieldType: 'string', nullable: false, primaryKey: false },
        name: { name: 'name', fieldType: 'string', nullable: false, primaryKey: false },
        email: { name: 'email', fieldType: 'string', nullable: true, primaryKey: false },
        password: { name: 'password', fieldType: 'string', nullable: false, primaryKey: false },
      },
      relations: {
        orders: {
          name: 'orders',
          relationType: 'one_to_many',
          targetModel: 'Order',
        },
      },
      primaryKey: 'id',
    },
    Order: {
      name: 'Order',
      tableName: 'orders',
      fields: {
        id: { name: 'id', fieldType: 'string', nullable: false, primaryKey: true },
        total: { name: 'total', fieldType: 'float', nullable: false, primaryKey: false },
      },
      relations: {},
      primaryKey: 'id',
    },
    Secret: {
      name: 'Secret',
      tableName: 'secrets',
      fields: {
        id: { name: 'id', fieldType: 'string', nullable: false, primaryKey: true },
      },
      relations: {},
      primaryKey: 'id',
    },
  },
};

const testPolicy: Policy = PolicySchema.parse({
  models: {
    Customer: {
      allowed: true,
      readable: true,
      writable: false,
      fields: {
        password: { action: 'deny' },
      },
      relations: {
        orders: { allowed: true, maxDepth: 1 },
      },
    },
    Order: {
      allowed: true,
      readable: true,
      writable: true,
    },
    Secret: {
      allowed: false,
    },
  },
  writesEnabled: true,
});

function createTestContext(): RunContext {
  return createContext({
    tenantId: 'tenant-123',
    userId: 'user-456',
    db: {},
  });
}

// Mock adapter
function createMockAdapter(): OrmAdapter {
  return {
    introspect: vi.fn().mockResolvedValue(testSchema),
    compileQuery: vi.fn().mockReturnValue({
      query: {},
      request: { model: 'Customer', take: 25 },
      selectFields: ['id', 'name'],
      injectedFilters: [],
      policyDecisions: [],
    }),
    executeQuery: vi.fn().mockResolvedValue({
      data: [{ id: '1', name: 'John' }],
      count: 1,
      hasMore: false,
    }),
    compileGet: vi.fn().mockReturnValue({
      query: {},
      request: { model: 'Customer', id: '1' },
      selectFields: ['id', 'name'],
      injectedFilters: [],
      policyDecisions: [],
    }),
    executeGet: vi.fn().mockResolvedValue({
      data: { id: '1', name: 'John' },
      found: true,
    }),
    compileAggregate: vi.fn().mockReturnValue({
      query: {},
      request: { model: 'Order', operation: 'count' },
      injectedFilters: [],
      policyDecisions: [],
    }),
    executeAggregate: vi.fn().mockResolvedValue({
      value: 42,
      operation: 'count',
    }),
    compileCreate: vi.fn().mockReturnValue({
      query: {},
      request: { model: 'Order', data: { total: 100 } },
      injectedData: {},
      policyDecisions: [],
    }),
    executeCreate: vi.fn().mockResolvedValue({
      data: { id: '1', total: 100 },
      created: true,
    }),
    compileUpdate: vi.fn().mockReturnValue({
      query: {},
      request: { model: 'Order', id: '1', data: { total: 200 } },
      injectedFilters: [],
      policyDecisions: [],
    }),
    executeUpdate: vi.fn().mockResolvedValue({
      data: { id: '1', total: 200 },
      updated: true,
      previousData: { id: '1', total: 100 },
    }),
    compileDelete: vi.fn().mockReturnValue({
      query: {},
      request: { model: 'Order', id: '1' },
      injectedFilters: [],
      policyDecisions: [],
    }),
    executeDelete: vi.fn().mockResolvedValue({
      deleted: true,
      previousData: { id: '1', total: 200 },
    }),
    compileBulkUpdate: vi.fn().mockReturnValue({
      query: {},
      request: { model: 'Order', ids: ['1', '2'], data: { status: 'shipped' } },
      injectedFilters: [],
      policyDecisions: [],
    }),
    executeBulkUpdate: vi.fn().mockResolvedValue({
      updated: 2,
      ids: ['1', '2'],
    }),
    transaction: vi.fn().mockImplementation(async (_ctx, fn) => fn()),
  } as unknown as OrmAdapter;
}

describe('DescribeSchemaTool', () => {
  it('should have correct name and description', () => {
    const tool = new DescribeSchemaTool(testSchema, testPolicy);

    expect(tool.name).toBe('db.describe_schema');
    expect(tool.description).toContain('schema');
  });

  it('should return all allowed models when no model specified', async () => {
    const tool = new DescribeSchemaTool(testSchema, testPolicy);
    const ctx = createTestContext();

    const result = await tool.execute({}, ctx);

    expect(Object.keys(result.models)).toContain('Customer');
    expect(Object.keys(result.models)).toContain('Order');
    expect(Object.keys(result.models)).not.toContain('Secret');
  });

  it('should return specific model when requested', async () => {
    const tool = new DescribeSchemaTool(testSchema, testPolicy);
    const ctx = createTestContext();

    const result = await tool.execute({ model: 'Customer' }, ctx);

    expect(Object.keys(result.models)).toEqual(['Customer']);
  });

  it('should filter out denied fields', async () => {
    const tool = new DescribeSchemaTool(testSchema, testPolicy);
    const ctx = createTestContext();

    const result = await tool.execute({ model: 'Customer' }, ctx);

    expect(result.models.Customer.fields).not.toHaveProperty('password');
    expect(result.models.Customer.fields).toHaveProperty('name');
  });

  it('should include relation information', async () => {
    const tool = new DescribeSchemaTool(testSchema, testPolicy);
    const ctx = createTestContext();

    const result = await tool.execute({ model: 'Customer' }, ctx);

    expect(result.models.Customer.relations).toHaveProperty('orders');
    expect(result.models.Customer.relations.orders.target).toBe('Order');
  });
});

describe('QueryTool', () => {
  it('should have correct name and description', () => {
    const adapter = createMockAdapter();
    const tool = new QueryTool(adapter, testPolicy, testSchema);

    expect(tool.name).toBe('db.query');
    expect(tool.description).toContain('Query');
  });

  it('should execute query through adapter', async () => {
    const adapter = createMockAdapter();
    const tool = new QueryTool(adapter, testPolicy, testSchema);
    const ctx = createTestContext();

    const result = await tool.execute({ model: 'Customer', take: 10 }, ctx);

    expect(adapter.compileQuery).toHaveBeenCalled();
    expect(adapter.executeQuery).toHaveBeenCalled();
    expect(result.data).toHaveLength(1);
  });

  it('should pass filters to adapter', async () => {
    const adapter = createMockAdapter();
    const tool = new QueryTool(adapter, testPolicy, testSchema);
    const ctx = createTestContext();

    await tool.execute({
      model: 'Customer',
      where: [{ field: 'name', op: 'eq', value: 'John' }],
      take: 10,
    }, ctx);

    expect(adapter.compileQuery).toHaveBeenCalledWith(
      expect.objectContaining({
        where: expect.arrayContaining([
          expect.objectContaining({ field: 'name', op: 'eq' }),
        ]),
      }),
      expect.anything(),
      expect.anything(),
      expect.anything()
    );
  });
});

describe('GetTool', () => {
  it('should have correct name and description', () => {
    const adapter = createMockAdapter();
    const tool = new GetTool(adapter, testPolicy, testSchema);

    expect(tool.name).toBe('db.get');
    expect(tool.description).toContain('single record');
  });

  it('should execute get through adapter', async () => {
    const adapter = createMockAdapter();
    const tool = new GetTool(adapter, testPolicy, testSchema);
    const ctx = createTestContext();

    const result = await tool.execute({ model: 'Customer', id: '123' }, ctx);

    expect(adapter.compileGet).toHaveBeenCalled();
    expect(adapter.executeGet).toHaveBeenCalled();
    expect(result.found).toBe(true);
  });
});

describe('AggregateTool', () => {
  it('should have correct name and description', () => {
    const adapter = createMockAdapter();
    const tool = new AggregateTool(adapter, testPolicy, testSchema);

    expect(tool.name).toBe('db.aggregate');
    expect(tool.description).toContain('aggregation');
  });

  it('should execute aggregate through adapter', async () => {
    const adapter = createMockAdapter();
    const tool = new AggregateTool(adapter, testPolicy, testSchema);
    const ctx = createTestContext();

    const result = await tool.execute({
      model: 'Order',
      operation: 'count',
    }, ctx);

    expect(adapter.compileAggregate).toHaveBeenCalled();
    expect(adapter.executeAggregate).toHaveBeenCalled();
    expect(result.value).toBe(42);
  });
});

describe('CreateTool', () => {
  it('should have correct name and description', () => {
    const adapter = createMockAdapter();
    const tool = new CreateTool(adapter, testPolicy, testSchema);

    expect(tool.name).toBe('db.create');
    expect(tool.description).toContain('Create');
  });

  it('should execute create through adapter', async () => {
    const adapter = createMockAdapter();
    const tool = new CreateTool(adapter, testPolicy, testSchema);
    const ctx = createTestContext();

    const result = await tool.execute({
      model: 'Order',
      data: { total: 100 },
    }, ctx);

    expect(adapter.compileCreate).toHaveBeenCalled();
    expect(adapter.executeCreate).toHaveBeenCalled();
    expect(result.created).toBe(true);
  });
});

describe('UpdateTool', () => {
  it('should have correct name and description', () => {
    const adapter = createMockAdapter();
    const tool = new UpdateTool(adapter, testPolicy, testSchema);

    expect(tool.name).toBe('db.update');
    expect(tool.description).toContain('Update');
  });

  it('should execute update through adapter', async () => {
    const adapter = createMockAdapter();
    const tool = new UpdateTool(adapter, testPolicy, testSchema);
    const ctx = createTestContext();

    const result = await tool.execute({
      model: 'Order',
      id: '123',
      data: { total: 200 },
    }, ctx);

    expect(adapter.compileUpdate).toHaveBeenCalled();
    expect(adapter.executeUpdate).toHaveBeenCalled();
    expect(result.updated).toBe(true);
  });
});

describe('DeleteTool', () => {
  it('should have correct name and description', () => {
    const adapter = createMockAdapter();
    const tool = new DeleteTool(adapter, testPolicy, testSchema);

    expect(tool.name).toBe('db.delete');
    expect(tool.description).toContain('Delete');
  });

  it('should execute delete through adapter', async () => {
    const adapter = createMockAdapter();
    const tool = new DeleteTool(adapter, testPolicy, testSchema);
    const ctx = createTestContext();

    const result = await tool.execute({
      model: 'Order',
      id: '123',
    }, ctx);

    expect(adapter.compileDelete).toHaveBeenCalled();
    expect(adapter.executeDelete).toHaveBeenCalled();
    expect(result.deleted).toBe(true);
  });
});

describe('BulkUpdateTool', () => {
  it('should have correct name and description', () => {
    const adapter = createMockAdapter();
    const tool = new BulkUpdateTool(adapter, testPolicy, testSchema);

    expect(tool.name).toBe('db.bulk_update');
    expect(tool.description).toContain('multiple records');
  });

  it('should execute bulk update through adapter', async () => {
    const adapter = createMockAdapter();
    const tool = new BulkUpdateTool(adapter, testPolicy, testSchema);
    const ctx = createTestContext();

    const result = await tool.execute({
      model: 'Order',
      ids: ['1', '2', '3'],
      data: { status: 'shipped' },
    }, ctx);

    expect(adapter.compileBulkUpdate).toHaveBeenCalled();
    expect(adapter.executeBulkUpdate).toHaveBeenCalled();
    expect(result.updated).toBe(2);
  });
});

describe('createGenericTools', () => {
  it('should create read-only tools by default', () => {
    const adapter = createMockAdapter();
    const readOnlyPolicy = PolicySchema.parse({
      models: { Customer: { allowed: true } },
      writesEnabled: false,
    });

    const tools = createGenericTools({
      adapter,
      policy: readOnlyPolicy,
      schema: testSchema,
    });

    const toolNames = tools.map(t => t.name);
    expect(toolNames).toContain('db.describe_schema');
    expect(toolNames).toContain('db.query');
    expect(toolNames).toContain('db.get');
    expect(toolNames).toContain('db.aggregate');
    expect(toolNames).not.toContain('db.create');
    expect(toolNames).not.toContain('db.update');
    expect(toolNames).not.toContain('db.delete');
  });

  it('should include write tools when policy enables writes', () => {
    const adapter = createMockAdapter();

    const tools = createGenericTools({
      adapter,
      policy: testPolicy,
      schema: testSchema,
    });

    const toolNames = tools.map(t => t.name);
    expect(toolNames).toContain('db.create');
    expect(toolNames).toContain('db.update');
    expect(toolNames).toContain('db.delete');
    expect(toolNames).toContain('db.bulk_update');
  });

  it('should include write tools when includeWrite is true', () => {
    const adapter = createMockAdapter();
    const readOnlyPolicy = PolicySchema.parse({
      models: { Customer: { allowed: true } },
      writesEnabled: false,
    });

    const tools = createGenericTools({
      adapter,
      policy: readOnlyPolicy,
      schema: testSchema,
      includeWrite: true,
    });

    const toolNames = tools.map(t => t.name);
    expect(toolNames).toContain('db.create');
    expect(toolNames).toContain('db.update');
  });
});
