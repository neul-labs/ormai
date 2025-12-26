/**
 * Prisma schema introspection using DMMF.
 *
 * Extracts schema metadata from Prisma's Data Model Meta Format (DMMF).
 */

import type {
  FieldMetadata,
  FieldType,
  ModelMetadata,
  RelationMetadata,
  RelationType,
  SchemaMetadata,
} from '../../core/types.js';

/**
 * DMMF types (simplified for our needs).
 */
interface DMMFField {
  name: string;
  type: string;
  kind: 'scalar' | 'object' | 'enum' | 'unsupported';
  isList: boolean;
  isRequired: boolean;
  isId: boolean;
  hasDefaultValue: boolean;
  default?: unknown;
  relationName?: string;
  relationFromFields?: string[];
  relationToFields?: string[];
  documentation?: string;
}

interface DMMFModel {
  name: string;
  dbName: string | null;
  fields: DMMFField[];
  primaryKey?: {
    name: string | null;
    fields: string[];
  };
  documentation?: string;
}

interface DMMF {
  datamodel: {
    models: DMMFModel[];
    enums: Array<{ name: string; values: Array<{ name: string }> }>;
    types?: DMMFModel[];
  };
}

/**
 * Map Prisma types to our normalized field types.
 */
function mapFieldType(prismaType: string): FieldType {
  const typeMap: Record<string, FieldType> = {
    String: 'string',
    Int: 'integer',
    BigInt: 'integer',
    Float: 'float',
    Decimal: 'float',
    Boolean: 'boolean',
    DateTime: 'datetime',
    Date: 'date',
    Time: 'time',
    Json: 'json',
    Bytes: 'binary',
  };

  return typeMap[prismaType] ?? 'unknown';
}

/**
 * Determine relation type from Prisma field.
 */
function getRelationType(field: DMMFField, allModels: DMMFModel[]): RelationType {
  // Find the target model
  const targetModel = allModels.find((m) => m.name === field.type);
  if (!targetModel) {
    return field.isList ? 'one_to_many' : 'many_to_one';
  }

  // Find the back-reference field
  const backRefField = targetModel.fields.find(
    (f) => f.kind === 'object' && f.relationName === field.relationName
  );

  if (field.isList && backRefField?.isList) {
    return 'many_to_many';
  }
  if (field.isList) {
    return 'one_to_many';
  }
  if (backRefField?.isList) {
    return 'many_to_one';
  }
  return 'one_to_one';
}

/**
 * Extract field metadata from DMMF field.
 */
function extractFieldMetadata(field: DMMFField): FieldMetadata {
  return {
    name: field.name,
    fieldType: mapFieldType(field.type),
    nullable: !field.isRequired,
    primaryKey: field.isId,
    default: field.hasDefaultValue ? field.default : undefined,
    description: field.documentation,
  };
}

/**
 * Extract relation metadata from DMMF field.
 */
function extractRelationMetadata(field: DMMFField, allModels: DMMFModel[]): RelationMetadata {
  return {
    name: field.name,
    targetModel: field.type,
    relationType: getRelationType(field, allModels),
    foreignKey: field.relationFromFields?.[0],
    backPopulates: undefined, // Will be resolved later if needed
  };
}

/**
 * Extract model metadata from DMMF model.
 */
function extractModelMetadata(model: DMMFModel, allModels: DMMFModel[]): ModelMetadata {
  const fields: Record<string, FieldMetadata> = {};
  const relations: Record<string, RelationMetadata> = {};

  let primaryKey = 'id'; // Default
  const primaryKeys: string[] = [];

  for (const field of model.fields) {
    if (field.kind === 'scalar' || field.kind === 'enum') {
      fields[field.name] = extractFieldMetadata(field);
      if (field.isId) {
        primaryKey = field.name;
        primaryKeys.push(field.name);
      }
    } else if (field.kind === 'object') {
      relations[field.name] = extractRelationMetadata(field, allModels);
    }
  }

  // Handle composite primary key
  if (model.primaryKey?.fields && model.primaryKey.fields.length > 1) {
    primaryKey = model.primaryKey.fields[0];
    primaryKeys.length = 0;
    primaryKeys.push(...model.primaryKey.fields);
  }

  return {
    name: model.name,
    tableName: model.dbName ?? model.name,
    fields,
    relations,
    primaryKey,
    primaryKeys: primaryKeys.length > 1 ? primaryKeys : undefined,
    description: model.documentation,
  };
}

/**
 * Introspect a Prisma schema from DMMF.
 *
 * @param dmmf - The DMMF object from PrismaClient
 * @param modelFilter - Optional list of models to include
 * @returns Schema metadata
 */
export function introspectFromDMMF(dmmf: DMMF, modelFilter?: string[]): SchemaMetadata {
  const models: Record<string, ModelMetadata> = {};
  const allModels = dmmf.datamodel.models;

  for (const model of allModels) {
    if (modelFilter && !modelFilter.includes(model.name)) {
      continue;
    }
    models[model.name] = extractModelMetadata(model, allModels);
  }

  return { models };
}

/**
 * Get DMMF from a Prisma client instance.
 *
 * This accesses the internal DMMF structure. The exact path may vary
 * between Prisma versions.
 */
export function getDMMF(prismaClient: unknown): DMMF | undefined {
  // Try different known paths for DMMF access
  const client = prismaClient as Record<string, unknown>;

  // Prisma 5.x
  if (client['_baseDmmf']) {
    return client['_baseDmmf'] as DMMF;
  }

  // Prisma 4.x
  if (client['_dmmf']) {
    return client['_dmmf'] as DMMF;
  }

  // Alternative path
  const engineConfig = client['_engineConfig'] as Record<string, unknown> | undefined;
  if (engineConfig?.['document']) {
    return { datamodel: engineConfig['document'] as DMMF['datamodel'] };
  }

  return undefined;
}

/**
 * Introspect schema directly from a Prisma client.
 */
export function introspectPrismaClient(
  prismaClient: unknown,
  modelFilter?: string[]
): SchemaMetadata {
  const dmmf = getDMMF(prismaClient);
  if (!dmmf) {
    throw new Error(
      'Could not extract DMMF from Prisma client. Ensure you are using Prisma 4.x or 5.x.'
    );
  }
  return introspectFromDMMF(dmmf, modelFilter);
}
