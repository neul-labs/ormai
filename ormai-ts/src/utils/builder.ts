/**
 * Policy builder for constructing policies programmatically.
 */

import type {
  Budget,
  FieldAction,
  FieldPolicy,
  ModelPolicy,
  Policy,
  RelationPolicy,
  RowPolicy,
  WritePolicy,
} from '../policy/models.js';
import { BudgetSchema, PolicySchema, RowPolicySchema, WritePolicySchema } from '../policy/models.js';
import type { DefaultsProfile } from './defaults.js';
import { budgetFromProfile, getDefaultsProfile, writePolicyFromProfile } from './defaults.js';

/**
 * Mutable version of a type (removes readonly).
 */
type Mutable<T> = {
  -readonly [P in keyof T]: T[P];
};

/**
 * Mutable ModelPolicy for builder use.
 */
type MutableModelPolicy = Mutable<ModelPolicy> & {
  fields?: Record<string, Mutable<FieldPolicy>>;
  relations?: Record<string, Mutable<RelationPolicy>>;
  rowPolicy?: Mutable<RowPolicy>;
  writePolicy?: Mutable<WritePolicy>;
  budget?: Mutable<Budget>;
};

/**
 * Builder for constructing policies.
 */
export class PolicyBuilder {
  private models: Record<string, Partial<MutableModelPolicy>> = {};
  private defaultBudget: Mutable<Budget>;
  private defaultRowPolicy: Partial<Mutable<RowPolicy>> = {};
  private globalDenyPatterns: string[] = [];
  private globalMaskPatterns: string[] = [];
  private requireTenantScope: boolean;
  private writesEnabled: boolean;
  private profile: DefaultsProfile;

  constructor(mode: DefaultsProfile['mode'] = 'prod') {
    this.profile = getDefaultsProfile(mode);
    this.defaultBudget = budgetFromProfile(this.profile);
    this.requireTenantScope = this.profile.requireTenantScope;
    this.writesEnabled = this.profile.writesEnabled;
  }

  /**
   * Register models with default policies.
   */
  registerModels(models: string[]): this {
    for (const model of models) {
      if (!this.models[model]) {
        this.models[model] = {
          allowed: true,
          readable: true,
          writable: this.writesEnabled,
        };
      }
    }
    return this;
  }

  /**
   * Configure a specific model.
   */
  model(name: string, config: Partial<ModelPolicy>): this {
    this.models[name] = { ...this.models[name], ...config };
    return this;
  }

  /**
   * Set field policy for a model.
   */
  field(model: string, field: string, policy: Partial<FieldPolicy>): this {
    if (!this.models[model]) {
      this.models[model] = { allowed: true };
    }
    if (!this.models[model].fields) {
      this.models[model].fields = {};
    }
    this.models[model].fields![field] = { action: 'allow', ...policy };
    return this;
  }

  /**
   * Deny fields matching a glob pattern globally.
   */
  denyFields(pattern: string): this {
    this.globalDenyPatterns.push(pattern);
    return this;
  }

  /**
   * Mask fields matching a glob pattern globally.
   */
  maskFields(pattern: string): this {
    this.globalMaskPatterns.push(pattern);
    return this;
  }

  /**
   * Set default field action for a model.
   */
  defaultFieldAction(model: string, action: FieldAction): this {
    if (!this.models[model]) {
      this.models[model] = { allowed: true };
    }
    this.models[model].defaultFieldAction = action;
    return this;
  }

  /**
   * Allow relations for a model.
   */
  allowRelations(model: string, relations: string[]): this {
    if (!this.models[model]) {
      this.models[model] = { allowed: true };
    }
    if (!this.models[model].relations) {
      this.models[model].relations = {};
    }
    for (const rel of relations) {
      this.models[model].relations![rel] = { allowed: true, maxDepth: 1 };
    }
    return this;
  }

  /**
   * Configure relation policy.
   */
  relation(model: string, relation: string, policy: Partial<RelationPolicy>): this {
    if (!this.models[model]) {
      this.models[model] = { allowed: true };
    }
    if (!this.models[model].relations) {
      this.models[model].relations = {};
    }
    this.models[model].relations![relation] = { allowed: true, maxDepth: 1, ...policy };
    return this;
  }

