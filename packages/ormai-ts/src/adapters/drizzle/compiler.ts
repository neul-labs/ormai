/**
 * Drizzle query compiler.
 *
 * Converts OrmAI DSL to Drizzle query builder calls.
 */

import type { FilterClause, OrderClause } from '../../core/dsl.js';
import { AdapterError } from '../../core/errors.js';

/**
 * Drizzle filter operators.
 */
export interface DrizzleOperators {
  eq: (column: unknown, value: unknown) => unknown;
  ne: (column: unknown, value: unknown) => unknown;
  lt: (column: unknown, value: unknown) => unknown;
  lte: (column: unknown, value: unknown) => unknown;
  gt: (column: unknown, value: unknown) => unknown;
  gte: (column: unknown, value: unknown) => unknown;
  inArray: (column: unknown, values: unknown[]) => unknown;
  notInArray: (column: unknown, values: unknown[]) => unknown;
  isNull: (column: unknown) => unknown;
  isNotNull: (column: unknown) => unknown;
  like: (column: unknown, pattern: string) => unknown;
  ilike: (column: unknown, pattern: string) => unknown;
  between: (column: unknown, min: unknown, max: unknown) => unknown;
  and: (...conditions: unknown[]) => unknown;
  or: (...conditions: unknown[]) => unknown;
  not: (condition: unknown) => unknown;
  asc: (column: unknown) => unknown;
  desc: (column: unknown) => unknown;
}

/**
 * Drizzle table reference.
 */
export interface DrizzleTableRef {
  [key: string]: unknown;
}

/**
 * Compiled Drizzle query.
 */
export interface CompiledDrizzleQuery {
  table: DrizzleTableRef;
  where?: unknown;
  orderBy?: unknown[];
  limit?: number;
  offset?: number;
  columns?: Record<string, boolean>;
}

/**
 * Compiled Drizzle mutation.
 */
export interface CompiledDrizzleMutation {
  table: DrizzleTableRef;
  type: 'insert' | 'update' | 'delete';
  data?: Record<string, unknown>;
  where?: unknown;
  returning?: boolean;
}

/**
 * Drizzle query compiler.
 */
export class DrizzleCompiler {
  private readonly tables: Record<string, DrizzleTableRef>;
  private readonly operators: DrizzleOperators;

  constructor(tables: Record<string, DrizzleTableRef>, operators: DrizzleOperators) {
    this.tables = tables;
    this.operators = operators;
  }

  /**
   * Get table reference by model name.
   */
  getTable(modelName: string): DrizzleTableRef {
    // Try exact match first
    if (this.tables[modelName]) {
      return this.tables[modelName];
    }

    // Try lowercase
    const lowerName = modelName.toLowerCase();
    if (this.tables[lowerName]) {
      return this.tables[lowerName];
    }

    // Try snake_case
    const snakeName = modelName
      .replace(/([a-z])([A-Z])/g, '$1_$2')
      .toLowerCase();
    if (this.tables[snakeName]) {
      return this.tables[snakeName];
    }

    throw new AdapterError(`Table not found for model: ${modelName}`);
  }

  /**
   * Get column from table.
   */
  getColumn(table: DrizzleTableRef, fieldName: string): unknown {
    if (fieldName in table) {
      return table[fieldName];
    }

    // Try snake_case
    const snakeName = fieldName
      .replace(/([a-z])([A-Z])/g, '$1_$2')
      .toLowerCase();
    if (snakeName in table) {
      return table[snakeName];
    }

    throw new AdapterError(`Column not found: ${fieldName}`);
  }

  /**
   * Compile filters to Drizzle where clause.
   */
  compileFilters(
    filters: FilterClause[],
    table: DrizzleTableRef
  ): unknown {
    if (filters.length === 0) {
      return undefined;
    }

    const conditions = filters.map((filter) => this.compileFilter(filter, table));

    if (conditions.length === 1) {
      return conditions[0];
    }

    return this.operators.and(...conditions);
  }

