/**
 * Budget enforcement and complexity scoring.
 *
 * Budgets prevent runaway queries by limiting rows, includes, fields,
 * and query complexity.
 */

import type { FilterClause, IncludeClause, QueryRequest } from '../core/dsl.js';
import { QueryBudgetExceededError } from '../core/errors.js';
import type { Budget } from './models.js';

/**
 * Default weights for complexity factors.
 */
export const DEFAULT_COMPLEXITY_WEIGHTS = {
  base: 1,
  perField: 1,
  perFilter: 2,
  perInclude: 10,
  perOrder: 1,
  stringFilter: 3, // contains, startswith, endswith
  inFilter: 2, // per item in IN clause
  betweenFilter: 2,
} as const;

export type ComplexityWeights = typeof DEFAULT_COMPLEXITY_WEIGHTS;

/**
 * Scores query complexity based on various factors.
 *
 * Higher scores indicate more complex (and potentially expensive) queries.
 */
export class ComplexityScorer {
  private readonly weights: ComplexityWeights;

  constructor(weights?: Partial<ComplexityWeights>) {
    this.weights = { ...DEFAULT_COMPLEXITY_WEIGHTS, ...weights };
  }

  /**
   * Calculate complexity score for a query request.
   *
   * Returns an integer score where higher = more complex.
   */
  score(request: QueryRequest): number {
    let score = this.weights.base;

    // Field selection
    if (request.select) {
      score += request.select.length * this.weights.perField;
    }

    // Filters
    if (request.where) {
      for (const f of request.where) {
        score += this.scoreFilter(f);
      }
    }

    // Includes
    if (request.include) {
      for (const inc of request.include) {
        score += this.scoreInclude(inc);
      }
    }

    // Ordering
    if (request.orderBy) {
      score += request.orderBy.length * this.weights.perOrder;
    }

    return score;
  }

  /**
   * Score a single filter clause.
   */
  private scoreFilter(filterClause: FilterClause): number {
    let score = this.weights.perFilter;

    // String operations are more expensive
    if (['contains', 'startswith', 'endswith'].includes(filterClause.op)) {
      score += this.weights.stringFilter;
    }

    // IN clauses scale with list size
    if (filterClause.op === 'in' && Array.isArray(filterClause.value)) {
      score += filterClause.value.length * this.weights.inFilter;
    }

    // BETWEEN is slightly more expensive
    if (filterClause.op === 'between') {
      score += this.weights.betweenFilter;
    }

    return score;
  }

  /**
   * Score a single include clause.
   */
  private scoreInclude(include: IncludeClause): number {
    let score = this.weights.perInclude;

    // Fields in the include
    if (include.select) {
      score += include.select.length * this.weights.perField;
    }

    // Filters in the include
    if (include.where) {
      for (const f of include.where) {
        score += this.scoreFilter(f);
      }
    }

    return score;
  }
}

/**
 * Enforces budget limits on queries.
 *
 * Checks various limits and raises appropriate errors when exceeded.
 */
export class BudgetEnforcer {
  private readonly scorer: ComplexityScorer;

  constructor(
    private readonly budget: Budget,
    scorer?: ComplexityScorer
  ) {
    this.scorer = scorer ?? new ComplexityScorer();
  }

  /**
   * Enforce all budget limits on a query request.
   *
   * Throws QueryBudgetExceededError if any limit is exceeded.
   */
  enforce(request: QueryRequest): void {
    this.checkRowLimit(request);
    this.checkFieldLimit(request);
    this.checkIncludeLimit(request);
    this.checkComplexity(request);
  }

  /**
   * Check if requested rows exceed limit.
   */
  private checkRowLimit(request: QueryRequest): void {
    if (request.take > this.budget.maxRows) {
      throw new QueryBudgetExceededError('rows', this.budget.maxRows, request.take);
    }
  }

  /**
   * Check if selected fields exceed limit.
   */
  private checkFieldLimit(request: QueryRequest): void {
    if (request.select && request.select.length > this.budget.maxSelectFields) {
      throw new QueryBudgetExceededError(
        'fields',
        this.budget.maxSelectFields,
        request.select.length
      );
    }
  }

  /**
   * Check if includes exceed depth limit.
   */
  private checkIncludeLimit(request: QueryRequest): void {
    if (request.include && request.include.length > this.budget.maxIncludesDepth) {
      throw new QueryBudgetExceededError(
        'includes',
        this.budget.maxIncludesDepth,
        request.include.length
      );
    }
  }

  /**
   * Check if query complexity exceeds limit.
   */
  private checkComplexity(request: QueryRequest): void {
    const score = this.scorer.score(request);
    if (score > this.budget.maxComplexityScore) {
      throw new QueryBudgetExceededError('complexity', this.budget.maxComplexityScore, score);
    }
  }

  /**
   * Get the effective row limit considering budget.
   *
   * Returns the minimum of requested limit and budget limit.
   */
  getEffectiveLimit(requested?: number): number {
    if (requested === undefined) {
      return this.budget.maxRows;
    }
    return Math.min(requested, this.budget.maxRows);
  }
}

/**
 * Create a complexity scorer with optional custom weights.
 */
export function createComplexityScorer(weights?: Partial<ComplexityWeights>): ComplexityScorer {
  return new ComplexityScorer(weights);
}

/**
 * Create a budget enforcer for a budget.
 */
export function createBudgetEnforcer(budget: Budget, scorer?: ComplexityScorer): BudgetEnforcer {
  return new BudgetEnforcer(budget, scorer);
}
