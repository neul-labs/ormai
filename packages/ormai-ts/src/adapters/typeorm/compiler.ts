/**
 * TypeORM query compiler.
 *
 * Converts OrmAI DSL to TypeORM QueryBuilder calls.
 */

import type { FilterClause, OrderClause } from '../../core/dsl.js';
import { AdapterError } from '../../core/errors.js';

/**
 * TypeORM query builder interface.
 */
export interface TypeORMQueryBuilder<T = unknown> {
  select: (fields: string[]) => TypeORMQueryBuilder<T>;
  addSelect: (field: string) => TypeORMQueryBuilder<T>;
  where: (condition: string, parameters?: Record<string, unknown>) => TypeORMQueryBuilder<T>;
  andWhere: (condition: string, parameters?: Record<string, unknown>) => TypeORMQueryBuilder<T>;
  orWhere: (condition: string, parameters?: Record<string, unknown>) => TypeORMQueryBuilder<T>;
  orderBy: (field: string, order: 'ASC' | 'DESC') => TypeORMQueryBuilder<T>;
  addOrderBy: (field: string, order: 'ASC' | 'DESC') => TypeORMQueryBuilder<T>;
  take: (limit: number) => TypeORMQueryBuilder<T>;
  skip: (offset: number) => TypeORMQueryBuilder<T>;
  leftJoinAndSelect: (relation: string, alias: string) => TypeORMQueryBuilder<T>;
  getMany: () => Promise<T[]>;
  getOne: () => Promise<T | null>;
  getCount: () => Promise<number>;
  execute: () => Promise<unknown>;
}

/**
 * Compiled TypeORM query options.
 */
export interface CompiledTypeORMQuery {
  entityName: string;
  alias: string;
  selectFields?: string[];
  whereConditions: Array<{ condition: string; parameters: Record<string, unknown> }>;
  orderBy: Array<{ field: string; direction: 'ASC' | 'DESC' }>;
  take?: number;
  skip?: number;
  joins: Array<{ relation: string; alias: string }>;
}

/**
 * Compiled TypeORM mutation.
 */
export interface CompiledTypeORMMutation {
  entityName: string;
  type: 'insert' | 'update' | 'delete';
  data?: Record<string, unknown>;
  whereConditions: Array<{ condition: string; parameters: Record<string, unknown> }>;
}

/**
 * TypeORM query compiler.
 */
export class TypeORMCompiler {
  private parameterIndex = 0;

  /**
   * Reset parameter index for a new query.
   */
  resetParameters(): void {
    this.parameterIndex = 0;
  }

  /**
   * Generate a unique parameter name.
   */
  private nextParameterName(): string {
    return `p${this.parameterIndex++}`;
  }

  /**
   * Compile filters to TypeORM where conditions.
   */
  compileFilters(
    filters: FilterClause[],
    alias: string
  ): Array<{ condition: string; parameters: Record<string, unknown> }> {
    return filters.map((filter) => this.compileFilter(filter, alias));
  }

