/**
 * Tests for audit record models and Zod schemas.
 */

import { describe, it, expect } from 'vitest';
import {
  ErrorInfoSchema,
  AuditRecordSchema,
  isSuccess,
  toLogDict,
  createAuditRecord,
} from '@ormai/core';

describe('ErrorInfoSchema', () => {
  it('should parse a valid ErrorInfo', () => {
    const result = ErrorInfoSchema.parse({
      type: 'TestError',
      message: 'something went wrong',
    });
    expect(result.type).toBe('TestError');
    expect(result.message).toBe('something went wrong');
    expect(result.code).toBeUndefined();
  });

  it('should parse ErrorInfo with optional code', () => {
    const result = ErrorInfoSchema.parse({
      type: 'TestError',
      message: 'fail',
      code: 'E001',
    });
    expect(result.code).toBe('E001');
  });

  it('should default details to empty object', () => {
    const result = ErrorInfoSchema.parse({
      type: 'TestError',
      message: 'fail',
    });
    expect(result.details).toEqual({});
  });

  it('should reject ErrorInfo missing required fields', () => {
    expect(() => ErrorInfoSchema.parse({ type: 'TestError' })).toThrow();
    expect(() => ErrorInfoSchema.parse({ message: 'fail' })).toThrow();
    expect(() => ErrorInfoSchema.parse({})).toThrow();
  });

  it('should reject ErrorInfo with wrong types', () => {
    expect(() =>
      ErrorInfoSchema.parse({ type: 123, message: 'fail' })
    ).toThrow();
    expect(() =>
      ErrorInfoSchema.parse({ type: 'TestError', message: [] })
    ).toThrow();
  });
});

describe('AuditRecordSchema', () => {
  const validRecord = {
    id: 'rec-001',
    toolName: 'query',
    principalId: 'user-1',
    tenantId: 'tenant-1',
    timestamp: new Date(),
  };

  it('should parse a minimal valid record', () => {
    const result = AuditRecordSchema.parse(validRecord);
    expect(result.id).toBe('rec-001');
    expect(result.toolName).toBe('query');
    expect(result.principalId).toBe('user-1');
    expect(result.tenantId).toBe('tenant-1');
    expect(result.timestamp).toBeInstanceOf(Date);
  });

  it('should apply defaults for optional collections', () => {
    const result = AuditRecordSchema.parse(validRecord);
    expect(result.inputs).toEqual({});
    expect(result.policyDecisions).toEqual([]);
  });

  it('should parse a fully populated record', () => {
    const result = AuditRecordSchema.parse({
      ...validRecord,
      requestId: 'req-1',
      traceId: 'trace-1',
      durationMs: 150,
      inputs: { sql: 'SELECT 1' },
      outputs: { rows: 1 },
      policyDecisions: ['allowed'],
      rowCount: 10,
      affectedRows: 3,
      error: undefined,
      beforeSnapshot: { status: 'draft' },
      afterSnapshot: { status: 'published' },
      reason: 'user requested',
      metadata: { source: 'api' },
    });
    expect(result.requestId).toBe('req-1');
    expect(result.traceId).toBe('trace-1');
    expect(result.durationMs).toBe(150);
    expect(result.inputs).toEqual({ sql: 'SELECT 1' });
    expect(result.outputs).toEqual({ rows: 1 });
    expect(result.policyDecisions).toEqual(['allowed']);
    expect(result.rowCount).toBe(10);
    expect(result.affectedRows).toBe(3);
    expect(result.beforeSnapshot).toEqual({ status: 'draft' });
    expect(result.afterSnapshot).toEqual({ status: 'published' });
    expect(result.reason).toBe('user requested');
    expect(result.metadata).toEqual({ source: 'api' });
  });

  it('should parse a record with error', () => {
    const result = AuditRecordSchema.parse({
      ...validRecord,
      error: {
        type: 'QueryTooBroadError',
        message: 'Too broad',
        code: 'QUERY_TOO_BROAD',
        details: { model: 'User' },
      },
    });
    expect(result.error).toBeDefined();
    expect(result.error!.type).toBe('QueryTooBroadError');
    expect(result.error!.code).toBe('QUERY_TOO_BROAD');
  });

  it('should reject a record missing required id', () => {
    expect(() =>
      AuditRecordSchema.parse({
        toolName: 'query',
        principalId: 'user-1',
        tenantId: 'tenant-1',
        timestamp: new Date(),
      })
    ).toThrow();
  });

  it('should reject a record missing required toolName', () => {
    expect(() =>
      AuditRecordSchema.parse({
        id: 'rec-001',
        principalId: 'user-1',
        tenantId: 'tenant-1',
        timestamp: new Date(),
      })
    ).toThrow();
  });

  it('should reject a record with wrong timestamp type', () => {
    expect(() =>
      AuditRecordSchema.parse({
        ...validRecord,
        timestamp: '2024-01-01T00:00:00Z',
      })
    ).toThrow();
  });

  it('should reject a record with wrong rowCount type (float)', () => {
    expect(() =>
      AuditRecordSchema.parse({
        ...validRecord,
        rowCount: 3.5,
      })
    ).toThrow();
  });

  it('should accept integer rowCount and affectedRows', () => {
    const result = AuditRecordSchema.parse({
      ...validRecord,
      rowCount: 3,
      affectedRows: 0,
    });
    expect(result.rowCount).toBe(3);
    expect(result.affectedRows).toBe(0);
  });
});

