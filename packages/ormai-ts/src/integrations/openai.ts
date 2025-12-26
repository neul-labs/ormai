/**
 * OpenAI SDK integration.
 *
 * Converts OrmAI tools to OpenAI function calling format.
 */

import { zodToJsonSchema } from 'zod-to-json-schema';
import type { RunContext } from '../core/context.js';
import type { Tool } from '../tools/base.js';

/**
 * OpenAI function definition.
 */
export interface OpenAIFunction {
  name: string;
  description: string;
  parameters: Record<string, unknown>;
}

/**
 * OpenAI tool definition (newer format).
 */
export interface OpenAIToolDefinition {
  type: 'function';
  function: OpenAIFunction;
}

/**
 * Convert OrmAI tools to OpenAI function definitions.
 *
 * @param tools - OrmAI tools to convert
 * @returns Array of OpenAI function definitions
 */
export function toOpenAIFunctions<T extends Tool<unknown, unknown>[]>(
  tools: T
): OpenAIFunction[] {
  return tools.map((tool) => ({
    name: tool.name,
    description: tool.description,
    parameters: zodToJsonSchema(tool.inputSchema),
  }));
}

/**
 * Convert OrmAI tools to OpenAI tool definitions (newer format).
 *
 * @param tools - OrmAI tools to convert
 * @returns Array of OpenAI tool definitions
 */
export function toOpenAITools<T extends Tool<unknown, unknown>[]>(
  tools: T
): OpenAIToolDefinition[] {
  return tools.map((tool) => ({
    type: 'function' as const,
    function: {
      name: tool.name,
      description: tool.description,
      parameters: zodToJsonSchema(tool.inputSchema),
    },
  }));
}

/**
 * Execute a tool call from OpenAI's response.
 *
 * @param tools - Available OrmAI tools
 * @param functionName - Name of the function to call
 * @param functionArgs - Arguments from OpenAI (as JSON string)
 * @param ctx - Run context
 * @returns Tool execution result as string
 */
export async function executeOpenAIFunctionCall<T extends Tool<unknown, unknown>[]>(
  tools: T,
  functionName: string,
  functionArgs: string,
  ctx: RunContext
): Promise<string> {
  const tool = tools.find((t) => t.name === functionName);
  if (!tool) {
    throw new Error(`Unknown function: ${functionName}`);
  }

  const args = JSON.parse(functionArgs);
  const result = await tool.execute(args, ctx);
  return JSON.stringify(result);
}

/**
 * Create a function to handle OpenAI tool calls.
 *
 * Usage with OpenAI SDK:
 * ```ts
 * import OpenAI from 'openai';
 *
 * const client = new OpenAI();
 * const tools = toOpenAITools(registry.list());
 * const handleToolCall = createOpenAIToolHandler(registry.list(), ctx);
 *
 * const response = await client.chat.completions.create({
 *   model: 'gpt-4o',
 *   messages: [...],
 *   tools,
 * });
 *
 * for (const toolCall of response.choices[0].message.tool_calls ?? []) {
 *   const result = await handleToolCall(
 *     toolCall.function.name,
 *     toolCall.function.arguments
 *   );
 *   // Add tool response to messages...
 * }
 * ```
 */
export function createOpenAIToolHandler<T extends Tool<unknown, unknown>[]>(
  tools: T,
  ctx: RunContext
): (functionName: string, functionArgs: string) => Promise<string> {
  return (functionName, functionArgs) =>
    executeOpenAIFunctionCall(tools, functionName, functionArgs, ctx);
}
