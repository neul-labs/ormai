/**
 * TypeORM adapter for OrmAI.
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
  TypeORMCompiler,
  type CompiledTypeORMQuery,
  type CompiledTypeORMMutation,
} from './compiler.js';
import { TypeORMIntrospector, type TypeORMDataSource } from './introspection.js';

/**
 * TypeORM repository interface.
 */
export interface TypeORMRepository<T = unknown> {
  find: (options?: TypeORMFindOptions) => Promise<T[]>;
  findOne: (options?: TypeORMFindOptions) => Promise<T | null>;
  save: (entity: T | T[]) => Promise<T | T[]>;
  update: (criteria: unknown, partialEntity: Partial<T>) => Promise<TypeORMUpdateResult>;
  delete: (criteria: unknown) => Promise<TypeORMDeleteResult>;
  createQueryBuilder: (alias?: string) => TypeORMSelectQueryBuilder<T>;
  count: (options?: TypeORMFindOptions) => Promise<number>;
}

/**
 * TypeORM find options.
 */
export interface TypeORMFindOptions {
  where?: Record<string, unknown> | Record<string, unknown>[];
  order?: Record<string, 'ASC' | 'DESC'>;
  take?: number;
  skip?: number;
  select?: string[];
  relations?: string[];
}

/**
 * TypeORM select query builder.
 */
export interface TypeORMSelectQueryBuilder<T = unknown> {
  select: (fields?: string[]) => TypeORMSelectQueryBuilder<T>;
  addSelect: (field: string) => TypeORMSelectQueryBuilder<T>;
  where: (condition: string, parameters?: Record<string, unknown>) => TypeORMSelectQueryBuilder<T>;
  andWhere: (condition: string, parameters?: Record<string, unknown>) => TypeORMSelectQueryBuilder<T>;
  orderBy: (field: string, order: 'ASC' | 'DESC') => TypeORMSelectQueryBuilder<T>;
  addOrderBy: (field: string, order: 'ASC' | 'DESC') => TypeORMSelectQueryBuilder<T>;
  take: (limit: number) => TypeORMSelectQueryBuilder<T>;
  skip: (offset: number) => TypeORMSelectQueryBuilder<T>;
  leftJoinAndSelect: (relation: string, alias: string) => TypeORMSelectQueryBuilder<T>;
  getMany: () => Promise<T[]>;
  getOne: () => Promise<T | null>;
  getCount: () => Promise<number>;
}

/**
 * TypeORM update result.
 */
export interface TypeORMUpdateResult {
  affected?: number;
  raw?: unknown;
}

/**
 * TypeORM delete result.
 */
export interface TypeORMDeleteResult {
  affected?: number;
  raw?: unknown;
}

/**
 * TypeORM entity manager interface.
 */
export interface TypeORMEntityManager {
  getRepository: <T>(entity: string | Function) => TypeORMRepository<T>;
  transaction: <T>(fn: (entityManager: TypeORMEntityManager) => Promise<T>) => Promise<T>;
}

/**
 * Extended TypeORM data source for adapter.
 */
export interface TypeORMAdapterDataSource extends TypeORMDataSource {
  manager: TypeORMEntityManager;
  getRepository: <T>(entity: string | Function) => TypeORMRepository<T>;
  transaction: <T>(fn: (entityManager: TypeORMEntityManager) => Promise<T>) => Promise<T>;
}

/**
 * TypeORM adapter configuration.
 */
export interface TypeORMAdapterConfig {
  /** TypeORM data source */
  dataSource: TypeORMAdapterDataSource;

  /** Model names to expose (optional, defaults to all) */
  models?: string[];
}

/**
 * TypeORM adapter for OrmAI.
 */
export class TypeORMAdapter extends BaseOrmAdapter<
  TypeORMAdapterDataSource,
  CompiledTypeORMQuery,
  CompiledTypeORMMutation
