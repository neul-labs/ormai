/**
 * Abstract base adapter interface.
 *
 * All ORM adapters must implement this interface to be compatible with OrmAI.
 */

import type { RunContext } from '../core/context.js';
import type {
  AggregateRequest,
  AggregateResult,
  BulkUpdateRequest,
  BulkUpdateResult,
  CreateRequest,
  CreateResult,
  DeleteRequest,
  DeleteResult,
  FilterClause,
  GetRequest,
  GetResult,
  QueryRequest,
  QueryResult,
  UpdateRequest,
  UpdateResult,
} from '../core/dsl.js';
import { AdapterNotImplementedError } from '../core/errors.js';
import type { SchemaMetadata } from '../core/types.js';
import type { Policy } from '../policy/models.js';

/**
 * Result of query compilation.
 *
 * Contains the ORM-specific query object and metadata needed for execution.
 */
export interface CompiledQuery<T = unknown> {
  /** The compiled query object (type depends on adapter) */
  query: T;

  /** Original request for reference */
  request: QueryRequest | GetRequest | AggregateRequest;

  /** Fields to select (after policy filtering) */
  selectFields: string[];

  /** Filters injected by policy (for auditing) */
  injectedFilters: FilterClause[];

  /** Policy decisions made during compilation */
  policyDecisions: string[];

  /** Statement timeout in milliseconds */
  timeoutMs?: number;
}

/**
 * Result of mutation compilation.
 */
export interface CompiledMutation<T = unknown> {
  /** The compiled mutation object (type depends on adapter) */
  mutation: T;

  /** Original request for reference */
  request: CreateRequest | UpdateRequest | DeleteRequest | BulkUpdateRequest;

  /** Data to write (after policy filtering and scope injection) */
  data?: Record<string, unknown>;

  /** Filters injected by policy (for scoping) */
  injectedFilters: FilterClause[];

  /** Policy decisions made during compilation */
  policyDecisions: string[];

  /** Fields to return after mutation */
  returnFields: string[];
}

/**
 * Create a new CompiledQuery with default values.
 */
export function createCompiledQuery<T>(
  query: T,
  request: QueryRequest | GetRequest | AggregateRequest
): CompiledQuery<T> {
  return {
    query,
    request,
    selectFields: [],
    injectedFilters: [],
    policyDecisions: [],
  };
}

/**
 * Create a new CompiledMutation with default values.
 */
export function createCompiledMutation<T>(
  mutation: T,
  request: CreateRequest | UpdateRequest | DeleteRequest | BulkUpdateRequest
): CompiledMutation<T> {
  return {
    mutation,
    request,
    injectedFilters: [],
    policyDecisions: [],
    returnFields: [],
  };
}

/**
 * Abstract interface for ORM adapters.
 *
 * Adapters are responsible for:
 * 1. Schema introspection
 * 2. Query compilation (DSL -> ORM query)
 * 3. Query execution
 * 4. Session/transaction management
 */
export interface OrmAdapter<DB = unknown, CompiledT = unknown, MutationT = unknown> {
  /**
   * Introspect the database schema.
   *
   * Returns metadata about all models, fields, relations, and types.
   * This is called once at startup and cached.
   */
  introspect(): Promise<SchemaMetadata>;

  /**
   * Compile a query request into an ORM-specific query.
   *
   * This method:
   * 1. Validates the request against policies
   * 2. Injects scope filters
   * 3. Builds the ORM query
   * 4. Returns a CompiledQuery with the result
   *
   * Throws policy errors if validation fails.
   */
  compileQuery(
    request: QueryRequest,
    ctx: RunContext<DB>,
    policy: Policy,
    schema: SchemaMetadata
  ): CompiledQuery<CompiledT>;

  /**
   * Compile a get-by-id request into an ORM-specific query.
   */
  compileGet(
    request: GetRequest,
    ctx: RunContext<DB>,
    policy: Policy,
    schema: SchemaMetadata
  ): CompiledQuery<CompiledT>;

  /**
   * Compile an aggregation request into an ORM-specific query.
   */
  compileAggregate(
    request: AggregateRequest,
    ctx: RunContext<DB>,
    policy: Policy,
    schema: SchemaMetadata
  ): CompiledQuery<CompiledT>;

  /**
   * Execute a compiled query and return results.
   *
   * Results are returned as dicts with field redaction already applied.
   */
  executeQuery(compiled: CompiledQuery<CompiledT>, ctx: RunContext<DB>): Promise<QueryResult>;

  /**
   * Execute a compiled get request and return the result.
   */
  executeGet(compiled: CompiledQuery<CompiledT>, ctx: RunContext<DB>): Promise<GetResult>;

  /**
   * Execute a compiled aggregation and return the result.
   */
  executeAggregate(
    compiled: CompiledQuery<CompiledT>,
    ctx: RunContext<DB>
  ): Promise<AggregateResult>;

  /**
   * Execute a function within a transaction.
   *
   * The transaction is committed if the function completes successfully,
   * or rolled back if an exception is raised.
   */
  transaction<T>(ctx: RunContext<DB>, fn: () => Promise<T>): Promise<T>;

  // =========================================================================
  // MUTATION METHODS
  // =========================================================================

  /**
   * Compile a create request.
   *
   * Validates write permissions and prepares the insert statement.
   */
  compileCreate(
    request: CreateRequest,
    ctx: RunContext<DB>,
    policy: Policy,
    schema: SchemaMetadata
  ): CompiledMutation<MutationT>;

