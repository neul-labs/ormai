/**
 * Tests for Drizzle adapter
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
    User: {
      name: 'User',
      tableName: 'users',
      fields: {
        id: { name: 'id', fieldType: 'string', nullable: false, primaryKey: true },
        tenantId: { name: 'tenantId', fieldType: 'string', nullable: false, primaryKey: false },
        name: { name: 'name', fieldType: 'string', nullable: false, primaryKey: false },
        role: { name: 'role', fieldType: 'string', nullable: true, primaryKey: false },
      },
      relations: {},
      primaryKey: 'id',
    },
  },
};

const testPolicy = PolicySchema.parse({
  models: {
    User: {
      allowed: true,
      readable: true,
      writable: true,
      fields: {
        id: { action: 'allow' },
        tenantId: { action: 'allow' },
        name: { action: 'allow' },
        role: { action: 'deny' },
      },
      rowPolicy: {
        tenantScopeField: 'tenantId',
        ownershipScopeField: 'userId',
      },
      writePolicy: {
        enabled: true,
        allowCreate: true,
        allowUpdate: true,
        allowDelete: true,
        allowBulk: true,
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
    tenantId: 'tenant-abc',
    userId: 'user-789',
    db: {},
  });
}

describe('BaseOrmAdapter - Drizzle (AdapterNotImplementedError)', () => {
  describe('compile methods', () => {
    it('should throw AdapterNotImplementedError for unimplemented compileUpdate', () => {
      class TestAdapter extends BaseOrmAdapter {
        introspect() {
          return Promise.resolve(testSchema);
        }
        compileQuery() {
          return createCompiledQuery({}, { model: 'User', take: 10 });
        }
        compileGet() {
          return createCompiledQuery({}, { model: 'User', id: '123' });
        }
        compileAggregate() {
          return createCompiledQuery({}, { model: 'User', operation: 'count' });
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
          { model: 'User', id: '123', data: { name: 'Updated' } },
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
          return createCompiledQuery({}, { model: 'User', take: 10 });
        }
        compileGet() {
          return createCompiledQuery({}, { model: 'User', id: '123' });
        }
        compileAggregate() {
          return createCompiledQuery({}, { model: 'User', operation: 'count' });
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
          { model: 'User', id: '123' },
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
          return createCompiledQuery({}, { model: 'User', take: 10 });
        }
        compileGet() {
          return createCompiledQuery({}, { model: 'User', id: '123' });
        }
        compileAggregate() {
          return createCompiledQuery({}, { model: 'User', operation: 'count' });
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
          { model: 'User', ids: ['1', '2', '3'], data: { role: 'admin' } },
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
          return createCompiledQuery({}, { model: 'User', take: 10 });
        }
        compileGet() {
          return createCompiledQuery({}, { model: 'User', id: '123' });
        }
        compileAggregate() {
          return createCompiledQuery({}, { model: 'User', operation: 'count' });
        }
        compileCreate() {
          return createCompiledMutation({}, { model: 'User', data: { name: 'John' } });
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
      const compiled = createCompiledMutation({}, { model: 'User', data: { name: 'John' } });

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
          return createCompiledQuery({}, { model: 'User', take: 10 });
        }
        compileGet() {
          return createCompiledQuery({}, { model: 'User', id: '123' });
        }
        compileAggregate() {
          return createCompiledQuery({}, { model: 'User', operation: 'count' });
        }
        compileUpdate() {
          return createCompiledMutation({}, { model: 'User', id: '123', data: { name: 'Updated' } });
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
      const compiled = createCompiledMutation({}, { model: 'User', id: '123', data: { name: 'Updated' } });

      let errorThrown = false;
      try {
        await adapter.executeUpdate(compiled, ctx);
      } catch (error: any) {
        errorThrown = true;
        expect(error.name).toBe('AdapterNotImplementedError');
      }
      expect(errorThrown).toBe(true);
    });
  });
});
