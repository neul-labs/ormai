/**
 * Generic database tools.
 *
 * These are the core tools that provide structured access to the database.
 */

import { z } from 'zod';
import type { RunContext } from '../core/context.js';
import {
  type AggregateResult,
  type BulkUpdateResult,
  type CreateResult,
  type DeleteResult,
  type GetResult,
  type QueryResult,
  type UpdateResult,
  AggregateRequestSchema,
  BulkUpdateRequestSchema,
  CreateRequestSchema,
  DeleteRequestSchema,
  FilterClauseSchema,
  GetRequestSchema,
  IncludeClauseSchema,
  OrderClauseSchema,
  QueryRequestSchema,
  UpdateRequestSchema,
} from '../core/dsl.js';
import type { SchemaMetadata } from '../core/types.js';
import type { OrmAdapter } from '../adapters/base.js';
import type { Policy } from '../policy/models.js';
import { PolicyUtils, ModelPolicyUtils } from '../policy/models.js';
import { BaseTool } from './base.js';

// =============================================================================
// TOOL LIMITS
// =============================================================================

/**
 * Tool limits for configuring constraints.
 */
export interface ToolLimits {
  /** Maximum number of rows returned by query (default: 100) */
  maxQueryRows: number;
  /** Maximum number of IDs in bulk update (default: 100) */
  maxBulkUpdateIds: number;
  /** Maximum number of IDs in bulk delete (default: 100) */
  maxBulkDeleteIds: number;
}

/**
 * Default tool limits.
 */
export const DEFAULT_TOOL_LIMITS: ToolLimits = {
  maxQueryRows: 100,
  maxBulkUpdateIds: 100,
  maxBulkDeleteIds: 100,
};

// =============================================================================
// DESCRIBE SCHEMA TOOL
// =============================================================================

const DescribeSchemaInputSchema = z.object({
  model: z
    .string()
    .optional()
    .describe('Optional model name to get schema for. If not provided, returns all allowed models.'),
});

type DescribeSchemaInput = z.infer<typeof DescribeSchemaInputSchema>;

interface SchemaDescription {
  models: Record<string, ModelDescription>;
}

interface ModelDescription {
  table: string;
  fields: Record<string, FieldDescription>;
  relations: Record<string, RelationDescription>;
  readable: boolean;
  writable: boolean;
}

interface FieldDescription {
  type: string;
  nullable: boolean;
  primaryKey: boolean;
}

interface RelationDescription {
  target: string;
  type: string;
}

/**
 * Tool to describe the database schema.
 */
export class DescribeSchemaTool extends BaseTool<DescribeSchemaInput, SchemaDescription> {
  readonly name = 'db.describe_schema';
  readonly description = 'Get the database schema including allowed models, fields, and relations.';
  readonly inputSchema = DescribeSchemaInputSchema;

  constructor(
    private readonly schema: SchemaMetadata,
    private readonly policy: Policy
  ) {
    super();
  }

  async execute(input: DescribeSchemaInput, _ctx: RunContext): Promise<SchemaDescription> {
    const result: Record<string, ModelDescription> = {};

    if (input.model) {
      const modelMeta = this.schema.models[input.model];
      const modelPolicy = PolicyUtils.getModelPolicy(this.policy, input.model);

      if (modelMeta && modelPolicy?.allowed) {
        result[input.model] = this.describeModel(input.model, modelMeta, modelPolicy);
      }
    } else {
      for (const modelName of PolicyUtils.listAllowedModels(this.policy)) {
        const modelMeta = this.schema.models[modelName];
        const modelPolicy = PolicyUtils.getModelPolicy(this.policy, modelName);

        if (modelMeta && modelPolicy) {
          result[modelName] = this.describeModel(modelName, modelMeta, modelPolicy);
        }
      }
    }

    return { models: result };
  }

