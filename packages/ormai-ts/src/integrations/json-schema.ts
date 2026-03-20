/**
 * JSON Schema export for universal compatibility.
 *
 * Exports OrmAI tools as JSON Schema for use with any framework.
 */

import { zodToJsonSchema } from 'zod-to-json-schema';
import type { Tool } from '../tools/base.js';

/**
 * JSON Schema tool definition.
 */
export interface JsonSchemaTool {
  name: string;
  description: string;
  inputSchema: Record<string, unknown>;
}

/**
 * Convert a single OrmAI tool to JSON Schema format.
 *
 * @param tool - OrmAI tool to convert
 * @returns JSON Schema tool definition
 */
export function toJsonSchema<Input, Output>(tool: Tool<Input, Output>): JsonSchemaTool {
  return {
    name: tool.name,
    description: tool.description,
    inputSchema: zodToJsonSchema(tool.inputSchema),
  };
}

/**
 * Convert multiple OrmAI tools to JSON Schema format.
 *
 * @param tools - OrmAI tools to convert
 * @returns Array of JSON Schema tool definitions
 */
export function toJsonSchemas<T extends Tool<unknown, unknown>[]>(tools: T): JsonSchemaTool[] {
  return tools.map((tool) => toJsonSchema(tool));
}

/**
 * Export tools as a JSON-serializable schema document.
 *
 * This is useful for:
 * - Generating documentation
 * - Sharing schemas with other systems
 * - Storing tool definitions
 */
export function exportToolSchemas<T extends Tool<unknown, unknown>[]>(
  tools: T
): {
  version: string;
  tools: JsonSchemaTool[];
} {
  return {
    version: '1.0',
    tools: toJsonSchemas(tools),
  };
}

/**
 * Convert JSON Schema tools to a map by name.
 */
export function toolSchemasToMap(tools: JsonSchemaTool[]): Map<string, JsonSchemaTool> {
  return new Map(tools.map((t) => [t.name, t]));
}
