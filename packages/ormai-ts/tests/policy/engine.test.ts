/**
 * Tests for policy/engine.ts
 */

import { describe, it, expect } from 'vitest';
import { PolicyEngine, PolicyDecision } from '../../src/policy/engine.js';
import { PolicySchema, type Policy } from '../../src/policy/models.js';
import type { SchemaMetadata } from '../../src/core/types.js';
import { createContext } from '../../src/core/context.js';
import {
  ModelNotAllowedError,
  FieldNotAllowedError,
  TenantScopeRequiredError,
  WriteDisabledError,
} from '../../src/core/errors.js';

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
        tenantId: { name: 'tenantId', fieldType: 'string', nullable: false, primaryKey: false },
        customerId: { name: 'customerId', fieldType: 'string', nullable: false, primaryKey: false },
        total: { name: 'total', fieldType: 'float', nullable: false, primaryKey: false },
        status: { name: 'status', fieldType: 'string', nullable: false, primaryKey: false },
      },
      relations: {
        customer: {
          name: 'customer',
          relationType: 'many_to_one',
          targetModel: 'Customer',
        },
      },
      primaryKey: 'id',
    },
    Secret: {
      name: 'Secret',
      tableName: 'secrets',
      fields: {
        id: { name: 'id', fieldType: 'string', nullable: false, primaryKey: true },
        value: { name: 'value', fieldType: 'string', nullable: false, primaryKey: false },
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
        email: { action: 'mask' },
      },
      relations: {
        orders: { allowed: true, maxDepth: 1 },
      },
      rowPolicy: {
        tenantScopeField: 'tenantId',
      },
    },
    Order: {
      allowed: true,
      readable: true,
      writable: true,
      writePolicy: {
        enabled: true,
        allowCreate: true,
        allowUpdate: true,
        allowDelete: false,
        maxAffectedRows: 1,
      },
      rowPolicy: {
        tenantScopeField: 'tenantId',
      },
    },
    Secret: {
      allowed: false,
    },
  },
  defaultBudget: {
    maxRows: 100,
    maxIncludesDepth: 2,
  },
  defaultRowPolicy: {
    tenantScopeField: 'tenantId',
    requireScope: true,
  },
  requireTenantScope: true,
  writesEnabled: true,
});

function createTestContext(tenantId = 'tenant-123', userId = 'user-456') {
  return createContext({
    tenantId,
    userId,
    db: {},
  });
}

