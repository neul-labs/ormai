/**
 * Tests for core/dsl.ts
 */

import { describe, it, expect } from 'vitest';
import {
  FilterOpSchema,
  FilterClauseSchema,
  OrderDirectionSchema,
  OrderClauseSchema,
  IncludeClauseSchema,
  QueryRequestSchema,
  GetRequestSchema,
  AggregateRequestSchema,
  CreateRequestSchema,
  UpdateRequestSchema,
  DeleteRequestSchema,
  BulkUpdateRequestSchema,
  filter,
  orderBy,
  include,
} from '../../src/core/dsl.js';

describe('FilterOpSchema', () => {
  it('should accept valid filter operators', () => {
    const validOps = [
      'eq', 'ne', 'lt', 'lte', 'gt', 'gte',
      'in', 'not_in', 'is_null',
      'contains', 'startswith', 'endswith', 'between',
    ];

    for (const op of validOps) {
      expect(FilterOpSchema.parse(op)).toBe(op);
    }
  });

  it('should reject invalid filter operators', () => {
    expect(() => FilterOpSchema.parse('invalid')).toThrow();
    expect(() => FilterOpSchema.parse('equals')).toThrow();
  });
});

describe('FilterClauseSchema', () => {
  it('should parse valid filter clause', () => {
    const clause = FilterClauseSchema.parse({
      field: 'name',
      op: 'eq',
      value: 'John',
    });

    expect(clause.field).toBe('name');
    expect(clause.op).toBe('eq');
    expect(clause.value).toBe('John');
  });

  it('should parse filter with array value', () => {
    const clause = FilterClauseSchema.parse({
      field: 'status',
      op: 'in',
      value: ['active', 'pending'],
    });

    expect(clause.value).toEqual(['active', 'pending']);
  });

  it('should parse filter with null value', () => {
    const clause = FilterClauseSchema.parse({
      field: 'deletedAt',
      op: 'is_null',
      value: true,
    });

    expect(clause.value).toBe(true);
  });

  it('should reject filter without field', () => {
    expect(() => FilterClauseSchema.parse({
      op: 'eq',
      value: 'test',
    })).toThrow();
  });

  it('should reject filter without op', () => {
    expect(() => FilterClauseSchema.parse({
      field: 'name',
      value: 'test',
    })).toThrow();
  });
});

describe('OrderClauseSchema', () => {
  it('should parse ascending order', () => {
    const clause = OrderClauseSchema.parse({
      field: 'createdAt',
      direction: 'asc',
    });

    expect(clause.field).toBe('createdAt');
    expect(clause.direction).toBe('asc');
  });

  it('should parse descending order', () => {
    const clause = OrderClauseSchema.parse({
      field: 'createdAt',
      direction: 'desc',
    });

    expect(clause.direction).toBe('desc');
  });

  it('should default to asc direction', () => {
    const clause = OrderClauseSchema.parse({
      field: 'createdAt',
    });

    expect(clause.direction).toBe('asc');
  });
});

describe('IncludeClauseSchema', () => {
  it('should parse simple include', () => {
    const clause = IncludeClauseSchema.parse({
      relation: 'orders',
    });

    expect(clause.relation).toBe('orders');
  });

  it('should parse include with select', () => {
    const clause = IncludeClauseSchema.parse({
      relation: 'orders',
      select: ['id', 'total'],
    });

    expect(clause.select).toEqual(['id', 'total']);
  });

  it('should parse include with where', () => {
    const clause = IncludeClauseSchema.parse({
      relation: 'orders',
      where: [{ field: 'status', op: 'eq', value: 'active' }],
    });

    expect(clause.where).toHaveLength(1);
    expect(clause.where![0].field).toBe('status');
  });

  it('should parse include with take', () => {
    const clause = IncludeClauseSchema.parse({
      relation: 'orders',
      take: 5,
    });

    expect(clause.take).toBe(5);
  });
});

