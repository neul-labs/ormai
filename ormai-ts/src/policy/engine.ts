/**
 * Policy evaluation engine.
 *
 * The PolicyEngine is the central point for policy evaluation. It validates
 * requests against policies and provides decisions for query compilation.
 */

import type { RunContext } from '../core/context.js';
import type {
  AggregateRequest,
  BulkUpdateRequest,
  CreateRequest,
  DeleteRequest,
  FilterClause,
  GetRequest,
  IncludeClause,
  QueryRequest,
  UpdateRequest,
} from '../core/dsl.js';
import {
  FieldNotAllowedError,
  MaxAffectedRowsExceededError,
  ModelNotAllowedError,
  QueryBudgetExceededError,
  QueryTooBroadError,
  RelationNotAllowedError,
  TenantScopeRequiredError,
  ValidationError,
  WriteDisabledError,
} from '../core/errors.js';
import type { SchemaMetadata } from '../core/types.js';
import type { Budget, ModelPolicy, Policy, RowPolicy, WritePolicy } from './models.js';
import { ModelPolicyUtils, PolicyUtils } from './models.js';
import { createScopeInjector } from './scoping.js';

/**
 * Result of policy evaluation.
 *
 * Contains all decisions made during policy evaluation that need to be
 * applied during query compilation or result processing.
 */
export class PolicyDecision {
  /** Fields that are allowed to be selected */
  allowedFields: string[] = [];

  /** Filters to inject into the query (for scoping) */
  injectedFilters: FilterClause[] = [];

  /** Redaction rules to apply to results (field -> action) */
  redactionRules: Record<string, string> = {};

  /** Budget for this query */
  budget: Budget | null = null;

  /** Audit log of decisions made */
  decisions: string[] = [];

  /**
   * Add a decision to the audit log.
   */
  addDecision(decision: string): void {
    this.decisions.push(decision);
  }
}

/**
 * Evaluates policies against requests.
 *
 * The engine performs:
 * 1. Model access validation
 * 2. Field access validation
 * 3. Relation access validation
 * 4. Scope requirement validation
 * 5. Budget validation
 * 6. Generates policy decisions for query compilation
 */
export class PolicyEngine {
  constructor(
    private readonly policy: Policy,
    private readonly schema: SchemaMetadata
  ) {}

  /**
   * Validate a query request against policies.
   *
   * Raises appropriate errors if the request violates any policy.
   * Returns a PolicyDecision with all decisions for query compilation.
   */
  validateQuery(request: QueryRequest, ctx: RunContext): PolicyDecision {
    const decision = new PolicyDecision();

    // 1. Validate model access
    const modelPolicy = this.validateModelAccess(request.model, { readable: true });
    decision.addDecision(`Model '${request.model}' access validated`);

    // 2. Get and validate budget
    const budget = PolicyUtils.getBudget(this.policy, request.model);
    decision.budget = budget;
    this.validateBudget(request, budget);
    decision.addDecision(`Budget validated: maxRows=${budget.maxRows}`);

    // 3. Validate and filter fields
    const schemaModel = this.schema.models[request.model];
    const allFields = schemaModel ? Object.keys(schemaModel.fields) : [];

    if (request.select) {
      decision.allowedFields = this.validateFields(
        request.select,
        request.model,
        modelPolicy,
        allFields
      );
    } else {
      decision.allowedFields = ModelPolicyUtils.getAllowedFields(modelPolicy, allFields);
    }
    decision.addDecision(`Selected ${decision.allowedFields.length} fields`);

    // 4. Validate relations/includes
    if (request.include) {
      this.validateIncludes(request.include, request.model, modelPolicy, budget);
      decision.addDecision(`Validated ${request.include.length} includes`);
    }

    // 5. Validate and inject scoping
    const rowPolicy = PolicyUtils.getRowPolicy(this.policy, request.model);
    const scopeFilters = this.validateAndGetScopeFilters(
      request.model,
      rowPolicy,
      ctx,
      request.where
    );
    decision.injectedFilters.push(...scopeFilters);
    if (scopeFilters.length > 0) {
      decision.addDecision(`Injected ${scopeFilters.length} scope filters`);
    }

    // 6. Check broad query guard
    if (budget.broadQueryGuard) {
      this.validateQueryBreadth(request, budget, scopeFilters);
      decision.addDecision('Broad query guard passed');
    }

    // 7. Collect redaction rules
    for (const field of decision.allowedFields) {
      const fieldPolicy = ModelPolicyUtils.getFieldPolicy(modelPolicy, field);
      if (fieldPolicy.action !== 'allow') {
        decision.redactionRules[field] = fieldPolicy.action;
      }
    }

    return decision;
  }

