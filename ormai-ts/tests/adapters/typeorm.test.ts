/**
 * Tests for TypeORM adapter
 */

import { describe, it, expect } from 'vitest';
import { PolicySchema } from '../../src/policy/models.js';
import type { SchemaMetadata } from '../../src/core/types.js';
import type { RunContext } from '../../src/core/context.js';
import { createContext } from '../../src/core/context.js';
import { createCompiledQuery, createCompiledMutation, BaseOrmAdapter } from '../../src/adapters/base.js';
import { AdapterNotImplementedError } from '../../src/core/errors.js';

// Test schema
const testSchema: SchemaMetadata = {
  models: {
    Product: {
      name: 'Product',
      tableName: 'products',
      fields: {
        id: { name: 'id', fieldType: 'string', nullable: false, primaryKey: true },
        tenantId: { name: 'tenantId', fieldType: 'string', nullable: false, primaryKey: false },
        name: { name: 'name', fieldType: 'string', nullable: false, primaryKey: false },
        price: { name: 'price', fieldType: 'number', nullable: false, primaryKey: false },
        stock: { name: 'stock', fieldType: 'number', nullable: true, primaryKey: false },
      },
      relations: {},
      primaryKey: 'id',
    },
  },
};

const testPolicy = PolicySchema.parse({
  models: {
    Product: {
      allowed: true,
      readable: true,
      writable: true,
      fields: {
        id: { action: 'allow' },
        tenantId: { action: 'allow' },
        name: { action: 'allow' },
        price: { action: 'allow' },
        stock: { action: 'mask', maskPattern: '****' },
      },
      rowPolicy: {
        tenantScopeField: 'tenantId',
      },
      writePolicy: {
        enabled: true,
        allowCreate: true,
        allowUpdate: true,
        allowDelete: true,
        allowBulk: false,
        readonlyFields: ['id'],
      },
    },
  },
  defaultRowPolicy: {
    tenantScopeField: 'tenantId',
    requireScope: false,
  },
});

function createTestContext(): RunContext {
  return createContext({
    tenantId: 'tenant-xyz',
    userId: 'admin-001',
    db: {},
  });
}

