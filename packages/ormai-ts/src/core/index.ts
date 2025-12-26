/**
 * Core module for OrmAI.
 *
 * Provides the foundational types, schemas, and utilities for the entire library.
 */

// Context
export {
  type Principal,
  type RunContext,
  type CreateContextOptions,
  createPrincipal,
  createContext,
  createContextWithPrincipal,
  hasRole,
  hasAnyRole,
  isPrincipal,
  isRunContext,
} from './context.js';

// Types
export {
  type FieldType,
  type RelationType,
  type AggregateOp,
  type FieldMetadata,
  type RelationMetadata,
  type ModelMetadata,
  type SchemaMetadata,
  SchemaMetadataUtils,
} from './types.js';

// DSL Schemas
export {
  // Schema exports
  FilterOpSchema,
  OrderDirectionSchema,
  FilterClauseSchema,
  OrderClauseSchema,
  IncludeClauseSchema,
  QueryRequestSchema,
  GetRequestSchema,
  AggregateRequestSchema,
  QueryResultSchema,
  GetResultSchema,
  AggregateResultSchema,
  CreateRequestSchema,
  UpdateRequestSchema,
  DeleteRequestSchema,
  BulkUpdateRequestSchema,
  CreateResultSchema,
  UpdateResultSchema,
  DeleteResultSchema,
  BulkUpdateResultSchema,
  // Type exports
  type FilterOp,
  type OrderDirection,
  type FilterClause,
  type OrderClause,
  type IncludeClause,
  type QueryRequest,
  type GetRequest,
  type AggregateRequest,
  type QueryResult,
  type GetResult,
  type AggregateResult,
  type CreateRequest,
  type UpdateRequest,
  type DeleteRequest,
  type BulkUpdateRequest,
  type CreateResult,
  type UpdateResult,
  type DeleteResult,
  type BulkUpdateResult,
  type AnyRequest,
  type AnyResult,
  // Helper functions
  filter,
  orderBy,
  include,
} from './dsl.js';

// Cursor
export {
  type CursorType,
  type CursorData,
  type OrderField,
  type FilterCondition,
  CursorEncoder,
  buildKeysetCondition,
  defaultEncoder,
} from './cursor.js';

// Errors
export {
  ErrorCodes,
  type ErrorCode,
  OrmAIError,
  ModelNotAllowedError,
  FieldNotAllowedError,
  RelationNotAllowedError,
  TenantScopeRequiredError,
  QueryTooBroadError,
  QueryBudgetExceededError,
  WriteDisabledError,
  WriteApprovalRequiredError,
  MaxAffectedRowsExceededError,
  ValidationError,
  NotFoundError,
  AdapterError,
  InternalError,
  isOrmAIError,
  wrapError,
} from './errors.js';