describe('PolicyEngine', () => {
  describe('validateQuery', () => {
    it('should validate query for allowed model', () => {
      const engine = new PolicyEngine(testPolicy, testSchema);
      const ctx = createTestContext();

      const decision = engine.validateQuery({
        model: 'Customer',
        take: 10,
      }, ctx);

      expect(decision).toBeInstanceOf(PolicyDecision);
      expect(decision.allowedFields).toContain('id');
      expect(decision.allowedFields).toContain('name');
      expect(decision.allowedFields).not.toContain('password');
    });

    it('should throw for disallowed model', () => {
      const engine = new PolicyEngine(testPolicy, testSchema);
      const ctx = createTestContext();

      expect(() => engine.validateQuery({
        model: 'Secret',
        take: 10,
      }, ctx)).toThrow(ModelNotAllowedError);
    });

    it('should inject tenant filter', () => {
      const engine = new PolicyEngine(testPolicy, testSchema);
      const ctx = createTestContext('tenant-abc');

      const decision = engine.validateQuery({
        model: 'Customer',
        take: 10,
      }, ctx);

      expect(decision.injectedFilters.length).toBeGreaterThan(0);
      expect(decision.injectedFilters.some(f =>
        f.field === 'tenantId' && f.value === 'tenant-abc'
      )).toBe(true);
    });

    it('should throw for disallowed field in select', () => {
      const engine = new PolicyEngine(testPolicy, testSchema);
      const ctx = createTestContext();

      expect(() => engine.validateQuery({
        model: 'Customer',
        select: ['id', 'password'],
        take: 10,
      }, ctx)).toThrow(FieldNotAllowedError);
    });

    it('should include budget in decision', () => {
      const engine = new PolicyEngine(testPolicy, testSchema);
      const ctx = createTestContext();

      const decision = engine.validateQuery({
        model: 'Customer',
        take: 10,
      }, ctx);

      expect(decision.budget).toBeDefined();
      expect(decision.budget?.maxRows).toBe(100);
    });
  });

  describe('validateGet', () => {
    it('should validate get for allowed model', () => {
      const engine = new PolicyEngine(testPolicy, testSchema);
      const ctx = createTestContext();

      const decision = engine.validateGet({
        model: 'Customer',
        id: '123',
      }, ctx);

      expect(decision.allowedFields).toContain('id');
      expect(decision.allowedFields).not.toContain('password');
    });

    it('should inject tenant filter for get', () => {
      const engine = new PolicyEngine(testPolicy, testSchema);
      const ctx = createTestContext('tenant-xyz');

      const decision = engine.validateGet({
        model: 'Customer',
        id: '123',
      }, ctx);

      expect(decision.injectedFilters.some(f =>
        f.field === 'tenantId' && f.value === 'tenant-xyz'
      )).toBe(true);
    });
  });

  describe('validateAggregate', () => {
    it('should validate aggregate for allowed model', () => {
      const engine = new PolicyEngine(testPolicy, testSchema);
      const ctx = createTestContext();

      const decision = engine.validateAggregate({
        model: 'Order',
        operation: 'count',
      }, ctx);

      expect(decision).toBeInstanceOf(PolicyDecision);
    });

    it('should throw for disallowed aggregate field', () => {
      const engine = new PolicyEngine(testPolicy, testSchema);
      const ctx = createTestContext();

      expect(() => engine.validateAggregate({
        model: 'Customer',
        operation: 'sum',
        field: 'password',
      }, ctx)).toThrow(FieldNotAllowedError);
    });
  });

  describe('validateCreate', () => {
    it('should validate create for writable model with reason', () => {
      const engine = new PolicyEngine(testPolicy, testSchema);
      const ctx = createTestContext();

      const decision = engine.validateCreate({
        model: 'Order',
        data: { customerId: '123', total: 100, status: 'pending' },
        reason: 'Test creation',
      }, ctx);

      expect(decision).toBeInstanceOf(PolicyDecision);
    });

    it('should throw for non-writable model', () => {
      const engine = new PolicyEngine(testPolicy, testSchema);
      const ctx = createTestContext();

      // Customer model has allowed: true but writable: false
      expect(() => engine.validateCreate({
        model: 'Customer',
        data: { name: 'John' },
        reason: 'Test',
      }, ctx)).toThrow();
    });
  });

  describe('validateUpdate', () => {
    it('should validate update for writable model with reason', () => {
      const engine = new PolicyEngine(testPolicy, testSchema);
      const ctx = createTestContext();

      const decision = engine.validateUpdate({
        model: 'Order',
        id: '123',
        data: { status: 'completed' },
        reason: 'Test update',
      }, ctx);

      expect(decision).toBeInstanceOf(PolicyDecision);
    });

    it('should throw for non-writable model', () => {
      const engine = new PolicyEngine(testPolicy, testSchema);
      const ctx = createTestContext();

      // Customer model has allowed: true but writable: false
      expect(() => engine.validateUpdate({
        model: 'Customer',
        id: '123',
        data: { name: 'Jane' },
        reason: 'Test',
      }, ctx)).toThrow();
    });
  });

  describe('validateDelete', () => {
    it('should throw when delete is not allowed', () => {
      const engine = new PolicyEngine(testPolicy, testSchema);
      const ctx = createTestContext();

      // Order has allowDelete: false in the policy
      expect(() => engine.validateDelete({
        model: 'Order',
        id: '123',
      }, ctx)).toThrow(WriteDisabledError);
    });
  });
});

describe('PolicyDecision', () => {
  it('should create with default values', () => {
    const decision = new PolicyDecision();

    expect(decision.allowedFields).toEqual([]);
    expect(decision.injectedFilters).toEqual([]);
    expect(decision.decisions).toEqual([]);
    expect(decision.budget).toBeNull();
    expect(decision.redactionRules).toEqual({});
  });

  it('should allow setting allowed fields', () => {
    const decision = new PolicyDecision();
    decision.allowedFields = ['id', 'name'];

    expect(decision.allowedFields).toEqual(['id', 'name']);
  });

  it('should allow adding injected filters', () => {
    const decision = new PolicyDecision();
    decision.injectedFilters = [
      { field: 'tenantId', op: 'eq', value: 'tenant-123' },
    ];

    expect(decision.injectedFilters).toHaveLength(1);
  });

  it('should allow adding decisions', () => {
    const decision = new PolicyDecision();
    decision.decisions = ['Tenant filter applied', 'Password field denied'];

    expect(decision.decisions).toHaveLength(2);
  });

  it('should allow setting budget', () => {
    const decision = new PolicyDecision();
    decision.budget = { maxRows: 50, maxIncludesDepth: 2 } as any;

    expect(decision.budget?.maxRows).toBe(50);
  });
});
