/**
 * Tests for core/errors.ts
 */

import { describe, it, expect } from 'vitest';
import {
  OrmAIError,
  ModelNotAllowedError,
  FieldNotAllowedError,
  RelationNotAllowedError,
  TenantScopeRequiredError,
  QueryBudgetExceededError,
  QueryTooBroadError,
  WriteDisabledError,
  ValidationError,
  AdapterError,
  isOrmAIError,
  wrapError,
  ErrorCodes,
} from '../../src/core/errors.js';

describe('OrmAIError', () => {
  it('should create error with code and message', () => {
    const error = new OrmAIError(ErrorCodes.INTERNAL_ERROR, 'Something went wrong');

    expect(error.message).toBe('Something went wrong');
    expect(error.code).toBe('INTERNAL_ERROR');
    expect(error.name).toBe('OrmAIError');
  });

  it('should create error with retry hints', () => {
    const error = new OrmAIError(ErrorCodes.INTERNAL_ERROR, 'Something went wrong', {
      retryHints: ['Try again with different params'],
    });

    expect(error.retryHints).toEqual(['Try again with different params']);
  });

  it('should create error with details', () => {
    const error = new OrmAIError(ErrorCodes.INTERNAL_ERROR, 'Something went wrong', {
      details: { field: 'name' },
    });

    expect(error.details).toEqual({ field: 'name' });
  });

  it('should serialize to JSON', () => {
    const error = new OrmAIError(ErrorCodes.INTERNAL_ERROR, 'Something went wrong', {
      retryHints: ['Try again'],
      details: { field: 'name' },
    });

    const json = error.toJSON();

    expect(json.code).toBe('INTERNAL_ERROR');
    expect(json.message).toBe('Something went wrong');
    expect(json.retryHints).toEqual(['Try again']);
    expect(json.details).toEqual({ field: 'name' });
  });

  it('should be instance of Error', () => {
    const error = new OrmAIError(ErrorCodes.INTERNAL_ERROR, 'Test');

    expect(error).toBeInstanceOf(Error);
    expect(error).toBeInstanceOf(OrmAIError);
  });

  it('should freeze retry hints and details', () => {
    const error = new OrmAIError(ErrorCodes.INTERNAL_ERROR, 'Test', {
      retryHints: ['Try again'],
      details: { foo: 'bar' },
    });

    expect(Object.isFrozen(error.retryHints)).toBe(true);
    expect(Object.isFrozen(error.details)).toBe(true);
  });
});

describe('ModelNotAllowedError', () => {
  it('should create with model and allowed models', () => {
    const error = new ModelNotAllowedError('Secret', ['Customer', 'Order']);

    expect(error.message).toContain('Secret');
    expect(error.code).toBe('MODEL_NOT_ALLOWED');
    expect(error.details.model).toBe('Secret');
    expect(error.details.allowedModels).toEqual(['Customer', 'Order']);
  });

  it('should include allowed models in retry hints', () => {
    const error = new ModelNotAllowedError('Secret', ['Customer', 'Order']);

    expect(error.retryHints.length).toBeGreaterThan(0);
    expect(error.retryHints.some(h => h.includes('Customer'))).toBe(true);
  });
});

describe('FieldNotAllowedError', () => {
  it('should create with field, model, and allowed fields', () => {
    // Note: constructor signature is (field, model, allowedFields)
    const error = new FieldNotAllowedError('password', 'Customer', ['id', 'name', 'email']);

    expect(error.message).toContain('password');
    expect(error.message).toContain('Customer');
    expect(error.code).toBe('FIELD_NOT_ALLOWED');
    expect(error.details.model).toBe('Customer');
    expect(error.details.field).toBe('password');
    expect(error.details.allowedFields).toEqual(['id', 'name', 'email']);
  });

  it('should include allowed fields in retry hints', () => {
    const error = new FieldNotAllowedError('password', 'Customer', ['id', 'name']);

    expect(error.retryHints.length).toBeGreaterThan(0);
  });
});

describe('RelationNotAllowedError', () => {
  it('should create with relation, model, and allowed relations', () => {
    // Note: constructor signature is (relation, model, allowedRelations)
    const error = new RelationNotAllowedError('secrets', 'Customer', ['orders', 'profile']);

    expect(error.message).toContain('secrets');
    expect(error.message).toContain('Customer');
    expect(error.code).toBe('RELATION_NOT_ALLOWED');
    expect(error.details.model).toBe('Customer');
    expect(error.details.relation).toBe('secrets');
    expect(error.details.allowedRelations).toEqual(['orders', 'profile']);
  });
});

describe('TenantScopeRequiredError', () => {
  it('should create with model and scope field', () => {
    const error = new TenantScopeRequiredError('Customer', 'tenantId');

    expect(error.message).toContain('Customer');
    expect(error.code).toBe('TENANT_SCOPE_REQUIRED');
    expect(error.details.model).toBe('Customer');
    expect(error.details.scopeField).toBe('tenantId');
  });

  it('should include retry hints', () => {
    const error = new TenantScopeRequiredError('Customer', 'tenantId');

    expect(error.retryHints.length).toBeGreaterThan(0);
  });
});

