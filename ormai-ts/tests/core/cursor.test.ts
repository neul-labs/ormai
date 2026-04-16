/**
 * Tests for CursorEncoder and keyset pagination.
 */

import { describe, it, expect } from 'vitest';
import { CursorEncoder, buildKeysetCondition } from '@ormai/core';

describe('CursorEncoder', () => {
  describe('offset cursors', () => {
    it('should encode and decode offset cursors', () => {
      const encoder = new CursorEncoder('test-secret');
      const cursor = encoder.encodeOffset(42);
      const offset = encoder.decodeOffset(cursor);
      expect(offset).toBe(42);
    });

    it('should encode offset 0', () => {
      const encoder = new CursorEncoder('test-secret');
      const cursor = encoder.encodeOffset(0);
      const offset = encoder.decodeOffset(cursor);
      expect(offset).toBe(0);
    });

    it('should throw for keyset cursor when decoding offset', () => {
      const encoder = new CursorEncoder('test-secret');
      const cursor = encoder.encodeKeyset({ id: 1 }, ['id']);
      expect(() => encoder.decodeOffset(cursor)).toThrow('Expected offset cursor');
    });
  });

  describe('keyset cursors', () => {
    it('should encode and decode keyset cursors', () => {
      const encoder = new CursorEncoder('test-secret');
      const cursor = encoder.encodeKeyset({ id: 123, name: 'test' }, ['id', 'name']);
      const [values, direction] = encoder.decodeKeyset(cursor);
      expect(values.id).toBe(123);
      expect(values.name).toBe('test');
      expect(direction).toBe('forward');
    });

    it('should support backward direction', () => {
      const encoder = new CursorEncoder('test-secret');
      const cursor = encoder.encodeKeyset({ id: 5 }, ['id'], 'backward');
      const [values, direction] = encoder.decodeKeyset(cursor);
      expect(values.id).toBe(5);
      expect(direction).toBe('backward');
    });

    it('should throw for offset cursor when decoding keyset', () => {
      const encoder = new CursorEncoder('test-secret');
      const cursor = encoder.encodeOffset(10);
      expect(() => encoder.decodeKeyset(cursor)).toThrow('Expected keyset cursor');
    });

    it('should handle Date values in keyset', () => {
      const encoder = new CursorEncoder('test-secret');
      const date = new Date('2024-01-15T12:00:00Z');
      const cursor = encoder.encodeKeyset({ created_at: date }, ['created_at']);
      const [values] = encoder.decodeKeyset(cursor);
      expect(values.created_at).toBeInstanceOf(Date);
      expect((values.created_at as Date).toISOString()).toBe(date.toISOString());
    });

    it('should only include specified order fields', () => {
      const encoder = new CursorEncoder('test-secret');
      const cursor = encoder.encodeKeyset(
        { id: 1, name: 'test', extra: 'field' },
        ['id']
      );
      const [values] = encoder.decodeKeyset(cursor);
      expect(values.id).toBe(1);
      expect(values.name).toBeUndefined();
      expect(values.extra).toBeUndefined();
    });
  });

  describe('checksum verification', () => {
    it('should verify checksum with matching secret', () => {
      const encoder = new CursorEncoder('my-secret');
      const cursor = encoder.encodeOffset(100);
      const data = encoder.decode(cursor);
      expect(data.cursorType).toBe('offset');
      expect(data.values.offset).toBe(100);
    });

    it('should fail checksum verification with wrong secret', () => {
      const encoder1 = new CursorEncoder('secret-1');
      const encoder2 = new CursorEncoder('secret-2');
      const cursor = encoder1.encodeOffset(50);
      expect(() => encoder2.decode(cursor)).toThrow();
    });

    it('should work without secret', () => {
      const encoder = new CursorEncoder();
      const cursor = encoder.encodeOffset(25);
      const offset = encoder.decodeOffset(cursor);
      expect(offset).toBe(25);
    });
  });

  describe('error handling', () => {
    it('should throw for invalid cursor format', () => {
      const encoder = new CursorEncoder('secret');
      expect(() => encoder.decode('not-a-valid-cursor!!!')).toThrow('Invalid cursor');
    });

    it('should throw for empty string', () => {
      const encoder = new CursorEncoder('secret');
      expect(() => encoder.decode('')).toThrow('Invalid cursor');
    });
  });
});

describe('buildKeysetCondition', () => {
  it('should return empty object for empty order fields', () => {
    const result = buildKeysetCondition({}, []);
    expect(result).toEqual({});
  });

  it('should build single field condition (ASC forward)', () => {
    const result = buildKeysetCondition({ id: 5 }, [{ field: 'id', direction: 'asc' }]);
    expect(result).toEqual({ field: 'id', op: 'gt', value: 5 });
  });

  it('should build single field condition (DESC forward)', () => {
    const result = buildKeysetCondition({ id: 5 }, [{ field: 'id', direction: 'desc' }]);
    expect(result).toEqual({ field: 'id', op: 'lt', value: 5 });
  });

  it('should build single field condition (ASC backward)', () => {
    const result = buildKeysetCondition(
      { id: 5 },
      [{ field: 'id', direction: 'asc' }],
      'backward'
    );
    expect(result).toEqual({ field: 'id', op: 'lt', value: 5 });
  });

  it('should build multi-field condition', () => {
    const result = buildKeysetCondition(
      { id: 5, created_at: '2024-01-01' },
      [
        { field: 'id', direction: 'asc' },
        { field: 'created_at', direction: 'desc' },
      ]
    );
    expect(result).toEqual({
      or: [
        { field: 'id', op: 'gt', value: 5 },
        {
          and: [
            { field: 'id', op: 'eq', value: 5 },
            { field: 'created_at', op: 'lt', value: '2024-01-01' },
          ],
        },
      ],
    });
  });
});