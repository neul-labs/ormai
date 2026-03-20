/**
 * Policy model definitions.
 *
 * Policies control what data can be accessed, how it's filtered, and what operations
 * are allowed. They are evaluated at validation time, compile time (for query injection),
 * and post-execution (for redaction).
 */

import { z } from 'zod';

/**
 * Action to take for a field.
 */
export const FieldActionSchema = z.enum(['allow', 'deny', 'mask', 'hash']);

export type FieldAction = z.infer<typeof FieldActionSchema>;

/**
 * Policy for a single field.
 *
 * Controls visibility and transformation of field values.
 */
export const FieldPolicySchema = z
  .object({
    action: FieldActionSchema.default('allow'),
    maskPattern: z
      .string()
      .optional()
      .describe("Pattern for masking (e.g., '****{last4}' for credit cards)"),
  })
  .readonly();

export type FieldPolicy = z.infer<typeof FieldPolicySchema>;

/**
 * Custom redactor function type.
 */
export type CustomRedactor = (value: unknown) => unknown;

/**
 * Extended field policy with runtime redactor.
 */
export interface FieldPolicyWithRedactor extends FieldPolicy {
  customRedactor?: CustomRedactor;
}

/**
 * Policy for a relation/include.
 *
 * Controls which relations can be expanded and with what constraints.
 */
export const RelationPolicySchema = z
  .object({
    allowed: z.boolean().default(true),
    maxDepth: z.number().int().min(0).max(5).default(1),
    allowedFields: z
      .array(z.string())
      .optional()
      .describe('If set, only these fields can be selected from the relation'),
  })
  .readonly();

export type RelationPolicy = z.infer<typeof RelationPolicySchema>;

/**
 * Row-level security policy.
 *
 * Defines how rows are filtered based on the execution context.
 */
export const RowPolicySchema = z
  .object({
    /** Field used for tenant scoping (e.g., "tenantId") */
    tenantScopeField: z.string().optional(),

    /** Field used for ownership scoping (e.g., "userId", "ownerId") */
    ownershipScopeField: z.string().optional(),

    /** Whether scoping is required (if true, queries without scope will fail) */
    requireScope: z.boolean().default(true),

    /** Soft delete field (e.g., "deletedAt", "isDeleted") */
    softDeleteField: z.string().optional(),

    /** Whether to include soft-deleted records */
    includeSoftDeleted: z.boolean().default(false),
  })
  .readonly();

export type RowPolicy = z.infer<typeof RowPolicySchema>;

/**
 * Policy for write operations.
 */
export const WritePolicySchema = z
  .object({
    /** Whether writes are enabled at all */
    enabled: z.boolean().default(false),

    /** Whether create operations are allowed */
    allowCreate: z.boolean().default(false),

    /** Whether update operations are allowed */
    allowUpdate: z.boolean().default(false),

    /** Whether delete operations are allowed */
    allowDelete: z.boolean().default(false),

    /** Whether bulk operations are allowed */
    allowBulk: z.boolean().default(false),

    /** Whether updates require primary key */
    requirePrimaryKey: z.boolean().default(true),

    /** Whether soft delete is the default delete behavior */
    softDelete: z.boolean().default(true),

    /** Maximum rows that can be affected by a single operation */
    maxAffectedRows: z.number().int().min(1).max(1000).default(1),

    /** Whether a reason is required for writes */
    requireReason: z.boolean().default(true),

    /** Whether human approval is required */
    requireApproval: z.boolean().default(false),

    /** Fields that cannot be written to */
    readonlyFields: z.array(z.string()).default([]),
  })
  .readonly();

export type WritePolicy = z.infer<typeof WritePolicySchema>;

/**
 * Resource budget for queries.
 *
 * Limits query complexity to prevent runaway operations.
 */
export const BudgetSchema = z
  .object({
    /** Maximum rows to return */
    maxRows: z.number().int().min(1).max(10000).default(100),

    /** Maximum depth for relation includes */
    maxIncludesDepth: z.number().int().min(0).max(5).default(1),

    /** Maximum number of fields that can be selected */
    maxSelectFields: z.number().int().min(1).max(200).default(40),

    /** Query timeout in milliseconds */
    statementTimeoutMs: z.number().int().min(100).max(30000).default(2000),

    /** Maximum complexity score (if scoring is enabled) */
    maxComplexityScore: z.number().int().min(1).default(100),

    /** Whether to enable broad query guard (block unfiltered queries on large tables) */
    broadQueryGuard: z.boolean().default(true),

    /** Minimum filters required to bypass broad query guard */
    minFiltersForBroadQuery: z.number().int().min(0).default(1),
  })
  .readonly();

export type Budget = z.infer<typeof BudgetSchema>;

/**
 * Complete policy for a single model.
 */
