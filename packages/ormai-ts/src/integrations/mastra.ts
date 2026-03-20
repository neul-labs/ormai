/**
 * Mastra integration.
 *
 * Converts OrmAI tools to Mastra tool format.
 */

import { zodToJsonSchema } from 'zod-to-json-schema';
import type { RunContext } from '../core/context.js';
import type { Tool } from '../tools/base.js';

/**
 * Mastra tool definition.
 */
export interface MastraToolDefinition {
  name: string;
  description: string;
  inputSchema: Record<string, unknown>;
  execute: (input: Record<string, unknown>) => Promise<unknown>;
}

/**
 * Convert OrmAI tools to Mastra tool definitions.
 *
 * @param tools - OrmAI tools to convert
 * @param ctx - Run context for execution
 * @returns Array of Mastra tool definitions
 */
export function toMastraTools<T extends Tool<unknown, unknown>[]>(
  tools: T,
  ctx: RunContext
): MastraToolDefinition[] {
  return tools.map((tool) => ({
    name: tool.name,
    description: tool.description,
    inputSchema: zodToJsonSchema(tool.inputSchema),
    execute: async (input: Record<string, unknown>) => {
      return tool.execute(input, ctx);
    },
  }));
}

/**
 * Create Mastra tools using the @mastra/core package.
 *
 * This function attempts to dynamically import the package.
 * If it's not installed, it throws an error.
 *
 * Usage with Mastra:
 * ```ts
 * import { Agent } from '@mastra/core';
 *
 * const tools = await createMastraTools(registry.list(), ctx);
 * const agent = new Agent({ tools });
 * ```
 */
export async function createMastraTools<T extends Tool<unknown, unknown>[]>(
  tools: T,
  ctx: RunContext
): Promise<unknown[]> {
  try {
    const mastra = await import('@mastra/core');
    const createTool = mastra.createTool ?? (mastra as { default: { createTool: unknown } }).default?.createTool;

    if (!createTool) {
      throw new Error('createTool not found in @mastra/core');
    }

    return tools.map((tool) =>
      (createTool as Function)({
        name: tool.name,
        description: tool.description,
        inputSchema: tool.inputSchema,
        execute: async (input: Record<string, unknown>) => {
          return tool.execute(input, ctx);
        },
      })
    );
  } catch (e) {
    if ((e as Error).message?.includes('@mastra/core')) {
      throw e;
    }
    throw new Error('Failed to import @mastra/core. Make sure it is installed: npm install @mastra/core');
  }
}
