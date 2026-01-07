/**
 * Drizzle ORM adapter for OrmAI.
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
import type { CompiledMutation, CompiledQuery } from '../base.js';
import { BaseOrmAdapter } from '../base.js';
import {
  DrizzleCompiler,
  type DrizzleOperators,
  type DrizzleTableRef,
  type CompiledDrizzleQuery,
  type CompiledDrizzleMutation,
} from './compiler.js';
import { DrizzleIntrospector, type DrizzleRelation, type DrizzleSchema } from './introspection.js';

/**
 * Drizzle database instance type.
 */
export interface DrizzleDB {
  select: (fields?: Record<string, unknown>) => DrizzleQueryBuilder;
  insert: (table: DrizzleTableRef) => DrizzleInsertBuilder;
  update: (table: DrizzleTableRef) => DrizzleUpdateBuilder;
  delete: (table: DrizzleTableRef) => DrizzleDeleteBuilder;
  transaction: <T>(fn: (tx: DrizzleDB) => Promise<T>) => Promise<T>;
}

/**
 * Drizzle query builder interface.
 */
export interface DrizzleQueryBuilder {
  from: (table: DrizzleTableRef) => DrizzleQueryBuilder;
  where: (...conditions: unknown[]) => DrizzleQueryBuilder;
  orderBy: (...orders: unknown[]) => DrizzleQueryBuilder;
  limit: (n: number) => DrizzleQueryBuilder;
  offset: (n: number) => DrizzleQueryBuilder;
  then: <T>(resolve: (value: unknown[]) => T) => Promise<T>;
}

/**
 * Drizzle insert builder interface.
 */
export interface DrizzleInsertBuilder {
  values: (data: Record<string, unknown> | Record<string, unknown>[]) => DrizzleInsertBuilder;
  returning: () => DrizzleInsertBuilder;
  then: <T>(resolve: (value: unknown[]) => T) => Promise<T>;
}

/**
 * Drizzle update builder interface.
 */
export interface DrizzleUpdateBuilder {
  set: (data: Record<string, unknown>) => DrizzleUpdateBuilder;
  where: (...conditions: unknown[]) => DrizzleUpdateBuilder;
  returning: () => DrizzleUpdateBuilder;
  then: <T>(resolve: (value: unknown[]) => T) => Promise<T>;
}

/**
 * Drizzle delete builder interface.
 */
export interface DrizzleDeleteBuilder {
  where: (...conditions: unknown[]) => DrizzleDeleteBuilder;
  returning: () => DrizzleDeleteBuilder;
  then: <T>(resolve: (value: unknown[]) => T) => Promise<T>;
}

/**
 * Drizzle adapter configuration.
 */
export interface DrizzleAdapterConfig {
  /** Drizzle database instance */
  db: DrizzleDB;

  /** Drizzle schema (tables) */
  schema: DrizzleSchema;

  /** Drizzle operators */
  operators: DrizzleOperators;

  /** Drizzle relations (optional) */
  relations?: Record<string, DrizzleRelation[]>;

  /** Model names to expose (optional, defaults to all) */
  models?: string[];
}

/**
 * Drizzle adapter for OrmAI.
 */
export class DrizzleAdapter extends BaseOrmAdapter<DrizzleDB, CompiledDrizzleQuery, CompiledDrizzleMutation> {
  private readonly db: DrizzleDB;
  private readonly drizzleSchema: DrizzleSchema;
  private readonly operators: DrizzleOperators;
  private readonly relations: Record<string, DrizzleRelation[]>;
  private readonly modelFilter?: string[];
  private readonly compiler: DrizzleCompiler;
  private cachedSchema?: SchemaMetadata;

  constructor(config: DrizzleAdapterConfig) {
    super();
    this.db = config.db;
    this.drizzleSchema = config.schema;
    this.operators = config.operators;
    this.relations = config.relations ?? {};
    this.modelFilter = config.models;

    // Build table map from schema
    const tables: Record<string, DrizzleTableRef> = {};
    for (const [name, table] of Object.entries(this.drizzleSchema)) {
      tables[name] = table as DrizzleTableRef;
      if (table._ && table._.name) {
        tables[table._.name as string] = table as DrizzleTableRef;
      }
    }

    this.compiler = new DrizzleCompiler(tables, this.operators);
  }

