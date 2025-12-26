/**
 * Rich query cost estimation model.
 *
 * Provides detailed cost breakdowns for query planning and optimization.
 */

import { z } from 'zod';
import type { FilterClause, QueryRequest } from '../core/dsl.js';

/**
 * Categories of query cost.
 */
export type CostCategory =
  | 'scan'
  | 'filter'
  | 'join'
  | 'sort'
  | 'aggregate'
  | 'network'
  | 'memory';

/**
 * Detailed cost breakdown by category.
 */
export interface CostBreakdown {
  scanCost: number;
  filterCost: number;
  joinCost: number;
  sortCost: number;
  aggregateCost: number;
  networkCost: number;
  memoryCost: number;
  details: Record<string, unknown>;
}

/**
 * Create a new cost breakdown with default values.
 */
export function createCostBreakdown(): CostBreakdown {
  return {
    scanCost: 0,
    filterCost: 0,
    joinCost: 0,
    sortCost: 0,
    aggregateCost: 0,
    networkCost: 0,
    memoryCost: 0,
    details: {},
  };
}

/**
 * Calculate total cost from a breakdown.
 */
export function getTotalCost(breakdown: CostBreakdown): number {
  return (
    breakdown.scanCost +
    breakdown.filterCost +
    breakdown.joinCost +
    breakdown.sortCost +
    breakdown.aggregateCost +
    breakdown.networkCost +
    breakdown.memoryCost
  );
}

/**
 * Convert cost breakdown to a plain object.
 */
export function costBreakdownToDict(breakdown: CostBreakdown): Record<string, unknown> {
  return {
    scan: breakdown.scanCost,
    filter: breakdown.filterCost,
    join: breakdown.joinCost,
    sort: breakdown.sortCost,
    aggregate: breakdown.aggregateCost,
    network: breakdown.networkCost,
    memory: breakdown.memoryCost,
    total: getTotalCost(breakdown),
    details: breakdown.details,
  };
}

/**
 * Statistics about a table for cost estimation.
 */
export const TableStatsSchema = z
  .object({
    tableName: z.string(),
    estimatedRowCount: z.number().int().default(1000),
    avgRowSizeBytes: z.number().int().default(100),
    indexedColumns: z.array(z.string()).default([]),
    primaryKey: z.string().optional(),
    defaultSelectivity: z.number().default(0.1),
    uniqueSelectivity: z.number().default(0.001),
  })
  .readonly();

export type TableStats = z.infer<typeof TableStatsSchema>;

/**
 * Default cost weights for operations.
 */
export const DEFAULT_COST_WEIGHTS = {
  // Scan costs
  fullScanPerRow: 1.0,
  indexScanPerRow: 0.3,
  pkLookup: 0.1,
  // Filter costs
  equalityFilter: 0.1,
  rangeFilter: 0.2,
  stringFilter: 0.5,
  inFilterPerItem: 0.05,
  complexFilter: 0.3,
  // Join costs
  nestedLoopPerRow: 2.0,
  hashJoinPerRow: 0.5,
  includeBase: 5.0,
  includePerRow: 0.2,
  // Sort costs
  sortPerRow: 0.1,
  sortPerColumn: 1.0,
  inMemorySortThreshold: 1000,
  diskSortMultiplier: 3.0,
  // Aggregate costs
  aggregatePerRow: 0.05,
  distinctPerRow: 0.2,
  groupByPerRow: 0.15,
  // Network costs
  networkPerRow: 0.01,
  networkPerColumn: 0.001,
  // Memory costs
  memoryPerRow: 0.001,
  memoryPerColumn: 0.0001,
} as const;

export type CostWeights = typeof DEFAULT_COST_WEIGHTS;

/**
 * Estimates query execution cost based on table statistics and query structure.
 *
 * Cost units are abstract but proportional to expected resource usage.
 */
export class QueryCostEstimator {
  private readonly tableStats: Record<string, TableStats>;
  private readonly costs: CostWeights;

  constructor(
    tableStats?: Record<string, TableStats>,
    costWeights?: Partial<CostWeights>
  ) {
    this.tableStats = tableStats ?? {};
    this.costs = { ...DEFAULT_COST_WEIGHTS, ...costWeights };
  }