  /**
   * Compile an update request.
   *
   * Validates write permissions and prepares the update statement.
   */
  compileUpdate(
    request: UpdateRequest,
    ctx: RunContext<DB>,
    policy: Policy,
    schema: SchemaMetadata
  ): CompiledMutation<MutationT>;

  /**
   * Compile a delete request.
   *
   * Validates delete permissions and prepares the delete statement.
   */
  compileDelete(
    request: DeleteRequest,
    ctx: RunContext<DB>,
    policy: Policy,
    schema: SchemaMetadata
  ): CompiledMutation<MutationT>;

  /**
   * Compile a bulk update request.
   *
   * Validates bulk operation permissions and prepares the update statements.
   */
  compileBulkUpdate(
    request: BulkUpdateRequest,
    ctx: RunContext<DB>,
    policy: Policy,
    schema: SchemaMetadata
  ): CompiledMutation<MutationT>;

  /**
   * Execute a compiled create request.
   */
  executeCreate(compiled: CompiledMutation<MutationT>, ctx: RunContext<DB>): Promise<CreateResult>;

  /**
   * Execute a compiled update request.
   */
  executeUpdate(compiled: CompiledMutation<MutationT>, ctx: RunContext<DB>): Promise<UpdateResult>;

  /**
   * Execute a compiled delete request.
   */
  executeDelete(compiled: CompiledMutation<MutationT>, ctx: RunContext<DB>): Promise<DeleteResult>;

  /**
   * Execute a compiled bulk update request.
   */
  executeBulkUpdate(
    compiled: CompiledMutation<MutationT>,
    ctx: RunContext<DB>
  ): Promise<BulkUpdateResult>;
}

/**
 * Base class for ORM adapters with default implementations.
 *
 * Provides no-op implementations for mutation methods that can be overridden.
 */
export abstract class BaseOrmAdapter<DB = unknown, CompiledT = unknown, MutationT = unknown>
  implements OrmAdapter<DB, CompiledT, MutationT>
{
  abstract introspect(): Promise<SchemaMetadata>;

  abstract compileQuery(
    request: QueryRequest,
    ctx: RunContext<DB>,
    policy: Policy,
    schema: SchemaMetadata
  ): CompiledQuery<CompiledT>;

  abstract compileGet(
    request: GetRequest,
    ctx: RunContext<DB>,
    policy: Policy,
    schema: SchemaMetadata
  ): CompiledQuery<CompiledT>;

  abstract compileAggregate(
    request: AggregateRequest,
    ctx: RunContext<DB>,
    policy: Policy,
    schema: SchemaMetadata
  ): CompiledQuery<CompiledT>;

  abstract executeQuery(
    compiled: CompiledQuery<CompiledT>,
    ctx: RunContext<DB>
  ): Promise<QueryResult>;

  abstract executeGet(compiled: CompiledQuery<CompiledT>, ctx: RunContext<DB>): Promise<GetResult>;

  abstract executeAggregate(
    compiled: CompiledQuery<CompiledT>,
    ctx: RunContext<DB>
  ): Promise<AggregateResult>;

  abstract transaction<T>(ctx: RunContext<DB>, fn: () => Promise<T>): Promise<T>;

  // Default mutation implementations that throw NotImplementedError
  compileCreate(
    _request: CreateRequest,
    _ctx: RunContext<DB>,
    _policy: Policy,
    _schema: SchemaMetadata
  ): CompiledMutation<MutationT> {
    throw new AdapterNotImplementedError('Create', this.constructor.name);
  }

  compileUpdate(
    _request: UpdateRequest,
    _ctx: RunContext<DB>,
    _policy: Policy,
    _schema: SchemaMetadata
  ): CompiledMutation<MutationT> {
    throw new AdapterNotImplementedError('Update', this.constructor.name);
  }

  compileDelete(
    _request: DeleteRequest,
    _ctx: RunContext<DB>,
    _policy: Policy,
    _schema: SchemaMetadata
  ): CompiledMutation<MutationT> {
    throw new AdapterNotImplementedError('Delete', this.constructor.name);
  }

  compileBulkUpdate(
    _request: BulkUpdateRequest,
    _ctx: RunContext<DB>,
    _policy: Policy,
    _schema: SchemaMetadata
  ): CompiledMutation<MutationT> {
    throw new AdapterNotImplementedError('Bulk update', this.constructor.name);
  }

  executeCreate(
    _compiled: CompiledMutation<MutationT>,
    _ctx: RunContext<DB>
  ): Promise<CreateResult> {
    throw new AdapterNotImplementedError('Create', this.constructor.name);
  }

  executeUpdate(
    _compiled: CompiledMutation<MutationT>,
    _ctx: RunContext<DB>
  ): Promise<UpdateResult> {
    throw new AdapterNotImplementedError('Update', this.constructor.name);
  }

  executeDelete(
    _compiled: CompiledMutation<MutationT>,
    _ctx: RunContext<DB>
  ): Promise<DeleteResult> {
    throw new AdapterNotImplementedError('Delete', this.constructor.name);
  }

  executeBulkUpdate(
    _compiled: CompiledMutation<MutationT>,
    _ctx: RunContext<DB>
  ): Promise<BulkUpdateResult> {
    throw new AdapterNotImplementedError('Bulk update', this.constructor.name);
  }
}
