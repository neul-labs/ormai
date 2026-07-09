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
 *
 * Verifies JWT signatures using HMAC-SHA256 (HS256) by default.
 * For production use with RS256 or other algorithms, provide a custom
 * `verifySignature` function.
 *
 * **Important**: Always provide a `secret` in production. The middleware
 * verifies the token signature to prevent forgery.
 */
export function createJwtAuth(options: {
  secret: string;
  issuer?: string;
  audience?: string;
  algorithm?: 'HS256' | 'HS384' | 'HS512';
  verifySignature?: (header: object, payload: object, signature: Uint8Array) => boolean;
  extractPrincipal: (payload: Record<string, unknown>) => Principal;
}): AuthMiddleware {
  return async (headers) => {
    const authHeader = headers['authorization'] || headers['Authorization'];
    if (!authHeader?.startsWith('Bearer ')) {
      return { authenticated: false, error: 'Missing or invalid Authorization header' };
    }

    const token = authHeader.slice(7);

    try {
      const parts = token.split('.');
      if (parts.length !== 3) {
        return { authenticated: false, error: 'Invalid JWT format' };
      }

      // Decode header and payload
      const headerStr = Buffer.from(parts[0], 'base64url').toString('utf-8');
      const header = JSON.parse(headerStr) as Record<string, unknown>;

      const payloadStr = Buffer.from(parts[1], 'base64url').toString('utf-8');
      const payload = JSON.parse(payloadStr) as Record<string, unknown>;

      // Verify signature
      const algorithm = options.algorithm ?? 'HS256';
      const algMap: Record<string, string> = {
        HS256: 'SHA-256',
        HS384: 'SHA-384',
        HS512: 'SHA-512',
      };

      if (options.verifySignature) {
        const signatureBytes = Buffer.from(parts[2], 'base64url');
        if (!options.verifySignature(header, payload, signatureBytes)) {
          return { authenticated: false, error: 'Invalid JWT signature' };
        }
      } else {
        // Verify signature using Web Crypto API (available in Node.js 15+, all modern browsers)
        const message = `${parts[0]}.${parts[1]}`;
        const encoder = new TextEncoder();
        const keyData = encoder.encode(options.secret);

        let key: CryptoKey;
        try {
          key = await crypto.subtle.importKey(
            'raw',
            keyData,
            { name: 'HMAC', hash: algMap[algorithm] ?? 'SHA-256' },
            false,
            ['verify']
          );
        } catch {
          // Fallback for environments without Web Crypto API (e.g., older Node.js)
          // Use Node.js crypto module
          const crypto = await import('crypto');
          const expectedSig = crypto
            .createHmac(algMap[algorithm]?.replace('SHA-', 'sha') ?? 'sha256', options.secret)
            .update(message)
            .digest('base64url');
          if (parts[2] !== expectedSig) {
            return { authenticated: false, error: 'Invalid JWT signature' };
          }
          // Skip Web Crypto verification since we already verified
          return verifyPayload();
        }

        const signatureBuffer = Buffer.from(parts[2], 'base64url');
        const valid = await crypto.subtle.verify(
          { name: 'HMAC' },
          key,
          signatureBuffer,
          encoder.encode(message)
        );

        if (!valid) {
          return { authenticated: false, error: 'Invalid JWT signature' };
        }
      }

      return verifyPayload();

      function verifyPayload(): AuthResult {
        // Check expiration
        if (payload.exp && typeof payload.exp === 'number') {
          if (Date.now() / 1000 > payload.exp) {
            return { authenticated: false, error: 'Token expired' };
          }
        }

        // Check not-before
        if (payload.nbf && typeof payload.nbf === 'number') {
          if (Date.now() / 1000 < payload.nbf) {
            return { authenticated: false, error: 'Token not yet valid' };
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
      }
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