  /**
   * Validate a get-by-id request.
   */
  validateGet(request: GetRequest, ctx: RunContext): PolicyDecision {
    const decision = new PolicyDecision();

    // Validate model access
    const modelPolicy = this.validateModelAccess(request.model, { readable: true });
    decision.addDecision(`Model '${request.model}' access validated`);

    // Get budget
    const budget = PolicyUtils.getBudget(this.policy, request.model);
    decision.budget = budget;

    // Validate fields
    const schemaModel = this.schema.models[request.model];
    const allFields = schemaModel ? Object.keys(schemaModel.fields) : [];

    if (request.select) {
      decision.allowedFields = this.validateFields(
        request.select,
        request.model,
        modelPolicy,
        allFields
      );
    } else {
      decision.allowedFields = ModelPolicyUtils.getAllowedFields(modelPolicy, allFields);
    }

    // Validate includes
    if (request.include) {
      this.validateIncludes(request.include, request.model, modelPolicy, budget);
    }

    // Inject scope filters
    const rowPolicy = PolicyUtils.getRowPolicy(this.policy, request.model);
    decision.injectedFilters = this.validateAndGetScopeFilters(
      request.model,
      rowPolicy,
      ctx,
      undefined
    );

    return decision;
  }

  /**
   * Validate an aggregation request.
   */
  validateAggregate(request: AggregateRequest, ctx: RunContext): PolicyDecision {
    const decision = new PolicyDecision();

    // Validate model access
    const modelPolicy = this.validateModelAccess(request.model, { readable: true });
    decision.addDecision(`Model '${request.model}' access validated`);

    // Validate operation is allowed
    if (!modelPolicy.allowedAggregations.includes(request.operation)) {
      throw new FieldNotAllowedError(
        `aggregation:${request.operation}`,
        request.model,
        modelPolicy.allowedAggregations
      );
    }

    // Validate field is aggregatable (for non-count operations)
    if (request.field && request.operation !== 'count') {
      if (
        modelPolicy.aggregatableFields !== undefined &&
        !modelPolicy.aggregatableFields.includes(request.field)
      ) {
        throw new FieldNotAllowedError(
          request.field,
          request.model,
          modelPolicy.aggregatableFields
        );
      }
      // Also check regular field policy
      if (!ModelPolicyUtils.isFieldAllowed(modelPolicy, request.field)) {
        throw new FieldNotAllowedError(request.field, request.model, []);
      }
    }

    // Get budget
    decision.budget = PolicyUtils.getBudget(this.policy, request.model);

    // Inject scope filters
    const rowPolicy = PolicyUtils.getRowPolicy(this.policy, request.model);
    decision.injectedFilters = this.validateAndGetScopeFilters(
      request.model,
      rowPolicy,
      ctx,
      request.where
    );

    return decision;
  }

  /**
   * Validate a create request against policies.
   */
  validateCreate(request: CreateRequest, ctx: RunContext): PolicyDecision {
    // 1. Validate model access (writable)
    const modelPolicy = this.validateModelAccess(request.model, { writable: true });

    // 2. Validate write policy (common)
    const { decision, writePolicy, rowPolicy } = this.validateWritePolicy(
      request,
      ctx,
      'create',
      modelPolicy
    );

    // 3. Validate fields being written
    const schemaModel = this.schema.models[request.model];
    const allFields = schemaModel ? Object.keys(schemaModel.fields) : [];
    const writableFields = this.getWritableFields(allFields, modelPolicy);

    for (const field of Object.keys(request.data)) {
      if (writePolicy.readonlyFields.includes(field)) {
        throw new FieldNotAllowedError(field, request.model, writableFields);
      }
    }
    decision.addDecision(`Validated ${Object.keys(request.data).length} fields for write`);

    // 4. Get return fields
    if (request.returnFields) {
      decision.allowedFields = this.validateFields(
        request.returnFields,
        request.model,
        modelPolicy,
        allFields
      );
    } else {
      decision.allowedFields = ModelPolicyUtils.getAllowedFields(modelPolicy, allFields);
    }

    // 5. Inject scope data (tenant_id to be set on created record)
    decision.injectedFilters = this.validateAndGetScopeFilters(
      request.model,
      rowPolicy,
      ctx
    );

    return decision;
  }

