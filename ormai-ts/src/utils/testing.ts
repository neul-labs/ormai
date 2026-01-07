/**
 * Testing utilities for OrmAI.
 */

import type { RunContext } from '../core/context.js';
import { createContext } from '../core/context.js';
import type { FieldMetadata, ModelMetadata, SchemaMetadata } from '../core/types.js';
import type { Policy } from '../policy/models.js';
import { PolicySchema } from '../policy/models.js';

/**
 * Create a test context with minimal configuration.
 */
export function createTestContext<DB>(
  db: DB,
  opts?: {
    tenantId?: string;
    userId?: string;
    roles?: string[];
    requestId?: string;
  }
): RunContext<DB> {
  return createContext({
    db,
    tenantId: opts?.tenantId ?? 'test-tenant',
    userId: opts?.userId ?? 'test-user',
    roles: opts?.roles ?? [],
    requestId: opts?.requestId,
  });
}

/**
 * Create a test schema with minimal configuration.
 */
export function createTestSchema(models: Record<string, Partial<ModelMetadata>>): SchemaMetadata {
  const result: Record<string, ModelMetadata> = {};

  for (const [name, config] of Object.entries(models)) {
    const fields: Record<string, FieldMetadata> = {};

    // Add id field by default
    if (!config.fields?.id) {
      fields.id = {
        name: 'id',
        fieldType: 'integer',
        nullable: false,
        primaryKey: true,
      };
    }

    // Add provided fields
    if (config.fields) {
      for (const [fieldName, fieldConfig] of Object.entries(config.fields)) {
        fields[fieldName] = {
          name: fieldName,
          fieldType: fieldConfig.fieldType ?? 'string',
          nullable: fieldConfig.nullable ?? true,
          primaryKey: fieldConfig.primaryKey ?? false,
          default: fieldConfig.default,
          description: fieldConfig.description,
        };
      }
    }

    result[name] = {
      name,
      tableName: config.tableName ?? name.toLowerCase(),
      fields,
      relations: config.relations ?? {},
      primaryKey: config.primaryKey ?? 'id',
      primaryKeys: config.primaryKeys,
      description: config.description,
    };
  }

  return { models: result };
}

/**
 * Create a test policy with minimal configuration.
 */
export function createTestPolicy(
  models: string[],
  opts?: {
    writesEnabled?: boolean;
    requireTenantScope?: boolean;
    tenantScopeField?: string;
  }
): Policy {
  const modelPolicies: Record<string, unknown> = {};

  for (const model of models) {
    modelPolicies[model] = {
      allowed: true,
      readable: true,
      writable: opts?.writesEnabled ?? false,
      rowPolicy: opts?.tenantScopeField
        ? { tenantScopeField: opts.tenantScopeField }
        : undefined,
    };
  }

  return PolicySchema.parse({
    models: modelPolicies,
    requireTenantScope: opts?.requireTenantScope ?? false,
    writesEnabled: opts?.writesEnabled ?? false,
    defaultRowPolicy: opts?.tenantScopeField
      ? { tenantScopeField: opts.tenantScopeField }
      : {},
  });
}

/**
 * Mock function type for testing.
 */
export type MockFn = (...args: unknown[]) => unknown;
export type AsyncMockFn = (...args: unknown[]) => Promise<unknown>;

/**
 * Mock adapter interface for testing.
 */
export interface MockAdapter {
  introspect: () => Promise<SchemaMetadata>;
  compileQuery: MockFn;
  executeQuery: AsyncMockFn;
  compileGet: MockFn;
  executeGet: AsyncMockFn;
  compileAggregate: MockFn;
  executeAggregate: AsyncMockFn;
  transaction: <T>(ctx: RunContext, fn: () => Promise<T>) => Promise<T>;
  compileCreate: MockFn;
  executeCreate: AsyncMockFn;
  compileUpdate: MockFn;
  executeUpdate: AsyncMockFn;
  compileDelete: MockFn;
  executeDelete: AsyncMockFn;
  compileBulkUpdate: MockFn;
  executeBulkUpdate: AsyncMockFn;
}

/**
 * Create a mock adapter for testing.
 */
export function createMockAdapter(schema: SchemaMetadata): MockAdapter {
  const mockFn = (): unknown => ({});
  const asyncMockFn = async (): Promise<unknown> => ({});

  return {
    introspect: async () => schema,
    compileQuery: mockFn,
    executeQuery: asyncMockFn,
    compileGet: mockFn,
    executeGet: asyncMockFn,
    compileAggregate: mockFn,
    executeAggregate: asyncMockFn,
    transaction: async <T>(_ctx: RunContext, fn: () => Promise<T>) => fn(),
    compileCreate: mockFn,
    executeCreate: asyncMockFn,
    compileUpdate: mockFn,
    executeUpdate: asyncMockFn,
    compileDelete: mockFn,
    executeDelete: asyncMockFn,
    compileBulkUpdate: mockFn,
    executeBulkUpdate: asyncMockFn,
  };
}

/**
 * Assert that an async function throws a specific error.
 */
export async function assertThrows(
  fn: () => Promise<unknown>,
  errorType?: new (...args: unknown[]) => Error,
  messageContains?: string
): Promise<Error> {
  let error: Error | undefined;

  try {
    await fn();
  } catch (e) {
    error = e as Error;
  }

  if (!error) {
    throw new Error('Expected function to throw, but it did not');
  }

  if (errorType && !(error instanceof errorType)) {
    throw new Error(`Expected error of type ${errorType.name}, got ${(error as Error).constructor.name}`);
  }

  if (messageContains && !error.message.includes(messageContains)) {
    throw new Error(`Expected error message to contain '${messageContains}', got '${error.message}'`);
  }

  return error;
}
