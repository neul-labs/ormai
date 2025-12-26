/**
 * Tests for utils/builder.ts
 */

import { describe, it, expect } from 'vitest';
import { PolicyBuilder, createPolicyBuilder } from '../../src/utils/builder.js';

describe('PolicyBuilder', () => {
  describe('constructor', () => {
    it('should create builder with prod defaults', () => {
      const builder = new PolicyBuilder('prod');
      const policy = builder.build();

      expect(policy.requireTenantScope).toBe(true);
      expect(policy.writesEnabled).toBe(false);
      expect(policy.defaultBudget.maxRows).toBe(100);
    });

    it('should create builder with dev defaults', () => {
      const builder = new PolicyBuilder('dev');
      const policy = builder.build();

      expect(policy.requireTenantScope).toBe(false);
      expect(policy.writesEnabled).toBe(true);
      expect(policy.defaultBudget.maxRows).toBe(1000);
    });

    it('should default to prod mode', () => {
      const builder = new PolicyBuilder();
      const policy = builder.build();

      expect(policy.defaultBudget.maxRows).toBe(100);
    });
  });

  describe('registerModels', () => {
    it('should register models with default policies', () => {
      const policy = new PolicyBuilder('prod')
        .registerModels(['Customer', 'Order'])
        .build();

      expect(policy.models.Customer).toBeDefined();
      expect(policy.models.Customer.allowed).toBe(true);
      expect(policy.models.Customer.readable).toBe(true);
      expect(policy.models.Order).toBeDefined();
    });

    it('should not override existing model config', () => {
      const policy = new PolicyBuilder('prod')
        .model('Customer', { readable: false })
        .registerModels(['Customer', 'Order'])
        .build();

      expect(policy.models.Customer.readable).toBe(false);
    });
  });

  describe('model', () => {
    it('should configure a specific model', () => {
      const policy = new PolicyBuilder('prod')
        .model('Customer', { allowed: true, readable: true, writable: true })
        .build();

      expect(policy.models.Customer.writable).toBe(true);
    });

    it('should merge with existing config', () => {
      const policy = new PolicyBuilder('prod')
        .model('Customer', { allowed: true })
        .model('Customer', { readable: false })
        .build();

      expect(policy.models.Customer.allowed).toBe(true);
      expect(policy.models.Customer.readable).toBe(false);
    });
  });

  describe('field', () => {
    it('should set field policy', () => {
      const policy = new PolicyBuilder('prod')
        .field('Customer', 'password', { action: 'deny' })
        .build();

      expect(policy.models.Customer.fields?.password?.action).toBe('deny');
    });

    it('should support mask action with pattern', () => {
      const policy = new PolicyBuilder('prod')
        .field('Customer', 'email', { action: 'mask', maskPattern: '****{last4}' })
        .build();

      expect(policy.models.Customer.fields?.email?.action).toBe('mask');
      expect(policy.models.Customer.fields?.email?.maskPattern).toBe('****{last4}');
    });

    it('should create model if not exists', () => {
      const policy = new PolicyBuilder('prod')
        .field('NewModel', 'secret', { action: 'deny' })
        .build();

      expect(policy.models.NewModel).toBeDefined();
      expect(policy.models.NewModel.fields?.secret?.action).toBe('deny');
    });
  });

  describe('denyFields', () => {
    it('should add to global deny patterns', () => {
      const policy = new PolicyBuilder('prod')
        .denyFields('*password*')
        .denyFields('*secret*')
        .build();

      expect(policy.globalDenyPatterns).toContain('*password*');
      expect(policy.globalDenyPatterns).toContain('*secret*');
    });
  });

  describe('maskFields', () => {
    it('should add to global mask patterns', () => {
      const policy = new PolicyBuilder('prod')
        .maskFields('*email*')
        .maskFields('*phone*')
        .build();

      expect(policy.globalMaskPatterns).toContain('*email*');
      expect(policy.globalMaskPatterns).toContain('*phone*');
    });
  });

  describe('defaultFieldAction', () => {
    it('should set default field action for model', () => {
      const policy = new PolicyBuilder('prod')
        .defaultFieldAction('Customer', 'deny')
        .build();

      expect(policy.models.Customer.defaultFieldAction).toBe('deny');
    });
  });

  describe('allowRelations', () => {
    it('should configure allowed relations', () => {
      const policy = new PolicyBuilder('prod')
        .allowRelations('Customer', ['orders', 'profile'])
        .build();

      expect(policy.models.Customer.relations?.orders?.allowed).toBe(true);
      expect(policy.models.Customer.relations?.profile?.allowed).toBe(true);
    });
  });

  describe('relation', () => {
    it('should configure relation policy', () => {
      const policy = new PolicyBuilder('prod')
        .relation('Customer', 'orders', { allowed: true, maxDepth: 2 })
        .build();

      expect(policy.models.Customer.relations?.orders?.allowed).toBe(true);
      expect(policy.models.Customer.relations?.orders?.maxDepth).toBe(2);
    });
  });

  describe('tenantScope', () => {
    it('should set tenant scope for specific model', () => {
      const policy = new PolicyBuilder('prod')
        .tenantScope('tenantId', 'Customer')
        .build();

      expect(policy.models.Customer.rowPolicy?.tenantScopeField).toBe('tenantId');
    });

    it('should set default tenant scope for all models', () => {
      const policy = new PolicyBuilder('prod')
        .tenantScope('orgId')
        .build();

      expect(policy.defaultRowPolicy?.tenantScopeField).toBe('orgId');
    });
  });

  describe('ownershipScope', () => {
    it('should set ownership scope for specific model', () => {
      const policy = new PolicyBuilder('prod')
        .ownershipScope('userId', 'Customer')
        .build();

      expect(policy.models.Customer.rowPolicy?.ownershipScopeField).toBe('userId');
    });

    it('should set default ownership scope for all models', () => {
      const policy = new PolicyBuilder('prod')
        .ownershipScope('createdBy')
        .build();

      expect(policy.defaultRowPolicy?.ownershipScopeField).toBe('createdBy');
    });
  });

  describe('softDelete', () => {
    it('should set soft delete field for specific model', () => {
      const policy = new PolicyBuilder('prod')
        .softDelete('deletedAt', 'Customer')
        .build();

      expect(policy.models.Customer.rowPolicy?.softDeleteField).toBe('deletedAt');
    });

    it('should set default soft delete field for all models', () => {
      const policy = new PolicyBuilder('prod')
        .softDelete('deletedAt')
        .build();

      expect(policy.defaultRowPolicy?.softDeleteField).toBe('deletedAt');
    });
  });

  describe('enableWrites', () => {
    it('should enable writes for specific models', () => {
      const policy = new PolicyBuilder('prod')
        .enableWrites(['Order', 'Customer'])
        .build();

      expect(policy.models.Order.writable).toBe(true);
      expect(policy.models.Order.writePolicy?.enabled).toBe(true);
      expect(policy.models.Customer.writable).toBe(true);
    });

    it('should accept custom write config', () => {
      const policy = new PolicyBuilder('prod')
        .enableWrites(['Order'], { allowDelete: false, maxAffectedRows: 10 })
        .build();

      expect(policy.models.Order.writePolicy?.allowDelete).toBe(false);
      expect(policy.models.Order.writePolicy?.maxAffectedRows).toBe(10);
    });
  });

  describe('budget', () => {
    it('should set custom budget for model', () => {
      const policy = new PolicyBuilder('prod')
        .budget('Customer', { maxRows: 50, maxIncludesDepth: 3 })
        .build();

      expect(policy.models.Customer.budget?.maxRows).toBe(50);
      expect(policy.models.Customer.budget?.maxIncludesDepth).toBe(3);
    });
  });

  describe('defaultBudgetConfig', () => {
    it('should set default budget', () => {
      const policy = new PolicyBuilder('prod')
        .defaultBudgetConfig({ maxRows: 200 })
        .build();

      expect(policy.defaultBudget.maxRows).toBe(200);
    });
  });

  describe('setRequireTenantScope', () => {
    it('should configure tenant scope requirement', () => {
      const policy = new PolicyBuilder('prod')
        .setRequireTenantScope(false)
        .build();

      expect(policy.requireTenantScope).toBe(false);
    });
  });

  describe('setWritesEnabled', () => {
    it('should configure writes enabled', () => {
      const policy = new PolicyBuilder('prod')
        .setWritesEnabled(true)
        .build();

      expect(policy.writesEnabled).toBe(true);
    });
  });

  describe('build', () => {
    it('should build a valid policy', () => {
      const policy = new PolicyBuilder('prod')
        .registerModels(['Customer', 'Order'])
        .field('Customer', 'password', { action: 'deny' })
        .tenantScope('tenantId')
        .enableWrites(['Order'])
        .build();

      expect(policy.models.Customer).toBeDefined();
      expect(policy.models.Order).toBeDefined();
      expect(policy.models.Customer.fields?.password?.action).toBe('deny');
      expect(policy.models.Order.writable).toBe(true);
    });

    it('should be chainable', () => {
      const policy = new PolicyBuilder('prod')
        .registerModels(['Customer'])
        .field('Customer', 'password', { action: 'deny' })
        .field('Customer', 'email', { action: 'mask' })
        .tenantScope('tenantId')
        .allowRelations('Customer', ['orders'])
        .denyFields('*secret*')
        .build();

      expect(policy.models.Customer.fields?.password?.action).toBe('deny');
      expect(policy.models.Customer.fields?.email?.action).toBe('mask');
      expect(policy.globalDenyPatterns).toContain('*secret*');
    });
  });
});

describe('createPolicyBuilder', () => {
  it('should create builder with prod mode by default', () => {
    const builder = createPolicyBuilder();
    const policy = builder.build();

    expect(policy.defaultBudget.maxRows).toBe(100);
  });

  it('should create builder with specified mode', () => {
    const builder = createPolicyBuilder('dev');
    const policy = builder.build();

    expect(policy.defaultBudget.maxRows).toBe(1000);
  });
});
