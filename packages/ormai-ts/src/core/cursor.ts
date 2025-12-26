/**
 * Cursor-based pagination with stability guarantees.
 *
 * Provides keyset-based cursors that remain stable under concurrent writes,
 * unlike offset-based pagination which can skip or duplicate rows.
 */

import { createHash } from 'crypto';

/**
 * Type of cursor implementation.
 */
export type CursorType = 'offset' | 'keyset';

/**
 * Decoded cursor data.
 *
 * Contains the information needed to resume pagination.
 */
export interface CursorData {
  /** Cursor type (offset or keyset) */
  cursorType: CursorType;

  /** Key field values for keyset, or offset for offset pagination */
  values: Record<string, unknown>;

  /** Pagination direction */
  direction: 'forward' | 'backward';

  /** Checksum for validation */
  checksum?: string;
}

/**
 * Serialized cursor data format.
 */
interface SerializedCursor {
  t: string;
  v: Record<string, unknown>;
  d: string;
  c?: string;
}

/**
 * Serialize CursorData to wire format.
 */
function cursorToDict(cursor: CursorData): SerializedCursor {
  return {
    t: cursor.cursorType,
    v: cursor.values,
    d: cursor.direction,
    c: cursor.checksum,
  };
}

/**
 * Deserialize CursorData from wire format.
 */
function cursorFromDict(data: SerializedCursor): CursorData {
  return {
    cursorType: data.t as CursorType,
    values: data.v,
    direction: (data.d as 'forward' | 'backward') ?? 'forward',
    checksum: data.c,
  };
}

/**
 * Serialize a value for JSON encoding.
 */
function serializeValue(value: unknown): unknown {
  if (value instanceof Date) {
    return { _dt: value.toISOString() };
  }
  return value;
}

/**
 * Deserialize a value from JSON.
 */
function deserializeValue(value: unknown): unknown {
  if (typeof value === 'object' && value !== null && '_dt' in value) {
    return new Date((value as { _dt: string })._dt);
  }
  return value;
}

/**
 * Encodes and decodes pagination cursors.
 *
 * Cursors are opaque strings that encode:
 * - For offset pagination: the current offset
 * - For keyset pagination: the key field values of the last row
 *
 * Keyset pagination provides stability guarantees:
 * - No rows are skipped when new rows are inserted
 * - No rows are duplicated when rows are deleted
 * - Consistent results during concurrent writes
 */
export class CursorEncoder {
  private readonly secret: string;

  /**
   * Initialize the encoder.
   *
   * @param secret - Optional secret for cursor signing (prevents tampering)
   */
  constructor(secret?: string) {
    this.secret = secret ?? 'ormai-cursor-default';
  }

  /**
   * Encode an offset-based cursor.
   *
   * Simple and fast, but not stable under concurrent writes.
   */
  encodeOffset(offset: number): string {
    const data: CursorData = {
      cursorType: 'offset',
      values: { offset },
      direction: 'forward',
    };
    return this.encode(data);
  }

  /**
   * Decode an offset cursor and return the offset.
   */
  decodeOffset(cursor: string): number {
    const data = this.decode(cursor);
    if (data.cursorType !== 'offset') {
      throw new Error('Expected offset cursor');
    }
    return (data.values.offset as number) ?? 0;
  }

  /**
   * Encode a keyset-based cursor.
   *
   * @param keyValues - Values of the key fields from the last row
   * @param orderFields - List of fields used for ordering
   * @param direction - Pagination direction (forward or backward)
   * @returns Encoded cursor string
   */
  encodeKeyset(
    keyValues: Record<string, unknown>,
    orderFields: string[],
    direction: 'forward' | 'backward' = 'forward'
  ): string {
    // Only include the order fields
    const values: Record<string, unknown> = {};
    for (const key of orderFields) {
      if (key in keyValues) {
        values[key] = serializeValue(keyValues[key]);
      }
    }

    const data: CursorData = {
      cursorType: 'keyset',
      values,
      direction,
    };
    return this.encode(data);
  }