  /**
   * Validate an update request against policies.
   */
  validateUpdate(request: UpdateRequest, ctx: RunContext): PolicyDecision {
    // 1. Validate model access (writable)
    const modelPolicy = this.validateModelAccess(request.model, { writable: true });

    // 2. Validate write policy (common)
    const { decision, writePolicy, rowPolicy } = this.validateWritePolicy(
      request,
      ctx,
      'update',
      modelPolicy
    );

    // 3. Validate fields being updated
    const schemaModel = this.schema.models[request.model];
    const allFields = schemaModel ? Object.keys(schemaModel.fields) : [];
    const writableFields = this.getWritableFields(allFields, modelPolicy);

    for (const field of Object.keys(request.data)) {
      if (writePolicy.readonlyFields.includes(field)) {
        throw new FieldNotAllowedError(field, request.model, writableFields);
      }
    }
    decision.addDecision(`Validated ${Object.keys(request.data).length} fields for update`);

    // 4. Get return fields
    if (request.returnFields) {
      decision.allowedFields = this.validateFields(
        request.returnFields,
        request.model,
        modelPolicy,
        allFields
      );
    } else {
      decision.allowedFields = ModelPolicyUtils.getAllowedFields(modelPolicy, allFields);
    }

    // 5. Inject scope filters (to ensure update is scoped)
    decision.injectedFilters = this.validateAndGetScopeFilters(
      request.model,
      rowPolicy,
      ctx
    );

    return decision;
  }

  /**
   * Validate a delete request against policies.
   */
  validateDelete(request: DeleteRequest, ctx: RunContext): PolicyDecision {
    const decision = new PolicyDecision();

    // 1. Validate model access (writable)
    const modelPolicy = this.validateModelAccess(request.model, { writable: true });
    decision.addDecision(`Model '${request.model}' write access validated`);

    // 2. Check write policy
    const writePolicy = modelPolicy.writePolicy;
    if (!writePolicy.enabled) {
      throw new WriteDisabledError('delete', request.model);
    }
    if (!writePolicy.allowDelete) {
      throw new WriteDisabledError('delete', request.model);
    }
    decision.addDecision('Delete operation allowed by policy');

    // 3. Check reason requirement
    if (writePolicy.requireReason && !request.reason) {
      throw new ValidationError('A reason is required for this delete operation', 'reason');
    }

    // 4. If hard delete requested, check if allowed
    if (request.hard && writePolicy.softDelete) {
      throw new ValidationError('Hard delete is not allowed; use soft delete instead');
    }

    // 5. Validate return fields (if requested)
    const schemaModel = this.schema.models[request.model];
    const allFields = schemaModel ? Object.keys(schemaModel.fields) : [];
    if (request.returnFields) {
      decision.allowedFields = this.validateFields(
        request.returnFields,
        request.model,
        modelPolicy,
        allFields
      );
    } else {
      decision.allowedFields = ModelPolicyUtils.getAllowedFields(modelPolicy, allFields);
    }
    decision.addDecision(`Validated ${decision.allowedFields.length} return fields`);

    // 6. Inject scope filters
    const rowPolicy = PolicyUtils.getRowPolicy(this.policy, request.model);
    decision.injectedFilters = this.validateAndGetScopeFilters(
      request.model,
      rowPolicy,
      ctx
    );

    decision.budget = PolicyUtils.getBudget(this.policy, request.model);
    return decision;
  }