  /**
   * Introspect the Drizzle schema.
   */
  async introspect(): Promise<SchemaMetadata> {
    if (this.cachedSchema) {
      return this.cachedSchema;
    }

    const introspector = new DrizzleIntrospector(this.drizzleSchema, this.relations);
    let schema = introspector.introspect();

    // Filter models if specified
    if (this.modelFilter) {
      const filtered: Record<string, typeof schema.models[string]> = {};
      for (const name of this.modelFilter) {
        if (schema.models[name]) {
          filtered[name] = schema.models[name];
        }
      }
      schema = { models: filtered };
    }

    this.cachedSchema = schema;
    return schema;
  }

  /**
   * Compile a query request.
   */
  compileQuery(
    request: QueryRequest,
    ctx: RunContext<DrizzleDB>,
    policy: Policy,
    schema: SchemaMetadata
  ): CompiledQuery<CompiledDrizzleQuery> {
    const engine = new PolicyEngine(policy, schema);
    const decision = engine.validateQuery(request, ctx);

    const table = this.compiler.getTable(request.model);

    // Merge user filters with scope filters
    const allFilters = [
      ...(request.where ?? []),
      ...decision.injectedFilters,
    ];

    const compiled: CompiledDrizzleQuery = {
      table,
      where: allFilters.length > 0 ? this.compiler.compileFilters(allFilters, table) : undefined,
      orderBy: request.orderBy ? this.compiler.compileOrderBy(request.orderBy, table) : [],
      limit: request.take,
      offset: undefined,
      columns: decision.allowedFields.length > 0
        ? this.compiler.compileSelect(decision.allowedFields, table)
        : undefined,
    };

    return {
      query: compiled,
      request,
      selectFields: decision.allowedFields,
      injectedFilters: decision.injectedFilters,
      policyDecisions: decision.decisions,
      timeoutMs: decision.budget?.statementTimeoutMs,
    };
  }

  /**
   * Execute a compiled query.
   */
  async executeQuery(
    compiled: CompiledQuery<CompiledDrizzleQuery>,
    ctx: RunContext<DrizzleDB>
  ): Promise<QueryResult> {
    const { query } = compiled;
    const db = ctx.db ?? this.db;
    const request = compiled.request as QueryRequest;

    try {
      let builder = db.select().from(query.table);

      if (query.where) {
        builder = builder.where(query.where);
      }

      if (query.orderBy && query.orderBy.length > 0) {
        builder = builder.orderBy(...query.orderBy);
      }

      if (query.limit !== undefined) {
        builder = builder.limit(query.limit);
      }

      if (query.offset !== undefined) {
        builder = builder.offset(query.offset);
      }

      const rows = await builder as Record<string, unknown>[];

      // Rows are already filtered to allowedFields via the compiled query
      return {
        data: rows,
        nextCursor: null,
        hasMore: rows.length >= request.take,
        totalCount: null,
      };
    } catch (error) {
      throw new Error(`Query execution failed: ${(error as Error).message}`);
    }
  }

  /**
   * Compile a get request.
   */
  compileGet(
    request: GetRequest,
    ctx: RunContext<DrizzleDB>,
    policy: Policy,
    schema: SchemaMetadata
  ): CompiledQuery<CompiledDrizzleQuery> {
    const engine = new PolicyEngine(policy, schema);
    const decision = engine.validateGet(request, ctx);

    const table = this.compiler.getTable(request.model);
    const model = schema.models[request.model];

    if (!model) {
      throw new Error(`Model '${request.model}' not found in schema`);
    }

    // Build primary key filter
    const pkFilter = { field: model.primaryKey, op: 'eq' as const, value: request.id };
    const allFilters = [pkFilter, ...decision.injectedFilters];

    const compiled: CompiledDrizzleQuery = {
      table,
      where: this.compiler.compileFilters(allFilters, table),
      orderBy: [],
      limit: 1,
      columns: decision.allowedFields.length > 0
        ? this.compiler.compileSelect(decision.allowedFields, table)
        : undefined,
    };

    return {
      query: compiled,
      request,
      selectFields: decision.allowedFields,
      injectedFilters: decision.injectedFilters,
      policyDecisions: decision.decisions,
      timeoutMs: decision.budget?.statementTimeoutMs,
    };
  }

