/**
 * Query DSL schemas for OrmAI.
 *
 * These Zod schemas define the structured query language that agents use
 * to interact with the database. The DSL is designed to be safe, expressive,
 * and easily validated.
 */

import { z } from 'zod';

// =============================================================================
// FILTER OPERATORS
// =============================================================================

/**
 * Supported filter operators.
 */
export const FilterOpSchema = z.enum([
  'eq',
  'ne',
  'lt',
  'lte',
  'gt',
  'gte',
  'in',
  'not_in',
  'is_null',
  'contains',
  'startswith',
  'endswith',
  'between',
]);

export type FilterOp = z.infer<typeof FilterOpSchema>;

/**
 * Sort order direction.
 */
export const OrderDirectionSchema = z.enum(['asc', 'desc']);

export type OrderDirection = z.infer<typeof OrderDirectionSchema>;

// =============================================================================
// CLAUSE SCHEMAS
// =============================================================================

/**
 * Validate field name to prevent injection.
 */
const fieldNameSchema = z
  .string()
  .min(1, 'Field name cannot be empty')
  .refine(
    (v) => !v.includes(';') && !v.includes('--') && !v.includes('/*') && !v.includes('*/'),
    { message: 'Invalid characters in field name' }
  )
  .transform((v) => v.trim());

/**
 * A single filter condition.
 *
 * @example
 * { field: "status", op: "eq", value: "active" }
 * { field: "created_at", op: "gte", value: "2024-01-01" }
 * { field: "id", op: "in", value: [1, 2, 3] }
 */
export const FilterClauseSchema = z
  .object({
    field: fieldNameSchema.describe('The field name to filter on'),
    op: FilterOpSchema.describe('The filter operator'),
    value: z.unknown().describe('The value to compare against'),
  })
  .readonly();

export type FilterClause = z.infer<typeof FilterClauseSchema>;

/**
 * A single order/sort clause.
 *
 * @example
 * { field: "created_at", direction: "desc" }
 */
export const OrderClauseSchema = z
  .object({
    field: fieldNameSchema.describe('The field name to order by'),
    direction: OrderDirectionSchema.default('asc').describe('Sort direction'),
  })
  .readonly();

export type OrderClause = z.infer<typeof OrderClauseSchema>;

/**
 * Specifies a relation to include in the query results.
 *
 * @example
 * { relation: "orders", select: ["id", "total", "status"] }
 */
export const IncludeClauseSchema = z
  .object({
    relation: z.string().min(1).describe('The relation name to include'),
    select: z.array(z.string()).optional().describe('Fields to select from the relation'),
    where: z.array(z.lazy(() => FilterClauseSchema)).optional().describe('Filters to apply to the relation'),
    take: z.number().int().min(1).max(100).optional().describe('Max items to include from relation'),
  })
  .readonly();

export type IncludeClause = z.infer<typeof IncludeClauseSchema>;

// =============================================================================
// QUERY REQUEST/RESULT SCHEMAS
// =============================================================================

/**
 * A structured query request.
 *
 * This is the primary DSL for querying data through OrmAI. It supports:
 * - Field selection
 * - Filtering with various operators
 * - Ordering
 * - Cursor-based pagination
 * - Relation includes
 *
 * @example
 * {
 *   model: "Order",
 *   select: ["id", "total", "status", "created_at"],
 *   where: [
 *     { field: "status", op: "eq", value: "pending" },
 *     { field: "created_at", op: "gte", value: "2024-01-01" }
 *   ],
 *   orderBy: [{ field: "created_at", direction: "desc" }],
 *   take: 25,
 *   include: [{ relation: "customer", select: ["id", "name"] }]
 * }
 */
export const QueryRequestSchema = z
  .object({
    model: z.string().min(1).describe('The model/table name to query'),
    select: z.array(z.string()).optional().describe('Fields to select (undefined means all allowed fields)'),
    where: z.array(FilterClauseSchema).optional().describe('Filter conditions (AND-ed together)'),
    orderBy: z.array(OrderClauseSchema).optional().describe('Sort order'),
    take: z.number().int().min(1).max(100).default(25).describe('Maximum number of rows to return'),
    cursor: z.string().optional().describe('Pagination cursor from previous response'),
    include: z.array(IncludeClauseSchema).optional().describe('Relations to include'),
  })
  .readonly();