  /**
   * Estimate the cost of executing a query.
   *
   * Returns a detailed cost breakdown.
   */
  estimate(request: QueryRequest): CostBreakdown {
    const breakdown = createCostBreakdown();
    let stats = this.tableStats[request.model];

    if (!stats) {
      stats = TableStatsSchema.parse({ tableName: request.model });
    }

    // Estimate number of rows after filtering
    const estimatedRows = this.estimateFilteredRows(request, stats);

    // Scan cost
    breakdown.scanCost = this.estimateScanCost(request, stats);
    breakdown.details['estimatedBaseRows'] = stats.estimatedRowCount;

    // Filter cost
    breakdown.filterCost = this.estimateFilterCost(request, stats);
    breakdown.details['estimatedFilteredRows'] = estimatedRows;

    // Join/include cost
    breakdown.joinCost = this.estimateJoinCost(request, estimatedRows);

    // Sort cost
    breakdown.sortCost = this.estimateSortCost(request, estimatedRows);

    // Network cost
    breakdown.networkCost = this.estimateNetworkCost(request, estimatedRows);

    // Memory cost
    breakdown.memoryCost = this.estimateMemoryCost(request, estimatedRows);

    return breakdown;
  }

  /**
   * Estimate cost of an aggregate query.
   */
  estimateAggregate(
    model: string,
    operation: string,
    field?: string,
    filters?: FilterClause[],
    groupBy?: string[]
  ): CostBreakdown {
    const breakdown = createCostBreakdown();
    const stats = this.tableStats[model] ?? TableStatsSchema.parse({ tableName: model });

    // Scan cost for the base data
    breakdown.scanCost = stats.estimatedRowCount * this.costs.fullScanPerRow;

    // Filter cost if filters provided
    if (filters) {
      for (const f of filters) {
        breakdown.filterCost += this.filterClauseCost(f);
      }
    }

    // Aggregate cost
    breakdown.aggregateCost = stats.estimatedRowCount * this.costs.aggregatePerRow;

    // Group by adds significant cost
    if (groupBy) {
      breakdown.aggregateCost +=
        stats.estimatedRowCount * groupBy.length * this.costs.groupByPerRow;
    }

    breakdown.details['operation'] = operation;
    breakdown.details['field'] = field;
    breakdown.details['groupBy'] = groupBy;

    return breakdown;
  }

  private estimateFilteredRows(request: QueryRequest, stats: TableStats): number {
    let rows = stats.estimatedRowCount;

    if (!request.where) {
      return Math.min(rows, request.take);
    }

    let selectivity = 1.0;
    for (const filterClause of request.where) {
      selectivity *= this.filterSelectivity(filterClause, stats);
    }

    const filteredRows = Math.floor(rows * selectivity);
    return Math.min(filteredRows, request.take);
  }

  private filterSelectivity(filterClause: FilterClause, stats: TableStats): number {
    // Check if filtering on indexed/unique column
    if (stats.indexedColumns.includes(filterClause.field)) {
      if (filterClause.op === 'eq') {
        return stats.uniqueSelectivity;
      }
      return stats.defaultSelectivity * 0.5;
    }

    if (filterClause.field === stats.primaryKey) {
      if (filterClause.op === 'eq') {
        return 1.0 / Math.max(stats.estimatedRowCount, 1);
      }
    }

    const selectivityMap: Record<string, number> = {
      eq: 0.1,
      ne: 0.9,
      lt: 0.3,
      lte: 0.35,
      gt: 0.3,
      gte: 0.35,
      in: Array.isArray(filterClause.value)
        ? Math.min(0.1 * filterClause.value.length, 0.5)
        : 0.1,
      not_in: 0.9,
      contains: 0.1,
      startswith: 0.05,
      endswith: 0.1,
      is_null: 0.05,
    };

    return selectivityMap[filterClause.op] ?? stats.defaultSelectivity;
  }