describe('BaseOrmAdapter - TypeORM (AdapterNotImplementedError)', () => {
  describe('compile methods', () => {
    it('should throw AdapterNotImplementedError for unimplemented compileCreate', () => {
      class TestAdapter extends BaseOrmAdapter {
        introspect() {
          return Promise.resolve(testSchema);
        }
        compileQuery() {
          return createCompiledQuery({}, { model: 'Product', take: 10 });
        }
        compileGet() {
          return createCompiledQuery({}, { model: 'Product', id: '123' });
        }
        compileAggregate() {
          return createCompiledQuery({}, { model: 'Product', operation: 'count' });
        }
        executeQuery() {
          return Promise.resolve({ data: [], count: 0, hasMore: false });
        }
        executeGet() {
          return Promise.resolve({ data: null, found: false });
        }
        executeAggregate() {
          return Promise.resolve({ value: 0, operation: 'count' });
        }
        transaction() {
          return Promise.resolve({} as any);
        }
      }

      const adapter = new TestAdapter();
      const ctx = createTestContext();

      expect(() =>
        adapter.compileCreate(
          { model: 'Product', data: { name: 'New Product', price: 99.99 } },
          ctx,
          testPolicy,
          testSchema
        )
      ).toThrow(AdapterNotImplementedError);
    });

    it('should throw AdapterNotImplementedError for unimplemented compileBulkUpdate', () => {
      class TestAdapter extends BaseOrmAdapter {
        introspect() {
          return Promise.resolve(testSchema);
        }
        compileQuery() {
          return createCompiledQuery({}, { model: 'Product', take: 10 });
        }
        compileGet() {
          return createCompiledQuery({}, { model: 'Product', id: '123' });
        }
        compileAggregate() {
          return createCompiledQuery({}, { model: 'Product', operation: 'count' });
        }
        executeQuery() {
          return Promise.resolve({ data: [], count: 0, hasMore: false });
        }
        executeGet() {
          return Promise.resolve({ data: null, found: false });
        }
        executeAggregate() {
          return Promise.resolve({ value: 0, operation: 'count' });
        }
        transaction() {
          return Promise.resolve({} as any);
        }
      }

      const adapter = new TestAdapter();
      const ctx = createTestContext();

      expect(() =>
        adapter.compileBulkUpdate(
          { model: 'Product', ids: ['1', '2', '3'], data: { stock: 0 } },
          ctx,
          testPolicy,
          testSchema
        )
      ).toThrow(AdapterNotImplementedError);
    });
  });

  describe('execute methods', () => {
    it('should throw AdapterNotImplementedError for unimplemented executeCreate', async () => {
      class TestAdapter extends BaseOrmAdapter {
        introspect() {
          return Promise.resolve(testSchema);
        }
        compileQuery() {
          return createCompiledQuery({}, { model: 'Product', take: 10 });
        }
        compileGet() {
          return createCompiledQuery({}, { model: 'Product', id: '123' });
        }
        compileAggregate() {
          return createCompiledQuery({}, { model: 'Product', operation: 'count' });
        }
        compileCreate() {
          return createCompiledMutation({}, { model: 'Product', data: { name: 'New' } });
        }
        executeQuery() {
          return Promise.resolve({ data: [], count: 0, hasMore: false });
        }
        executeGet() {
          return Promise.resolve({ data: null, found: false });
        }
        executeAggregate() {
          return Promise.resolve({ value: 0, operation: 'count' });
        }
        transaction() {
          return Promise.resolve({} as any);
        }
      }

      const adapter = new TestAdapter();
      const ctx = createTestContext();
      const compiled = createCompiledMutation({}, { model: 'Product', data: { name: 'New' } });

      let errorThrown = false;
      try {
        await adapter.executeCreate(compiled, ctx);
      } catch (error: any) {
        errorThrown = true;
        expect(error.name).toBe('AdapterNotImplementedError');
      }
      expect(errorThrown).toBe(true);
    });

    it('should throw AdapterNotImplementedError for unimplemented executeUpdate', async () => {
      class TestAdapter extends BaseOrmAdapter {
        introspect() {
          return Promise.resolve(testSchema);
        }
        compileQuery() {
          return createCompiledQuery({}, { model: 'Product', take: 10 });
        }
        compileGet() {
          return createCompiledQuery({}, { model: 'Product', id: '123' });
        }
        compileAggregate() {
          return createCompiledQuery({}, { model: 'Product', operation: 'count' });
        }
        compileUpdate() {
          return createCompiledMutation({}, { model: 'Product', id: '123', data: { name: 'Updated' } });
        }
        executeQuery() {
          return Promise.resolve({ data: [], count: 0, hasMore: false });
        }
        executeGet() {
          return Promise.resolve({ data: null, found: false });
        }
        executeAggregate() {
          return Promise.resolve({ value: 0, operation: 'count' });
        }
        transaction() {
          return Promise.resolve({} as any);
        }
      }

      const adapter = new TestAdapter();
      const ctx = createTestContext();
      const compiled = createCompiledMutation({}, { model: 'Product', id: '123', data: { name: 'Updated' } });

      let errorThrown = false;
      try {
        await adapter.executeUpdate(compiled, ctx);
      } catch (error: any) {
        errorThrown = true;
        expect(error.name).toBe('AdapterNotImplementedError');
      }
      expect(errorThrown).toBe(true);
    });

    it('should throw AdapterNotImplementedError for unimplemented executeDelete', async () => {
      class TestAdapter extends BaseOrmAdapter {
        introspect() {
          return Promise.resolve(testSchema);
        }
        compileQuery() {
          return createCompiledQuery({}, { model: 'Product', take: 10 });
        }
        compileGet() {
          return createCompiledQuery({}, { model: 'Product', id: '123' });
        }
        compileAggregate() {
          return createCompiledQuery({}, { model: 'Product', operation: 'count' });
        }
        compileDelete() {
          return createCompiledMutation({}, { model: 'Product', id: '123' });
        }
        executeQuery() {
          return Promise.resolve({ data: [], count: 0, hasMore: false });
        }
        executeGet() {
          return Promise.resolve({ data: null, found: false });
        }
        executeAggregate() {
          return Promise.resolve({ value: 0, operation: 'count' });
        }
        transaction() {
          return Promise.resolve({} as any);
        }
      }

      const adapter = new TestAdapter();
      const ctx = createTestContext();
      const compiled = createCompiledMutation({}, { model: 'Product', id: '123' });

      let errorThrown = false;
      try {
        await adapter.executeDelete(compiled, ctx);
      } catch (error: any) {
        errorThrown = true;
        expect(error.name).toBe('AdapterNotImplementedError');
      }
      expect(errorThrown).toBe(true);
    });
  });
});
