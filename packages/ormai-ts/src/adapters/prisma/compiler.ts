/**
 * Prisma query compiler.
 *
 * Compiles OrmAI DSL queries into Prisma query objects.
 */

import type { FilterClause, IncludeClause, OrderClause } from '../../core/dsl.js';
import type { ModelMetadata } from '../../core/types.js';

/**
 * Prisma where input type.
 */
export type PrismaWhereInput = Record<string, unknown>;

/**
 * Prisma order by input type.
 */
export type PrismaOrderByInput = Record<string, 'asc' | 'desc'>;

/**
 * Prisma include input type.
 */
export type PrismaIncludeInput = Record<string, boolean | PrismaIncludeDetails>;

/**
 * Prisma include details type.
 */
export interface PrismaIncludeDetails {
  select?: PrismaSelectInput;
  where?: PrismaWhereInput;
  take?: number;
  include?: PrismaIncludeInput;
}

/**
 * Prisma select input type.
 */
export type PrismaSelectInput = Record<string, boolean | PrismaSelectDetails>;

/**
 * Prisma select details type.
 */
export interface PrismaSelectDetails {
  select?: PrismaSelectInput;
  where?: PrismaWhereInput;
  take?: number;
}

/**
 * Compiled Prisma query args.
 */
export interface PrismaFindManyArgs {
  where?: PrismaWhereInput;
  orderBy?: PrismaOrderByInput[];
  take?: number;
  skip?: number;
  cursor?: Record<string, unknown>;
  select?: PrismaSelectInput;
  include?: PrismaIncludeInput;
}

/**
 * Compiled Prisma findUnique args.
 */
export interface PrismaFindUniqueArgs {
  where: Record<string, unknown>;
  select?: PrismaSelectInput;
  include?: PrismaIncludeInput;
}

/**
 * Compiled Prisma aggregate args.
 */
export interface PrismaAggregateArgs {
  where?: PrismaWhereInput;
  _count?: boolean | Record<string, boolean>;
  _sum?: Record<string, boolean>;
  _avg?: Record<string, boolean>;
  _min?: Record<string, boolean>;
  _max?: Record<string, boolean>;
}

/**
 * Compiled Prisma create args.
 */
export interface PrismaCreateArgs {
  data: Record<string, unknown>;
  select?: PrismaSelectInput;
  include?: PrismaIncludeInput;
}

/**
 * Compiled Prisma update args.
 */
export interface PrismaUpdateArgs {
  where: Record<string, unknown>;
  data: Record<string, unknown>;
  select?: PrismaSelectInput;
  include?: PrismaIncludeInput;
}

/**
 * Compiled Prisma delete args.
 */
export interface PrismaDeleteArgs {
  where: Record<string, unknown>;
}

/**
 * Prisma query compiler.
 */
export class PrismaCompiler {
  /**
   * Compile filter clauses to Prisma where input.
   */
  compileFilters(filters: readonly FilterClause[], _model?: ModelMetadata): PrismaWhereInput {
    if (filters.length === 0) {
      return {};
    }

    if (filters.length === 1) {
      return this.compileFilter(filters[0]);
    }

    // Multiple filters are AND-ed together
    return {
      AND: filters.map((f) => this.compileFilter(f)),
    };
  }

  /**
   * Compile a single filter clause.
   */
  compileFilter(filter: FilterClause): PrismaWhereInput {
    const { field, op, value } = filter;

    switch (op) {
      case 'eq':
        return { [field]: value };
      case 'ne':
        return { [field]: { not: value } };
      case 'lt':
        return { [field]: { lt: value } };
      case 'lte':
        return { [field]: { lte: value } };
      case 'gt':
        return { [field]: { gt: value } };
      case 'gte':
        return { [field]: { gte: value } };
      case 'in':
        return { [field]: { in: value } };
      case 'not_in':
        return { [field]: { notIn: value } };
      case 'is_null':
        return { [field]: value ? null : { not: null } };
      case 'contains':
        return { [field]: { contains: value, mode: 'insensitive' } };
      case 'startswith':
        return { [field]: { startsWith: value, mode: 'insensitive' } };
      case 'endswith':
        return { [field]: { endsWith: value, mode: 'insensitive' } };
      case 'between':
        if (Array.isArray(value) && value.length === 2) {
          return { [field]: { gte: value[0], lte: value[1] } };
        }
        return {};
      default:
        return { [field]: value };
    }
  }

  /**
   * Compile order clauses to Prisma orderBy input.
   */
  compileOrderBy(orders: readonly OrderClause[]): PrismaOrderByInput[] {
    return orders.map((order) => ({
      [order.field]: order.direction,
    }));
  }

  /**
   * Compile include clauses to Prisma include input.
   */
  compileIncludes(includes: readonly IncludeClause[]): PrismaIncludeInput {
    const result: PrismaIncludeInput = {};

    for (const inc of includes) {
      if (inc.select || inc.where || inc.take) {
        const details: PrismaIncludeDetails = {};

        if (inc.select) {
          details.select = this.compileSelect(inc.select);
        }

        if (inc.where) {
          details.where = this.compileFilters(inc.where);
        }

        if (inc.take) {
          details.take = inc.take;
        }

        result[inc.relation] = details;
      } else {
        result[inc.relation] = true;
      }
    }

    return result;
  }

  /**
   * Compile select fields to Prisma select input.
   */
  compileSelect(fields: readonly string[]): PrismaSelectInput {
    const result: PrismaSelectInput = {};
    for (const field of fields) {
      result[field] = true;
    }
    return result;
  }

  /**
   * Merge where conditions with AND.
   */
  mergeWhere(existing: PrismaWhereInput, additional: PrismaWhereInput): PrismaWhereInput {
    if (Object.keys(existing).length === 0) {
      return additional;
    }
    if (Object.keys(additional).length === 0) {
      return existing;
    }

    // If both have content, AND them together
    return {
      AND: [existing, additional],
    };
  }

  /**
   * Build a primary key where clause.
   */
  buildPrimaryKeyWhere(
    id: unknown,
    model: ModelMetadata
  ): Record<string, unknown> {
    if (model.primaryKeys && model.primaryKeys.length > 1) {
      // Composite primary key - id should be an object
      if (typeof id === 'object' && id !== null) {
        return id as Record<string, unknown>;
      }
      throw new Error(`Composite primary key requires an object with fields: ${model.primaryKeys.join(', ')}`);
    }

    return { [model.primaryKey]: id };
  }
}

/**
 * Default compiler instance.
 */
export const defaultCompiler = new PrismaCompiler();