  private describeModel(
    _modelName: string,
    modelMeta: SchemaMetadata['models'][string],
    modelPolicy: NonNullable<ReturnType<typeof PolicyUtils.getModelPolicy>>
  ): ModelDescription {
    const fields: Record<string, FieldDescription> = {};
    for (const [fieldName, fieldMeta] of Object.entries(modelMeta.fields)) {
      if (ModelPolicyUtils.isFieldAllowed(modelPolicy, fieldName)) {
        fields[fieldName] = {
          type: fieldMeta.fieldType,
          nullable: fieldMeta.nullable,
          primaryKey: fieldMeta.primaryKey,
        };
      }
    }

    const relations: Record<string, RelationDescription> = {};
    for (const [relName, relMeta] of Object.entries(modelMeta.relations)) {
      const relPolicy = modelPolicy.relations[relName];
      if (!relPolicy || relPolicy.allowed) {
        relations[relName] = {
          target: relMeta.targetModel,
          type: relMeta.relationType,
        };
      }
    }

    return {
      table: modelMeta.tableName,
      fields,
      relations,
      readable: modelPolicy.readable,
      writable: modelPolicy.writable,
    };
  }
}

// =============================================================================
// QUERY TOOL
// =============================================================================

const QueryInputSchema = z.object({
  model: z.string().describe('The model to query'),
  select: z.array(z.string()).optional().describe('Fields to select (defaults to all allowed)'),
  where: z.array(z.record(z.unknown())).optional().describe('Filter conditions'),
  orderBy: z.array(z.record(z.unknown())).optional().describe('Sort order'),
  take: z.number().int().min(1).default(25).describe('Max rows to return'),
  cursor: z.string().optional().describe('Pagination cursor'),
  include: z.array(z.record(z.unknown())).optional().describe('Relations to include'),
});

type QueryInput = z.infer<typeof QueryInputSchema>;

/**
 * Tool to query database records.
 */
export class QueryTool extends BaseTool<QueryInput, QueryResult> {
  readonly name = 'db.query';
  readonly description = 'Query database records with filtering, ordering, and pagination.';
  readonly inputSchema = QueryInputSchema;

  constructor(
    private readonly adapter: OrmAdapter,
    private readonly policy: Policy,
    private readonly schema: SchemaMetadata,
    private readonly limits: ToolLimits = DEFAULT_TOOL_LIMITS
  ) {
    super();
  }

  async execute(input: QueryInput, ctx: RunContext): Promise<QueryResult> {
    // Validate take against limits
    if (input.take > this.limits.maxQueryRows) {
      throw new Error(`take value ${input.take} exceeds maximum of ${this.limits.maxQueryRows}`);
    }

    const request = QueryRequestSchema.parse({
      model: input.model,
      select: input.select,
      where: input.where?.map((f) => FilterClauseSchema.parse(f)),
      orderBy: input.orderBy?.map((o) => OrderClauseSchema.parse(o)),
      take: input.take,
      cursor: input.cursor,
      include: input.include?.map((i) => IncludeClauseSchema.parse(i)),
    });

    const compiled = this.adapter.compileQuery(request, ctx, this.policy, this.schema);
    return this.adapter.executeQuery(compiled, ctx);
  }
}

// =============================================================================
// GET TOOL
// =============================================================================

const GetInputSchema = z.object({
  model: z.string().describe('The model to get from'),
  id: z.unknown().describe('The primary key value'),
  select: z.array(z.string()).optional().describe('Fields to select'),
  include: z.array(z.record(z.unknown())).optional().describe('Relations to include'),
});

type GetInput = z.infer<typeof GetInputSchema>;

/**
 * Tool to get a single record by ID.
 */
export class GetTool extends BaseTool<GetInput, GetResult> {
  readonly name = 'db.get';
  readonly description = 'Get a single record by its primary key.';
  readonly inputSchema = GetInputSchema;

  constructor(
    private readonly adapter: OrmAdapter,
    private readonly policy: Policy,
    private readonly schema: SchemaMetadata
  ) {
    super();
  }

  async execute(input: GetInput, ctx: RunContext): Promise<GetResult> {
    const request = GetRequestSchema.parse({
      model: input.model,
      id: input.id,
      select: input.select,
      include: input.include?.map((i) => IncludeClauseSchema.parse(i)),
    });

    const compiled = this.adapter.compileGet(request, ctx, this.policy, this.schema);
    return this.adapter.executeGet(compiled, ctx);
  }
}

