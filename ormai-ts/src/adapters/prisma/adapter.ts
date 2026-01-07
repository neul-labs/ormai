/**
 * Prisma adapter for OrmAI.
 *
 * Provides full CRUD support for Prisma ORM.
 */

import type { RunContext } from '../../core/context.js';
import type {
  AggregateRequest,
  AggregateResult,
  BulkUpdateRequest,
  BulkUpdateResult,
  CreateRequest,
  CreateResult,
  DeleteRequest,
  DeleteResult,
  GetRequest,
  GetResult,
  QueryRequest,
  QueryResult,
  UpdateRequest,
  UpdateResult,
} from '../../core/dsl.js';
import type { SchemaMetadata } from '../../core/types.js';
import type { Policy } from '../../policy/models.js';
import { PolicyEngine } from '../../policy/engine.js';
import { PolicyUtils } from '../../policy/models.js';
import { CursorEncoder } from '../../core/cursor.js';
import type {
  CompiledMutation,
  CompiledQuery,
} from '../base.js';
import { BaseOrmAdapter } from '../base.js';
import { introspectPrismaClient } from './introspection.js';
import {
  PrismaCompiler,
  type PrismaAggregateArgs,
  type PrismaCreateArgs,
  type PrismaDeleteArgs,
  type PrismaFindManyArgs,
  type PrismaFindUniqueArgs,
  type PrismaUpdateArgs,
} from './compiler.js';

/**
 * Prisma client interface (minimal type for compatibility).
 */
export interface PrismaClientLike {
  $transaction: <T>(fn: () => Promise<T>) => Promise<T>;
  [modelName: string]: unknown;
}

/**
 * Prisma adapter options.
 */
export interface PrismaAdapterOptions {
  /** List of models to include (defaults to all) */
  models?: string[];

  /** Custom cursor encoder secret */
  cursorSecret?: string;
}

/**
 * Prisma adapter for OrmAI.
 */
export class PrismaAdapter extends BaseOrmAdapter<
  PrismaClientLike,
  PrismaFindManyArgs | PrismaFindUniqueArgs | PrismaAggregateArgs,
  PrismaCreateArgs | PrismaUpdateArgs | PrismaDeleteArgs
