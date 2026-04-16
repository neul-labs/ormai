/**
 * @ormai/core - Core types, policy engine, adapter interfaces, and schemas.
 */

// ─── Core ──────────────────────────────────────────────────────────────────────

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
} from './core/context.js';

export {
  type FieldType,
  type RelationType,
  type AggregateOp,
  type FieldMetadata,
  type RelationMetadata,
  type ModelMetadata,
  type SchemaMetadata,
  SchemaMetadataUtils,
} from './core/types.js';

export {
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
  filter,
  orderBy,
  include,
} from './core/dsl.js';

export {
  type CursorType,
  type CursorData,
  type OrderField,
  type FilterCondition,
  CursorEncoder,
  buildKeysetCondition,
  defaultEncoder,
} from './core/cursor.js';

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
  AdapterNotImplementedError,
  InternalError,
  isOrmAIError,
  wrapError,
} from './core/errors.js';

// ─── Policy ───────────────────────────────────────────────────────────────────

export {
  FieldActionSchema,
  FieldPolicySchema,
  RelationPolicySchema,
  RowPolicySchema,
  WritePolicySchema,
  BudgetSchema,
  ModelPolicySchema,
  PolicySchema,
  type FieldAction,
  type FieldPolicy,
  type FieldPolicyWithRedactor,
  type CustomRedactor,
  type RelationPolicy,
  type RowPolicy,
  type WritePolicy,
  type Budget,
  type ModelPolicy,
  type Policy,
  ModelPolicyUtils,
  PolicyUtils,
  DEFAULT_BUDGET,
  DEFAULT_ROW_POLICY,
  DEFAULT_WRITE_POLICY,
} from './policy/models.js';

export { PolicyDecision, PolicyEngine } from './policy/engine.js';

export { ScopeInjector, createScopeInjector } from './policy/scoping.js';

export {
  type RedactionStrategy,
  Redactor,
  createRedactor,
  maskEmail,
  maskPhone,
  maskPartial,
  maskCard,
  hashSha256,
  maskValue,
} from './policy/redaction.js';

export {
  DEFAULT_COMPLEXITY_WEIGHTS,
  type ComplexityWeights,
  ComplexityScorer,
  BudgetEnforcer,
  createComplexityScorer,
  createBudgetEnforcer,
} from './policy/budgets.js';

export {
  type CostCategory,
  type CostBreakdown,
  createCostBreakdown,
  getTotalCost,
  costBreakdownToDict,
  TableStatsSchema,
  type TableStats,
  DEFAULT_COST_WEIGHTS,
  type CostWeights,
  QueryCostEstimator,
  CostBudgetSchema,
  type CostBudget,
  checkCostBudget,
  CostTracker,
  createQueryCostEstimator,
} from './policy/costs.js';

// ─── Adapter Base ─────────────────────────────────────────────────────────────

export {
  type CompiledQuery,
  type CompiledMutation,
  type OrmAdapter,
  BaseOrmAdapter,
  createCompiledQuery,
  createCompiledMutation,
  applyRedaction,
  applyRedactionToRecords,
} from './adapter.js';

// ─── Tool Base ─────────────────────────────────────────────────────────────────

export {
  type ToolResult,
  type Tool,
  BaseTool,
  ToolRegistry,
  ok,
  fail,
  createToolRegistry,
} from './tool.js';

// ─── Audit Base ────────────────────────────────────────────────────────────────

export {
  type AuditQueryOptions,
  type AuditStore,
  BaseAuditStore,
} from './store-base.js';

export {
  ErrorInfoSchema,
  AuditRecordSchema,
  type ErrorInfo,
  type AuditRecord,
  isSuccess,
  toLogDict,
  createAuditRecord,
} from './store-models.js';