> {
  private readonly dataSource: TypeORMAdapterDataSource;
  private readonly modelFilter?: string[];
  private readonly compiler: TypeORMCompiler;
  private cachedSchema?: SchemaMetadata;

  constructor(config: TypeORMAdapterConfig) {
    super();
    this.dataSource = config.dataSource;
    this.modelFilter = config.models;
    this.compiler = new TypeORMCompiler();
  }

  /**
   * Introspect the TypeORM schema.
   */
  async introspect(): Promise<SchemaMetadata> {
    if (this.cachedSchema) {
      return this.cachedSchema;
    }

    const introspector = new TypeORMIntrospector(this.dataSource, this.modelFilter);
    this.cachedSchema = introspector.introspect();
    return this.cachedSchema;
  }

  /**
   * Get repository for a model.
   */
  private getRepository<T>(
    modelName: string,
    ctx?: RunContext<TypeORMAdapterDataSource>
  ): TypeORMRepository<T> {
    const ds = ctx?.db ?? this.dataSource;
    return ds.getRepository<T>(modelName);
  }

  /**
   * Compile a query request.
   */
  compileQuery(
    request: QueryRequest,
    ctx: RunContext<TypeORMAdapterDataSource>,
    policy: Policy,
    schema: SchemaMetadata
  ): CompiledQuery<CompiledTypeORMQuery> {
    const engine = new PolicyEngine(policy, schema);
    const decision = engine.validateQuery(request, ctx);

    // Merge user filters with scope filters
    const allFilters = [
      ...(request.where ?? []),
      ...decision.injectedFilters,
    ];

    // Compile includes
    const includes = request.include?.map((inc) => inc.relation) ?? [];

    const compiled = this.compiler.compileQuery({
      model: request.model,
      filters: allFilters,
      orderBy: request.orderBy,
      take: request.take,
      select: decision.allowedFields,
      includes,
    });

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
    compiled: CompiledQuery<CompiledTypeORMQuery>,
    ctx: RunContext<TypeORMAdapterDataSource>
  ): Promise<QueryResult> {
    const { query } = compiled;
    const request = compiled.request as QueryRequest;
    const repo = this.getRepository(query.entityName, ctx);

    try {
      let qb = repo.createQueryBuilder(query.alias);

      // Apply select fields
      if (query.selectFields && query.selectFields.length > 0) {
        qb = qb.select(query.selectFields);
      }

      // Apply where conditions
      for (let i = 0; i < query.whereConditions.length; i++) {
        const { condition, parameters } = query.whereConditions[i];
        if (i === 0) {
          qb = qb.where(condition, parameters);
        } else {
          qb = qb.andWhere(condition, parameters);
        }
      }

      // Apply order by
      for (let i = 0; i < query.orderBy.length; i++) {
        const { field, direction } = query.orderBy[i];
        if (i === 0) {
          qb = qb.orderBy(field, direction);
        } else {
          qb = qb.addOrderBy(field, direction);
        }
      }

      // Apply joins
      for (const join of query.joins) {
        qb = qb.leftJoinAndSelect(join.relation, join.alias);
      }

      // Apply pagination
      if (query.take !== undefined) {
        qb = qb.take(query.take);
      }
      if (query.skip !== undefined) {
        qb = qb.skip(query.skip);
      }

      const rows = await qb.getMany();

      // Rows are already filtered to allowedFields via the compiled query
      return {
        data: rows as Record<string, unknown>[],
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
    ctx: RunContext<TypeORMAdapterDataSource>,
    policy: Policy,
    schema: SchemaMetadata
  ): CompiledQuery<CompiledTypeORMQuery> {
    const engine = new PolicyEngine(policy, schema);
    const decision = engine.validateGet(request, ctx);

    const model = schema.models[request.model];
    if (!model) {
      throw new Error(`Model '${request.model}' not found in schema`);
    }

    // Build primary key filter with scope filters
    const pkFilter = { field: model.primaryKey, op: 'eq' as const, value: request.id };
    const allFilters = [pkFilter, ...decision.injectedFilters];

    // Compile includes
    const includes = request.include?.map((inc) => inc.relation) ?? [];

    const compiled = this.compiler.compileQuery({
      model: request.model,
      filters: allFilters,
      select: decision.allowedFields,
      includes,
      take: 1,
    });

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
    compiled: CompiledQuery<CompiledTypeORMQuery>,
    ctx: RunContext<TypeORMAdapterDataSource>
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
    ctx: RunContext<TypeORMAdapterDataSource>,
    policy: Policy,
    schema: SchemaMetadata
  ): CompiledQuery<CompiledTypeORMQuery> {
    const engine = new PolicyEngine(policy, schema);
    const decision = engine.validateAggregate(request, ctx);

    // Merge user filters with scope filters
    const allFilters = [
      ...(request.where ?? []),
      ...decision.injectedFilters,
    ];

    const compiled = this.compiler.compileQuery({
      model: request.model,
      filters: allFilters,
    });

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
    compiled: CompiledQuery<CompiledTypeORMQuery>,
    ctx: RunContext<TypeORMAdapterDataSource>
  ): Promise<AggregateResult> {
    const { query } = compiled;
    const request = compiled.request as AggregateRequest;
    const repo = this.getRepository(query.entityName, ctx);

    try {
      let qb = repo.createQueryBuilder(query.alias);

      // Apply where conditions
      for (let i = 0; i < query.whereConditions.length; i++) {
        const { condition, parameters } = query.whereConditions[i];
        if (i === 0) {
          qb = qb.where(condition, parameters);
        } else {
          qb = qb.andWhere(condition, parameters);
        }
      }

      let value: unknown = null;
      let rowCount = 0;

      switch (request.operation) {
        case 'count':
          value = await qb.getCount();
          rowCount = value as number;
          break;
        default: {
          // For other aggregates, fetch rows and compute client-side
          const rows = await qb.getMany() as Record<string, unknown>[];
          rowCount = rows.length;

          if (request.field) {
            switch (request.operation) {
              case 'sum':
                value = rows.reduce((sum, row) => sum + (Number(row[request.field!]) || 0), 0);
                break;
              case 'avg':
                if (rows.length > 0) {
                  value = rows.reduce((sum, row) => sum + (Number(row[request.field!]) || 0), 0) / rows.length;
                }
                break;
              case 'min':
                if (rows.length > 0) {
                  value = Math.min(...rows.map((row) => Number(row[request.field!]) || 0));
                }
                break;
              case 'max':
                if (rows.length > 0) {
                  value = Math.max(...rows.map((row) => Number(row[request.field!]) || 0));
                }
                break;
            }
          }
        }
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
    ctx: RunContext<TypeORMAdapterDataSource>,
    policy: Policy,
    schema: SchemaMetadata
  ): CompiledMutation<CompiledTypeORMMutation> {
    const engine = new PolicyEngine(policy, schema);
    const decision = engine.validateCreate(request, ctx);

    // Build data with scope injection
    const data = { ...request.data };
    for (const filter of decision.injectedFilters) {
      if (filter.op === 'eq') {
        data[filter.field] = filter.value;
      }
    }

    const compiled = this.compiler.compileInsert({
      model: request.model,
      data,
    });

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
    compiled: CompiledMutation<CompiledTypeORMMutation>,
    ctx: RunContext<TypeORMAdapterDataSource>
  ): Promise<CreateResult> {
    const { mutation } = compiled;
    const repo = this.getRepository(mutation.entityName, ctx);

    try {
      const result = await repo.save(mutation.data as Record<string, unknown>);

      return {
        data: result as Record<string, unknown>,
        id: (result as Record<string, unknown>)['id'],
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
    ctx: RunContext<TypeORMAdapterDataSource>,
    policy: Policy,
    schema: SchemaMetadata
  ): CompiledMutation<CompiledTypeORMMutation> {
    const engine = new PolicyEngine(policy, schema);
    const decision = engine.validateUpdate(request, ctx);

    const model = schema.models[request.model];
    if (!model) {
      throw new Error(`Model '${request.model}' not found in schema`);
    }

    // Build primary key filter with scope filters
    const pkFilter = { field: model.primaryKey, op: 'eq' as const, value: request.id };
    const allFilters = [pkFilter, ...decision.injectedFilters];

    const compiled = this.compiler.compileUpdate({
      model: request.model,
      data: request.data,
      filters: allFilters,
    });

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
    compiled: CompiledMutation<CompiledTypeORMMutation>,
    ctx: RunContext<TypeORMAdapterDataSource>
  ): Promise<UpdateResult> {
    const { mutation } = compiled;
    const request = compiled.request as UpdateRequest;
    const repo = this.getRepository(mutation.entityName, ctx);
    const schema = await this.introspect();
    const model = schema.models[mutation.entityName];
    const pkField = model.primaryKey;

    try {
      const result = await repo.update(
        { [pkField]: request.id } as unknown,
        mutation.data as Record<string, unknown>
      );

      // Fetch the updated record
      const updated = await repo.findOne({
        where: { [pkField]: request.id } as Record<string, unknown>,
      });

      return {
        data: updated as Record<string, unknown> | null,
        success: (result.affected ?? 0) > 0,
        found: (result.affected ?? 0) > 0,
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
    ctx: RunContext<TypeORMAdapterDataSource>,
    policy: Policy,
    schema: SchemaMetadata
  ): CompiledMutation<CompiledTypeORMMutation> {
    const engine = new PolicyEngine(policy, schema);
    const decision = engine.validateDelete(request, ctx);

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
      const compiled = this.compiler.compileUpdate({
        model: request.model,
        data: { [rowPolicy.softDeleteField!]: new Date() },
        filters: allFilters,
      });

      return {
        mutation: compiled,
        request,
        data: { [rowPolicy.softDeleteField!]: new Date() },
        injectedFilters: decision.injectedFilters,
        policyDecisions: [...decision.decisions, 'Using soft delete'],
        returnFields: [],
      };
    }

    const compiled = this.compiler.compileDelete({
      model: request.model,
      filters: allFilters,
    });

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
    compiled: CompiledMutation<CompiledTypeORMMutation>,
    ctx: RunContext<TypeORMAdapterDataSource>
  ): Promise<DeleteResult> {
    const { mutation } = compiled;
    const request = compiled.request as DeleteRequest;
    const repo = this.getRepository(mutation.entityName, ctx);
    const schema = await this.introspect();
    const model = schema.models[mutation.entityName];
    const pkField = model.primaryKey;

    try {
      if (mutation.type === 'update') {
        // Soft delete
        const result = await repo.update(
          { [pkField]: request.id } as unknown,
          mutation.data as Record<string, unknown>
        );

        return {
          success: (result.affected ?? 0) > 0,
          found: (result.affected ?? 0) > 0,
          softDeleted: true,
        };
      } else {
        // Hard delete
        const result = await repo.delete({ [pkField]: request.id } as unknown);

        return {
          success: (result.affected ?? 0) > 0,
          found: (result.affected ?? 0) > 0,
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
    ctx: RunContext<TypeORMAdapterDataSource>,
    policy: Policy,
    schema: SchemaMetadata
  ): CompiledMutation<CompiledTypeORMMutation> {
    const engine = new PolicyEngine(policy, schema);
    const decision = engine.validateBulkUpdate(request, ctx);

    const model = schema.models[request.model];
    if (!model) {
      throw new Error(`Model '${request.model}' not found in schema`);
    }

    // Build where clause with all IDs and scope filters
    const idsFilter = { field: model.primaryKey, op: 'in' as const, value: request.ids };
    const allFilters = [idsFilter, ...decision.injectedFilters];

    const compiled = this.compiler.compileUpdate({
      model: request.model,
      data: request.data,
      filters: allFilters,
    });

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
    compiled: CompiledMutation<CompiledTypeORMMutation>,
    ctx: RunContext<TypeORMAdapterDataSource>
  ): Promise<BulkUpdateResult> {
    const { mutation } = compiled;
    const repo = this.getRepository(mutation.entityName, ctx);

    try {
      // Build criteria from where conditions
      const criteria: Record<string, unknown> = {};
      for (const { parameters } of mutation.whereConditions) {
        Object.assign(criteria, parameters);
      }

      const result = await repo.update(
        criteria,
        mutation.data as Record<string, unknown>
      );

      return {
        updatedCount: result.affected ?? 0,
        success: (result.affected ?? 0) > 0,
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
    ctx: RunContext<TypeORMAdapterDataSource>,
    fn: () => Promise<T>
  ): Promise<T> {
    const ds = ctx.db ?? this.dataSource;
    return ds.transaction(async () => fn());
  }
}

/**
 * Create a TypeORM adapter.
 */
export function createTypeORMAdapter(config: TypeORMAdapterConfig): TypeORMAdapter {
  return new TypeORMAdapter(config);
}