describe('isSuccess', () => {
  it('should return true for records without an error', () => {
    const record = createAuditRecord({
      id: 'rec-001',
      toolName: 'query',
      principalId: 'user-1',
      tenantId: 'tenant-1',
    });
    expect(isSuccess(record)).toBe(true);
  });

  it('should return false for records with an error', () => {
    const record = createAuditRecord({
      id: 'rec-001',
      toolName: 'query',
      principalId: 'user-1',
      tenantId: 'tenant-1',
      error: {
        type: 'TestError',
        message: 'fail',
        details: {},
      },
    });
    expect(isSuccess(record)).toBe(false);
  });
});

describe('toLogDict', () => {
  it('should convert timestamp to ISO string', () => {
    const date = new Date('2024-06-15T12:00:00Z');
    const record = createAuditRecord({
      id: 'rec-001',
      toolName: 'query',
      principalId: 'user-1',
      tenantId: 'tenant-1',
      timestamp: date,
    });
    const logDict = toLogDict(record);
    expect(logDict.timestamp).toBe('2024-06-15T12:00:00.000Z');
  });

  it('should spread all record fields', () => {
    const record = createAuditRecord({
      id: 'rec-001',
      toolName: 'query',
      principalId: 'user-1',
      tenantId: 'tenant-1',
    });
    const logDict = toLogDict(record);
    expect(logDict.id).toBe('rec-001');
    expect(logDict.toolName).toBe('query');
    expect(logDict.principalId).toBe('user-1');
    expect(logDict.tenantId).toBe('tenant-1');
  });
});

describe('createAuditRecord', () => {
  it('should create a record with defaults', () => {
    const record = createAuditRecord({
      id: 'rec-001',
      toolName: 'query',
      principalId: 'user-1',
      tenantId: 'tenant-1',
    });
    expect(record.id).toBe('rec-001');
    expect(record.inputs).toEqual({});
    expect(record.policyDecisions).toEqual([]);
    expect(record.timestamp).toBeInstanceOf(Date);
  });

  it('should use provided timestamp', () => {
    const date = new Date('2024-01-01T00:00:00Z');
    const record = createAuditRecord({
      id: 'rec-001',
      toolName: 'query',
      principalId: 'user-1',
      tenantId: 'tenant-1',
      timestamp: date,
    });
    expect(record.timestamp).toEqual(date);
  });

  it('should use provided inputs and policyDecisions', () => {
    const record = createAuditRecord({
      id: 'rec-001',
      toolName: 'query',
      principalId: 'user-1',
      tenantId: 'tenant-1',
      inputs: { sql: 'SELECT * FROM users' },
      policyDecisions: ['allowed', 'scoped'],
    });
    expect(record.inputs).toEqual({ sql: 'SELECT * FROM users' });
    expect(record.policyDecisions).toEqual(['allowed', 'scoped']);
  });
});