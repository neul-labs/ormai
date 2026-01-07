/**
 * Drizzle ORM adapter module for OrmAI.
 */

// Introspection
export {
  type DrizzleTable,
  type DrizzleColumn,
  type DrizzleRelation,
  type DrizzleSchema,
  DrizzleIntrospector,
  createDrizzleIntrospector,
} from './introspection.js';

// Compiler
export {
  type DrizzleOperators,
  type DrizzleTableRef,
  type CompiledDrizzleQuery,
  type CompiledDrizzleMutation,
  DrizzleCompiler,
  createDrizzleCompiler,
} from './compiler.js';

// Adapter
export {
  type DrizzleDB,
  type DrizzleQueryBuilder,
  type DrizzleInsertBuilder,
  type DrizzleUpdateBuilder,
  type DrizzleDeleteBuilder,
  type DrizzleAdapterConfig,
  DrizzleAdapter,
  createDrizzleAdapter,
} from './adapter.js';
