/**
 * JSONL file-based audit store.
 *
 * A simple file-based implementation for development and testing.
 */

import { readFile, appendFile, unlink, mkdir } from 'fs/promises';
import { existsSync } from 'fs';
import { dirname } from 'path';
import type { AuditRecord } from './models.js';
import { AuditRecordSchema } from './models.js';
import type { AuditQueryOptions, AuditStore } from './base.js';

/**
 * Audit store that writes records to a JSONL file.
 *
 * Each line in the file is a JSON-encoded audit record.
 * This is suitable for development and small-scale deployments.
 */
export class JsonlAuditStore implements AuditStore {
  private readonly path: string;
  private initialized = false;

  constructor(path: string) {
    this.path = path;
  }

  private async ensureDirectory(): Promise<void> {
    if (this.initialized) return;
    const dir = dirname(this.path);
    if (dir && !existsSync(dir)) {
      await mkdir(dir, { recursive: true });
    }
    this.initialized = true;
  }

  async store(record: AuditRecord): Promise<void> {
    await this.ensureDirectory();
    const data = this.serializeRecord(record);
    const line = JSON.stringify(data) + '\n';
    await appendFile(this.path, line, 'utf8');
  }

  async get(recordId: string): Promise<AuditRecord | undefined> {
    if (!existsSync(this.path)) {
      return undefined;
    }

    const content = await readFile(this.path, 'utf8');
    const lines = content.split('\n').filter((l) => l.trim());

    for (const line of lines) {
      const data = JSON.parse(line);
      if (data.id === recordId) {
        return this.deserializeRecord(data);
      }
    }

    return undefined;
  }

  async query(options: AuditQueryOptions): Promise<AuditRecord[]> {
    if (!existsSync(this.path)) {
      return [];
    }

    const { tenantId, principalId, toolName, startTime, endTime, limit = 100, offset = 0 } = options;

    const content = await readFile(this.path, 'utf8');
    const lines = content.split('\n').filter((l) => l.trim());

    const results: AuditRecord[] = [];
    let skipped = 0;

    for (const line of lines) {
      const data = JSON.parse(line);

      // Apply filters
      if (tenantId && data.tenantId !== tenantId) continue;
      if (principalId && data.principalId !== principalId) continue;
      if (toolName && data.toolName !== toolName) continue;

      const recordTime = new Date(data.timestamp);
      if (startTime && recordTime < startTime) continue;
      if (endTime && recordTime > endTime) continue;

      // Handle offset
      if (skipped < offset) {
        skipped++;
        continue;
      }

      results.push(this.deserializeRecord(data));

      if (results.length >= limit) {
        break;
      }
    }

    return results;
  }

  /**
   * Clear all records (for testing).
   */
  async clear(): Promise<void> {
    if (existsSync(this.path)) {
      await unlink(this.path);
    }
  }

  private serializeRecord(record: AuditRecord): Record<string, unknown> {
    return {
      ...record,
      timestamp: record.timestamp.toISOString(),
    };
  }

  private deserializeRecord(data: Record<string, unknown>): AuditRecord {
    if (typeof data.timestamp === 'string') {
      data.timestamp = new Date(data.timestamp);
    }
    return AuditRecordSchema.parse(data);
  }
}

/**
 * Create a JSONL audit store.
 */
export function createJsonlAuditStore(path: string): JsonlAuditStore {
  return new JsonlAuditStore(path);
}
