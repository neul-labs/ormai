/**
 * Abstract audit store interface.
 */

import type { AuditRecord } from './models.js';

/**
 * Query options for audit records.
 */
export interface AuditQueryOptions {
  tenantId?: string;
  principalId?: string;
  toolName?: string;
  startTime?: Date;
  endTime?: Date;
  limit?: number;
  offset?: number;
}

/**
 * Abstract interface for audit log storage.
 *
 * Implementations can store audit records in various backends:
 * - SQL databases
 * - Document stores
 * - File systems
 * - Cloud services
 */
export interface AuditStore {
  /**
   * Store an audit record.
   *
   * This should be called after every tool execution.
   */
  store(record: AuditRecord): Promise<void>;

  /**
   * Retrieve an audit record by ID.
   */
  get(recordId: string): Promise<AuditRecord | undefined>;

  /**
   * Query audit records with filters.
   */
  query(options: AuditQueryOptions): Promise<AuditRecord[]>;
}

/**
 * Base class for audit store implementations.
 */
export abstract class BaseAuditStore implements AuditStore {
  abstract store(record: AuditRecord): Promise<void>;
  abstract get(recordId: string): Promise<AuditRecord | undefined>;
  abstract query(options: AuditQueryOptions): Promise<AuditRecord[]>;
}