> {
  private readonly compiler = new PrismaCompiler();
  private readonly cursorEncoder: CursorEncoder;
  private readonly modelFilter?: string[];
  private cachedSchema?: SchemaMetadata;

  constructor(
    private readonly prisma: PrismaClientLike,
    options?: PrismaAdapterOptions
  ) {
    super();
    this.modelFilter = options?.models;
    this.cursorEncoder = new CursorEncoder(options?.cursorSecret);
  }

  /**
   * Introspect the Prisma schema.
   */
  async introspect(): Promise<SchemaMetadata> {
    if (this.cachedSchema) {
      return this.cachedSchema;
    }
    this.cachedSchema = introspectPrismaClient(this.prisma, this.modelFilter);
    return this.cachedSchema;
  }

  /**
   * Get a model delegate from Prisma client.
   */
  private getModelDelegate(modelName: string): Record<string, (...args: unknown[]) => Promise<unknown>> {
    // Convert PascalCase to camelCase for Prisma model access
    const delegateName = modelName.charAt(0).toLowerCase() + modelName.slice(1);
    const delegate = this.prisma[delegateName];
    if (!delegate || typeof delegate !== 'object') {
      throw new Error(`Model '${modelName}' not found on Prisma client`);
    }
    return delegate as Record<string, (...args: unknown[]) => Promise<unknown>>;
  }

  /**
   * Compile a query request.
   */
  compileQuery(
    request: QueryRequest,
    ctx: RunContext<PrismaClientLike>,
    policy: Policy,
    schema: SchemaMetadata
  ): CompiledQuery<PrismaFindManyArgs> {
    const engine = new PolicyEngine(policy, schema);
    const decision = engine.validateQuery(request, ctx);

    const args: PrismaFindManyArgs = {};

    // Build where clause from user filters and injected filters
    const userWhere = request.where ? this.compiler.compileFilters(request.where) : {};
    const scopeWhere = this.compiler.compileFilters(decision.injectedFilters);
    args.where = this.compiler.mergeWhere(scopeWhere, userWhere);

    // Build select clause
    if (decision.allowedFields.length > 0) {
      args.select = this.compiler.compileSelect(decision.allowedFields);
    }

    // Build order by
    if (request.orderBy) {
      args.orderBy = this.compiler.compileOrderBy(request.orderBy);
    }

    // Build includes
    if (request.include) {
      // If we have select, we need to add includes inside select
      if (args.select) {
        const includes = this.compiler.compileIncludes(request.include);
        for (const [rel, inc] of Object.entries(includes)) {
          args.select[rel] = inc;
        }
      } else {
        args.include = this.compiler.compileIncludes(request.include);
      }
    }

    // Pagination
    args.take = request.take;

    // Cursor-based pagination
    if (request.cursor) {
      const [cursorValues] = this.cursorEncoder.decodeKeyset(request.cursor);
      if (Object.keys(cursorValues).length > 0) {
        args.cursor = cursorValues;
        args.skip = 1; // Skip the cursor record
      }
    }

    return {
      query: args,
      request,
      selectFields: decision.allowedFields,
      injectedFilters: decision.injectedFilters,
      policyDecisions: decision.decisions,
      timeoutMs: decision.budget?.statementTimeoutMs,
    };
  }

  /**
   * Compile a get request.
   */
  compileGet(
    request: GetRequest,
    ctx: RunContext<PrismaClientLike>,
    policy: Policy,
    schema: SchemaMetadata
  ): CompiledQuery<PrismaFindUniqueArgs> {
    const engine = new PolicyEngine(policy, schema);
    const decision = engine.validateGet(request, ctx);

    const model = schema.models[request.model];
    const pkWhere = this.compiler.buildPrimaryKeyWhere(request.id, model);

    // Merge with scope filters
    const scopeWhere = this.compiler.compileFilters(decision.injectedFilters);
    const where = this.compiler.mergeWhere(pkWhere, scopeWhere);

    const args: PrismaFindUniqueArgs = { where };

    // Build select clause
    if (decision.allowedFields.length > 0) {
      args.select = this.compiler.compileSelect(decision.allowedFields);
    }

    // Build includes
    if (request.include) {
      if (args.select) {
        const includes = this.compiler.compileIncludes(request.include);
        for (const [rel, inc] of Object.entries(includes)) {
          args.select[rel] = inc;
        }
      } else {
        args.include = this.compiler.compileIncludes(request.include);
      }
    }

    return {
      query: args,
      request,
      selectFields: decision.allowedFields,
      injectedFilters: decision.injectedFilters,
      policyDecisions: decision.decisions,
      timeoutMs: decision.budget?.statementTimeoutMs,
    };
  }

  /**
   * Compile an aggregate request.
   */
  compileAggregate(
    request: AggregateRequest,
    ctx: RunContext<PrismaClientLike>,
    policy: Policy,
    schema: SchemaMetadata
  ): CompiledQuery<PrismaAggregateArgs> {
    const engine = new PolicyEngine(policy, schema);
    const decision = engine.validateAggregate(request, ctx);

    const args: PrismaAggregateArgs = {};

    // Build where clause
    const userWhere = request.where ? this.compiler.compileFilters(request.where) : {};
    const scopeWhere = this.compiler.compileFilters(decision.injectedFilters);
    args.where = this.compiler.mergeWhere(scopeWhere, userWhere);

    // Build aggregation
    switch (request.operation) {
      case 'count':
        args._count = true;
        break;
      case 'sum':
        if (request.field) {
          args._sum = { [request.field]: true };
        }
        break;
      case 'avg':
        if (request.field) {
          args._avg = { [request.field]: true };
        }
        break;
      case 'min':
        if (request.field) {
          args._min = { [request.field]: true };
        }
        break;
      case 'max':
        if (request.field) {
          args._max = { [request.field]: true };
        }
        break;
    }

    return {
      query: args,
      request,
      selectFields: [],
      injectedFilters: decision.injectedFilters,
      policyDecisions: decision.decisions,
      timeoutMs: decision.budget?.statementTimeoutMs,
    };
  }

  /**
   * Execute a compiled query.
   */
  async executeQuery(
    compiled: CompiledQuery<PrismaFindManyArgs>,
    _ctx: RunContext<PrismaClientLike>
  ): Promise<QueryResult> {
    const request = compiled.request as QueryRequest;
    const delegate = this.getModelDelegate(request.model);

    // Execute query
    const results = (await delegate['findMany'](compiled.query)) as Record<string, unknown>[];

    // Build cursor for next page
    let nextCursor: string | null = null;
    if (results.length >= request.take) {
      const schema = await this.introspect();
      const lastRecord = results[results.length - 1];
      const model = schema.models[request.model];
      const orderFields = request.orderBy?.map((o) => o.field) ?? [model.primaryKey];
      nextCursor = this.cursorEncoder.encodeKeyset(lastRecord, orderFields);
    }

    // Rows are already filtered to allowedFields via the compiled query
    return {
      data: results,
      nextCursor,
      hasMore: results.length >= request.take,
      totalCount: null,
    };
  }

  /**
   * Execute a compiled get request.
   */
  async executeGet(
    compiled: CompiledQuery<PrismaFindUniqueArgs>,
    _ctx: RunContext<PrismaClientLike>
  ): Promise<GetResult> {
    const request = compiled.request as GetRequest;
    const delegate = this.getModelDelegate(request.model);

    // Use findFirst instead of findUnique to support compound where clauses
    const result = (await delegate['findFirst'](compiled.query)) as Record<string, unknown> | null;

    if (!result) {
      return { data: null, found: false };
    }

    // Rows are already filtered to allowedFields via the compiled query
    return { data: result, found: true };
  }

  /**
   * Execute a compiled aggregate request.
   */
  async executeAggregate(
    compiled: CompiledQuery<PrismaAggregateArgs>,
    _ctx: RunContext<PrismaClientLike>
  ): Promise<AggregateResult> {
    const request = compiled.request as AggregateRequest;
    const delegate = this.getModelDelegate(request.model);

    const result = (await delegate['aggregate'](compiled.query)) as Record<string, unknown>;

    // Extract the value based on operation
    let value: unknown = null;
    let rowCount = 0;

    if (request.operation === 'count') {
      const count = result['_count'];
      value = typeof count === 'number' ? count : (count as Record<string, unknown>)?.['_all'] ?? 0;
      rowCount = value as number;
    } else {
      const opResult = result[`_${request.operation}`] as Record<string, unknown> | undefined;
      if (opResult && request.field) {
        value = opResult[request.field];
      }
    }

    return {
      value,
      operation: request.operation,
      field: request.field ?? null,
      rowCount,
    };
  }

  /**
   * Execute a function within a transaction.
   */
  async transaction<T>(
    _ctx: RunContext<PrismaClientLike>,
    fn: () => Promise<T>
  ): Promise<T> {
    return this.prisma.$transaction(fn);
  }

  // =========================================================================
  // MUTATION METHODS
  // =========================================================================

  /**
   * Compile a create request.
   */
  compileCreate(
    request: CreateRequest,
    ctx: RunContext<PrismaClientLike>,
    policy: Policy,
    schema: SchemaMetadata
  ): CompiledMutation<PrismaCreateArgs> {
    const engine = new PolicyEngine(policy, schema);
    const decision = engine.validateCreate(request, ctx);

    // Build data with scope injection
    const data = { ...request.data };
    for (const filter of decision.injectedFilters) {
      if (filter.op === 'eq') {
        data[filter.field] = filter.value;
      }
    }

    const args: PrismaCreateArgs = { data };

    // Build select for return fields
    if (decision.allowedFields.length > 0) {
      args.select = this.compiler.compileSelect(decision.allowedFields);
    }

    return {
      mutation: args,
      request,
      data,
      injectedFilters: decision.injectedFilters,
      policyDecisions: decision.decisions,
      returnFields: decision.allowedFields,
    };
  }

  /**
   * Compile an update request.
   */
  compileUpdate(
    request: UpdateRequest,
    ctx: RunContext<PrismaClientLike>,
    policy: Policy,
    schema: SchemaMetadata
  ): CompiledMutation<PrismaUpdateArgs> {
    const engine = new PolicyEngine(policy, schema);
    const decision = engine.validateUpdate(request, ctx);

    const model = schema.models[request.model];
    const pkWhere = this.compiler.buildPrimaryKeyWhere(request.id, model);
    const scopeWhere = this.compiler.compileFilters(decision.injectedFilters);
    const where = this.compiler.mergeWhere(pkWhere, scopeWhere);

    const args: PrismaUpdateArgs = {
      where,
      data: request.data,
    };

    if (decision.allowedFields.length > 0) {
      args.select = this.compiler.compileSelect(decision.allowedFields);
    }

    return {
      mutation: args,
      request,
      data: request.data,
      injectedFilters: decision.injectedFilters,
      policyDecisions: decision.decisions,
      returnFields: decision.allowedFields,
    };
  }

  /**
   * Compile a delete request.
   */
  compileDelete(
    request: DeleteRequest,
    ctx: RunContext<PrismaClientLike>,
    policy: Policy,
    schema: SchemaMetadata
  ): CompiledMutation<PrismaDeleteArgs> {
    const engine = new PolicyEngine(policy, schema);
    const decision = engine.validateDelete(request, ctx);

    const model = schema.models[request.model];
    const rowPolicy = PolicyUtils.getRowPolicy(policy, request.model);

    // Check if we should soft delete
    const softDelete = !request.hard && rowPolicy.softDeleteField;

    if (softDelete) {
      // Soft delete is actually an update
      const pkWhere = this.compiler.buildPrimaryKeyWhere(request.id, model);
      const scopeWhere = this.compiler.compileFilters(decision.injectedFilters);
      const where = this.compiler.mergeWhere(pkWhere, scopeWhere);

      return {
        mutation: { where } as PrismaDeleteArgs,
        request,
        data: { [rowPolicy.softDeleteField!]: new Date() },
        injectedFilters: decision.injectedFilters,
        policyDecisions: [...decision.decisions, 'Using soft delete'],
        returnFields: [],
      };
    }

    // Hard delete
    const pkWhere = this.compiler.buildPrimaryKeyWhere(request.id, model);
    const scopeWhere = this.compiler.compileFilters(decision.injectedFilters);
    const where = this.compiler.mergeWhere(pkWhere, scopeWhere);

    return {
      mutation: { where },
      request,
      injectedFilters: decision.injectedFilters,
      policyDecisions: decision.decisions,
      returnFields: [],
    };
  }

  /**
   * Compile a bulk update request.
   */
  compileBulkUpdate(
    request: BulkUpdateRequest,
    ctx: RunContext<PrismaClientLike>,
    policy: Policy,
    schema: SchemaMetadata
  ): CompiledMutation<PrismaUpdateArgs> {
    const engine = new PolicyEngine(policy, schema);
    const decision = engine.validateBulkUpdate(request, ctx);

    const model = schema.models[request.model];
    const scopeWhere = this.compiler.compileFilters(decision.injectedFilters);

    // Build where clause with all IDs
    const idsWhere = { [model.primaryKey]: { in: request.ids } };
    const where = this.compiler.mergeWhere(idsWhere, scopeWhere);

    return {
      mutation: { where, data: request.data },
      request,
      data: request.data,
      injectedFilters: decision.injectedFilters,
      policyDecisions: decision.decisions,
      returnFields: [],
    };
  }

  /**
   * Execute a compiled create request.
   */
  async executeCreate(
    compiled: CompiledMutation<PrismaCreateArgs>,
    _ctx: RunContext<PrismaClientLike>
  ): Promise<CreateResult> {
    const request = compiled.request as CreateRequest;
    const delegate = this.getModelDelegate(request.model);

    const result = (await delegate['create'](compiled.mutation)) as Record<string, unknown>;

    // Get primary key from result
    const schema = await this.introspect();
    const model = schema.models[request.model];
    const id = result[model.primaryKey];

    return {
      data: result,
      id,
      success: true,
    };
  }

  /**
   * Execute a compiled update request.
   */
  async executeUpdate(
    compiled: CompiledMutation<PrismaUpdateArgs>,
    _ctx: RunContext<PrismaClientLike>
  ): Promise<UpdateResult> {
    const request = compiled.request as UpdateRequest;
    const delegate = this.getModelDelegate(request.model);

    try {
      // Use updateMany for scoped updates
      const result = (await delegate['updateMany']({
        where: compiled.mutation.where,
        data: compiled.mutation.data,
      })) as { count: number };

      if (result.count === 0) {
        return { data: null, success: false, found: false };
      }

      return { data: compiled.data ?? null, success: true, found: true };
    } catch (error) {
      return { data: null, success: false, found: false };
    }
  }

  /**
   * Execute a compiled delete request.
   */
  async executeDelete(
    compiled: CompiledMutation<PrismaDeleteArgs>,
    _ctx: RunContext<PrismaClientLike>
  ): Promise<DeleteResult> {
    const request = compiled.request as DeleteRequest;
    const delegate = this.getModelDelegate(request.model);

    try {
      if (compiled.data) {
        // Soft delete (update)
        const result = (await delegate['updateMany']({
          where: compiled.mutation.where,
          data: compiled.data,
        })) as { count: number };

        return {
          success: result.count > 0,
          found: result.count > 0,
          softDeleted: true,
        };
      } else {
        // Hard delete
        const result = (await delegate['deleteMany']({
          where: compiled.mutation.where,
        })) as { count: number };

        return {
          success: result.count > 0,
          found: result.count > 0,
          softDeleted: false,
        };
      }
    } catch (error) {
      return { success: false, found: false, softDeleted: false };
    }
  }

  /**
   * Execute a compiled bulk update request.
   */
  async executeBulkUpdate(
    compiled: CompiledMutation<PrismaUpdateArgs>,
    _ctx: RunContext<PrismaClientLike>
  ): Promise<BulkUpdateResult> {
    const request = compiled.request as BulkUpdateRequest;
    const delegate = this.getModelDelegate(request.model);

    try {
      const result = (await delegate['updateMany']({
        where: compiled.mutation.where,
        data: compiled.mutation.data,
      })) as { count: number };

      return {
        updatedCount: result.count,
        success: true,
        failedIds: [],
      };
    } catch (error) {
      return {
        updatedCount: 0,
        success: false,
        failedIds: request.ids,
      };
    }
  }
}

/**
 * Create a Prisma adapter.
 */
export function createPrismaAdapter(
  prisma: PrismaClientLike,
  options?: PrismaAdapterOptions
): PrismaAdapter {
  return new PrismaAdapter(prisma, options);
}