  /**
   * Execute a compiled get query.
   */
  async executeGet(
    compiled: CompiledQuery<CompiledDrizzleQuery>,
    ctx: RunContext<DrizzleDB>
  ): Promise<GetResult> {
    const result = await this.executeQuery(compiled, ctx);
    const row = result.data[0] ?? null;
    return { data: row, found: row !== null };
  }

  /**
   * Compile an aggregate request.
   */
  compileAggregate(
    request: AggregateRequest,
    ctx: RunContext<DrizzleDB>,
    policy: Policy,
    schema: SchemaMetadata
  ): CompiledQuery<CompiledDrizzleQuery> {
    const engine = new PolicyEngine(policy, schema);
    const decision = engine.validateAggregate(request, ctx);

    const table = this.compiler.getTable(request.model);

    // Merge user filters with scope filters
    const allFilters = [
      ...(request.where ?? []),
      ...decision.injectedFilters,
    ];

    const compiled: CompiledDrizzleQuery = {
      table,
      where: allFilters.length > 0 ? this.compiler.compileFilters(allFilters, table) : undefined,
      orderBy: [],
    };

    return {
      query: compiled,
      request,
      selectFields: [],
      injectedFilters: decision.injectedFilters,
      policyDecisions: decision.decisions,
      timeoutMs: decision.budget?.statementTimeoutMs,
    };
  }

  /**
   * Execute a compiled aggregate query.
   */
  async executeAggregate(
    compiled: CompiledQuery<CompiledDrizzleQuery>,
    ctx: RunContext<DrizzleDB>
  ): Promise<AggregateResult> {
    // For aggregates, we need to execute and compute client-side
    // A real implementation would use raw SQL or Drizzle's aggregation APIs
    const { query } = compiled;
    const request = compiled.request as AggregateRequest;
    const db = ctx.db ?? this.db;

    try {
      let builder = db.select().from(query.table);
      if (query.where) {
        builder = builder.where(query.where);
      }
      const rows = await builder as Record<string, unknown>[];

      let value: unknown = null;
      const rowCount = rows.length;

      switch (request.operation) {
        case 'count':
          value = rowCount;
          break;
        case 'sum':
          if (request.field) {
            value = rows.reduce((sum, row) => sum + (Number(row[request.field!]) || 0), 0);
          }
          break;
        case 'avg':
          if (request.field && rows.length > 0) {
            value = rows.reduce((sum, row) => sum + (Number(row[request.field!]) || 0), 0) / rows.length;
          }
          break;
        case 'min':
          if (request.field && rows.length > 0) {
            value = Math.min(...rows.map((row) => Number(row[request.field!]) || 0));
          }
          break;
        case 'max':
          if (request.field && rows.length > 0) {
            value = Math.max(...rows.map((row) => Number(row[request.field!]) || 0));
          }
          break;
      }

      return {
        value,
        operation: request.operation,
        field: request.field ?? null,
        rowCount,
      };
    } catch (error) {
      throw new Error(`Aggregate execution failed: ${(error as Error).message}`);
    }
  }

  /**
   * Compile a create request.
   */
  compileCreate(
    request: CreateRequest,
    ctx: RunContext<DrizzleDB>,
    policy: Policy,
    schema: SchemaMetadata
  ): CompiledMutation<CompiledDrizzleMutation> {
    const engine = new PolicyEngine(policy, schema);
    const decision = engine.validateCreate(request, ctx);

    // Build data with scope injection
    const data = { ...request.data };
    for (const filter of decision.injectedFilters) {
      if (filter.op === 'eq') {
        data[filter.field] = filter.value;
      }
    }

    const table = this.compiler.getTable(request.model);
    const compiled: CompiledDrizzleMutation = {
      table,
      type: 'insert',
      data,
      returning: true,
    };

    return {
      mutation: compiled,
      request,
      data,
      injectedFilters: decision.injectedFilters,
      policyDecisions: decision.decisions,
      returnFields: decision.allowedFields,
    };
  }

