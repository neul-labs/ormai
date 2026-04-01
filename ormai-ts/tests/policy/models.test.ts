/**
 * Tests for policy/models.ts
 */

import { describe, it, expect } from 'vitest';
import {
  FieldActionSchema,
  FieldPolicySchema,
  RelationPolicySchema,
  RowPolicySchema,
  WritePolicySchema,
  BudgetSchema,
  ModelPolicySchema,
  PolicySchema,
  ModelPolicyUtils,
  PolicyUtils,
  DEFAULT_BUDGET,
  DEFAULT_ROW_POLICY,
  DEFAULT_WRITE_POLICY,
} from '../../src/policy/models.js';

describe('FieldActionSchema', () => {
  it('should accept valid actions', () => {
    expect(FieldActionSchema.parse('allow')).toBe('allow');
    expect(FieldActionSchema.parse('deny')).toBe('deny');
    expect(FieldActionSchema.parse('mask')).toBe('mask');
    expect(FieldActionSchema.parse('hash')).toBe('hash');
  });

  it('should reject invalid actions', () => {
    expect(() => FieldActionSchema.parse('invalid')).toThrow();
  });
});

describe('FieldPolicySchema', () => {
  it('should create with defaults', () => {
    const policy = FieldPolicySchema.parse({});

    expect(policy.action).toBe('allow');
  });

  it('should accept mask pattern', () => {
    const policy = FieldPolicySchema.parse({
      action: 'mask',
      maskPattern: '****{last4}',
    });

    expect(policy.action).toBe('mask');
    expect(policy.maskPattern).toBe('****{last4}');
  });
});

describe('RelationPolicySchema', () => {
  it('should create with defaults', () => {
    const policy = RelationPolicySchema.parse({});

    expect(policy.allowed).toBe(true);
    expect(policy.maxDepth).toBe(1);
  });

  it('should accept custom values', () => {
    const policy = RelationPolicySchema.parse({
      allowed: false,
      maxDepth: 3,
      allowedFields: ['id', 'name'],
    });

    expect(policy.allowed).toBe(false);
    expect(policy.maxDepth).toBe(3);
    expect(policy.allowedFields).toEqual(['id', 'name']);
  });
});

describe('RowPolicySchema', () => {
  it('should create with defaults', () => {
    const policy = RowPolicySchema.parse({});

    expect(policy.requireScope).toBe(true);
    expect(policy.includeSoftDeleted).toBe(false);
  });

  it('should accept tenant scope field', () => {
    const policy = RowPolicySchema.parse({
      tenantScopeField: 'tenantId',
    });

    expect(policy.tenantScopeField).toBe('tenantId');
  });

  it('should accept ownership scope field', () => {
    const policy = RowPolicySchema.parse({
      ownershipScopeField: 'userId',
    });

    expect(policy.ownershipScopeField).toBe('userId');
  });

  it('should accept soft delete field', () => {
    const policy = RowPolicySchema.parse({
      softDeleteField: 'deletedAt',
    });

    expect(policy.softDeleteField).toBe('deletedAt');
  });
});

describe('WritePolicySchema', () => {
  it('should create with defaults', () => {
    const policy = WritePolicySchema.parse({});

    expect(policy.enabled).toBe(false);
    expect(policy.allowCreate).toBe(false);
    expect(policy.allowUpdate).toBe(false);
    expect(policy.allowDelete).toBe(false);
    expect(policy.allowBulk).toBe(false);
    expect(policy.requirePrimaryKey).toBe(true);
    expect(policy.maxAffectedRows).toBe(1);
    expect(policy.requireReason).toBe(true);
  });

  it('should accept custom values', () => {
    const policy = WritePolicySchema.parse({
      enabled: true,
      allowCreate: true,
      allowUpdate: true,
      maxAffectedRows: 10,
      readonlyFields: ['createdAt', 'updatedAt'],
    });

    expect(policy.enabled).toBe(true);
    expect(policy.allowCreate).toBe(true);
    expect(policy.maxAffectedRows).toBe(10);
    expect(policy.readonlyFields).toEqual(['createdAt', 'updatedAt']);
  });
});

