/**
 * Scope injection for row-level security.
 *
 * The ScopeInjector modifies queries to enforce tenant isolation and ownership
 * scoping at the database level.
 */

import type { RunContext } from '../core/context.js';
import type { FilterClause } from '../core/dsl.js';
import type { RowPolicy } from './models.js';

/**
 * Injects scope filters into queries based on row policies and context.
 *
 * This ensures that all queries are automatically filtered to only return
 * data that the current principal is allowed to see.
 */
export class ScopeInjector {
  constructor(private readonly rowPolicy: RowPolicy) {}

  /**
   * Generate scope filters based on the row policy and context.
   *
   * Returns a list of FilterClause objects that should be injected
   * into the query's WHERE clause.
   */
  getScopeFilters(ctx: RunContext): FilterClause[] {
    const filters: FilterClause[] = [];

    // Tenant scope filter
    if (this.rowPolicy.tenantScopeField && ctx.principal.tenantId) {
      filters.push({
        field: this.rowPolicy.tenantScopeField,
        op: 'eq',
        value: ctx.principal.tenantId,
      });
    }

    // Ownership scope filter
    if (this.rowPolicy.ownershipScopeField && ctx.principal.userId) {
      filters.push({
        field: this.rowPolicy.ownershipScopeField,
        op: 'eq',
        value: ctx.principal.userId,
      });
    }

    // Soft delete filter
    if (this.rowPolicy.softDeleteField && !this.rowPolicy.includeSoftDeleted) {
      filters.push({
        field: this.rowPolicy.softDeleteField,
        op: 'is_null',
        value: true,
      });
    }

    return filters;
  }

  /**
   * Merge user-provided filters with scope filters.
   *
   * Scope filters are always applied and cannot be overridden by user filters.
   */
  mergeFilters(
    userFilters: readonly FilterClause[] | undefined,
    scopeFilters: FilterClause[]
  ): FilterClause[] {
    const result = [...scopeFilters]; // Scope filters first
    if (userFilters) {
      result.push(...userFilters);
    }
    return result;
  }

  /**
   * Get data to inject into created records for scoping.
   *
   * This is used to automatically set tenant/owner fields on new records.
   */
  getScopeData(ctx: RunContext): Record<string, unknown> {
    const data: Record<string, unknown> = {};

    if (this.rowPolicy.tenantScopeField && ctx.principal.tenantId) {
      data[this.rowPolicy.tenantScopeField] = ctx.principal.tenantId;
    }

    if (this.rowPolicy.ownershipScopeField && ctx.principal.userId) {
      data[this.rowPolicy.ownershipScopeField] = ctx.principal.userId;
    }

    return data;
  }
}

/**
 * Create a scope injector for a row policy.
 */
export function createScopeInjector(rowPolicy: RowPolicy): ScopeInjector {
  return new ScopeInjector(rowPolicy);
}
