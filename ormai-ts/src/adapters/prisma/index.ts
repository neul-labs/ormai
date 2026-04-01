/**
 * Prisma adapter for OrmAI.
 */

export {
  PrismaAdapter,
  createPrismaAdapter,
  type PrismaAdapterOptions,
  type PrismaClientLike,
} from './adapter.js';

export {
  introspectFromDMMF,
  introspectPrismaClient,
  getDMMF,
} from './introspection.js';

export {
  PrismaCompiler,
  defaultCompiler,
  type PrismaWhereInput,
  type PrismaOrderByInput,
  type PrismaIncludeInput,
  type PrismaSelectInput,
  type PrismaFindManyArgs,
  type PrismaFindUniqueArgs,
  type PrismaAggregateArgs,
  type PrismaCreateArgs,
  type PrismaUpdateArgs,
  type PrismaDeleteArgs,
} from './compiler.js';
