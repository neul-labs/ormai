/**
 * In-memory audit store.
 *
 * Useful for testing and development.
 */

import type { AuditRecord } from './models.js';
import type { AuditQueryOptions, AuditStore } from './base.js';

/**
 * In-memory audit store for testing.
 */
export class InMemoryAuditStore implements AuditStore {
  private readonly records: Map<string, AuditRecord> = new Map();

  async store(record: AuditRecord): Promise<void> {
    this.records.set(record.id, record);
  }

  async get(recordId: string): Promise<AuditRecord | undefined> {
    return this.records.get(recordId);
  }

  async query(options: AuditQueryOptions): Promise<AuditRecord[]> {
    const { tenantId, principalId, toolName, startTime, endTime, limit = 100, offset = 0 } = options;

    let results: AuditRecord[] = [];

    for (const record of this.records.values()) {
      // Apply filters
      if (tenantId && record.tenantId !== tenantId) continue;
      if (principalId && record.principalId !== principalId) continue;
      if (toolName && record.toolName !== toolName) continue;
      if (startTime && record.timestamp < startTime) continue;
      if (endTime && record.timestamp > endTime) continue;

      results.push(record);
    }

    // Sort by timestamp descending
    results.sort((a, b) => b.timestamp.getTime() - a.timestamp.getTime());

    // Apply offset and limit
    return results.slice(offset, offset + limit);
  }

  /**
   * Clear all records.
   */
  clear(): void {
    this.records.clear();
  }

  /**
   * Get total record count.
   */
  count(): number {
    return this.records.size;
  }

  /**
   * Get all records (for testing).
   */
  all(): AuditRecord[] {
    return Array.from(this.records.values());
  }
}

/**
 * Create an in-memory audit store.
 */
export function createInMemoryAuditStore(): InMemoryAuditStore {
  return new InMemoryAuditStore();
}
