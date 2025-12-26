/**
 * Tests for policy/scoping.ts
 */

import { describe, it, expect } from 'vitest';
import { ScopeInjector, createScopeInjector } from '../../src/policy/scoping.js';
import { RowPolicySchema } from '../../src/policy/models.js';
import { createContext } from '../../src/core/context.js';

function createTestContext(tenantId = 'tenant-123', userId = 'user-456') {
  return createContext({
    tenantId,
    userId,
    db: {},
  });
}

describe('ScopeInjector', () => {
  describe('getScopeFilters', () => {
    it('should inject tenant filter when tenantScopeField is set', () => {
      const rowPolicy = RowPolicySchema.parse({
        tenantScopeField: 'tenantId',
      });
      const injector = new ScopeInjector(rowPolicy);
      const ctx = createTestContext('tenant-abc');

      const filters = injector.getScopeFilters(ctx);

      expect(filters).toHaveLength(1);
      expect(filters[0]).toEqual({
        field: 'tenantId',
        op: 'eq',
        value: 'tenant-abc',
      });
    });

    it('should inject ownership filter when ownershipScopeField is set', () => {
      const rowPolicy = RowPolicySchema.parse({
        ownershipScopeField: 'userId',
      });
      const injector = new ScopeInjector(rowPolicy);
      const ctx = createTestContext('tenant-abc', 'user-xyz');

      const filters = injector.getScopeFilters(ctx);

      expect(filters).toHaveLength(1);
      expect(filters[0]).toEqual({
        field: 'userId',
        op: 'eq',
        value: 'user-xyz',
      });
    });

    it('should inject both tenant and ownership filters', () => {
      const rowPolicy = RowPolicySchema.parse({
        tenantScopeField: 'tenantId',
        ownershipScopeField: 'userId',
      });
      const injector = new ScopeInjector(rowPolicy);
      const ctx = createTestContext();

      const filters = injector.getScopeFilters(ctx);

      expect(filters).toHaveLength(2);
      expect(filters.some(f => f.field === 'tenantId')).toBe(true);
      expect(filters.some(f => f.field === 'userId')).toBe(true);
    });

    it('should inject soft delete filter when softDeleteField is set', () => {
      const rowPolicy = RowPolicySchema.parse({
        softDeleteField: 'deletedAt',
        includeSoftDeleted: false,
      });
      const injector = new ScopeInjector(rowPolicy);
      const ctx = createTestContext();

      const filters = injector.getScopeFilters(ctx);

      expect(filters).toHaveLength(1);
      expect(filters[0]).toEqual({
        field: 'deletedAt',
        op: 'is_null',
        value: true,
      });
    });

    it('should not inject soft delete filter when includeSoftDeleted is true', () => {
      const rowPolicy = RowPolicySchema.parse({
        softDeleteField: 'deletedAt',
        includeSoftDeleted: true,
      });
      const injector = new ScopeInjector(rowPolicy);
      const ctx = createTestContext();

      const filters = injector.getScopeFilters(ctx);

      expect(filters).toHaveLength(0);
    });

    it('should return empty array when no scope fields are set', () => {
      const rowPolicy = RowPolicySchema.parse({});
      const injector = new ScopeInjector(rowPolicy);
      const ctx = createTestContext();

      const filters = injector.getScopeFilters(ctx);

      expect(filters).toHaveLength(0);
    });
  });

  describe('mergeFilters', () => {
    it('should merge scope filters with user filters', () => {
      const rowPolicy = RowPolicySchema.parse({
        tenantScopeField: 'tenantId',
      });
      const injector = new ScopeInjector(rowPolicy);

      const userFilters = [
        { field: 'status', op: 'eq' as const, value: 'active' },
      ];
      const scopeFilters = [
        { field: 'tenantId', op: 'eq' as const, value: 'tenant-123' },
      ];

      const merged = injector.mergeFilters(userFilters, scopeFilters);

      expect(merged).toHaveLength(2);
      expect(merged[0].field).toBe('tenantId'); // Scope filters first
      expect(merged[1].field).toBe('status');
    });

    it('should handle undefined user filters', () => {
      const rowPolicy = RowPolicySchema.parse({});
      const injector = new ScopeInjector(rowPolicy);

      const scopeFilters = [
        { field: 'tenantId', op: 'eq' as const, value: 'tenant-123' },
      ];

      const merged = injector.mergeFilters(undefined, scopeFilters);

      expect(merged).toHaveLength(1);
      expect(merged[0].field).toBe('tenantId');
    });

    it('should handle empty scope filters', () => {
      const rowPolicy = RowPolicySchema.parse({});
      const injector = new ScopeInjector(rowPolicy);

      const userFilters = [
        { field: 'status', op: 'eq' as const, value: 'active' },
      ];

      const merged = injector.mergeFilters(userFilters, []);

      expect(merged).toHaveLength(1);
      expect(merged[0].field).toBe('status');
    });
  });

  describe('getScopeData', () => {
    it('should return tenant data for creation', () => {
      const rowPolicy = RowPolicySchema.parse({
        tenantScopeField: 'tenantId',
      });
      const injector = new ScopeInjector(rowPolicy);
      const ctx = createTestContext('tenant-xyz');

      const data = injector.getScopeData(ctx);

      expect(data).toEqual({ tenantId: 'tenant-xyz' });
    });

    it('should return ownership data for creation', () => {
      const rowPolicy = RowPolicySchema.parse({
        ownershipScopeField: 'createdBy',
      });
      const injector = new ScopeInjector(rowPolicy);
      const ctx = createTestContext('tenant-abc', 'user-123');

      const data = injector.getScopeData(ctx);

      expect(data).toEqual({ createdBy: 'user-123' });
    });

    it('should return both tenant and ownership data', () => {
      const rowPolicy = RowPolicySchema.parse({
        tenantScopeField: 'tenantId',
        ownershipScopeField: 'userId',
      });
      const injector = new ScopeInjector(rowPolicy);
      const ctx = createTestContext('tenant-abc', 'user-xyz');

      const data = injector.getScopeData(ctx);

      expect(data).toEqual({
        tenantId: 'tenant-abc',
        userId: 'user-xyz',
      });
    });

    it('should return empty object when no scope fields are set', () => {
      const rowPolicy = RowPolicySchema.parse({});
      const injector = new ScopeInjector(rowPolicy);
      const ctx = createTestContext();

      const data = injector.getScopeData(ctx);

      expect(data).toEqual({});
    });
  });
});

describe('createScopeInjector', () => {
  it('should create a scope injector', () => {
    const rowPolicy = RowPolicySchema.parse({
      tenantScopeField: 'tenantId',
    });

    const injector = createScopeInjector(rowPolicy);

    expect(injector).toBeInstanceOf(ScopeInjector);
  });
});
