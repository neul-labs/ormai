/**
 * Factory functions for creating OrmAI toolsets.
 */

import type { OrmAdapter } from '../adapters/base.js';
import type { SchemaMetadata } from '../core/types.js';
import type { Policy } from '../policy/models.js';
import { ToolRegistry } from '../tools/base.js';
import { createGenericTools } from '../tools/generic.js';
import type { DefaultsProfile } from './defaults.js';
import { PolicyBuilder } from './builder.js';

/**
 * Options for creating a toolset.
 */
export interface ToolsetFactoryOptions<DB> {
  /** ORM adapter */
  adapter: OrmAdapter<DB>;

  /** Policy to apply */
  policy: Policy;

  /** Schema metadata */
  schema: SchemaMetadata;

  /** Whether to include write tools */
  includeWriteTools?: boolean;
}

/**
 * Create a toolset from policy and adapter.
 */
export function createToolset<DB>(options: ToolsetFactoryOptions<DB>): ToolRegistry {
  const { adapter, policy, schema, includeWriteTools = false } = options;

  const registry = new ToolRegistry();
  const tools = createGenericTools({
    adapter: adapter as OrmAdapter,
    policy,
    schema,
    includeWrite: includeWriteTools || policy.writesEnabled,
  });

  for (const tool of tools) {
    registry.register(tool);
  }

  return registry;
}

/**
 * Options for quick setup.
 */
export interface QuickSetupOptions<DB> {
  /** ORM adapter */
  adapter: OrmAdapter<DB>;

  /** Model names to expose */
  models: string[];

  /** Profile mode */
  mode?: DefaultsProfile['mode'];

  /** Tenant scope field */
  tenantScopeField?: string;

  /** Models with write access */
  writableModels?: string[];

  /** Relations to allow (model -> relations) */
  relations?: Record<string, string[]>;
}

/**
 * Quick setup for common use cases.
 */
export async function quickSetup<DB>(options: QuickSetupOptions<DB>): Promise<{
  policy: Policy;
  schema: SchemaMetadata;
  registry: ToolRegistry;
}> {
  const {
    adapter,
    models,
    mode = 'prod',
    tenantScopeField,
    writableModels = [],
    relations = {},
  } = options;

  // Introspect schema
  const schema = await adapter.introspect();

  // Build policy
  const builder = new PolicyBuilder(mode).registerModels(models);

  if (tenantScopeField) {
    builder.tenantScope(tenantScopeField);
  }

  for (const [model, rels] of Object.entries(relations)) {
    builder.allowRelations(model, rels);
  }

  if (writableModels.length > 0) {
    builder.enableWrites(writableModels);
  }

  const policy = builder.build();

  // Create toolset
  const registry = createToolset({
    adapter,
    policy,
    schema,
    includeWriteTools: writableModels.length > 0,
  });

  return { policy, schema, registry };
}

/**
 * Options for view factory.
 */
export interface ViewFactoryOptions {
  /** Base policy to extend */
  basePolicy: Policy;

  /** Schema metadata */
  schema: SchemaMetadata;

  /** Additional restrictions */
  restrictions?: {
    /** Models to allow (subset of base) */
    allowedModels?: string[];

    /** Fields to deny */
    denyFields?: Record<string, string[]>;

    /** Disable writes */
    disableWrites?: boolean;

    /** Lower budget limits */
    maxRows?: number;
  };
}

/**
 * Create a restricted view of an existing policy.
 */
export function createRestrictedView(options: ViewFactoryOptions): Policy {
  const { basePolicy, restrictions = {} } = options;
  const { allowedModels, denyFields = {}, disableWrites = false, maxRows } = restrictions;

  // Clone the base policy
  const models = { ...basePolicy.models };

  // Filter allowed models
  if (allowedModels) {
    for (const modelName of Object.keys(models)) {
      if (!allowedModels.includes(modelName)) {
        delete models[modelName];
      }
    }
  }

  // Apply field denials
  for (const [modelName, fields] of Object.entries(denyFields)) {
    if (models[modelName]) {
      const modelFields = { ...models[modelName].fields };
      for (const field of fields) {
        modelFields[field] = { action: 'deny' };
      }
      models[modelName] = { ...models[modelName], fields: modelFields };
    }
  }

  // Disable writes if requested
  if (disableWrites) {
    for (const modelName of Object.keys(models)) {
      models[modelName] = {
        ...models[modelName],
        writable: false,
        writePolicy: { ...models[modelName].writePolicy, enabled: false },
      };
    }
  }

  // Apply budget restrictions
  const defaultBudget = maxRows
    ? { ...basePolicy.defaultBudget, maxRows: Math.min(maxRows, basePolicy.defaultBudget.maxRows) }
    : basePolicy.defaultBudget;

  return {
    models,
    defaultBudget,
    defaultRowPolicy: basePolicy.defaultRowPolicy,
    globalDenyPatterns: basePolicy.globalDenyPatterns,
    globalMaskPatterns: basePolicy.globalMaskPatterns,
    requireTenantScope: basePolicy.requireTenantScope,
    writesEnabled: disableWrites ? false : basePolicy.writesEnabled,
  };
}
