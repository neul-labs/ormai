/**
 * Execution context for OrmAI tool calls.
 *
 * The context carries identity information, database connection, and request
 * metadata through the entire tool execution pipeline.
 */

import { randomUUID } from 'crypto';

/**
 * Identity information for the executing user/tenant.
 *
 * Principal is immutable and carries all identity claims needed for
 * policy evaluation and audit logging.
 */
export interface Principal {
  /** Tenant identifier for multi-tenancy scoping */
  readonly tenantId: string;

  /** User identifier for audit logging */
  readonly userId: string;

  /** Roles for role-based access control */
  readonly roles: readonly string[];

  /** Additional identity metadata */
  readonly metadata?: Readonly<Record<string, unknown>>;
}

/**
 * Create a new Principal.
 */
export function createPrincipal(opts: {
  tenantId: string;
  userId: string;
  roles?: readonly string[];
  metadata?: Record<string, unknown>;
}): Principal {
  return Object.freeze({
    tenantId: opts.tenantId,
    userId: opts.userId,
    roles: Object.freeze(opts.roles ?? []),
    metadata: opts.metadata ? Object.freeze({ ...opts.metadata }) : undefined,
  });
}

/**
 * Check if a principal has a specific role.
 */
export function hasRole(principal: Principal, role: string): boolean {
  return principal.roles.includes(role);
}

/**
 * Check if a principal has any of the specified roles.
 */
export function hasAnyRole(principal: Principal, ...roles: string[]): boolean {
  return roles.some((role) => principal.roles.includes(role));
}

/**
 * Execution context for a tool call.
 *
 * RunContext is created for each request and carries all information
 * needed for policy evaluation, query execution, and auditing.
 *
 * @typeParam DB - The database client type (e.g., PrismaClient)
 */
export interface RunContext<DB = unknown> {
  /** Identity of the executing user/tenant */
  readonly principal: Principal;

  /** Database client/connection */
  readonly db: DB;

  /** Unique request identifier for tracing */
  readonly requestId: string;

  /** Distributed trace ID (optional) */
  readonly traceId?: string;

  /** Current timestamp at request start */
  readonly now: Date;

  /** Additional request metadata */
  readonly metadata?: Readonly<Record<string, unknown>>;
}

/**
 * Options for creating a RunContext.
 */
export interface CreateContextOptions<DB> {
  /** Tenant ID */
  tenantId: string;

  /** User ID */
  userId: string;

  /** Database client */
  db: DB;

  /** User roles (optional) */
  roles?: readonly string[];

  /** Request ID (auto-generated if not provided) */
  requestId?: string;

  /** Trace ID for distributed tracing */
  traceId?: string;

  /** Additional metadata */
  metadata?: Record<string, unknown>;
}

/**
 * Create a new RunContext.
 */
export function createContext<DB>(opts: CreateContextOptions<DB>): RunContext<DB> {
  const principal = createPrincipal({
    tenantId: opts.tenantId,
    userId: opts.userId,
    roles: opts.roles,
  });

  return Object.freeze({
    principal,
    db: opts.db,
    requestId: opts.requestId ?? randomUUID(),
    traceId: opts.traceId,
    now: new Date(),
    metadata: opts.metadata ? Object.freeze({ ...opts.metadata }) : undefined,
  });
}

/**
 * Create a context with full options including a pre-built Principal.
 */
export function createContextWithPrincipal<DB>(opts: {
  principal: Principal;
  db: DB;
  requestId?: string;
  traceId?: string;
  metadata?: Record<string, unknown>;
}): RunContext<DB> {
  return Object.freeze({
    principal: opts.principal,
    db: opts.db,
    requestId: opts.requestId ?? randomUUID(),
    traceId: opts.traceId,
    now: new Date(),
    metadata: opts.metadata ? Object.freeze({ ...opts.metadata }) : undefined,
  });
}

/**
 * Type guard to check if a value is a valid Principal.
 */
export function isPrincipal(value: unknown): value is Principal {
  if (typeof value !== 'object' || value === null) {
    return false;
  }
  const obj = value as Record<string, unknown>;
  return (
    typeof obj['tenantId'] === 'string' &&
    typeof obj['userId'] === 'string' &&
    Array.isArray(obj['roles'])
  );
}

/**
 * Type guard to check if a value is a valid RunContext.
 */
export function isRunContext<DB>(value: unknown): value is RunContext<DB> {
  if (typeof value !== 'object' || value === null) {
    return false;
  }
  const obj = value as Record<string, unknown>;
  return (
    isPrincipal(obj['principal']) &&
    typeof obj['requestId'] === 'string' &&
    obj['now'] instanceof Date
  );
}
