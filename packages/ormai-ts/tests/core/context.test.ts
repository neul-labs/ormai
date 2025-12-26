/**
 * Tests for core/context.ts
 */

import { describe, it, expect } from 'vitest';
import {
  createPrincipal,
  createContext,
  hasRole,
  isPrincipal,
  isRunContext,
  type Principal,
  type RunContext,
} from '../../src/core/context.js';

describe('createPrincipal', () => {
  it('should create a principal with required fields', () => {
    const principal = createPrincipal({
      tenantId: 'tenant-123',
      userId: 'user-456',
    });

    expect(principal.tenantId).toBe('tenant-123');
    expect(principal.userId).toBe('user-456');
    expect(principal.roles).toEqual([]);
    expect(principal.metadata).toBeUndefined();
  });

  it('should create a principal with roles', () => {
    const principal = createPrincipal({
      tenantId: 'tenant-123',
      userId: 'user-456',
      roles: ['admin', 'editor'],
    });

    expect(principal.roles).toEqual(['admin', 'editor']);
  });

  it('should create a principal with metadata', () => {
    const principal = createPrincipal({
      tenantId: 'tenant-123',
      userId: 'user-456',
      metadata: { department: 'engineering' },
    });

    expect(principal.metadata).toEqual({ department: 'engineering' });
  });

  it('should freeze the principal object', () => {
    const principal = createPrincipal({
      tenantId: 'tenant-123',
      userId: 'user-456',
    });

    expect(Object.isFrozen(principal)).toBe(true);
    expect(Object.isFrozen(principal.roles)).toBe(true);
  });
});

describe('hasRole', () => {
  it('should return true if principal has the role', () => {
    const principal = createPrincipal({
      tenantId: 'tenant-123',
      userId: 'user-456',
      roles: ['admin', 'editor'],
    });

    expect(hasRole(principal, 'admin')).toBe(true);
    expect(hasRole(principal, 'editor')).toBe(true);
  });

  it('should return false if principal does not have the role', () => {
    const principal = createPrincipal({
      tenantId: 'tenant-123',
      userId: 'user-456',
      roles: ['editor'],
    });

    expect(hasRole(principal, 'admin')).toBe(false);
  });

  it('should return false for empty roles', () => {
    const principal = createPrincipal({
      tenantId: 'tenant-123',
      userId: 'user-456',
    });

    expect(hasRole(principal, 'admin')).toBe(false);
  });
});

describe('createContext', () => {
  it('should create a context with required fields', () => {
    const ctx = createContext({
      tenantId: 'tenant-123',
      userId: 'user-456',
      db: { client: 'mock' },
    });

    expect(ctx.principal.tenantId).toBe('tenant-123');
    expect(ctx.principal.userId).toBe('user-456');
    expect(ctx.db).toEqual({ client: 'mock' });
    expect(ctx.requestId).toBeDefined();
    expect(ctx.now).toBeInstanceOf(Date);
  });

  it('should create a context with custom requestId', () => {
    const ctx = createContext({
      tenantId: 'tenant-123',
      userId: 'user-456',
      db: { client: 'mock' },
      requestId: 'req-789',
    });

    expect(ctx.requestId).toBe('req-789');
  });

  it('should create a context with traceId', () => {
    const ctx = createContext({
      tenantId: 'tenant-123',
      userId: 'user-456',
      db: { client: 'mock' },
      traceId: 'trace-abc',
    });

    expect(ctx.traceId).toBe('trace-abc');
  });

  it('should create a context with roles', () => {
    const ctx = createContext({
      tenantId: 'tenant-123',
      userId: 'user-456',
      db: { client: 'mock' },
      roles: ['admin'],
    });

    expect(ctx.principal.roles).toEqual(['admin']);
  });

  it('should freeze the context object', () => {
    const ctx = createContext({
      tenantId: 'tenant-123',
      userId: 'user-456',
      db: { client: 'mock' },
    });

    expect(Object.isFrozen(ctx)).toBe(true);
  });
});

describe('isPrincipal', () => {
  it('should return true for valid principal', () => {
    const principal = createPrincipal({
      tenantId: 'tenant-123',
      userId: 'user-456',
    });

    expect(isPrincipal(principal)).toBe(true);
  });

  it('should return true for plain object with required fields', () => {
    const obj = {
      tenantId: 'tenant-123',
      userId: 'user-456',
      roles: ['admin'],
    };

    expect(isPrincipal(obj)).toBe(true);
  });

  it('should return false for null', () => {
    expect(isPrincipal(null)).toBe(false);
  });

  it('should return false for undefined', () => {
    expect(isPrincipal(undefined)).toBe(false);
  });

  it('should return false for non-object', () => {
    expect(isPrincipal('string')).toBe(false);
    expect(isPrincipal(123)).toBe(false);
  });

  it('should return false for object missing required fields', () => {
    expect(isPrincipal({ tenantId: 'tenant-123' })).toBe(false);
    expect(isPrincipal({ userId: 'user-456' })).toBe(false);
    expect(isPrincipal({ tenantId: 'tenant-123', userId: 'user-456' })).toBe(false);
  });
});

describe('isRunContext', () => {
  it('should return true for valid context', () => {
    const ctx = createContext({
      tenantId: 'tenant-123',
      userId: 'user-456',
      db: { client: 'mock' },
    });

    expect(isRunContext(ctx)).toBe(true);
  });

  it('should return false for null', () => {
    expect(isRunContext(null)).toBe(false);
  });

  it('should return false for undefined', () => {
    expect(isRunContext(undefined)).toBe(false);
  });

  it('should return false for object missing principal', () => {
    expect(isRunContext({ requestId: 'req-123', now: new Date() })).toBe(false);
  });

  it('should return false for object missing requestId', () => {
    const principal = createPrincipal({
      tenantId: 'tenant-123',
      userId: 'user-456',
    });
    expect(isRunContext({ principal, now: new Date() })).toBe(false);
  });
});
