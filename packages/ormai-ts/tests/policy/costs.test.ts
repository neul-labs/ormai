/**
 * Tests for policy/costs.ts
 */

import { describe, it, expect } from 'vitest';
import {
  createCostBreakdown,
  getTotalCost,
  costBreakdownToDict,
  QueryCostEstimator,
  CostTracker,
  checkCostBudget,
  TableStatsSchema,
  CostBudgetSchema,
  DEFAULT_COST_WEIGHTS,
  createQueryCostEstimator,
} from '../../src/policy/costs.js';

describe('createCostBreakdown', () => {
  it('should create breakdown with all costs at zero', () => {
    const breakdown = createCostBreakdown();

    expect(breakdown.scanCost).toBe(0);
    expect(breakdown.filterCost).toBe(0);
    expect(breakdown.joinCost).toBe(0);
    expect(breakdown.sortCost).toBe(0);
    expect(breakdown.aggregateCost).toBe(0);
    expect(breakdown.networkCost).toBe(0);
    expect(breakdown.memoryCost).toBe(0);
    expect(breakdown.details).toEqual({});
  });
});

describe('getTotalCost', () => {
  it('should sum all cost components', () => {
    const breakdown = createCostBreakdown();
    breakdown.scanCost = 10;
    breakdown.filterCost = 5;
    breakdown.joinCost = 20;
    breakdown.sortCost = 3;
    breakdown.aggregateCost = 2;
    breakdown.networkCost = 1;
    breakdown.memoryCost = 1;

    expect(getTotalCost(breakdown)).toBe(42);
  });
});

describe('costBreakdownToDict', () => {
  it('should convert breakdown to dictionary', () => {
    const breakdown = createCostBreakdown();
    breakdown.scanCost = 10;
    breakdown.filterCost = 5;
    breakdown.details = { foo: 'bar' };

    const dict = costBreakdownToDict(breakdown);

    expect(dict.scan).toBe(10);
    expect(dict.filter).toBe(5);
    expect(dict.total).toBe(15);
    expect(dict.details).toEqual({ foo: 'bar' });
  });
});

describe('TableStatsSchema', () => {
  it('should parse with defaults', () => {
    const stats = TableStatsSchema.parse({ tableName: 'customers' });

    expect(stats.tableName).toBe('customers');
    expect(stats.estimatedRowCount).toBe(1000);
    expect(stats.avgRowSizeBytes).toBe(100);
    expect(stats.indexedColumns).toEqual([]);
  });

  it('should accept custom values', () => {
    const stats = TableStatsSchema.parse({
      tableName: 'customers',
      estimatedRowCount: 5000,
      indexedColumns: ['email', 'tenantId'],
      primaryKey: 'id',
    });

    expect(stats.estimatedRowCount).toBe(5000);
    expect(stats.indexedColumns).toEqual(['email', 'tenantId']);
    expect(stats.primaryKey).toBe('id');
  });
});

describe('DEFAULT_COST_WEIGHTS', () => {
  it('should have expected values', () => {
    expect(DEFAULT_COST_WEIGHTS.fullScanPerRow).toBe(1.0);
    expect(DEFAULT_COST_WEIGHTS.indexScanPerRow).toBe(0.3);
    expect(DEFAULT_COST_WEIGHTS.equalityFilter).toBe(0.1);
    expect(DEFAULT_COST_WEIGHTS.stringFilter).toBe(0.5);
  });
});

