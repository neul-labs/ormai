/**
 * Tests for utils/defaults.ts
 */

import { describe, it, expect } from 'vitest';
import {
  DefaultsProfileSchema,
  PROD_DEFAULTS,
  INTERNAL_DEFAULTS,
  DEV_DEFAULTS,
  getDefaultsProfile,
  budgetFromProfile,
  writePolicyFromProfile,
} from '../../src/utils/defaults.js';

describe('DefaultsProfileSchema', () => {
  it('should parse prod mode', () => {
    const profile = DefaultsProfileSchema.parse({
      mode: 'prod',
    });

    expect(profile.mode).toBe('prod');
    expect(profile.maxRows).toBe(100);
    expect(profile.writesEnabled).toBe(false);
  });

  it('should accept custom values', () => {
    const profile = DefaultsProfileSchema.parse({
      mode: 'prod',
      maxRows: 50,
      maxIncludesDepth: 3,
      writesEnabled: true,
    });

    expect(profile.maxRows).toBe(50);
    expect(profile.maxIncludesDepth).toBe(3);
    expect(profile.writesEnabled).toBe(true);
  });

  it('should reject invalid mode', () => {
    expect(() => DefaultsProfileSchema.parse({
      mode: 'invalid',
    })).toThrow();
  });
});

describe('PROD_DEFAULTS', () => {
  it('should have expected production values', () => {
    expect(PROD_DEFAULTS.mode).toBe('prod');
    expect(PROD_DEFAULTS.maxRows).toBe(100);
    expect(PROD_DEFAULTS.maxIncludesDepth).toBe(1);
    expect(PROD_DEFAULTS.maxSelectFields).toBe(40);
    expect(PROD_DEFAULTS.statementTimeoutMs).toBe(2000);
    expect(PROD_DEFAULTS.writesEnabled).toBe(false);
    expect(PROD_DEFAULTS.requireTenantScope).toBe(true);
    expect(PROD_DEFAULTS.requireReasonForWrites).toBe(true);
  });
});

describe('INTERNAL_DEFAULTS', () => {
  it('should have expected internal values', () => {
    expect(INTERNAL_DEFAULTS.mode).toBe('internal');
    expect(INTERNAL_DEFAULTS.maxRows).toBe(500);
    expect(INTERNAL_DEFAULTS.maxIncludesDepth).toBe(2);
    expect(INTERNAL_DEFAULTS.maxSelectFields).toBe(100);
    expect(INTERNAL_DEFAULTS.statementTimeoutMs).toBe(5000);
    expect(INTERNAL_DEFAULTS.writesEnabled).toBe(false);
    expect(INTERNAL_DEFAULTS.requireTenantScope).toBe(true);
  });
});

describe('DEV_DEFAULTS', () => {
  it('should have expected development values', () => {
    expect(DEV_DEFAULTS.mode).toBe('dev');
    expect(DEV_DEFAULTS.maxRows).toBe(1000);
    expect(DEV_DEFAULTS.maxIncludesDepth).toBe(3);
    expect(DEV_DEFAULTS.maxSelectFields).toBe(200);
    expect(DEV_DEFAULTS.statementTimeoutMs).toBe(10000);
    expect(DEV_DEFAULTS.writesEnabled).toBe(true);
    expect(DEV_DEFAULTS.requireTenantScope).toBe(false);
    expect(DEV_DEFAULTS.requireReasonForWrites).toBe(false);
  });
});

describe('getDefaultsProfile', () => {
  it('should return prod defaults for prod mode', () => {
    const profile = getDefaultsProfile('prod');

    expect(profile).toEqual(PROD_DEFAULTS);
  });

  it('should return internal defaults for internal mode', () => {
    const profile = getDefaultsProfile('internal');

    expect(profile).toEqual(INTERNAL_DEFAULTS);
  });

  it('should return dev defaults for dev mode', () => {
    const profile = getDefaultsProfile('dev');

    expect(profile).toEqual(DEV_DEFAULTS);
  });
});

describe('budgetFromProfile', () => {
  it('should create budget from prod profile', () => {
    const budget = budgetFromProfile(PROD_DEFAULTS);

    expect(budget.maxRows).toBe(100);
    expect(budget.maxIncludesDepth).toBe(1);
    expect(budget.maxSelectFields).toBe(40);
    expect(budget.statementTimeoutMs).toBe(2000);
    expect(budget.broadQueryGuard).toBe(true);
  });

  it('should create budget from dev profile', () => {
    const budget = budgetFromProfile(DEV_DEFAULTS);

    expect(budget.maxRows).toBe(1000);
    expect(budget.maxIncludesDepth).toBe(3);
    expect(budget.broadQueryGuard).toBe(false);
  });

  it('should set broadQueryGuard based on mode', () => {
    expect(budgetFromProfile(PROD_DEFAULTS).broadQueryGuard).toBe(true);
    expect(budgetFromProfile(INTERNAL_DEFAULTS).broadQueryGuard).toBe(false);
    expect(budgetFromProfile(DEV_DEFAULTS).broadQueryGuard).toBe(false);
  });
});

describe('writePolicyFromProfile', () => {
  it('should create write policy from prod profile', () => {
    const writePolicy = writePolicyFromProfile(PROD_DEFAULTS);

    expect(writePolicy.enabled).toBe(false);
    expect(writePolicy.allowCreate).toBe(false);
    expect(writePolicy.allowUpdate).toBe(false);
    expect(writePolicy.allowDelete).toBe(false);
    expect(writePolicy.allowBulk).toBe(false);
    expect(writePolicy.requirePrimaryKey).toBe(true);
    expect(writePolicy.maxAffectedRows).toBe(1);
    expect(writePolicy.requireReason).toBe(true);
  });

  it('should create write policy from dev profile', () => {
    const writePolicy = writePolicyFromProfile(DEV_DEFAULTS);

    expect(writePolicy.enabled).toBe(true);
    expect(writePolicy.allowCreate).toBe(true);
    expect(writePolicy.allowUpdate).toBe(true);
    expect(writePolicy.allowDelete).toBe(true);
    expect(writePolicy.allowBulk).toBe(true);
    expect(writePolicy.maxAffectedRows).toBe(100);
    expect(writePolicy.requireReason).toBe(false);
  });

  it('should not allow bulk in prod mode even with writes enabled', () => {
    const prodWithWrites = { ...PROD_DEFAULTS, writesEnabled: true };
    const writePolicy = writePolicyFromProfile(prodWithWrites);

    expect(writePolicy.enabled).toBe(true);
    expect(writePolicy.allowBulk).toBe(false);
  });

  it('should allow bulk in internal mode with writes enabled', () => {
    const internalWithWrites = { ...INTERNAL_DEFAULTS, writesEnabled: true };
    const writePolicy = writePolicyFromProfile(internalWithWrites);

    expect(writePolicy.enabled).toBe(true);
    expect(writePolicy.allowBulk).toBe(true);
  });
});
