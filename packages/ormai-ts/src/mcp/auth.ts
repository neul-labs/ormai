/**
 * Authentication helpers for MCP server.
 */

import type { Principal, RunContext } from '../core/context.js';
import { createContext, createPrincipal } from '../core/context.js';

/**
 * Authentication result from middleware.
 */
export interface AuthResult {
  authenticated: boolean;
  principal?: Principal;
  error?: string;
}

/**
 * Authentication middleware function type.
 */
export type AuthMiddleware = (
  headers: Record<string, string | undefined>
) => Promise<AuthResult> | AuthResult;

/**
 * Create a simple API key authentication middleware.
 */
export function createApiKeyAuth(
  validKeys: Map<string, Principal> | Record<string, Principal>
): AuthMiddleware {
  const keyMap = validKeys instanceof Map ? validKeys : new Map(Object.entries(validKeys));

  return (headers) => {
    const authHeader = headers['authorization'] || headers['Authorization'];
    if (!authHeader) {
      return { authenticated: false, error: 'Missing Authorization header' };
    }

    // Support "Bearer <key>" or just "<key>"
    const key = authHeader.startsWith('Bearer ')
      ? authHeader.slice(7)
      : authHeader;

    const principal = keyMap.get(key);
    if (!principal) {
      return { authenticated: false, error: 'Invalid API key' };
    }

    return { authenticated: true, principal };
  };
}

/**
 * Create a JWT authentication middleware.
 * This is a placeholder that can be extended with actual JWT verification.
 */
export function createJwtAuth(options: {
  secret: string;
  issuer?: string;
  audience?: string;
  extractPrincipal: (payload: Record<string, unknown>) => Principal;
}): AuthMiddleware {
  return async (headers) => {
    const authHeader = headers['authorization'] || headers['Authorization'];
    if (!authHeader?.startsWith('Bearer ')) {
      return { authenticated: false, error: 'Missing or invalid Authorization header' };
    }

    const token = authHeader.slice(7);

    try {
      // This is a simplified implementation
      // In production, use a proper JWT library like jose
      const parts = token.split('.');
      if (parts.length !== 3) {
        return { authenticated: false, error: 'Invalid JWT format' };
      }

      const payloadStr = Buffer.from(parts[1], 'base64url').toString('utf-8');
      const payload = JSON.parse(payloadStr) as Record<string, unknown>;

      // Check expiration
      if (payload.exp && typeof payload.exp === 'number') {
        if (Date.now() / 1000 > payload.exp) {
          return { authenticated: false, error: 'Token expired' };
        }
      }

      // Check issuer
      if (options.issuer && payload.iss !== options.issuer) {
        return { authenticated: false, error: 'Invalid issuer' };
      }

      // Check audience
      if (options.audience && payload.aud !== options.audience) {
        return { authenticated: false, error: 'Invalid audience' };
      }

      const principal = options.extractPrincipal(payload);
      return { authenticated: true, principal };
    } catch {
      return { authenticated: false, error: 'Failed to parse JWT' };
    }
  };
}

/**
 * Create a context factory for authenticated requests.
 */
export function createContextFactory<DB>(
  db: DB,
  defaultMetadata?: Record<string, unknown>
): (principal: Principal, requestId?: string) => RunContext<DB> {
  return (principal, requestId) => {
    return createContext({
      db,
      tenantId: principal.tenantId,
      userId: principal.userId,
      roles: [...principal.roles],
      requestId,
      metadata: { ...defaultMetadata, ...principal.metadata },
    });
  };
}

/**
 * Extract tenant ID from common header patterns.
 */
export function extractTenantFromHeaders(
  headers: Record<string, string | undefined>,
  headerName = 'x-tenant-id'
): string | undefined {
  return headers[headerName] || headers[headerName.toLowerCase()];
}

/**
 * Create a principal from common header patterns.
 */
export function principalFromHeaders(
  headers: Record<string, string | undefined>,
  options?: {
    tenantHeader?: string;
    userHeader?: string;
    rolesHeader?: string;
    rolesSeparator?: string;
  }
): Principal | undefined {
  const {
    tenantHeader = 'x-tenant-id',
    userHeader = 'x-user-id',
    rolesHeader = 'x-user-roles',
    rolesSeparator = ',',
  } = options ?? {};

  const tenantId = headers[tenantHeader] || headers[tenantHeader.toLowerCase()];
  const userId = headers[userHeader] || headers[userHeader.toLowerCase()];

  if (!tenantId || !userId) {
    return undefined;
  }

  const rolesStr = headers[rolesHeader] || headers[rolesHeader.toLowerCase()];
  const roles = rolesStr ? rolesStr.split(rolesSeparator).map((r) => r.trim()) : [];

  return createPrincipal({ tenantId, userId, roles });
}

/**
 * Combine multiple auth middlewares (try each in order).
 */
export function combineAuthMiddlewares(...middlewares: AuthMiddleware[]): AuthMiddleware {
  return async (headers) => {
    for (const middleware of middlewares) {
      const result = await middleware(headers);
      if (result.authenticated) {
        return result;
      }
    }
    return { authenticated: false, error: 'Authentication failed' };
  };
}

/**
 * Create a no-op auth middleware that always succeeds with a default principal.
 * Useful for development/testing only.
 */
export function createDevAuth(defaultPrincipal: Principal): AuthMiddleware {
  return () => ({ authenticated: true, principal: defaultPrincipal });
}