describe('QueryCostEstimator', () => {
  describe('estimate', () => {
    it('should estimate cost for simple query', () => {
      const estimator = new QueryCostEstimator();

      const breakdown = estimator.estimate({
        model: 'Customer',
        take: 25,
      });

      expect(breakdown.scanCost).toBeGreaterThan(0);
      expect(breakdown.details['estimatedBaseRows']).toBe(1000); // default
    });

    it('should use table stats when available', () => {
      const estimator = new QueryCostEstimator({
        Customer: TableStatsSchema.parse({
          tableName: 'customers',
          estimatedRowCount: 10000,
        }),
      });

      const breakdown = estimator.estimate({
        model: 'Customer',
        take: 25,
      });

      expect(breakdown.details['estimatedBaseRows']).toBe(10000);
    });

    it('should reduce scan cost when using indexed column', () => {
      const tableStats = {
        Customer: TableStatsSchema.parse({
          tableName: 'customers',
          estimatedRowCount: 1000,
          indexedColumns: ['email'],
        }),
      };
      const estimator = new QueryCostEstimator(tableStats);

      const indexedBreakdown = estimator.estimate({
        model: 'Customer',
        where: [{ field: 'email', op: 'eq', value: 'test@example.com' }],
        take: 25,
      });

      const nonIndexedBreakdown = estimator.estimate({
        model: 'Customer',
        where: [{ field: 'name', op: 'eq', value: 'John' }],
        take: 25,
      });

      expect(indexedBreakdown.scanCost).toBeLessThan(nonIndexedBreakdown.scanCost);
    });

    it('should add filter costs', () => {
      const estimator = new QueryCostEstimator();

      const withFilter = estimator.estimate({
        model: 'Customer',
        where: [{ field: 'status', op: 'eq', value: 'active' }],
        take: 25,
      });

      const withoutFilter = estimator.estimate({
        model: 'Customer',
        take: 25,
      });

      expect(withFilter.filterCost).toBeGreaterThan(withoutFilter.filterCost);
    });

    it('should add higher cost for string filters', () => {
      const estimator = new QueryCostEstimator();

      const stringFilter = estimator.estimate({
        model: 'Customer',
        where: [{ field: 'name', op: 'contains', value: 'john' }],
        take: 25,
      });

      const equalityFilter = estimator.estimate({
        model: 'Customer',
        where: [{ field: 'status', op: 'eq', value: 'active' }],
        take: 25,
      });

      expect(stringFilter.filterCost).toBeGreaterThan(equalityFilter.filterCost);
    });

    it('should add join cost for includes', () => {
      const estimator = new QueryCostEstimator();

      const withInclude = estimator.estimate({
        model: 'Customer',
        include: [{ relation: 'orders' }],
        take: 25,
      });

      const withoutInclude = estimator.estimate({
        model: 'Customer',
        take: 25,
      });

      expect(withInclude.joinCost).toBeGreaterThan(withoutInclude.joinCost);
    });

    it('should add sort cost for order by', () => {
      const estimator = new QueryCostEstimator();

      const withSort = estimator.estimate({
        model: 'Customer',
        orderBy: [{ field: 'createdAt', direction: 'desc' }],
        take: 25,
      });

      const withoutSort = estimator.estimate({
        model: 'Customer',
        take: 25,
      });

      expect(withSort.sortCost).toBeGreaterThan(withoutSort.sortCost);
    });
  });

  describe('estimateAggregate', () => {
    it('should estimate aggregate cost', () => {
      const estimator = new QueryCostEstimator();

      const breakdown = estimator.estimateAggregate('Customer', 'count');

      expect(breakdown.scanCost).toBeGreaterThan(0);
      expect(breakdown.aggregateCost).toBeGreaterThan(0);
      expect(breakdown.details['operation']).toBe('count');
    });

    it('should add cost for group by', () => {
      const estimator = new QueryCostEstimator();

      const withGroupBy = estimator.estimateAggregate(
        'Order',
        'count',
        undefined,
        undefined,
        ['status', 'customerId']
      );

      const withoutGroupBy = estimator.estimateAggregate('Order', 'count');

      expect(withGroupBy.aggregateCost).toBeGreaterThan(withoutGroupBy.aggregateCost);
    });
  });
});

describe('CostBudgetSchema', () => {
  it('should parse with defaults', () => {
    const budget = CostBudgetSchema.parse({});

    expect(budget.maxTotalCost).toBe(1000);
  });

  it('should accept custom limits', () => {
    const budget = CostBudgetSchema.parse({
      maxTotalCost: 500,
      maxScanCost: 100,
      maxJoinCost: 50,
    });

    expect(budget.maxTotalCost).toBe(500);
    expect(budget.maxScanCost).toBe(100);
    expect(budget.maxJoinCost).toBe(50);
  });
});

