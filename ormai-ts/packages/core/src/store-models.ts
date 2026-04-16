/**
 * Audit record models.
 */

import { z } from 'zod';

/**
 * Error information for failed tool calls.
 */
export const ErrorInfoSchema = z
  .object({
    type: z.string(),
    message: z.string(),
    code: z.string().optional(),
    details: z.record(z.unknown()).default({}),
  })
  .readonly();

export type ErrorInfo = z.infer<typeof ErrorInfoSchema>;

/**
 * Record of a single tool call execution.
 *
 * Captures all information needed for auditing and compliance.
 */
export const AuditRecordSchema = z
  .object({
    /** Unique identifier for this audit record */
    id: z.string(),

    /** Tool name */
    toolName: z.string(),

    /** Principal information */
    principalId: z.string(),
    tenantId: z.string(),

    /** Request tracking */
    requestId: z.string().optional(),
    traceId: z.string().optional(),

    /** Timing */
    timestamp: z.date(),
    durationMs: z.number().optional(),

    /** Request details (sanitized - no sensitive data) */
    inputs: z.record(z.unknown()).default({}),

    /** Response data (sanitized) */
    outputs: z.record(z.unknown()).optional(),

    /** Policy decisions made during execution */
    policyDecisions: z.array(z.string()).default([]),

    /** Result summary */
    rowCount: z.number().int().optional(),
    affectedRows: z.number().int().optional(),

    /** Error information (if failed) */
    error: ErrorInfoSchema.optional(),

    /** Optional before/after snapshots for write operations */
    beforeSnapshot: z.record(z.unknown()).optional(),
    afterSnapshot: z.record(z.unknown()).optional(),

    /** Reason for write operations */
    reason: z.string().optional(),

    /** Additional metadata */
    metadata: z.record(z.unknown()).optional(),
  })
  .readonly();

export type AuditRecord = z.infer<typeof AuditRecordSchema>;

/**
 * Check if an audit record represents a successful operation.
 */
export function isSuccess(record: AuditRecord): boolean {
  return record.error === undefined;
}

/**
 * Convert an audit record to a log-friendly object.
 */
export function toLogDict(record: AuditRecord): Record<string, unknown> {
  return {
    ...record,
    timestamp: record.timestamp.toISOString(),
  };
}

/**
 * Create an audit record from tool execution.
 */
export function createAuditRecord(opts: {
  id: string;
  toolName: string;
  principalId: string;
  tenantId: string;
  requestId?: string;
  traceId?: string;
  timestamp?: Date;
  durationMs?: number;
  inputs?: Record<string, unknown>;
  outputs?: Record<string, unknown>;
  policyDecisions?: string[];
  rowCount?: number;
  affectedRows?: number;
  error?: ErrorInfo;
  beforeSnapshot?: Record<string, unknown>;
  afterSnapshot?: Record<string, unknown>;
  reason?: string;
  metadata?: Record<string, unknown>;
}): AuditRecord {
  return AuditRecordSchema.parse({
    ...opts,
    timestamp: opts.timestamp ?? new Date(),
    inputs: opts.inputs ?? {},
    policyDecisions: opts.policyDecisions ?? [],
  });
}
