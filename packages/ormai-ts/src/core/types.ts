/**
 * Core type definitions for OrmAI.
 *
 * These types define the schema metadata structure that adapters must produce
 * and that the policy engine and tools consume.
 */

/**
 * Supported field types across all ORMs.
 */
export type FieldType =
  | 'string'
  | 'integer'
  | 'float'
  | 'boolean'
  | 'datetime'
  | 'date'
  | 'time'
  | 'uuid'
  | 'json'
  | 'binary'
  | 'unknown';

/**
 * Relation cardinality types.
 */
export type RelationType =
  | 'one_to_one'
  | 'one_to_many'
  | 'many_to_one'
  | 'many_to_many';

/**
 * Aggregate operation types.
 */
export type AggregateOp = 'count' | 'sum' | 'avg' | 'min' | 'max';

/**
 * Metadata for a single field in a model.
 */
export interface FieldMetadata {
  /** Field name */
  name: string;

  /** Field data type */
  fieldType: FieldType;

  /** Whether the field can be null */
  nullable: boolean;

  /** Whether this field is a primary key */
  primaryKey: boolean;

  /** Default value if any */
  default?: unknown;

  /** Human-readable description */
  description?: string;
}

/**
 * Metadata for a relation between models.
 */
export interface RelationMetadata {
  /** Relation name (property name on the model) */
  name: string;

  /** Target model name */
  targetModel: string;

  /** Cardinality of the relation */
  relationType: RelationType;

  /** Foreign key field name (on the source or target) */
  foreignKey?: string;

  /** Back-populates field name on the target model */
  backPopulates?: string;
}

/**
 * Metadata for a single model/entity.
 */
export interface ModelMetadata {
  /** Model/entity name */
  name: string;

  /** Database table name */
  tableName: string;

  /** Fields available on this model */
  fields: Record<string, FieldMetadata>;

  /** Relations to other models */
  relations: Record<string, RelationMetadata>;

  /** Primary key field name */
  primaryKey: string;

  /** Composite primary key field names (if applicable) */
  primaryKeys?: string[];

  /** Human-readable description */
  description?: string;
}

/**
 * Complete schema metadata for an ORM.
 */
export interface SchemaMetadata {
  /** All models in the schema */
  models: Record<string, ModelMetadata>;
}

/**
 * Helper functions for working with schema metadata.
 */
export const SchemaMetadataUtils = {
  /**
   * Get a model by name.
   */
  getModel(schema: SchemaMetadata, name: string): ModelMetadata | undefined {
    return schema.models[name];
  },

  /**
   * List all model names.
   */
  listModels(schema: SchemaMetadata): string[] {
    return Object.keys(schema.models);
  },

  /**
   * Get all field names for a model.
   */
  getFieldNames(schema: SchemaMetadata, modelName: string): string[] {
    const model = schema.models[modelName];
    return model ? Object.keys(model.fields) : [];
  },

  /**
   * Get all relation names for a model.
   */
  getRelationNames(schema: SchemaMetadata, modelName: string): string[] {
    const model = schema.models[modelName];
    return model ? Object.keys(model.relations) : [];
  },

  /**
   * Check if a field exists on a model.
   */
  hasField(schema: SchemaMetadata, modelName: string, fieldName: string): boolean {
    const model = schema.models[modelName];
    return model ? fieldName in model.fields : false;
  },

  /**
   * Check if a relation exists on a model.
   */
  hasRelation(schema: SchemaMetadata, modelName: string, relationName: string): boolean {
    const model = schema.models[modelName];
    return model ? relationName in model.relations : false;
  },
};
