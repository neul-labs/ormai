/**
 * Audit middleware for automatic tool call logging.
 */

import { randomUUID } from 'crypto';
import type { RunContext } from '../core/context.js';
import type { Tool } from '../tools/base.js';
import { isOrmAIError } from '../core/errors.js';
import type { AuditStore } from './base.js';
import type { ErrorInfo } from './models.js';
import { createAuditRecord } from './models.js';

/**
 * Options for the audit middleware.
 */
export interface AuditMiddlewareOptions {
  /** Audit store to use */
  store: AuditStore;

  /** Whether to include inputs in audit records */
  includeInputs?: boolean;

  /** Whether to include outputs in audit records */
  includeOutputs?: boolean;

  /** Fields to redact from inputs */
  redactInputFields?: string[];

  /** Fields to redact from outputs */
  redactOutputFields?: string[];
}

/**
 * Wrap a tool with audit logging.
 */
export function withAudit<Input, Output>(
  tool: Tool<Input, Output>,
  options: AuditMiddlewareOptions
): Tool<Input, Output> {
  const { store, includeInputs = true, includeOutputs = false, redactInputFields = [], redactOutputFields = [] } =
    options;

  return {
    name: tool.name,
    description: tool.description,
    inputSchema: tool.inputSchema,

    async execute(input: Input, ctx: RunContext): Promise<Output> {
      const startTime = Date.now();
      const recordId = randomUUID();

      let result: Output | undefined;
      let error: ErrorInfo | undefined;

      try {
        result = await tool.execute(input, ctx);
        return result;
      } catch (e) {
        if (isOrmAIError(e)) {
          error = {
            type: e.name,
            message: e.message,
            code: e.code,
            details: e.details as Record<string, unknown>,
          };
        } else {
          error = {
            type: 'Error',
            message: e instanceof Error ? e.message : String(e),
            details: {},
          };
        }
        throw e;
      } finally {
        const durationMs = Date.now() - startTime;

        // Prepare inputs
        let inputs: Record<string, unknown> = {};
        if (includeInputs) {
          inputs = redactFields(input as Record<string, unknown>, redactInputFields);
        }

        // Prepare outputs
        let outputs: Record<string, unknown> | undefined;
        if (includeOutputs && result !== undefined) {
          outputs = redactFields(result as Record<string, unknown>, redactOutputFields);
        }

        const record = createAuditRecord({
          id: recordId,
          toolName: tool.name,
          principalId: ctx.principal.userId,
          tenantId: ctx.principal.tenantId,
          requestId: ctx.requestId,
          traceId: ctx.traceId,
          durationMs,
          inputs,
          outputs,
          error,
        });

        // Store asynchronously (don't await to avoid blocking)
        store.store(record).catch((err) => {
          console.error('Failed to store audit record:', err);
        });
      }
    },
  };
}

/**
 * Create an audited tool registry.
 */
export function createAuditedToolRegistry(
  tools: Tool<unknown, unknown>[],
  options: AuditMiddlewareOptions
): Tool<unknown, unknown>[] {
  return tools.map((tool) => withAudit(tool, options));
}

/**
 * Redact sensitive fields from an object.
 */
function redactFields(obj: Record<string, unknown>, fields: string[]): Record<string, unknown> {
  if (fields.length === 0) {
    return { ...obj };
  }

  const result: Record<string, unknown> = {};
  for (const [key, value] of Object.entries(obj)) {
    if (fields.includes(key)) {
      result[key] = '[REDACTED]';
    } else if (typeof value === 'object' && value !== null && !Array.isArray(value)) {
      result[key] = redactFields(value as Record<string, unknown>, fields);
    } else {
      result[key] = value;
    }
  }
  return result;
}