  /**
   * Execute a compiled create mutation.
   */
  async executeCreate(
    compiled: CompiledMutation<CompiledDrizzleMutation>,
    ctx: RunContext<DrizzleDB>
  ): Promise<CreateResult> {
    const { mutation } = compiled;
    const db = ctx.db ?? this.db;

    try {
      const result = await db
        .insert(mutation.table)
        .values(mutation.data!)
        .returning() as Record<string, unknown>[];

      const record = result[0] ?? null;

      return {
        data: record,
        id: record ? record['id'] : undefined,
        success: true,
      };
    } catch (error) {
      throw new Error(`Create failed: ${(error as Error).message}`);
    }
  }

  /**
   * Compile an update request.
   */
  compileUpdate(
    request: UpdateRequest,
    ctx: RunContext<DrizzleDB>,
    policy: Policy,
    schema: SchemaMetadata
  ): CompiledMutation<CompiledDrizzleMutation> {
    const engine = new PolicyEngine(policy, schema);
    const decision = engine.validateUpdate(request, ctx);

    const table = this.compiler.getTable(request.model);
    const model = schema.models[request.model];

    if (!model) {
      throw new Error(`Model '${request.model}' not found in schema`);
    }

    // Build primary key filter with scope filters
    const pkFilter = { field: model.primaryKey, op: 'eq' as const, value: request.id };
    const allFilters = [pkFilter, ...decision.injectedFilters];

    const compiled: CompiledDrizzleMutation = {
      table,
      type: 'update',
      data: request.data,
      where: this.compiler.compileFilters(allFilters, table),
      returning: true,
    };

    return {
      mutation: compiled,
      request,
      data: request.data,
      injectedFilters: decision.injectedFilters,
      policyDecisions: decision.decisions,
      returnFields: decision.allowedFields,
    };
  }

  /**
   * Execute a compiled update mutation.
   */
  async executeUpdate(
    compiled: CompiledMutation<CompiledDrizzleMutation>,
    ctx: RunContext<DrizzleDB>
  ): Promise<UpdateResult> {
    const { mutation } = compiled;
    const db = ctx.db ?? this.db;

    try {
      let builder = db.update(mutation.table).set(mutation.data!);

      if (mutation.where) {
        builder = builder.where(mutation.where);
      }

      const result = await builder.returning() as Record<string, unknown>[];
      const record = result[0] ?? null;

      return {
        data: record,
        success: result.length > 0,
        found: result.length > 0,
      };
    } catch (error) {
      throw new Error(`Update failed: ${(error as Error).message}`);
    }
  }

  /**
   * Compile a delete request.
   */
  compileDelete(
    request: DeleteRequest,
    ctx: RunContext<DrizzleDB>,
    policy: Policy,
    schema: SchemaMetadata
  ): CompiledMutation<CompiledDrizzleMutation> {
    const engine = new PolicyEngine(policy, schema);
    const decision = engine.validateDelete(request, ctx);

    const table = this.compiler.getTable(request.model);
    const model = schema.models[request.model];

    if (!model) {
      throw new Error(`Model '${request.model}' not found in schema`);
    }

    // Build primary key filter with scope filters
    const pkFilter = { field: model.primaryKey, op: 'eq' as const, value: request.id };
    const allFilters = [pkFilter, ...decision.injectedFilters];

    const rowPolicy = PolicyUtils.getRowPolicy(policy, request.model);
    const softDelete = !request.hard && rowPolicy.softDeleteField;

    if (softDelete) {
      // Soft delete is an update
      const compiled: CompiledDrizzleMutation = {
        table,
        type: 'update',
        data: { [rowPolicy.softDeleteField!]: new Date() },
        where: this.compiler.compileFilters(allFilters, table),
        returning: true,
      };

      return {
        mutation: compiled,
        request,
        data: { [rowPolicy.softDeleteField!]: new Date() },
        injectedFilters: decision.injectedFilters,
        policyDecisions: [...decision.decisions, 'Using soft delete'],
        returnFields: [],
      };
    }

    const compiled: CompiledDrizzleMutation = {
      table,
      type: 'delete',
      where: this.compiler.compileFilters(allFilters, table),
      returning: true,
    };

    return {
      mutation: compiled,
      request,
      injectedFilters: decision.injectedFilters,
      policyDecisions: decision.decisions,
      returnFields: [],
    };
  }