  /**
   * Compile a single filter.
   */
  private compileFilter(
    filter: FilterClause,
    alias: string
  ): { condition: string; parameters: Record<string, unknown> } {
    const field = `${alias}.${filter.field}`;
    const paramName = this.nextParameterName();

    switch (filter.op) {
      case 'eq':
        return {
          condition: `${field} = :${paramName}`,
          parameters: { [paramName]: filter.value },
        };

      case 'ne':
        return {
          condition: `${field} != :${paramName}`,
          parameters: { [paramName]: filter.value },
        };

      case 'lt':
        return {
          condition: `${field} < :${paramName}`,
          parameters: { [paramName]: filter.value },
        };

      case 'lte':
        return {
          condition: `${field} <= :${paramName}`,
          parameters: { [paramName]: filter.value },
        };

      case 'gt':
        return {
          condition: `${field} > :${paramName}`,
          parameters: { [paramName]: filter.value },
        };

      case 'gte':
        return {
          condition: `${field} >= :${paramName}`,
          parameters: { [paramName]: filter.value },
        };

      case 'in':
        return {
          condition: `${field} IN (:...${paramName})`,
          parameters: { [paramName]: filter.value },
        };

      case 'not_in':
        return {
          condition: `${field} NOT IN (:...${paramName})`,
          parameters: { [paramName]: filter.value },
        };

      case 'is_null':
        return filter.value
          ? { condition: `${field} IS NULL`, parameters: {} }
          : { condition: `${field} IS NOT NULL`, parameters: {} };

      case 'contains':
        return {
          condition: `${field} ILIKE :${paramName}`,
          parameters: { [paramName]: `%${filter.value}%` },
        };

      case 'startswith':
        return {
          condition: `${field} ILIKE :${paramName}`,
          parameters: { [paramName]: `${filter.value}%` },
        };

      case 'endswith':
        return {
          condition: `${field} ILIKE :${paramName}`,
          parameters: { [paramName]: `%${filter.value}` },
        };

      case 'between': {
        const [min, max] = filter.value as [unknown, unknown];
        const minParam = this.nextParameterName();
        const maxParam = this.nextParameterName();
        return {
          condition: `${field} BETWEEN :${minParam} AND :${maxParam}`,
          parameters: { [minParam]: min, [maxParam]: max },
        };
      }

      default:
        throw new AdapterError(`Unsupported filter operator: ${filter.op}`);
    }
  }

  /**
   * Compile order by clauses.
   */
  compileOrderBy(
    orderBy: OrderClause[],
    alias: string
  ): Array<{ field: string; direction: 'ASC' | 'DESC' }> {
    return orderBy.map((order) => ({
      field: `${alias}.${order.field}`,
      direction: order.direction === 'desc' ? 'DESC' : 'ASC',
    }));
  }

  /**
   * Compile a query request.
   */
  compileQuery(options: {
    model: string;
    alias?: string;
    filters?: FilterClause[];
    orderBy?: OrderClause[];
    take?: number;
    skip?: number;
    select?: string[];
    includes?: string[];
  }): CompiledTypeORMQuery {
    this.resetParameters();
    const alias = options.alias ?? options.model.toLowerCase();

    const whereConditions = options.filters
      ? this.compileFilters(options.filters, alias)
      : [];

    const orderByCompiled = options.orderBy
      ? this.compileOrderBy(options.orderBy, alias)
      : [];

    const joins = (options.includes ?? []).map((relation, index) => ({
      relation: `${alias}.${relation}`,
      alias: `${relation}_${index}`,
    }));

    return {
      entityName: options.model,
      alias,
      selectFields: options.select?.map((f) => `${alias}.${f}`),
      whereConditions,
      orderBy: orderByCompiled,
      take: options.take,
      skip: options.skip,
      joins,
    };
  }

  /**
   * Compile an insert mutation.
   */
  compileInsert(options: {
    model: string;
    data: Record<string, unknown>;
  }): CompiledTypeORMMutation {
    return {
      entityName: options.model,
      type: 'insert',
      data: options.data,
      whereConditions: [],
    };
  }

  /**
   * Compile an update mutation.
   */
  compileUpdate(options: {
    model: string;
    data: Record<string, unknown>;
    filters: FilterClause[];
  }): CompiledTypeORMMutation {
    this.resetParameters();
    const alias = options.model.toLowerCase();

    return {
      entityName: options.model,
      type: 'update',
      data: options.data,
      whereConditions: this.compileFilters(options.filters, alias),
    };
  }

  /**
   * Compile a delete mutation.
   */
  compileDelete(options: {
    model: string;
    filters: FilterClause[];
  }): CompiledTypeORMMutation {
    this.resetParameters();
    const alias = options.model.toLowerCase();

    return {
      entityName: options.model,
      type: 'delete',
      whereConditions: this.compileFilters(options.filters, alias),
    };
  }
}

/**
 * Create a TypeORM compiler.
 */
export function createTypeORMCompiler(): TypeORMCompiler {
  return new TypeORMCompiler();
}