  /**
   * Compile a single filter.
   */
  private compileFilter(filter: FilterClause, table: DrizzleTableRef): unknown {
    const column = this.getColumn(table, filter.field);

    switch (filter.op) {
      case 'eq':
        return this.operators.eq(column, filter.value);
      case 'ne':
        return this.operators.ne(column, filter.value);
      case 'lt':
        return this.operators.lt(column, filter.value);
      case 'lte':
        return this.operators.lte(column, filter.value);
      case 'gt':
        return this.operators.gt(column, filter.value);
      case 'gte':
        return this.operators.gte(column, filter.value);
      case 'in':
        return this.operators.inArray(column, filter.value as unknown[]);
      case 'not_in':
        return this.operators.notInArray(column, filter.value as unknown[]);
      case 'is_null':
        return filter.value
          ? this.operators.isNull(column)
          : this.operators.isNotNull(column);
      case 'contains':
        return this.operators.ilike(column, `%${filter.value}%`);
      case 'startswith':
        return this.operators.ilike(column, `${filter.value}%`);
      case 'endswith':
        return this.operators.ilike(column, `%${filter.value}`);
      case 'between': {
        const [min, max] = filter.value as [unknown, unknown];
        return this.operators.between(column, min, max);
      }
      default:
        throw new AdapterError(`Unsupported filter operator: ${filter.op}`);
    }
  }

  /**
   * Compile order by clauses.
   */
  compileOrderBy(orderBy: OrderClause[], table: DrizzleTableRef): unknown[] {
    return orderBy.map((order) => {
      const column = this.getColumn(table, order.field);
      return order.direction === 'desc'
        ? this.operators.desc(column)
        : this.operators.asc(column);
    });
  }

  /**
   * Compile select fields to column selection.
   */
  compileSelect(fields: string[], _table: DrizzleTableRef): Record<string, boolean> {
    const columns: Record<string, boolean> = {};
    for (const field of fields) {
      columns[field] = true;
    }
    return columns;
  }

  /**
   * Compile a query request.
   */
  compileQuery(options: {
    model: string;
    filters?: FilterClause[];
    orderBy?: OrderClause[];
    take?: number;
    skip?: number;
    select?: string[];
  }): CompiledDrizzleQuery {
    const table = this.getTable(options.model);

    return {
      table,
      where: options.filters ? this.compileFilters(options.filters, table) : undefined,
      orderBy: options.orderBy ? this.compileOrderBy(options.orderBy, table) : undefined,
      limit: options.take,
      offset: options.skip,
      columns: options.select ? this.compileSelect(options.select, table) : undefined,
    };
  }

  /**
   * Compile an insert mutation.
   */
  compileInsert(options: {
    model: string;
    data: Record<string, unknown>;
  }): CompiledDrizzleMutation {
    const table = this.getTable(options.model);

    return {
      table,
      type: 'insert',
      data: options.data,
      returning: true,
    };
  }

  /**
   * Compile an update mutation.
   */
  compileUpdate(options: {
    model: string;
    data: Record<string, unknown>;
    filters: FilterClause[];
  }): CompiledDrizzleMutation {
    const table = this.getTable(options.model);

    return {
      table,
      type: 'update',
      data: options.data,
      where: this.compileFilters(options.filters, table),
      returning: true,
    };
  }

  /**
   * Compile a delete mutation.
   */
  compileDelete(options: {
    model: string;
    filters: FilterClause[];
  }): CompiledDrizzleMutation {
    const table = this.getTable(options.model);

    return {
      table,
      type: 'delete',
      where: this.compileFilters(options.filters, table),
      returning: true,
    };
  }
}

/**
 * Create a Drizzle compiler.
 */
export function createDrizzleCompiler(
  tables: Record<string, DrizzleTableRef>,
  operators: DrizzleOperators
): DrizzleCompiler {
  return new DrizzleCompiler(tables, operators);
}
