/**
 * Tests for Prisma adapter
 */

import { describe, it, expect, vi } from 'vitest';
import { PolicySchema } from '../../src/policy/models.js';
import type { SchemaMetadata } from '../../src/core/types.js';
import type { RunContext } from '../../src/core/context.js';
import { createContext } from '../../src/core/context.js';
import { createCompiledQuery, createCompiledMutation, BaseOrmAdapter } from '../../src/adapters/base.js';
import { AdapterNotImplementedError } from '../../src/core/errors.js';

// Test schema
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
      },
      relations: {},
      primaryKey: 'id',
    },
  },
};

const testPolicy = PolicySchema.parse({
  models: {
    Customer: {
      allowed: true,
      readable: true,
      writable: true,
      fields: {
        id: { action: 'allow' },
        tenantId: { action: 'allow' },
        name: { action: 'allow' },
        email: { action: 'mask', maskPattern: '****' },
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
        readonlyFields: [],
      },
    },
  },
  defaultRowPolicy: {
    tenantScopeField: 'tenantId',
    requireScope: false, // Changed to false for tests
  },
});

function createTestContext(tenantId?: string): RunContext {
  return createContext({
    tenantId: tenantId ?? 'tenant-123',
    userId: 'user-456',
    db: {},
  });
}

describe('BaseOrmAdapter - AdapterNotImplementedError', () => {
  describe('compile methods', () => {
    it('should throw AdapterNotImplementedError for unimplemented compileCreate', () => {
      class TestAdapter extends BaseOrmAdapter {
        introspect() {
          return Promise.resolve(testSchema);
        }
        compileQuery() {
          return createCompiledQuery({}, { model: 'Customer', take: 10 });
        }
        compileGet() {
          return createCompiledQuery({}, { model: 'Customer', id: '123' });
        }
        compileAggregate() {
          return createCompiledQuery({}, { model: 'Customer', operation: 'count' });
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
          { model: 'Customer', data: { name: 'John' } },
          ctx,
          testPolicy,
          testSchema
        )
      ).toThrow(AdapterNotImplementedError);
    });

    it('should throw AdapterNotImplementedError for unimplemented compileUpdate', () => {
      class TestAdapter extends BaseOrmAdapter {
        introspect() {
          return Promise.resolve(testSchema);
        }
        compileQuery() {
          return createCompiledQuery({}, { model: 'Customer', take: 10 });
        }
        compileGet() {
          return createCompiledQuery({}, { model: 'Customer', id: '123' });
        }
        compileAggregate() {
          return createCompiledQuery({}, { model: 'Customer', operation: 'count' });
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
        adapter.compileUpdate(
          { model: 'Customer', id: '123', data: { name: 'Updated' } },
          ctx,
          testPolicy,
          testSchema
        )
      ).toThrow(AdapterNotImplementedError);
    });

    it('should throw AdapterNotImplementedError for unimplemented compileDelete', () => {
      class TestAdapter extends BaseOrmAdapter {
        introspect() {
          return Promise.resolve(testSchema);
        }
        compileQuery() {
          return createCompiledQuery({}, { model: 'Customer', take: 10 });
        }
        compileGet() {
          return createCompiledQuery({}, { model: 'Customer', id: '123' });
        }
        compileAggregate() {
          return createCompiledQuery({}, { model: 'Customer', operation: 'count' });
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
        adapter.compileDelete(
          { model: 'Customer', id: '123' },
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
          return createCompiledQuery({}, { model: 'Customer', take: 10 });
        }
        compileGet() {
          return createCompiledQuery({}, { model: 'Customer', id: '123' });
        }
        compileAggregate() {
          return createCompiledQuery({}, { model: 'Customer', operation: 'count' });
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
          { model: 'Customer', ids: ['1', '2', '3'], data: { name: 'Updated' } },
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
          return createCompiledQuery({}, { model: 'Customer', take: 10 });
        }
        compileGet() {
          return createCompiledQuery({}, { model: 'Customer', id: '123' });
        }
        compileAggregate() {
          return createCompiledQuery({}, { model: 'Customer', operation: 'count' });
        }
        compileCreate() {
          return createCompiledMutation({}, { model: 'Customer', data: { name: 'John' } });
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
      const compiled = createCompiledMutation({}, { model: 'Customer', data: { name: 'John' } });

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
          return createCompiledQuery({}, { model: 'Customer', take: 10 });
        }
        compileGet() {
          return createCompiledQuery({}, { model: 'Customer', id: '123' });
        }
        compileAggregate() {
          return createCompiledQuery({}, { model: 'Customer', operation: 'count' });
        }
        compileUpdate() {
          return createCompiledMutation({}, { model: 'Customer', id: '123', data: { name: 'Updated' } });
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
      const compiled = createCompiledMutation({}, { model: 'Customer', id: '123', data: { name: 'Updated' } });

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
          return createCompiledQuery({}, { model: 'Customer', take: 10 });
        }
        compileGet() {
          return createCompiledQuery({}, { model: 'Customer', id: '123' });
        }
        compileAggregate() {
          return createCompiledQuery({}, { model: 'Customer', operation: 'count' });
        }
        compileDelete() {
          return createCompiledMutation({}, { model: 'Customer', id: '123' });
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
      const compiled = createCompiledMutation({}, { model: 'Customer', id: '123' });

      let errorThrown = false;
      try {
        await adapter.executeDelete(compiled, ctx);
      } catch (error: any) {
        errorThrown = true;
        expect(error.name).toBe('AdapterNotImplementedError');
      }
      expect(errorThrown).toBe(true);
    });

    it('should throw AdapterNotImplementedError for unimplemented executeBulkUpdate', async () => {
      class TestAdapter extends BaseOrmAdapter {
        introspect() {
          return Promise.resolve(testSchema);
        }
        compileQuery() {
          return createCompiledQuery({}, { model: 'Customer', take: 10 });
        }
        compileGet() {
          return createCompiledQuery({}, { model: 'Customer', id: '123' });
        }
        compileAggregate() {
          return createCompiledQuery({}, { model: 'Customer', operation: 'count' });
        }
        compileBulkUpdate() {
          return createCompiledMutation({}, { model: 'Customer', ids: ['1', '2'], data: { name: 'Updated' } });
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
      const compiled = createCompiledMutation({}, { model: 'Customer', ids: ['1', '2'], data: { name: 'Updated' } });

      let errorThrown = false;
      try {
        await adapter.executeBulkUpdate(compiled, ctx);
      } catch (error: any) {
        errorThrown = true;
        expect(error.name).toBe('AdapterNotImplementedError');
      }
      expect(errorThrown).toBe(true);
    });
  });

  describe('AdapterNotImplementedError properties', () => {
    it('should have correct error name and message', () => {
      try {
        class TestAdapter extends BaseOrmAdapter {
          introspect() {
            return Promise.resolve(testSchema);
          }
          compileQuery() {
            return createCompiledQuery({}, { model: 'Customer', take: 10 });
          }
          compileGet() {
            return createCompiledQuery({}, { model: 'Customer', id: '123' });
          }
          compileAggregate() {
            return createCompiledQuery({}, { model: 'Customer', operation: 'count' });
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
        adapter.compileCreate({ model: 'Customer', data: {} }, createTestContext(), testPolicy, testSchema);
      } catch (error: any) {
        expect(error.name).toBe('AdapterNotImplementedError');
        expect(error.message).toContain('Create');
        expect(error.message).toContain('TestAdapter');
      }
    });
  });
});