describe('QueryRequestSchema', () => {
  it('should parse minimal query', () => {
    const query = QueryRequestSchema.parse({
      model: 'Customer',
    });

    expect(query.model).toBe('Customer');
    expect(query.take).toBe(25); // default
  });

  it('should parse query with select', () => {
    const query = QueryRequestSchema.parse({
      model: 'Customer',
      select: ['id', 'name', 'email'],
    });

    expect(query.select).toEqual(['id', 'name', 'email']);
  });

  it('should parse query with where', () => {
    const query = QueryRequestSchema.parse({
      model: 'Customer',
      where: [{ field: 'active', op: 'eq', value: true }],
    });

    expect(query.where).toHaveLength(1);
  });

  it('should parse query with orderBy', () => {
    const query = QueryRequestSchema.parse({
      model: 'Customer',
      orderBy: [{ field: 'createdAt', direction: 'desc' }],
    });

    expect(query.orderBy).toHaveLength(1);
  });

  it('should parse query with take', () => {
    const query = QueryRequestSchema.parse({
      model: 'Customer',
      take: 50,
    });

    expect(query.take).toBe(50);
  });

  it('should enforce max take of 100', () => {
    const query = QueryRequestSchema.parse({
      model: 'Customer',
      take: 100,
    });

    expect(query.take).toBe(100);
  });

  it('should reject take over 100', () => {
    expect(() => QueryRequestSchema.parse({
      model: 'Customer',
      take: 101,
    })).toThrow();
  });

  it('should parse query with cursor', () => {
    const query = QueryRequestSchema.parse({
      model: 'Customer',
      cursor: 'abc123',
    });

    expect(query.cursor).toBe('abc123');
  });

  it('should parse query with include', () => {
    const query = QueryRequestSchema.parse({
      model: 'Customer',
      include: [{ relation: 'orders' }],
    });

    expect(query.include).toHaveLength(1);
    expect(query.include![0].relation).toBe('orders');
  });
});

describe('GetRequestSchema', () => {
  it('should parse get request', () => {
    const req = GetRequestSchema.parse({
      model: 'Customer',
      id: '123',
    });

    expect(req.model).toBe('Customer');
    expect(req.id).toBe('123');
  });

  it('should parse get request with numeric id', () => {
    const req = GetRequestSchema.parse({
      model: 'Customer',
      id: 123,
    });

    expect(req.id).toBe(123);
  });

  it('should parse get request with select', () => {
    const req = GetRequestSchema.parse({
      model: 'Customer',
      id: '123',
      select: ['id', 'name'],
    });

    expect(req.select).toEqual(['id', 'name']);
  });

  it('should parse get request with include', () => {
    const req = GetRequestSchema.parse({
      model: 'Customer',
      id: '123',
      include: [{ relation: 'orders' }],
    });

    expect(req.include).toHaveLength(1);
  });
});

describe('AggregateRequestSchema', () => {
  it('should parse count aggregate', () => {
    const req = AggregateRequestSchema.parse({
      model: 'Order',
      operation: 'count',
    });

    expect(req.model).toBe('Order');
    expect(req.operation).toBe('count');
  });

  it('should parse sum aggregate with field', () => {
    const req = AggregateRequestSchema.parse({
      model: 'Order',
      operation: 'sum',
      field: 'total',
    });

    expect(req.operation).toBe('sum');
    expect(req.field).toBe('total');
  });

  it('should parse aggregate with where', () => {
    const req = AggregateRequestSchema.parse({
      model: 'Order',
      operation: 'count',
      where: [{ field: 'status', op: 'eq', value: 'completed' }],
    });

    expect(req.where).toHaveLength(1);
  });

  it('should accept valid operations', () => {
    const ops = ['count', 'sum', 'avg', 'min', 'max'];
    for (const op of ops) {
      const req = AggregateRequestSchema.parse({
        model: 'Order',
        operation: op,
      });
      expect(req.operation).toBe(op);
    }
  });
});

