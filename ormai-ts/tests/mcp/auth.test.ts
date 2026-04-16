/**
 * Tests for MCP authentication helpers.
 */

import { describe, it, expect } from 'vitest';
import { createHmac } from 'crypto';
import {
  createApiKeyAuth,
  createJwtAuth,
  extractTenantFromHeaders,
  principalFromHeaders,
  combineAuthMiddlewares,
  createDevAuth,
} from '@ormai/mcp';
import type { Principal } from '@ormai/core';

function createHmacToken(payload: Record<string, unknown>, secret: string, algorithm: string = 'sha256'): string {
  const header = Buffer.from(JSON.stringify({ alg: `HS${algorithm.replace('sha', '')}`, typ: 'JWT' })).toString('base64url');
  const payloadStr = Buffer.from(JSON.stringify(payload)).toString('base64url');
  const message = `${header}.${payloadStr}`;
  const sig = createHmac(algorithm as 'sha256' | 'sha384' | 'sha512', secret).update(message).digest('base64url');
  return `${header}.${payloadStr}.${sig}`;
}

describe('createApiKeyAuth', () => {
  const principal: Principal = { tenantId: 't1', userId: 'u1', roles: ['admin'] };
  const auth = createApiKeyAuth({ 'my-api-key': principal });

  it('should authenticate with Bearer prefix', async () => {
    const result = await auth({ authorization: 'Bearer my-api-key' });
    expect(result.authenticated).toBe(true);
    expect(result.principal?.tenantId).toBe('t1');
  });

  it('should authenticate with raw key', async () => {
    const result = await auth({ authorization: 'my-api-key' });
    expect(result.authenticated).toBe(true);
  });

  it('should reject missing authorization header', async () => {
    const result = await auth({});
    expect(result.authenticated).toBe(false);
    expect(result.error).toContain('Missing');
  });

  it('should reject invalid API key', async () => {
    const result = await auth({ authorization: 'Bearer wrong-key' });
    expect(result.authenticated).toBe(false);
    expect(result.error).toContain('Invalid');
  });

  it('should work with Map', async () => {
    const keyMap = new Map<string, Principal>();
    keyMap.set('key-1', principal);
    const mapAuth = createApiKeyAuth(keyMap);
    const result = await mapAuth({ authorization: 'Bearer key-1' });
    expect(result.authenticated).toBe(true);
  });
});

describe('createJwtAuth', () => {
  const principalExtractor = (payload: Record<string, unknown>) => ({
    tenantId: payload.tenant_id as string,
    userId: payload.sub as string,
    roles: (payload.roles as string[]) ?? [],
  });

  it('should authenticate valid JWT', async () => {
    const secret = 'test-secret-key';
    const auth = createJwtAuth({
      secret,
      extractPrincipal: principalExtractor,
    });

    const token = createHmacToken(
      { sub: 'user-1', tenant_id: 'tenant-1', roles: ['admin'] },
      secret
    );

    const result = await auth({ authorization: `Bearer ${token}` });
    expect(result.authenticated).toBe(true);
    expect(result.principal?.userId).toBe('user-1');
  });

  it('should reject missing authorization header', async () => {
    const auth = createJwtAuth({
      secret: 'secret',
      extractPrincipal: principalExtractor,
    });

    const result = await auth({});
    expect(result.authenticated).toBe(false);
    expect(result.error).toContain('Missing');
  });

  it('should reject non-Bearer token', async () => {
    const auth = createJwtAuth({
      secret: 'secret',
      extractPrincipal: principalExtractor,
    });

    const result = await auth({ authorization: 'Basic dXNlcjpwYXNz' });
    expect(result.authenticated).toBe(false);
    expect(result.error).toContain('Missing');
  });

  it('should reject invalid JWT format', async () => {
    const auth = createJwtAuth({
      secret: 'secret',
      extractPrincipal: principalExtractor,
    });

    const result = await auth({ authorization: 'Bearer not.a.valid.jwt.format' });
    expect(result.authenticated).toBe(false);
    expect(result.error).toContain('Invalid JWT');
  });

  it('should reject wrong secret', async () => {
    const auth = createJwtAuth({
      secret: 'correct-secret',
      extractPrincipal: principalExtractor,
    });

    const token = createHmacToken({ sub: 'user' }, 'wrong-secret');
    const result = await auth({ authorization: `Bearer ${token}` });
    expect(result.authenticated).toBe(false);
    expect(result.error).toContain('signature');
  });

  it('should reject expired token', async () => {
    const secret = 'test-secret';
    const auth = createJwtAuth({
      secret,
      extractPrincipal: principalExtractor,
    });

    const token = createHmacToken(
      { sub: 'user', exp: Math.floor(Date.now() / 1000) - 3600 },
      secret
    );

    const result = await auth({ authorization: `Bearer ${token}` });
    expect(result.authenticated).toBe(false);
    expect(result.error).toContain('expired');
  });

  it('should validate issuer', async () => {
    const secret = 'test-secret';
    const auth = createJwtAuth({
      secret,
      issuer: 'my-issuer',
      extractPrincipal: principalExtractor,
    });

    const token = createHmacToken({ sub: 'user', iss: 'wrong-issuer' }, secret);
    const result = await auth({ authorization: `Bearer ${token}` });
    expect(result.authenticated).toBe(false);
    expect(result.error).toContain('issuer');
  });

  it('should validate audience', async () => {
    const secret = 'test-secret';
    const auth = createJwtAuth({
      secret,
      audience: 'my-audience',
      extractPrincipal: principalExtractor,
    });

    const token = createHmacToken({ sub: 'user', aud: 'wrong-audience' }, secret);
    const result = await auth({ authorization: `Bearer ${token}` });
    expect(result.authenticated).toBe(false);
    expect(result.error).toContain('audience');
  });

  it('should use custom verifySignature', async () => {
    const auth = createJwtAuth({
      secret: 'any',
      verifySignature: () => true,
      extractPrincipal: principalExtractor,
    });

    const header = Buffer.from(JSON.stringify({ alg: 'HS256' })).toString('base64url');
    const payload = Buffer.from(JSON.stringify({ sub: 'user-1', tenant_id: 't1' })).toString('base64url');
    const fakeToken = `${header}.${payload}.fakesig`;

    const result = await auth({ authorization: `Bearer ${fakeToken}` });
    expect(result.authenticated).toBe(true);
  });
});

