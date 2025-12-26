/**
 * Drizzle ORM schema introspection.
 */

import type {
  FieldMetadata,
  FieldType,
  ModelMetadata,
  RelationMetadata,
  SchemaMetadata,
} from '../../core/types.js';

/**
 * Drizzle table type.
 */
export interface DrizzleTable {
  [key: string]: unknown;
  _: {
    name: string;
    columns: Record<string, DrizzleColumn>;
  };
}

/**
 * Drizzle column type.
 */
export interface DrizzleColumn {
  name: string;
  dataType: string;
  notNull: boolean;
  primary?: boolean;
  default?: unknown;
  columnType?: string;
}

/**
 * Drizzle relation definition.
 */
export interface DrizzleRelation {
  referencedTableName: string;
  fieldName: string;
  relationType: 'one' | 'many';
}

/**
 * Drizzle schema type (record of table names to tables).
 */
export type DrizzleSchema = Record<string, DrizzleTable>;

/**
 * Drizzle introspector for converting Drizzle schemas to OrmAI metadata.
 */
export class DrizzleIntrospector {
  private readonly schema: DrizzleSchema;
  private readonly relations: Record<string, DrizzleRelation[]>;

  constructor(schema: DrizzleSchema, relations?: Record<string, DrizzleRelation[]>) {
    this.schema = schema;
    this.relations = relations ?? {};
  }

  /**
   * Convert Drizzle schema to OrmAI SchemaMetadata.
   */
  introspect(): SchemaMetadata {
    const models: Record<string, ModelMetadata> = {};

    for (const [tableName, table] of Object.entries(this.schema)) {
      if (!table._ || !table._.columns) {
        continue;
      }

      const modelName = this.tableNameToModelName(tableName);
      const fields: Record<string, FieldMetadata> = {};
      let primaryKey = 'id';
      const primaryKeys: string[] = [];

      // Process columns
      for (const [columnName, column] of Object.entries(table._.columns)) {
        fields[columnName] = {
          name: columnName,
          fieldType: this.mapColumnType(column.dataType, column.columnType),
          nullable: !column.notNull,
          primaryKey: column.primary ?? false,
          default: column.default,
        };

        if (column.primary) {
          primaryKey = columnName;
          primaryKeys.push(columnName);
        }
      }

      // Process relations
      const relations: Record<string, RelationMetadata> = {};
      const tableRelations = this.relations[tableName] ?? [];
      for (const rel of tableRelations) {
        relations[rel.fieldName] = {
          name: rel.fieldName,
          relationType: rel.relationType === 'many' ? 'one_to_many' : 'many_to_one',
          targetModel: this.tableNameToModelName(rel.referencedTableName),
          foreignKey: rel.fieldName,
        };
      }

      models[modelName] = {
        name: modelName,
        tableName: table._.name || tableName,
        fields,
        relations,
        primaryKey,
        ...(primaryKeys.length > 1 ? { primaryKeys } : {}),
      };
    }

    return { models };
  }

  /**
   * Convert table name to model name (PascalCase).
   */
  private tableNameToModelName(tableName: string): string {
    return tableName
      .split('_')
      .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
      .join('');
  }

  /**
   * Map Drizzle column type to OrmAI field type.
   */
  private mapColumnType(dataType: string, columnType?: string): FieldType {
    const dt = (columnType || dataType).toLowerCase();

    // String types
    if (dt.includes('varchar') || dt.includes('char') || dt.includes('text') || dt === 'string') {
      return 'string';
    }

    // Integer types
    if (
      dt.includes('int') ||
      dt === 'serial' ||
      dt === 'smallserial' ||
      dt === 'bigserial' ||
      dt === 'integer' ||
      dt === 'number'
    ) {
      return 'integer';
    }

    // Float types
    if (
      dt.includes('float') ||
      dt.includes('double') ||
      dt.includes('decimal') ||
      dt.includes('numeric') ||
      dt.includes('real')
    ) {
      return 'float';
    }

    // Boolean
    if (dt.includes('bool')) {
      return 'boolean';
    }

    // Date/Time
    if (dt.includes('timestamp') || dt.includes('datetime')) {
      return 'datetime';
    }
    if (dt.includes('date')) {
      return 'date';
    }
    if (dt.includes('time')) {
      return 'time';
    }

    // JSON
    if (dt.includes('json')) {
      return 'json';
    }

    // UUID
    if (dt.includes('uuid')) {
      return 'uuid';
    }

    // Binary - map to string since bytes is not a valid type
    if (dt.includes('bytea') || dt.includes('blob') || dt.includes('binary')) {
      return 'string';
    }

    // Default
    return 'string';
  }
}

/**
 * Create a DrizzleIntrospector from a Drizzle schema.
 */
export function createDrizzleIntrospector(
  schema: DrizzleSchema,
  relations?: Record<string, DrizzleRelation[]>
): DrizzleIntrospector {
  return new DrizzleIntrospector(schema, relations);
}
