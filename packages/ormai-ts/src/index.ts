/**
 * OrmAI TypeScript Edition
 *
 * A policy-governed, auditable database capability layer for TypeScript/Node.js applications.
 */

// Core module
export {
  // Types
  type FieldType,
  type RelationType,
  type AggregateOp,
  type FieldMetadata,
  type RelationMetadata,
  type ModelMetadata,
  type SchemaMetadata,
  SchemaMetadataUtils,
  // Context
  type Principal,
  type CreateContextOptions,
  type RunContext,
  createPrincipal,
  createContext,
  hasRole,
  // Errors
  OrmAIError,
  ModelNotAllowedError,
  FieldNotAllowedError,
  RelationNotAllowedError,
  TenantScopeRequiredError,
  QueryBudgetExceededError,
  QueryTooBroadError,
  WriteDisabledError,
  ValidationError,
  AdapterError,
  // DSL
  FilterOpSchema,
  FilterClauseSchema,
  type FilterClause,
  OrderDirectionSchema,
  OrderClauseSchema,
  type OrderClause,
  IncludeClauseSchema,
  type IncludeClause,
  QueryRequestSchema,
  type QueryRequest,
  GetRequestSchema,
  type GetRequest,
  AggregateRequestSchema,
  type AggregateRequest,
  CreateRequestSchema,
  type CreateRequest,
  UpdateRequestSchema,
  type UpdateRequest,
  DeleteRequestSchema,
  type DeleteRequest,
  BulkUpdateRequestSchema,
  type BulkUpdateRequest,
  filter,
  orderBy,
  include,
  // Cursor
  CursorEncoder,
  buildKeysetCondition,
} from './core/index.js';

// Policy module
export {
  // Models
  type FieldAction,
  FieldPolicySchema,
  type FieldPolicy,
  RelationPolicySchema,
  type RelationPolicy,
  RowPolicySchema,
  type RowPolicy,
  WritePolicySchema,
  type WritePolicy,
  BudgetSchema,
  type Budget,
  ModelPolicySchema,
  type ModelPolicy,
  PolicySchema,
  type Policy,
  PolicyDecision,
  // Engine
  PolicyEngine,
  // Scoping
  ScopeInjector,
  // Redaction
  Redactor,
  // Budgets
  ComplexityScorer,
  BudgetEnforcer,
  // Costs
  QueryCostEstimator,
  CostTracker,
} from './policy/index.js';

// Adapters
export {
  type CompiledQuery,
  type CompiledMutation,
  type OrmAdapter,
  BaseOrmAdapter,
  createCompiledQuery,
  createCompiledMutation,
} from './adapters/index.js';

// Prisma adapter
export {
  PrismaAdapter,
  PrismaCompiler,
  introspectPrismaClient,
  introspectFromDMMF,
} from './adapters/prisma/index.js';

// Drizzle adapter
export {
  DrizzleAdapter,
  DrizzleCompiler,
  DrizzleIntrospector,
  createDrizzleAdapter,
  type DrizzleAdapterConfig,
  type DrizzleDB,
  type DrizzleSchema,
} from './adapters/drizzle/index.js';

// TypeORM adapter
export {
  TypeORMAdapter,
  TypeORMCompiler,
  TypeORMIntrospector,
  createTypeORMAdapter,
  type TypeORMAdapterConfig,
  type TypeORMAdapterDataSource,
} from './adapters/typeorm/index.js';

// Tools
export {
  type Tool,
  type ToolResult,
  BaseTool,
  ToolRegistry,
  DescribeSchemaTool,
  QueryTool,
  GetTool,
  AggregateTool,
  CreateTool,
  UpdateTool,
  DeleteTool,
  BulkUpdateTool,
  createGenericTools,
} from './tools/index.js';

// Store
export {
  AuditRecordSchema,
  type AuditRecord,
  type AuditStore,
  InMemoryAuditStore,
  JsonlAuditStore,
  withAudit,
} from './store/index.js';

// Integrations
export {
  toVercelAITools,
  toLangChainTools,
  toOpenAITools,
  toAnthropicTools,
  toLlamaIndexTools,
  toMastraTools,
  toJsonSchemas,
} from './integrations/index.js';

// Utils
export {
  type ProfileMode,
  DefaultsProfileSchema,
  type DefaultsProfile,
  PROD_DEFAULTS,
  INTERNAL_DEFAULTS,
  DEV_DEFAULTS,
  getDefaultsProfile,
  budgetFromProfile,
  writePolicyFromProfile,
  PolicyBuilder,
  createPolicyBuilder,
  type ToolsetFactoryOptions,
  type QuickSetupOptions,
  type ViewFactoryOptions,
  createToolset,
  quickSetup,
  createRestrictedView,
  createTestContext,
  createTestSchema,
  createTestPolicy,
  createMockAdapter,
  assertThrows,
} from './utils/index.js';

// MCP
export {
  type AuthResult,
  type AuthMiddleware,
  createApiKeyAuth,
  createJwtAuth,
  createContextFactory,
  extractTenantFromHeaders,
  principalFromHeaders,
  combineAuthMiddlewares,
  createDevAuth,
  type McpToolDefinition,
  type McpToolCallRequest,
  type McpToolCallResult,
  type McpServerConfig,
  McpServer,
  createMcpServer,
  createSimpleMcpServer,
} from './mcp/index.js';