export const ModelPolicySchema = z
  .object({
    /** Whether the model is accessible at all */
    allowed: z.boolean().default(true),

    /** Whether read operations are allowed */
    readable: z.boolean().default(true),

    /** Whether write operations are allowed */
    writable: z.boolean().default(false),

    /** Field-level policies (field name -> policy) */
    fields: z.record(FieldPolicySchema).default({}),

    /** Default field action for fields not in the fields dict */
    defaultFieldAction: FieldActionSchema.default('allow'),

    /** Relation policies (relation name -> policy) */
    relations: z.record(RelationPolicySchema).default({}),

    /** Row-level security policy */
    rowPolicy: RowPolicySchema.optional(),

    /** Write policy */
    writePolicy: WritePolicySchema.default({}),

    /** Budget overrides for this model */
    budget: BudgetSchema.optional(),

    /** Allowed operations for aggregations */
    allowedAggregations: z
      .array(z.string())
      .default(['count', 'sum', 'avg', 'min', 'max']),

    /** Fields that can be aggregated */
    aggregatableFields: z
      .array(z.string())
      .optional()
      .describe('If set, only these fields can be aggregated'),
  })
  .readonly();

export type ModelPolicy = z.infer<typeof ModelPolicySchema>;

/**
 * Helper functions for ModelPolicy.
 */
export const ModelPolicyUtils = {
  /**
   * Get policy for a specific field, falling back to default.
   */
  getFieldPolicy(modelPolicy: ModelPolicy, field: string): FieldPolicy {
    if (field in modelPolicy.fields) {
      return modelPolicy.fields[field];
    }
    return { action: modelPolicy.defaultFieldAction };
  },

  /**
   * Check if a field is allowed (not denied).
   */
  isFieldAllowed(modelPolicy: ModelPolicy, field: string): boolean {
    const policy = ModelPolicyUtils.getFieldPolicy(modelPolicy, field);
    return policy.action !== 'deny';
  },

  /**
   * Get list of allowed fields from a list of all fields.
   */
  getAllowedFields(modelPolicy: ModelPolicy, allFields: string[]): string[] {
    return allFields.filter((f) => ModelPolicyUtils.isFieldAllowed(modelPolicy, f));
  },
};

/**
 * Complete policy configuration.
 *
 * The root policy object that contains all model policies and defaults.
 */
export const PolicySchema = z
  .object({
    /** Model-specific policies */
    models: z.record(ModelPolicySchema).default({}),

    /** Default budget applied to all models unless overridden */
    defaultBudget: BudgetSchema.default({}),

    /** Default row policy applied to all models unless overridden */
    defaultRowPolicy: RowPolicySchema.default({}),

    /** Global field patterns to deny (e.g., "*password*", "*secret*") */
    globalDenyPatterns: z.array(z.string()).default([]),

    /** Global field patterns to mask (e.g., "email", "phone") */
    globalMaskPatterns: z.array(z.string()).default([]),

    /** Whether to require tenant scope by default */
    requireTenantScope: z.boolean().default(true),

    /** Whether writes are enabled globally */
    writesEnabled: z.boolean().default(false),
  })
  .readonly();

export type Policy = z.infer<typeof PolicySchema>;

/**
 * Helper functions for Policy.
 */
export const PolicyUtils = {
  /**
   * Get policy for a specific model.
   */
  getModelPolicy(policy: Policy, model: string): ModelPolicy | undefined {
    return policy.models[model];
  },

  /**
   * Get budget for a model, falling back to default.
   */
  getBudget(policy: Policy, model: string): Budget {
    const modelPolicy = policy.models[model];
    if (modelPolicy?.budget) {
      return modelPolicy.budget;
    }
    return policy.defaultBudget;
  },

  /**
   * Get row policy for a model, falling back to default.
   */
  getRowPolicy(policy: Policy, model: string): RowPolicy {
    const modelPolicy = policy.models[model];
    if (modelPolicy?.rowPolicy) {
      return modelPolicy.rowPolicy;
    }
    return policy.defaultRowPolicy;
  },

  /**
   * Check if a model is allowed.
   */
  isModelAllowed(policy: Policy, model: string): boolean {
    const modelPolicy = policy.models[model];
    return modelPolicy !== undefined && modelPolicy.allowed;
  },

  /**
   * List all allowed model names.
   */
  listAllowedModels(policy: Policy): string[] {
    return Object.entries(policy.models)
      .filter(([, p]) => p.allowed)
      .map(([name]) => name);
  },
};

/**
 * Default budget values.
 */
export const DEFAULT_BUDGET: Budget = BudgetSchema.parse({});

/**
 * Default row policy values.
 */
export const DEFAULT_ROW_POLICY: RowPolicy = RowPolicySchema.parse({});

/**
 * Default write policy values.
 */
export const DEFAULT_WRITE_POLICY: WritePolicy = WritePolicySchema.parse({});
