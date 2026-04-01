/**
 * Field redaction logic.
 *
 * The Redactor applies field-level transformations to query results based on
 * field policies. This includes masking, hashing, and denying field access.
 */

import { createHash } from 'crypto';
import type { FieldPolicy, ModelPolicy } from './models.js';
import { ModelPolicyUtils } from './models.js';

/**
 * Built-in redaction strategies.
 */
export type RedactionStrategy =
  | 'deny'
  | 'mask_email'
  | 'mask_phone'
  | 'mask_card'
  | 'mask_partial'
  | 'hash_sha256';

/**
 * Applies redaction rules to query results.
 *
 * Redaction is applied after query execution to ensure sensitive data
 * never leaves the server in readable form.
 */
export class Redactor {
  constructor(private readonly modelPolicy: ModelPolicy) {}

  /**
   * Apply redaction rules to a single record.
   *
   * Returns a new object with redacted values.
   */
  redactRecord(record: Record<string, unknown>): Record<string, unknown> {
    const result: Record<string, unknown> = {};

    for (const [field, value] of Object.entries(record)) {
      const fieldPolicy = ModelPolicyUtils.getFieldPolicy(this.modelPolicy, field);
      result[field] = this.redactValue(value, fieldPolicy);
    }

    return result;
  }

  /**
   * Apply redaction to a list of records.
   */
  redactRecords(records: Record<string, unknown>[]): Record<string, unknown>[] {
    return records.map((record) => this.redactRecord(record));
  }

  /**
   * Apply redaction to a single value based on policy.
   */
  private redactValue(value: unknown, policy: FieldPolicy): unknown {
    if (value === null || value === undefined) {
      return null;
    }

    switch (policy.action) {
      case 'allow':
        return value;
      case 'deny':
        return null;
      case 'mask':
        return this.applyMask(value, policy.maskPattern);
      case 'hash':
        return this.applyHash(value);
      default:
        return value;
    }
  }

  /**
   * Apply masking to a value.
   */
  private applyMask(value: unknown, pattern: string | undefined): string {
    const strValue = String(value);

    if (pattern) {
      return this.applyCustomMask(strValue, pattern);
    }

    // Default masking based on value format
    if (strValue.includes('@')) {
      return maskEmail(strValue);
    }
    const digitsOnly = strValue.replace(/[+\-\s]/g, '');
    if (/^\d+$/.test(digitsOnly)) {
      if (strValue.length > 10) {
        return maskPhone(strValue);
      }
      return maskPartial(strValue);
    }
    return maskPartial(strValue);
  }

  /**
   * Apply a custom mask pattern.
   */
  private applyCustomMask(value: string, pattern: string): string {
    let result = pattern;

    // Replace {lastN} patterns
    const lastMatch = /\{last(\d+)\}/.exec(pattern);
    if (lastMatch) {
      const n = parseInt(lastMatch[1], 10);
      const lastN = value.length >= n ? value.slice(-n) : value;
      result = result.replace(lastMatch[0], lastN);
    }

    // Replace {firstN} patterns
    const firstMatch = /\{first(\d+)\}/.exec(pattern);
    if (firstMatch) {
      const n = parseInt(firstMatch[1], 10);
      const firstN = value.length >= n ? value.slice(0, n) : value;
      result = result.replace(firstMatch[0], firstN);
    }

    return result;
  }

  /**
   * Hash a value using SHA256.
   */
  private applyHash(value: unknown): string {
    const strValue = String(value);
    return createHash('sha256').update(strValue).digest('hex');
  }
}

/**
 * Mask an email address: user@domain.com -> u***@domain.com
 */
export function maskEmail(email: string): string {
  if (!email.includes('@')) {
    return maskPartial(email);
  }
  const [local, domain] = email.split('@');
  if (local.length <= 1) {
    return `${local}***@${domain}`;
  }
  return `${local[0]}***@${domain}`;
}

/**
 * Mask a phone number: +1234567890 -> +1******890
 */
export function maskPhone(phone: string): string {
  if (phone.length <= 5) {
    return '*'.repeat(phone.length);
  }
  return phone.slice(0, 2) + '*'.repeat(phone.length - 5) + phone.slice(-3);
}

/**
 * Generic partial masking: show first and last char.
 */
export function maskPartial(value: string): string {
  if (value.length <= 2) {
    return '*'.repeat(value.length);
  }
  return value[0] + '*'.repeat(value.length - 2) + value[value.length - 1];
}

/**
 * Mask a credit card number: 1234567890123456 -> ****3456
 */
export function maskCard(card: string): string {
  if (card.length <= 4) {
    return '****';
  }
  return '*'.repeat(card.length - 4) + card.slice(-4);
}

/**
 * Hash a value using SHA256.
 */
export function hashSha256(value: string): string {
  return createHash('sha256').update(value).digest('hex');
}

/**
 * Utility function to mask a value using a built-in strategy.
 *
 * This can be used for custom redaction outside of the main flow.
 */
export function maskValue(value: unknown, strategy: RedactionStrategy): unknown {
  if (value === null || value === undefined) {
    return null;
  }

  const strValue = String(value);

  switch (strategy) {
    case 'deny':
      return null;
    case 'mask_email':
      return maskEmail(strValue);
    case 'mask_phone':
      return maskPhone(strValue);
    case 'mask_card':
      return maskCard(strValue);
    case 'mask_partial':
      return maskPartial(strValue);
    case 'hash_sha256':
      return hashSha256(strValue);
    default:
      return value;
  }
}

/**
 * Create a redactor for a model policy.
 */
export function createRedactor(modelPolicy: ModelPolicy): Redactor {
  return new Redactor(modelPolicy);
}