describe('extractTenantFromHeaders', () => {
  it('should extract from default header', () => {
    expect(extractTenantFromHeaders({ 'x-tenant-id': 'acme' })).toBe('acme');
  });

  it('should extract from custom header', () => {
    expect(extractTenantFromHeaders({ 'X-Org': 'org1' }, 'X-Org')).toBe('org1');
  });

  it('should return undefined for missing header', () => {
    expect(extractTenantFromHeaders({})).toBeUndefined();
  });
});

describe('principalFromHeaders', () => {
  it('should create principal from headers', () => {
    const result = principalFromHeaders({
      'x-tenant-id': 'acme',
      'x-user-id': 'user-1',
      'x-user-roles': 'admin,editor',
    });
    expect(result).toBeDefined();
    expect(result!.tenantId).toBe('acme');
    expect(result!.userId).toBe('user-1');
    expect(result!.roles).toEqual(['admin', 'editor']);
  });

  it('should return undefined if tenant missing', () => {
    const result = principalFromHeaders({ 'x-user-id': 'user-1' });
    expect(result).toBeUndefined();
  });

  it('should return undefined if user missing', () => {
    const result = principalFromHeaders({ 'x-tenant-id': 'acme' });
    expect(result).toBeUndefined();
  });

  it('should handle custom headers', () => {
    const result = principalFromHeaders(
      { 'X-Org': 'org1', 'X-User': 'user1' },
      { tenantHeader: 'X-Org', userHeader: 'X-User' }
    );
    expect(result).toBeDefined();
    expect(result!.tenantId).toBe('org1');
  });
});

describe('combineAuthMiddlewares', () => {
  it('should return first successful auth', async () => {
    const principal: Principal = { tenantId: 't1', userId: 'u1', roles: [] };
    const mw1 = createApiKeyAuth({ 'key-1': principal });
    const mw2 = createApiKeyAuth({ 'key-2': principal });
    const combined = combineAuthMiddlewares(mw1, mw2);

    const result = await combined({ authorization: 'Bearer key-1' });
    expect(result.authenticated).toBe(true);
  });

  it('should try next middleware if first fails', async () => {
    const principal: Principal = { tenantId: 't1', userId: 'u1', roles: [] };
    const mw1 = createApiKeyAuth({ 'key-1': principal });
    const mw2 = createApiKeyAuth({ 'key-2': principal });
    const combined = combineAuthMiddlewares(mw1, mw2);

    const result = await combined({ authorization: 'Bearer key-2' });
    expect(result.authenticated).toBe(true);
  });

  it('should fail if all middlewares fail', async () => {
    const principal: Principal = { tenantId: 't1', userId: 'u1', roles: [] };
    const mw = createApiKeyAuth({ 'key-1': principal });
    const combined = combineAuthMiddlewares(mw);

    const result = await combined({ authorization: 'Bearer wrong' });
    expect(result.authenticated).toBe(false);
  });
});

describe('createDevAuth', () => {
  it('should always authenticate with default principal', async () => {
    const principal: Principal = { tenantId: 'dev', userId: 'dev-user', roles: ['admin'] };
    const auth = createDevAuth(principal);

    const result = await auth({});
    expect(result.authenticated).toBe(true);
    expect(result.principal?.userId).toBe('dev-user');
  });
});