export type QueryRequest = z.infer<typeof QueryRequestSchema>;

/**
 * A request to get a single record by primary key.
 *
 * @example
 * {
 *   model: "Order",
 *   id: 123,
 *   select: ["id", "total", "status"],
 *   include: [{ relation: "items" }]
 * }
 */
export const GetRequestSchema = z
  .object({
    model: z.string().min(1).describe('The model/table name'),
    id: z.unknown().describe('The primary key value'),
    select: z.array(z.string()).optional().describe('Fields to select'),
    include: z.array(IncludeClauseSchema).optional().describe('Relations to include'),
  })
  .readonly();

export type GetRequest = z.infer<typeof GetRequestSchema>;

/**
 * A request to perform an aggregation.
 *
 * @example
 * {
 *   model: "Order",
 *   operation: "sum",
 *   field: "total",
 *   where: [{ field: "status", op: "eq", value: "completed" }]
 * }
 */
export const AggregateRequestSchema = z
  .object({
    model: z.string().min(1).describe('The model/table name'),
    operation: z
      .enum(['count', 'sum', 'avg', 'min', 'max'])
      .describe('Aggregation operation'),
    field: z.string().optional().describe('Field to aggregate (required for sum/avg/min/max)'),
    where: z.array(FilterClauseSchema).optional().describe('Filter conditions'),
  })
  .readonly();

export type AggregateRequest = z.infer<typeof AggregateRequestSchema>;

/**
 * Result of a query operation.
 */
export const QueryResultSchema = z
  .object({
    data: z.array(z.record(z.unknown())).default([]),
    nextCursor: z.string().nullable().default(null),
    hasMore: z.boolean().default(false),
    totalCount: z.number().int().nullable().default(null),
  })
  .readonly();

export type QueryResult = z.infer<typeof QueryResultSchema>;

/**
 * Result of a get operation.
 */
export const GetResultSchema = z
  .object({
    data: z.record(z.unknown()).nullable().default(null),
    found: z.boolean().default(false),
  })
  .readonly();

export type GetResult = z.infer<typeof GetResultSchema>;

/**
 * Result of an aggregation operation.
 */
export const AggregateResultSchema = z
  .object({
    value: z.unknown().default(null),
    operation: z.string(),
    field: z.string().nullable().default(null),
    rowCount: z.number().int().default(0),
  })
  .readonly();

export type AggregateResult = z.infer<typeof AggregateResultSchema>;

// =============================================================================
// MUTATION REQUEST/RESULT SCHEMAS
// =============================================================================

/**
 * A request to create a new record.
 *
 * @example
 * {
 *   model: "Order",
 *   data: {
 *     customerId: 123,
 *     total: 99.99,
 *     status: "pending"
 *   },
 *   reason: "Customer placed order via checkout flow"
 * }
 */
export const CreateRequestSchema = z
  .object({
    model: z.string().min(1).describe('The model/table name'),
    data: z.record(z.unknown()).describe('Field values for the new record'),
    reason: z.string().optional().describe('Reason for the mutation (required by some policies)'),
    returnFields: z.array(z.string()).optional().describe('Fields to return after creation'),
  })
  .readonly();

export type CreateRequest = z.infer<typeof CreateRequestSchema>;

/**
 * A request to update a record by primary key.
 *
 * @example
 * {
 *   model: "Order",
 *   id: 123,
 *   data: { status: "shipped" },
 *   reason: "Order shipped by warehouse"
 * }
 */
export const UpdateRequestSchema = z
  .object({
    model: z.string().min(1).describe('The model/table name'),
    id: z.unknown().describe('The primary key of the record to update'),
    data: z.record(z.unknown()).describe('Fields to update'),
    reason: z.string().optional().describe('Reason for the mutation'),
    returnFields: z.array(z.string()).optional().describe('Fields to return after update'),
  })
  .readonly();

export type UpdateRequest = z.infer<typeof UpdateRequestSchema>;

