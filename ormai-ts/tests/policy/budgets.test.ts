/**
 * Tests for policy/budgets.ts
 */

import { describe, it, expect } from 'vitest';
import {
  ComplexityScorer,
  BudgetEnforcer,
  createComplexityScorer,
  createBudgetEnforcer,
  DEFAULT_COMPLEXITY_WEIGHTS,
} from '../../src/policy/budgets.js';
import { BudgetSchema } from '../../src/policy/models.js';
import { QueryBudgetExceededError } from '../../src/core/errors.js';

describe('DEFAULT_COMPLEXITY_WEIGHTS', () => {
  it('should have expected default values', () => {
    expect(DEFAULT_COMPLEXITY_WEIGHTS.base).toBe(1);
    expect(DEFAULT_COMPLEXITY_WEIGHTS.perField).toBe(1);
    expect(DEFAULT_COMPLEXITY_WEIGHTS.perFilter).toBe(2);
    expect(DEFAULT_COMPLEXITY_WEIGHTS.perInclude).toBe(10);
    expect(DEFAULT_COMPLEXITY_WEIGHTS.stringFilter).toBe(3);
  });
});

describe('ComplexityScorer', () => {
  describe('score', () => {
    it('should return base score for minimal query', () => {
      const scorer = new ComplexityScorer();

      const score = scorer.score({
        model: 'Customer',
        take: 25,
      });

      expect(score).toBe(DEFAULT_COMPLEXITY_WEIGHTS.base);
    });

    it('should add score for selected fields', () => {
      const scorer = new ComplexityScorer();

      const score = scorer.score({
        model: 'Customer',
        select: ['id', 'name', 'email'],
        take: 25,
      });

      expect(score).toBe(
        DEFAULT_COMPLEXITY_WEIGHTS.base + 3 * DEFAULT_COMPLEXITY_WEIGHTS.perField
      );
    });

    it('should add score for filters', () => {
      const scorer = new ComplexityScorer();

      const score = scorer.score({
        model: 'Customer',
        where: [
          { field: 'status', op: 'eq', value: 'active' },
        ],
        take: 25,
      });

      expect(score).toBe(
        DEFAULT_COMPLEXITY_WEIGHTS.base + DEFAULT_COMPLEXITY_WEIGHTS.perFilter
      );
    });

    it('should add extra score for string filters', () => {
      const scorer = new ComplexityScorer();

      const score = scorer.score({
        model: 'Customer',
        where: [
          { field: 'name', op: 'contains', value: 'john' },
        ],
        take: 25,
      });

      expect(score).toBe(
        DEFAULT_COMPLEXITY_WEIGHTS.base +
        DEFAULT_COMPLEXITY_WEIGHTS.perFilter +
        DEFAULT_COMPLEXITY_WEIGHTS.stringFilter
      );
    });

    it('should add score for IN filters based on array length', () => {
      const scorer = new ComplexityScorer();

      const score = scorer.score({
        model: 'Customer',
        where: [
          { field: 'status', op: 'in', value: ['a', 'b', 'c'] },
        ],
        take: 25,
      });

      expect(score).toBe(
        DEFAULT_COMPLEXITY_WEIGHTS.base +
        DEFAULT_COMPLEXITY_WEIGHTS.perFilter +
        3 * DEFAULT_COMPLEXITY_WEIGHTS.inFilter
      );
    });

    it('should add score for includes', () => {
      const scorer = new ComplexityScorer();

      const score = scorer.score({
        model: 'Customer',
        include: [{ relation: 'orders' }],
        take: 25,
      });

      expect(score).toBe(
        DEFAULT_COMPLEXITY_WEIGHTS.base + DEFAULT_COMPLEXITY_WEIGHTS.perInclude
      );
    });

    it('should add score for order by', () => {
      const scorer = new ComplexityScorer();

      const score = scorer.score({
        model: 'Customer',
        orderBy: [
          { field: 'createdAt', direction: 'desc' },
          { field: 'name', direction: 'asc' },
        ],
        take: 25,
      });

      expect(score).toBe(
        DEFAULT_COMPLEXITY_WEIGHTS.base + 2 * DEFAULT_COMPLEXITY_WEIGHTS.perOrder
      );
    });

    it('should accumulate all complexity factors', () => {
      const scorer = new ComplexityScorer();

      const score = scorer.score({
        model: 'Customer',
        select: ['id', 'name'],
        where: [{ field: 'status', op: 'eq', value: 'active' }],
        orderBy: [{ field: 'createdAt', direction: 'desc' }],
        include: [{ relation: 'orders', select: ['id'] }],
        take: 25,
      });

      // base + 2 fields + 1 filter + 1 order + include (base + 1 field)
      const expected =
        DEFAULT_COMPLEXITY_WEIGHTS.base +
        2 * DEFAULT_COMPLEXITY_WEIGHTS.perField +
        DEFAULT_COMPLEXITY_WEIGHTS.perFilter +
        DEFAULT_COMPLEXITY_WEIGHTS.perOrder +
        DEFAULT_COMPLEXITY_WEIGHTS.perInclude +
        1 * DEFAULT_COMPLEXITY_WEIGHTS.perField; // include select

      expect(score).toBe(expected);
    });
  });

  it('should accept custom weights', () => {
    const scorer = new ComplexityScorer({ base: 10, perField: 5 });

    const score = scorer.score({
      model: 'Customer',
      select: ['id', 'name'],
      take: 25,
    });

    expect(score).toBe(10 + 2 * 5);
  });
});