describe('QueryBudgetExceededError', () => {
  it('should create with budget type, limit, and requested', () => {
    const error = new QueryBudgetExceededError('rows', 100, 150);

    expect(error.message).toContain('100');
    expect(error.message).toContain('150');
    expect(error.code).toBe('QUERY_BUDGET_EXCEEDED');
    expect(error.details.budgetType).toBe('rows');
    expect(error.details.limit).toBe(100);
    expect(error.details.requested).toBe(150);
  });

  it('should include retry hints for rows', () => {
    const error = new QueryBudgetExceededError('rows', 100, 150);

    expect(error.retryHints.some(h => h.includes('100') || h.includes('take'))).toBe(true);
  });

  it('should include retry hints for complexity', () => {
    const error = new QueryBudgetExceededError('complexity', 50, 75);

    expect(error.retryHints.length).toBeGreaterThan(0);
  });
});

describe('QueryTooBroadError', () => {
  it('should create with model', () => {
    const error = new QueryTooBroadError('Customer');

    expect(error.message).toContain('Customer');
    expect(error.code).toBe('QUERY_TOO_BROAD');
    expect(error.details.model).toBe('Customer');
  });

  it('should include retry hints', () => {
    const error = new QueryTooBroadError('Customer');

    expect(error.retryHints.length).toBeGreaterThan(0);
  });

  it('should accept optional suggestion', () => {
    const error = new QueryTooBroadError('Customer', 'Try filtering by id');

    expect(error.retryHints.some(h => h.includes('id'))).toBe(true);
  });
});

describe('WriteDisabledError', () => {
  it('should create with operation and model', () => {
    // Note: constructor signature is (operation, model)
    const error = new WriteDisabledError('create', 'Customer');

    expect(error.message).toContain('Customer');
    expect(error.message).toContain('create');
    expect(error.code).toBe('WRITE_DISABLED');
    expect(error.details.model).toBe('Customer');
    expect(error.details.operation).toBe('create');
  });
});

describe('ValidationError', () => {
  it('should create with message', () => {
    const error = new ValidationError('Invalid input');

    expect(error.message).toBe('Invalid input');
    expect(error.code).toBe('VALIDATION_ERROR');
  });

  it('should create with field', () => {
    const error = new ValidationError('Name is required', 'name');

    expect(error.details.field).toBe('name');
  });

  it('should create with additional details', () => {
    const error = new ValidationError('Invalid input', undefined, { constraint: 'minLength' });

    expect(error.details.constraint).toBe('minLength');
  });
});

describe('AdapterError', () => {
  it('should create with message', () => {
    const error = new AdapterError('Database connection failed');

    expect(error.message).toBe('Database connection failed');
    expect(error.code).toBe('ADAPTER_ERROR');
  });

  it('should wrap original error', () => {
    const originalError = new Error('Connection timeout');
    const error = new AdapterError('Database connection failed', originalError);

    expect(error.cause).toBe(originalError);
    expect(error.details.originalError).toBe('Connection timeout');
  });
});

describe('isOrmAIError', () => {
  it('should return true for OrmAIError', () => {
    const error = new OrmAIError(ErrorCodes.INTERNAL_ERROR, 'Test');

    expect(isOrmAIError(error)).toBe(true);
  });

  it('should return true for OrmAIError subclasses', () => {
    expect(isOrmAIError(new ModelNotAllowedError('Test', []))).toBe(true);
    expect(isOrmAIError(new FieldNotAllowedError('f', 'M', []))).toBe(true);
    expect(isOrmAIError(new TenantScopeRequiredError('M', 'tenantId'))).toBe(true);
    expect(isOrmAIError(new QueryBudgetExceededError('rows', 100, 150))).toBe(true);
    expect(isOrmAIError(new WriteDisabledError('create', 'M'))).toBe(true);
    expect(isOrmAIError(new ValidationError('Test'))).toBe(true);
    expect(isOrmAIError(new AdapterError('Test'))).toBe(true);
  });

  it('should return false for regular Error', () => {
    const error = new Error('Test');

    expect(isOrmAIError(error)).toBe(false);
  });

  it('should return false for non-errors', () => {
    expect(isOrmAIError(null)).toBe(false);
    expect(isOrmAIError(undefined)).toBe(false);
    expect(isOrmAIError('error')).toBe(false);
    expect(isOrmAIError({})).toBe(false);
  });
});

describe('wrapError', () => {
  it('should return OrmAIError unchanged', () => {
    const error = new OrmAIError(ErrorCodes.INTERNAL_ERROR, 'Test');

    expect(wrapError(error)).toBe(error);
  });

  it('should wrap regular Error', () => {
    const error = new Error('Test');
    const wrapped = wrapError(error);

    expect(wrapped).toBeInstanceOf(OrmAIError);
    expect(wrapped.message).toBe('Test');
    expect(wrapped.code).toBe('INTERNAL_ERROR');
  });

  it('should wrap string', () => {
    const wrapped = wrapError('Something went wrong');

    expect(wrapped).toBeInstanceOf(OrmAIError);
    expect(wrapped.message).toBe('Something went wrong');
  });
});
