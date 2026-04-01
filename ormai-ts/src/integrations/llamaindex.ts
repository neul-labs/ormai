/**
 * LlamaIndex.ts integration.
 *
 * Converts OrmAI tools to LlamaIndex FunctionTool format.
 */

import { zodToJsonSchema } from 'zod-to-json-schema';
import type { RunContext } from '../core/context.js';
import type { Tool } from '../tools/base.js';

/**
 * LlamaIndex tool definition.
 */
export interface LlamaIndexToolDefinition {
  name: string;
  description: string;
  parameters: Record<string, unknown>;
  fn: (input: Record<string, unknown>) => Promise<string>;
}

/**
 * Convert OrmAI tools to LlamaIndex tool definitions.
 *
 * @param tools - OrmAI tools to convert
 * @param ctx - Run context for execution
 * @returns Array of LlamaIndex tool definitions
 */
export function toLlamaIndexTools<T extends Tool<unknown, unknown>[]>(
  tools: T,
  ctx: RunContext
): LlamaIndexToolDefinition[] {
  return tools.map((tool) => ({
    name: tool.name,
    description: tool.description,
    parameters: zodToJsonSchema(tool.inputSchema),
    fn: async (input: Record<string, unknown>) => {
      const result = await tool.execute(input, ctx);
      return JSON.stringify(result);
    },
  }));
}

/**
 * Create LlamaIndex FunctionTool instances.
 *
 * This function attempts to dynamically import the package.
 * If it's not installed, it throws an error.
 *
 * Usage with LlamaIndex.ts:
 * ```ts
 * import { FunctionTool, OpenAIAgent } from 'llamaindex';
 *
 * const tools = await createLlamaIndexTools(registry.list(), ctx);
 * const agent = new OpenAIAgent({ tools });
 * ```
 */
export async function createLlamaIndexTools<T extends Tool<unknown, unknown>[]>(
  tools: T,
  ctx: RunContext
): Promise<unknown[]> {
  try {
    const { FunctionTool } = await import('llamaindex');

    return tools.map((tool) =>
      FunctionTool.from(
        async (input: Record<string, unknown>) => {
          const result = await tool.execute(input, ctx);
          return JSON.stringify(result);
        },
        {
          name: tool.name,
          description: tool.description,
          parameters: zodToJsonSchema(tool.inputSchema),
        }
      )
    );
  } catch (e) {
    throw new Error('Failed to import llamaindex. Make sure it is installed: npm install llamaindex');
  }
}