/**
 * A request to delete a record by primary key.
 *
 * By default, this performs a soft delete if the model has a soft delete field.
 * Hard deletes require explicit policy permission.
 *
 * @example
 * {
 *   model: "Order",
 *   id: 123,
 *   reason: "Customer requested cancellation",
 *   hard: false
 * }
 */
export const DeleteRequestSchema = z
  .object({
    model: z.string().min(1).describe('The model/table name'),
    id: z.unknown().describe('The primary key of the record to delete'),
    reason: z.string().optional().describe('Reason for the deletion'),
    hard: z.boolean().default(false).describe('If true, perform hard delete instead of soft delete'),
  })
  .readonly();

export type DeleteRequest = z.infer<typeof DeleteRequestSchema>;

/**
 * A request to update multiple records by their primary keys.
 *
 * This is safer than a filter-based bulk update because it requires
 * explicit identification of each record to update.
 *
 * @example
 * {
 *   model: "Order",
 *   ids: [123, 124, 125],
 *   data: { status: "cancelled" },
 *   reason: "Batch cancellation due to supplier issue"
 * }
 */
export const BulkUpdateRequestSchema = z
  .object({
    model: z.string().min(1).describe('The model/table name'),
    ids: z
      .array(z.unknown())
      .min(1)
      .max(100)
      .describe('Primary keys of records to update'),
    data: z.record(z.unknown()).describe('Fields to update on all records'),
    reason: z.string().optional().describe('Reason for the mutation'),
  })
  .readonly();

export type BulkUpdateRequest = z.infer<typeof BulkUpdateRequestSchema>;

/**
 * Result of a create operation.
 */
export const CreateResultSchema = z
  .object({
    data: z.record(z.unknown()).default({}),
    id: z.unknown().describe('Primary key of created record'),
    success: z.boolean().default(true),
  })
  .readonly();

export type CreateResult = z.infer<typeof CreateResultSchema>;

/**
 * Result of an update operation.
 */
export const UpdateResultSchema = z
  .object({
    data: z.record(z.unknown()).nullable().default(null),
    success: z.boolean().default(true),
    found: z.boolean().default(true),
  })
  .readonly();

export type UpdateResult = z.infer<typeof UpdateResultSchema>;

/**
 * Result of a delete operation.
 */
export const DeleteResultSchema = z
  .object({
    success: z.boolean().default(true),
    found: z.boolean().default(true),
    softDeleted: z.boolean().default(true).describe('True if soft delete was used'),
  })
  .readonly();

export type DeleteResult = z.infer<typeof DeleteResultSchema>;

/**
 * Result of a bulk update operation.
 */
export const BulkUpdateResultSchema = z
  .object({
    updatedCount: z.number().int().default(0),
    success: z.boolean().default(true),
    failedIds: z.array(z.unknown()).default([]).describe('IDs that failed to update'),
  })
  .readonly();

export type BulkUpdateResult = z.infer<typeof BulkUpdateResultSchema>;

// =============================================================================
// HELPER FUNCTIONS
// =============================================================================

/**
 * Create a filter clause with type safety.
 */
export function filter(field: string, op: FilterOp, value: unknown): FilterClause {
  return FilterClauseSchema.parse({ field, op, value });
}

/**
 * Create an order clause with type safety.
 */
export function orderBy(field: string, direction: OrderDirection = 'asc'): OrderClause {
  return OrderClauseSchema.parse({ field, direction });
}

/**
 * Create an include clause with type safety.
 */
export function include(
  relation: string,
  opts?: { select?: string[]; where?: FilterClause[]; take?: number }
): IncludeClause {
  return IncludeClauseSchema.parse({ relation, ...opts });
}

/**
 * Union type for all request types.
 */
export type AnyRequest =
  | QueryRequest
  | GetRequest
  | AggregateRequest
  | CreateRequest
  | UpdateRequest
  | DeleteRequest
  | BulkUpdateRequest;

/**
 * Union type for all result types.
 */
export type AnyResult =
  | QueryResult
  | GetResult
  | AggregateResult
  | CreateResult
  | UpdateResult
  | DeleteResult
  | BulkUpdateResult;
