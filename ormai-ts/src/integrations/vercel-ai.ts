/**
 * Vercel AI SDK integration.
 *
 * Converts OrmAI tools to Vercel AI SDK format.
 */

import { zodToJsonSchema } from 'zod-to-json-schema';
import type { RunContext } from '../core/context.js';
import type { Tool } from '../tools/base.js';

/**
 * Vercel AI SDK tool definition.
 */
export interface VercelAITool<Input, Output> {
  description: string;
  parameters: Record<string, unknown>;
  execute: (input: Input) => Promise<Output>;
}

/**
 * Convert OrmAI tools to Vercel AI SDK format.
 *
 * @param tools - OrmAI tools to convert
 * @param ctx - Run context for execution
 * @returns Object with tool definitions for Vercel AI SDK
 */
export function toVercelAITools<T extends Tool<unknown, unknown>[]>(
  tools: T,
  ctx: RunContext
): Record<string, VercelAITool<unknown, unknown>> {
  const result: Record<string, VercelAITool<unknown, unknown>> = {};

  for (const tool of tools) {
    result[tool.name] = {
      description: tool.description,
      parameters: zodToJsonSchema(tool.inputSchema),
      execute: async (input: unknown) => {
        return tool.execute(input, ctx);
      },
    };
  }

  return result;
}

/**
 * Create a Vercel AI SDK compatible tools object.
 *
 * Usage with Vercel AI SDK:
 * ```ts
 * import { generateText } from 'ai';
 *
 * const tools = createVercelAITools(registry.list(), ctx);
 *
 * const result = await generateText({
 *   model: openai('gpt-4o'),
 *   tools,
 *   prompt: 'Query the database for all users',
 * });
 * ```
 */
export function createVercelAITools<T extends Tool<unknown, unknown>[]>(
  tools: T,
  ctx: RunContext
): Record<string, VercelAITool<unknown, unknown>> {
  return toVercelAITools(tools, ctx);
}