describe('CreateRequestSchema', () => {
  it('should parse create request', () => {
    const req = CreateRequestSchema.parse({
      model: 'Customer',
      data: { name: 'John', email: 'john@example.com' },
    });

    expect(req.model).toBe('Customer');
    expect(req.data).toEqual({ name: 'John', email: 'john@example.com' });
  });

  it('should parse create with reason', () => {
    const req = CreateRequestSchema.parse({
      model: 'Customer',
      data: { name: 'John' },
      reason: 'New customer registration',
    });

    expect(req.reason).toBe('New customer registration');
  });
});

describe('UpdateRequestSchema', () => {
  it('should parse update request', () => {
    const req = UpdateRequestSchema.parse({
      model: 'Customer',
      id: '123',
      data: { name: 'Jane' },
    });

    expect(req.model).toBe('Customer');
    expect(req.id).toBe('123');
    expect(req.data).toEqual({ name: 'Jane' });
  });

  it('should parse update with reason', () => {
    const req = UpdateRequestSchema.parse({
      model: 'Customer',
      id: '123',
      data: { name: 'Jane' },
      reason: 'Customer requested name change',
    });

    expect(req.reason).toBe('Customer requested name change');
  });
});

describe('DeleteRequestSchema', () => {
  it('should parse delete request', () => {
    const req = DeleteRequestSchema.parse({
      model: 'Customer',
      id: '123',
    });

    expect(req.model).toBe('Customer');
    expect(req.id).toBe('123');
    expect(req.hard).toBe(false); // default
  });

  it('should parse hard delete', () => {
    const req = DeleteRequestSchema.parse({
      model: 'Customer',
      id: '123',
      hard: true,
    });

    expect(req.hard).toBe(true);
  });

  it('should parse delete with reason', () => {
    const req = DeleteRequestSchema.parse({
      model: 'Customer',
      id: '123',
      reason: 'Customer requested account deletion',
    });

    expect(req.reason).toBe('Customer requested account deletion');
  });
});

describe('BulkUpdateRequestSchema', () => {
  it('should parse bulk update request', () => {
    const req = BulkUpdateRequestSchema.parse({
      model: 'Order',
      ids: ['1', '2', '3'],
      data: { status: 'shipped' },
    });

    expect(req.model).toBe('Order');
    expect(req.ids).toEqual(['1', '2', '3']);
    expect(req.data).toEqual({ status: 'shipped' });
  });

  it('should require at least one id', () => {
    expect(() => BulkUpdateRequestSchema.parse({
      model: 'Order',
      ids: [],
      data: { status: 'shipped' },
    })).toThrow();
  });
});

describe('Helper functions', () => {
  describe('filter', () => {
    it('should create a filter clause', () => {
      const clause = filter('name', 'eq', 'John');

      expect(clause.field).toBe('name');
      expect(clause.op).toBe('eq');
      expect(clause.value).toBe('John');
    });
  });

  describe('orderBy', () => {
    it('should create an order clause with default asc', () => {
      const clause = orderBy('createdAt');

      expect(clause.field).toBe('createdAt');
      expect(clause.direction).toBe('asc');
    });

    it('should create an order clause with specified direction', () => {
      const clause = orderBy('createdAt', 'desc');

      expect(clause.field).toBe('createdAt');
      expect(clause.direction).toBe('desc');
    });
  });

  describe('include', () => {
    it('should create a simple include clause', () => {
      const clause = include('orders');

      expect(clause.relation).toBe('orders');
    });

    it('should create an include clause with options', () => {
      const clause = include('orders', {
        select: ['id', 'total'],
        take: 5,
      });

      expect(clause.relation).toBe('orders');
      expect(clause.select).toEqual(['id', 'total']);
      expect(clause.take).toBe(5);
    });
  });
});