// =============================================================================
// AGGREGATE TOOL
// =============================================================================

const AggregateInputSchema = z.object({
  model: z.string().describe('The model to aggregate'),
  operation: z.enum(['count', 'sum', 'avg', 'min', 'max']).describe('Aggregation operation'),
  field: z.string().optional().describe('Field to aggregate (required for sum/avg/min/max)'),
  where: z.array(z.record(z.unknown())).optional().describe('Filter conditions'),
});

type AggregateInput = z.infer<typeof AggregateInputSchema>;

/**
 * Tool to perform aggregations.
 */
export class AggregateTool extends BaseTool<AggregateInput, AggregateResult> {
  readonly name = 'db.aggregate';
  readonly description = 'Perform aggregation operations (count, sum, avg, min, max).';
  readonly inputSchema = AggregateInputSchema;

  constructor(
    private readonly adapter: OrmAdapter,
    private readonly policy: Policy,
    private readonly schema: SchemaMetadata
  ) {
    super();
  }

  async execute(input: AggregateInput, ctx: RunContext): Promise<AggregateResult> {
    const request = AggregateRequestSchema.parse({
      model: input.model,
      operation: input.operation,
      field: input.field,
      where: input.where?.map((f) => FilterClauseSchema.parse(f)),
    });

    const compiled = this.adapter.compileAggregate(request, ctx, this.policy, this.schema);
    return this.adapter.executeAggregate(compiled, ctx);
  }
}

// =============================================================================
// CREATE TOOL
// =============================================================================

const CreateInputSchema = z.object({
  model: z.string().describe('The model to create'),
  data: z.record(z.unknown()).describe('Field values for the new record'),
  reason: z.string().optional().describe('Reason for the mutation'),
  returnFields: z.array(z.string()).optional().describe('Fields to return after creation'),
});

type CreateInput = z.infer<typeof CreateInputSchema>;

/**
 * Tool to create a new record.
 */
export class CreateTool extends BaseTool<CreateInput, CreateResult> {
  readonly name = 'db.create';
  readonly description = 'Create a new database record.';
  readonly inputSchema = CreateInputSchema;

  constructor(
    private readonly adapter: OrmAdapter,
    private readonly policy: Policy,
    private readonly schema: SchemaMetadata
  ) {
    super();
  }

  async execute(input: CreateInput, ctx: RunContext): Promise<CreateResult> {
    const request = CreateRequestSchema.parse({
      model: input.model,
      data: input.data,
      reason: input.reason,
      returnFields: input.returnFields,
    });

    const compiled = this.adapter.compileCreate(request, ctx, this.policy, this.schema);
    return this.adapter.executeCreate(compiled, ctx);
  }
}

// =============================================================================
// UPDATE TOOL
// =============================================================================

const UpdateInputSchema = z.object({
  model: z.string().describe('The model to update'),
  id: z.unknown().describe('The primary key of the record to update'),
  data: z.record(z.unknown()).describe('Fields to update'),
  reason: z.string().optional().describe('Reason for the mutation'),
  returnFields: z.array(z.string()).optional().describe('Fields to return after update'),
});

type UpdateInput = z.infer<typeof UpdateInputSchema>;

/**
 * Tool to update a record.
 */
export class UpdateTool extends BaseTool<UpdateInput, UpdateResult> {
  readonly name = 'db.update';
  readonly description = 'Update a database record by its primary key.';
  readonly inputSchema = UpdateInputSchema;

  constructor(
    private readonly adapter: OrmAdapter,
    private readonly policy: Policy,
    private readonly schema: SchemaMetadata
  ) {
    super();
  }

  async execute(input: UpdateInput, ctx: RunContext): Promise<UpdateResult> {
    const request = UpdateRequestSchema.parse({
      model: input.model,
      id: input.id,
      data: input.data,
      reason: input.reason,
      returnFields: input.returnFields,
    });

    const compiled = this.adapter.compileUpdate(request, ctx, this.policy, this.schema);
    return this.adapter.executeUpdate(compiled, ctx);
  }
}

// =============================================================================
// DELETE TOOL
// =============================================================================