  /**
   * Set tenant scope field for a model or all models.
   */
  tenantScope(field: string, model?: string): this {
    if (model) {
      if (!this.models[model]) {
        this.models[model] = { allowed: true };
      }
      const basePolicy = RowPolicySchema.parse({});
      this.models[model].rowPolicy = {
        ...basePolicy,
        ...this.models[model].rowPolicy,
        tenantScopeField: field,
      };
    } else {
      this.defaultRowPolicy.tenantScopeField = field;
    }
    return this;
  }

  /**
   * Set ownership scope field for a model or all models.
   */
  ownershipScope(field: string, model?: string): this {
    if (model) {
      if (!this.models[model]) {
        this.models[model] = { allowed: true };
      }
      const basePolicy = RowPolicySchema.parse({});
      this.models[model].rowPolicy = {
        ...basePolicy,
        ...this.models[model].rowPolicy,
        ownershipScopeField: field,
      };
    } else {
      this.defaultRowPolicy.ownershipScopeField = field;
    }
    return this;
  }

  /**
   * Set soft delete field for a model or all models.
   */
  softDelete(field: string, model?: string): this {
    if (model) {
      if (!this.models[model]) {
        this.models[model] = { allowed: true };
      }
      const basePolicy = RowPolicySchema.parse({});
      this.models[model].rowPolicy = {
        ...basePolicy,
        ...this.models[model].rowPolicy,
        softDeleteField: field,
      };
    } else {
      this.defaultRowPolicy.softDeleteField = field;
    }
    return this;
  }

  /**
   * Enable writes for specific models.
   */
  enableWrites(models: string[], config?: Partial<WritePolicy>): this {
    const writePolicy = writePolicyFromProfile(this.profile);
    const finalWritePolicy = {
      ...writePolicy,
      enabled: true,
      allowCreate: true,
      allowUpdate: true,
      allowDelete: true,
      ...config,
    };

    for (const model of models) {
      if (!this.models[model]) {
        this.models[model] = { allowed: true };
      }
      this.models[model].writable = true;
      this.models[model].writePolicy = finalWritePolicy;
    }
    return this;
  }

  /**
   * Set custom budget for a model.
   */
  budget(model: string, budget: Partial<Budget>): this {
    if (!this.models[model]) {
      this.models[model] = { allowed: true };
    }
    this.models[model].budget = BudgetSchema.parse({ ...this.defaultBudget, ...budget });
    return this;
  }

  /**
   * Set default budget for all models.
   */
  defaultBudgetConfig(budget: Partial<Budget>): this {
    this.defaultBudget = BudgetSchema.parse({ ...this.defaultBudget, ...budget });
    return this;
  }

  /**
   * Configure requirement for tenant scope.
   */
  setRequireTenantScope(require: boolean): this {
    this.requireTenantScope = require;
    return this;
  }

  /**
   * Enable or disable writes globally.
   */
  setWritesEnabled(enabled: boolean): this {
    this.writesEnabled = enabled;
    return this;
  }

  /**
   * Build the final policy.
   */
  build(): Policy {
    const models: Record<string, ModelPolicy> = {};

    for (const [name, config] of Object.entries(this.models)) {
      models[name] = {
        allowed: config.allowed ?? true,
        readable: config.readable ?? true,
        writable: config.writable ?? this.writesEnabled,
        fields: config.fields ?? {},
        defaultFieldAction: config.defaultFieldAction ?? 'allow',
        relations: config.relations ?? {},
        rowPolicy: config.rowPolicy,
        writePolicy: config.writePolicy ?? WritePolicySchema.parse({}),
        budget: config.budget,
        allowedAggregations: config.allowedAggregations ?? ['count', 'sum', 'avg', 'min', 'max'],
        aggregatableFields: config.aggregatableFields,
      };
    }

    return PolicySchema.parse({
      models,
      defaultBudget: this.defaultBudget,
      defaultRowPolicy: this.defaultRowPolicy,
      globalDenyPatterns: this.globalDenyPatterns,
      globalMaskPatterns: this.globalMaskPatterns,
      requireTenantScope: this.requireTenantScope,
      writesEnabled: this.writesEnabled,
    });
  }
}

/**
 * Create a new policy builder.
 */
export function createPolicyBuilder(mode: DefaultsProfile['mode'] = 'prod'): PolicyBuilder {
  return new PolicyBuilder(mode);
}
