/**
 * TypeORM adapter module for OrmAI.
 */

// Introspection
export {
  type TypeORMColumnMetadata,
  type TypeORMRelationMetadata,
  type TypeORMEntityMetadata,
  type TypeORMDataSource,
  TypeORMIntrospector,
  createTypeORMIntrospector,
} from './introspection.js';

// Compiler
export {
  type TypeORMQueryBuilder,
  type CompiledTypeORMQuery,
  type CompiledTypeORMMutation,
  TypeORMCompiler,
  createTypeORMCompiler,
} from './compiler.js';

// Adapter
export {
  type TypeORMRepository,
  type TypeORMFindOptions,
  type TypeORMSelectQueryBuilder,
  type TypeORMUpdateResult,
  type TypeORMDeleteResult,
  type TypeORMEntityManager,
  type TypeORMAdapterDataSource,
  type TypeORMAdapterConfig,
  TypeORMAdapter,
  createTypeORMAdapter,
} from './adapter.js';
