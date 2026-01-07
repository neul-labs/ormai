/**
 * JSONL file-based audit store.
 *
 * A file-based implementation with support for:
 * - File rotation based on size
 * - Compression of rotated files
 * - Configurable options
 */

import { readFile, appendFile, unlink, mkdir, stat, rename, writeFile } from 'fs/promises';
import { existsSync } from 'fs';
import { dirname } from 'path';
import { createGzip } from 'zlib';
import { pipeline } from 'stream/promises';
import { Readable } from 'stream';
import type { AuditRecord } from './models.js';
import { AuditRecordSchema } from './models.js';
import type { AuditQueryOptions, AuditStore } from './base.js';

/**
 * Options for JsonlAuditStore.
 */
export interface JsonlAuditStoreOptions {
  /** Path to the JSONL file */
  path: string;
  /** Maximum file size in bytes before rotation (default: 10MB) */
  maxFileSizeBytes?: number;
  /** Whether to compress rotated files (default: false) */
  compressOnRotation?: boolean;
}

const DEFAULT_OPTIONS: Required<JsonlAuditStoreOptions> = {
  path: '',
  maxFileSizeBytes: 10 * 1024 * 1024, // 10MB
  compressOnRotation: false,
};

/**
 * Audit store that writes records to a JSONL file.
 *
 * Each line in the file is a JSON-encoded audit record.
 * Supports file rotation and compression.
 */
export class JsonlAuditStore implements AuditStore {
  private readonly path: string;
  private readonly maxFileSizeBytes: number;
  private readonly compressOnRotation: boolean;
  private initialized = false;

  constructor(options: JsonlAuditStoreOptions) {
    const opts = { ...DEFAULT_OPTIONS, ...options };
    this.path = opts.path;
    this.maxFileSizeBytes = opts.maxFileSizeBytes;
    this.compressOnRotation = opts.compressOnRotation;
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

    // Check file size before writing
    await this.checkRotation();

    const data = this.serializeRecord(record);
    const line = JSON.stringify(data) + '\n';
    await appendFile(this.path, line, 'utf8');
  }

  private async checkRotation(): Promise<void> {
    if (!existsSync(this.path)) return;

    const stats = await stat(this.path);
    if (stats.size >= this.maxFileSizeBytes) {
      await this.rotateFile();
    }
  }

  private async rotateFile(): Promise<void> {
    const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
    const rotatedPath = this.path.replace('.jsonl', `_${timestamp}.jsonl`);

    // Rename current file to rotated path
    await rename(this.path, rotatedPath);

    // Create empty file for new writes
    await writeFile(this.path, '', 'utf8');

    // Optionally compress
    if (this.compressOnRotation) {
      await this.compressFile(rotatedPath);
    }
  }

  private async compressFile(filePath: string): Promise<void> {
    const gzipPath = filePath + '.gz';
    const input = await readFile(filePath);
    const gzip = createGzip();

    const { Writable } = await import('stream');
    const output = new Writable({
      write(chunk, encoding, callback) {
        appendFile(gzipPath, chunk).then(() => callback(), callback);
      },
    });

    const inputStream = Readable.from(input);
    await pipeline(inputStream, gzip, output);
    await unlink(filePath);
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
    this.initialized = false;
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
export function createJsonlAuditStore(
  path: string,
  options?: Partial<JsonlAuditStoreOptions>
): JsonlAuditStore {
  return new JsonlAuditStore({ path, ...options });
}