describe('BudgetSchema', () => {
  it('should create with defaults', () => {
    const budget = BudgetSchema.parse({});

    expect(budget.maxRows).toBe(100);
    expect(budget.maxIncludesDepth).toBe(1);
    expect(budget.maxSelectFields).toBe(40);
    expect(budget.statementTimeoutMs).toBe(2000);
    expect(budget.maxComplexityScore).toBe(100);
    expect(budget.broadQueryGuard).toBe(true);
  });

  it('should accept custom values', () => {
    const budget = BudgetSchema.parse({
      maxRows: 50,
      maxIncludesDepth: 3,
      statementTimeoutMs: 5000,
    });

    expect(budget.maxRows).toBe(50);
    expect(budget.maxIncludesDepth).toBe(3);
    expect(budget.statementTimeoutMs).toBe(5000);
  });
});

describe('ModelPolicySchema', () => {
  it('should create with defaults', () => {
    const policy = ModelPolicySchema.parse({});

    expect(policy.allowed).toBe(true);
    expect(policy.readable).toBe(true);
    expect(policy.writable).toBe(false);
    expect(policy.defaultFieldAction).toBe('allow');
  });

  it('should accept fields configuration', () => {
    const policy = ModelPolicySchema.parse({
      fields: {
        password: { action: 'deny' },
        email: { action: 'mask' },
      },
    });

    expect(policy.fields?.password?.action).toBe('deny');
    expect(policy.fields?.email?.action).toBe('mask');
  });

  it('should accept relations configuration', () => {
    const policy = ModelPolicySchema.parse({
      relations: {
        orders: { allowed: true, maxDepth: 2 },
        secrets: { allowed: false },
      },
    });

    expect(policy.relations?.orders?.allowed).toBe(true);
    expect(policy.relations?.secrets?.allowed).toBe(false);
  });
});

describe('PolicySchema', () => {
  it('should create with defaults', () => {
    const policy = PolicySchema.parse({
      models: {},
    });

    expect(policy.models).toEqual({});
    expect(policy.requireTenantScope).toBe(true);
    expect(policy.writesEnabled).toBe(false);
  });

  it('should accept models configuration', () => {
    const policy = PolicySchema.parse({
      models: {
        Customer: { allowed: true },
        Order: { allowed: true, writable: true },
      },
    });

    expect(policy.models.Customer?.allowed).toBe(true);
    expect(policy.models.Order?.writable).toBe(true);
  });

  it('should accept global patterns', () => {
    const policy = PolicySchema.parse({
      models: {},
      globalDenyPatterns: ['*password*', '*secret*'],
      globalMaskPatterns: ['*email*', '*phone*'],
    });

    expect(policy.globalDenyPatterns).toEqual(['*password*', '*secret*']);
    expect(policy.globalMaskPatterns).toEqual(['*email*', '*phone*']);
  });
});

describe('ModelPolicyUtils', () => {
  const modelPolicy = ModelPolicySchema.parse({
    fields: {
      id: { action: 'allow' },
      name: { action: 'allow' },
      email: { action: 'mask' },
      password: { action: 'deny' },
    },
    defaultFieldAction: 'allow',
  });

  describe('getFieldPolicy', () => {
    it('should return field policy if defined', () => {
      const policy = ModelPolicyUtils.getFieldPolicy(modelPolicy, 'password');

      expect(policy?.action).toBe('deny');
    });

    it('should return default policy for undefined field', () => {
      const policy = ModelPolicyUtils.getFieldPolicy(modelPolicy, 'unknown');

      // Returns a default policy with action from defaultFieldAction
      expect(policy.action).toBe('allow');
    });
  });

  describe('isFieldAllowed', () => {
    it('should return true for allowed field', () => {
      expect(ModelPolicyUtils.isFieldAllowed(modelPolicy, 'id')).toBe(true);
      expect(ModelPolicyUtils.isFieldAllowed(modelPolicy, 'name')).toBe(true);
    });

    it('should return false for denied field', () => {
      expect(ModelPolicyUtils.isFieldAllowed(modelPolicy, 'password')).toBe(false);
    });

    it('should return true for masked field', () => {
      expect(ModelPolicyUtils.isFieldAllowed(modelPolicy, 'email')).toBe(true);
    });

    it('should use default action for undefined fields', () => {
      expect(ModelPolicyUtils.isFieldAllowed(modelPolicy, 'unknown')).toBe(true);
    });
  });

  describe('getAllowedFields', () => {
    it('should filter out denied fields', () => {
      const allFields = ['id', 'name', 'email', 'password'];
      const allowed = ModelPolicyUtils.getAllowedFields(modelPolicy, allFields);

      expect(allowed).toContain('id');
      expect(allowed).toContain('name');
      expect(allowed).toContain('email');
      expect(allowed).not.toContain('password');
    });
  });
});