describe('BudgetEnforcer', () => {
  describe('enforce', () => {
    it('should pass for query within budget', () => {
      const budget = BudgetSchema.parse({ maxRows: 100 });
      const enforcer = new BudgetEnforcer(budget);

      expect(() => enforcer.enforce({
        model: 'Customer',
        take: 50,
      })).not.toThrow();
    });

    it('should throw for row limit exceeded', () => {
      const budget = BudgetSchema.parse({ maxRows: 50 });
      const enforcer = new BudgetEnforcer(budget);

      expect(() => enforcer.enforce({
        model: 'Customer',
        take: 100,
      })).toThrow(QueryBudgetExceededError);
    });

    it('should throw for field limit exceeded', () => {
      const budget = BudgetSchema.parse({ maxSelectFields: 5 });
      const enforcer = new BudgetEnforcer(budget);

      expect(() => enforcer.enforce({
        model: 'Customer',
        select: ['a', 'b', 'c', 'd', 'e', 'f', 'g'],
        take: 25,
      })).toThrow(QueryBudgetExceededError);
    });

    it('should throw for include depth exceeded', () => {
      const budget = BudgetSchema.parse({ maxIncludesDepth: 1 });
      const enforcer = new BudgetEnforcer(budget);

      expect(() => enforcer.enforce({
        model: 'Customer',
        include: [
          { relation: 'orders' },
          { relation: 'profile' },
        ],
        take: 25,
      })).toThrow(QueryBudgetExceededError);
    });

    it('should throw for complexity exceeded', () => {
      const budget = BudgetSchema.parse({ maxComplexityScore: 5 });
      const enforcer = new BudgetEnforcer(budget);

      expect(() => enforcer.enforce({
        model: 'Customer',
        select: ['a', 'b', 'c', 'd', 'e', 'f', 'g'],
        where: [
          { field: 'a', op: 'eq', value: 1 },
          { field: 'b', op: 'eq', value: 2 },
        ],
        include: [{ relation: 'orders' }],
        take: 25,
      })).toThrow(QueryBudgetExceededError);
    });
  });

  describe('getEffectiveLimit', () => {
    it('should return budget max when no limit requested', () => {
      const budget = BudgetSchema.parse({ maxRows: 100 });
      const enforcer = new BudgetEnforcer(budget);

      expect(enforcer.getEffectiveLimit()).toBe(100);
    });

    it('should return requested limit when below budget', () => {
      const budget = BudgetSchema.parse({ maxRows: 100 });
      const enforcer = new BudgetEnforcer(budget);

      expect(enforcer.getEffectiveLimit(50)).toBe(50);
    });

    it('should return budget limit when requested exceeds budget', () => {
      const budget = BudgetSchema.parse({ maxRows: 100 });
      const enforcer = new BudgetEnforcer(budget);

      expect(enforcer.getEffectiveLimit(150)).toBe(100);
    });
  });
});

describe('createComplexityScorer', () => {
  it('should create a scorer with default weights', () => {
    const scorer = createComplexityScorer();

    expect(scorer).toBeInstanceOf(ComplexityScorer);
  });

  it('should create a scorer with custom weights', () => {
    const scorer = createComplexityScorer({ base: 5 });

    const score = scorer.score({ model: 'Test', take: 25 });
    expect(score).toBe(5);
  });
});

describe('createBudgetEnforcer', () => {
  it('should create an enforcer', () => {
    const budget = BudgetSchema.parse({});
    const enforcer = createBudgetEnforcer(budget);

    expect(enforcer).toBeInstanceOf(BudgetEnforcer);
  });

  it('should create an enforcer with custom scorer', () => {
    const budget = BudgetSchema.parse({ maxComplexityScore: 3 });
    const scorer = createComplexityScorer({ base: 5 });
    const enforcer = createBudgetEnforcer(budget, scorer);

    // Base score is 5, which exceeds limit of 3
    expect(() => enforcer.enforce({
      model: 'Test',
      take: 25,
    })).toThrow(QueryBudgetExceededError);
  });
});