  private estimateScanCost(request: QueryRequest, stats: TableStats): number {
    let canUseIndex = false;
    if (request.where) {
      for (const f of request.where) {
        if (stats.indexedColumns.includes(f.field) || f.field === stats.primaryKey) {
          canUseIndex = true;
          break;
        }
      }
    }

    if (canUseIndex) {
      return stats.estimatedRowCount * this.costs.indexScanPerRow;
    }
    return stats.estimatedRowCount * this.costs.fullScanPerRow;
  }

  private estimateFilterCost(request: QueryRequest, stats: TableStats): number {
    if (!request.where) {
      return 0;
    }

    let cost = 0;
    for (const f of request.where) {
      cost += this.filterClauseCost(f);
    }

    return cost * stats.estimatedRowCount;
  }

  private filterClauseCost(filterClause: FilterClause): number {
    const op = filterClause.op;

    if (op === 'eq' || op === 'ne') {
      return this.costs.equalityFilter;
    }
    if (['lt', 'lte', 'gt', 'gte', 'between'].includes(op)) {
      return this.costs.rangeFilter;
    }
    if (['contains', 'startswith', 'endswith'].includes(op)) {
      return this.costs.stringFilter;
    }
    if (op === 'in') {
      const items = Array.isArray(filterClause.value) ? filterClause.value.length : 1;
      return this.costs.inFilterPerItem * items;
    }

    return this.costs.complexFilter;
  }

  private estimateJoinCost(request: QueryRequest, estimatedRows: number): number {
    if (!request.include) {
      return 0;
    }

    let cost = 0;
    for (const include of request.include) {
      cost += this.costs.includeBase;
      cost += estimatedRows * this.costs.includePerRow;
      if (include.select) {
        cost += include.select.length * 0.1;
      }
    }

    return cost;
  }

  private estimateSortCost(request: QueryRequest, estimatedRows: number): number {
    if (!request.orderBy) {
      return 0;
    }

    let baseSortCost = estimatedRows * this.costs.sortPerRow;
    const columnCost = request.orderBy.length * this.costs.sortPerColumn;

    if (estimatedRows > this.costs.inMemorySortThreshold) {
      baseSortCost *= this.costs.diskSortMultiplier;
    }

    return baseSortCost + columnCost;
  }

  private estimateNetworkCost(request: QueryRequest, estimatedRows: number): number {
    const rowsReturned = Math.min(estimatedRows, request.take);
    const columns = request.select?.length ?? 10;

    return (
      rowsReturned * this.costs.networkPerRow +
      rowsReturned * columns * this.costs.networkPerColumn
    );
  }

  private estimateMemoryCost(request: QueryRequest, estimatedRows: number): number {
    const rowsReturned = Math.min(estimatedRows, request.take);
    const columns = request.select?.length ?? 10;

    return (
      rowsReturned * this.costs.memoryPerRow +
      rowsReturned * columns * this.costs.memoryPerColumn
    );
  }
}

/**
 * Budget defined in terms of estimated cost.
 */
export const CostBudgetSchema = z
  .object({
    maxTotalCost: z.number().default(1000),
    maxScanCost: z.number().optional(),
    maxFilterCost: z.number().optional(),
    maxJoinCost: z.number().optional(),
    maxSortCost: z.number().optional(),
    maxAggregateCost: z.number().optional(),
    maxNetworkCost: z.number().optional(),
    maxMemoryCost: z.number().optional(),
  })
  .readonly();

export type CostBudget = z.infer<typeof CostBudgetSchema>;

/**
 * Check if a cost breakdown exceeds budget limits.
 *
 * Returns list of exceeded limits (empty if within budget).
 */