  /**
   * Execute a compiled delete mutation.
   */
  async executeDelete(
    compiled: CompiledMutation<CompiledDrizzleMutation>,
    ctx: RunContext<DrizzleDB>
  ): Promise<DeleteResult> {
    const { mutation } = compiled;
    const db = ctx.db ?? this.db;

    try {
      if (mutation.type === 'update') {
        // Soft delete
        let builder = db.update(mutation.table).set(mutation.data!);
        if (mutation.where) {
          builder = builder.where(mutation.where);
        }
        const result = await builder.returning() as unknown[];
        return {
          success: result.length > 0,
          found: result.length > 0,
          softDeleted: true,
        };
      } else {
        // Hard delete
        let builder = db.delete(mutation.table);
        if (mutation.where) {
          builder = builder.where(mutation.where);
        }
        const result = await builder.returning() as unknown[];
        return {
          success: result.length > 0,
          found: result.length > 0,
          softDeleted: false,
        };
      }
    } catch (error) {
      throw new Error(`Delete failed: ${(error as Error).message}`);
    }
  }

  /**
   * Compile a bulk update request.
   */
  compileBulkUpdate(
    request: BulkUpdateRequest,
    ctx: RunContext<DrizzleDB>,
    policy: Policy,
    schema: SchemaMetadata
  ): CompiledMutation<CompiledDrizzleMutation> {
    const engine = new PolicyEngine(policy, schema);
    const decision = engine.validateBulkUpdate(request, ctx);

    const table = this.compiler.getTable(request.model);
    const model = schema.models[request.model];

    if (!model) {
      throw new Error(`Model '${request.model}' not found in schema`);
    }

    // Build where clause with all IDs and scope filters
    const idsFilter = { field: model.primaryKey, op: 'in' as const, value: request.ids };
    const allFilters = [idsFilter, ...decision.injectedFilters];

    const compiled: CompiledDrizzleMutation = {
      table,
      type: 'update',
      data: request.data,
      where: this.compiler.compileFilters(allFilters, table),
      returning: true,
    };

    return {
      mutation: compiled,
      request,
      data: request.data,
      injectedFilters: decision.injectedFilters,
      policyDecisions: decision.decisions,
      returnFields: [],
    };
  }

  /**
   * Execute a compiled bulk update mutation.
   */
  async executeBulkUpdate(
    compiled: CompiledMutation<CompiledDrizzleMutation>,
    ctx: RunContext<DrizzleDB>
  ): Promise<BulkUpdateResult> {
    const { mutation } = compiled;
    const db = ctx.db ?? this.db;

    try {
      let builder = db.update(mutation.table).set(mutation.data!);
      if (mutation.where) {
        builder = builder.where(mutation.where);
      }
      const result = await builder.returning() as unknown[];

      return {
        updatedCount: result.length,
        success: true,
        failedIds: [],
      };
    } catch (error) {
      throw new Error(`Bulk update failed: ${(error as Error).message}`);
    }
  }

  /**
   * Execute operations in a transaction.
   */
  async transaction<T>(
    ctx: RunContext<DrizzleDB>,
    fn: () => Promise<T>
  ): Promise<T> {
    const db = ctx.db ?? this.db;
    return db.transaction(async () => fn());
  }
}

/**
 * Create a Drizzle adapter.
 */
export function createDrizzleAdapter(config: DrizzleAdapterConfig): DrizzleAdapter {
  return new DrizzleAdapter(config);
}
