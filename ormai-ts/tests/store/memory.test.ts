/**
 * Tests for in-memory audit store.
 */

import { describe, it, expect, beforeEach } from 'vitest';
import { InMemoryAuditStore } from '@ormai/store';
import { createAuditRecord } from '@ormai/core';

function makeRecord(overrides: Record<string, unknown> = {}): ReturnType<typeof createAuditRecord> {
  return createAuditRecord({
    id: 'rec-001',
    toolName: 'query',
    principalId: 'user-1',
    tenantId: 'tenant-1',
    ...overrides,
  });
}

describe('InMemoryAuditStore', () => {
  let store: InMemoryAuditStore;

  beforeEach(() => {
    store = new InMemoryAuditStore();
  });

  describe('store and get', () => {
    it('should store and retrieve a record', async () => {
      const record = makeRecord();
      await store.store(record);
      const result = await store.get('rec-001');
      expect(result).toBeDefined();
      expect(result!.id).toBe('rec-001');
    });

    it('should return undefined for nonexistent record', async () => {
      const result = await store.get('nonexistent');
      expect(result).toBeUndefined();
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

    it('should query all records with no filter', async () => {
      const results = await store.query({});
      expect(results.length).toBe(3);
    });

    it('should filter by tenantId', async () => {
      const results = await store.query({ tenantId: 'tenant-1' });
      expect(results.length).toBe(2);
      expect(results.every(r => r.tenantId === 'tenant-1')).toBe(true);
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
  });

  describe('count', () => {
    it('should count all records', async () => {
      await store.store(makeRecord({ id: '1' }));
      await store.store(makeRecord({ id: '2' }));
      expect(store.count()).toBe(2);
    });
  });

  describe('clear', () => {
    it('should clear all records', async () => {
      await store.store(makeRecord());
      store.clear();
      const results = await store.query({});
      expect(results.length).toBe(0);
    });
  });
});