export function checkCostBudget(budget: CostBudget, breakdown: CostBreakdown): string[] {
  const exceeded: string[] = [];
  const total = getTotalCost(breakdown);

  if (total > budget.maxTotalCost) {
    exceeded.push(`total_cost: ${total.toFixed(1)} > ${budget.maxTotalCost.toFixed(1)}`);
  }

  if (budget.maxScanCost !== undefined && breakdown.scanCost > budget.maxScanCost) {
    exceeded.push(
      `scan_cost: ${breakdown.scanCost.toFixed(1)} > ${budget.maxScanCost.toFixed(1)}`
    );
  }

  if (budget.maxFilterCost !== undefined && breakdown.filterCost > budget.maxFilterCost) {
    exceeded.push(
      `filter_cost: ${breakdown.filterCost.toFixed(1)} > ${budget.maxFilterCost.toFixed(1)}`
    );
  }

  if (budget.maxJoinCost !== undefined && breakdown.joinCost > budget.maxJoinCost) {
    exceeded.push(
      `join_cost: ${breakdown.joinCost.toFixed(1)} > ${budget.maxJoinCost.toFixed(1)}`
    );
  }

  if (budget.maxSortCost !== undefined && breakdown.sortCost > budget.maxSortCost) {
    exceeded.push(
      `sort_cost: ${breakdown.sortCost.toFixed(1)} > ${budget.maxSortCost.toFixed(1)}`
    );
  }

  if (budget.maxAggregateCost !== undefined && breakdown.aggregateCost > budget.maxAggregateCost) {
    exceeded.push(
      `aggregate_cost: ${breakdown.aggregateCost.toFixed(1)} > ${budget.maxAggregateCost.toFixed(1)}`
    );
  }

  if (budget.maxNetworkCost !== undefined && breakdown.networkCost > budget.maxNetworkCost) {
    exceeded.push(
      `network_cost: ${breakdown.networkCost.toFixed(1)} > ${budget.maxNetworkCost.toFixed(1)}`
    );
  }

  if (budget.maxMemoryCost !== undefined && breakdown.memoryCost > budget.maxMemoryCost) {
    exceeded.push(
      `memory_cost: ${breakdown.memoryCost.toFixed(1)} > ${budget.maxMemoryCost.toFixed(1)}`
    );
  }

  return exceeded;
}

/**
 * Tracks actual vs estimated costs for calibration and monitoring.
 */
export class CostTracker {
  private records: Array<{
    model: string;
    estimatedCost: number;
    estimatedRows: number;
    actualDurationMs: number;
    actualRows: number;
    costBreakdown: Record<string, unknown>;
  }> = [];

  /**
   * Record an actual query execution for comparison.
   */
  record(
    model: string,
    estimated: CostBreakdown,
    actualDurationMs: number,
    actualRows: number
  ): void {
    this.records.push({
      model,
      estimatedCost: getTotalCost(estimated),
      estimatedRows: (estimated.details['estimatedFilteredRows'] as number) ?? 0,
      actualDurationMs,
      actualRows,
      costBreakdown: costBreakdownToDict(estimated),
    });
  }

  /**
   * Calculate accuracy statistics for cost estimates.
   */
  getAccuracyStats(): Record<string, unknown> {
    if (this.records.length === 0) {
      return { count: 0 };
    }

    const estimatedCosts = this.records.map((r) => r.estimatedCost);
    const actualDurations = this.records.map((r) => r.actualDurationMs);

    // Simple ratio analysis
    const ratios = estimatedCosts.map((est, i) => actualDurations[i] / Math.max(est, 0.001));
    const avgRatio = ratios.reduce((a, b) => a + b, 0) / ratios.length;

    // Row estimation accuracy
    const rowErrors = this.records.map(
      (r) => Math.abs(r.estimatedRows - r.actualRows) / Math.max(r.actualRows, 1)
    );
    const avgRowError = rowErrors.reduce((a, b) => a + b, 0) / rowErrors.length;

    return {
      count: this.records.length,
      avgCostToDurationRatio: avgRatio,
      avgRowEstimationError: avgRowError,
      minDurationMs: Math.min(...actualDurations),
      maxDurationMs: Math.max(...actualDurations),
      avgDurationMs: actualDurations.reduce((a, b) => a + b, 0) / actualDurations.length,
    };
  }

  /**
   * Clear recorded data.
   */
  clear(): void {
    this.records = [];
  }
}

/**
 * Create a query cost estimator with optional table stats and weights.
 */
export function createQueryCostEstimator(
  tableStats?: Record<string, TableStats>,
  costWeights?: Partial<CostWeights>
): QueryCostEstimator {
  return new QueryCostEstimator(tableStats, costWeights);
}
