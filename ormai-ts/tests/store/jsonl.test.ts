/**
 * Tests for JSONL file-based audit store.
 */

import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import { mkdtempSync, rmSync } from 'fs';
import { join } from 'path';
import { tmpdir } from 'os';
import { JsonlAuditStore, createJsonlAuditStore } from '../../src/store/jsonl.js';
import { createAuditRecord } from '../../src/store/models.js';

function makeRecord(overrides: Record<string, unknown> = {}): ReturnType<typeof createAuditRecord> {
  return createAuditRecord({
    id: 'rec-001',
    toolName: 'query',
    principalId: 'user-1',
    tenantId: 'tenant-1',
    ...overrides,
  });
}

function tempFilePath(): string {
  const dir = mkdtempSync(join(tmpdir(), 'jsonl-test-'));
  return join(dir, 'audit.jsonl');
}

function cleanupPath(filePath: string): void {
  try {
    const dir = filePath.substring(0, filePath.lastIndexOf('/'));
    rmSync(dir, { recursive: true, force: true });
  } catch {
    // ignore
  }
}

describe('JsonlAuditStore', () => {
  let store: JsonlAuditStore;
  let filePath: string;

  beforeEach(() => {
    filePath = tempFilePath();
    store = new JsonlAuditStore({ path: filePath });
  });

  afterEach(async () => {
    await store.clear();
    cleanupPath(filePath);
  });

  describe('store and get', () => {
    it('should store and retrieve a record', async () => {
      const record = makeRecord();
      await store.store(record);
      const result = await store.get('rec-001');
      expect(result).toBeDefined();
      expect(result!.id).toBe('rec-001');
      expect(result!.toolName).toBe('query');
      expect(result!.principalId).toBe('user-1');
      expect(result!.tenantId).toBe('tenant-1');
    });

    it('should return undefined for nonexistent record', async () => {
      const result = await store.get('nonexistent');
      expect(result).toBeUndefined();
    });

    it('should preserve timestamp as Date', async () => {
      const date = new Date('2024-06-15T12:30:00Z');
      const record = makeRecord({ timestamp: date });
      await store.store(record);
      const result = await store.get('rec-001');
      expect(result).toBeDefined();
      expect(result!.timestamp).toBeInstanceOf(Date);
      expect(result!.timestamp.toISOString()).toBe(date.toISOString());
    });

    it('should preserve optional fields', async () => {
      const record = makeRecord({
        id: 'rec-002',
        requestId: 'req-1',
        traceId: 'trace-1',
        durationMs: 42,
        inputs: { sql: 'SELECT 1' },
        outputs: { count: 1 },
        policyDecisions: ['allowed'],
        rowCount: 10,
        affectedRows: 5,
        error: {
          type: 'TestError',
          message: 'failed',
          code: 'E001',
          details: { field: 'email' },
        },
        reason: 'user action',
        metadata: { source: 'api' },
      });
      await store.store(record);
      const result = await store.get('rec-002');
      expect(result).toBeDefined();
      expect(result!.requestId).toBe('req-1');
      expect(result!.traceId).toBe('trace-1');
      expect(result!.durationMs).toBe(42);
      expect(result!.inputs).toEqual({ sql: 'SELECT 1' });
      expect(result!.outputs).toEqual({ count: 1 });
      expect(result!.policyDecisions).toEqual(['allowed']);
      expect(result!.rowCount).toBe(10);
      expect(result!.affectedRows).toBe(5);
      expect(result!.error!.type).toBe('TestError');
      expect(result!.error!.code).toBe('E001');
      expect(result!.reason).toBe('user action');
      expect(result!.metadata).toEqual({ source: 'api' });
    });
  });

  describe('query', () => {
    beforeEach(async () => {
      await store.store(makeRecord({
        id: 'rec-1',
        tenantId: 'tenant-1',
        principalId: 'user-1',
        toolName: 'query',
      }));
      await store.store(makeRecord({
        id: 'rec-2',
        tenantId: 'tenant-2',
        principalId: 'user-2',
        toolName: 'create',
      }));
      await store.store(makeRecord({
        id: 'rec-3',
        tenantId: 'tenant-1',
        principalId: 'user-1',
        toolName: 'create',
      }));
    });

    it('should return all records with empty filter', async () => {
      const results = await store.query({});
      expect(results.length).toBe(3);
    });

    it('should filter by tenantId', async () => {
      const results = await store.query({ tenantId: 'tenant-1' });
      expect(results.length).toBe(2);
      expect(results.every((r) => r.tenantId === 'tenant-1')).toBe(true);
    });

    it('should filter by principalId', async () => {
      const results = await store.query({ principalId: 'user-2' });
      expect(results.length).toBe(1);
    });

    it('should filter by toolName', async () => {
      const results = await store.query({ toolName: 'create' });
      expect(results.length).toBe(2);
    });

    it('should apply limit', async () => {
      const results = await store.query({ limit: 2 });
      expect(results.length).toBe(2);
    });

    it('should apply offset', async () => {
      const results = await store.query({ offset: 1 });
      expect(results.length).toBe(2);
    });

    it('should return empty array when file does not exist', async () => {
      const emptyStore = new JsonlAuditStore({
        path: join(tmpdir(), 'nonexistent', 'audit.jsonl'),
      });
      const result = await emptyStore.get('whatever');
      expect(result).toBeUndefined();
      const results = await emptyStore.query({});
      expect(results).toEqual([]);
    });
  });

  describe('file rotation', () => {
    it('should rotate file when size exceeds maxFileSizeBytes', async () => {
      const smallStore = new JsonlAuditStore({
        path: filePath,
        maxFileSizeBytes: 1, // very small to trigger rotation
      });

      // First write creates file, second should trigger rotation check
      await smallStore.store(makeRecord({ id: 'rec-a' }));
      await smallStore.store(makeRecord({ id: 'rec-b' }));

      // The second record should still be stored (in new file after rotation)
      const result = await smallStore.get('rec-b');
      expect(result).toBeDefined();
      expect(result!.id).toBe('rec-b');

      await smallStore.clear();
    });
  });

  describe('clear', () => {
    it('should clear all records', async () => {
      await store.store(makeRecord({ id: '1' }));
      await store.store(makeRecord({ id: '2' }));
      await store.clear();
      const results = await store.query({});
      expect(results.length).toBe(0);
    });
  });
});

describe('createJsonlAuditStore', () => {
  it('should create a JsonlAuditStore instance', () => {
    const filePath = tempFilePath();
    const s = createJsonlAuditStore(filePath);
    expect(s).toBeInstanceOf(JsonlAuditStore);
    cleanupPath(filePath);
  });

  it('should pass options to the store', () => {
    const filePath = tempFilePath();
    const s = createJsonlAuditStore(filePath, {
      maxFileSizeBytes: 1024,
      compressOnRotation: true,
    });
    expect(s).toBeInstanceOf(JsonlAuditStore);
    cleanupPath(filePath);
  });
});