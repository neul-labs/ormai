/**
 * TypeORM schema introspection.
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
 * TypeORM column metadata.
 */
export interface TypeORMColumnMetadata {
  propertyName: string;
  databaseName: string;
  type: string | Function;
  isPrimary: boolean;
  isNullable: boolean;
  default?: unknown;
}

/**
 * TypeORM relation metadata.
 */
export interface TypeORMRelationMetadata {
  propertyName: string;
  relationType: 'one-to-one' | 'one-to-many' | 'many-to-one' | 'many-to-many';
  inverseSidePropertyPath?: string;
  type: string | Function;
}

/**
 * TypeORM entity metadata.
 */
export interface TypeORMEntityMetadata {
  name: string;
  tableName: string;
  columns: TypeORMColumnMetadata[];
  relations: TypeORMRelationMetadata[];
  primaryColumns: TypeORMColumnMetadata[];
}

/**
 * TypeORM data source for introspection.
 */
export interface TypeORMDataSource {
  entityMetadatas: TypeORMEntityMetadata[];
  getMetadata: (entity: string | Function) => TypeORMEntityMetadata;
}

/**
 * TypeORM introspector for converting TypeORM metadata to OrmAI metadata.
 */
export class TypeORMIntrospector {
  private readonly dataSource: TypeORMDataSource;
  private readonly modelFilter?: string[];

  constructor(dataSource: TypeORMDataSource, models?: string[]) {
    this.dataSource = dataSource;
    this.modelFilter = models;
  }

  /**
   * Convert TypeORM metadata to OrmAI SchemaMetadata.
   */
  introspect(): SchemaMetadata {
    const models: Record<string, ModelMetadata> = {};

    for (const entityMetadata of this.dataSource.entityMetadatas) {
      const modelName = entityMetadata.name;

      // Filter models if specified
      if (this.modelFilter && !this.modelFilter.includes(modelName)) {
        continue;
      }

      const fields: Record<string, FieldMetadata> = {};
      const primaryKeys: string[] = [];

      // Process columns
      for (const column of entityMetadata.columns) {
        fields[column.propertyName] = {
          name: column.propertyName,
          fieldType: this.mapColumnType(column.type),
          nullable: column.isNullable,
          primaryKey: column.isPrimary,
          default: column.default,
        };

        if (column.isPrimary) {
          primaryKeys.push(column.propertyName);
        }
      }

      // Process relations
      const relations: Record<string, RelationMetadata> = {};
      for (const relation of entityMetadata.relations) {
        const targetName = typeof relation.type === 'function'
          ? (relation.type as Function).name
          : String(relation.type);

        relations[relation.propertyName] = {
          name: relation.propertyName,
          relationType: this.mapRelationType(relation.relationType),
          targetModel: targetName,
          foreignKey: relation.inverseSidePropertyPath,
        };
      }

      const primaryKey = primaryKeys.length > 0 ? primaryKeys[0] : 'id';

      models[modelName] = {
        name: modelName,
        tableName: entityMetadata.tableName,
        fields,
        relations,
        primaryKey,
        primaryKeys: primaryKeys.length > 1 ? primaryKeys : undefined,
      };
    }

    return { models };
  }

  /**
   * Map TypeORM column type to OrmAI field type.
   */
  private mapColumnType(type: string | Function): FieldType {
    const typeStr = typeof type === 'function' ? type.name.toLowerCase() : String(type).toLowerCase();

    // String types
    if (typeStr === 'string' || typeStr.includes('varchar') || typeStr.includes('char') || typeStr.includes('text')) {
      return 'string';
    }

    // Integer types
    if (typeStr === 'number' || typeStr.includes('int') || typeStr === 'integer') {
      return 'integer';
    }

    // Float types
    if (typeStr.includes('float') || typeStr.includes('double') || typeStr.includes('decimal') || typeStr.includes('numeric')) {
      return 'float';
    }

    // Boolean
    if (typeStr === 'boolean' || typeStr === 'bool') {
      return 'boolean';
    }

    // Date/Time
    if (typeStr === 'date') {
      return 'date';
    }
    if (typeStr.includes('timestamp') || typeStr.includes('datetime')) {
      return 'datetime';
    }
    if (typeStr.includes('time')) {
      return 'time';
    }

    // JSON
    if (typeStr === 'json' || typeStr === 'jsonb' || typeStr === 'object') {
      return 'json';
    }

    // UUID
    if (typeStr === 'uuid') {
      return 'uuid';
    }

    // Binary - map to string since bytes is not a valid type
    if (typeStr.includes('blob') || typeStr.includes('binary') || typeStr === 'buffer') {
      return 'string';
    }

    // Default
    return 'string';
  }

  /**
   * Map TypeORM relation type to OrmAI relation type.
   */
  private mapRelationType(type: string): RelationType {
    switch (type) {
      case 'one-to-one':
        return 'one_to_one';
      case 'one-to-many':
        return 'one_to_many';
      case 'many-to-one':
        return 'many_to_one';
      case 'many-to-many':
        return 'many_to_many';
      default:
        return 'many_to_one';
    }
  }
}

/**
 * Create a TypeORM introspector.
 */
export function createTypeORMIntrospector(
  dataSource: TypeORMDataSource,
  models?: string[]
): TypeORMIntrospector {
  return new TypeORMIntrospector(dataSource, models);
}