  /**
   * Validate a bulk update request against policies.
   */
  validateBulkUpdate(request: BulkUpdateRequest, ctx: RunContext): PolicyDecision {
    // 1. Validate model access (writable)
    const modelPolicy = this.validateModelAccess(request.model, { writable: true });

    // 2. Validate write policy (common)
    const { decision, writePolicy, rowPolicy } = this.validateWritePolicy(
      request,
      ctx,
      'bulk_update',
      modelPolicy
    );

    // 3. Validate fields being updated
    const schemaModel = this.schema.models[request.model];
    const allFields = schemaModel ? Object.keys(schemaModel.fields) : [];
    const writableFields = this.getWritableFields(allFields, modelPolicy);

    for (const field of Object.keys(request.data)) {
      if (writePolicy.readonlyFields.includes(field)) {
        throw new FieldNotAllowedError(field, request.model, writableFields);
      }
    }

    // 4. Inject scope filters
    decision.injectedFilters = this.validateAndGetScopeFilters(
      request.model,
      rowPolicy,
      ctx
    );

    return decision;
  }

  // =========================================================================
  // PRIVATE HELPER METHODS
  // =========================================================================

  /**
   * Validate that a model is accessible.
   */
  private validateModelAccess(
    model: string,
    opts: { readable?: boolean; writable?: boolean } = {}
  ): ModelPolicy {
    const modelPolicy = PolicyUtils.getModelPolicy(this.policy, model);

    if (modelPolicy === undefined) {
      throw new ModelNotAllowedError(model, PolicyUtils.listAllowedModels(this.policy));
    }

    if (!modelPolicy.allowed) {
      throw new ModelNotAllowedError(model, PolicyUtils.listAllowedModels(this.policy));
    }

    if (opts.readable && !modelPolicy.readable) {
      throw new ModelNotAllowedError(
        model,
        Object.entries(this.policy.models)
          .filter(([, p]) => p.allowed && p.readable)
          .map(([m]) => m)
      );
    }

    if (opts.writable && !modelPolicy.writable) {
      throw new ModelNotAllowedError(
        model,
        Object.entries(this.policy.models)
          .filter(([, p]) => p.allowed && p.writable)
          .map(([m]) => m)
      );
    }

    return modelPolicy;
  }

  /**
   * Validate field access and return allowed fields.
   */
  private validateFields(
    fields: string[],
    model: string,
    modelPolicy: ModelPolicy,
    allFields: string[]
  ): string[] {
    const allowed: string[] = [];

    for (const field of fields) {
      if (!allFields.includes(field)) {
        throw new FieldNotAllowedError(field, model, allFields);
      }
      if (!ModelPolicyUtils.isFieldAllowed(modelPolicy, field)) {
        throw new FieldNotAllowedError(
          field,
          model,
          ModelPolicyUtils.getAllowedFields(modelPolicy, allFields)
        );
      }
      allowed.push(field);
    }

    return allowed;
  }

  /**
   * Validate relation includes.
   */
  private validateIncludes(
    includes: readonly IncludeClause[],
    model: string,
    modelPolicy: ModelPolicy,
    budget: Budget
  ): void {
    if (includes.length > budget.maxIncludesDepth) {
      throw new QueryBudgetExceededError('includes', budget.maxIncludesDepth, includes.length);
    }

    const schemaModel = this.schema.models[model];
    const availableRelations = schemaModel ? Object.keys(schemaModel.relations) : [];

    for (const include of includes) {
      // Check relation exists
      if (schemaModel && !(include.relation in schemaModel.relations)) {
        throw new RelationNotAllowedError(include.relation, model, availableRelations);
      }

      // Check relation policy
      const relationPolicy = modelPolicy.relations[include.relation];
      if (relationPolicy === undefined || !relationPolicy.allowed) {
        const allowedRelations = Object.entries(modelPolicy.relations)
          .filter(([, p]) => p.allowed)
          .map(([r]) => r);
        throw new RelationNotAllowedError(
          include.relation,
          model,
          allowedRelations.length > 0 ? allowedRelations : availableRelations
        );
      }
    }
  }