const DeleteInputSchema = z.object({
  model: z.string().describe('The model to delete from'),
  id: z.unknown().describe('The primary key of the record to delete'),
  reason: z.string().optional().describe('Reason for the deletion'),
  hard: z.boolean().default(false).describe('If true, perform hard delete'),
});

type DeleteInput = z.infer<typeof DeleteInputSchema>;

/**
 * Tool to delete a record.
 */
export class DeleteTool extends BaseTool<DeleteInput, DeleteResult> {
  readonly name = 'db.delete';
  readonly description = 'Delete a database record (soft delete by default).';
  readonly inputSchema = DeleteInputSchema;

  constructor(
    private readonly adapter: OrmAdapter,
    private readonly policy: Policy,
    private readonly schema: SchemaMetadata
  ) {
    super();
  }

  async execute(input: DeleteInput, ctx: RunContext): Promise<DeleteResult> {
    const request = DeleteRequestSchema.parse({
      model: input.model,
      id: input.id,
      reason: input.reason,
      hard: input.hard,
    });

    const compiled = this.adapter.compileDelete(request, ctx, this.policy, this.schema);
    return this.adapter.executeDelete(compiled, ctx);
  }
}

// =============================================================================
// BULK UPDATE TOOL
// =============================================================================

const BulkUpdateInputSchema = z.object({
  model: z.string().describe('The model to update'),
  ids: z.array(z.unknown()).min(1).describe('Primary keys of records to update'),
  data: z.record(z.unknown()).describe('Fields to update on all records'),
  reason: z.string().optional().describe('Reason for the mutation'),
});

type BulkUpdateInput = z.infer<typeof BulkUpdateInputSchema>;

/**
 * Tool to bulk update records.
 */
export class BulkUpdateTool extends BaseTool<BulkUpdateInput, BulkUpdateResult> {
  readonly name = 'db.bulk_update';
  readonly description = 'Update multiple records by their primary keys.';
  readonly inputSchema = BulkUpdateInputSchema;

  constructor(
    private readonly adapter: OrmAdapter,
    private readonly policy: Policy,
    private readonly schema: SchemaMetadata,
    private readonly limits: ToolLimits = DEFAULT_TOOL_LIMITS
  ) {
    super();
  }

  async execute(input: BulkUpdateInput, ctx: RunContext): Promise<BulkUpdateResult> {
    // Validate ids count against limits
    if (input.ids.length > this.limits.maxBulkUpdateIds) {
      throw new Error(`Bulk update IDs count ${input.ids.length} exceeds maximum of ${this.limits.maxBulkUpdateIds}`);
    }

    const request = BulkUpdateRequestSchema.parse({
      model: input.model,
      ids: input.ids,
      data: input.data,
      reason: input.reason,
    });

    const compiled = this.adapter.compileBulkUpdate(request, ctx, this.policy, this.schema);
    return this.adapter.executeBulkUpdate(compiled, ctx);
  }
}

// =============================================================================
// FACTORY FUNCTION
// =============================================================================

/**
 * Options for creating generic tools.
 */
export interface GenericToolsOptions {
  adapter: OrmAdapter;
  policy: Policy;
  schema: SchemaMetadata;
  includeWrite?: boolean;
  limits?: Partial<ToolLimits>;
}

/**
 * Create all generic database tools.
 */
export function createGenericTools(options: GenericToolsOptions): BaseTool<unknown, unknown>[] {
  const { adapter, policy, schema, includeWrite = false, limits } = options;
  const effectiveLimits = { ...DEFAULT_TOOL_LIMITS, ...limits };

  const tools: BaseTool<unknown, unknown>[] = [
    new DescribeSchemaTool(schema, policy),
    new QueryTool(adapter, policy, schema, effectiveLimits),
    new GetTool(adapter, policy, schema),
    new AggregateTool(adapter, policy, schema),
  ];

  if (includeWrite || policy.writesEnabled) {
    tools.push(
      new CreateTool(adapter, policy, schema),
      new UpdateTool(adapter, policy, schema),
      new DeleteTool(adapter, policy, schema),
      new BulkUpdateTool(adapter, policy, schema, effectiveLimits)
    );
  }

  return tools;
}