describe('checkCostBudget', () => {
  it('should return empty array when within budget', () => {
    const budget = CostBudgetSchema.parse({ maxTotalCost: 1000 });
    const breakdown = createCostBreakdown();
    breakdown.scanCost = 100;

    const exceeded = checkCostBudget(budget, breakdown);

    expect(exceeded).toEqual([]);
  });

  it('should return exceeded limits when total exceeds budget', () => {
    const budget = CostBudgetSchema.parse({ maxTotalCost: 100 });
    const breakdown = createCostBreakdown();
    breakdown.scanCost = 150;

    const exceeded = checkCostBudget(budget, breakdown);

    expect(exceeded).toHaveLength(1);
    expect(exceeded[0]).toContain('total_cost');
  });

  it('should check individual cost limits', () => {
    const budget = CostBudgetSchema.parse({
      maxTotalCost: 1000,
      maxScanCost: 50,
    });
    const breakdown = createCostBreakdown();
    breakdown.scanCost = 100;

    const exceeded = checkCostBudget(budget, breakdown);

    expect(exceeded).toHaveLength(1);
    expect(exceeded[0]).toContain('scan_cost');
  });

  it('should report multiple exceeded limits', () => {
    const budget = CostBudgetSchema.parse({
      maxTotalCost: 50,
      maxScanCost: 10,
      maxJoinCost: 5,
    });
    const breakdown = createCostBreakdown();
    breakdown.scanCost = 30;
    breakdown.joinCost = 30;

    const exceeded = checkCostBudget(budget, breakdown);

    expect(exceeded.length).toBeGreaterThan(1);
  });
});

describe('CostTracker', () => {
  describe('record', () => {
    it('should record query execution', () => {
      const tracker = new CostTracker();
      const breakdown = createCostBreakdown();
      breakdown.scanCost = 100;
      breakdown.details['estimatedFilteredRows'] = 50;

      tracker.record('Customer', breakdown, 150, 45);

      const stats = tracker.getAccuracyStats();
      expect(stats.count).toBe(1);
    });
  });

  describe('getAccuracyStats', () => {
    it('should return empty stats for no records', () => {
      const tracker = new CostTracker();

      const stats = tracker.getAccuracyStats();

      expect(stats.count).toBe(0);
    });

    it('should calculate stats for multiple records', () => {
      const tracker = new CostTracker();

      const breakdown1 = createCostBreakdown();
      breakdown1.scanCost = 100;
      breakdown1.details['estimatedFilteredRows'] = 50;

      const breakdown2 = createCostBreakdown();
      breakdown2.scanCost = 200;
      breakdown2.details['estimatedFilteredRows'] = 100;

      tracker.record('Customer', breakdown1, 150, 45);
      tracker.record('Order', breakdown2, 250, 95);

      const stats = tracker.getAccuracyStats();

      expect(stats.count).toBe(2);
      expect(stats.avgDurationMs).toBe(200);
      expect(stats.minDurationMs).toBe(150);
      expect(stats.maxDurationMs).toBe(250);
    });
  });

  describe('clear', () => {
    it('should clear recorded data', () => {
      const tracker = new CostTracker();
      const breakdown = createCostBreakdown();
      breakdown.scanCost = 100;

      tracker.record('Customer', breakdown, 150, 45);
      expect(tracker.getAccuracyStats().count).toBe(1);

      tracker.clear();
      expect(tracker.getAccuracyStats().count).toBe(0);
    });
  });
});

describe('createQueryCostEstimator', () => {
  it('should create estimator with default weights', () => {
    const estimator = createQueryCostEstimator();

    expect(estimator).toBeInstanceOf(QueryCostEstimator);
  });

  it('should create estimator with table stats', () => {
    const estimator = createQueryCostEstimator({
      Customer: TableStatsSchema.parse({
        tableName: 'customers',
        estimatedRowCount: 5000,
      }),
    });

    const breakdown = estimator.estimate({
      model: 'Customer',
      take: 25,
    });

    expect(breakdown.details['estimatedBaseRows']).toBe(5000);
  });
});
