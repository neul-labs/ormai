/**
 * ORM adapters for OrmAI.
 */

// Base adapter
export {
  type CompiledQuery,
  type CompiledMutation,
  type OrmAdapter,
  BaseOrmAdapter,
  createCompiledQuery,
  createCompiledMutation,
} from './base.js';

// Re-export Prisma adapter
export * from './prisma/index.js';

// Re-export Drizzle adapter
export * from './drizzle/index.js';

// Re-export TypeORM adapter
export * from './typeorm/index.js';