  /**
   * Validate scoping requirements and return scope filters to inject.
   */
  private validateAndGetScopeFilters(
    model: string,
    rowPolicy: RowPolicy,
    ctx: RunContext
  ): FilterClause[] {
    // Use ScopeInjector for filter generation
    const scopeInjector = createScopeInjector(rowPolicy);
    const filters = scopeInjector.getScopeFilters(ctx);

    // Check tenant scope requirement
    if (rowPolicy.tenantScopeField && this.policy.requireTenantScope && !ctx.principal.tenantId) {
      throw new TenantScopeRequiredError(model, rowPolicy.tenantScopeField);
    }

    return filters;
  }

  /**
   * Validate request against budget limits.
   */
  private validateBudget(request: QueryRequest, budget: Budget): void {
    // Check row limit
    if (request.take > budget.maxRows) {
      throw new QueryBudgetExceededError('rows', budget.maxRows, request.take);
    }

    // Check field count
    if (request.select && request.select.length > budget.maxSelectFields) {
      throw new QueryBudgetExceededError('fields', budget.maxSelectFields, request.select.length);
    }

    // Check include depth
    if (request.include && request.include.length > budget.maxIncludesDepth) {
      throw new QueryBudgetExceededError('includes', budget.maxIncludesDepth, request.include.length);
    }
  }

  /**
   * Validate that the query isn't too broad (broad query guard).
   */
  private validateQueryBreadth(
    request: QueryRequest,
    budget: Budget,
    scopeFilters: FilterClause[]
  ): void {
    let totalFilters = scopeFilters.length;
    if (request.where) {
      totalFilters += request.where.length;
    }

    if (totalFilters < budget.minFiltersForBroadQuery) {
      throw new QueryTooBroadError(
        request.model,
        `Add at least ${budget.minFiltersForBroadQuery} filter(s) to narrow the query`
      );
    }
  }

  /**
   * Validate write policy and return common write validation result.
   * This is used by validateCreate, validateUpdate, and validateBulkUpdate.
   */
  private validateWritePolicy(
    request: CreateRequest | UpdateRequest | BulkUpdateRequest,
    ctx: RunContext,
    operation: 'create' | 'update' | 'bulk_update',
    modelPolicy: ModelPolicy
  ): { decision: PolicyDecision; writePolicy: WritePolicy; rowPolicy: RowPolicy } {
    const decision = new PolicyDecision();
    decision.addDecision(`Model '${request.model}' write access validated`);

    const writePolicy = modelPolicy.writePolicy;

    // Check if writes are enabled
    if (!writePolicy.enabled) {
      throw new WriteDisabledError(operation, request.model);
    }

    // Check specific operation permission
    switch (operation) {
      case 'create':
        if (!writePolicy.allowCreate) {
          throw new WriteDisabledError('create', request.model);
        }
        break;
      case 'update':
        if (!writePolicy.allowUpdate) {
          throw new WriteDisabledError('update', request.model);
        }
        break;
      case 'bulk_update':
        if (!writePolicy.allowUpdate || !writePolicy.allowBulk) {
          throw new WriteDisabledError('bulk_update', request.model);
        }
        break;
    }
    decision.addDecision(`${operation} operation allowed by policy`);

    // Check reason requirement
    if (writePolicy.requireReason && !request.reason) {
      throw new ValidationError(`A reason is required for this ${operation} operation`, 'reason');
    }

    // For bulk update, check max affected rows
    if (operation === 'bulk_update') {
      if (request.ids.length > writePolicy.maxAffectedRows) {
        throw new MaxAffectedRowsExceededError(
          'bulk_update',
          writePolicy.maxAffectedRows,
          request.ids.length
        );
      }
      decision.addDecision(`Bulk update size validated: ${request.ids.length} rows`);
    }

    const rowPolicy = PolicyUtils.getRowPolicy(this.policy, request.model);
    decision.budget = PolicyUtils.getBudget(this.policy, request.model);

    return { decision, writePolicy, rowPolicy };
  }

  /**
   * Get list of fields that can be written to.
   */
  private getWritableFields(allFields: string[], modelPolicy: ModelPolicy): string[] {
    const readonly = new Set(modelPolicy.writePolicy.readonlyFields);
    return allFields.filter((f) => !readonly.has(f));
  }
}