  /**
   * Decode a keyset cursor.
   *
   * @returns Tuple of [keyValues, direction]
   */
  decodeKeyset(cursor: string): [Record<string, unknown>, 'forward' | 'backward'] {
    const data = this.decode(cursor);
    if (data.cursorType !== 'keyset') {
      throw new Error('Expected keyset cursor');
    }

    // Deserialize values
    const values: Record<string, unknown> = {};
    for (const [key, val] of Object.entries(data.values)) {
      values[key] = deserializeValue(val);
    }
    return [values, data.direction];
  }

  /**
   * Decode any cursor type.
   */
  decode(cursor: string): CursorData {
    try {
      const jsonStr = Buffer.from(cursor, 'base64url').toString('utf8');
      const rawData = JSON.parse(jsonStr) as SerializedCursor;
      const data = cursorFromDict(rawData);

      // Verify checksum if present
      if (this.secret && data.checksum) {
        const expected = this.computeChecksum(data.values);
        if (data.checksum !== expected) {
          throw new Error('Cursor checksum mismatch');
        }
      }

      return data;
    } catch (e) {
      throw new Error(`Invalid cursor: ${e instanceof Error ? e.message : String(e)}`);
    }
  }

  /**
   * Encode cursor data to string.
   */
  private encode(data: CursorData): string {
    // Add checksum if secret is set
    if (this.secret) {
      data.checksum = this.computeChecksum(data.values);
    }

    const jsonStr = JSON.stringify(cursorToDict(data));
    return Buffer.from(jsonStr, 'utf8').toString('base64url');
  }

  /**
   * Compute checksum for cursor values.
   */
  private computeChecksum(values: Record<string, unknown>): string {
    const content = JSON.stringify(values, Object.keys(values).sort()) + this.secret;
    return createHash('sha256').update(content).digest('hex').slice(0, 16);
  }
}

/**
 * Order field specification for keyset pagination.
 */
export interface OrderField {
  field: string;
  direction: 'asc' | 'desc';
}

/**
 * Filter condition structure.
 */
export interface FilterCondition {
  field?: string;
  op?: string;
  value?: unknown;
  and?: FilterCondition[];
  or?: FilterCondition[];
}

/**
 * Build a filter condition for keyset pagination.
 *
 * For keyset pagination with ORDER BY (a ASC, b DESC), the cursor
 * condition for the next page is:
 *     (a > cursor_a) OR (a = cursor_a AND b < cursor_b)
 *
 * This ensures stable pagination even under concurrent writes.
 *
 * @param cursorValues - Key field values from cursor
 * @param orderFields - List of { field, direction } objects
 * @param direction - forward or backward
 * @returns Filter condition for the query DSL
 */
export function buildKeysetCondition(
  cursorValues: Record<string, unknown>,
  orderFields: OrderField[],
  direction: 'forward' | 'backward' = 'forward'
): FilterCondition {
  if (orderFields.length === 0) {
    return {};
  }

  // Build OR conditions
  const conditions: FilterCondition[] = [];

  for (let i = 0; i < orderFields.length; i++) {
    const andParts: FilterCondition[] = [];

    // Equality conditions for fields before current
    for (let j = 0; j < i; j++) {
      const { field } = orderFields[j];
      if (field in cursorValues) {
        andParts.push({
          field,
          op: 'eq',
          value: cursorValues[field],
        });
      }
    }

    // Comparison condition for current field
    const { field, direction: sortDir } = orderFields[i];
    if (field in cursorValues) {
      // Determine operator based on sort direction and pagination direction
      let op: string;
      if (direction === 'forward') {
        op = sortDir === 'asc' ? 'gt' : 'lt';
      } else {
        op = sortDir === 'asc' ? 'lt' : 'gt';
      }

      andParts.push({
        field,
        op,
        value: cursorValues[field],
      });
    }

    if (andParts.length > 0) {
      if (andParts.length === 1) {
        conditions.push(andParts[0]);
      } else {
        conditions.push({ and: andParts });
      }
    }
  }

  if (conditions.length === 0) {
    return {};
  }
  if (conditions.length === 1) {
    return conditions[0];
  }
  return { or: conditions };
}

/**
 * Default encoder instance.
 */
export const defaultEncoder = new CursorEncoder();
