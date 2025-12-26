/**
 * LangChain.js integration.
 *
 * Converts OrmAI tools to LangChain tool format.
 */

import { zodToJsonSchema } from 'zod-to-json-schema';
import type { RunContext } from '../core/context.js';
import type { Tool } from '../tools/base.js';

/**
 * LangChain tool definition interface.
 */
export interface LangChainToolDefinition {
  name: string;
  description: string;
  schema: Record<string, unknown>;
  func: (input: unknown) => Promise<string>;
}

/**
 * Convert OrmAI tools to LangChain DynamicStructuredTool format.
 *
 * @param tools - OrmAI tools to convert
 * @param ctx - Run context for execution
 * @returns Array of LangChain tool definitions
 */
export function toLangChainTools<T extends Tool<unknown, unknown>[]>(
  tools: T,
  ctx: RunContext
): LangChainToolDefinition[] {
  return tools.map((tool) => ({
    name: tool.name,
    description: tool.description,
    schema: zodToJsonSchema(tool.inputSchema),
    func: async (input: unknown) => {
      const result = await tool.execute(input, ctx);
      return JSON.stringify(result);
    },
  }));
}

/**
 * Create LangChain DynamicStructuredTool instances.
 *
 * Usage with LangChain.js:
 * ```ts
 * import { DynamicStructuredTool } from '@langchain/core/tools';
 *
 * const toolDefs = toLangChainToolDefinitions(registry.list(), ctx);
 *
 * const tools = toolDefs.map(def => new DynamicStructuredTool({
 *   name: def.name,
 *   description: def.description,
 *   schema: def.schema,
 *   func: def.func,
 * }));
 * ```
 */
export function toLangChainToolDefinitions<T extends Tool<unknown, unknown>[]>(
  tools: T,
  ctx: RunContext
): LangChainToolDefinition[] {
  return toLangChainTools(tools, ctx);
}

/**
 * Create LangChain tools using the @langchain/core package.
 *
 * This function attempts to dynamically import the package.
 * If it's not installed, it throws an error.
 */
export async function createLangChainTools<T extends Tool<unknown, unknown>[]>(
  tools: T,
  ctx: RunContext
): Promise<unknown[]> {
  try {
    // Dynamic import to avoid hard dependency
    const { DynamicStructuredTool } = await import('@langchain/core/tools');

    return tools.map(
      (tool) =>
        new DynamicStructuredTool({
          name: tool.name,
          description: tool.description,
          schema: tool.inputSchema,
          func: async (input: unknown) => {
            const result = await tool.execute(input, ctx);
            return JSON.stringify(result);
          },
        })
    );
  } catch (e) {
    throw new Error(
      'Failed to import @langchain/core. Make sure it is installed: npm install @langchain/core'
    );
  }
}
