/**
 * Tests for policy/redaction.ts
 */

import { describe, it, expect } from 'vitest';
import {
  Redactor,
  createRedactor,
  maskEmail,
  maskPhone,
  maskPartial,
  maskCard,
  hashSha256,
  maskValue,
} from '../../src/policy/redaction.js';
import { ModelPolicySchema } from '../../src/policy/models.js';

describe('maskEmail', () => {
  it('should mask email showing first char and domain', () => {
    expect(maskEmail('john@example.com')).toBe('j***@example.com');
  });

  it('should handle single character local part', () => {
    expect(maskEmail('j@example.com')).toBe('j***@example.com');
  });

  it('should handle email without @ as partial mask', () => {
    expect(maskEmail('notanemail')).toBe('n********l');
  });
});

describe('maskPhone', () => {
  it('should mask phone showing first 2 and last 3 chars', () => {
    expect(maskPhone('+1234567890')).toBe('+1******890');
  });

  it('should fully mask short phone numbers', () => {
    expect(maskPhone('12345')).toBe('*****');
  });

  it('should handle longer numbers', () => {
    expect(maskPhone('+14155551234')).toBe('+1*******234');
  });
});

describe('maskPartial', () => {
  it('should show first and last char with asterisks in between', () => {
    expect(maskPartial('password')).toBe('p******d');
  });

  it('should fully mask 2 char strings', () => {
    expect(maskPartial('ab')).toBe('**');
  });

  it('should fully mask single char strings', () => {
    expect(maskPartial('a')).toBe('*');
  });

  it('should handle empty string', () => {
    expect(maskPartial('')).toBe('');
  });
});

describe('maskCard', () => {
  it('should show last 4 digits of card number', () => {
    expect(maskCard('4111111111111111')).toBe('************1111');
  });

  it('should handle short card numbers', () => {
    expect(maskCard('1234')).toBe('****');
  });

  it('should handle very short numbers', () => {
    expect(maskCard('12')).toBe('****');
  });
});

describe('hashSha256', () => {
  it('should return consistent hash for same input', () => {
    const hash1 = hashSha256('test');
    const hash2 = hashSha256('test');

    expect(hash1).toBe(hash2);
    expect(hash1).toHaveLength(64); // SHA256 hex length
  });

  it('should return different hash for different inputs', () => {
    const hash1 = hashSha256('test1');
    const hash2 = hashSha256('test2');

    expect(hash1).not.toBe(hash2);
  });
});

describe('maskValue', () => {
  it('should return null for deny strategy', () => {
    expect(maskValue('secret', 'deny')).toBeNull();
  });

  it('should mask email with mask_email strategy', () => {
    expect(maskValue('test@example.com', 'mask_email')).toBe('t***@example.com');
  });

  it('should mask phone with mask_phone strategy', () => {
    expect(maskValue('+1234567890', 'mask_phone')).toBe('+1******890');
  });

  it('should mask card with mask_card strategy', () => {
    expect(maskValue('4111111111111111', 'mask_card')).toBe('************1111');
  });

  it('should mask partial with mask_partial strategy', () => {
    expect(maskValue('secret', 'mask_partial')).toBe('s****t');
  });

  it('should hash with hash_sha256 strategy', () => {
    const result = maskValue('test', 'hash_sha256');
    expect(typeof result).toBe('string');
    expect((result as string).length).toBe(64);
  });

  it('should return null for null input', () => {
    expect(maskValue(null, 'mask_email')).toBeNull();
  });

  it('should return null for undefined input', () => {
    expect(maskValue(undefined, 'mask_email')).toBeNull();
  });
});

describe('Redactor', () => {
  describe('redactRecord', () => {
    it('should allow fields with allow action', () => {
      const modelPolicy = ModelPolicySchema.parse({
        fields: {
          name: { action: 'allow' },
        },
      });
      const redactor = new Redactor(modelPolicy);

      const record = { name: 'John', id: '123' };
      const result = redactor.redactRecord(record);

      expect(result.name).toBe('John');
      expect(result.id).toBe('123'); // Default is allow
    });

    it('should redact fields with deny action', () => {
      const modelPolicy = ModelPolicySchema.parse({
        fields: {
          password: { action: 'deny' },
        },
      });
      const redactor = new Redactor(modelPolicy);

      const record = { name: 'John', password: 'secret123' };
      const result = redactor.redactRecord(record);

      expect(result.name).toBe('John');
      expect(result.password).toBeNull();
    });

    it('should mask fields with mask action', () => {
      const modelPolicy = ModelPolicySchema.parse({
        fields: {
          email: { action: 'mask' },
        },
      });
      const redactor = new Redactor(modelPolicy);

      const record = { email: 'john@example.com' };
      const result = redactor.redactRecord(record);

      expect(result.email).toBe('j***@example.com');
    });

    it('should hash fields with hash action', () => {
      const modelPolicy = ModelPolicySchema.parse({
        fields: {
          ssn: { action: 'hash' },
        },
      });
      const redactor = new Redactor(modelPolicy);

      const record = { ssn: '123-45-6789' };
      const result = redactor.redactRecord(record);

      expect(typeof result.ssn).toBe('string');
      expect((result.ssn as string).length).toBe(64);
    });

    it('should apply custom mask pattern', () => {
      const modelPolicy = ModelPolicySchema.parse({
        fields: {
          card: { action: 'mask', maskPattern: '****{last4}' },
        },
      });
      const redactor = new Redactor(modelPolicy);

      const record = { card: '4111111111111111' };
      const result = redactor.redactRecord(record);

      expect(result.card).toBe('****1111');
    });

    it('should apply firstN mask pattern', () => {
      const modelPolicy = ModelPolicySchema.parse({
        fields: {
          code: { action: 'mask', maskPattern: '{first2}***' },
        },
      });
      const redactor = new Redactor(modelPolicy);

      const record = { code: 'ABCDEF' };
      const result = redactor.redactRecord(record);

      expect(result.code).toBe('AB***');
    });

    it('should return null for null values', () => {
      const modelPolicy = ModelPolicySchema.parse({
        fields: {
          email: { action: 'mask' },
        },
      });
      const redactor = new Redactor(modelPolicy);

      const record = { email: null };
      const result = redactor.redactRecord(record);

      expect(result.email).toBeNull();
    });
  });

  describe('redactRecords', () => {
    it('should redact multiple records', () => {
      const modelPolicy = ModelPolicySchema.parse({
        fields: {
          password: { action: 'deny' },
        },
      });
      const redactor = new Redactor(modelPolicy);

      const records = [
        { id: '1', password: 'secret1' },
        { id: '2', password: 'secret2' },
      ];
      const result = redactor.redactRecords(records);

      expect(result).toHaveLength(2);
      expect(result[0].password).toBeNull();
      expect(result[1].password).toBeNull();
      expect(result[0].id).toBe('1');
      expect(result[1].id).toBe('2');
    });

    it('should handle empty array', () => {
      const modelPolicy = ModelPolicySchema.parse({});
      const redactor = new Redactor(modelPolicy);

      const result = redactor.redactRecords([]);

      expect(result).toEqual([]);
    });
  });
});

describe('createRedactor', () => {
  it('should create a redactor', () => {
    const modelPolicy = ModelPolicySchema.parse({});

    const redactor = createRedactor(modelPolicy);

    expect(redactor).toBeInstanceOf(Redactor);
  });
});