describe('PolicyUtils', () => {
  const policy = PolicySchema.parse({
    models: {
      Customer: {
        allowed: true,
        budget: { maxRows: 50 },
        rowPolicy: { tenantScopeField: 'tenantId' },
      },
      Order: {
        allowed: true,
      },
      Secret: {
        allowed: false,
      },
    },
    defaultBudget: { maxRows: 100 },
    defaultRowPolicy: { tenantScopeField: 'orgId' },
  });

  describe('getModelPolicy', () => {
    it('should return model policy if defined', () => {
      const modelPolicy = PolicyUtils.getModelPolicy(policy, 'Customer');

      expect(modelPolicy?.allowed).toBe(true);
    });

    it('should return undefined for undefined model', () => {
      const modelPolicy = PolicyUtils.getModelPolicy(policy, 'Unknown');

      expect(modelPolicy).toBeUndefined();
    });
  });

  describe('getBudget', () => {
    it('should return model budget if defined', () => {
      const budget = PolicyUtils.getBudget(policy, 'Customer');

      expect(budget.maxRows).toBe(50);
    });

    it('should return default budget if model budget not defined', () => {
      const budget = PolicyUtils.getBudget(policy, 'Order');

      expect(budget.maxRows).toBe(100);
    });
  });

  describe('getRowPolicy', () => {
    it('should return model row policy if defined', () => {
      const rowPolicy = PolicyUtils.getRowPolicy(policy, 'Customer');

      expect(rowPolicy.tenantScopeField).toBe('tenantId');
    });

    it('should return default row policy if model row policy not defined', () => {
      const rowPolicy = PolicyUtils.getRowPolicy(policy, 'Order');

      expect(rowPolicy.tenantScopeField).toBe('orgId');
    });
  });

  describe('isModelAllowed', () => {
    it('should return true for allowed model', () => {
      expect(PolicyUtils.isModelAllowed(policy, 'Customer')).toBe(true);
      expect(PolicyUtils.isModelAllowed(policy, 'Order')).toBe(true);
    });

    it('should return false for denied model', () => {
      expect(PolicyUtils.isModelAllowed(policy, 'Secret')).toBe(false);
    });

    it('should return false for undefined model', () => {
      expect(PolicyUtils.isModelAllowed(policy, 'Unknown')).toBe(false);
    });
  });

  describe('listAllowedModels', () => {
    it('should return list of allowed models', () => {
      const allowed = PolicyUtils.listAllowedModels(policy);

      expect(allowed).toContain('Customer');
      expect(allowed).toContain('Order');
      expect(allowed).not.toContain('Secret');
    });
  });
});

describe('Default constants', () => {
  it('DEFAULT_BUDGET should have expected values', () => {
    expect(DEFAULT_BUDGET.maxRows).toBe(100);
    expect(DEFAULT_BUDGET.maxIncludesDepth).toBe(1);
  });

  it('DEFAULT_ROW_POLICY should have expected values', () => {
    expect(DEFAULT_ROW_POLICY.requireScope).toBe(true);
    expect(DEFAULT_ROW_POLICY.includeSoftDeleted).toBe(false);
  });

  it('DEFAULT_WRITE_POLICY should have expected values', () => {
    expect(DEFAULT_WRITE_POLICY.enabled).toBe(false);
    expect(DEFAULT_WRITE_POLICY.requirePrimaryKey).toBe(true);
  });
});
