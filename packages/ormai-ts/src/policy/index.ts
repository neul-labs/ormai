/**
 * Policy module for OrmAI.
 *
 * Provides policy definitions, evaluation engine, scoping, redaction, and budgets.
 */

// Models
export {
  // Schemas
  FieldActionSchema,
  FieldPolicySchema,
  RelationPolicySchema,
  RowPolicySchema,
  WritePolicySchema,
  BudgetSchema,
  ModelPolicySchema,
  PolicySchema,
  // Types
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
  // Utils
  ModelPolicyUtils,
  PolicyUtils,
  // Defaults
  DEFAULT_BUDGET,
  DEFAULT_ROW_POLICY,
  DEFAULT_WRITE_POLICY,
} from './models.js';

// Engine
export { PolicyDecision, PolicyEngine } from './engine.js';

// Scoping
export { ScopeInjector, createScopeInjector } from './scoping.js';

// Redaction
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
} from './redaction.js';

// Budgets
export {
  DEFAULT_COMPLEXITY_WEIGHTS,
  type ComplexityWeights,
  ComplexityScorer,
  BudgetEnforcer,
  createComplexityScorer,
  createBudgetEnforcer,
} from './budgets.js';

// Costs
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
} from './costs.js';
